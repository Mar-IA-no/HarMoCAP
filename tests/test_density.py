"""H6-F1 — backend de densidad y agregados de masa (A+C). Causalidad y semántica.

El backend ONNX puede no estar exportado en CI, así que esos tests se saltan si
falta el artefacto; los del agregador corren siempre (no dependen del modelo).
"""
import numpy as np
import pytest

from harmocap.density_crowd import DensityCrowdAggregator

FPS = 30.0


def _map(dh=14, dw=25, blob=None):
    m = np.zeros((dh, dw), np.float32)
    if blob:
        (y, x, v) = blob
        m[y, x] = v
    return m


def _frame(moving_block=None):
    f = np.zeros((360, 640, 3), np.uint8)
    if moving_block is not None:
        x = moving_block
        f[150:250, x:x + 80] = 200
    return f


def test_masa_presente_normaliza_por_percentil_rodante():
    """La masa presente es dinámica relativa contra el p95 rodante: una escena
    que baja del pico de la sesión lee < 1, y volver al pico la sube de nuevo.
    (Con densidad constante satura en 1.0 por definición del percentil — el
    rango de sesión colapsa; en video real la densidad varía y el p95 es techo.)"""
    agg = DensityCrowdAggregator()
    # línea de base con variación: densidad oscilando, con picos ocasionales
    for i in range(60):
        v = 4.0 + 3.0 * (i % 5 == 0)     # picos periódicos fijan el p95 ~7
        agg.update(_map(blob=(7, 12, v)), _frame(), int(i / FPS * 1e6))
    low = agg.update(_map(blob=(7, 12, 2.0)), _frame(), int(60 / FPS * 1e6))
    high = agg.update(_map(blob=(7, 12, 7.0)), _frame(), int(61 / FPS * 1e6))
    assert low["mass_present"] < high["mass_present"], "no refleja la dinámica"
    assert low["mass_present"] < 1.0     # por debajo del pico de sesión


def test_provisional_antes_de_llenar_la_ventana():
    """Sin muestras suficientes la normalización es 0 (rango aún desconocido)."""
    agg = DensityCrowdAggregator()
    out = agg.update(_map(blob=(7, 12, 5.0)), _frame(), 0)
    assert out["mass_present"] == 0.0 and out["mass_active"] == 0.0


def test_masa_activa_separa_movimiento_de_presencia():
    """Misma densidad; con movimiento la masa activa es mayor que sin él."""
    # sin movimiento: bloque quieto
    agg_static = DensityCrowdAggregator()
    out_s = None
    for i in range(60):
        out_s = agg_static.update(_map(blob=(5, 10, 4.0)), _frame(100),
                                  int(i / FPS * 1e6))
    # con movimiento: bloque que se desplaza + densidad en esa zona
    agg_move = DensityCrowdAggregator()
    out_m = None
    for i in range(60):
        out_m = agg_move.update(_map(blob=(5, 10, 4.0)), _frame(100 + i * 4),
                                int(i / FPS * 1e6))
    assert out_m["mass_active"] > out_s["mass_active"], \
        "la masa activa no distingue movimiento de presencia"


def test_centroide_sigue_la_densidad():
    """El centroide es el primer momento del campo."""
    agg = DensityCrowdAggregator()
    out = agg.update(_map(blob=(2, 2, 5.0)), _frame(), 0)      # arriba-izquierda
    assert out["centroid_y"] < 0.4 and out["centroid_x"] < 0.6
    out = agg.update(_map(blob=(12, 22, 5.0)), _frame(), 33_000)  # abajo-derecha
    assert out["centroid_y"] > 0.6


def test_escena_vacia_es_estable():
    agg = DensityCrowdAggregator()
    for i in range(40):
        out = agg.update(_map(), _frame(), int(i / FPS * 1e6))
    assert out["mass_present"] == 0.0 and out["density_count_raw"] == 0.0


def test_reset_borra_historia_y_movimiento():
    agg = DensityCrowdAggregator()
    for i in range(40):
        agg.update(_map(blob=(7, 12, 3.0)), _frame(i * 3), int(i / FPS * 1e6))
    agg.reset()
    out = agg.update(_map(blob=(7, 12, 3.0)), _frame(), int(50 / FPS * 1e6))
    assert out["mass_present"] == 0.0        # provisional otra vez


# ---------------------------------------------------------------- backend ONNX
def _backend():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "outputs/density/zip_qnrf_n.onnx"
    if not p.exists():
        pytest.skip("ONNX de densidad no exportado (scripts/export_density.py)")
    from harmocap.density import DensityBackend
    return DensityBackend(p, providers=["CPUExecutionProvider"])


def test_backend_produce_mapa_no_negativo():
    be = _backend()
    fr = (np.random.rand(360, 640, 3) * 255).astype(np.uint8)
    dm = be.infer(fr)
    assert dm.ndim == 2 and dm.min() >= -1e-3
    assert dm.shape[0] >= 8 and dm.shape[1] >= 8


def test_backend_cuenta_mas_donde_hay_mas():
    """Escena "llena" vs "vacía": el conteo crudo debe ser mayor en la llena.
    No verifica escala absoluta (no la tenemos), solo el orden."""
    be = _backend()
    empty = np.full((360, 640, 3), 30, np.uint8)
    full = (np.random.rand(360, 640, 3) * 255).astype(np.uint8)
    assert be.infer(full).sum() >= be.infer(empty).sum()
