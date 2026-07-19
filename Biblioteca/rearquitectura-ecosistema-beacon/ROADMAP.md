# Roadmap ejecutable: re-arquitectura del ecosistema Harmonic Beacon

> 2026-07-18. Decisiones cerradas (SINTESIS.md §5). Este documento es el plan de implementación con derivación de trabajo por agente, pensado para ejecutarse en oleadas durante una sesión intensiva ("oneshot") administrando presupuesto de tokens.

## Principios de derivación

- **Claude**: tareas de criterio arquitectónico — diseño de contratos, reconciliación del fork del shaper, núcleo del router, cortes donde hay ambigüedad. Lo que si sale mal invalida trabajo aguas abajo.
- **Codex (modelo Sol, thinking al máximo)**: las tareas complejas que se derivan — fix de merge delicado, integración SuperCollider/DSP, UI grande sobre boceto, diagnósticos sutiles (clipping).
- **Grok (grok-4.5, max effort)**: tareas medianas **bien especificadas** — migraciones con destino conocido, manifiestos a partir de plantilla, drivers con spec clara, verificaciones por checklist. Cada tarea se deriva con un brief autocontenido.
- **kimi (kimi-k2.6)**: mecánica/genérica pura — scaffolding de repos, borrado de basura, mudanza de documentos, ARCHIVE.md por checklist ya escrito.
- Hermes queda disponible como reserva (deepseek-v4-flash vía ia-bridge) pero fuera del reparto por defecto. Asignación de modelos fijada por el usuario el 2026-07-18.
- **Regla de oro anti-gasto**: los briefs de derivación citan los reportes de `reportes_agentes/` como spec (rutas y líneas ya relevadas). **Ningún agente derivado re-explora los repos**; si el brief no alcanza, la falla es del brief.
- Verificación cruzada: lo que implementa Codex lo audita Claude (o viceversa), según el protocolo de roles de AGENTS.md. La BITACORA la actualiza el rol auditor.

## Mecánica de derivación (verificada en esta máquina, 2026-07-18)

- **Canal principal**: `ia-bridge-mcp` (`~/Projects/ia-bridge-mcp`) — script `marketplace/plugins/peer-opinion/scripts/build.sh`: `build.sh --task "<brief>" --agent codex|hermes|grok [--with-review] [--timeout-seconds N] [--model ...]`. Corre autónomo (always-approve), detecta contexto git del repo desde el que se invoca, loguea en `~/.bridge-ai/builds/`. Config de agentes en `~/.bridge-ai/config.json` — todos habilitados: codex, grok, kimi, hermes, gemini, claude. Defaults actualizados y **verificados con pings reales** el 2026-07-18 (backup `config.json.bak-20260718`; codex CLI actualizado 0.142.3 → 0.144.5, requerido por GPT-5.6): Codex → `gpt-5.6-terra` con `model_reasoning_effort=medium`; Grok → `grok-4.5`; kimi → `kimi-code/k3` (args del adapter corregidos: el CLI actual no acepta `--quiet` ni `-y` junto a `-p`, y no pasaba `-m`). Para las tareas marcadas "Codex Sol" se despacha con override `--model gpt-5.6-sol` + effort máximo (`model_reasoning_effort=xhigh` verificado); Grok siempre con `--effort max`. Caveat kimi: el modo prompt no admite auto-aprobación explícita — validar en T0.2 que pueda editar archivos; si no, sus tareas pasan a Grok.
- **Fallback directo**: `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh -C <repo> --output-last-message <file> -` con brief por stdin; `grok --single "<prompt>" -m grok-4.5 --always-approve`; `kimi -m kimi-code/k3 -p "<prompt>"`. En background para paralelizar oleadas.
- **Auditoría cruzada**: `/second-opinion` y `/forum` de ia-bridge (revisión ciega entre agentes) para los puntos de verificación del protocolo.
- **Flujo por tarea**: brief en `briefs/TX.Y-<agente>.md` (cita reportes como spec) → despacho en background desde el repo destino → auditoría de `git diff` + log del build → commit/merge solo tras auditoría.
- **Precauciones**: subir `--timeout-seconds` (default 600 s, corto para tareas M/L); smoke test del circuito antes de la oleada 1 completa (T0.2 con kimi, T0.3 con Grok, ping mínimo a Codex para validar el id del modelo Sol); los agentes derivados trabajan en el working tree — nada se commitea sin auditoría del rol auditor.

