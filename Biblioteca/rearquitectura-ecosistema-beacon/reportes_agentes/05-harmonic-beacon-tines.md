# Informe de archivo: `harmonic-beacon-tines` (`~/Projects/harmonic-beacon-tines`)

> Reporte crudo de agente Explore, 2026-07-18. Remoto: `github.com/AlterMundi/harmonic-beacon-tines`.

Contexto: el hardware físico (púas/tines electromagnéticas con ESP32) ya no existe. Objetivo: archivar sin perder el conocimiento.

## 1. Qué era el sistema

Un "faro armónico": instrumento físico de púas metálicas tipo kalimba excitadas electromagnéticamente, afinadas a una serie armónica natural (fundamental 50 Hz; 5 púas a 100/150/200/250/300 Hz = H2..H6). El software genera campos armónicos sostenidos y paisajes sonoros bioacústicos ("Nature Lab").

Arquitectura en capas (protocolo común: OSC/UDP broadcast, puerto 53280):

- **`beacon_core/`** — Núcleo compartido, sin hardware. `config.py` (frecuencias, esquema OSC canónico), `state.py` (`ElementStateStore`), `nature_state.py`/`nature_types.py`, `session_manager.py` (presets).
- **`beacon_daemon/`** — Daemon principal para las púas físicas. `main.py`/`cli.py`, `nature_renderer.py` (motor Nature Lab con `NatureScheduler` unificado), `osc_sender.py` (salida OSC hacia ESP32 / Surge XT, plugins de expresión: breathe, orbit, pulse, resonance, morph, gravity, chaos, drift, strike, strum), `feedback.py`, `control/` (MIDI Minilab3 + Launchpad), `ui/` (FastAPI).
- **`synth_beacon/`** — Alternativa 100% software. `audio_engine.py` es un motor de síntesis aditiva real (sounddevice/numpy), `osc_receiver.py` (mismo protocolo OSC), `midi_control.py`, `api.py`, servidor web. **No depende del hardware muerto; sigue funcional.**
- **`esp32_tines_beacon/`** — Firmware PlatformIO/Arduino (PWM LEDC + MOSFETs, web UI, config SPIFFS, OTA, receptor OSC). Atado al hardware muerto.
- **`beacon.py`** — Lanzador trivial.
- **`parts/`** — CAD paramétrico (build123d). `parts/sun/` = rueda de leva que excita las cuerdas del "Beacon Guitar" como arco de violín: `params.yaml` (fuente única de geometría), `build123d.py`, `spec.yaml`, STL/STEP. Evolución hacia excitación mecánica-rotatoria.

Relación externa (`MEMORY.md`): este repo era el "cuerpo físico"; `NaturalHarmony` el "cerebro software"; el puente era `harmonic_exciter` en NaturalHarmony.

## 2. Conocimiento a preservar

### `NATURE_LAB_V2_DESIGN.md` (1613 líneas) — el activo intelectual central

Tratado de diseño de síntesis sonora bioacústica. Tesis reutilizable:

> **"El detalle vive en la modulación por-muestra, no en la frecuencia de actualización."** Cada paquete de 50 ms (20 Hz) debe llevar suficiente estado de modulación para generar 50 ms de audio rico a nivel de muestra.

Contiene, para 6 elementos (grillo, rana, cigarra, búho, agua, viento):
- Investigación bioacústica de cada mecanismo (estridulación, saco vocal como resonador de Helmholtz, timbales, siringe, turbulencia/gotas/burbujas, tonos eólicos por vórtices).
- Modelos físicos implementables (máquinas de estado ataque/sostén/decaimiento; sigmoides; trenes de impulsos; pesado por formantes; coro con voces incommensurables).
- Micro-modulación (bancos de LFOs incommensurables, fatiga acumulada, deriva térmica, startle).
- Tablas de mapeo parámetro→efecto y apéndice de rangos 0-1.
- Patrón unificado `NatureElementV2.render_frame(params, intensity, dt)`.

Todo el código Python es hardware-agnóstico (produce "duty" 0-1 por púa); portable a cualquier motor de síntesis.

### `PERFORMANCE_ANALYSIS.md` (517 líneas) — lecciones de arquitectura en tiempo real

- **Colapso de hilos**: de 15+ hilos a 1 scheduler unificado a 50 Hz; renderers/plugins como lógica sin hilo propio.
- **Contención de locks**: un `RLock` compartido era el cuello de botella; snapshots atómicos y lecturas lock-free.
- **OSC flooding**: 1.500-2.000 msg/s → 20-50 msg/s (-98%) con rate-limiting, `batch_update()` (context manager con supresión de notificación), sync diferencial y coalescing.
- Resultados: CPU 40-60% → 2-5%; latencia de toggle 2-5 s → <50 ms.
- Anti-patrones documentados: "lock+notify en hot path", "snapshot en bucle apretado", "check-then-act" con datos rancios, "active-set thrashing".

