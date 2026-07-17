"""Percepción — wrapper de YOLO-pose con tracking (plan M2).

- Backend explícito (r4 #12): carga el .engine TensorRT si existe; si no, el
  .pt de fallback — y REGISTRA cuál cargó (se verifica en runtime).
- model.track(persist=True, stream=False por-frame) con tracker ByteTrack.
- Extracción robusta (finding #14): N=0, boxes.id None, alineación por índice.
- Coordenadas ISOTRÓPICAS (addendum #2): x_px/frame_h, y_px/frame_h — NO se usa
  keypoints.xyn de Ultralytics (anisotrópico: x/w, y/h distorsiona ángulos).
"""
from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

from harmocap.identity import Detection


class PoseBackend:
    def __init__(self, *, realtime_checkpoint: str, fallback_checkpoint: str,
                 device: str = "cuda:0", imgsz: int = 640, conf: float = 0.25,
                 max_det: int = 8, tracker: str = "bytetrack.yaml"):
        rt = Path(realtime_checkpoint)
        if rt.exists():
            self.loaded_checkpoint = str(rt)
            self.is_engine = rt.suffix == ".engine"
        else:
            self.loaded_checkpoint = fallback_checkpoint
            self.is_engine = False
        self.model = YOLO(self.loaded_checkpoint)
        self.device = device
        self.imgsz = imgsz
        self.conf = conf
        self.max_det = max_det
        self.tracker = tracker

    def info(self) -> dict:
        """Artefacto realmente cargado (r4 #12) — va al manifest del run."""
        return {"loaded_checkpoint": self.loaded_checkpoint,
                "is_engine": self.is_engine, "imgsz": self.imgsz,
                "conf": self.conf, "max_det": self.max_det,
                "tracker": self.tracker}

    def track_frame(self, frame) -> tuple[list[Detection], dict, tuple[int, int]]:
        """Un frame BGR → (detecciones, speed_ms, (frame_w, frame_h)).

        boxes.id None → lista vacía de Detection con track_id (addendum #5:
        no se emite slot provisional; se espera al tracker).
        """
        h, w = frame.shape[:2]
        results = self.model.track(
            frame, persist=True, verbose=False, device=self.device,
            imgsz=self.imgsz, conf=self.conf, max_det=self.max_det,
            tracker=self.tracker)
        res = results[0]
        dets: list[Detection] = []
        kpts, boxes = res.keypoints, res.boxes
        if kpts is not None and boxes is not None and len(boxes) > 0:
            n = len(boxes)
            xy = kpts.xy                                  # (N,17,2) píxeles
            kconf = kpts.conf                             # (N,17) o None
            ids = boxes.id                                # None si sin tracker aún
            xywhn = boxes.xywhn
            if tuple(xy.shape) != (n, 17, 2):
                raise ValueError(f"forma keypoints inesperada: {tuple(xy.shape)}")
            if ids is not None:
                for i in range(n):                        # alineación por índice
                    iso = [(float(x) / h, float(y) / h,
                            1.0 if kconf is None else float(kconf[i][j]))
                           for j, (x, y) in enumerate(xy[i])]
                    dets.append(Detection(
                        track_id=int(ids[i]),
                        bbox_xywhn=tuple(float(v) for v in xywhn[i]),
                        keypoints_iso=iso))
        return dets, dict(res.speed), (w, h)
