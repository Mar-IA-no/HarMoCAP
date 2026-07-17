# HarMoCAP

HarMoCAP desarrolla un sistema de captura, pose estimation y tracking del movimiento corporal humano para convertir variables de movimiento en modulacion armonica en tiempo real dentro del ecosistema Harmonic Beacon.

## Que es

Un desarrollo de software experimental por capas. El primer hito valida el workflow de entrenamiento, validacion e inferencia con Ultralytics `yolo26m-pose` y el dataset `COCO8-pose`. Los siguientes hitos incorporaran tracking temporal, entrada en vivo, multiples personas y datasets externos mas grandes, sujetos a revision de calidad y licencia.

## Que no es

No es todavia un producto clinico, un sistema de interpretacion psicologica del cuerpo ni una validacion de Harmonic Information Theory. Un resultado favorable de deteccion o tracking prueba una propiedad del pipeline implementado, no una afirmacion mas amplia sobre la experiencia Beacon.

## Arquitectura inicial

1. Pose estimation: keypoints corporales y confianza.
2. Tracking: identidad temporal, suavizado y oclusiones.
3. Movimiento: variables derivadas, normalizacion y estado.
4. Modulacion: mapeo reproducible hacia parametros armonicos de Harmonic Beacon.

## Estructura del repositorio

| Archivo / carpeta | Funcion |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Bootstrap operativo para agentes |
| `BITACORA.md` | Log cronologico canonico |
| `PENDIENTES.md` | Pendientes del usuario |
| `NOTAS_<A>-<B>.md` | Canales escritos entre Claude y Codex |
| `Biblioteca/` | Investigaciones y fuentes archivadas |
| `src/harmocap/` | Pipeline: captura, percepcion (YOLO26-pose), identidad, suavizado, features, interfaz OSC |
| `schemas/` | Contrato canonico: `osc_contract.v1.json` (manifiesto) + JSON Schema de grabaciones |
| `harmocap-nico-kit/` | **Kit portable para Nico** (generado, no editar a mano): replay + receptor + spec, stdlib pura |
| `docs/` | `INTERFACE_SPEC.md` (contrato explicado), `FEATURES.md` (formulas), `DATASET_ROADMAP.md` |
| `scripts/` | validate_workflow, export_model, run_realtime, record_session, build_nico_kit |
| `configs/` | model / smoothing / identity / features / osc (YAML) |
| `examples/` | sesion sintetica de ejemplo + fixtures deterministas del contrato |
| `reports/<run_id>/` | evidencia versionada por corrida (env, build del engine, metricas GO/NO-GO) |
| `tests/` | 36 tests: suavizado, identidad, features, contrato OSC, aislamiento del kit |

### Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # GPU: torch cu126
.venv/bin/python -m pytest tests/            # suite completa
.venv/bin/python scripts/run_realtime.py --source 0          # camara en vivo → OSC
.venv/bin/python scripts/build_nico_kit.py   # regenerar el kit para Nico
```

Para Nico: la carpeta `harmocap-nico-kit/` es autocontenida — ver su `README.md`.

## Repositorios remotos

El repositorio de trabajo principal es `Mar-IA-no/HarMoCAP`. El espejo publico de `AlterMundi` es `AlterMundi/HarMoCAP`. La configuracion local hace que un `git push` normal publique en ambos destinos mediante multiples `pushurl` en `origin`.

## Fuentes iniciales

- Ultralytics pose training: https://docs.ultralytics.com/tasks/pose#train
- Harmonic Information Theory, capitulo 12: `/mnt/m2-1TB/editorial-altermundi/harmonic-information-theory/Hamonic_Information_Theory_Foundations_ES.md`
- Marco Beacon-HIT: `/mnt/m2-1TB/editorial-altermundi/beacon-pmp-wellness-product/documentos/05_marco_conceptual_beacon_hit/MARCO_CONCEPTUAL_BEACON_HIT.md`

## Roles activos

Claude y Codex pueden implementar o auditar segun la asignacion casuistica del usuario.

## Catalogo editorial padre

`/mnt/m2-1TB/editorial-altermundi/AGENTS.md`

## Licencia

MIT (ver `LICENSE`). El pipeline de percepcion depende de `ultralytics`
(AGPL-3.0, no redistribuida): si el pipeline combinado se distribuye como
producto rigen los terminos AGPL para la combinacion — decision de producto
diferida y documentada. El kit `harmocap-nico-kit/` no depende de ultralytics
y es MIT puro.

## Contacto

TBD.
