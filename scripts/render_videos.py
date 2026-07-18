#!/usr/bin/env python
"""Inferencia batch sobre videos con 4 variantes de render (una sola pasada).

Modelo: best.pt de ft2 (época 30, mAP50-95 0.6261 en CrowdPose-val).
Entrada:  Biblioteca/videos_people_dancing/*.mp4
Salida:   Biblioteca/videos_people_dancing_inferido/
            01_esqueleto/     esqueleto pro, color por persona (track id)
            02_bbox_trackid/  ídem + bbox + id
            03_estelas/       ídem + trails de muñecas/tobillos (15 frames)
            04_fondo_negro/   solo esqueletos sobre negro
Si hay ffmpeg, se remuxa el audio original en cada salida.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "Biblioteca" / "videos_people_dancing"
DST = REPO / "Biblioteca" / "videos_people_dancing_inferido"
CKPT = REPO / "runs" / "20260718_0832_ft2_crowdpose_mixed30" / "weights" / "best.pt"

VARIANTS = ["01_esqueleto", "02_bbox_trackid", "03_estelas", "04_fondo_negro"]
KPT_CONF = 0.35
TRAIL_LEN = 15
TRAIL_KPTS = (9, 10, 15, 16)          # muñecas y tobillos
EDGES = ((0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8),
         (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15),
         (12, 14), (14, 16))

# paleta viva, indexada por track_id (BGR)
PALETTE = [(66, 133, 244), (52, 168, 83), (251, 188, 5), (234, 67, 53),
           (171, 71, 188), (0, 172, 193), (255, 112, 67), (124, 179, 66),
           (3, 169, 244), (255, 202, 40), (236, 64, 122), (0, 200, 150)]


def color_for(tid: int) -> tuple:
    return PALETTE[tid % len(PALETTE)]


def draw_skeleton(img, kxy, kconf, col, thick=3):
    pts = {}
    for i, (x, y) in enumerate(kxy):
        if kconf[i] >= KPT_CONF:
            pts[i] = (int(x), int(y))
    for a, b in EDGES:
        if a in pts and b in pts:
            cv2.line(img, pts[a], pts[b], col, thick, cv2.LINE_AA)
    for p in pts.values():
        cv2.circle(img, p, thick + 2, col, -1, cv2.LINE_AA)
        cv2.circle(img, p, thick + 2, (255, 255, 255), 1, cv2.LINE_AA)
    return pts


def process_video(src: Path) -> dict:
    model = YOLO(str(CKPT))            # instancia fresca → tracker limpio por video
    cap = cv2.VideoCapture(str(src))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    writers = {}
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    for v in VARIANTS:
        out = DST / v / src.name
        out.parent.mkdir(parents=True, exist_ok=True)
        writers[v] = cv2.VideoWriter(str(out), fourcc, fps, (w, h))

    trails: dict = defaultdict(lambda: deque(maxlen=TRAIL_LEN))
    t0, frames, persons_seen = time.time(), 0, set()

    # TODO (Mariano, 2026-07-18): próxima pasada → decidir tracker explícito.
    # Hoy usa el default de Ultralytics (BoT-SORT+GMC: bueno para cámara en mano
    # de conciertos, pero emite "not enough matching points" en cortes/blur y
    # difiere del pipeline en vivo que usa ByteTrack). Opciones: tracker=
    # "bytetrack.yaml" (consistencia+silencio) o botsort con gmc_method: none.
    for res in model.track(source=str(src), stream=True, persist=True,
                           conf=0.25, verbose=False, device="cuda:0"):
        frame = res.orig_img
        frames += 1
        base = frame.copy()
        black = np.zeros_like(frame)
        dets = []
        if res.keypoints is not None and res.boxes is not None \
                and res.boxes.id is not None:
            kxy = res.keypoints.xy.cpu().numpy()
            kcf = (res.keypoints.conf.cpu().numpy()
                   if res.keypoints.conf is not None
                   else np.ones(kxy.shape[:2]))
            ids = res.boxes.id.int().cpu().tolist()
            xyxy = res.boxes.xyxy.cpu().numpy()
            dets = list(zip(ids, kxy, kcf, xyxy))
            persons_seen.update(ids)

        # --- 01: esqueleto por persona -----------------------------------
        img1 = base.copy()
        for tid, kp, kc, _ in dets:
            draw_skeleton(img1, kp, kc, color_for(tid))
        writers["01_esqueleto"].write(img1)

        # --- 02: + bbox + track id ---------------------------------------
        img2 = img1.copy()
        for tid, _, _, bb in dets:
            col = color_for(tid)
            cv2.rectangle(img2, (int(bb[0]), int(bb[1])),
                          (int(bb[2]), int(bb[3])), col, 2)
            cv2.putText(img2, f"#{tid}", (int(bb[0]), max(16, int(bb[1]) - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2, cv2.LINE_AA)
        writers["02_bbox_trackid"].write(img2)

        # --- 03: + estelas ------------------------------------------------
        for tid, kp, kc, _ in dets:
            pts = [(int(kp[i][0]), int(kp[i][1])) if kc[i] >= KPT_CONF else None
                   for i in TRAIL_KPTS]
            trails[tid].append(pts)
        img3 = img1.copy()
        for tid, dq in trails.items():
            col = color_for(tid)
            for j in range(len(TRAIL_KPTS)):
                prev = None
                for age, snap in enumerate(dq):
                    p = snap[j]
                    if p is not None and prev is not None:
                        alpha = (age + 1) / len(dq)
                        cc = tuple(int(c * alpha) for c in col)
                        cv2.line(img3, prev, p, cc, 2, cv2.LINE_AA)
                    prev = p
        writers["03_estelas"].write(img3)

        # --- 04: fondo negro ---------------------------------------------
        for tid, kp, kc, _ in dets:
            draw_skeleton(black, kp, kc, color_for(tid), thick=4)
        writers["04_fondo_negro"].write(black)

    for wtr in writers.values():
        wtr.release()

    # remuxar audio original si hay ffmpeg
    if shutil.which("ffmpeg"):
        for v in VARIANTS:
            out = DST / v / src.name
            tmp = out.with_suffix(".audio.mp4")
            r = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out),
                 "-i", str(src), "-c:v", "copy", "-map", "0:v:0",
                 "-map", "1:a:0?", "-c:a", "aac", "-shortest", str(tmp)])
            if r.returncode == 0 and tmp.exists():
                tmp.replace(out)
            elif tmp.exists():
                tmp.unlink()

    dt = time.time() - t0
    # trazabilidad: args EFECTIVOS de inferencia (incluye todos los defaults)
    eff = {}
    if getattr(model, "predictor", None) is not None:
        eff = {k: v for k, v in vars(model.predictor.args).items()
               if isinstance(v, (int, float, str, bool, type(None)))}
    return {"frames": frames, "persons": len(persons_seen),
            "s": round(dt, 1), "fps_proc": round(frames / dt, 1),
            "effective_args": eff}


def main() -> int:
    assert CKPT.exists(), f"checkpoint no encontrado: {CKPT}"
    videos = sorted(SRC.glob("*.mp4"))
    print(f"[render] {len(videos)} videos → {DST} (4 variantes c/u)")
    print(f"[render] modelo: {CKPT.name} (ft2 ep30, CrowdPose-val 0.6261)")
    import hashlib
    import json
    manifest = {"checkpoint": str(CKPT),
                "checkpoint_sha256": hashlib.sha256(CKPT.read_bytes()).hexdigest(),
                "videos": {}}
    for i, v in enumerate(videos, 1):
        print(f"[render] ({i}/{len(videos)}) {v.name} …", flush=True)
        stats = process_video(v)
        manifest["videos"][v.name] = stats
        if "effective_args" in stats and "effective_args" not in manifest:
            manifest["effective_args"] = stats["effective_args"]
        print(f"[render]   {stats['frames']} frames, {stats['persons']} personas "
              f"trackeadas, {stats['s']}s ({stats['fps_proc']} fps proc)", flush=True)
    (DST / "render_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str))
    print(f"[render] manifest → {DST / 'render_manifest.json'}")
    print("[render] COMPLETO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
