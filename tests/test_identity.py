"""M2 — máquina de estados del slot principal (plan Verificación M2, r2 #9)."""
from harmocap.identity import Detection, PrincipalSlot, SlotState

KP = [(0.5, 0.5, 0.9)] * 17
US = 1_000_000


def det(track_id, area=0.1, cx=0.5):
    w = area ** 0.5
    return Detection(track_id=track_id, bbox_xywhn=(cx, 0.5, w, w),
                     keypoints_iso=KP)


def test_acquire_and_keep_incumbent():
    slot = PrincipalSlot()
    d, tomb, reset = slot.update([det(7)], US)
    assert d.track_id == 7 and reset and not tomb
    # entra otra persona MÁS GRANDE: el incumbente retiene el slot (histéresis)
    d, tomb, reset = slot.update([det(7, area=0.05), det(9, area=0.5)], US + 33_000)
    assert d.track_id == 7 and not reset


def test_occlusion_grace_then_release_then_tombstone():
    slot = PrincipalSlot(occlusion_grace_ms=100, release_timeout_ms=300,
                         tombstone_repeat_frames=3)
    slot.update([det(7)], US)
    t = US
    # oclusión < grace: sin tombstone
    t += 50_000
    d, tomb, reset = slot.update([], t)
    assert d is None and not tomb and slot.state == SlotState.OCCLUDED
    # > grace, < release: releasing (lost_for = 200 ms > 100 ms grace)
    t += 150_000
    d, tomb, reset = slot.update([], t)
    assert slot.state == SlotState.RELEASING and not tomb
    # > release: tombstone + reset (lost_for = 500 ms > 300 ms release)
    t += 300_000
    d, tomb, reset = slot.update([], t)
    assert tomb and reset and slot.incumbent_track_id is None
    # tombstones repetidos (r8 #1)
    tombs = 0
    for _ in range(5):
        t += 33_000
        _, tomb, _ = slot.update([], t)
        tombs += int(tomb)
    assert tombs == 2  # los 3 configurados menos el ya emitido


def test_reacquire_deterministic_largest():
    slot = PrincipalSlot(occlusion_grace_ms=10, release_timeout_ms=20,
                         tombstone_repeat_frames=0)
    slot.update([det(7)], US)
    t = US + 100_000
    slot.update([], t)                       # oclusión
    t += 33_000
    # el incumbente venció: este frame retira (tombstone) aunque haya candidatos
    d, tomb, _ = slot.update([det(1, area=0.04), det(2, area=0.36)], t)
    assert d is None and tomb
    t += 33_000
    d, _, reset = slot.update([det(1, area=0.04), det(2, area=0.36)], t)
    assert d.track_id == 2 and reset          # desempate: mayor área


def test_incumbent_returns_within_grace():
    slot = PrincipalSlot(occlusion_grace_ms=200, release_timeout_ms=500)
    slot.update([det(7)], US)
    slot.update([], US + 50_000)             # se pierde un frame
    d, tomb, reset = slot.update([det(7)], US + 100_000)
    assert d.track_id == 7 and not reset and not tomb
    assert slot.state == SlotState.ACTIVE