## Convenciones para todos los repos nuevos

Molde HarMoCAP: layout `src/`, `pyproject.toml` + lock, MIT, `configs/` YAML, `docs/`, `tests/`, `BITACORA.md`, manifiesto `*.contract.json` + golden sidecar + codec stdlib copiado, `origin` con doble pushurl (Mar-IA-no + AlterMundi), públicos.

---

## F0 — Saneamiento (desbloquea el evento; sin re-arquitectura)

| ID | Tarea | Entregable / criterio de done | Tam. | Agente | Depende |
|----|-------|-------------------------------|------|--------|---------|
| T0.1 | Resolver el merge roto de `beacon-spatial/webui.py` (conflictos commiteados en `c8ce383`, líneas 718–780 y 1725–1753; rama `sensors` vs fix `9fbe782`). Conservar AMBAS funcionalidades: lógica de sensores y fix de ruta de grabación. | `python3 -m ast` parsea; la UI arranca y `/control` responde. | M | Codex (Sol) | — |
| T0.2 | Limpieza digital-beacon: borrar dir `: RTK && `, symlinks muertos de `normalized_analysis/`, venv duplicado. **No tocar** `data/uploads/` (muestras de naturaleza) ni `originals/`. | `git status` limpio de basura; muestras intactas. | S | kimi | — |
| T0.3 | Docs beacon-spatial: README a 13 bandas/WAV correcto, tabla OSC de MEMORY.md al esquema real (`/beacon/gain/N`, no `bandIdx` como arg), anotar en `beacon-osc.json` las direcciones sin destino. | Docs coinciden con el código (reporte 03 §2 es la spec). | S | Grok | — |
| T0.4 | Reordenar beacon-spatial: PD stack completo (`*.pd`, `bridge.py`, `generate.py`, tests PD) y `beacon_pd_replica.scd` + `run-stack.sh` a `legacy/` (dedupe con lo ya existente); `research/` → `docs/research/`; borrar `beacon_record_260616_092811_/`. | Raíz del repo = solo el stack vigente. | S | kimi | T0.1 |

## F1 — Contratos (la pieza que gobierna todo)

| ID | Tarea | Entregable | Tam. | Agente | Depende |
|----|-------|-----------|------|--------|---------|
| T1.1 | **Plantillas de contrato de AMBOS planos** derivadas de `schemas/osc_contract.v1.json` de HarMoCAP: "Source Frame v1" (canales normalizados + rangos + polarity + estado observed\|held\|invalid) e "Instrument Control v1" (capacidades), con `contract_id` por hash + golden sidecar, reglas de receptor, handshake/estado. Incluye el codec/validador stdlib copiable y un test golden de referencia. Se congela por mérito y se comparte con el equipo de Anii; las divergencias con su BCP v1 se resuelven por mejor idea, no por convergencia (INFORME_CRUZADO.md, D1: NO se adopta su modelo de voz unificado de instrumentos). | `source_frame.template.json` + `instrument_contract.template.json` + codec + doc de uso, en harmonic-weaver (o repo de specs). | M | **Claude** | — |
| T1.2 | Manifiesto OSC de beacon-spatial (formalizar los 69 OSCdefs de `beacon.scd`) + **estado bidireccional** (`/beacon/state` dump o broadcast periódico) + host/puerto por argumento/env en el `.scd` (escuchar configurable, no solo 127.0.0.1). | `beacon_spatial.contract.json` + cambios en `beacon.scd` + test de round-trip. | M | Codex Sol (brief de Claude) | T1.1, T0.4 |
| T1.3 | Manifiesto OSC del shaper (`/shaper/*` sobre el código existente de digital-beacon). | `shaper.contract.json` (viaja con T2.2). | S | Grok | T1.1 |

## F2 — harmonic-shaper (repo nuevo)

