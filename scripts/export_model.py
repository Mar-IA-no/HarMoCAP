#!/usr/bin/env python
"""M1 — Exporta yolo26m-pose (producción) a TensorRT engine FP16 (plan M1).

Claim honesto (r2 #11, r3 #13): "engine construido con flag half=True",
verificado por el build log — NO se afirma auditoría de precisión por-capa.
El build log + SHA-256 del engine se versionan en reports/<run_id>/ (r8 #6).
Incluye prueba de carga+inferencia que confirma que el engine corre.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from ultralytics import YOLO

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "outputs"
OUT.mkdir(exist_ok=True)

import argparse

_ap = argparse.ArgumentParser()
_ap.add_argument("--checkpoint", default="yolo26m-pose.pt",
                 help="checkpoint a exportar (default: preentrenado)")
_ap.add_argument("--name", default=None,
                 help="nombre base del engine en outputs/ (default: stem del checkpoint)")
_ARGS = _ap.parse_args()

PROD_CHECKPOINT = _ARGS.checkpoint
ENGINE_NAME = (_ARGS.name or Path(PROD_CHECKPOINT).stem) + ".engine"
# dynamic=True (H4-P0): engine válido en el RANGO de resoluciones — el modo
# grupo infiere a 640 y el modo masa a 1280 con el MISMO engine. El export de
# M1 era estático a 640 y habría hecho caer el modo masa al .pt silenciosamente.
EXPORT_ARGS = dict(format="engine", half=True, device=0, imgsz=1280,
                   dynamic=True, batch=1)


def current_run_dir() -> Path:
    run_file = REPO / "reports" / "CURRENT_RUN"
    run_id = run_file.read_text().strip().split("=", 1)[1] if run_file.exists() \
        else time.strftime("%Y%m%d_manual")
    d = REPO / "reports" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def main() -> int:
    run_dir = current_run_dir()
    log: dict = {"checkpoint": PROD_CHECKPOINT, "export_args": EXPORT_ARGS,
                 "claim": "engine construido con flag half=True (build log); "
                          "sin auditoría de precisión por-capa"}

    print(f"[1/3] export {PROD_CHECKPOINT} → TensorRT engine (half=True)…")
    t0 = time.time()
    model = YOLO(PROD_CHECKPOINT)
    engine_path = Path(model.export(**EXPORT_ARGS))
    log["export_s"] = round(time.time() - t0, 1)
    log["engine_path"] = str(engine_path)

    # mover el engine a outputs/ (ruta canónica de configs/model.yaml)
    final = OUT / ENGINE_NAME
    if engine_path.resolve() != final.resolve():
        engine_path.replace(final)
    log["engine_final"] = str(final)
    log["engine_sha256"] = hashlib.sha256(final.read_bytes()).hexdigest()
    log["engine_bytes"] = final.stat().st_size

    print("[2/3] prueba de carga + inferencia del engine a 640 Y 1280 (dinámico)…")
    t0 = time.time()
    engine = YOLO(str(final))
    log["inference_test"] = {}
    for sz in (640, 1280):
        res = engine.predict(str(OUT / "bus.jpg"), device=0, imgsz=sz,
                             verbose=False)
        log["inference_test"][f"imgsz_{sz}"] = {
            "ok": True,
            "n_persons": 0 if res[0].keypoints is None
            else int(res[0].keypoints.xy.shape[0]),
            "speed_ms": res[0].speed,
        }
    log["inference_s"] = round(time.time() - t0, 1)

    print("[3/3] registrando build log en reports/…")
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = "unknown"
    log["commit"] = commit
    (run_dir / "engine_build.json").write_text(json.dumps(log, indent=2, allow_nan=False))
    print(f"EXPORT OK — {final} ({log['engine_bytes']/1e6:.0f} MB)  "
          f"sha256={log['engine_sha256'][:16]}…")
    print(f"build log: {run_dir / 'engine_build.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
