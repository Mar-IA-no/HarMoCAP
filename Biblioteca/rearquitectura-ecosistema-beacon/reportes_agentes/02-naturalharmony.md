# Informe: proyecto NaturalHarmony (`~/Projects/NaturalHarmony`)

> Reporte crudo de agente Explore, 2026-07-18.

## Resumen ejecutivo

NaturalHarmony es un ecosistema Python en torno a la **serie armónica natural**. La documentación "oficial" (`README.md`, `SPEC.md`) solo reconoce **dos** componentes (Beacon + Visualizer), pero el repo contiene **cuatro** paquetes ejecutables más herramientas. El componente clave —el **sintetizador/shaper**— es `harmonic_shaper/`: un motor DSP aditivo en Python puro, autocontenido, funcional y notablemente limpio, pero **invisibilizado** en la documentación (aparece como "(TBD)" en `MEMORY.md`). Es el candidato claro a convertirse en producto propio.

## 1. Propósito real de cada subcomponente

### `harmonic_beacon/` — motor MIDI→OSC (el "cerebro" histórico) — ~3.185 líneas
El núcleo original y más grande. Recibe MIDI (notas/CC), mapea teclas a frecuencias de la serie armónica (prototipos cromáticos, transposición por octava, modos Pad/Keyboard/Stacking/Split, modulación de f₁ por CC74, LFO chorus) y **emite OSC a Surge XT** (`/fnote`, `/fnote/rel`, `/ne/pitch`). Opcionalmente hace **broadcast OSC** de su estado (`/beacon/*`) y salida MPE. El más maduro; único con programa literario (`harmonic-beacon.lit.md`, 120 KB + PDF). Archivos clave: `main.py` (925 líneas), `osc_sender.py` (470), `mpe_sender.py` (418), `harmonics.py` (405), `key_mapper.py` (227).

### `harmonic_shaper/` — **el sintetizador elemental** — ~1.093 líneas + UI web 542
**Sintetizador aditivo por síntesis directa en Python.** Senos puros por armónico con control independiente de **gain, pan (equal-power) y fase**, para el experimento cimático (láser+globo+tubo). Piezas:
- `audio_engine.py` (150): motor de síntesis aditiva estéreo con `sounddevice`, acumuladores de fase por armónico, mezcla+clip. **Corazón del sintetizador.**
- `state.py` (184): `VoiceParameterStore` thread-safe (dict por `harmonic_n` → gain/pan/phase/freq), polifonía de 5 voces con note-stealing, panic. **La fuente de verdad del synth.**
- `osc_receiver.py` (163): doble puerto — broadcasts del beacon (`/beacon/voice/on|off|freq`, puerto 9001 con `SO_REUSEPORT`) y control directo (`/shaper/harmonic/<n>/gain|pan|phase`, puerto 9002).
- `midi_control.py` (164): Minilab3 → parámetros (sliders=gain, knobs sup=pan, knobs inf=fase, modwheel=master).
- `api.py` (160): FastAPI + WebSocket (REST `PUT /api/harmonic/{n}`, `/api/panic`, `/api/state`, sesiones de dataset) + push de estado en tiempo real.
- `logger.py` (128): `DatasetLogger`, snapshots CSV+JSON temporizados para correlacionar patrón cimático con parámetros.
- `static/index.html` (542): mixer web sincronizado por WebSocket.
- `main.py` (94): orquestador con banderas `--no-midi/--no-osc/--no-ui/--list-devices`.

### `harmonic_exciter/` — puente MIDI→ESP32 (hardware físico) — ~719 líneas
Controla los **tines** de un beacon físico vía **HTTP a un ESP32** (`beacon.local`). No produce audio: excita hardware. Fundamental fija 50 Hz, 5 tines (100–300 Hz). Reusa el patrón del shaper (store + Minilab3 + Launchpad) con `BeaconClient` HTTP en lugar de motor de audio. Trabajo **más reciente** (commits NH-14…NH-21).

### `harmonic_visualizer/` — visualizador pasivo OSC — ~1.713 líneas
Recibe `/beacon/*` y dibuja el estado. 2D en PyGame (`renderer.py`, 329) o 3D en ModernGL con bloom (`renderer_3d.py`, 983). Consumidor puro del broadcast.

### `midi_monitor.py` (110) y `midi_wizard.py` (161) — herramientas de operador
Descubrimiento de CC del Minilab3. `midi_wizard.py` **escribe `harmonic_shaper/config.py`** con el mapeo. Bootstrap, no runtime.

### `experiments/` — runner de experimentos cimáticos — ~170 líneas
`base.py` (105): clase `Experiment` + `ShaperClient` (wrapper HTTP sobre la API del shaper) para automatizar barridos con grabación de sesión. `example_phase_sweep.py` (65). **Depende exclusivamente del shaper.**

## 2. Entradas / salidas / motor de audio

| Componente | Entradas | Salidas | Motor de audio |
|---|---|---|---|
| harmonic_beacon | MIDI (teclado + Launchpad + 2º controlador), CC | **OSC a Surge XT**; broadcast OSC `/beacon/*`; MPE virtual | Ninguno propio → **Surge XT** |
| harmonic_shaper | OSC del beacon, OSC directo `/shaper/*`, MIDI Minilab3, HTTP/WebSocket | **Audio directo a placa** (estéreo), WebSocket, CSV/JSON | **Python DSP puro (`sounddevice` + `numpy`)** |
| harmonic_exciter | MIDI (Minilab3 + Launchpad) | **HTTP a ESP32** (tines físicos) | Ninguno (sonido físico) |
| harmonic_visualizer | OSC `/beacon/*` | Gráficos | N/A |