| ID | Tarea | Entregable | Tam. | Agente | Depende |
|----|-------|-----------|------|--------|---------|
| T2.1 | Scaffolding del repo `harmonic-shaper` según convenciones (incluye creación GitHub + doble pushurl). | Repo vacío estructurado, CI de pytest si aplica. | S | kimi | — |
| T2.2 | Migrar el Shaper de digital-beacon (`audio_engine.py`, `state.py`, `config.py` secciones shaper, `midi_control.py`, `osc_receiver.py` rama `/digital/*`→renombrar a `/shaper/*`, endpoints `/api/shaper/*` de `api.py`, `tools/synth_pure.py`) **reconciliando con NaturalHarmony** (diffs conocidos: 32 voces, waveshaper, LFO, sidechain, normalización 1/√N). Deps reales declaradas. | Synth corre standalone; `pip install -e .` limpio. | L | **Claude** | T2.1, T1.3 |
| T2.3 | Fuente de notas propia: portar `harmonic_beacon/harmonics.py` + `key_mapper.py` (mapeo MIDI-nota→armónico→freq); el modo esclavo del broadcast `/beacon/voice/*` queda opcional tras flag. | Tocar el synth desde un teclado MIDI sin el beacon corriendo. | M | Grok (brief de Claude) | T2.2 |
| T2.4 | Tests: golden del contrato + round-trips + smoke de audio (render N samples, sin NaN/clipping). Diagnóstico de los bugs de clipping usando `synth_pure.py` como referencia de oro. | Suite verde; clipping caracterizado (fix si es barato, issue si no). | M | Codex Sol; escala a Claude si el clipping es profundo | T2.2 |

## F3 — Naturaleza → beacon-spatial

| ID | Tarea | Entregable | Tam. | Agente | Depende |
|----|-------|-----------|------|--------|---------|
| T3.1 | Migrar `resonant_filter.py` + `sample_layer.py` a beacon-spatial, **vendorizando** `nh_analysis.mask.harmonic_mask` (única dep del refactor apartado). | Módulos corren en beacon-spatial con sus deps (numpy/librosa) declaradas. | M | Grok | T0.4 |
| T3.2 | Portar `sample_player.py` + SynthDef `\sample_player` (de `digital-beacon/beacon.scd` líneas 187-192, 311-337) al `beacon.scd` de beacon-spatial; exponer `/beacon/nature/*` (load/gain/stop) y sumarlo al manifiesto T1.2. | Muestra de naturaleza suena mezclada en el spatializer, controlada por OSC. | M | Codex (Sol) | T1.2, T3.1 |
| T3.3 | Partir `sample_modulator.py`/`sample_manager.py`: los `ModulationTarget` tipo `beacon` (presets `spectrum-projection`, `harmonic-projection`, `consonance-gate`, `timbre-filter`) → beacon-spatial; los tipo `shaper` → issue en harmonic-shaper para F5 (no bloquea MVP). **El corte lo revisa Claude.** | Modulación por descriptores funcionando contra beacon-spatial. | M | Grok + revisión Claude | T3.1 |
| T3.4 | Mover muestras de `digital-beacon/data/uploads/` a beacon-spatial (o a un dir de assets fuera de git con MANIFEST). | Muestras accesibles; git sin WAVs de 62 MB. | S | kimi | T3.2 |

## F4 — harmonic-weaver MVP (el desarrollo nuevo real)

| ID | Tarea | Entregable | Tam. | Agente | Depende |
|----|-------|-----------|------|--------|---------|
| T4.1 | **Diseño del núcleo**: modelo de datos de rutas/escenas/transformaciones, categoría de fuentes agregadas, API WebSocket del servidor headless (contrato-manifest propio), semántica de pánico. Documento corto + esquemas. | `docs/CORE_DESIGN.md` + `stage.contract.json` draft. | M | **Claude** | T1.1 |
| T4.2 | **Motor de ruteo headless**: fuentes → transformaciones (escala/curva/suavizado/gate/combinadores) → instrumentos vía sus manifiestos; escenas conmutables en caliente; pánico global; agregados sobre slots HarMoCAP. Granularidad hasta keypoint/feature por slot. Referencia primaria de implementación para API WS + state store: `digital_beacon/api.py` (rescate de patrones, no de codebase). | Servidor corre, API WS operativa, rutas ↔ OSC verificadas con fixtures. | L | **Claude** | T4.1, T2.1-scaffolding análogo |
| T4.3a | Driver HarMoCAP: receptor basado en `harmocap-nico-kit` (codec/replay ya resueltos), exponiendo slots/keypoints/features como fuentes. | Fixtures `two_persons.jsonl` visibles como fuentes en el router. | M | Grok (el kit es la spec) | T4.1 |
| T4.3b | Driver MIDI: generalizar `midi_relay.py` de cymatic-control (CC/nota → fuente normalizada 0-1). | Minilab3/Launchpad como fuentes. | S | kimi | T4.1 |
| T4.3c | Driver ECG: envolver `ECGProcessor` (Pan-Tompkins, con tests) como fuente de trigger rítmico + BPM continuo; entrada OSC `:5001` del firmware ESP32 existente. | Latidos como eventos de trigger en el router; probado con `simulate_*`. | M | Grok | T4.1 |
| T4.4 | Cliente web del patchbay: UI de matriz/patcheo sobre la API WS (diseño de interacción lo boceta Claude; criterio §6: patchear se siente performance). | Patchear, conmutar escenas y pánico desde el browser. | L | Codex Sol sobre boceto de Claude | T4.2 |
| T4.5 | **Integración e2e y ensayo**: script que levanta beacon-spatial (modo `--file`), shaper, harmonic-weaver y los simuladores (EEG/HR de cymatic-control + replay HarMoCAP); escena de demo del evento. | Ensayo completo sin hardware ni gente: audio audible modulado por fuentes simuladas. | M | **Claude** (verificación final) | T4.2-4, T1.2, T2.x, T3.2 |

