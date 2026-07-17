"""Captura de baja latencia — LatchingCamera (plan M2).

La captura es el término dominante de la latencia (pack §F.1): webcam USB sin
optimizar ~200 ms; afinada ~35-66 ms. Patrón: hilo lector dedicado que lee sin
parar y retiene SOLO el frame más reciente ("último frame"), buffer de OpenCV
en 1. Drop de frames > backpressure.

Advertencia (addendum #6): CAP_PROP_BUFFERSIZE puede ser IGNORADO por algunos
backends. El perfil real de captura (backend, resolución, FPS, formato) se
registra en el manifest del run; si OpenCV no controla el buffer, el fallback
documentado es V4L2/GStreamer con `drop=true max-buffers=1`.
"""
from __future__ import annotations

import threading
import time

import cv2


def mono_us() -> int:
    """Reloj monótono del pipeline en µs (plan: time.monotonic_ns, r2 #1)."""
    return time.monotonic_ns() // 1_000


class LatchingCamera:
    """Hilo lector 'último frame'. get_latest() nunca bloquea en el lector."""

    def __init__(self, source: int | str = 0, width: int | None = None,
                 height: int | None = None, fps: int | None = None):
        self.source = source
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"no se pudo abrir la fuente de video: {source!r}")
        # buffer mínimo (puede ser ignorado según backend — se registra el perfil)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if fps:
            self.cap.set(cv2.CAP_PROP_FPS, fps)

        self._lock = threading.Lock()
        self._frame = None
        self._captured_at_us = 0
        self._frame_counter = 0          # captured_frame_id: con huecos si se saltan
        self._dropped = 0
        self._running = False
        self._thread: threading.Thread | None = None

    # -- perfil real (para el manifest del run; addendum #6) -------------------
    def profile(self) -> dict:
        return {
            "source": str(self.source),
            "backend": self.cap.getBackendName(),
            "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": float(self.cap.get(cv2.CAP_PROP_FPS)),
            "buffersize_req": 1,
            "fourcc": int(self.cap.get(cv2.CAP_PROP_FOURCC)),
        }

    # -- ciclo de vida ---------------------------------------------------------
    def start(self) -> "LatchingCamera":
        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True,
                                        name="harmocap-capture")
        self._thread.start()
        return self

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.cap.release()

    def _reader(self) -> None:
        # Un ARCHIVO de video no es una cámara: el decode corre mucho más rápido
        # que el tiempo real. Para que la fuente-archivo simule una cámara en
        # vivo (e2e sin cámara física), se ritma la lectura a 1/fps.
        is_file = isinstance(self.source, str)
        pace_s = 0.0
        if is_file:
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            pace_s = 1.0 / max(fps, 1.0)
        next_t = time.monotonic()
        while self._running:
            ok, frame = self.cap.read()
            if not ok:
                if is_file:                        # archivo de video: fin
                    self._running = False
                    break
                time.sleep(0.005)
                continue
            if is_file:
                next_t += pace_s
                delay = next_t - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            t = mono_us()
            with self._lock:
                if self._frame is not None:
                    self._dropped += 1             # el consumidor no llegó: drop-oldest
                self._frame = frame
                self._captured_at_us = t
                self._frame_counter += 1

    # -- consumo ---------------------------------------------------------------
    def get_latest(self) -> tuple | None:
        """(frame, captured_frame_id, captured_at_us) o None si no hay nuevo."""
        with self._lock:
            if self._frame is None:
                return None
            frame, fid, t = self._frame, self._frame_counter, self._captured_at_us
            self._frame = None                     # latch: cada frame se entrega 1 vez
        return frame, fid, t

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def alive(self) -> bool:
        return self._running
