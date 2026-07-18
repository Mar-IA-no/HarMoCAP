#!/usr/bin/env python
"""Barrido OFAT de hiperparámetros de INFERENCIA sobre Biblioteca/test/two.

13 variantes alrededor de la base (conf=0.25, imgsz=640, iou=0.7, max_det=300,
kpt_conf=0.35), render bbox+trackid+esqueleto con caption de config quemado.
Tracker fijo: bytetrack.yaml (TODO resuelto para esta pasada).
Salida: Biblioteca/test/two_sweep/<variante>/<video> + sweep_manifest.json
(args efectivos + detecciones medias/frame + IDs únicos + fps de proceso).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
from ultralytics import YOLO

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "Biblioteca" / "test" / "two"
DST = REPO / "Biblioteca" / "test" / "two_sweep"
CKPT = REPO / "runs" / "20260718_0832_ft2_crowdpose_mixed30" / "weights" / "best.pt"

BASE = dict(conf=0.25, imgsz=640, iou=0.7, max_det=300)
BASE_KPT_CONF = 0.35

# (nombre_variante, overrides_yolo, kpt_conf_dibujo)
VARIANTS = [("base", {}, BASE_KPT_CONF)]
VARIANTS += [(f"conf_{v:.2f}", {"conf": v}, BASE_KPT_CONF)
             for v in (0.05, 0.10, 0.40, 0.60)]
VARIANTS += [(f"imgsz_{v}", {"imgsz": v}, BASE_KPT_CONF) for v in (960, 1280)]
VARIANTS += [(f"iou_{v:.2f}", {"iou": v}, BASE_KPT_CONF) for v in (0.45, 0.90)]
VARIANTS += [(f"maxdet_{v}", {"max_det": v}, BASE_KPT_CONF) for v in (8, 50)]
VARIANTS += [(f"kptconf_{v:.2f}", {}, v) for v in (0.20, 0.50)]

EDGES = ((0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8),
         (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15),
         (12, 14), (14, 16))
PALETTE = [(66, 133, 244), (52, 168, 83), (251, 188, 5), (234, 67, 53),
           (171, 71, 188), (0, 172, 193), (255, 112, 67), (124, 179, 66),
           (3, 169, 244), (255, 202, 40), (236, 64, 122), (0, 200, 150)]


def render_variant(src: Path, name: str, overrides: dict, kpt_conf: float,
                   ckpt: Path = CKPT, dst: Path = DST) -> dict:
    args = {**BASE, **overrides}
    caption = (f"{name} | conf={args['conf']} imgsz={args['imgsz']} "
               f"iou={args['iou']} max_det={args['max_det']} kpt_conf={kpt_conf} "
               f"| {ckpt.stem} bytetrack")
    model = YOLO(str(ckpt))
    cap = cv2.VideoCapture(str(src))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    out_path = dst / name / src.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path),
                             cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    frames, det_total, ids_seen = 0, 0, set()
    t0 = time.time()
    eff = {}
    for res in model.track(source=str(src), stream=True, persist=True,
                           tracker="bytetrack.yaml", verbose=False,
                           device="cuda:0", **args):
        img = res.orig_img.copy()
        frames += 1
        if res.keypoints is not None and res.boxes is not None \
                and res.boxes.id is not None:
            kxy = res.keypoints.xy.cpu().numpy()
            kcf = res.keypoints.conf.cpu().numpy() \
                if res.keypoints.conf is not None else None
            ids = res.boxes.id.int().cpu().tolist()
            xyxy = res.boxes.xyxy.cpu().numpy()
            det_total += len(ids)
            ids_seen.update(ids)
            for j, tid in enumerate(ids):
                col = PALETTE[tid % len(PALETTE)]
                bb = xyxy[j]
                cv2.rectangle(img, (int(bb[0]), int(bb[1])),
                              (int(bb[2]), int(bb[3])), col, 2)
                cv2.putText(img, f"#{tid}", (int(bb[0]), max(16, int(bb[1]) - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2, cv2.LINE_AA)
                pts = {}
                for i in range(17):
                    c = 1.0 if kcf is None else kcf[j][i]
                    if c >= kpt_conf:
                        pts[i] = (int(kxy[j][i][0]), int(kxy[j][i][1]))
                for a, b in EDGES:
                    if a in pts and b in pts:
                        cv2.line(img, pts[a], pts[b], col, 2, cv2.LINE_AA)
                for p in pts.values():
                    cv2.circle(img, p, 4, col, -1, cv2.LINE_AA)
        cv2.rectangle(img, (0, h - 28), (w, h), (0, 0, 0), -1)
        cv2.putText(img, caption, (8, h - 9), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (255, 255, 255), 1, cv2.LINE_AA)
        writer.write(img)
    writer.release()
    if getattr(model, "predictor", None) is not None:
        eff = {k: v for k, v in vars(model.predictor.args).items()
               if isinstance(v, (int, float, str, bool, type(None)))}
    if shutil.which("ffmpeg"):
        tmp = out_path.with_suffix(".audio.mp4")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-i", str(out_path), "-i", str(src), "-c:v", "copy",
                            "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "aac",
                            "-shortest", str(tmp)])
        if r.returncode == 0 and tmp.exists():
            tmp.replace(out_path)
        elif tmp.exists():
            tmp.unlink()
    dt = time.time() - t0
    return {"kpt_conf_draw": kpt_conf, "frames": frames,
            "mean_det_per_frame": round(det_total / max(frames, 1), 2),
            "unique_track_ids": len(ids_seen),
            "proc_fps": round(frames / dt, 1), "s": round(dt, 1),
            "effective_args": eff}


def main() -> int:
    videos = sorted(SRC.glob("*.mp4"))
    manifest = {"checkpoint": str(CKPT),
                "checkpoint_sha256": hashlib.sha256(CKPT.read_bytes()).hexdigest(),
                "base": {**BASE, "kpt_conf_draw": BASE_KPT_CONF,
                         "tracker": "bytetrack.yaml"},
                "variants": {}}
    total = len(VARIANTS) * len(videos)
    n = 0
    for name, ov, kc in VARIANTS:
        manifest["variants"][name] = {}
        for v in videos:
            n += 1
            print(f"[sweep] ({n}/{total}) {name} / {v.name} …", flush=True)
            stats = render_variant(v, name, ov, kc)
            manifest["variants"][name][v.name] = stats
            print(f"[sweep]   det/frame={stats['mean_det_per_frame']} "
                  f"ids={stats['unique_track_ids']} "
                  f"proc={stats['proc_fps']}fps", flush=True)
            (DST / "sweep_manifest.json").write_text(
                json.dumps(manifest, indent=2, default=str))
    print("[sweep] COMPLETO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