## F5 — Post-evento (NO se implementa ahora; queda especificado)

Drivers EEG/HR y audio→modulación (`SampleDescriptor` como fuente genérica), sensores de celular — **pendiente del push de Anii** (IMU + variables pareadas sway/synchrony/pair_energy, "Pair Mode"; ver INFORME_CRUZADO D4): al llegar se evalúa por mérito contra la extracción del Sensor Interpreter de webui.py y gana el mejor; si está maduro puede adelantarse al MVP —, **surge-bridge** (extracción de `harmonic_beacon` + entrada OSC de control, repo propio con visualizer), mitad "shaper" de sample_modulator, cliente móvil, cliente Quest/WebXR, candidato Nature Lab generativo (decisión 4: anotado, sin compromiso).

## F6 — Archivo (mecánico, al final)

| ID | Tarea | Entregable | Tam. | Agente | Depende |
|----|-------|-----------|------|--------|---------|
| T6.1 | `ARCHIVE.md` en harmonic-beacon-tines según el checklist del reporte 05 (declaración + enlaces a los 4 docs de prioridad alta + lista de código reutilizable con rutas). | Repo congelado y autoexplicativo. | S | kimi | — |
| T6.2 | Archivo de digital-beacon: verificación de que todo lo listado en el reporte 04 §6 migró (checklist), `ARCHIVE.md`, preservando el pipeline LUFS de `tools/` y `nh-analysis` referenciados desde el archivo. | Nada útil quedó sin destino. | S | Grok (verificación) | T2.2, T3.x |
| T6.3 | Archivo de NaturalHarmony: `ARCHIVE.md` apuntando a harmonic-shaper y al futuro surge-bridge (F5); literate program preservado. | Repo congelado. | S | kimi | T2.2 |

## Oleadas de ejecución (paralelismo para la sesión)

1. **Oleada 1** (paralelo, arranca ya): T0.1 (Codex Sol) + T0.3 (Grok) + T0.2/T0.4 (kimi) ∥ T1.1 (Claude) ∥ T2.1 + T6.1 (kimi).
2. **Oleada 2**: T1.2 (Codex Sol) y T1.3 (Grok) con la plantilla ∥ T4.1 (Claude diseña mientras los derivados formalizan).
3. **Oleada 3**: T2.2 (Claude) ∥ T3.1 (Grok) ∥ T4.3a/c (Grok) + T4.3b (kimi), briefs independientes.
4. **Oleada 4**: T4.2 (Claude) ∥ T2.3, T3.3 (Grok) ∥ T2.4, T3.2 (Codex Sol).
5. **Oleada 5**: T4.4 (Codex Sol sobre boceto) ∥ T3.4 (kimi) ∥ luego T4.5 (Claude, integración).
6. **Cierre**: T6.2, T6.3; BITACORA por el rol auditor; push doble verificado en ambos remotos.

Ruta crítica: **T1.1 → T4.1 → T4.2 → T4.5** (todo Claude). Lo demás cuelga en paralelo. Si el presupuesto de tokens aprieta, se recorta primero T4.4 (UI mínima: tabla de rutas editable en vez de matriz visual) y T2.4 (clipping como issue), nunca T4.5 (sin ensayo e2e no hay evento).
