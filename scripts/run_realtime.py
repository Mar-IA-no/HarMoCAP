#!/usr/bin/env python
"""M2/M4 — corre el pipeline de tiempo real (plan M2).

Fuente: webcam (índice) o archivo de video. Emite OSC según el contrato v1 y
reporta al final las métricas GO/NO-GO (latencia software p50/p95/p99, jitter
|Δsent−Δcaptured|, drops) que se versionan en reports/<run_id>/.

Uso:
    python scripts/run_realtime.py --source 0 --show
    python scripts/run_realtime.py --source video.mp4 --record outputs/sessions/s1.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from harmocap.pipeline import HarmocapPipeline  # noqa: E402


# COCO-17 connections in the same order used by YOLO-pose.
SKELETON_EDGES = (
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
)


def visible_people_map(persons):
    """Mapea teclas 1-8 a personas visibles ordenadas de izquierda a derecha."""
    visible = [p for p in persons if p.present]
    visible.sort(key=lambda p: (p.bbox[0], p.slot_id))
    by_key = {i + 1: p.slot_id for i, p in enumerate(visible)}
    display_number = {p.slot_id: i + 1 for i, p in enumerate(visible)}
    return by_key, display_number


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="0",
                    help="índice de webcam o ruta de video")
    ap.add_argument("--seconds", type=float, default=None,
                    help="duración; indefinido por defecto")
    ap.add_argument("--warmup", type=float, default=10.0,
                    help="warmup excluido de métricas (plan r3 #12)")
    ap.add_argument("--record", default=None, help="grabar sesión a .jsonl")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--mode", default="group", choices=("group", "crowd"),
                    help="group: identidad sagrada (BoT-SORT+ReID+reasoc) | "
                         "crowd: masa, recall (imgsz alto, agregados)")
    ap.add_argument("--checkpoint", default=None,
                    help="Explicit local pose checkpoint for this run")
    ap.add_argument("--show", action="store_true",
                    help="ventana con esqueletos + selección de foco: teclas "
                         "1-N = persona visible (izq→der), 0/a = auto, q/ESC = salir")
    args = ap.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    dests = [(args.host, args.port)] if args.host and args.port else None
    pipe = HarmocapPipeline(REPO, source=source, record_to=args.record,
                            osc_destinations=dests, mode=args.mode,
                            checkpoint=args.checkpoint)
    pipe.camera.start()
    print(f"[run] backend: {pipe.backend.info()}")
    print(f"[run] captura: {pipe.camera.profile()}")
    print(f"[run] stream_id={pipe.stream_id} contract_id={pipe.contract_id}")

    show = args.show
    if show:
        import cv2
    t0 = time.monotonic()
    warmup_done = False
    try:
        deadline = (None if args.seconds is None
                    else t0 + args.warmup + args.seconds)
        while deadline is None or time.monotonic() < deadline:
            if not warmup_done and time.monotonic() - t0 >= args.warmup:
                pipe.metrics["lat_sw_ms"].clear()   # descartar warmup
                pipe.metrics["jitter_ms"].clear()
                warmup_done = True
            if not pipe.step():
                print("[run] fuente agotada")
                break
            if show and getattr(pipe, "last_frame_img", None) is not None:
                img = pipe.last_frame_img.copy()
                h = img.shape[0]
                key_to_slot, display_number = visible_people_map(pipe.last_persons)
                for p in pipe.last_persons:
                    if not p.present:
                        continue
                    col = (0, 220, 255) if p.focused else (0, 180, 0)
                    points = {
                        i: (int(k.x * h), int(k.y * h))
                        for i, k in enumerate(p.keypoints)
                        if k.state != 2
                    }
                    for left, right in SKELETON_EDGES:
                        if left in points and right in points:
                            cv2.line(img, points[left], points[right], col,
                                     3, cv2.LINE_AA)
                    for i, k in enumerate(p.keypoints):
                        if k.state != 2:
                            point_col = col if k.state == 0 else (255, 190, 0)
                            cv2.circle(img, points[i], 5, point_col, -1)
                    xs = [point[0] for point in points.values()]
                    ys = [point[1] for point in points.values()]
                    if xs:
                        person_number = display_number[p.slot_id]
                        cv2.putText(img, f"P{person_number} / slot {p.slot_id}" +
                                    (" *FOCO*" if p.focused else ""),
                                    (int(min(xs)), max(14, int(min(ys)) - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)
                focused_number = display_number.get(pipe.slots.focused_slot, "-")
                cv2.putText(img, f"foco: {pipe.slots.focus_mode} "
                            f"(P{focused_number} / slot {pipe.slots.focused_slot})  "
                            f"[1-{len(key_to_slot)}]=persona izq->der 0/a=auto q=salir",
                            (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                            (255, 255, 255), 1)
                cv2.imshow("HarMoCAP", img)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key in (ord("0"), ord("a")):
                    pipe.slots.select_auto()
                elif ord("1") <= key <= ord("8"):
                    slot = key_to_slot.get(key - ord("0"))
                    if slot is not None:
                        pipe.slots.select_focus(slot)
    except KeyboardInterrupt:
        print("\n[run] interrumpido")
    finally:
        if show:
            cv2.destroyAllWindows()
        report = pipe.report()
        pipe.close()

    print(json.dumps(report, indent=2, default=str))
    run_file = REPO / "reports" / "CURRENT_RUN"
    if run_file.exists():
        run_id = run_file.read_text().strip().split("=", 1)[1]
        out = REPO / "reports" / run_id / "realtime_metrics.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str))
        print(f"[run] métricas → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
