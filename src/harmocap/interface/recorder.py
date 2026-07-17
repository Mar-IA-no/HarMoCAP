"""Grabador .jsonl — rama NO bloqueante, separada del transporte RT (plan M4).

- Una línea JSON por MovementFrame, con metadata completa (incluye los params
  del perfil de calibración: la grabación es auto-contenida, r4 #5).
- Serialización con allow_nan=False (r3 #5): ausencia = null + estado, jamás NaN.
- Corre en su propio hilo con cola acotada drop-oldest (r2 #3): una pausa de
  disco no bloquea la emisión OSC.
- PRIVACIDAD (addendum #4): las grabaciones naturales van a outputs/sessions/
  (gitignored); solo se publican con consentimiento documentado.
"""
from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

from harmocap.schema import (
    CALIBRATION_PARAM_ORDER, CalibrationProfile, FEATURE_ORDER,
    FEATURE_SET_VERSION, KEYPOINT_ORDER, MovementFrame, PRODUCER_VERSION,
    SCHEMA_VERSION,
)


def frame_to_dict(frame: MovementFrame, calib: CalibrationProfile | None,
                  *, contract_id: str, config_hash: str, model_id: str) -> dict:
    """Proyección MovementFrame → dict serializable (contrato de grabación)."""
    d = {
        "schema_version": SCHEMA_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "producer_version": PRODUCER_VERSION,
        "contract_id": contract_id,
        "config_hash": config_hash,
        "model_id": model_id,
        "stream_id": frame.stream_id,
        "captured_frame_id": frame.captured_frame_id,
        "captured_at_us": frame.captured_at_us,
        "processed_at_us": frame.processed_at_us,
        "frame_w": frame.frame_w,
        "frame_h": frame.frame_h,
        "fps": frame.fps,
        "calibration_generation": frame.calibration_generation,
        "calibration_state": frame.calibration_state,
        "n_persons": frame.n_persons,
        "keypoint_order": list(KEYPOINT_ORDER),
        "feature_order": list(FEATURE_ORDER),
        "persons": [],
    }
    if calib is not None:
        d["calibration_params"] = dict(zip(CALIBRATION_PARAM_ORDER, calib.params))
        d["calibration_effective_from"] = calib.effective_from_frame_id
    for p in frame.persons:
        pd = {"slot_id": p.slot_id, "present": p.present}
        if p.present:
            pd.update({
                "keypoints": [[k.x, k.y, k.conf] for k in p.keypoints],
                "kp_state": [[k.state, k.age_frames, k.age_us] for k in p.keypoints],
                "bbox_xywhn": list(p.bbox),
                "features": list(p.features),
                "feat_state": list(p.feature_states),
                "provisional": p.provisional,
            })
        d["persons"].append(pd)
    return d


class Recorder:
    def __init__(self, out_path: str | Path, *, queue_size: int = 256):
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self._q: queue.Queue = queue.Queue(maxsize=queue_size)
        self.dropped = 0
        self._running = True
        self._thread = threading.Thread(target=self._writer, daemon=True,
                                        name="harmocap-recorder")
        self._thread.start()

    def put(self, frame_dict: dict) -> None:
        """Drop-oldest si la cola se llena (r2 #3): nunca bloquea al productor."""
        try:
            self._q.put_nowait(frame_dict)
        except queue.Full:
            try:
                self._q.get_nowait()
                self.dropped += 1
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(frame_dict)
            except queue.Full:
                self.dropped += 1

    def _writer(self) -> None:
        with open(self.out_path, "a", encoding="utf-8") as f:
            while self._running or not self._q.empty():
                try:
                    d = self._q.get(timeout=0.25)
                except queue.Empty:
                    continue
                # allow_nan=False: cualquier fuga de NaN falla ACÁ (r3 #5)
                f.write(json.dumps(d, separators=(",", ":"), allow_nan=False) + "\n")

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=3.0)
