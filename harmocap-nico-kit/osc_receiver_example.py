#!/usr/bin/env python
"""Receptor OSC de referencia — decodifica el contrato HarMoCAP v1.

SOLO biblioteca estándar (socket + osc_codec). Implementa las reglas que TODO
receptor debe cumplir (INTERFACE_SPEC.md):
  gating por (contract_id, generación, hash) · scope por stream_id ·
  descarte monotónico por bundle_seq · lease de presencia · sentinel de
  features inválidas · manejo de tombstones.

Uso:
    python osc_receiver_example.py [--port 9000] [--quiet]

Reemplazá `on_movement()` por tu mapeo movimiento→sonido.
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # robusto ante -I
import osc_codec  # noqa: E402

LEASE_MS = 2000
STATE_NAMES = {0: "obs", 1: "held", 2: "inv"}


class ContractReceiver:
    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.stream_id: str | None = None
        self.hello: dict | None = None
        self.calibration: dict | None = None
        self.last_seq = -1
        self.last_data_ms: dict[int, float] = {}   # slot → último dato
        self.stats = {"bundles": 0, "dropped_old": 0, "gated": 0,
                      "stream_resets": 0, "lost": 0}

    # ------------------------------------------------------------------ estado
    def _reset_stream(self, stream_id: str) -> None:
        self.stream_id = stream_id
        self.hello = None
        self.calibration = None
        self.last_seq = -1
        self.last_data_ms.clear()
        self.stats["stream_resets"] += 1
        print(f"[receiver] stream nuevo: {stream_id} — estado reseteado")

    def _gated(self) -> bool:
        """Gating por tupla: necesita /hello Y /calibration coincidentes."""
        if self.hello is None or self.calibration is None:
            return True
        return (self.hello["calibration_generation"] != self.calibration["generation"]
                or self.hello["calibration_hash"] != self.calibration["hash"])

    # ------------------------------------------------------------------ ingest
    def handle_datagram(self, data: bytes) -> None:
        try:
            msgs = osc_codec.decode_bundle(data)
        except Exception as e:
            print(f"[receiver] datagrama inválido: {e}", file=sys.stderr)
            return
        addr0 = msgs[0][0]
        if addr0.endswith("/hello"):
            self._on_hello(msgs[0][1])
        elif addr0.endswith("/calibration"):
            self._on_calibration(msgs[0][1])
        elif addr0.endswith("/crowd"):
            self._on_crowd(msgs[0][1])
        elif addr0.endswith("/meta"):
            self._on_frame(msgs)

    def _on_hello(self, a: list) -> None:
        stream_id = a[0]
        if stream_id != self.stream_id:
            self._reset_stream(stream_id)
        self.hello = {
            "schema_version": a[1], "feature_set_version": a[2],
            "producer_version": a[3], "model_id": a[4], "config_hash": a[5],
            "contract_id": a[6], "layout_version": a[7],
            "calibration_generation": a[8], "calibration_state": a[9],
            "calibration_hash": a[10], "effective_from": a[11],
            "frame_w": a[12], "frame_h": a[13],
        }

    def _on_calibration(self, a: list) -> None:
        stream_id = a[0]
        if stream_id != self.stream_id:
            self._reset_stream(stream_id)
        params_blob = a[4]
        h = osc_codec.calibration_hash(params_blob)
        if h != a[2]:
            print(f"[receiver] calibration_hash NO coincide: rechazada", file=sys.stderr)
            return
        self.calibration = {"generation": a[1], "hash": a[2],
                            "effective_from": a[3],
                            "params": osc_codec.unpack_calibration_params(params_blob)}

    def _on_frame(self, msgs: list) -> None:
        meta = msgs[0][1]
        stream_id, frame_id, seq = meta[0], meta[1], meta[2]
        if stream_id != self.stream_id:
            self._reset_stream(stream_id)      # scope por stream_id
        if seq <= self.last_seq:
            self.stats["dropped_old"] += 1     # descarte monotónico
            return
        if self.last_seq >= 0 and seq > self.last_seq + 1:
            self.stats["lost"] += seq - self.last_seq - 1   # pérdida UDP medida
        self.last_seq = seq
        if self._gated():
            self.stats["gated"] += 1           # sin handshake completo: no consumir
            return
        self.stats["bundles"] += 1

        persons: dict[int, dict] = {}
        for addr, args in msgs[1:]:
            parts = addr.split("/")            # /harmocap/v1/person/{slot}/campo
            slot, field = int(parts[4]), parts[5]
            p = persons.setdefault(slot, {})
            if field == "present":
                p["present"] = bool(args[0])
            elif field == "focused":
                p["focused"] = bool(args[0])   # contrato 1.1: marcador de foco
            elif field == "keypoints":
                p["keypoints"] = osc_codec.unpack_keypoints(args[0])
            elif field == "kp_state":
                p["kp_state"] = osc_codec.unpack_kp_state(args[0])
            elif field == "bbox":
                p["bbox"] = args
            elif field == "features":
                p["features"] = osc_codec.unpack_features(args[0])
            elif field == "feat_state":
                p["feat_state"] = osc_codec.unpack_feat_state(args[0])

        now_ms = time.monotonic() * 1000.0
        for slot, p in persons.items():
            if p.get("present"):
                self.last_data_ms[slot] = now_ms
                self.on_movement(slot, p, meta)
            else:
                self.last_data_ms.pop(slot, None)
                self.on_absent(slot)
        # lease: slots callados > LEASE_MS se consideran ausentes
        for slot in [s for s, t in self.last_data_ms.items()
                     if now_ms - t > LEASE_MS]:
            del self.last_data_ms[slot]
            self.on_absent(slot)

    def _on_crowd(self, a: list) -> None:
        """Contrato 1.2: agregados de multitud (stream, frame, seq, 8 campos).

        IMPORTANTE: /crowd también consume bundle_seq — hay que contabilizarlo
        en el descarte monotónico o cada crowd parecería un bundle perdido.
        """
        if a[0] != self.stream_id:
            self._reset_stream(a[0])
        seq = a[2]
        if seq <= self.last_seq:
            self.stats["dropped_old"] += 1
            return
        if self.last_seq >= 0 and seq > self.last_seq + 1:
            self.stats["lost"] += seq - self.last_seq - 1
        self.last_seq = seq
        if self._gated():
            self.stats["gated"] += 1   # crowd TAMBIÉN gatea por handshake
            return
        self.stats["bundles"] += 1
        # el orden de los campos lo fija osc_codec.CROWD_FIELDS (contrato 1.4)
        self.on_crowd(dict(zip(osc_codec.CROWD_FIELDS, a[3:])))

    def on_crowd(self, crowd: dict) -> None:
        """REEMPLAZAR: agregados de multitud (la masa como UN instrumento).

        1.3: crowd_tempo_bpm/beat_phase/conf (pulso de la masa; 0 = desconocido).
        1.4: mass_present/mass_active (masa por densidad, SOLO en modo masa, 0 en
        grupo): present = toda la gente en cuadro; active = cuánta se mueve.
        Escala relativa a la sesión, no absoluta."""
        if not self.quiet:
            print(f"[crowd] n={crowd['crowd_count']} qom={crowd['crowd_qom']:.2f} "
                  f"densidad={crowd['density']:.2f} disp={crowd['dispersion']:.2f} "
                  f"masa_pres={crowd['mass_present']:.2f} masa_activa={crowd['mass_active']:.2f}")

    # ------------------------------------------------------------- tu mapeo
    def on_movement(self, slot: int, p: dict, meta: list) -> None:
        """REEMPLAZAR: acá va tu mapeo movimiento→sonido."""
        if self.quiet:
            return
        feats, fstates = p["features"], p["feat_state"]
        # regla del sentinel: ignorar features con estado invalid (2)
        shown = " ".join(
            f"{osc_codec_feature_name(i)}={v:.2f}" if s != 2 else
            f"{osc_codec_feature_name(i)}=--"
            for i, (v, s) in enumerate(zip(feats, fstates)) if i in (0, 2, 9))
        star = "★" if p.get("focused") else " "
        print(f"[slot {slot}]{star} frame={meta[1]} seq={meta[2]} {shown}")

    def on_absent(self, slot: int) -> None:
        if not self.quiet:
            print(f"[slot {slot}] AUSENTE (tombstone o lease vencido)")


_FEATURE_NAMES = ["qom", "contraction", "expansion", "vel_hand_l", "vel_hand_r",
                  "vel_center", "smoothness_l", "smoothness_r", "symmetry",
                  "verticality", "angle_elbow_l", "angle_elbow_r",
                  "angle_knee_l", "angle_knee_r", "angle_shoulder_l",
                  "angle_shoulder_r", "angle_hip_l", "angle_hip_r",
                  "laban_weight_proxy", "laban_time_proxy", "laban_space_proxy"]


def osc_codec_feature_name(i: int) -> str:
    return _FEATURE_NAMES[i]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--seconds", type=float, default=0,
                    help="0 = correr hasta Ctrl-C")
    args = ap.parse_args()

    rx = ContractReceiver(quiet=args.quiet)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(0.5)
    print(f"[receiver] escuchando osc://{args.host}:{args.port}")
    t0 = time.monotonic()
    try:
        while not args.seconds or time.monotonic() - t0 < args.seconds:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            rx.handle_datagram(data)
    except KeyboardInterrupt:
        pass
    print(f"[receiver] stats: {rx.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
