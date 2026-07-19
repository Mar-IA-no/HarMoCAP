"""SlotManager — N slots estables + foco + REASOCIACIÓN (H4a, contrato 1.1/1.2).

Capas de identidad (plan H4):
- El tracker (BoT-SORT+ReID en modo grupo) re-asocia por apariencia.
- Esta capa re-asocia a nivel SLOT por posición predicha + tamaño + borde de
  salida: aunque el tracker bautice de nuevo a una persona tras oclusión o
  salida de cuadro, el slot (lo que Nico escucha) no se entera.
- Matcher determinista y auditable; umbrales en configs/identity.yaml.

Reglas previas intactas: asignación lowest-free, histéresis del incumbente,
tombstones repetidos, foco auto (ratio de switch, PR #1) / manual con reversión.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


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
        dx = abs(self.bbox_xywhn[0] - 0.5)
        dy = abs(self.bbox_xywhn[1] - 0.5)
        return 1.0 - min(1.0, (dx * dx + dy * dy) ** 0.5)


class SlotState:
    EMPTY = "empty"
    ACTIVE = "active"
    OCCLUDED = "occluded"
    RELEASING = "releasing"
    TOMBSTONE = "tombstone"


@dataclass
class _Slot:
    state: str = SlotState.EMPTY
    track_id: int | None = None
    lost_since_us: int | None = None
    tombstones_left: int = 0
    # H4a — estado para reasociación:
    last_center: tuple[float, float] | None = None
    last_area: float = 0.0
    vel: tuple[float, float] = (0.0, 0.0)     # EMA de velocidad del centro (norm/s)
    last_seen_us: int = 0
    exit_edge: str = "none"                   # left|right|top|bottom|none


@dataclass
class SlotEvent:
    """Resultado por slot de un update(): qué emitir y si resetear estado."""
    slot_id: int
    detection: Detection | None
    emit_tombstone: bool
    slot_reset: bool          # True → el pipeline resetea smoother+features
    rebound: bool = False     # True si este frame hubo reasociación de track


_VEL_EMA = 0.3   # peso de la muestra nueva en la EMA de velocidad


class SlotManager:
    """Gestor de N slots estables + foco + reasociación. Thread-safe en el foco."""

    def __init__(self, *, max_slots: int = 8,
                 occlusion_grace_ms: float = 1500.0,
                 release_timeout_ms: float = 3000.0,
                 acquire_rule: str = "largest_bbox",
                 auto_focus_switch_ratio: float = 1.20,
                 tombstone_repeat_frames: int = 15,
                 reacquisition: dict | None = None):
        self.max_slots = max_slots
        self.occlusion_grace_us = occlusion_grace_ms * 1000.0
        self.release_timeout_us = release_timeout_ms * 1000.0
        self.acquire_rule = acquire_rule
        self.auto_focus_switch_ratio = auto_focus_switch_ratio
        self.tombstone_repeat_frames = tombstone_repeat_frames
        rq = reacquisition or {}
        self.rq_enabled = rq.get("enabled", True)
        self.rq_max_pred_dist = rq.get("max_pred_dist", 0.35)
        self.rq_growth_per_s = rq.get("pred_dist_growth_per_s", 0.15)
        self.rq_size_ratio_max = rq.get("size_ratio_max", 1.8)
        self.rq_edge_margin = rq.get("edge_margin", 0.06)
        self.rq_edge_gate_dist = rq.get("edge_gate_dist", 0.30)
        self.rq_teleport_dist = rq.get("teleport_reset_dist", 0.25)
        self._slots = [_Slot() for _ in range(max_slots)]
        self._focus_lock = threading.Lock()
        self._manual_focus: int | None = None
        self._auto_focus: int | None = None
        self.rebind_count = 0        # telemetría: reasociaciones realizadas

    # ------------------------------------------------------------------- foco
    def select_focus(self, slot: int) -> bool:
        with self._focus_lock:
            if slot < 0:
                self._manual_focus = None
                return True
            if 0 <= slot < self.max_slots:
                self._manual_focus = slot
                return True
            return False

    def select_auto(self) -> None:
        self.select_focus(-1)

    @property
    def focused_slot(self) -> int | None:
        with self._focus_lock:
            return self._manual_focus if self._manual_focus is not None \
                else self._auto_focus

    @property
    def focus_mode(self) -> str:
        with self._focus_lock:
            return "manual" if self._manual_focus is not None else "auto"

    # -------------------------------------------------------------- helpers H4a
    def _touch(self, slot: _Slot, det: Detection, t_us: int) -> None:
        """Actualiza el estado cinemático del slot con la detección del frame."""
        cx, cy = det.bbox_xywhn[0], det.bbox_xywhn[1]
        if slot.last_center is not None and t_us > slot.last_seen_us:
            dt = (t_us - slot.last_seen_us) / 1e6
            if dt > 0:
                vx = (cx - slot.last_center[0]) / dt
                vy = (cy - slot.last_center[1]) / dt
                slot.vel = (slot.vel[0] * (1 - _VEL_EMA) + vx * _VEL_EMA,
                            slot.vel[1] * (1 - _VEL_EMA) + vy * _VEL_EMA)
        slot.last_center = (cx, cy)
        slot.last_area = det.area
        slot.last_seen_us = t_us

    def _exit_edge_of(self, slot: _Slot) -> str:
        """Borde que tocaba la última bbox al perderse (o 'none' si interior)."""
        if slot.last_center is None:
            return "none"
        cx, cy = slot.last_center
        m = self.rq_edge_margin
        # aproximamos con el centro ± semiancho: usamos área para el semiancho
        half = (slot.last_area ** 0.5) / 2.0
        if cx - half <= m:
            return "left"
        if cx + half >= 1.0 - m:
            return "right"
        if cy - half <= m:
            return "top"
        if cy + half >= 1.0 - m:
            return "bottom"
        return "none"

    def _reacquisition_score(self, slot: _Slot, det: Detection, t_us: int
                             ) -> float | None:
        """None si no pasa los gates; si pasa, distancia (menor = mejor)."""
        if slot.last_center is None:
            return None
        dt = max((t_us - slot.last_seen_us) / 1e6, 0.0)
        # gate de tamaño
        if slot.last_area > 1e-9 and det.area > 1e-9:
            ratio = max(det.area / slot.last_area, slot.last_area / det.area)
            if ratio > self.rq_size_ratio_max:
                return None
        cx, cy = det.bbox_xywhn[0], det.bbox_xywhn[1]
        if slot.exit_edge != "none":
            # salió por un borde: debe reaparecer cerca del MISMO borde
            edge_dist = {"left": cx, "right": 1.0 - cx,
                         "top": cy, "bottom": 1.0 - cy}[slot.exit_edge]
            if edge_dist > self.rq_edge_gate_dist:
                return None
            # distancia a la última posición conocida (sin predicción: al salir
            # de cuadro la velocidad extrapolada no es confiable)
            dx = cx - slot.last_center[0]
            dy = cy - slot.last_center[1]
            return (dx * dx + dy * dy) ** 0.5
        # oclusión interior: gate por posición PREDICHA con incertidumbre creciente
        px = slot.last_center[0] + slot.vel[0] * dt
        py = slot.last_center[1] + slot.vel[1] * dt
        dx, dy = cx - px, cy - py
        dist = (dx * dx + dy * dy) ** 0.5
        gate = self.rq_max_pred_dist + self.rq_growth_per_s * dt
        if dist > gate:
            return None
        return dist

    # ----------------------------------------------------------------- update
    def update(self, detections: list[Detection], t_us: int) -> list[SlotEvent]:
        by_id = {d.track_id: d for d in detections if d.track_id is not None}
        events: list[SlotEvent] = []
        claimed: set[int] = set()

        # 1) incumbentes: retienen su slot con histéresis
        for sid, slot in enumerate(self._slots):
            if slot.state in (SlotState.ACTIVE, SlotState.OCCLUDED, SlotState.RELEASING):
                det = by_id.get(slot.track_id)
                if det is not None:
                    slot.state = SlotState.ACTIVE
                    slot.lost_since_us = None
                    self._touch(slot, det, t_us)
                    claimed.add(slot.track_id)
                    events.append(SlotEvent(sid, det, False, False))
                    continue
                if slot.lost_since_us is None:
                    slot.lost_since_us = t_us
                    slot.exit_edge = self._exit_edge_of(slot)   # H4a: borde de salida
                lost_for = t_us - slot.lost_since_us
                if lost_for <= self.occlusion_grace_us:
                    slot.state = SlotState.OCCLUDED
                elif lost_for <= self.release_timeout_us:
                    slot.state = SlotState.RELEASING
                else:
                    slot.state = SlotState.TOMBSTONE
                    slot.track_id = None
                    slot.lost_since_us = None
                    slot.last_center = None
                    slot.exit_edge = "none"
                    slot.tombstones_left = max(0, self.tombstone_repeat_frames - 1)
                    events.append(SlotEvent(sid, None, True, True))
            elif slot.state == SlotState.TOMBSTONE:
                if slot.tombstones_left > 0:
                    slot.tombstones_left -= 1
                    events.append(SlotEvent(sid, None, True, False))
                else:
                    slot.state = SlotState.EMPTY

        unclaimed = [d for tid, d in by_id.items() if tid not in claimed]

        # 2) H4a — REASOCIACIÓN (ANTES de asignar slots libres, autoauditoría #4):
        #    tracks nuevos vs slots ausentes, greedy por distancia (determinista)
        if self.rq_enabled and unclaimed:
            lost_slots = [i for i, s in enumerate(self._slots)
                          if s.state in (SlotState.OCCLUDED, SlotState.RELEASING)]
            pairs = []
            for det in unclaimed:
                for sid in lost_slots:
                    score = self._reacquisition_score(self._slots[sid], det, t_us)
                    if score is not None:
                        pairs.append((score, sid, det))
            pairs.sort(key=lambda p: (p[0], p[1], p[2].track_id))
            used_slots: set[int] = set()
            used_tracks: set[int] = set()
            for score, sid, det in pairs:
                if sid in used_slots or det.track_id in used_tracks:
                    continue
                slot = self._slots[sid]
                # teleport check: ¿el salto respecto de la última posición exige reset?
                dx = det.bbox_xywhn[0] - slot.last_center[0]
                dy = det.bbox_xywhn[1] - slot.last_center[1]
                teleport = (dx * dx + dy * dy) ** 0.5 > self.rq_teleport_dist
                slot.state = SlotState.ACTIVE
                slot.track_id = det.track_id
                slot.lost_since_us = None
                slot.exit_edge = "none"
                slot.vel = (0.0, 0.0)          # la velocidad vieja ya no es confiable
                self._touch(slot, det, t_us)
                self.rebind_count += 1
                used_slots.add(sid)
                used_tracks.add(det.track_id)
                claimed.add(det.track_id)
                # slot_reset solo si teleport (resetea One-Euro + features en pipeline)
                events.append(SlotEvent(sid, det, False, teleport, rebound=True))
            unclaimed = [d for d in unclaimed if d.track_id not in used_tracks]

        # 3) tracks restantes → slots libres (lowest-free, orden determinista)
        free = [i for i, s in enumerate(self._slots) if s.state == SlotState.EMPTY]
        key = (lambda d: -d.area) if self.acquire_rule == "largest_bbox" \
            else (lambda d: -d.centrality)
        for det in sorted(unclaimed, key=key):
            if not free:
                break
            sid = free.pop(0)
            slot = self._slots[sid]
            slot.state = SlotState.ACTIVE
            slot.track_id = det.track_id
            slot.lost_since_us = None
            slot.vel = (0.0, 0.0)
            self._touch(slot, det, t_us)
            events.append(SlotEvent(sid, det, False, True))

        # 4) foco automático con histéresis de ratio (PR #1) + reversión del manual
        active = {e.slot_id: e.detection for e in events if e.detection is not None}
        with self._focus_lock:
            if self._manual_focus is not None and \
                    self._slots[self._manual_focus].state in (
                        SlotState.EMPTY, SlotState.TOMBSTONE):
                self._manual_focus = None
            if not active:
                self._auto_focus = None
            else:
                best = max(active, key=lambda s: active[s].area)
                if self._auto_focus not in active:
                    self._auto_focus = best
                elif best != self._auto_focus:
                    current_area = active[self._auto_focus].area
                    if active[best].area >= current_area * self.auto_focus_switch_ratio:
                        self._auto_focus = best

        events.sort(key=lambda e: e.slot_id)
        return events
