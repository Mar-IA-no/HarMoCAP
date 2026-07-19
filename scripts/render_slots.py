#!/usr/bin/env python
"""H4c ítem 5 — render de inspección visual: bbox + slot_id estable por color.

Genera un mp4 por configuración (a_bytetrack vs c_botsort_reid_reasoc) para
verificar a ojo el caso señalado por el usuario: dos personas que se cruzan /
salen y vuelven deben CONSERVAR su número de slot (color estable).

Uso: python scripts/render_slots.py <video> [--out DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from harmocap.identity import SlotManager  # noqa: E402
from harmocap.perception import PoseBackend  # noqa: E402

from eval_tracking import CONFIGS  # noqa: E402  (mismas 3 configs)

COLORS = [(66, 133, 244), (52, 168, 83), (251, 188, 5), (234, 67, 53),
          (171, 71, 188), (0, 172, 193), (255, 112, 67), (158, 157, 36)]


def render(video: Path, name: str, cfg: dict, out_dir: Path) -> Path:
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
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dst = out_dir / f"{video.stem}__slots_{name}.mp4"
    vw = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    t_us = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t_us += int(1e6 / fps)
        dets, _raw, _speed, _wh = backend.track_frame(frame)
        for ev in slots.update(dets, t_us, aspect=w / h if h else 16 / 9):
            if ev.detection is None:
                continue
            cx, cy, bw, bh = ev.detection.bbox_xywhn
            x1, y1 = int((cx - bw / 2) * w), int((cy - bh / 2) * h)
            x2, y2 = int((cx + bw / 2) * w), int((cy + bh / 2) * h)
            color = COLORS[ev.slot_id % 8]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            tag = f"S{ev.slot_id}" + ("*" if ev.rebound else "")
            cv2.putText(frame, tag, (x1, max(y1 - 8, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)
        cv2.putText(frame, name, (12, h - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        vw.write(frame)
    cap.release()
    vw.release()
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path,
                    default=REPO / "Biblioteca/test/two_slots_render")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("a_bytetrack", "c_botsort_reid_reasoc"):
        print(f"[render-slots] {args.video.name} / {name} …", flush=True)
        dst = render(args.video, name, CONFIGS[name], args.out)
        print(f"[render-slots] → {dst}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
