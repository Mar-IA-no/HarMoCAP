# Síntesis: re-arquitectura del ecosistema Harmonic Beacon

> 2026-07-18. Basada en 6 relevamientos paralelos (ver `reportes_agentes/`) + visión del usuario registrada en §6. Estado: **propuesta pendiente de aprobación del usuario**. Las observaciones están verificadas en código; la arquitectura objetivo es hipótesis de diseño.

## 1. Diagnóstico

El ecosistema tiene hoy **seis repos** con tres problemas estructurales:

1. **Duplicación por fork**: el synth aditivo ("Shaper") existe dos veces — `NaturalHarmony/harmonic_shaper/` (5 voces, original) y `digital_beacon/audio_engine.py` (fork evolucionado: 32 voces, waveshaper, LFO por voz, sidechain, recording tap). Además `harmonic-beacon-tines/synth_beacon/audio_engine.py` es un tercer primo del mismo algoritmo.
2. **Mezcla de responsabilidades**: digital-beacon fusionó synth + spatializer + capa de naturaleza; el punto exacto de la mezcla es `sample_modulator.py`/`sample_manager.py`, cuyos `ModulationTarget` apuntan indistintamente a `"beacon"` o `"shaper"`.
3. **Contratos OSC implícitos**: cada proyecto expone OSC pero ninguno (salvo HarMoCAP) tiene su esquema como contrato formal. Hay direcciones documentadas que el código no mapea (`/beacon/wet`, `/beacon/dry`, `/beacon/lfo/offset` en beacon-spatial), docs con esquemas viejos, y flujo unidireccional sin feedback de estado.

Hallazgos operativos urgentes (independientes de la re-arquitectura):
- `beacon-spatial/webui.py` está **roto en `main`**: conflictos de merge commiteados (líneas 718–780 y 1725–1753, commit `c8ce383`, rama `sensors` sin mergear). No parsea.
- `digital-beacon` tiene basura: directorio `: RTK && ` (mkdir mal pegado, vacío), 37 symlinks muertos en `normalized_analysis/`, dos venvs.

## 2. HarMoCAP como referencia: qué se adopta

Los 7 patrones extraídos (detalle en `reportes_agentes/01-harmocap-referencia.md`):

| # | Patrón | Aplicación al ecosistema |
|---|---|---|
| 1 | Contrato machine-readable único (`*.contract.json`) + doc que cede autoridad | Cada instrumento y cada fuente publica su manifiesto OSC |
| 2 | `contract_id` por hash + golden sidecar; bump gatea clientes viejos | El patchbay verifica compatibilidad al conectar |
| 3 | Codec canónico único en stdlib pura | Un codec OSC compartido por copia (es chico) en cada repo |
| 4 | Artefacto portable generado, verificado por byte-identidad | Kits de integración entre proyectos (como harmocap-nico-kit) |
| 5 | Golden vectors del wire + round-trips como tests | Suite mínima por contrato |
| 6 | Handshake `/hello` + gating + reglas de receptor normadas | El dashboard sincroniza estado al conectar (resuelve la unidireccionalidad actual) |
| 7 | Trazabilidad decisión-a-línea + `reports/<run_id>/` + BITACORA | Convención de todos los repos activos |

El requisito conceptual (AGENTS.md de HarMoCAP) se hereda: **cada transformación movimiento/señal → parámetro musical queda documentada como decisión de diseño, explícita, auditable y de baja latencia**. El patchbay materializa esto: los mapeos son presets declarativos versionados, no código ad-hoc.

## 3. Arquitectura objetivo: la "orquesta"

