#!/usr/bin/env python
"""replay — reproduce una sesión .jsonl re-emitiendo OSC (mock para Nico).

SOLO biblioteca estándar + osc_codec (también stdlib). Este archivo se copia
IDÉNTICO al kit portable: permite desarrollar el mapeo movimiento→sonido sin
cámara, sin GPU y sin ultralytics (requisito transversal del plan).

Modo único `capture-timing` (r3 #1, r4 #6): duerme según los Δt monótonos de
captured_at de la grabación y emite bundles con timetag immediately. Gaps de
la grabación se respetan hasta --max-gap-s (default 2 s). Los /hello y
/calibration se emiten al inicio y en rebroadcast ~1 Hz (r5 #2), con el
stream_id de la grabación.

Uso:
    python replay.py examples/session_v1.jsonl [--host 127.0.0.1] [--port 9000]
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

try:                                     # en el kit (archivo plano al lado) —
    import osc_codec  # type: ignore     # SIEMPRE preferir el codec local del kit
except ImportError:                      # en el repo
    from harmocap.interface import osc_codec


def load_session(path: Path) -> list[dict]:
    frames = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                frames.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[replay] línea {line_no} inválida: {e}", file=sys.stderr)
    if not frames:
        raise SystemExit(f"[replay] sesión vacía: {path}")
    return frames


def frame_to_wire(d: dict, bundle_seq: int, queued_us: int) -> bytes:
    persons_wire = []
    for p in d.get("persons", []):
        if not p.get("present"):
            persons_wire.append({"slot_id": p["slot_id"], "present": False})
            continue
        kps = [(k[0], k[1], k[2]) for k in p["keypoints"]]
        kst = [(s[0], s[1], s[2]) for s in p["kp_state"]]
        persons_wire.append({
            "slot_id": p["slot_id"], "present": True,
            "keypoints_blob": osc_codec.pack_keypoints(kps),
            "kp_state_blob": osc_codec.pack_kp_state(kst),
            "bbox": p["bbox_xywhn"],
            "features_blob": osc_codec.pack_features(
                [0.0 if v is None else v for v in p["features"]]),
            "feat_state_blob": osc_codec.pack_feat_state(p["feat_state"]),
        })
    return osc_codec.build_frame_bundle(
        stream_id=d["stream_id"],
        captured_frame_id=d["captured_frame_id"], bundle_seq=bundle_seq,
        n_persons=d["n_persons"], fps=d["fps"], contract_id=d["contract_id"],
        calibration_generation=d["calibration_generation"],
        calibration_state=d["calibration_state"],
        captured_at_us=d["captured_at_us"], processed_at_us=d["processed_at_us"],
        queued_for_send_at_us=queued_us, persons=persons_wire)


def handshake_bytes(d: dict) -> list[bytes]:
    """(/hello, /calibration) reconstruidos desde la metadata de la grabación."""
    out = []
    params = d.get("calibration_params")
    params_blob = b""
    calib_hash = "0" * 32
    if params:
        order = ["torso_height_norm", "vmax_hand", "vmax_center",
                 "jerk_ref", "energy_ref", "accel_ref"]
        params_blob = osc_codec.pack_calibration_params([params[k] for k in order])
        calib_hash = osc_codec.calibration_hash(params_blob)
    out.append(osc_codec.build_hello(
        stream_id=d["stream_id"], schema_version=d["schema_version"],
        feature_set_version=d["feature_set_version"],
        producer_version=d["producer_version"] + "+replay",
        model_id=d["model_id"], config_hash=d["config_hash"],
        contract_id=d["contract_id"],
        calibration_generation=d["calibration_generation"],
        calibration_state=d["calibration_state"], calib_hash=calib_hash,
        effective_from_frame_id=d.get("calibration_effective_from", 0),
        frame_w=d["frame_w"], frame_h=d["frame_h"]))
    if params:
        out.append(osc_codec.build_calibration(
            stream_id=d["stream_id"], generation=d["calibration_generation"],
            calib_hash=calib_hash,
            effective_from_frame_id=d.get("calibration_effective_from", 0),
            params_blob=params_blob))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("session", type=Path)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--max-gap-s", type=float, default=2.0,
                    help="gap máximo a dormir entre frames de la grabación")
    ap.add_argument("--loop", action="store_true", help="repetir en bucle")
    args = ap.parse_args()

    frames = load_session(args.session)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.host, args.port)
    print(f"[replay] {len(frames)} frames → osc://{args.host}:{args.port} "
          f"(capture-timing; Ctrl-C para cortar)")

    seq = 0
    last_hello = 0.0
    while True:
        prev_cap_us: int | None = None
        for d in frames:
            now = time.monotonic()
            if now - last_hello >= 1.0:               # rebroadcast ~1 Hz
                for pkt in handshake_bytes(d):
                    sock.sendto(pkt, dest)
                last_hello = now
            if prev_cap_us is not None:
                gap = (d["captured_at_us"] - prev_cap_us) / 1e6
                if 0.0 < gap:
                    time.sleep(min(gap, args.max_gap_s))
            prev_cap_us = d["captured_at_us"]
            seq += 1
            sock.sendto(frame_to_wire(d, seq, time.monotonic_ns() // 1000), dest)
        if not args.loop:
            break
    print(f"[replay] fin — {seq} bundles emitidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
