# Informe: `cymatic-control` (GitHub `AlterMundi/cymatic-control`)

> Reporte crudo de agente general-purpose, 2026-07-18. Clonado a scratchpad de sesión (temporal). El nombre correcto lleva la 'l' final; `cymatic-contro` no existe.

Repo chico y coherente: 6 commits, último 2026-03-28, ~6.400 líneas Python + firmware Arduino. Licencia MIT.

## 1. Qué hace

**Puente de biofeedback en tiempo real**: toma señales corporales (cerebro, corazón) y de un controlador MIDI, las convierte en parámetros y las inyecta por OSC al sintetizador `harmonic_shaper` (NaturalHarmony) para modular en vivo los patrones cimáticos. Nació como migración de un proyecto previo `zuna-implemetation` (denoising EEG).

Lo "cimático" NO es una fuente de entrada: es la **salida** (patrones de interferencia del harmonic_shaper y, en una rama alternativa, una superficie física vibrante ESP32).

**Componentes** (raíz):
- `cymatic.py` (967 líneas): lanzador interactivo, wizard de 3 pasos (EEG → HR → MIDI) que orquesta los demás scripts como subprocesos, con presets ("test sin hardware", "muse-only", "sesión completa").
- `muse_bridge.py` (935): **núcleo**. EEG + latido + slider → modulación de gains/fases del shaper.
- `hr_relay.py`, `midi_relay.py`: relays de entrada → OSC.
- `osc_bridge.py`, `eeg_harmonic_bridge.py`: puentes alternativos EEG → actuador ESP32 "Beacon" (`/fnote`) / Surge XT.
- `eeg_analysis.py`, `ecg_analysis.py`: DSP reutilizable (numpy/scipy).
- `simulate_eeg.py`, `simulate_tilt.py`: mocks de EEG sin hardware.
- `test_devices.py`, `test_ecg_stream.py`: monitores de hardware standalone.
- `firmware/ecg_esp32/ecg_esp32.ino`: firmware ESP32 para sensor ECG.
- `config.json`, `docs/` (4 análisis), `tests/` (pytest).

## 2. Fuentes de entrada y protocolos

| Fuente | Hardware | Cómo entra | Protocolo | Script |
|---|---|---|---|---|
| EEG | Muse 2 | app Mind Monitor → `/muse/eeg` (TP9/AF7/AF8/TP10 @256Hz) | OSC/UDP :5000 | `muse_bridge.py`, `osc_bridge.py` |
| ECG | AD8232 + ESP32 (pecho) | ESP32 muestrea 250Hz, batches `/ecg/raw` por WiFi | OSC/UDP :5001 | `hr_relay.py --mode ecg` + firmware |
| HR | Fitbit Charge 6 / pulsómetro estándar | perfil BLE Heart Rate (UUID 0x180D) | BLE (`bleak`) | `hr_relay.py --mode ble` |
| HR | cualquier Fitbit | Fitbit Web API intraday (OAuth2) | HTTPS polling | `hr_relay.py --mode fitbit-api` |
| MIDI | Launchpad Mini (slider/CC) | un CC → `/bridge/gain_depth` | MIDI (`mido`) → OSC | `midi_relay.py` |
| Simuladas | ninguno | EEG/latido sintéticos | OSC local | `simulate_*.py` |

**Importante**: NO hay acelerómetro/motion de celular. El "tilt" del proyecto es *spectral gain tilt* (ratio alpha/beta del EEG), no inclinación física.

El firmware ESP32 es notable: OSC crudo sobre UDP a mano, config WiFi por serial persistida en flash (`Preferences`), muestreo 250Hz en batches de 8, detección lead-off.

## 3. Salida

Principal: **OSC hacia harmonic_shaper** en `127.0.0.1:9002`, más lectura del estado base por HTTP (`:8080/api/state`). Tres ejes (`--param gain|phase|both`):
- **Gain tilt** (EEG): ratio alpha/beta frontal → inclina gains de los 5 armónicos con pesos `[-0.8,-0.4,0,0.4,0.8]`. Relajado = graves, enfocado = agudos. `/shaper/harmonic/N/gain`.
- **Phase rotation** (EEG): cada sensor/banda controla la velocidad de rotación de fase de su armónico (H2←TP9/theta, H3←AF7/alpha, H4←AF8/beta, H5←TP10/gamma; H1 anclado). `/shaper/harmonic/N/phase`, interpolado a 30Hz.
- **Heartbeat pulse** (ECG/HR): cada latido dispara envolvente exponencial de gain.

Fórmula: `final_gain = base * (1 + tilt*gain_depth) * (1 + heartbeat_envelope)`, con `gain_depth` en el slider MIDI. Al salir restaura valores base.

Salidas alternativas: `osc_bridge.py` → actuador ESP32 vía `/fnote`; `eeg_harmonic_bridge.py` → Surge XT + actuador.

## 4. Estado

Sorprendentemente maduro para 6 commits — "usable/beta bien construido":
- Capas limpias (entrada → análisis → salida), config centralizada, cada entrada independiente y opcional.
- Tests reales: `tests/test_muse_bridge.py` (794 líneas) y `tests/test_ecg_analysis.py` (318), 73 tests que cubren gain tilt, phase rotation, envolvente, R-peak y handlers OSC — sin hardware.
- DSP serio: Pan-Tompkins completo para R-peaks, Welch PSD para bandas EEG, normalización adaptativa por percentiles, doble tasa (análisis lento / salida 30Hz).
- Buen tooling: wizard, monitores, simuladores, docs, firmware con config serial.

Límites: depende de harmonic_shaper corriendo; BLE/Fitbit requieren hardware/OAuth sin CI; software de escritorio single-user.

## 5. Veredicto — drivers de entrada reutilizables

Mina de drivers ya resueltos y desacoplados; todos normalizan a OSC (el pegamento natural de un patchbay):

**Casi tal cual (alto valor):**
- `ecg_analysis.py` — `ECGProcessor`: R-peak Pan-Tompkins streaming, autocontenido, con tests.
- `eeg_analysis.py` — band powers (Welch), frecuencia dominante, concentración, mapeos a rango.
- `hr_relay.py` — parser BLE Heart Rate (`parse_hr_measurement`, spec 0x180D) + flujo OAuth2 Fitbit.
- `midi_relay.py` — patrón mínimo MIDI CC → OSC con `mido`.
- `firmware/ecg_esp32.ino` — patrón ESP32→OSC/UDP para cualquier sensor analógico.

**Como referencia de arquitectura:** el patrón "relay independiente y opcional → OSC namespaced (`/bridge/*`)" con auto-normalización (acepta 0-127 MIDI o 0.0-1.0) es exactamente el contrato para un patchbay de fuentes. `muse_bridge.py` muestra cómo mezclar N fuentes con locks y doble tasa. Los simuladores permiten desarrollar el dashboard sin hardware.

**Fuera del driver layer:** la lógica de mapeo a armónicos/fases (`compute_tilt`, `analyze_phase_velocities`, fórmula de gain) es específica de harmonic_shaper — capa de modulación/destino, no de entrada.

**Recomendación:** `eeg_analysis.py`, `ecg_analysis.py` y los parsers de `hr_relay.py`/`midi_relay.py` son candidatos a una librería común de "input drivers" compartida entre cymatic-control, HarMoCAP (que aporta el driver de pose/motion, hoy ausente aquí) y el dashboard de patcheo. El contrato OSC `/bridge/*` existente puede ser el estándar de bus fuentes↔instrumentos.
