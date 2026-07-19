#!/usr/bin/env python
"""H4c — métrica de identidad comparativa sobre videos (sin ground truth).

Corre el pipeline de percepción+slots sobre un video con 3 configuraciones:
  a) bytetrack           (el baseline del MVP)
  b) botsort_reid        (capa 1+2: BoT-SORT + ReID + buffer 120)
  c) botsort_reid+reasoc (capas 1+2+3: + reasociación de slots)
y reporta por configuración:
  - unique_track_ids : IDs únicos que emitió el tracker (menos = mejor)
  - slot_switches    : asignaciones de slot nuevo (slot_reset=True con detección)
  - rebinds          : reasociaciones logradas por la capa 3
  - slot_switches_per_min (métrica principal; proxy documentado SIN ground truth)

Uso: python scripts/eval_tracking.py video1.mp4 [video2.mp4 …]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from harmocap.identity import SlotManager  # noqa: E402
from harmocap.perception import PoseBackend  # noqa: E402

CONFIGS = {
    "a_bytetrack": {"tracker": "bytetrack.yaml", "reacq": False},
    "b_botsort_reid": {"tracker": str(REPO / "configs/tracker_group.yaml"),
                       "reacq": False},
    "c_botsort_reid_reasoc": {"tracker": str(REPO / "configs/tracker_group.yaml"),
                              "reacq": True},
}


def eval_config(video: Path, name: str, cfg: dict) -> dict:
    ident = yaml.safe_load((REPO / "configs" / "identity.yaml").read_text())
    rq = dict(ident.get("reacquisition", {}))
    rq["enabled"] = cfg["reacq"]
    backend = PoseBackend(
        realtime_checkpoint=str(REPO / "outputs/harmocap-m-pose-ft2.engine"),
        fallback_checkpoint="harmocap-m-pose-ft2.pt",
        imgsz=640, conf=0.05, max_det=300, tracker=cfg["tracker"])
    slots = SlotManager(
        max_slots=8,
        occlusion_grace_ms=ident["slot"]["occlusion_grace_ms"],
        release_timeout_ms=ident["slot"]["release_timeout_ms"],
        acquire_rule=ident["slot"]["acquire_rule"],
        tombstone_repeat_frames=ident["slot"]["tombstone_repeat_frames"],
        reacquisition=rq)

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    ids_seen: set[int] = set()
    slot_switches = frames = 0
    t_us = 0
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1
        t_us += int(1e6 / fps)
        dets, _raw, _speed, (fw, fh) = backend.track_frame(frame)
        ids_seen.update(d.track_id for d in dets)
        for ev in slots.update(dets, t_us, aspect=fw / fh if fh else 16 / 9):
            if ev.slot_reset and ev.detection is not None and not ev.rebound:
                slot_switches += 1
    cap.release()
    minutes = frames / fps / 60.0
    return {"unique_track_ids": len(ids_seen),
            "slot_switches": slot_switches,
            "rebinds": slots.rebind_count,
            "slot_switches_per_min": round(slot_switches / max(minutes, 1e-6), 1),
            "frames": frames, "proc_fps": round(frames / (time.time() - t0), 1)}


def main() -> int:
    videos = [Path(a) for a in sys.argv[1:]]
    assert videos, "uso: eval_tracking.py <video> [...]"
    out: dict = {}
    for v in videos:
        out[v.name] = {}
        for name, cfg in CONFIGS.items():
            print(f"[track-eval] {v.name} / {name} …", flush=True)
            r = eval_config(v, name, cfg)
            out[v.name][name] = r
            print(f"[track-eval]   ids={r['unique_track_ids']} "
                  f"switches/min={r['slot_switches_per_min']} "
                  f"rebinds={r['rebinds']} proc={r['proc_fps']}fps", flush=True)
    dest = REPO / "reports" / "20260717_e71e14a" / "tracking_identity_eval.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"[track-eval] → {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
