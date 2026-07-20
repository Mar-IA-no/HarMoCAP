#!/usr/bin/env python
"""H6-F1 — render de evidencia de la masa por densidad (A+C).

Por cada video: mapa de densidad en falso color + barras de masa PRESENTE y
masa ACTIVA (normalizadas por percentil rodante) + el conteo de detección para
comparar. Sirve para ver si las dos señales se separan cuando deben: mucha
gente quieta debería dar presente alto / activa baja; un pogo, ambas altas.

Uso: python scripts/render_density.py video1.mp4 [...] [--model qnrf_n]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from harmocap.density import DensityBackend  # noqa: E402
from harmocap.density_crowd import DensityCrowdAggregator  # noqa: E402
from harmocap.perception import PoseBackend  # noqa: E402


def _bar(frame, x, y, w, h, frac, color, label):
    cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 60, 60), -1)
    cv2.rectangle(frame, (x, y + int(h * (1 - frac))), (x + w, y + h), color, -1)
    cv2.putText(frame, label, (x - 4, y + h + 18), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (255, 255, 255), 1)


def render(video: Path, backend: DensityBackend, out_dir: Path) -> Path:
    yolo = PoseBackend(
        realtime_checkpoint=str(REPO / "outputs/harmocap-m-pose-ft2.engine"),
        fallback_checkpoint="harmocap-m-pose-ft2.pt", imgsz=1280, conf=0.05,
        max_det=300, tracker="bytetrack.yaml")
    agg = DensityCrowdAggregator()
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dst = out_dir / f"{video.stem}__densidad.mp4"
    vw = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    t_us = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t_us += int(1e6 / fps)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        dm = backend.infer(rgb)
        c = agg.update(dm, rgb, t_us)
        _dets, raw, _s, _wh = yolo.track_frame(frame)

        hm = cv2.resize(dm, (w, h), interpolation=cv2.INTER_LINEAR)
        hm = np.clip(hm / (hm.max() + 1e-9), 0, 1)
        hm = cv2.applyColorMap((hm * 255).astype(np.uint8), cv2.COLORMAP_JET)
        frame = cv2.addWeighted(frame, 0.6, hm, 0.4, 0)

        _bar(frame, w - 90, 20, 24, 120, c["mass_present"], (120, 200, 120), "pres")
        _bar(frame, w - 45, 20, 24, 120, c["mass_active"], (80, 140, 255), "activ")
        txt = [f"densidad {c['density_count_raw']:.0f}", f"YOLO {len(raw)}",
               f"disp {c['dispersion']:.2f}"]
        for i, s in enumerate(txt):
            cv2.putText(frame, s, (12, 26 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 0, 0), 4)
            cv2.putText(frame, s, (12, 26 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
        vw.write(frame)
    cap.release(); vw.release()
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--model", default="qnrf_n")
    ap.add_argument("--out", type=Path, default=REPO / "Biblioteca/test/densidad_render")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    backend = DensityBackend(REPO / "outputs" / "density" / f"zip_{args.model}.onnx")
    print(f"[densidad] backend {args.model} · provider {backend.provider}")
    for v in args.videos:
        print(f"[densidad] {v.name} …", flush=True)
        dst = render(v, backend, args.out)
        print(f"[densidad]   → {dst.name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