### Otros documentos

- **`MEMORY.md`** — mapa mental y relación con NaturalHarmony; buen resumen para cabecera del archivo.
- **`.hermes/plans/2026-03-26_065740-my-friend-lets-plan-for-a-new-set.md`** — diseño de plugins de expresión con fórmulas (BREATHE envolvente colectiva LFO; RESONANCE acoplamiento simpático `ghost_vel = master_vel * coupling * (1/|harm_i - harm_j|)`; etc.).
- **`esp32_tines_beacon/README.md`** — pines GPIO, circuito MOSFET+flyback, config armónicos, OTA/UFW. Solo si se reconstruye hardware.
- **`parts/sun/notes.md` + `spec.yaml`** — decisiones DFM de la rueda de leva; evolución electromagnética → mecánica rotatoria.

**Lo aprendido (series armónicas / excitación / mapeo / latencia):**
- Series: fundamental configurable × enteros (F×1..F×5) en `beacon_core/config.py` y firmware; afinación de cada elemento natural en `nature_types.py`.
- Excitación: dos paradigmas — electromagnética (PWM/duty) y mecánica (leva). El control siempre se reduce a "duty" 0-1 por elemento.
- Mapeo sensor→sonido: mapeos MIDI concretos (Minilab3: modwheel→master duty, sliders→duty por elemento, knobs→fase, pad→panic) en `control/midi_control.py`; tablas param→comportamiento en el design doc.
- Latencia: red/OSC (evitar flooding UDP) y audio (~5 ms a 256 samples/44.1 kHz con continuidad de fase). Síntesis de ambos: "20 Hz de actualización + detalle por-muestra".

## 3. Código genérico reutilizable (no atado al hardware muerto)

1. **`synth_beacon/` completo** — motor de síntesis aditiva funcional. `audio_engine.py`: síntesis senoidal por voz con continuidad de fase (módulo para evitar drift), pan equal-power, thread-safety documentado.
2. **Lógica del Nature Lab** (modelos del design doc + `nature_renderer.py`) — generadores bioacústicos que producen valores 0-1; portables.
3. **Patrones de tiempo real** (`PERFORMANCE_ANALYSIS.md` + `beacon_core/state.py` + `osc_sender.py`): scheduler unificado, `batch_update()`, snapshots lock-free, sync diferencial, coalescing OSC.
4. **Daemons OSC**: `osc_sender.py` (cola, coalescing, rate-limiting), `synth_beacon/osc_receiver.py`. Esquema OSC limpio (`/beacon/play`, `/stop`, `/stopall`, `/phase`, `/duty`, `/master`).
5. **Mapeo MIDI**: `control/midi_control.py` (Minilab3), `launchpad_control.py`: CC→parámetro con auto-descubrimiento vía `mido`.
6. **`beacon_core/session_manager.py`**: presets con degradación elegante.
7. **CAD paramétrico**: `parts/sun/build123d.py` + `params.yaml`.

Tests (`tests/test_feedback.py`, `test_nature_state.py`, raíz `test_freq.py`, `test_nature.py`) documentan comportamiento esperado.

## 4. Checklist de extracción antes de archivar

Prioridad ALTA (conocimiento irrecuperable):
- [ ] `NATURE_LAB_V2_DESIGN.md` — íntegro.
- [ ] `PERFORMANCE_ANALYSIS.md` — íntegro.
- [ ] `MEMORY.md` — como cabecera/resumen del documento de archivo.
- [ ] `.hermes/plans/2026-03-26_065740-my-friend-lets-plan-for-a-new-set.md` — matemática de plugins de expresión.

Prioridad MEDIA (código reutilizable):
- [ ] `synth_beacon/audio_engine.py`.
- [ ] `beacon_core/config.py` (esquema OSC + modelo de armónicos).
- [ ] Patrones de `beacon_core/state.py` + `beacon_daemon/osc_sender.py`.
- [ ] Mapeos de `control/midi_control.py` y `launchpad_control.py`.
- [ ] `beacon_core/session_manager.py`.

Prioridad BAJA (referencia hardware/mecánica):
- [ ] `esp32_tines_beacon/README.md`.
- [ ] `parts/sun/` (README, notes, spec, params, build123d).

Recomendación de forma: un único `ARCHIVE.md` en la raíz que (a) declare el proyecto archivado y el hardware inexistente, (b) enlace los cuatro documentos de prioridad alta, (c) liste el código reutilizable con ruta y una línea de por qué. El repo se congela tal cual (git preserva todo).

Observación menor: `CLAUDE.md` y `agents.md` son boilerplate genérico; no aportan al archivo.
