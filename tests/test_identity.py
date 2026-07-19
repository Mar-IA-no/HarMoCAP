"""H2 — SlotManager multi-slot + foco (contrato 1.1)."""
from harmocap.identity import Detection, SlotManager, SlotState

KP = [(0.5, 0.5, 0.9)] * 17
US = 1_000_000
DT = 33_000


def det(track_id, area=0.1, cx=0.5):
    w = area ** 0.5
    return Detection(track_id=track_id, bbox_xywhn=(cx, 0.5, w, w),
                     keypoints_iso=KP)


def slots_of(events):
    return {e.slot_id: e for e in events}


# ---------------------------------------------------------------- asignación
def test_lowest_free_slot_assignment():
    sm = SlotManager(max_slots=8)
    ev = slots_of(sm.update([det(7, 0.3), det(9, 0.2), det(11, 0.1)], US))
    # mayor área primero → slot más bajo
    assert ev[0].detection.track_id == 7
    assert ev[1].detection.track_id == 9
    assert ev[2].detection.track_id == 11
    assert all(ev[i].slot_reset for i in (0, 1, 2))


def test_incumbents_keep_slots_new_person_gets_free():
    sm = SlotManager(max_slots=8)
    sm.update([det(7), det(9)], US)
    # entra una tercera MÁS GRANDE: no roba slots, va al 2
    ev = slots_of(sm.update([det(7), det(9), det(30, area=0.5)], US + DT))
    assert ev[0].detection.track_id == 7
    assert ev[1].detection.track_id == 9
    assert ev[2].detection.track_id == 30


def test_more_persons_than_slots_ignored():
    sm = SlotManager(max_slots=2)
    ev = sm.update([det(i, area=0.1 + i * 0.01) for i in range(5)], US)
    assert len([e for e in ev if e.detection]) == 2


# ---------------------------------------------------------------- histéresis
def test_per_slot_occlusion_release_tombstone():
    sm = SlotManager(max_slots=4, occlusion_grace_ms=100,
                     release_timeout_ms=300, tombstone_repeat_frames=3)
    sm.update([det(7), det(9)], US)
    t = US
    # el 9 desaparece; el 7 sigue
    t += 50_000
    ev = slots_of(sm.update([det(7)], t))
    assert 0 in ev and 1 not in ev            # slot 1 ocluido: sin evento aún
    # pasa el release del 9 → tombstone del slot 1, slot 0 intacto
    t += 500_000
    ev = slots_of(sm.update([det(7)], t))
    assert ev[1].emit_tombstone and ev[1].slot_reset
    assert ev[0].detection.track_id == 7
    # tombstones repetidos: total = 3 configurados
    tombs = 1
    for _ in range(5):
        t += DT
        ev = slots_of(sm.update([det(7)], t))
        tombs += int(1 in ev and ev[1].emit_tombstone)
    assert tombs == 3
    # el slot 1 quedó libre: una persona nueva lo toma
    t += DT
    ev = slots_of(sm.update([det(7), det(50)], t))
    assert ev[1].detection.track_id == 50 and ev[1].slot_reset


def test_incumbent_returns_within_grace():
    sm = SlotManager(max_slots=2, occlusion_grace_ms=200, release_timeout_ms=500)
    sm.update([det(7)], US)
    sm.update([], US + 50_000)
    ev = slots_of(sm.update([det(7)], US + 100_000))
    assert ev[0].detection.track_id == 7 and not ev[0].slot_reset


# ---------------------------------------------------------------- foco
def test_auto_focus_largest_with_hysteresis():
    sm = SlotManager(max_slots=4)
    sm.update([det(7, area=0.2), det(9, area=0.1)], US)
    assert sm.focused_slot == 0 and sm.focus_mode == "auto"
    # una diferencia pequeña no cambia el foco para evitar parpadeos
    sm.update([det(7, area=0.2), det(9, area=0.21)], US + DT)
    assert sm.focused_slot == 0
    # un nuevo mayor claramente más grande sí toma el foco automáticamente
    sm.update([det(7, area=0.2), det(9, area=0.4)], US + 2 * DT)
    assert sm.focused_slot == 1


def test_manual_select_and_revert_on_death():
    sm = SlotManager(max_slots=4, occlusion_grace_ms=10, release_timeout_ms=20,
                     tombstone_repeat_frames=0)
    sm.update([det(7, area=0.3), det(9, area=0.1)], US)
    assert sm.select_focus(1)
    assert sm.focused_slot == 1 and sm.focus_mode == "manual"
    # muere el focal: 1er update marca la pérdida, 2do (pasado release) retira
    sm.update([det(7, area=0.3)], US + DT)
    sm.update([det(7, area=0.3)], US + DT + 100_000)   # 100 ms > release 20 ms
    assert sm.focus_mode == "auto"
    assert sm.focused_slot == 0


