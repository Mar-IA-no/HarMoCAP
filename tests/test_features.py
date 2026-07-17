"""M3 — invarianzas y casos de borde de features (plan Verificación M3)."""
import math

import pytest

from harmocap.features import CalibrationManager, FeatureExtractor
from harmocap.schema import FEATURE_ORDER, KpState, N_KEYPOINTS

FALLBACK = {"torso_height_norm": 0.28, "vmax_hand": 3.0, "vmax_center": 1.5,
            "jerk_ref": 40.0, "energy_ref": 4.0, "accel_ref": 8.0}
WINDOWS = {"velocity_ms": 120, "accel_ms": 200, "jerk_ms": 300, "qom_ms": 400}
OBS = int(KpState.OBSERVED)
DT_US = 33_333


def make_pose(scale=1.0, dx=0.0, dy=0.0, arms_up=False):
    """Esqueleto de pie, frontal; retorna [(x,y,conf,state,af,aus)]*17."""
    base = {
        0: (0.50, 0.18), 1: (0.48, 0.165), 2: (0.52, 0.165),
        3: (0.46, 0.18), 4: (0.54, 0.18),
        5: (0.40, 0.34), 6: (0.60, 0.34),
        7: (0.37, 0.48), 8: (0.63, 0.48),
        9: (0.36, 0.61), 10: (0.64, 0.61),
        11: (0.425, 0.62), 12: (0.575, 0.62),
        13: (0.43, 0.78), 14: (0.57, 0.78),
        15: (0.435, 0.95), 16: (0.565, 0.95),
    }
    if arms_up:
        base[7] = (0.31, 0.24); base[8] = (0.69, 0.24)
        base[9] = (0.26, 0.10); base[10] = (0.74, 0.10)
    out = []
    for i in range(N_KEYPOINTS):
        x, y = base[i]
        out.append((x * scale + dx, y * scale + dy, 0.9, OBS, 0, 0))
    return out


def run_static(pose, n=12):
    """Corre n frames de la misma pose y devuelve el último (vals, states)."""
    calib = CalibrationManager(FALLBACK, period_ms=60_000)  # nunca congela
    fe = FeatureExtractor(WINDOWS, calib)
    t = 1_000_000
    for _ in range(n):
        t += DT_US
        vals, states = fe.extract(pose, t)
    return dict(zip(FEATURE_ORDER, vals)), states


def test_scale_invariance():
    """Misma pose a dos escalas → mismas features (normalización por torso)."""
    a, _ = run_static(make_pose(scale=1.0))
    b, _ = run_static(make_pose(scale=0.5))
    for name in ("contraction", "expansion", "symmetry", "verticality",
                 "angle_elbow_l", "angle_knee_r", "qom"):
        assert a[name] == pytest.approx(b[name], abs=0.02), name


def test_translation_invariance():
    a, _ = run_static(make_pose())
    b, _ = run_static(make_pose(dx=0.3, dy=0.05))
    for name in ("contraction", "expansion", "symmetry", "verticality"):
        assert a[name] == pytest.approx(b[name], abs=0.01), name


def test_arms_up_raises_expansion_not_verticality():
    """e2e r2 #16: brazos arriba ↑expansion; verticality NO cambia con brazos."""
    down, _ = run_static(make_pose())
    up, _ = run_static(make_pose(arms_up=True))
    assert up["expansion"] > down["expansion"] + 0.05
    assert up["verticality"] == pytest.approx(down["verticality"], abs=0.05)
    assert up["angle_shoulder_l"] > down["angle_shoulder_l"]


def test_lean_changes_verticality():
    """Inclinar el eje corporal SÍ cambia verticality (r2 #16)."""
    upright, _ = run_static(make_pose())
    # rotar la pose 60° alrededor de la cadera media
    pose = make_pose()
    ox, oy = 0.5, 0.62
    ang = math.radians(60)
    leaned = []
    for x, y, c, s, af, au in pose:
        dx0, dy0 = x - ox, y - oy
        leaned.append((ox + math.cos(ang) * dx0 - math.sin(ang) * dy0,
                       oy + math.sin(ang) * dx0 + math.cos(ang) * dy0,
                       c, s, af, au))
    lean, _ = run_static(leaned)
    assert lean["verticality"] < upright["verticality"] - 0.3


def test_still_pose_low_qom():
    vals, _ = run_static(make_pose(), n=20)
    assert vals["qom"] < 0.05


def test_invalid_keypoint_propagates_and_sentinel():
    """Feature con dep inválida → estado invalid + sentinel 0.0, nunca NaN (r5 #5)."""
    pose = make_pose()
    # invalidar muñeca izquierda (índice 9)
    pose[9] = (0.0, 0.0, 0.0, int(KpState.INVALID), 30, 1_000_000)
    vals_d, states = run_static(pose)
    idx = FEATURE_ORDER.index("vel_hand_l")
    assert states[idx] == int(KpState.INVALID)
    assert vals_d["vel_hand_l"] == 0.0
    # ninguna feature es NaN
    assert all(v == v for v in vals_d.values())


def test_held_keypoint_propagates_held():
    pose = make_pose()
    pose[9] = (0.36, 0.61, 0.2, int(KpState.HELD), 3, 100_000)
    _, states = run_static(pose)
    idx = FEATURE_ORDER.index("vel_hand_l")
    assert states[idx] == int(KpState.HELD)


def test_all_in_range():
    from harmocap.schema import FEATURE_RANGES
    vals, _ = run_static(make_pose(arms_up=True), n=15)
    for name, v in vals.items():
        lo, hi = FEATURE_RANGES[name]
        assert lo <= v <= hi, f"{name}={v} fuera de [{lo},{hi}]"


def test_calibration_freezes_new_generation():
    calib = CalibrationManager(FALLBACK, period_ms=300)
    fe = FeatureExtractor(WINDOWS, calib)
    t = 1_000_000
    froze = False
    for i in range(20):
        t += DT_US
        pose = make_pose()
        torso = fe._torso_height([(p[0], p[1]) for p in pose],
                                 [p[3] for p in pose])
        froze = calib.observe(torso, t, i) or froze
        fe.extract(pose, t)
    assert froze
    assert calib.profile.state == "frozen"
    assert calib.profile.generation == 2      # gen nueva al congelar (r6 #1)
    # el fallback NO se recalculó por frame: params solo cambian al congelar
    assert calib.profile.params[0] == pytest.approx(0.28, abs=0.1)
