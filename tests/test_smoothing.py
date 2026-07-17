"""M2 — One-Euro y máquina de estados de keypoints (plan Verificación M2)."""
import math

import pytest

from harmocap.schema import KpState, N_KEYPOINTS
from harmocap.smoothing import KeypointSmoother, OneEuroFilter

DT_US = 33_333  # ~30 fps


def _kps(conf=0.9, x=0.5, y=0.5):
    return [(x, y, conf)] * N_KEYPOINTS


def test_one_euro_reduces_jitter():
    """Señal con ruido determinista: la varianza filtrada debe bajar."""
    f = OneEuroFilter(mincutoff=1.0, beta=0.1)
    raw, filt = [], []
    for i in range(300):
        # posición quieta + jitter sintético determinista
        x = 0.5 + 0.01 * math.sin(i * 2.1) * math.cos(i * 7.3)
        raw.append(x)
        filt.append(f(x, 1 / 30))
    var = lambda xs: sum((v - sum(xs) / len(xs)) ** 2 for v in xs) / len(xs)
    assert var(filt[50:]) < var(raw[50:]) * 0.5  # al menos 2x menos varianza


def test_one_euro_tracks_fast_motion():
    """A alta velocidad el filtro sigue la señal, y subir beta reduce el lag."""
    def lag(beta):
        f = OneEuroFilter(mincutoff=1.0, beta=beta)
        x = 0.0
        for i in range(60):
            x = i * 0.02                  # movimiento rápido constante
            y = f(x, 1 / 30)
        return abs(y - x)
    assert lag(0.15) < 0.1                # con defaults el lag queda acotado
    assert lag(2.0) < lag(0.15) * 0.6     # la perilla beta reduce el lag (doc oficial)


def test_state_machine_observed_to_held_to_invalid():
    """Transición completa observed→held→invalid con timeout (r6 #4)."""
    sm = KeypointSmoother(conf_threshold=0.35, held_timeout_ms=200)
    t = 1_000_000
    out = sm.update(_kps(conf=0.9), t)
    assert all(o[3] == int(KpState.OBSERVED) for o in out)

    # conf cae: primer frame → held, coordenada retenida (hold-last, no cero)
    t += DT_US
    out = sm.update(_kps(conf=0.1, x=0.9), t)   # x=0.9 basura: NO debe usarse
    assert all(o[3] == int(KpState.HELD) for o in out)
    assert all(abs(o[0] - 0.5) < 0.01 for o in out)   # retiene 0.5, no salta a 0.9

    # conf decae durante held (r6 #5): conf efectiva < conf original
    assert all(o[2] < 0.9 for o in out)

    # pasado el timeout → invalid
    for _ in range(10):
        t += DT_US
        out = sm.update(_kps(conf=0.1), t)
    assert all(o[3] == int(KpState.INVALID) for o in out)
    assert all(o[2] == 0.0 for o in out)

    # edad acumulada
    assert all(o[4] > 0 and o[5] > 0 for o in out)


def test_state_machine_reset_on_reobservation():
    """Tras invalid, una observación válida reinicializa el filtro (sin arrastre)."""
    sm = KeypointSmoother(conf_threshold=0.35, held_timeout_ms=100)
    t = 1_000_000
    sm.update(_kps(conf=0.9, x=0.2), t)
    for _ in range(10):                      # → invalid
        t += DT_US
        sm.update(_kps(conf=0.1), t)
    t += DT_US
    out = sm.update(_kps(conf=0.9, x=0.8), t)
    assert all(o[3] == int(KpState.OBSERVED) for o in out)
    # el filtro se reinicializó: la salida arranca EN 0.8, sin arrastre desde 0.2
    assert all(abs(o[0] - 0.8) < 1e-6 for o in out)
    assert all(o[4] == 0 and o[5] == 0 for o in out)


def test_no_direct_jump_to_invalid():
    """No se salta directo a invalid: siempre pasa por held (r6 #4)."""
    sm = KeypointSmoother(conf_threshold=0.35, held_timeout_ms=500)
    t = 1_000_000
    sm.update(_kps(conf=0.9), t)
    out = sm.update(_kps(conf=0.0), t + DT_US)
    assert all(o[3] == int(KpState.HELD) for o in out)
