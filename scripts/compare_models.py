#!/usr/bin/env python
"""A/B de modelos con los MEJORES hiperparámetros del barrido (decisión usuario).

Config fija: conf=0.05, imgsz=1280, max_det=300 (máximo default), kpt_conf=0.20.
Modelos: ft2 (best.pt, ep30) vs base Ultralytics (yolo26m-pose.pt preentrenado).
Salida: Biblioteca/test/two_compare/{ft2,base_ultralytics}/<video>
        + compare_manifest.json (args efectivos + stats por modelo).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_inference import REPO, SRC, render_variant  # noqa: E402

DST = REPO / "Biblioteca" / "test" / "two_compare"
BEST_HP = {"conf": 0.05, "imgsz": 1280, "max_det": 300}
KPT_CONF = 0.20

MODELS = {
    "ft2": REPO / "runs" / "20260718_0832_ft2_crowdpose_mixed30" / "weights" / "best.pt",
    "base_ultralytics": REPO / "yolo26m-pose.pt",
}


def main() -> int:
    videos = sorted(SRC.glob("*.mp4"))
    manifest = {"best_hp": {**BEST_HP, "kpt_conf_draw": KPT_CONF,
                            "tracker": "bytetrack.yaml"},
                "models": {}}
    total = len(MODELS) * len(videos)
    n = 0
    for name, ckpt in MODELS.items():
        assert ckpt.exists(), f"checkpoint faltante: {ckpt}"
        manifest["models"][name] = {
            "checkpoint": str(ckpt),
            "sha256": hashlib.sha256(ckpt.read_bytes()).hexdigest(),
            "videos": {}}
        for v in videos:
            n += 1
            print(f"[compare] ({n}/{total}) {name} / {v.name} …", flush=True)
            stats = render_variant(v, name, BEST_HP, KPT_CONF,
                                   ckpt=ckpt, dst=DST)
            manifest["models"][name]["videos"][v.name] = stats
            print(f"[compare]   det/frame={stats['mean_det_per_frame']} "
                  f"ids={stats['unique_track_ids']} "
                  f"proc={stats['proc_fps']}fps", flush=True)
            (DST / "compare_manifest.json").write_text(
                json.dumps(manifest, indent=2, default=str))
    print("[compare] COMPLETO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
