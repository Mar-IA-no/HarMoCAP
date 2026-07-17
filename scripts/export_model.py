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

PROD_CHECKPOINT = "yolo26m-pose.pt"     # modelo canónico de tiempo real (AGENTS.md)
EXPORT_ARGS = dict(format="engine", half=True, device=0, imgsz=640)


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
    final = OUT / "yolo26m-pose.engine"
    if engine_path.resolve() != final.resolve():
        engine_path.replace(final)
    log["engine_final"] = str(final)
    log["engine_sha256"] = hashlib.sha256(final.read_bytes()).hexdigest()
    log["engine_bytes"] = final.stat().st_size

    print("[2/3] prueba de carga + inferencia del engine…")
    t0 = time.time()
    engine = YOLO(str(final))
    res = engine.predict(str(OUT / "bus.jpg"), device=0, verbose=False)
    log["inference_test"] = {
        "ok": True,
        "n_persons": 0 if res[0].keypoints is None else int(res[0].keypoints.xy.shape[0]),
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