def test_select_focus_validates_range():
    sm = SlotManager(max_slots=4)
    assert not sm.select_focus(99)
    assert sm.select_focus(-1)        # -1 = volver a auto
    assert sm.focus_mode == "auto"


# ---------------------------------------------------------------- compat MVP
def test_single_slot_compat():
    """max_slots=1 reproduce el comportamiento del slot principal del MVP."""
    sm = SlotManager(max_slots=1)
    ev = slots_of(sm.update([det(7, area=0.05), det(9, area=0.5)], US))
    assert list(ev) == [0]
    assert ev[0].detection.track_id == 9      # mayor área adquiere
    # el incumbente retiene aunque entre otro más grande
    ev = slots_of(sm.update([det(9, area=0.1), det(11, area=0.9)], US + DT))
    assert ev[0].detection.track_id == 9


# ---------------------------------------------------------- H4a: reasociación
def rdet(track_id, cx=0.5, cy=0.5, area=0.04):
    w = area ** 0.5
    return Detection(track_id=track_id, bbox_xywhn=(cx, cy, w, w),
                     keypoints_iso=KP)


def _rq_manager(**over):
    rq = {"enabled": True, "max_pred_dist": 0.2, "pred_dist_growth_per_s": 0.1,
          "size_ratio_max": 1.8, "edge_margin": 0.06, "edge_gate_dist": 0.3,
          "teleport_reset_dist": 0.25}
    rq.update(over)
    return SlotManager(max_slots=4, occlusion_grace_ms=2000,
                       release_timeout_ms=5000, reacquisition=rq)


def test_reacquisition_near_prediction_same_slot():
    """Oclusión interior → track NUEVO cerca de la posición → MISMO slot."""
    sm = _rq_manager()
    t = US
    for _ in range(5):                       # establecer velocidad ~0
        sm.update([rdet(7, cx=0.5)], t); t += DT
    sm.update([], t); t += DT                # se ocluye
    sm.update([], t); t += DT
    ev = {e.slot_id: e for e in sm.update([rdet(99, cx=0.53)], t)}
    assert 0 in ev and ev[0].detection.track_id == 99   # re-bindeado al slot 0
    assert ev[0].rebound and not ev[0].slot_reset       # sin teleport → sin reset
    assert sm.rebind_count == 1


def test_reacquisition_far_gets_new_slot():
    """Track nuevo LEJOS de la predicción → slot nuevo, no roba el ausente."""
    sm = _rq_manager()
    t = US
    for _ in range(3):
        sm.update([rdet(7, cx=0.2)], t); t += DT
    sm.update([], t); t += DT
    ev = {e.slot_id: e for e in sm.update([rdet(99, cx=0.9)], t)}
    assert 1 in ev and ev[1].detection.track_id == 99    # slot NUEVO (1)
    assert 0 not in ev or ev[0].detection is None


def test_reacquisition_edge_gating():
    """Salió por la izquierda → solo reaparece por la izquierda."""
    sm = _rq_manager()
    t = US
    for _ in range(3):
        sm.update([rdet(7, cx=0.05)], t); t += DT       # pegado al borde izq
    sm.update([], t); t += DT                            # sale de cuadro
    # reaparece por la DERECHA: NO debe re-bindear
    ev = {e.slot_id: e for e in sm.update([rdet(99, cx=0.95)], t)}
    assert ev.get(0) is None or ev[0].detection is None
    t += DT
    # reaparece por la IZQUIERDA: SÍ
    ev = {e.slot_id: e for e in sm.update([rdet(50, cx=0.08)], t)}
    assert 0 in ev and ev[0].detection.track_id == 50 and ev[0].rebound


def test_reacquisition_teleport_triggers_reset():
    """Re-bind con salto grande → slot_reset=True (One-Euro+features)."""
    sm = _rq_manager(max_pred_dist=0.6, teleport_reset_dist=0.2)
    t = US
    for _ in range(3):
        sm.update([rdet(7, cx=0.3)], t); t += DT
    sm.update([], t); t += DT
    ev = {e.slot_id: e for e in sm.update([rdet(99, cx=0.75)], t)}
    assert 0 in ev and ev[0].rebound and ev[0].slot_reset


def test_reacquisition_size_gate():
    """Bbox de tamaño muy distinto no se re-bindea (otra persona)."""
    sm = _rq_manager()
    t = US
    for _ in range(3):
        sm.update([rdet(7, cx=0.5, area=0.01)], t); t += DT
    sm.update([], t); t += DT
    ev = {e.slot_id: e for e in sm.update([rdet(99, cx=0.5, area=0.09)], t)}
    assert not any(e.rebound for e in ev.values())


def test_reacquisition_disabled():
    sm = _rq_manager(enabled=False)
    t = US
    for _ in range(3):
        sm.update([rdet(7, cx=0.5)], t); t += DT
    sm.update([], t); t += DT
    ev = {e.slot_id: e for e in sm.update([rdet(99, cx=0.52)], t)}
    assert 1 in ev and not any(e.rebound for e in ev.values())
