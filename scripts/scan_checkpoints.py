#!/usr/bin/env python
"""T4b — escanea checkpoints intermedios buscando uno que cumpla AMBOS umbrales."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_pose import run_eval

REPO = Path(__file__).resolve().parent.parent
W = REPO / "runs/20260718_0334_ft1_crowdpose_mixed/weights"
BASE_CP, BASE_COCO = 0.5960, 0.6822
NEED_CP = BASE_CP + 0.015          # >= 0.6110
NEED_COCO = BASE_COCO - 0.010      # >= 0.6722

results = {}
for ep in [11, 15, 19, 23]:        # epochN.pt = fin de la época N+1 (0-indexed)
    ck = W / f"epoch{ep}.pt"
    if not ck.exists():
        continue
    r = run_eval(str(ck), f"scan_ep{ep+1}")["benchmarks"]
    cp, co = r["crowdpose_val_coco17"]["pose_map50_95"], r["coco_pose_val2017"]["pose_map50_95"]
    ok = cp >= NEED_CP and co >= NEED_COCO
    results[ep + 1] = {"crowdpose": cp, "coco": co, "cumple_ambos": ok}
    print(f"SCAN epoch {ep+1}: crowdpose={cp:.4f} (Δ{100*(cp-BASE_CP):+.2f}) "
          f"coco={co:.4f} (Δ{100*(co-BASE_COCO):+.2f}) → {'✅ CUMPLE AMBOS' if ok else '—'}")
out = REPO / "reports/20260717_e71e14a/checkpoint_scan.json"
out.write_text(json.dumps(results, indent=2))
print(f"scan → {out}")
