"""Slot principal estable — máquina de estados con histéresis (plan M2, r2 #9).

Separa el slot estable (lo que Nico escucha) del track_id efímero de ByteTrack:
- Mantiene al INCUMBENTE mientras su track sea válido (nadie le roba el slot).
- Tolera oclusión durante occlusion_grace_ms.
- Libera el slot SOLO tras release_timeout_ms; recién entonces reacquiere con
  desempate determinista (mayor área de bbox o más central).
- boxes.id is None → NO se emite slot provisional: se espera al tracker
  (addendum #5, sin salto de identidad).
- Al retirarse el incumbente emite tombstone repetido N frames (r8 #1) y el
  estado de features se resetea (finding #3).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Detection:
    """Una detección trackeada de un frame (ya extraída de Ultralytics)."""
    track_id: int
    bbox_xywhn: tuple[float, float, float, float]   # xc, yc, w, h normalizados
    keypoints_iso: list[tuple[float, float, float]]  # coords isotrópicas + conf YOLO

    @property
    def area(self) -> float:
        return self.bbox_xywhn[2] * self.bbox_xywhn[3]

    @property
    def centrality(self) -> float:
        # 1 en el centro del frame, decae hacia los bordes (en coords normalizadas)
        dx = abs(self.bbox_xywhn[0] - 0.5)
        dy = abs(self.bbox_xywhn[1] - 0.5)
        return 1.0 - min(1.0, (dx * dx + dy * dy) ** 0.5)


class SlotState:
    EMPTY = "empty"          # sin incumbente
    ACTIVE = "active"        # incumbente visible
    OCCLUDED = "occluded"    # incumbente perdido < grace
    RELEASING = "releasing"  # perdido > grace, esperando release_timeout
    TOMBSTONE = "tombstone"  # emitiendo present=0 repetido


class PrincipalSlot:
    """MVP unipersonal: un solo slot (slot_id=0), esquema multi-persona a futuro."""

    SLOT_ID = 0

    def __init__(self, *, occlusion_grace_ms: float = 1500.0,
                 release_timeout_ms: float = 3000.0,
                 acquire_rule: str = "largest_bbox",
                 tombstone_repeat_frames: int = 15):
        self.occlusion_grace_us = occlusion_grace_ms * 1000.0
        self.release_timeout_us = release_timeout_ms * 1000.0
        self.acquire_rule = acquire_rule
        self.tombstone_repeat_frames = tombstone_repeat_frames
        self.state = SlotState.EMPTY
        self.incumbent_track_id: int | None = None
        self._lost_since_us: int | None = None
        self._tombstones_left = 0

    # -- API -----------------------------------------------------------------

    def update(self, detections: list[Detection], t_us: int
               ) -> tuple[Detection | None, bool, bool]:
        """Devuelve (detección_del_slot | None, emit_tombstone, slot_reset).

        slot_reset=True el frame en que el incumbente cambia o se retira:
        el llamador debe resetear smoother + features (finding #3).
        """
        by_id = {d.track_id: d for d in detections if d.track_id is not None}

        if self.state in (SlotState.ACTIVE, SlotState.OCCLUDED, SlotState.RELEASING):
            det = by_id.get(self.incumbent_track_id)
            if det is not None:
                # el incumbente sigue: retiene el slot pase lo que pase (histéresis)
                self.state = SlotState.ACTIVE
                self._lost_since_us = None
                return det, False, False
            # incumbente no visible este frame
            if self._lost_since_us is None:
                self._lost_since_us = t_us
            lost_for = t_us - self._lost_since_us
            if lost_for <= self.occlusion_grace_us:
                self.state = SlotState.OCCLUDED
                return None, False, False   # oclusión: sin datos, sin tombstone aún
            if lost_for <= self.release_timeout_us:
                self.state = SlotState.RELEASING
                return None, False, False
            # timeout: retirar al incumbente. Este retiro emite el 1er tombstone;
            # quedan N-1 repeticiones (total = tombstone_repeat_frames, r8 #1)
            self.state = SlotState.TOMBSTONE
            self.incumbent_track_id = None
            self._lost_since_us = None
            self._tombstones_left = max(0, self.tombstone_repeat_frames - 1)
            return None, True, True

        if self.state == SlotState.TOMBSTONE:
            if self._tombstones_left > 0:
                self._tombstones_left -= 1
                if not by_id:
                    return None, True, False
                # hay candidatos: cerrar el duelo de tombstones y reacquirir ya
            self.state = SlotState.EMPTY

        # EMPTY: reacquirir con desempate determinista
        if by_id:
            key = (lambda d: d.area) if self.acquire_rule == "largest_bbox" \
                else (lambda d: d.centrality)
            det = max(by_id.values(), key=key)
            self.incumbent_track_id = det.track_id
            self.state = SlotState.ACTIVE
            self._lost_since_us = None
            return det, False, True   # slot_reset: incumbente nuevo
        return None, False, False
