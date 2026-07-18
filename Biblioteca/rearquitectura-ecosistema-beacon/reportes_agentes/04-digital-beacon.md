# Informe: proyecto `digital-beacon` (`~/Projects/digital-beacon`)

> Reporte crudo de agente Explore, 2026-07-18.

Veredicto rápido: el repo es un experimento que superpone TRES capas entrelazadas por OSC y por módulos "pegamento": (1) un **synth aditivo digital** (el "Shaper", fork directo de NaturalHarmony) en Python/sounddevice; (2) un **spatializer binaural tipo beacon** en SuperCollider (`beacon.scd`); y (3) una capa de **filtro armónico + muestras de naturaleza** que analiza un WAV y modula tanto el beacon como el synth. Encima hay un refactor paralelo (`packages/`, la "nh-toolkit v2") que la propia documentación declara "apartado", y restos one-off de un pipeline de normalización de voz.

## 1. Estructura

**`digital_beacon/` (paquete Python "Shaper" + orquestación)** — 4434 líneas, corazón vivo del repo:
- `audio_engine.py` (232) — **motor de síntesis aditiva** (sounddevice/PortAudio). ESTE es el synth digital.
- `state.py` (380) — `VoiceParameterStore` thread-safe.
- `main.py` (158) — entrypoint: store + AudioEngine + OSC + MIDI + dashboard web.
- `api.py` (572) — **dashboard web FastAPI** en `:8080` con WebSocket `/ws` y ~40 endpoints `/api/*`.
- `osc_receiver.py` (165) — OSC del synth (`:9001` broadcasts NH, `:9002` `/digital/*`).
- `midi_control.py` (404) — Launchpad Mini (primario) + Minilab3.
- `config.py` (103) — constantes (f1=40.4 Hz, 32 bandas, polifonía 32, puertos).
- `recorder.py` (461) + `compressor.py` (323) — grabación y masterización "review-copy" (compresor + makeup + true-peak limiter). Independiente del synth.
- `resonant_filter.py` (105), `sample_layer.py` (380), `sample_modulator.py` (339), `sample_manager.py` (179), `sample_player.py` (52) — **capa de filtros + muestras de naturaleza** (§2).
- `stage1_format_integrity.py` (578) — validación de integridad de formato (duplicado en `tools/`).

**`packages/`** — refactor **nh-toolkit v2** ("HarmonicScene multi-source"): 8 paquetes (`nh-core`, `nh-presets`, `nh-model`, `nh-control`, `nh-analysis`, `nh-sensors`, `nh-renderers`, `nh-runtime`) + `nh-ui`. Reescritura paralela que NO usa `digital_beacon/`. `resonant_filter.py` importa `nh_analysis.mask` (punto de acoplamiento). `docs/analysis-inventory.md` dice que la UI v2 "está siendo apartada".

**`f1_bridge.py`** (111) — puente OSC: `/beacon/f1` en `:9001` → `/beacon/vsource` (varispeed) + `/beacon/f1` a sclang `:57120`. Hoy casi no-op (f1 fijo).

**`beacon.scd`** (378) — **spatializer binaural SC**: 31 BPF + 1 HPF (uno por armónico N=1..32 de f1), FoaPanB → FoaDecode(Listen HRTF) → estéreo. Fuente PlayBuf o SoundIn. ~165 OSCdefs en `:57120`. Incluye SynthDef `\sample_player` para mezclar una muestra por encima (líneas 187-192, 311-337). ESTE es el "procesamiento tipo beacon-spatial".

**`start.sh`** (9.5 KB) — launcher: `pw-jack scsynth` → `sclang beacon.scd` → `f1_bridge.py` → `digital_beacon.main`. Flags `--file/--live/--no-shaper/--no-bridge`.

**`static/index.html`** (44 KB) — UI web del dashboard legacy.

**`tools/`** — ~30 scripts: `normalize_sources*.py`, `voice_to_shaper.py`, `harmonic_explorer_components.py`, `analyze_field_recordings.py`, `voice_shaper_server.py`, `midi_sniffer.py`, `synth_pure.py` (síntesis aditiva voz→WAV en numpy puro, bypassa el Shaper por bugs de clipping), etc.

