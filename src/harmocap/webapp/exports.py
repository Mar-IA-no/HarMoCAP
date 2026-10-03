"""Exportación de una sesión procesada: CSV por persona y de multitud + gráficos."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from harmocap.schema import CROWD_FIELDS, FEATURE_ORDER


def export_csv(jsonl_path: str | Path, out_dir: str | Path,
               features: list[str] | None = None) -> tuple[Path, Path]:
    """Aplana el .jsonl a dos CSV: personas (una fila por persona-cuadro) y
    multitud (una fila por cuadro). `features`: subconjunto a exportar (None=todas)."""
    jsonl_path = Path(jsonl_path)
    out_dir = Path(out_dir)
    feats = [f for f in FEATURE_ORDER if features is None or f in features]
    stem = jsonl_path.stem
    persons_csv = out_dir / f"{stem}__personas.csv"
    crowd_csv = out_dir / f"{stem}__multitud.csv"
    provenance = ["t_us", "processed_elapsed_us", "processing_clock_domain",
                  "source_frame_index", "source_pts_ticks",
                  "source_pts_origin_ticks",
                  "source_time_base", "source_video_sha256", "timestamp_state"]

    with jsonl_path.open(encoding="utf-8") as fj, \
            persons_csv.open("w", newline="", encoding="utf-8") as fp, \
            crowd_csv.open("w", newline="", encoding="utf-8") as fc:
        wp = csv.writer(fp)
        wc = csv.writer(fc)
        wp.writerow(["t_s", "frame"] + provenance + ["slot", "focused"] + feats)
        wc.writerow(["t_s", "frame"] + provenance + list(CROWD_FIELDS))
        for line in fj:
            d = json.loads(line)
            source = [d.get(key, "") for key in provenance]
            for p in d.get("persons", []):
                idx = {f: i for i, f in enumerate(FEATURE_ORDER)}
                row = [d["t_s"], d["frame"]] + source + [p["slot"], int(p["focused"])]
                for f in feats:
                    i = idx[f]
                    # feature inválida → celda vacía (el estado 2 no se exporta)
                    v = p["features"][i]
                    st = p["feature_states"][i]
                    row.append("" if st == 2 else v)
                wp.writerow(row)
            c = d.get("crowd", {})
            wc.writerow([d["t_s"], d["frame"]] + source +
                        [c.get(k, "") for k in CROWD_FIELDS])
    return persons_csv, crowd_csv


def plot_features(feature_series: dict, features: list[str]):
    """Figura matplotlib: series temporales de las features elegidas (por slot)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    features = [f for f in features if feature_series.get(f)]
    if not features:
        return None
    n = len(features)
    fig, axes = plt.subplots(n, 1, figsize=(9, 1.8 * n), squeeze=False, sharex=True)
    for ax, fname in zip(axes[:, 0], features):
        by_slot: dict[int, list] = {}
        for t_s, slot, val in feature_series[fname]:
            by_slot.setdefault(slot, []).append((t_s, val))
        for slot, pts in sorted(by_slot.items()):
            ts = [p[0] for p in pts]
            vs = [p[1] for p in pts]
            ax.plot(ts, vs, lw=1.0, label=f"P{slot}")
        ax.set_ylabel(fname, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.2)
        if len(by_slot) > 1:
            ax.legend(fontsize=6, loc="upper right", ncol=len(by_slot))
    axes[-1, 0].set_xlabel("tiempo (s)", fontsize=8)
    fig.tight_layout()
    return fig


def plot_crowd(crowd_series: dict, fields: list[str]):
    """Figura matplotlib: series temporales de campos de multitud elegidos."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fields = [f for f in fields if crowd_series.get(f)]
    if not fields:
        return None
    fig, ax = plt.subplots(figsize=(9, 3.5))
    for f in fields:
        pts = crowd_series[f]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], lw=1.2, label=f)
    ax.set_xlabel("tiempo (s)", fontsize=8)
    ax.grid(alpha=0.2)
    ax.legend(fontsize=7, ncol=3)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    return fig
