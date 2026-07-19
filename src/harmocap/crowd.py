"""Features de MULTITUD (H4b, contrato 1.2) — agregados sobre detecciones crudas.

A diferencia de las features por-persona (slots), estos agregados se calculan
sobre TODAS las detecciones del frame (con y sin track_id): en masa importa el
recall, no la identidad. Causal, ventanas trailing en ms.

Variables (orden del contrato):
  crowd_count  int   conteo crudo de personas detectadas (≠ n_persons de /meta,
                     que cuenta SLOTS emitidos — el spec distingue ambos)
  crowd_qom    0..1  velocidad media de los centros de bbox (norm/s, clip)
  density      0..1  Σ áreas de bbox / área del frame (clip)
  centroid_x   0..~aspect  centro de masa del grupo (coords isotrópicas)
  centroid_y   0..1
  flow_x/y     -1..1 velocidad del centroide (norm/s, clip)
  dispersion   0..1  desvío medio de los centros al centroide / semidiagonal
"""
from __future__ import annotations

from harmocap.features import _TrailBuffer


def _clip(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


class CrowdAggregator:
    CROWD_QOM_VMAX = 1.5      # norm/s que mapea a qom=1.0 (documentado en spec)
    FLOW_VMAX = 0.8           # norm/s que mapea a |flow|=1.0

    def __init__(self, window_ms: float = 400.0):
        self._centers = _TrailBuffer(window_ms)      # (t, lista de centros)
        self._centroid = _TrailBuffer(window_ms)     # (t, centroide)

    def reset(self) -> None:
        self._centers.clear()
        self._centroid.clear()

    def update(self, raw_boxes_xywhn: list[tuple[float, float, float, float]],
               t_us: int, aspect: float = 16 / 9) -> dict:
        """raw_boxes_xywhn: TODAS las detecciones (xc,yc,w,h normalizados)."""
        n = len(raw_boxes_xywhn)
        if n == 0:
            # escena vacía: los baselines de movimiento dejan de ser válidos
            # (autoauditoría h4 M7 — sin esto, flow/qom se computaban contra un
            # snapshot anterior al gap, fuera de la ventana declarada)
            self._centers.clear()
            self._centroid.clear()
            return {"crowd_count": 0, "crowd_qom": 0.0, "density": 0.0,
                    "centroid_x": 0.0, "centroid_y": 0.0,
                    "flow_x": 0.0, "flow_y": 0.0, "dispersion": 0.0}

        # centros en coords ISOTRÓPICAS (x escala por aspect; h4 M2 — qom/flow/
        # dispersion se median en unidades anisotrópicas)
        centers = [(b[0] * aspect, b[1]) for b in raw_boxes_xywhn]
        cx = sum(c[0] for c in centers) / n
        cy = sum(c[1] for c in centers) / n
        density = _clip(sum(b[2] * b[3] for b in raw_boxes_xywhn), 0.0, 1.0)
        semidiag = ((aspect * aspect + 1.0) ** 0.5) / 2.0
        disp = (sum(((c[0] - cx) ** 2 + (c[1] - cy) ** 2) ** 0.5
                    for c in centers) / n) / semidiag
        disp = _clip(disp, 0.0, 1.0)

        # qom colectivo: velocidad media de centros contra el snapshot trailing.
        # push PRIMERO (poda la ventana) y baseline después (h4 M7).
        # Nota (h4 B1): sin correspondencia por identidad, la ENTRADA de una
        # persona nueva aporta su distancia al vecino más cercano — con conteos
        # muy cambiantes es ruido estructural asumido del modo masa.
        self._centers.push(t_us, centers)
        old = self._centers.oldest()
        qom = 0.0
        if old is not None and old[1]:
            t0, prev = old
            dt = (t_us - t0) / 1e6
            if dt >= 1e-3:
                # sin correspondencia por identidad (masa): aproximamos con el
                # promedio de distancias al centro previo más cercano (greedy)
                total = 0.0
                for c in centers:
                    d = min(((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2) ** 0.5
                            for p in prev)
                    total += d
                qom = (total / n) / dt
        qom = _clip(qom / self.CROWD_QOM_VMAX, 0.0, 1.0)

        # flujo del centroide (push primero: poda la ventana — h4 M7)
        self._centroid.push(t_us, (cx, cy))
        old_c = self._centroid.oldest()
        fx = fy = 0.0
        if old_c is not None:
            t0, (px, py) = old_c
            dt = (t_us - t0) / 1e6
            if dt >= 1e-3:
                fx = _clip((cx - px) / dt / self.FLOW_VMAX, -1.0, 1.0)
                fy = _clip((cy - py) / dt / self.FLOW_VMAX, -1.0, 1.0)

        return {"crowd_count": n, "crowd_qom": round(qom, 4),
                "density": round(density, 4),
                "centroid_x": round(cx, 4), "centroid_y": round(cy, 4),
                "flow_x": round(fx, 4), "flow_y": round(fy, 4),
                "dispersion": round(disp, 4)}
