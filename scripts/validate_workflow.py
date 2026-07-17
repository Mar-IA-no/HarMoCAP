#!/usr/bin/env python
"""M1 — Valida el workflow ML de Ultralytics con coco8-pose (plan M1).

OBJETIVO: probar el flujo train → val → predict end-to-end, NO la métrica
(coco8-pose son 8 imágenes: smoke del workflow, r2 #15). Usa explícitamente
yolo26n-pose.pt como checkpoint de smoke-test declarado.

Extracción robusta (finding #14): maneja N=0, boxes.id None, bbox de
boxes.xywhn, y verifica alineación por índice y forma (N,17,2).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from ultralytics import YOLO

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "outputs" / "validate_workflow"
OUT.mkdir(parents=True, exist_ok=True)

SMOKE_CHECKPOINT = "yolo26n-pose.pt"   # smoke-test declarado (r2 #15)


def extract_robust(result) -> list[dict]:
    """Extracción robusta de un Results de pose (finding #14)."""
    persons: list[dict] = []
    kpts = result.keypoints
    boxes = result.boxes
    if kpts is None or boxes is None or len(boxes) == 0:
        return persons                     # N=0: sin personas, lista vacía
    n = len(boxes)
    xy = kpts.xy                           # (N,17,2) píxeles
    conf = kpts.conf                       # (N,17) o None
    assert tuple(xy.shape) == (n, 17, 2), f"forma inesperada {tuple(xy.shape)}"
    ids = boxes.id                         # None si el tracker aún no asignó
    xywhn = boxes.xywhn                    # (N,4) normalizado
    for i in range(n):                     # alineación por índice fila↔fila
        persons.append({
            "track_id": None if ids is None else int(ids[i]),
            "bbox_xywhn": [float(v) for v in xywhn[i]],
            "keypoints_px": [[float(x), float(y)] for x, y in xy[i]],
            "kp_conf": None if conf is None else [float(c) for c in conf[i]],
        })
    return persons


def main() -> int:
    t0 = time.time()
    report: dict = {"checkpoint": SMOKE_CHECKPOINT, "steps": {}}

    print(f"[1/3] train — {SMOKE_CHECKPOINT} sobre coco8-pose (workflow, no métrica)")
    model = YOLO(SMOKE_CHECKPOINT)
    train_res = model.train(data="coco8-pose.yaml", epochs=3, imgsz=640,
                            device="cuda:0", project=str(OUT), name="train",
                            exist_ok=True, verbose=False)
    report["steps"]["train"] = {"ok": True, "save_dir": str(train_res.save_dir)}

    print("[2/3] val — metrics.pose.map")
    metrics = model.val(data="coco8-pose.yaml", device="cuda:0",
                        project=str(OUT), name="val", exist_ok=True, verbose=False)
    report["steps"]["val"] = {
        "ok": True,
        "pose_map50_95": float(metrics.pose.map),
        "pose_map50": float(metrics.pose.map50),
        "nota": "coco8-pose = 8 imágenes: valida el flujo, NO mide calidad real",
    }

    print("[3/3] predict — extracción robusta")
    results = model.predict(str(REPO / "outputs" / "bus.jpg"),
                            device="cuda:0", verbose=False)
    persons = extract_robust(results[0])
    report["steps"]["predict"] = {
        "ok": True, "n_persons": len(persons),
        "track_id_none_manejado": all(p["track_id"] is None for p in persons),
        "speed_ms": results[0].speed,
    }

    report["elapsed_s"] = round(time.time() - t0, 1)
    out_file = OUT / "workflow_report.json"
    out_file.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(f"\nWORKFLOW OK — reporte: {out_file}")
    print(json.dumps(report["steps"], indent=2)[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
