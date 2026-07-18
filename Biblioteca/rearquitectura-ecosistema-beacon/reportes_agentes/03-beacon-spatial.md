# Informe: proyecto `beacon-spatial` (`~/Projects/beacon-spatial`)

> Reporte crudo de agente Explore, 2026-07-18.

Aviso previo: la documentación del repo es contradictoria entre sí (el `README.md` describe una versión de 6 bandas con `extracto_2min.wav`, mientras que `MEMORY.md` y el código real describen 13 bandas con `harmonic_beacon_2026_05_13_session.wav`). El código es la fuente de verdad; el `README.md` está desactualizado. Además hay un problema crítico: `webui.py` está roto en `HEAD` (marcadores de conflicto de merge commiteados).

## 1. Arquitectura actual y motor vigente

**Motor vigente: SuperCollider.** Pure Data quedó como referencia histórica. Dos motores SC coexisten:

- `beacon.scd` — **el motor principal y actual.** Spatializer binaural de **13 bandas** (12 BPF + 1 HPF a 1800 Hz) usando ATK (Ambisonic Toolkit): FOA `FoaPanB` + `FoaDecode` con kernels HRTF "Listen" a 48 kHz. OSC en puerto **57120** (sclang). Corre contra `scsynth` en 57110.
- `beacon_pd_replica.scd` — **réplica exacta del patch PD original** de 6 bandas: BPF de BW constante 15 Hz, paneo de potencia constante, ITD (`DelayN`), atenuación 1/dist, AM "butterfly" 3.7 Hz y LFO de paneo 0.08 Hz ±90° en la banda de 240 Hz. OSC en puerto **9001** (el que usaba PD). Renderizador alternativo/A-B, no el principal.

Resto de archivos:
- `beacon-spatial.pd` — patch PD original, **legacy**. 6 bandas (40–240 Hz), `bp~` → gain → abstracción `spatializer~`. OSC vía `iemnet/udpreceive 9001`. Idéntico a `legacy/beacon-spatial.pd`.
- `spatializer~.pd` — abstracción PD del modelo espacial por banda: paneo `sin/sqrt`, ITD, 1/dist. Fuente del algoritmo que la réplica SC porta.
- `bridge.py` — **puente legacy OSC→PD**: OSC UDP 9000 → mensajes FUDI por TCP al `netreceive 8000` de PD. Ya no se usa con SC. Idéntico a `legacy/bridge.py`.
- `webui.py` (~90 KB) — **superficie de control actual.** Flask en `:5050`. 3 pestañas (Manual / Sensors / Presets), viz de espectro, control por banda (gain/az/dist/Q/solo), mix/master, record, reset, presets, y "Sensor Interpreter" (teléfono vía DeviceOrientation/DeviceMotion). Traduce HTTP POST `/control` → OSC. Envía **a ambos** motores (57120 y 9001). Rutas: `/`, `/control`, `/control/batch`, `/save_config`, `/list_configs`, `/load_config`.
- `generate.py` — generador legacy del patch PD (clase `PdPatch`). Obsoleto.
- `run-stack.sh` — launcher antiguo con `jackd` directo. Superado.
- `start-beacon.sh` — **launcher vigente.** `pw-jack scsynth` (57110), autoconexión JACK a Built-in + R24 y entrada R24 CH1→`SuperCollider:in_1`, `sclang beacon.scd` envuelto en `script(1)` (pseudo-TTY, sino sclang muere), Flask desde `venv`, opcional túnel HTTPS `cloudflared` (necesario para sensores del teléfono). Flags: `--live` (default, `SoundIn.ar(0)`), `--file` (WAV), `--no-https`.
- `start-beacon-pd.sh` — arranca solo la réplica en 9001 junto al principal, reutilizando `scsynth`.

## 2. Esquema OSC expuesto

Prefijo `/beacon/...`, un float por mensaje, índice de banda embebido en la dirección (`/N`), NO como argumento.

Motor principal `beacon.scd` (puerto 57120), 69 OSCdefs:

| Dirección | Args | Rango | Efecto |
|---|---|---|---|
| `/beacon/gain/N` | float | 0–3 | ganancia banda N (N=1..13), `.lag(0.05)` |
| `/beacon/az/N` | float | -180..180 | azimut grados (N=1..13) |
| `/beacon/dist/N` | float | 0..10 | distancia (N=1..13) |
| `/beacon/q/N` | float | — | Q/BW del BPF (N=1..12) |
| `/beacon/solo/N` | float | 0/1 | solo banda N |
| `/beacon/mix` | float | 0..1 | balance wet/dry |
| `/beacon/master` | float | 0..3 | master |
| `/beacon/record/start` | string/float | ruta WAV | inicia grabación |
| `/beacon/record/stop` | — | — | detiene |
| `/beacon/reset` | — | — | defaults |

Réplica (puerto 9001), 30 OSCdefs — mismo esquema, solo N=1..6; `/beacon/solo/+` y `record/*` son placeholders no-op. Detalle en `PD_REPLICA_OSC_SCHEME.md`.

Plantilla `beacon-osc.json` (Open Stage Control): usa `/beacon/wet` y `/beacon/dry` separados que el motor SC actual NO mapea (usa `/beacon/mix`), y `/beacon/lfo/offset` sin destino.

Discrepancia: la tabla OSC de `MEMORY.md` documenta un esquema viejo con `bandIdx` como argumento. El código real usa direcciones indexadas.

