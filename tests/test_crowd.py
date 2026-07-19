"""H4b — agregados de multitud (contrato 1.2)."""
from harmocap.crowd import CrowdAggregator

US, DT = 1_000_000, 33_333


def boxes_grid(n, spread=0.3, cx=0.5, cy=0.5):
    import math
    out = []
    for k in range(n):
        a = 2 * math.pi * k / max(n, 1)
        out.append((cx + spread * math.cos(a), cy + spread * math.sin(a),
                    0.05, 0.12))
    return out


def test_empty_frame():
    c = CrowdAggregator()
    r = c.update([], US)
    assert r["crowd_count"] == 0 and r["density"] == 0.0


def test_static_crowd_low_qom_and_counts():
    c = CrowdAggregator()
    t = US
    for _ in range(15):
        r = c.update(boxes_grid(20), t); t += DT
    assert r["crowd_count"] == 20
    assert r["crowd_qom"] < 0.05           # quieta
    assert 0 < r["density"] <= 1.0
    assert abs(r["centroid_y"] - 0.5) < 0.02
    assert r["dispersion"] > 0.2           # dispersa en círculo


def test_moving_crowd_raises_qom_and_flow():
    c = CrowdAggregator()
    t = US
    for i in range(15):
        r = c.update(boxes_grid(10, cx=0.3 + i * 0.01), t); t += DT
    assert r["crowd_qom"] > 0.1
    assert r["flow_x"] > 0.1               # deriva hacia la derecha


def test_ranges_clipped():
    c = CrowdAggregator()
    t = US
    r0 = c.update(boxes_grid(50), t)
    r1 = c.update(boxes_grid(50, cx=0.9), t + 1000)   # salto brutal en 1 ms
    for r in (r0, r1):
        assert 0 <= r["crowd_qom"] <= 1 and 0 <= r["density"] <= 1
        assert -1 <= r["flow_x"] <= 1 and 0 <= r["dispersion"] <= 1