**`docs/`** — `MIGRATION.md`, `analysis-inventory.md` (muy útil), planes de UI, protocolos OSC/WS.

**`ROADMAP.md`** (26 KB) — es en realidad el roadmap de **NaturalHarmony** (describe la `HarmonicScene` v2), no específico de digital-beacon.

**`SOURCE_OF_TRUTH.md`** — decisiones bloqueadas (f1=40 Hz, 32 bandas, Shaper = el synth, binaural ATK Listen core, solo varispeed no pitch-shift).

**`MEMORY.md`** (46 KB) — define el proyecto como "instrumento unificado que combina el spatializer de beacon-spatial con el Shaper de NaturalHarmony". Confirma la mezcla a separar.

## 2. Filtros y mezcla con muestras de naturaleza (lo más importante a rescatar)

Viven en 4 archivos de `digital_beacon/`:

**A) El filtro — `resonant_filter.py` (líneas 21-106).** `ResonantFilter` separa una señal en componente **armónica** (sobre la lattice f1·N) y **residual**, con ancho de banda **adaptativo** según flatness/inharmonicity/stability. Devuelve descriptores de armonicidad. Acoplamiento **muy bajo**: solo `numpy` y `nh_analysis.mask.harmonic_mask`. Lo más limpio y portable del repo. Rescate directo.

**B) El análisis de la muestra — `sample_layer.py` (líneas 98-381).** `SampleLayer` carga un WAV (librosa), lo reproduce en loop, separa armónico/residual una vez al cargar vía `ResonantFilter`, y analiza por chunks de 50 ms produciendo `SampleDescriptor` (rms, f0, centroid, flatness, inharmonicity, harmonicity, energía por banda octava, proyección armónica sobre f1·N…). Docstring: *"intentionally simple and self-contained. It does NOT depend on the nh-toolkit refactor; librosa + numpy + python-osc"*. Rescate directo.

**C) La MEZCLA — dos caminos:**
1. **Audio de la muestra dentro del beacon** — `sample_player.py` (52) envía OSC `/beacon/sample/load|gain|stop` a `beacon.scd`, donde el SynthDef `\sample_player` reproduce la muestra y la **suma a la salida del spatializer**. La mezcla real ocurre en SuperCollider.
2. **Modulación por DESCRIPTORES** — `sample_modulator.py` (líneas 149-339). `SampleModulator` mapea descriptores→parámetros con presets declarativos (`tune-to-sample`, `spectrum-projection`, `timbre-filter`, `consonance-gate`, `harmonic-projection`…). **El verdadero pegamento a desenredar**: cada `ModulationTarget` apunta a `"beacon"` (OSC `/beacon/*` → spatializer) O a `"shaper"` (→ `VoiceParameterStore` del synth). Bicéfalo (líneas 218-250).

**D) Orquestador — `sample_manager.py` (líneas 24-180).** Envuelve Layer+Modulator+Player, presets de mapping en `~/Music/digital-beacon-mapping-presets/`, `reset_audio()` por OSC.

Resumen de acoplamiento: `resonant_filter.py` + `sample_layer.py` casi standalone. `sample_player.py`+`beacon.scd \sample_player` = mezcla real de audio (→ beacon-spatial). `sample_modulator.py` partido entre beacon y synth: hay que dividirlo.

## 3. El synth digital (fork de NaturalHarmony)

Es el **"Shaper"**: `audio_engine.py` + `state.py`, ambos declaran el linaje en el docstring ("Adapted from NaturalHarmony/harmonic_shaper/..."). **Fork, no copia.** Diferencias vs NaturalHarmony:
- Polifonía 5 → **32 voces** (`MAX_VOICES`).
- Identidad de voz = `harmonic_n` (1..32); f1 como atributo de primera clase del store.
- **Waveshaper** añadido (`shape`→`tanh` drive) para timbre didgeridoo/vocal.
- **LFO por voz** (gain/pan/phase).
- **Sidechain** beacon→shaper.
- **Recording tap** del mix final.
- Normalización por `1/sqrt(N activas)` incluyendo colas de release.

Además `tools/synth_pure.py` reimplementa el algoritmo en numpy para render offline.

## 4. El análisis de audio (`normalized_analysis/`, `originals/`, `data/`)

