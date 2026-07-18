# Informe de arquitectura: HarMoCAP como referencia de patrones replicables

> Reporte crudo de agente Explore, 2026-07-18.

## Resumen ejecutivo

HarMoCAP es un pipeline de pose estimation (YOLO-pose) que emite variables de movimiento por OSC/UDP hacia un modulador de audio ("Nico"). Su mantenibilidad no viene del tamaño del código sino de tres decisiones estructurales: **(1)** un contrato de wire con una única fuente de verdad machine-readable e identificable por hash; **(2)** una separación estricta en capas donde el codec del contrato vive aislado de las dependencias pesadas; **(3)** un artefacto portable generado (no editado) desde las fuentes canónicas y verificado por tests de aislamiento y sincronía. Todo hallazgo o decisión de diseño está trazado con marcadores tipo `r4 #6`, `addendum #2`, que vinculan cada línea de código a su revisión de origen.

## 1. Estructura de capas (percepción / temporalidad / representación / modulación)

Las cuatro capas del README se materializan uno-a-uno en módulos de `src/harmocap/`, cada uno con un docstring que declara su responsabilidad y sus fronteras:

| Capa | Módulo | Frontera / responsabilidad declarada |
|---|---|---|
| Captura (I/O, latencia) | `src/harmocap/capture.py` | `LatchingCamera`: hilo lector que retiene solo el último frame; reloj monótono `mono_us()`. Aísla la latencia dominante. |
| Percepción | `src/harmocap/perception.py` | `PoseBackend`: único punto que toca `ultralytics`/YOLO. Convierte a coordenadas isotrópicas y entrega `Detection` (dataclass neutra). |
| Identidad / temporalidad | `src/harmocap/identity.py` | `SlotManager`: slots estables 0-7, histéresis de foco, tombstones. |
| Temporalidad (suavizado) | `src/harmocap/smoothing.py` | `KeypointSmoother` / One-Euro causal + máquina de estados observed→held→invalid. |
| Representación | `src/harmocap/features.py` | `FeatureExtractor` + `CalibrationManager`: keypoints → 21 features normalizadas, todo causal/time-aware. |
| Modulación / interfaz | `src/harmocap/interface/` | Frontera de salida: `osc_codec.py`, `osc_emitter.py`, `recorder.py`, `replay.py`. |
| Orquestación | `src/harmocap/pipeline.py` | `HarmocapPipeline.step()`: encadena las capas sin que ninguna conozca a la siguiente. |

Fronteras clave observadas en el código:
- **La percepción es el único módulo que importa `ultralytics`**. El resto del pipeline habla en dataclasses propias (`Detection`, `PersonState`, `MovementFrame`).
- **El contrato de datos interno vive separado del de wire**: `src/harmocap/schema.py` define dataclasses inmutables y los órdenes canónicos (`KEYPOINT_ORDER`, `FEATURE_ORDER`, `CALIBRATION_PARAM_ORDER`), mientras que el wire lo maneja `osc_codec.py`.
- **Separación telemetría/dato**: `MovementFrame` es `frozen=True` y NO contiene `sent_at`; la telemetría de envío vive en `TransportEnvelope` (`r5 #2`). El frame queda como valor puro serializable.
- **Fan-out no bloqueante**: en `pipeline.py` (`step()`), la rama de tiempo real (OSC) y la rama de grabación (`Recorder`, cola drop-oldest en su propio hilo) están desacopladas para que el disco no bloquee la emisión (`r2 #3`).

## 2. El contrato OSC como única fuente de verdad

**El manifiesto canónico**: `schemas/osc_contract.v1.json` es la fuente de verdad machine-readable. El documento humano `docs/INTERFACE_SPEC.md` lo *explica* pero cede autoridad explícitamente: "*Si algo difiere, manda el JSON*". El manifiesto contiene: transporte, sistema de coordenadas, definición de hashes, reglas del receptor, orden de keypoints, enum de estados, layouts de blobs, orden de las 21 features y todos los `addresses` con sus typetags.

**contract_id (identidad por hash)**: definido en `src/harmocap/interface/osc_codec.py`, funciones `canonical_json_hash()` y `contract_id_from_manifest()`. Es un SHA-256 truncado a 128 bits sobre el JSON canónico del manifiesto (claves ordenadas, sin espacios, sin NaN/Inf), **excluyendo** las claves auto-referenciales `contract_id`/`golden_hash`/`expected_contract_id`. El valor esperado se guarda en un **sidecar golden**: `schemas/contract_id.golden`, no dentro del manifiesto (`r8 #7`).