```
FUENTES (estado del intérprete/grupo)          PATCHBAY               INSTRUMENTOS (serie armónica)
─────────────────────────────────       ──────────────────────       ─────────────────────────────
HarMoCAP (pose/movimiento, OSC 1.1) ─►                          ┌──► beacon-spatial (beacon ANALÓGICO
EEG Muse / ECG / HR  (cymatic)      ─►   harmonic-weaver         │      mediado: 13 bandas + naturaleza)
MIDI (Minilab3/Launchpad/teclado)   ─►   matriz de mapeo        ├──► harmonic-shaper (synth digital
audio→modulación (SampleDescriptor) ─►   fuente→transf.→destino ├──►   elemental, 32 voces)
sensores celular (DeviceMotion)     ─►   presets declarativos   ├──► surge-bridge → Surge XT
simuladores (dev sin hardware)      ─►   UI web + estado vivo   └──► (futuros: visualizer, etc.)
```

### Repos resultantes

**A. `harmonic-weaver` (NUEVO — el dashboard de patcheo).** El único desarrollo nuevo grande.
- **Servidor headless desde el día uno**: el motor de ruteo corre sin UI, con su estado completo expuesto por API/WebSocket bajo el mismo patrón contrato-manifest. Todas las UIs son clientes delgados del mismo protocolo: web primero, cliente móvil después, y eventualmente Oculus Quest vía WebXR (visor AR que puede dibujar los slots de HarMoCAP sobre la escena real — la data espacial ya viaja en el wire). Anti-patrón a evitar: UI pegada al motor, como pasó con `webui.py` en beacon-spatial (el cliente Quest sería una reescritura).
- **Núcleo**: router de modulación — cada ruta = (fuente.señal → transformación → instrumento.parámetro). Transformaciones: escala/rango, curva, suavizado, gate/umbral, combinadores (N fuentes → 1 parámetro). Granularidad de ruteo hasta el keypoint/feature individual de un slot HarMoCAP (requisito: "el sujeto focal controla un armónico por extremidad + cabeza" — el contrato 1.1 ya emite todo lo necesario; es decisión de diseño del router, no desarrollo en HarMoCAP).
- **Fuentes agregadas/derivadas como categoría de primera clase**: señales computadas sobre N fuentes, p.ej. "energía cinética media de los slots no-focales" para que la crowd module el colchón armónico. Restricción: HarMoCAP trackea hasta 8 personas y lo que cubra la cámara — para crowd real, agregados gruesos antes que tracking fino.
- **Escenas y pánico**: presets de mapeo conmutables en caliente + botón de pánico global. En vivo son críticos, no accesorios.
- **Drivers de entrada** (mayormente rescate, no desarrollo): receptor HarMoCAP (el kit ya existe), `eeg_analysis.py`/`ecg_analysis.py`/parsers BLE-HR/MIDI de cymatic-control — el `ECGProcessor` (R-peak Pan-Tompkins, con tests) es un driver de trigger rítmico casi listo e independiente del MoCap—, `SampleLayer`+`SampleDescriptor` de digital-beacon como driver audio→modulación, Sensor Interpreter (celular) extraído del webui de beacon-spatial, simuladores de cymatic-control para desarrollar y ensayar sin hardware.
- **Registro de instrumentos**: consume los manifiestos `*.contract.json` de cada instrumento; solo lo declarado es patcheable. Handshake y gating à la HarMoCAP.
- **UI web**: cliente FastAPI/WebSocket del servidor headless (el patrón WebSocket ya está probado 3 veces en el ecosistema: shaper, digital-beacon, tines). Criterio de diseño (§6): que patchear sea tan fluido que se sienta parte de la performance, no operación técnica.
- cymatic-control queda absorbido aquí (era exactamente esto, cableado en duro a un solo instrumento).

**B. `harmonic-shaper` (el synth elemental, repo propio).**
- Base de código: la versión de **digital-beacon** (32 voces + waveshaper + LFO + sidechain) — es la evolución del original de NaturalHarmony; se reconcilia el fork en una sola fuente canónica.
- Se le agrega fuente de notas propia (portar `harmonics.py` + `key_mapper.py` del harmonic_beacon), quedando el modo esclavo del broadcast como opcional.
- Deuda a saldar: deps reales declaradas (`sounddevice`, `fastapi`, `uvicorn`, `numpy`…), tests (hoy no tiene), manifiesto OSC `/shaper/*`, y los bugs de clipping que motivaron `synth_pure.py`.