- **`originals/`** — 37 symlinks a `~/Music/voice-analysis/sources/PMP/wav/...` — grabaciones de **VOZ** (sesiones "PMP", "+HB"/"sin HB"). NO naturaleza.
- **`normalized_analysis/`** — 37 symlinks **ROTOS** (el directorio `runs/` fue borrado). Output one-off de una corrida de normalización de voz.
- **`data/sources/`** — copias de esos WAV de voz. **`data/migrated_presets/`** — output one-off de `scripts/migrate_presets.py` (presets `digital_beacon__*` y `beacon_spatial__*`). **`data/uploads/`** — aquí SÍ están las **muestras de naturaleza**: `dominicalito_frogs_pond.wav` (62 MB) + espectrogramas, subidas por la UI (`/api/sample/upload`) y procesadas por `SampleLayer`.

Conclusión: `normalized_analysis`/`originals` es un pipeline de normalización de VOZ cuyo **código** sí es reutilizable (`tools/normalize_sources_streaming.py` — two-pass streaming LUFS, `tools/verify_normalization.py`, `packages/nh-analysis/`) pero cuyos directorios de resultados son one-off con symlinks muertos. La rama de naturaleza es independiente: `data/uploads/` + `SampleLayer`/`ResonantFilter`.

## 5. Entradas de control y motor de audio

**Entradas (las tres a la vez):** OSC (`:9001` broadcasts NH, `:9002` `/digital/*`, `:57120` ~165 OSCdefs del beacon, `f1_bridge.py` relé 9001→57120); MIDI (Launchpad Mini primario, Minilab3 auxiliar); Web UI (`:8080`, WebSocket `/ws`, `/api/sample/*`).

**Motor doble:** SuperCollider scsynth (`beacon.scd`, `:57110`) + Python sounddevice (`audio_engine.py`). Ambos al mismo sink vía PipeWire. Auriculares requeridos (HRTF).

## 6. Veredicto — mapa de migración

**→ Proyecto SYNTH:** `audio_engine.py`, `state.py`, `config.py` (secciones Shaper/LFO/sidechain), `midi_control.py`, `osc_receiver.py` (rama `/digital/*`), endpoints `/api/shaper/*` de `api.py`, `tools/synth_pure.py`. **Ojo**: es un fork de NaturalHarmony/harmonic_shaper — decidir si esta versión de 32 voces + waveshaper + LFO + sidechain es la evolución canónica.

**→ BEACON-SPATIAL (filtros + naturaleza):** `resonant_filter.py`, `sample_layer.py`, `sample_player.py` + SynthDef `\sample_player` de `beacon.scd`, muestras en `data/uploads/`, `beacon.scd` completo (referencia del spatializer 32-banda) y `f1_bridge.py`, la mitad "beacon" de `sample_modulator.py` (presets `spectrum-projection`, `harmonic-projection`, `consonance-gate`, `timbre-filter`).

**Pieza a PARTIR:** `sample_modulator.py` y `sample_manager.py` son bicéfalos (target `"beacon"` vs `"shaper"`). Cortar: los `ModulationTarget` beacon → beacon-spatial; los shaper → proyecto synth. Es el punto exacto de la mezcla.

**ARCHIVAR / descartar:**
- `packages/` (nh-toolkit v2) — refactor "apartado"; preservar `packages/nh-analysis/` como librería de análisis reutilizable.
- `normalized_analysis/` y `originals/` — symlinks muertos, resultados one-off. Conservar el código del pipeline, no los resultados.
- `data/migrated_presets/`, `data/sources/` — one-off.
- `venv/` y `.venv/` duplicados.
- **`: RTK && `** — **basura confirmada**: directorio con ese nombre literal que contiene solo subdirectorios vacíos (`home/nicolas/Projects/digital-beacon/packages/nh-ui/web/src`, 0 archivos), creado por un `mkdir -p` con prefijo de comando mal pegado. Borrable sin pérdida.

**Nota de coherencia**: `ROADMAP.md` y buena parte de `docs/` describen la arquitectura de NaturalHarmony v2, no la de digital-beacon; pertenecen conceptualmente al esfuerzo `packages/` que se archiva.
