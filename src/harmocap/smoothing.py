"""Suavizado causal por keypoint + máquina de estados de validez (plan M2).

- One-Euro filter (Casiez, CHI 2012): low-pass adaptativo, estrictamente causal,
  time-aware (dt real por muestra, r4 #3).
- Máquina de estados temporal por keypoint (finding #2, r6 #4):
      observed --conf<umbral--> held --timeout--> invalid --conf>=umbral--> observed(reset)
  En 'held' se retiene la última coordenada válida (hold-last, NO decae a cero:
  fabricaría movimiento, r3 #4); decae la CONFIABILIDAD efectiva (r6 #5).
  'imputed' queda RESERVADO y no se emite en v1 (r4 #7).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from harmocap.schema import KpState, N_KEYPOINTS


class OneEuroFilter:
    """One-Euro causal para una señal escalar. dt en segundos, real por muestra."""

    def __init__(self, mincutoff: float = 1.0, beta: float = 0.15, dcutoff: float = 1.0):
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self._x_prev: float | None = None
        self._dx_prev = 0.0

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        self._x_prev = None
        self._dx_prev = 0.0

    def __call__(self, x: float, dt: float) -> float:
        if dt <= 0.0:
            dt = 1e-3
        if self._x_prev is None:
            self._x_prev = x
            self._dx_prev = 0.0
            return x
        dx = (x - self._x_prev) / dt
        a_d = self._alpha(self.dcutoff, dt)
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev
        cutoff = self.mincutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1.0 - a) * self._x_prev
        self._x_prev = x_hat
        self._dx_prev = dx_hat
        return x_hat


@dataclass
class KpTrackState:
    """Estado interno de un keypoint en la máquina temporal."""
    state: int = int(KpState.INVALID)
    x: float = 0.0
    y: float = 0.0
    conf: float = 0.0            # confiabilidad EFECTIVA causal
    age_frames: int = 0
    age_us: int = 0
    held_since_us: int = 0


class KeypointSmoother:
    """Máquina de estados + One-Euro para los 17 keypoints de una persona.

    update() es causal: recibe la observación cruda de YOLO (coords isotrópicas
    + conf del modelo) y el timestamp monótono en µs; devuelve la lista de
    (x, y, conf_efectiva, estado, age_frames, age_us) lista para el contrato.
    """

    def __init__(self, *, mincutoff: float = 1.0, beta: float = 0.15,
                 dcutoff: float = 1.0, conf_threshold: float = 0.35,
                 held_timeout_ms: float = 500.0, conf_decay_per_s: float = 1.2):
        self.conf_threshold = conf_threshold
        self.held_timeout_us = held_timeout_ms * 1000.0
        self.conf_decay_per_s = conf_decay_per_s
        self._filters = [(OneEuroFilter(mincutoff, beta, dcutoff),
                          OneEuroFilter(mincutoff, beta, dcutoff))
                         for _ in range(N_KEYPOINTS)]
        self._kp = [KpTrackState() for _ in range(N_KEYPOINTS)]
        self._last_t_us: int | None = None

    def reset(self) -> None:
        for fx, fy in self._filters:
            fx.reset(); fy.reset()
        self._kp = [KpTrackState() for _ in range(N_KEYPOINTS)]
        self._last_t_us = None

    def update(self, raw: list[tuple[float, float, float]], t_us: int
               ) -> list[tuple[float, float, float, int, int, int]]:
        if len(raw) != N_KEYPOINTS:
            raise ValueError(f"esperaba {N_KEYPOINTS} keypoints")
        dt = 1e-3 if self._last_t_us is None else max((t_us - self._last_t_us) / 1e6, 1e-3)
        self._last_t_us = t_us
        out = []
        for i, (x, y, conf) in enumerate(raw):
            kp = self._kp[i]
            fx, fy = self._filters[i]
            if conf >= self.conf_threshold:
                # OBSERVED: coordenada de YOLO filtrada; conf = conf del modelo (r6 #5)
                if kp.state == int(KpState.INVALID):
                    fx.reset(); fy.reset()   # reinicialización tras invalid
                kp.x = fx(x, dt)
                kp.y = fy(y, dt)
                kp.conf = conf
                kp.state = int(KpState.OBSERVED)
                kp.age_frames = 0
                kp.age_us = 0
                kp.held_since_us = 0
            else:
                kp.age_frames += 1
                kp.age_us += int(dt * 1e6)
                if kp.state == int(KpState.OBSERVED):
                    kp.state = int(KpState.HELD)
                    kp.held_since_us = t_us
                if kp.state == int(KpState.HELD):
                    # hold-last: coordenada retenida; decae la confiabilidad
                    kp.conf = max(0.0, kp.conf - self.conf_decay_per_s * dt)
                    if t_us - kp.held_since_us > self.held_timeout_us:
                        kp.state = int(KpState.INVALID)
                        kp.conf = 0.0
                # INVALID: se mantiene (sentinel de coordenada retenida, conf 0)
            out.append((kp.x, kp.y, kp.conf, kp.state, kp.age_frames, kp.age_us))
        return out