**C. `beacon-spatial` (se mantiene, saneado y ampliado).** El mediador del beacon analógico.
- Motor único canónico: `beacon.scd` (13 bandas ATK, `--live` desde la R24). El stack PD completo y la réplica van a `legacy/`.
- **Absorbe de digital-beacon**: `resonant_filter.py` (filtro armónico adaptativo), `sample_layer.py` (análisis armónico/residual de muestras), `sample_player.py` + SynthDef `\sample_player` (mezcla de muestras de naturaleza en el spatializer), la mitad "beacon" de `sample_modulator.py`, y las muestras (`data/uploads/`). Punto de inserción: el SynthDef de `beacon.scd`, exponiendo `/beacon/nature/*` — la arquitectura lo soporta sin rediseño.
- Para ser patcheable: fix de `webui.py`, manifiesto OSC formal, estado bidireccional (`/beacon/state` o broadcast), host/puerto configurables.

**D. `surge-bridge` (renombre/refactor de `NaturalHarmony/harmonic_beacon/`).** El instrumento "Surge XT": hoy es MIDI→OSC(Surge); se le agrega entrada OSC de control para que el patchbay pueda modularlo igual que a los demás. Es el componente más maduro del ecosistema (tests + literate program); el cambio es de empaquetado, no de lógica. `harmonic_visualizer` lo acompaña o se separa después.

**E. `HarMoCAP`** — sin cambios: ya es una fuente con contrato formal. Aporta además el molde de todos los manifiestos.

**F. Archivo.**
- `harmonic-beacon-tines`: congelar con un `ARCHIVE.md` según el checklist del reporte 05 (preservar íntegros `NATURE_LAB_V2_DESIGN.md`, `PERFORMANCE_ANALYSIS.md`, la matemática de plugins de expresión; señalar el código reutilizable). Los generadores bioacústicos del Nature Lab son candidatos futuros a "instrumento/capa de naturaleza generativa" — se anota, no se migra ahora.
- `digital-beacon`: se archiva DESPUÉS de migrar B y C. `packages/` (nh-toolkit v2) se archiva con él, preservando `nh-analysis` (dependencia de `resonant_filter`) y el pipeline de normalización LUFS de `tools/`.
- `NaturalHarmony`: tras extraer shaper y surge-bridge, queda como archivo histórico (el literate program del beacon es valioso como documento).

### El bus OSC

No se inventa un protocolo nuevo: cada instrumento conserva su namespace (`/beacon/*`, `/shaper/*`, `/fnote`…) pero lo **formaliza** en un manifiesto con `contract_id`. El patchbay habla los contratos nativos. Las fuentes nuevas normalizan a un namespace de fuente (el patrón `/bridge/*` de cymatic-control es el precedente). Latencia: todo el ecosistema ya es OSC/UDP local; HarMoCAP demostró p50 ~7 ms software — el patchbay debe presupuestar su overhead y medirlo con el patrón `reports/<run_id>/`.

## 4. Plan de migración por fases

- **F0 — Saneamiento (sin re-arquitectura, desbloquea el evento):** resolver el merge de `webui.py` (rama `sensors` vs `9fbe782`); borrar `: RTK && `, symlinks muertos y venvs duplicados de digital-beacon; corregir docs divergentes de beacon-spatial.
- **F1 — Contratos:** escribir los manifiestos OSC de beacon-spatial y del shaper (formalizar lo que ya existe), con codec/validador copiado de HarMoCAP. Estado bidireccional en beacon-spatial.
- **F2 — Extracción del shaper:** nuevo repo desde la versión digital-beacon, reconciliando con NaturalHarmony; fuente de notas propia; tests golden del contrato.
- **F3 — Naturaleza → beacon-spatial:** migrar filtro + sample layer + player + mitad beacon del modulator; `/beacon/nature/*`.
- **F4 — harmonic-weaver MVP (alcance fijado por el usuario, §6):** servidor headless + cliente web con 3 fuentes (HarMoCAP, MIDI, ECG como trigger rítmico) y 2 instrumentos (beacon-spatial, shaper), escenas conmutables en caliente + botón de pánico, y ensayo del setup completo con los simuladores de cymatic-control (sin gente ni hardware). Criterio de éxito = el escenario del evento: beacon analógico sonando mediado + shaper + mapeos en vivo, sujeto focal controlando armónicos por extremidad + cabeza.
- **F5 — Más drivers, clientes e instrumentos:** EEG/HR, audio→modulación, sensores de celular; surge-bridge con entrada OSC; cliente móvil; cliente Oculus Quest (WebXR/AR) — la arquitectura headless de F4 lo deja preparado sin costo extra ahora.
- **F6 — Archivo:** ARCHIVE.md en tines; archivo de digital-beacon y NaturalHarmony tras verificar que nada quedó sin migrar.