Punto clave: **dos "motores de sonido" distintos**. El beacon delega en Surge XT (OSC). El shaper es su propio motor DSP en Python. Esta divergencia es exactamente por qué el shaper puede independizarse.

## 3. Estado del código (declarado vs. real)

**Documentación declarada** (`SOURCE_OF_TRUTH.md`, `SPEC.md`, `BASELINE_STATE.md`, `REFACTOR_SUMMARY.md`, `TASKS.md`, `README.md`): datada 2026-02-11, centrada exclusivamente en beacon + visualizer. Declaran cerrado un "comprehensive cleanup" (tests reconstruidos —538 líneas, solo cubren `harmonics` y `key_mapper` del beacon—, LICENSE MIT, `pytest.ini`).

**Realidad (git):**
- Shaper y exciter se desarrollaron **después** del cleanup y nunca entraron en la doc oficial. `MEMORY.md` lista `harmonic_shaper/` como **"(TBD)"** pese a estar completo.
- Último commit del repo: 2026-07-07 (literate program). Último commit del shaper: 2026-03-20. Trabajo más reciente = exciter.
- `docs/SHAPER_PLAN.md` (186 líneas) está **completamente implementado**: las 6 cards (core engine, Minilab3, UI web, API OSC+HTTP, experiment runner, dataset logger) existen todas.

**Veredicto de madurez:** Terminado y usable: `harmonic_beacon` (maduro, tests + literate program), `harmonic_shaper` (completo, sin tests, sin docs oficiales), `harmonic_visualizer` (completo). Funcional reciente con hardware: `harmonic_exciter`. Nada abandonado, pero el shaper está "huérfano de documentación".

## 4. Acoplamientos

```
MIDI ─► harmonic_beacon ─► OSC ─► Surge XT (audio full mix)
              │
              └─ broadcast /beacon/* (puerto 9001)
                     ├─► harmonic_visualizer   (consumidor pasivo)
                     └─► harmonic_shaper        (consumidor + motor audio propio)
                                │
                                ├─ Minilab3 MIDI
                                ├─ OSC /shaper/* (9002)
                                └─ HTTP/WS (8080) ◄── experiments/
```

1. **Acoplamiento blando al beacon (el importante a separar).** El shaper obtiene frecuencias y activación de voces del broadcast `/beacon/voice/on|off|freq`. Hoy **no sabe generar notas por sí mismo** desde MIDI. Sin embargo `VoiceParameterStore` y `AudioEngine` son totalmente independientes; el shaper ya puede correr standalone vía `/shaper/*` OSC o HTTP. Para ser autónomo necesita **su propia fuente de notas** (mapeo MIDI-nota→armónico→freq, que hoy vive en el beacon: `key_mapper.py` + `harmonics.py`).
2. **Dependencias no declaradas.** `requirements.txt` no lista `sounddevice`, `fastapi`, `uvicorn[standard]`, `requests` — todas usadas por shaper/experiments.
3. **Config duplicada.** `MINILAB_PORT_PATTERN`, `MINILAB_SLIDER_CCS`, `MINILAB_PANIC_PAD`, `DEFAULT_F1=65.0` duplicados entre shaper, exciter y beacon.
4. **Patrón compartido shaper↔exciter** (Store thread-safe + Minilab3Control + panic): oportunidad de librería común de "store + control surfaces".
5. **Co-escucha de puerto 9001** vía `SO_REUSEPORT` (solo Linux) entre shaper y visualizer.

**No acoplado (buena noticia):** `audio_engine.py`, `state.py`, `logger.py`, `api.py`, `static/index.html` no importan nada del beacon ni del exciter. El límite del synth extraíble es nítido.

## 5. Veredicto

### El "sintetizador elemental" rescatable = `harmonic_shaper/` completo (~1.400 líneas Python + 542 UI)
Extraer: `audio_engine.py`, `state.py`, `config.py`, `main.py`, `logger.py`, `osc_receiver.py` (el listener `/beacon/*` a re-evaluar), `midi_control.py`, `api.py` + `static/index.html`, `experiments/`, `midi_monitor.py`, `midi_wizard.py`.

**Trabajo para independizarlo** (pequeño): (a) fuente de notas propia — portar el mínimo de `harmonic_beacon/harmonics.py` + `key_mapper.py` (o dejar el modo esclavo del beacon como opcional); (b) declarar deps reales; (c) resolver config Minilab3 duplicada.

### Se archiva / queda fuera del synth
- `harmonic_exciter/`: pertenece al hardware físico (relación con harmonic-beacon-tines); archivar o mover al repo de hardware.
- `harmonic_visualizer/`: consumidor del beacon; se queda con el ecosistema beacon.
- `harmonic_beacon/`: middleware MIDI→Surge XT; mantiene su camino. Extraer (no archivar) `harmonics.py` + `key_mapper.py` para el synth.
- Docs de estado (`BASELINE_STATE.md`, `REFACTOR_SUMMARY.md`, `SOURCE_OF_TRUTH.md`): históricos desfasados; archivar como registro.

### Riesgo declarado
`docs/SHAPER_PLAN.md` deja abiertas la **precisión de fase** (¿callback de `sounddevice` suficiente? objetivo ±5°) y el **routing de salida de audio** (misma placa que Surge XT vs. dedicada).