## 3. Cadena de señal

Entrada del beacon analógico: por la **Zoom R24** (interfaz USB). `start-beacon.sh` autoconecta `R24 capture_FL` → `SuperCollider:in_1` = `SoundIn.ar(0)` (modo `--live`, default). Modo `--file`: loop de `harmonic_beacon_2026_05_13_session.wav` (mono 48 kHz, ~659 MB, no en git) vía `PlayBuf`.

Procesamiento en `beacon.scd`:
1. Fuente → 12× `BPF` (Q configurable, `.lag(0.05)`) + 1× `HPF` 1800 Hz. Bandas: 40/80/120/160/200/240 (BW 40 Hz), 480/720/960/1200/1440/1680 (BW 240 Hz), HPF 1800+. Cada banda × gain.
2. Lógica de solo.
3. Camino **dry**: `Mix(bandas)` × (1-mix).
4. Camino **wet**: por banda `FoaPanB.ar(sig/dist, azRad, 0)` → B-format WXYZ → `FoaDecode.ar(bfmt, decoderListen)` × mix → binaural.
5. `(wet + dry) * master` → `Out.ar(0, 2)`. JACK/PipeWire enruta a Built-in y R24. **Requiere auriculares** (HRTF).

Sin reverb, efectos extra ni LFOs en el motor principal (decisión explícita "keep static").

## 4. `legacy/` y `research/`

`legacy/` — copia congelada del stack PD: patches, bridge, tests OSC. `beacon-spatial.pd` y `bridge.py` de raíz son idénticos a los de `legacy/` (duplicados).

`research/` — 7 markdown de deliberación multi-agente (mayo 2026) sobre qué motor elegir para reemplazar PD (propuestas de Claude/Grok/Kimi + síntesis `forum-spatial-engine-2026-05-23.md`; recomendaba Csound como spike y SC como fallback; en la práctica se adoptó SC). Contexto de decisión, no código.

Otros: `configs/` (12 presets JSON `{bands:[{gain,az,dist,solo,q}], mix, master}`; solo `version_1.json` en git). `beacon_record_260616_092811_/` es un directorio de grabación fallido (bug de ruta relativa ya corregido). `venv/`. `test_*` en raíz = pruebas del camino OSC/PD legacy.

## 5. Estado

**Funciona** (código + MEMORY.md, verificado e2e en sesiones previas): motor SC 13 bandas binaural con control OSC en vivo, grabación WAV, presets, reset; `start-beacon.sh` con autoconexión y túnel HTTPS; réplica PD en 9001; pipeline sensores de teléfono → `/control/batch`.

**Roto / crítico:** `webui.py` tiene **conflictos de merge sin resolver commiteados en `HEAD`** (commit `c8ce383`). Marcadores `<<<<<<< HEAD` / `=======` / `>>>>>>> 9fbe782` en líneas **718–780** y **1725–1753**. Confirmado con `python3 -m ast`: `SyntaxError` en línea 1753. **Tal como está en `main`, la UI no arranca.** Conflicto entre la rama `sensors` (sin mergear, existe local) y el fix de ruta de grabación (`9fbe782`).

A medio hacer: placeholders en la réplica; `beacon-osc.json` con direcciones sin destino; puerto mobile nativo "NOT YET STARTED".

Deuda técnica: docs divergentes (README 6 bandas vs código 13); duplicación raíz/legacy; dos launchers; rutas absolutas hardcodeadas a `/home/nicolas/...` en ambos `.scd`; `start-beacon-pd.sh` busca el `.scd` en una ruta de workspace Hermes kanban; directorio de grabación basura versionado; dos motores controlados por el mismo esquema OSC (ambigüedad sobre cuál es el núcleo).

## 6. Veredicto

**Núcleo a conservar:** `beacon.scd` (motor SC 13 bandas ATK, modo `--live` desde R24 CH1) como único motor canónico; `start-beacon.sh`; el esquema OSC en 57120; `webui.py` (tras resolver el conflicto) y `configs/`.

**Archivar/eliminar del núcleo:** todo el stack PD (patches, `bridge.py`, `generate.py`, tests PD, `legacy/`), `run-stack.sh`; decidir destino de `beacon_pd_replica.scd` (referencia del algoritmo PD, pero confunde). `research/` → `docs/`.

**Absorción desde digital-beacon (filtros + naturaleza):** el punto de inserción natural es el `SynthDef` de `beacon.scd`. Sumar buffers/fuentes adicionales antes o después del banco de filtros y exponer sus niveles como OSC nuevos (p.ej. `/beacon/nature/N/gain`). La arquitectura lo soporta sin rediseño.

**Falta para ser "patcheable" desde un dashboard OSC externo:**
1. Arreglar `webui.py` (bloqueante inmediato).
2. Documentar/estabilizar el mapa OSC como contrato público y corregir discrepancias (`MEMORY.md`, `beacon-osc.json`).
3. **OSC bidireccional / feedback de estado**: hoy el flujo es unidireccional; falta query/dump (`/beacon/state`) o broadcast periódico para sincronizar faders al conectar.
4. Puerto/IP configurables (hoy 127.0.0.1 y puertos hardcodeados en los `.scd`); escuchar en `0.0.0.0` para dashboard remoto.
5. Un único motor canónico en un único puerto OSC.
