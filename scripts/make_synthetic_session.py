#!/usr/bin/env python
"""Genera la sesión sintética determinista + fixtures de cobertura (plan M4).

La sesión de ejemplo del kit es SINTÉTICA (addendum #4): una trayectoria real
es dato conductual y no se publica sin consentimiento. Este script anima un
esqueleto paramétrico (sin aleatoriedad) y lo pasa por el PIPELINE REAL de
suavizado+features, así el .jsonl de ejemplo es 100 % coherente con el
contrato y sirve además de verificación e2e (r2 #16):
  fase A reposo (qom baja) → fase B brazos arriba (expansion sube) →
  fase C inclinación lateral (verticality baja) → fase D balanceo rápido.

Fixtures deterministas (r3 #14): lifecycle (oclusión→held/invalid→tombstone),
calibración (calibrating→frozen) y reinicio de stream (addendum #1).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from harmocap.crowd import CrowdAggregator  # noqa: E402
from harmocap.features import CalibrationManager, FeatureExtractor  # noqa: E402
from harmocap.interface.recorder import frame_to_dict  # noqa: E402
from harmocap.interface import osc_codec  # noqa: E402
from harmocap.schema import (  # noqa: E402
    KeypointData, MovementFrame, N_FEATURES, KpState, PersonState,
)
from harmocap.smoothing import KeypointSmoother  # noqa: E402

FPS = 30
DT_US = 1_000_000 // FPS
FRAME_W, FRAME_H = 1280, 720
STREAM_ID = "aabbccdd00112233"           # determinista (sesión de ejemplo)
STREAM_ID_2 = "eeff445566778899"         # para el fixture de reinicio
MODEL_ID = "synthetic"
CONFIG_HASH = "0" * 32


def skeleton(t: float, *, arms_up: float = 0.0, lean: float = 0.0,
             sway: float = 0.0) -> list[tuple[float, float, float]]:
    """Esqueleto COCO-17 paramétrico en coords isotrópicas (cámara frontal).

    arms_up ∈ [0,1]: 0 brazos abajo, 1 brazos en V arriba.
    lean: inclinación lateral del eje corporal en radianes.
    sway: amplitud del balanceo horizontal de brazos (anima con t).
    """
    cx = 0.89 + 0.02 * math.sin(2 * math.pi * 0.2 * t)   # centro ≈ w/h/2
    hip_y, sho_y, head_y = 0.62, 0.34, 0.18
    torso_half_w, hip_half_w = 0.10, 0.075

    def rot(x, y, ox, oy):
        c, s = math.cos(lean), math.sin(lean)
        dx, dy = x - ox, y - oy
        return ox + c * dx - s * dy, oy + s * dx + c * dy

    mid_hip = (cx, hip_y)
    pts = {}
    pts["l_hip"], pts["r_hip"] = (cx - hip_half_w, hip_y), (cx + hip_half_w, hip_y)
    pts["l_sho"], pts["r_sho"] = (cx - torso_half_w, sho_y), (cx + torso_half_w, sho_y)
    pts["nose"] = (cx, head_y)
    pts["l_eye"], pts["r_eye"] = (cx - 0.02, head_y - 0.015), (cx + 0.02, head_y - 0.015)
    pts["l_ear"], pts["r_ear"] = (cx - 0.04, head_y), (cx + 0.04, head_y)

    # brazos: interpolan entre colgando y en V, con balanceo sway
    swing = sway * math.sin(2 * math.pi * 1.2 * t)
    for side, sgn in (("l", -1), ("r", 1)):
        sho = pts[f"{side}_sho"]
        down_elb = (sho[0] + sgn * 0.02 + swing, sho[1] + 0.14)
        down_wri = (sho[0] + sgn * 0.03 + swing * 1.6, sho[1] + 0.27)
        up_elb = (sho[0] + sgn * 0.09, sho[1] - 0.10)
        up_wri = (sho[0] + sgn * 0.15, sho[1] - 0.24)
        lerp = lambda a, b: (a[0] + (b[0] - a[0]) * arms_up,
                             a[1] + (b[1] - a[1]) * arms_up)
        pts[f"{side}_elb"] = lerp(down_elb, up_elb)
        pts[f"{side}_wri"] = lerp(down_wri, up_wri)

    for side, sgn in (("l", -1), ("r", 1)):
        hip = pts[f"{side}_hip"]
        pts[f"{side}_kne"] = (hip[0] + sgn * 0.01, hip[1] + 0.16)
        pts[f"{side}_ank"] = (hip[0] + sgn * 0.015, hip[1] + 0.33)

    order = ["nose", "l_eye", "r_eye", "l_ear", "r_ear", "l_sho", "r_sho",
             "l_elb", "r_elb", "l_wri", "r_wri", "l_hip", "r_hip",
             "l_kne", "r_kne", "l_ank", "r_ank"]
    out = []
    for k in order:
        x, y = rot(*pts[k], *mid_hip) if lean else pts[k]
        out.append((x, y, 0.92))
    return out


class SyntheticRunner:
    """Pasa keypoints sintéticos por el pipeline real (smoother+features).

    Multi-slot (contrato 1.1): un smoother+extractor POR SLOT, como el pipeline.
    """

    def __init__(self, stream_id: str):
        self.cfg_feat = {"velocity_ms": 120, "accel_ms": 200, "jerk_ms": 300,
                         "aggregate_ms": 1000, "qom_ms": 400}
        fallback = {"torso_height_norm": 0.28, "vmax_hand": 3.0,
                    "vmax_center": 1.5, "jerk_ref": 40.0, "energy_ref": 4.0,
                    "accel_ref": 8.0}
        self.stream_id = stream_id
        self.calib = CalibrationManager(fallback, period_ms=3000)
        self._smoothers: dict[int, KeypointSmoother] = {}
        self._extractors: dict[int, FeatureExtractor] = {}
        self.contract_id = osc_codec.contract_id_from_manifest(
            json.loads((REPO / "schemas" / "osc_contract.v1.json").read_text()))
        self.t_us = 1_000_000            # arranque del reloj monótono sintético
        self.frame_id = 0
        self.crowd_agg = CrowdAggregator()

    def _slot(self, sid: int):
        if sid not in self._smoothers:
            self._smoothers[sid] = KeypointSmoother()
            self._extractors[sid] = FeatureExtractor(self.cfg_feat, self.calib)
        return self._smoothers[sid], self._extractors[sid]

    def frame_multi(self, slots: dict, *, focused_slot: int = 0,
                    tombstones: set[int] = frozenset(),
                    drop_conf: set[int] = frozenset(),
                    extra_raw_boxes: list | None = None) -> dict:
        """slots: {slot_id: raw_kps}. Genera un frame multi-persona."""
        self.t_us += DT_US
        self.frame_id += 1
        persons = []
        calib_done = False
        for sid in sorted(slots):
            raw = slots[sid]
            smoother, extractor = self._slot(sid)
            kps = [(x, y, 0.05 if i in drop_conf else c)
                   for i, (x, y, c) in enumerate(raw)]
            sm = smoother.update(kps, self.t_us)
            if not calib_done:
                torso = extractor._torso_height(
                    [(s[0], s[1]) for s in sm], [s[3] for s in sm])
                self.calib.observe(torso, self.t_us, self.frame_id)
                calib_done = True
            vals, states = extractor.extract(sm, self.t_us)
            kd = tuple(KeypointData(x=s[0], y=s[1], conf=s[2], state=s[3],
                                    age_frames=s[4], age_us=s[5]) for s in sm)
            xs = [k.x for k in kd]; ys = [k.y for k in kd]
            aspect = FRAME_W / FRAME_H
            bbox = (sum(xs) / len(xs) / aspect, sum(ys) / len(ys),
                    (max(xs) - min(xs)) / aspect * 1.15,
                    (max(ys) - min(ys)) * 1.15)
            persons.append(PersonState(
                slot_id=sid, present=True, keypoints=kd, bbox=bbox,
                features=tuple(vals), feature_states=tuple(states),
                provisional=self.calib.profile.state == "calibrating",
                focused=sid == focused_slot))
        for sid in sorted(tombstones):
            persons.append(PersonState(
                slot_id=sid, present=False, keypoints=(),
                bbox=(0.0, 0.0, 0.0, 0.0), features=(0.0,) * N_FEATURES,
                feature_states=(int(KpState.INVALID),) * N_FEATURES))
        mf = MovementFrame(
            stream_id=self.stream_id, captured_frame_id=self.frame_id,
            captured_at_us=self.t_us, processed_at_us=self.t_us + 8_000,
            frame_w=FRAME_W, frame_h=FRAME_H, fps=float(FPS),
            calibration_generation=self.calib.profile.generation,
            calibration_state=self.calib.profile.state, persons=tuple(persons))
        raw = [tuple(p.bbox) for p in persons if p.present]
        raw += [tuple(b) for b in (extra_raw_boxes or [])]
        crowd = self.crowd_agg.update(raw, self.t_us, aspect=FRAME_W / FRAME_H)
        return frame_to_dict(mf, self.calib.profile,
                             contract_id=self.contract_id,
                             config_hash=CONFIG_HASH, model_id=MODEL_ID,
                             crowd=crowd)

    def frame(self, raw_kps, *, present=True, drop_conf: set[int] = frozenset()
              ) -> dict:
        """Compat una-persona: slot 0 focal, o tombstone del slot 0."""
        if present and raw_kps is not None:
            return self.frame_multi({0: raw_kps}, focused_slot=0,
                                    drop_conf=drop_conf)
        return self.frame_multi({}, tombstones={0})


def write_jsonl(path: Path, frames: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for d in frames:
            f.write(json.dumps(d, separators=(",", ":"), allow_nan=False) + "\n")
    print(f"  {path}  ({len(frames)} frames)")


def main() -> int:
    print("[synthetic] sesión de ejemplo (4 fases, 24 s)…")
    r = SyntheticRunner(STREAM_ID)
    frames = []
    for i in range(FPS * 6):    # A: reposo (calibra y congela a los 3 s)
        frames.append(r.frame(skeleton(i / FPS)))
    for i in range(FPS * 6):    # B: brazos suben → expansion↑
        u = min(1.0, i / (FPS * 2))
        frames.append(r.frame(skeleton((i + 180) / FPS, arms_up=u)))
    for i in range(FPS * 3):    # C1: inclinación lateral → verticality↓
        lean = 0.6 * math.sin(2 * math.pi * 0.3 * i / FPS)
        frames.append(r.frame(skeleton((i + 360) / FPS, arms_up=1.0, lean=lean)))
    for i in range(FPS * 3):    # C2: inversión → verticality NEGATIVA.
        # Hallazgo de campo (bitácora Nico S14): verticality es el ÚNICO rango
        # firmado (-1..1) y ningún fixture lo ejercitaba — un consumidor con
        # bounds (0,1) pasaba todos los tests y explotaba con datos vivos.
        lean = min(1.0, i / (FPS * 1.5)) * 2.9
        frames.append(r.frame(skeleton((i + 450) / FPS, lean=lean)))
    for i in range(FPS * 6):    # D: balanceo rápido de brazos → qom/vel↑
        frames.append(r.frame(skeleton((i + 540) / FPS, sway=0.10)))
    # invariante: la sesión DEBE ejercitar verticality negativa (ver C2)
    min_vert = min(p["features"][9] for f in frames for p in f.get("persons", [])
                   if p.get("features") and p["features"][9] is not None)
    assert min_vert < -0.2, f"C2 no produjo verticality negativa ({min_vert})"
    print(f"[synthetic] min verticality en sesión: {min_vert:.2f} (rango firmado ejercitado)")
    write_jsonl(REPO / "examples" / "session_v1.jsonl", frames)

    print("[synthetic] fixture lifecycle (oclusión→held/invalid→tombstone)…")
    r = SyntheticRunner(STREAM_ID)
    fx = []
    for i in range(FPS * 4):
        fx.append(r.frame(skeleton(i / FPS)))
    for i in range(FPS * 1):    # oclusión parcial: muñeca+codo derechos caen
        fx.append(r.frame(skeleton((i + 120) / FPS), drop_conf={8, 10}))
    for i in range(FPS * 2):    # reaparece
        fx.append(r.frame(skeleton((i + 150) / FPS)))
    for _ in range(15):         # se va: tombstones repetidos (r8 #1)
        fx.append(r.frame(None, present=False))
    write_jsonl(REPO / "examples" / "fixtures" / "lifecycle.jsonl", fx)

    print("[synthetic] fixture calibración (calibrating→frozen visible)…")
    r = SyntheticRunner(STREAM_ID)
    fx = [r.frame(skeleton(i / FPS)) for i in range(FPS * 5)]
    write_jsonl(REPO / "examples" / "fixtures" / "calibration.jsonl", fx)

    print("[synthetic] fixture reinicio de stream (addendum #1)…")
    r1 = SyntheticRunner(STREAM_ID)
    fx = [r1.frame(skeleton(i / FPS)) for i in range(FPS * 2)]
    r2 = SyntheticRunner(STREAM_ID_2)   # proceso reiniciado: frame_id vuelve a 1
    fx += [r2.frame(skeleton(i / FPS)) for i in range(FPS * 2)]
    write_jsonl(REPO / "examples" / "fixtures" / "stream_restart.jsonl", fx)

    print("[synthetic] fixture dos personas + cambio de foco (contrato 1.1)…")
    r = SyntheticRunner(STREAM_ID)
    fx = []
    def two(t, focus):
        # persona 0 a la izquierda (quieta), persona 1 a la derecha (balanceando)
        p0 = [(x - 0.45, y, c) for x, y, c in skeleton(t)]
        p1 = [(x + 0.45, y, c) for x, y, c in skeleton(t, sway=0.08)]
        return r.frame_multi({0: p0, 1: p1}, focused_slot=focus)
    for i in range(FPS * 4):            # primera mitad: foco en slot 0
        fx.append(two(i / FPS, 0))
    for i in range(FPS * 4):            # segunda mitad: foco en slot 1
        fx.append(two((i + 120) / FPS, 1))
    write_jsonl(REPO / "examples" / "fixtures" / "two_persons.jsonl", fx)

    print("[synthetic] fixture multitud simulada (contrato 1.2)…")
    r = SyntheticRunner(STREAM_ID)
    fx = []
    for i in range(FPS * 4):
        t = i / FPS
        # 24 cajas fantasma orbitando (masa) + 1 esqueleto real
        boxes = []
        for k in range(24):
            ang = 2 * math.pi * (k / 24 + 0.05 * t)
            boxes.append((0.5 + 0.3 * math.cos(ang), 0.5 + 0.3 * math.sin(ang),
                          0.05, 0.12))
        fx.append(r.frame_multi({0: skeleton(t)}, focused_slot=0,
                                extra_raw_boxes=boxes))
    write_jsonl(REPO / "examples" / "fixtures" / "crowd.jsonl", fx)

    print("[synthetic] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
