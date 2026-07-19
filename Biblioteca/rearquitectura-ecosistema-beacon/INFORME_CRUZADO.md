# Informe cruzado: nuestro assessment vs. "Beacon Control Protocol v1" (Claude de Anii)

> 2026-07-18. Contraste entre `SINTESIS.md`/`ROADMAP.md` (este tema) y el artifact "Beacon Control Protocol — Unified Architecture" desarrollado por el Claude de Anii (claude.ai/code/artifact/8682242d-...).

## Acuerdos (el núcleo es el mismo)

1. **El patchbay/router es EL producto**, no una herramienta accesoria. Su "mappings as data, not baked into code" = nuestros mapeos como presets declarativos versionados y auditables. Coincidencia total, incluso en el porqué.
2. **Arquitectura de tres planos**: fuentes → router → instrumentos, con fuentes que emiten canales normalizados sin nombrar instrumentos. Es exactamente harmonic-weaver.
3. **HarMoCAP como referencia de contratos**: contract_id hasheado, golden vectors, stream_id scoping, presence lease, secuencia monótona, recorder+replay+kit stdlib. Adopción idéntica; ambos usamos `osc_contract.v1.json` como plantilla literal.
4. **Presets como "shows"** reproducibles = nuestras escenas conmutables en caliente.
5. **Fases "cheapest win first"**: congelar contratos primero (~su Fase 1 = nuestra F1), instrumentar después, greenfield al final. Misma lógica de secuenciación.
6. **Observación valiosa de ellos que validamos**: los cuatro synths convergen ~90% en `{gain 0–1, pan −1..+1, phase 0–360°}` por armónico + f1 + on/off. Consistente con nuestra genealogía del fork (NH shaper → digital-beacon Shaper → tines synth_beacon).
7. **Fuente de análisis de audio (FFT/onset/pitch/RMS)** como prueba de que agregar fuentes es trivial = nuestro driver audio→modulación de F5.

## Divergencias (a reconciliar con Anii)

### D1. Namespace unificado BCP vs. contratos nativos
BCP propone un protocolo único `/bcp/v1/source|instr/{id}/...` donde todos los instrumentos se reducen al modelo de voz común, con los prefijos viejos como aliases deprecated. Nosotros decidimos deliberadamente NO inventar protocolo nuevo: cada instrumento conserva su namespace nativo formalizado en manifiesto, y el weaver habla los contratos nativos.
- A favor de BCP: router más simple, instrumentos intercambiables.
- En contra: aplana al mínimo común denominador. **beacon-spatial no es un synth de voces** — es gain/az/dist/Q/mix sobre 13 bandas de una señal analógica viva; no mapea a `voice/{n}/gain|pan|phase` sin extensiones que rompen la uniformidad prometida (su propia tabla ya lista azimut/distancia/Q aparte).
- **Resolución por mérito (2026-07-18, criterio del usuario: no converger por converger)**: se adopta la normalización del plano de FUENTES porque es superadora por sí misma (un router que consume N fuentes heterogéneas necesita un frame común o crece con N casos especiales). NO se adopta el modelo de voz unificado del plano de instrumentos para el MVP: los contratos nativos + manifiestos de capacidades ya cubren al weaver, el alias agrega implementación y testing antes del evento sin necesidad que lo justifique, y el caso beacon-spatial demuestra que la uniformidad prometida no se sostiene. Si el lado de Anii necesita el modelo de voz, el alias es un adapter que puede implementarse sobre los contratos nativos sin tocar el router (candidato F5+).

### D2. Router construido sobre digital-beacon vs. greenfield
BCP: "construir router+dashboard sobre FastAPI+WS+state-store de digital-beacon (más maduro); Pair Mode ya es proto-patchbay". Nosotros: digital-beacon se desguaza y archiva (es el experimento enredado: `sample_modulator` bicéfalo, symlinks muertos, ROADMAP de otro proyecto), y harmonic-weaver nace headless en repo nuevo reutilizando patrones, no el codebase.
- El stack coincide (FastAPI+WS); la diferencia es evolucionar in-place vs. extraer.
- Nuestro requisito headless-multi-cliente (web/móvil/Quest, §6 de SINTESIS) pesa contra evolucionar una UI acoplada.
- **Reconciliación propuesta**: mantener greenfield, pero T4.1/T4.2 citan explícitamente `digital_beacon/api.py` + state store como referencia de implementación (ya era rescate parcial; subirlo de "patrón" a "referencia primaria").

