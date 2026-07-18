#!/usr/bin/env python
"""T3 — Fine-tuning ft1 con la configuración pineada de configs/train_ft2.yaml.

Registra ANTES de entrenar el manifest del run (config completa + manifest del
dataset + SHA-256 de las fuentes) y al terminar copia los artefactos livianos
(results.csv, args.yaml, best.pt SHA-256) a reports/<run_id_train>/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml
from ultralytics import YOLO

REPO = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((REPO / "configs" / "train_ft2.yaml").read_text())


def main() -> int:
    hp = CFG["hyperparameters"]
    run_id = time.strftime("%Y%m%d_%H%M") + "_" + CFG["run_name"]
    rep = REPO / "reports" / run_id
    rep.mkdir(parents=True, exist_ok=True)

    # manifest ANTES de entrenar (trazabilidad)
    ds_manifest = json.loads(
        (REPO / "data" / "crowdpose_yolo" / "manifest.json").read_text())
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = "unknown"
    manifest = {
        "run_id": run_id, "commit": commit, "config": CFG,
        "dataset_manifest": ds_manifest,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (rep / "train_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[train] manifest → {rep / 'train_manifest.json'}")
    print(f"[train] {CFG['run_name']}: {hp['epochs']} epochs, "
          f"base={CFG['base_checkpoint']}")

    model = YOLO(CFG["base_checkpoint"])
    kwargs = dict(
        data=str(REPO / CFG["data"]), epochs=hp["epochs"], imgsz=hp["imgsz"],
        batch=hp["batch"], seed=hp["seed"], deterministic=hp["deterministic"],
        patience=hp["patience"], device="cuda:0",
        save_period=1,      # directiva: guardar TODAS las épocas
        verbose=True,       # directiva: métricas completas visibles en tmux
        project=str(REPO / "runs"), name=run_id, exist_ok=True)
    if hp.get("optimizer") and hp["optimizer"] != "auto":
        kwargs["optimizer"] = hp["optimizer"]   # explícito: auto ignoraría lr0
    if hp.get("lr0"):
        kwargs["lr0"] = hp["lr0"]
    if hp.get("lrf"):
        kwargs["lrf"] = hp["lrf"]
    if hp.get("save_period"):
        kwargs["save_period"] = hp["save_period"]
    t0 = time.time()
    results = model.train(**kwargs)
    elapsed_h = (time.time() - t0) / 3600

    save_dir = Path(results.save_dir)
    best = save_dir / "weights" / "best.pt"
    for f in ("results.csv", "args.yaml"):
        if (save_dir / f).exists():
            shutil.copyfile(save_dir / f, rep / f)
    summary = {
        "elapsed_h": round(elapsed_h, 2),
        "best_pt": str(best),
        "best_sha256": hashlib.sha256(best.read_bytes()).hexdigest(),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (rep / "train_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[train] LISTO en {elapsed_h:.1f} h — best: {best}")
    print(f"[train] artefactos → {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