**Codec canónico único**: `osc_codec.py` declara ser "*el ÚNICO encoder/decoder del contrato*" y prohíbe importar nada fuera de la stdlib. Implementa las primitivas OSC 1.0 y los layouts binarios big-endian normativos (`pack_keypoints` 204 B, `pack_kp_state` 221 B, `pack_features` 84 B, `pack_feat_state` 21 B, `pack_calibration_params` 24 B). Rechaza `bool` y `NaN` en el wire con excepciones explícitas.

**Handshake /hello + /calibration + gating**:
- `build_hello()` empaqueta identidad de stream y de contrato + estado de calibración; se rebroadcastea ~1 Hz + on-change desde `OscEmitter._broadcast_handshake()`.
- Los **parámetros** de calibración viven exclusivamente en `/calibration` (`build_calibration`, `r7 #1`), separados de la identidad en `/hello`.
- La regla de **gating** está codificada como norma en el manifiesto (`receiver_rules.gating`): el receptor no consume frames hasta tener `/hello` **y** `/calibration` con tupla `(contract_id, calibration_generation, calibration_hash)` coincidente.

**Bundles atómicos**: `encode_bundle()` usa timetag "immediately". En el contrato 1.1, `build_person_bundle()` emite **un bundle atómico y autocontenido por persona** (`/meta` + datos de una persona), con una **aserción ejecutable de MTU**: `if len(bundle) > MAX_DATAGRAM_BYTES (1200): raise` (`r8 #8`). La atomicidad es por-persona para escalar a 8 slots sin exceder el MTU.

**Versionado 1.0→1.1**: el cambio (de bundle-por-frame a bundle-por-persona + `focused` + `/control/select`) **cambia el contract_id a propósito**, de modo que un kit 1.0 "gatea" (ignora) un stream 1.1 en vez de malinterpretarlo. Las versiones son múltiples y ortogonales: `contract_version 1.1`, `schema_version 1.1.0`, `feature_set_version 1.0.0`, `layout_version 1` (constantes espejadas en `schema.py`). Añadir features al wire requiere bump explícito de `FEATURE_SET_VERSION`.

## 3. El kit portable `harmocap-nico-kit`

**Qué es**: artefacto autocontenido para que el consumidor desarrolle su mapeo movimiento→sonido **sin cámara, sin GPU y sin ultralytics**, reproduciendo sesiones grabadas por OSC exactamente como el pipeline en vivo (README del kit: `scripts/kit_src/README.md`).

**Cómo se genera** (nunca se edita a mano): `scripts/build_nico_kit.py`:
- Borra y regenera el kit desde una lista explícita `COPIES` de (origen canónico → destino) — codec, replay, schema, manifiesto, docs, ejemplos, fixtures.
- **Regenera el golden sidecar** desde el manifiesto antes de copiar, garantizando que el hash publicado siempre corresponde al manifiesto vigente.
- Escribe `LICENSE` (MIT puro) + `THIRD_PARTY_NOTICES` que declaran que el kit **no depende de ultralytics (AGPL)**.
- Escribe `VERSION` con un **checksum SHA-256 del contenido completo** + commit git (`r4 #10`).

**Selftest**: `scripts/kit_src/selftest.py` (copiado al kit). Solo stdlib. Verifica extremo a extremo en la máquina del consumidor: reproducibilidad del `contract_id` contra el golden, golden vectors de blobs, rechazo de NaN, legibilidad de la sesión de ejemplo, **round-trip por UDP real**, handshake `/hello`, y monotonía de `bundle_seq`. Imprime `TODO OK`.

**Aislamiento stdlib**: garantizado por diseño y verificado por tests. El kit corre con `python -I` (isolated) y sin el repo en `sys.path`.

## 4. Testing

Estructura en `tests/` (5 archivos, ~36 tests): `test_schema_osc.py` (contrato de wire, el más denso), `test_kit_isolation.py`, `test_features.py`, `test_identity.py`, `test_smoothing.py`.

Lo que se testea del contrato (`tests/test_schema_osc.py`):
- **Golden vectors del wire**: bytes exactos del primer registro de cada blob, tamaños exactos (204/221/84 B).
- **Round-trips**: `MovementFrame ↔ OSC bundle ↔ decode` con tolerancia float32; `MovementFrame ↔ jsonl` validado contra el JSON Schema.
- **Invarianzas de tamaño (MTU)**: peor caso (slot 7, `n_persons=8`, contadores de 2^40) para todos los slots.
- **Reglas del contrato como tests**: forma del tombstone, rechazo de NaN, `contract_id` excluye auto-referencia y coincide con el sidecar golden, `calibration_hash` cambia al cambiar params.
- **Interop real**: `test_python_osc_can_parse_our_bundle` decodifica los bundles con la librería `python-osc` del lado del consumidor.