### D3. Tines como instrumento vivo vs. archivado
BCP lista "tines synth + ESP32 (H2–H6)" entre los 4 instrumentos activos. **El hardware de tines ya no existe** (decisión cerrada: archivo con preservación de conocimiento). El `synth_beacon` (software) sí sobrevive como código reutilizable, pero no como cuarto instrumento del MVP. Probablemente información desactualizada del lado de Anii.

### D4. Elementos que no observamos en los repos — CONFIRMADO como trabajo sin pushear
BCP menciona "IMU + variables pareadas (sway, synchrony, pair_energy)" y un "Pair Mode" en digital-beacon que nuestro relevamiento (reporte 04) no encontró. **Confirmado por el usuario (2026-07-18)**: es trabajo local de Anii sin pushear, sobre sensores del móvil como fuente de modulación. Pendiente su push. Al llegar, evaluar por mérito contra nuestro plan F5 de "Sensor Interpreter extraído de webui.py": si el trabajo de Anii lo supera (probable: IMU + variables pareadas es más rico que DeviceOrientation crudo, y las variables pareadas son un ejemplo real de nuestra categoría de fuentes agregadas/derivadas), reemplaza esa línea de F5 y hasta podría adelantarse al MVP si está maduro. Se decide con el código a la vista.

## Qué adoptamos de BCP (solo lo superador por mérito)

1. **T1.1 se amplía**: la plantilla de contratos cubre AMBOS planos — "Source Frame v1" (canales normalizados + rangos + polarity + estado observed|held|invalid) e "Instrument Control v1" (capacidades). BCP hace explícita una simetría que nuestro T1.1 solo insinuaba del lado instrumento, y es mejor diseño con independencia de quién lo propuso: sin frame común de fuentes, el router acumula un caso especial por driver.
2. **Estados de validez en fuentes** (`observed|held|invalid`, heredados de HarMoCAP) como parte del frame estándar — nuestro diseño los tenía solo en HarMoCAP; generalizarlos es ganancia neta (todo driver puede degradar señal y el router debe saberlo).

## Qué NO adoptamos (evaluado y descartado)

- **El modelo de voz unificado de instrumentos** (`/bcp/v1/instr/{id}/voice/{n}/...`) y los aliases deprecados: ver D1. No mejora nuestro caso, agrega costo pre-evento, y falla en beacon-spatial.
- **La tabla de convergencia de instrumentos como anexo normativo**: útil como documentación informativa, pero no forma parte del contrato — anexarla sugeriría que el modelo de voz es la norma, que es justo lo que descartamos.
- **Router sobre el codebase de digital-beacon** (D2): sostenemos greenfield headless. `digital_beacon/api.py` + state store quedan como referencia primaria de implementación (rescate de patrones, no de codebase) — esto ya estaba en nuestro plan como rescate parcial; se explicita en T4.1/T4.2.

## Qué sostenemos de lo nuestro

- Alcance completo del saneamiento (F0: webui roto, basura, docs divergentes) y del archivo (tines, digital-beacon, NaturalHarmony) — BCP no lo cubre; es complementario, no contradictorio.
- La capa de naturaleza → beacon-spatial (F3) — ausente en BCP.
- Headless multi-cliente como requisito de día uno.
- Derivación de trabajo por agente/costo (mecánica ya verificada).

## Veredicto

En agreement en la visión y en la disciplina de contratos; en desacuerdo operativo en D1–D3, resuelto por mérito (criterio del usuario: se mantienen las mejores ideas de cada lado, sin converger por converger; quien tenga la idea inferior ajusta su lado). Resultado: adoptamos su simetría de contratos de fuente (superadora), sostenemos contratos nativos de instrumento, greenfield headless y el archivo de tines (D3 era información desactualizada de su lado). D4 pendiente del push de Anii (sensores de móvil) — se evalúa con el código a la vista. El contrato compartido (T1.1) se congela por mérito y se comparte con el equipo de Anii; si su lado necesita el modelo de voz, lo implementa como adapter sobre los contratos nativos.
