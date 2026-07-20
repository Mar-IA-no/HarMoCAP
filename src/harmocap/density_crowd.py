"""Agregados de masa por densidad (H6, decisión A+C) — masa presente y activa.

Sobre el mapa de densidad del `DensityBackend` calcula, por cuadro:
  masa PRESENTE : suma del mapa = toda la gente en cuadro.
  masa ACTIVA   : suma de densidad × movimiento local = cuánta se mueve.
más el centroide y la dispersión espacial de la masa (momentos del campo).

Escala absoluta: NO es confiable (el modelo no está ajustado a nuestro dominio,
la investigación lo documenta). Lo que sí es útil es la DINÁMICA RELATIVA, así
que ambas masas se normalizan contra un percentil rodante de la propia sesión:
'sube cuando entra gente, baja cuando se vacía', sin pretender contar exacto.

Todo causal: el movimiento es diferencia de cuadros (mira solo hacia atrás) y el
percentil se toma sobre una ventana trailing.
"""
from __future__ import annotations

import numpy as np

_NORM_WINDOW_S = 20.0      # ventana del percentil rodante (dinámica de sesión)
_NORM_PCTL = 95.0          # el pico de referencia = p95 de la ventana
_NORM_MIN_SAMPLES = 30     # antes de esto la normalización es provisional
_MOTION_DECAY = 0.5        # EMA del mapa de movimiento (suaviza el frame-diff)


class DensityCrowdAggregator:
    def __init__(self, norm_window_s: float = _NORM_WINDOW_S):
        self._prev_gray: np.ndarray | None = None
        self._motion_ema: np.ndarray | None = None
        self._present_hist: list[tuple[int, float]] = []   # (t_us, masa cruda)
        self._active_hist: list[tuple[int, float]] = []
        self._win_us = norm_window_s * 1e6

    def reset(self) -> None:
        self._prev_gray = None
        self._motion_ema = None
        self._present_hist.clear()
        self._active_hist.clear()

    def _norm(self, hist: list[tuple[int, float]], value: float, t_us: int) -> float:
        hist.append((t_us, value))
        while hist and t_us - hist[0][0] > self._win_us:
            hist.pop(0)
        if len(hist) < _NORM_MIN_SAMPLES:
            return 0.0                       # provisional: sin rango aún
        ref = np.percentile([v for _t, v in hist], _NORM_PCTL)
        return float(min(value / ref, 1.0)) if ref > 1e-6 else 0.0

    def update(self, density_map: np.ndarray, frame_rgb: np.ndarray,
               t_us: int) -> dict:
        """density_map: (dh, dw) del backend. frame_rgb: HxWx3 uint8."""
        dm = np.clip(density_map, 0.0, None)
        present_raw = float(dm.sum())

        # movimiento local: |ΔI| en gris, submuestreado a la grilla del mapa
        gray = frame_rgb.mean(axis=2).astype(np.float32)
        dh, dw = dm.shape
        motion_grid = np.zeros_like(dm)
        if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
            diff = np.abs(gray - self._prev_gray)
            # promedio por bloque hasta (dh, dw) sin dependencias extra
            hh, ww = gray.shape
            ys = (np.arange(hh) * dh // hh)
            xs = (np.arange(ww) * dw // ww)
            acc = np.zeros((dh, dw), np.float32)
            cnt = np.zeros((dh, dw), np.float32)
            np.add.at(acc, (ys[:, None], xs[None, :]), diff)
            np.add.at(cnt, (ys[:, None], xs[None, :]), 1.0)
            motion_grid = acc / np.maximum(cnt, 1.0) / 255.0
        self._prev_gray = gray
        if self._motion_ema is None or self._motion_ema.shape != motion_grid.shape:
            self._motion_ema = motion_grid
        else:
            self._motion_ema = (_MOTION_DECAY * motion_grid
                                + (1 - _MOTION_DECAY) * self._motion_ema)

        active_raw = float((dm * self._motion_ema).sum())

        # momentos espaciales del campo (coords isotrópicas: x escala por aspect)
        total = present_raw + 1e-9
        yy, xx = np.mgrid[0:dh, 0:dw].astype(np.float32)
        aspect = frame_rgb.shape[1] / frame_rgb.shape[0]
        cx = float((dm * xx).sum() / total) / dw * aspect
        cy = float((dm * yy).sum() / total) / dh
        var_x = float((dm * (xx / dw * aspect - cx) ** 2).sum() / total)
        var_y = float((dm * (yy / dh - cy) ** 2).sum() / total)
        semidiag = ((aspect * aspect + 1.0) ** 0.5) / 2.0
        dispersion = min((var_x + var_y) ** 0.5 / semidiag, 1.0)

        return {
            "mass_present": round(self._norm(self._present_hist, present_raw, t_us), 4),
            "mass_active": round(self._norm(self._active_hist, active_raw, t_us), 4),
            "density_count_raw": round(present_raw, 1),   # escala cruda, informativa
            "centroid_x": round(cx, 4), "centroid_y": round(cy, 4),
            "dispersion": round(dispersion, 4),
        }