Aislamiento del kit (`tests/test_kit_isolation.py`):
- `test_kit_isolation`: copia solo el kit a un tmp, corre `selftest.py` con el **Python del sistema** (`/usr/bin/python3 -I`), sin el repo ni el venv, y exige `returncode 0` + `TODO OK`.
- `test_kit_never_imports_heavy_deps`: sonda que verifica que ningún módulo del kit trae `numpy/scipy/cv2/ultralytics/harmocap/torch/pythonosc` a `sys.modules`.
- `test_kit_in_sync`: **byte-identidad** (SHA-256) entre cada archivo del kit y su fuente canónica.
- `test_kit_has_license_and_version`.

## 5. Documentación y trazabilidad

- **docs/** como fuentes canónicas por dominio: `INTERFACE_SPEC.md` (contrato explicado), `FEATURES.md` (fórmulas — declarada fuente canónica desde el docstring de `features.py`), `DATASET_ROADMAP.md`.
- **reports/<run_id>/**: evidencia versionada por corrida. `reports/20260717_e71e14a/` contiene `env.txt` (commit, versiones pineadas, GPU), `engine_build.json` y `realtime_metrics.json` (métricas GO/NO-GO). Un puntero `reports/CURRENT_RUN` marca la corrida vigente. Cada afirmación de rendimiento es un artefacto reproducible atado a un commit.
- **BITACORA.md**: log cronológico canónico por sesiones (`S0`, `S1`, …) con commits y decisiones.
- **Trazabilidad línea-a-decisión**: marcadores `r<N> #<M>`, `addendum #<N>`, `finding #<N>` en docstrings y comentarios. Cada decisión no obvia apunta a su revisión de origen.
- **configs YAML** en `configs/` (`model`, `smoothing`, `identity`, `features`, `osc`): toda la parametrización operativa fuera del código. `HarmocapPipeline.__init__` las carga y calcula un `config_hash` canónico que viaja en `/hello` — el receptor puede detectar cambios de configuración del productor.
- **Fixtures deterministas**: `examples/fixtures/` (`lifecycle`, `calibration`, `stream_restart`, `two_persons`) ejercitan caminos borde del receptor sin cámara; la sesión de ejemplo es **sintética** (generada por `scripts/make_synthetic_session.py` a través del pipeline real) por privacidad.

## 6. Herramientas

- **`pyproject.toml`**: layout `src/`, deps pineadas con extra `[dev]`, `requires-python >=3.11`, `testpaths=["tests"]`, MIT.
- **`requirements.lock`**: lockfile completo separado del pin de alto nivel.
- **`scripts/`** como entry points de tarea, cada uno con docstring de propósito y marcador de hito (`M1`…`M4`).
- **`scripts/kit_src/`**: fuentes *exclusivas del kit* — mantiene la frontera "código del pipeline" vs "código entregable al consumidor".

## Patrones replicables (los 7 más valiosos para el ecosistema de audio/modulación)

1. **Contrato con única fuente de verdad machine-readable + doc que cede autoridad.** Un `*.contract.json` canónico gobierna; el `.md` humano lo explica y declara "si difiere, manda el JSON". Evita la deriva doc-vs-código.
2. **Identidad por hash del contrato (contract_id) + golden sidecar.** Productor y consumidor negocian compatibilidad con un solo string; un bump de contrato **gatea** deliberadamente clientes viejos.
3. **Codec canónico único aislado en stdlib pura.** Un solo archivo es el encoder/decoder del wire, sin dependencias pesadas, con layouts binarios normativos y aserciones ejecutables (MTU, prohibición de NaN/bool). El mismo archivo corre en producción y en el kit.
4. **Artefacto portable generado (no editado) + verificado por byte-identidad y aislamiento.** Elimina la clase entera de bugs "el ejemplo del cliente quedó desactualizado".
5. **Golden vectors del wire + round-trips + invarianzas de tamaño como suite de tests.** Se testea el *byte exacto*, no solo el comportamiento, incluida interop con la librería del consumidor.
6. **Handshake con gating y reglas de receptor normadas en el contrato.** `/hello` (identidad) + `/calibration` (parámetros) separados, rebroadcast periódico + on-change, y reglas de consumo escritas como norma. El consumidor sabe exactamente qué implementar.
7. **Trazabilidad decisión-a-línea + evidencia versionada por corrida.** Marcadores de revisión + `reports/<run_id>/` con métricas GO/NO-GO atadas a un commit + `BITACORA.md`.

Bonus transversal: **separación dato inmutable / telemetría** y **parametrización externa con `config_hash` en el handshake**. Ambos baratos de replicar.
