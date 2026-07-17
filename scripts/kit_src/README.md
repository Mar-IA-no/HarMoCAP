# harmocap-nico-kit — datos de movimiento corporal para tu mapeo a sonido

Kit **autocontenido** para desarrollar el mapeo movimiento→sonido de Harmonic
Beacon **sin cámara, sin GPU y sin ultralytics**: reproduce sesiones grabadas
de HarMoCAP emitiendo OSC exactamente como el pipeline en vivo.

Pensado para que lo corras vos o se lo des tal cual a tu agente de IA:
`INTERFACE_SPEC.md` + `osc_contract.v1.json` documentan el contrato completo.

## Requisitos

- Python ≥ 3.10 (Linux/Windows/macOS).
- Nada más: el kit corre con **biblioteca estándar pura**. `requirements.txt`
  instala `python-osc` (opcional) por si preferís usarlo en TU receptor.

## Arranque en una máquina limpia

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt   # opcional (el kit no lo necesita)
python selftest.py            # verifica el kit entero en tu máquina
```

## Uso

Terminal A — receptor de referencia (imprime las variables decodificadas):
```bash
python osc_receiver_example.py --port 9000
```

Terminal B — reproductor de la sesión de ejemplo (timing original, en loop):
```bash
python replay.py examples/session_v1.jsonl --port 9000 --loop
```

Después reemplazá `on_movement()` del receptor por tu mapeo, o escribí tu
propio receptor en el entorno que uses (Pd/SuperCollider/Max reciben OSC
nativo; los blobs binarios se decodifican como documenta `INTERFACE_SPEC.md`).

## Contenido

| Archivo | Qué es |
|---|---|
| `INTERFACE_SPEC.md` | **el contrato explicado** — leer primero |
| `osc_contract.v1.json` | manifiesto canónico machine-readable |
| `contract_id.golden` | hash esperado del manifiesto (verificación) |
| `movement_frame.v1.schema.json` | JSON Schema de las grabaciones `.jsonl` |
| `osc_codec.py` | codec OSC/blobs (el MISMO archivo que usa el pipeline) |
| `replay.py` | reproduce una `.jsonl` por OSC con timing original |
| `osc_receiver_example.py` | receptor de referencia con todas las reglas |
| `selftest.py` | prueba integral del kit en tu máquina |
| `examples/session_v1.jsonl` | sesión **sintética** de ejemplo (24 s, 4 fases) |
| `examples/fixtures/*.jsonl` | casos borde: oclusión, tombstone, reinicio de stream, calibración |
| `FEATURES.md` | definición y fórmula de cada variable |
| `VERSION`, `LICENSE`, `THIRD_PARTY_NOTICES` | identidad y licencias |

La sesión de ejemplo es sintética y determinista (una figura que reposa, sube
los brazos, se inclina y se balancea) — las grabaciones de personas reales no
se distribuyen en este kit.

## Garantías

- El kit se **genera** desde el repo HarMoCAP (`build_nico_kit.py`): no se
  edita a mano; `VERSION` incluye el checksum del contenido.
- `osc_codec.py` es byte-idéntico al del pipeline: lo que decodificás acá es
  exactamente lo que el sistema en vivo emite.
- Licencia MIT (ver `LICENSE`): el kit no depende de ultralytics ni de ningún
  componente AGPL.