F0–F1 son baratas y de bajo riesgo. F4 es el desarrollo nuevo real. F2–F3 son mudanzas con criterio.

## 5. Decisiones del usuario (todas resueltas 2026-07-18)

1. **Shaper canónico**: ✅ la versión digital-beacon (32 voces + waveshaper + LFO + sidechain) como base del nuevo repo; la de NaturalHarmony queda como historia.
2. **Destino de NaturalHarmony**: ✅ desguace — `harmonic_beacon` se extrae como surge-bridge, el shaper al nuevo repo, visualizer acompaña a surge-bridge; el repo se archiva (literate program preservado).
3. **Nombres**: ✅ `harmonic-weaver` (dashboard), `harmonic-shaper` (synth), `surge-bridge` (instrumento Surge XT).
4. **Nature Lab bioacústico** (tines): ✅ solo archivo ahora; queda anotado como candidato a capa generativa post-evento.
5. **Alcance del MVP** (§6): ✅ F0+F4 con HarMoCAP + MIDI + ECG como fuentes, beacon-spatial + shaper como instrumentos, escenas en caliente + pánico, ensayo con simuladores. Quest/AR y demás biofeedback en F5+.
6. **Organización GitHub**: ✅ esquema HarMoCAP — `origin` con doble pushurl (Mar-IA-no + espejo AlterMundi), públicos.

El plan ejecutable con derivación de trabajo por agente está en `ROADMAP.md` (mismo directorio).

## 6. Visión del usuario (2026-07-18, conversación /btw)

Contexto aportado por el usuario que fija requisitos y resuelve la decisión 5:

- **Interacción escénica objetivo**: el sujeto seleccionado (foco) controla un armónico por extremidad + cabeza. Cubierto por el contrato HarMoCAP 1.1 (17 keypoints + 21 features por persona, foco por `/control/select` y marcador `focused`); exige granularidad de ruteo a nivel keypoint/feature en el router.
- **ECG como fuente rítmica** del conjunto, independiente del MoCap (sensor de pecho ESP32). Entra al MVP.
- **La crowd modula el colchón armónico**: origina la categoría de *fuentes agregadas/derivadas* (p.ej. energía cinética media de slots no-focales → beacon-spatial). Límite práctico: 8 slots + cobertura de cámara; para crowd real, agregados gruesos.
- **Clientes múltiples**: dashboard web + cliente móvil + eventualmente Oculus Quest con AR (dibujar los slots sobre la escena real). Consecuencia arquitectónica fijada: harmonic-weaver nace **headless**, todas las UIs son clientes delgados del mismo protocolo con contrato-manifest. El Quest es F5+ sin costo extra ahora.
- **Operación en vivo**: escenas/presets de mapeo conmutables en caliente + botón de pánico; ensayo del setup completo con simuladores, sin la gente ni el hardware.
- **Marco conceptual**: referencia al Bé de los Baka — polifonía comunitaria sin separación dura entre intérprete, danzante y coro. El "master operator" no es director jerárquico sino quien teje los hilos entre participantes. Criterio de diseño de UI derivado: patchear debe sentirse parte de la performance, no operación técnica.
