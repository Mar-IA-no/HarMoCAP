# Bitacora - HarMoCAP

> Log cronologico del proyecto. La edicion canonica corresponde al rol auditor activo o a una instruccion explicita del usuario.

---

## 2026-07-17 - S0 - Init del workspace

Workspace inicializado con `mandinga_init_workspace` en `/mnt/m2-1TB/HarMoCAP`.

Definicion inicial: desarrollo de software para pose estimation y tracking corporal con Ultralytics YOLO26m-pose. El primer workflow usara COCO8-pose como dataset pequeno de validacion tecnica; el objetivo posterior es seleccionar y curar datasets mas grandes para tracking en tiempo real de una o varias personas.

Integracion prevista: las variables de movimiento alimentaran un modulador en tiempo real de la armonia de Harmonic Beacon. La percepcion, el tracking, la representacion corporal y la modulacion se mantienen como capas separables.

Roles: Claude y Codex pueden actuar como implementador o auditor segun la asignacion casuistica del usuario; no hay ownership permanente.

Archivos sembrados:

- `AGENTS.md` + `CLAUDE.md`
- `BITACORA.md`
- `PENDIENTES.md`
- `NOTAS_CLAUDE-CODEX.md` + `NOTAS_CODEX-CLAUDE.md`
- `README.md`
- `.gitignore`
- `Biblioteca/INDEX.md`

Memoria persistente de Codex: `/root/.codex/memories/mariano_global_directives_2026-07-09.md`. Las 25 directivas universales de `mandinga_init_workspace` ya constan alli; no se duplicaron.

Mensaje recursivo `001` integrado: se adopta el uso activo de la memoria colectiva y el registro de notas nuevas en `/mnt/m2-1TB/inbox/new/` cuando un hallazgo sea relevante para otros proyectos. El mapa permanece read-only.

La documentacion tecnica de pose consultada es `https://docs.ultralytics.com/tasks/pose#train`; el contexto conceptual inicial se ancla en HIT cap. 12 y el marco Beacon-HIT.

Repositorio principal: `Mar-IA-no/HarMoCAP` (privado), creado y publicado con los commits `a28bd8c` y `66b5004`. Espejo privado previsto: `AlterMundi/HarMoCAP`. El remoto local `altermundi` y los dos `pushurl` de `origin` ya estan configurados; falta que un administrador cree el repositorio organizacional porque la cuenta autenticada no tiene el scope/permisos necesarios para hacerlo.

## 2026-07-17 - S1 - Visibilidad y espejo GitHub

Por decision del usuario, ambos repositorios quedaron publicos:

- `Mar-IA-no/HarMoCAP`
- `AlterMundi/HarMoCAP`

El repo organizacional fue creado y el personal cambio de privado a publico. El push dual local queda habilitado para sincronizar `main` en cada `git push origin`.

## 2026-07-17 - S2 - Mensajes recursivos 002-003 integrados

Los mensajes recursivos `002` y `003` agregaron el contexto operativo de GitHub:

- `Mar-IA-no` autentica mediante el token OAuth de `gh`.
- `AlterMundi` usa un PAT fine-grained separado, con `Contents R/W` solo sobre repositorios autorizados.
- Crear un repositorio organizacional y pushear a uno existente son operaciones distintas.
- El repositorio nuevo `AlterMundi/HarMoCAP` ya existe y es publico, pero el PAT de AlterMundi aun debe incluirlo en su allowlist para que el push automatico funcione.

La prueba de `git push origin main` publico `a124285` en `Mar-IA-no` y recibio `403` en `AlterMundi`; el mismo commit fue publicado manualmente en el espejo con la credencial de `gh`. Por lo tanto, ambos `main` estan alineados en `a124285`, pero la sincronizacion automatica queda condicionada a que un owner agregue `AlterMundi/HarMoCAP` al PAT fine-grained. No se copiaron tokens a archivos del proyecto ni a la memoria colectiva.

## 2026-07-17 - S3 - Sincronizacion GitHub verificada

El usuario actualizo el PAT fine-grained de AlterMundi para incluir `HarMoCAP` con permiso de escritura. La prueba posterior de `git push origin main` termino correctamente para los dos destinos:

- `Mar-IA-no/HarMoCAP`: publico, `main` en `a1242853cd6df0e3a0771c1edcc5fbe35a605931`.
- `AlterMundi/HarMoCAP`: publico, `main` en `a1242853cd6df0e3a0771c1edcc5fbe35a605931`.

La sincronizacion automatica del espejo queda operativa mediante los dos `pushurl` de `origin`.

## 2026-07-17 - S4 - MVP implementado: pipeline YOLO-pose + interfaz OSC para Nico

Implementado el plan del MVP (v10 + addendum), auditado adversarialmente con Codex (skill codex-audit-loop, 8 rounds, trayectoria 16-16-16-14-12-8-9-11, ~102 findings integrados; loop cerrado por el usuario con veredicto "apto para implementacion"), mas autoauditoria de Claude (5 findings) y auditoria externa de ChatGPT (8 hallazgos integrados como addendum: stream_id por arranque, coordenadas isotropicas, licencia desde M0, sesion de ejemplo sintetica, semantica de contadores, perfil de captura, naming laban_*_proxy, lockfile).

Decisiones del usuario registradas: licencia MIT (checkpoint previo a M0/M4); interfaz OSC + spec + replay mock; agnostica del motor de audio; MVP de una persona con esquema multi-persona.

Entregado (M0-M5, verificado):

- M0: scaffolding, venv con deps pineadas (`ultralytics==8.4.99`, torch 2.13 cu126 sobre RTX 3090), `requirements.lock`, configs YAML, licencia MIT.
- M1: workflow ML validado con coco8-pose (train 3 epochs / val / predict, extraccion robusta N=0 y `boxes.id None`); export de `yolo26m-pose` a TensorRT engine `half=True` (47 MB, SHA-256 y build log en `reports/20260717_e71e14a/`), con prueba de carga+inferencia.
- M2: `capture.py` (hilo lector ultimo-frame, ritmado para fuente-archivo), `perception.py` (engine verificado en runtime), `identity.py` (slot con histeresis + tombstones repetidos), `smoothing.py` (One-Euro time-aware + maquina observed->held->invalid).
- M3: `features.py` — 21 variables causales (posturales + cinematicas + proxies Laban), normalizacion por torso/torso2, calibracion por generaciones con fallback fijo; fuente canonica `docs/FEATURES.md`.
- M4: contrato OSC v1 completo — manifiesto `schemas/osc_contract.v1.json` (unica fuente de verdad, contract_id `ce85a6de...`), codec canonico unico stdlib (`osc_codec.py`), emisor con bundles atomicos <=1200 B + handshake /hello + /calibration con rebroadcast, recorder no bloqueante, replay capture-timing; `docs/INTERFACE_SPEC.md`; sesion sintetica determinista de 4 fases + 3 fixtures; **kit portable `harmocap-nico-kit/`** generado desde fuentes canonicas, stdlib pura, con selftest y aislamiento probado con el Python del sistema.
- M5: `docs/DATASET_ROADMAP.md` (CrowdPose/AIST++ aptos; COCO pendiente asset-level; auditoria de esqueletos previa a fine-tuning).

Verificacion: 36/36 tests pasan (suavizado, identidad, invarianzas de features, golden vectors del wire, round-trips, tamanios, interop python-osc, aislamiento del kit). E2E real: video 300 frames -> engine TensorRT -> tracking -> features -> OSC UDP -> receptor del kit (Python del sistema, aislado): 290/290 bundles recibidos, 0 perdidos, 0 gateados. Metricas (fuente archivo, SIN latencia fisica de camara — no hay camara en este equipo): latencia software p50 6.7 ms / p95 7.4 / p99 9.9; jitter p50 0.2 / p99 5.4 ms — bajo los umbrales candidatos (40/60/90 y 15 ms). Artefactos en `reports/20260717_e71e14a/realtime_metrics.json`.

Pendiente (decisiones GO/NO-GO del usuario): firma de umbrales de aceptacion antes de la corrida con camara fisica real (medicion motion-to-wire con estimulo fisico); evaluacion INT8 (solo si hiciera falta); entrega del kit a Nico.

## 2026-07-17 - S5 - Hito 2: multi-persona con seleccion de foco (contrato 1.1)

Implementado el hito 2 (plan aprobado por el usuario; decisiones registradas: maximo 8 personas simultaneas; seleccion de foco por comando OSC Y teclado local; se emiten TODAS las personas con marcador `focused`).

Cambio central del contrato (1.0 -> 1.1): **un bundle OSC atomico POR PERSONA** (antes por frame) — un bundle con 2+ personas excedia el presupuesto MTU de 1200 B; con la nueva granularidad cada datagrama queda ~1 KB independiente de N y escala a 8 slots. La atomicidad pasa a ser por-persona; el receptor ensambla por (captured_frame_id, slot) con n_persons como guia. Nuevos elementos: `/person/{slot}/focused` (1|0) y `/harmocap/v1/control/select` (int: 0-7 pinea, -1 auto) al puerto de control. `contract_id` nuevo (`82c51ab2...`): un kit 1.0 gatea el stream 1.1 a proposito.

Implementacion: `SlotManager` (generaliza el slot principal: asignacion lowest-free, histeresis por slot, tombstones por slot, foco auto-con-histeresis/manual con reversion al morir el focal); pipeline con smoother+extractor POR SLOT; emisor con callback de seleccion; `run_realtime --show` (overlay cv2 con esqueletos, teclas 1-8/0/a/q); replay y kit actualizados; fixture sintetico `two_persons.jsonl` con cambio de foco a mitad de sesion; INTERFACE_SPEC 1.1.

Verificacion: 43/43 tests (SlotManager: asignacion/histeresis/tombstones/foco/compat max_slots=1; wire: bundle por persona <=1200 B peor caso, focused, control/select, golden nuevo; kit: aislamiento con Python del sistema). E2E real: video de 30 s con ~4-7 personas -> engine TensorRT -> 2879 bundles multi-persona; foco automatico en slot 0, `/control/select 2` enviado por UDP en vivo -> foco migro al slot 2 (modo manual) verificado en el wire y en el reporte del pipeline. Latencia software con multi-persona: p50 6.9 ms (sin degradacion vs una persona).

Nota operativa: si el kit 1.0 ya fue entregado a Nico, debe reemplazarse por el regenerado (el cambio de contract_id es deliberado).

## 2026-07-18 - S6 - Promocion ft2 + Hito 4: identidad robusta (modo grupo) y modo masa (contrato 1.2)

**Promocion ft2** (H4-P0): el fine-tune CrowdPose+COCO30k cumplio ambos umbrales GO/NO-GO (+2.96 AP CrowdPose / -0.70 COCO, umbral +1.5/-1.0) y paso la revision visual del usuario. Re-export a TensorRT **dinamico** (`dynamic=True`, valido 640 y 1280 — el engine M1 era estatico a 640 y el modo masa habria caido silenciosamente al .pt): `outputs/harmocap-m-pose-ft2.engine` (49 MB, sha en `reports/20260717_e71e14a/engine_build.json`). `configs/model.yaml` promovido (realtime=engine ft2, fallback=`harmocap-m-pose-ft2.pt`, conf 0.05 y max_det 300 por decision del usuario). Smoke e2e verificado: `is_engine: true`, receptor del kit 0 gated / 0 lost.

**Hito 4** (plan v2 autoauditado; implementado en automode por directiva del usuario):

- **Modo grupo** (`--mode group`, default): tres capas contra la perdida de identidad. (1) BoT-SORT+ReID `model: auto` + (2) `track_buffer 120` (`configs/tracker_group.yaml`); (3) reasociacion a nivel SLOT en `identity.py`: prediccion de posicion (pos+vel EMA con incertidumbre creciente), gate de tamano, gating por borde de salida, teleport-reset de smoother+features; umbrales auditables en `configs/identity.yaml` seccion `reacquisition`.
- **Modo masa** (`--mode crowd`): imgsz 1280 (engine dinamico), ByteTrack, y **contrato 1.2**: nuevo mensaje `/harmocap/v1/crowd` (bundle propio por frame, emitido en AMBOS modos) con 8 agregados sobre TODAS las detecciones crudas (crowd_count, crowd_qom, density, centroid, flow, dispersion) — `src/harmocap/crowd.py`, causal, ventanas trailing. Bumps: schema 1.2.0, contract_id nuevo (kit 1.1 gatea el stream 1.2 a proposito), manifiesto+golden+JSON Schema+INTERFACE_SPEC+kit regenerado con fixture `crowd.jsonl`.
- Fix de contabilidad en el receptor de referencia: `/crowd` consume `bundle_seq` y debe integrarse al descarte monotonico (sin eso, cada crowd contaba como bundle perdido).

**Validacion de identidad** (`scripts/eval_tracking.py`, proxy sin ground truth documentado; `reports/20260717_e71e14a/tracking_identity_eval.json`), videos de baile `Biblioteca/test/two`:

| Config | IDs unicos (v1/v2) | slot-switches/min (v1/v2) | fps proceso 3090 |
|---|---|---|---|
| (a) ByteTrack (baseline MVP) | 255 / 850 | 55.7 / 56.3 | 123-136 |
| (b) BoT-SORT+ReID buffer120 | 214 / 849 | 45.8 / 50.5 | 30-33 |
| (c) (b) + reasociacion slots | 214 / 849 | **11.0 / 8.3** | 30-33 |

Reduccion monotona (a)→(c): -80%/-85% de slot-switches (255/856 rebinds logrados por la capa 3). **Overhead ReID+GMC: ~4x** (136→33 fps de proceso en 3090) — sigue >=30 fps o sea tiempo real, pero al borde; en Mac (mps) el modo grupo probablemente no sostenga 30 fps con ReID: knob documentado (`with_reid: False` o `gmc_method: none` para camara fija). Renders de inspeccion visual con slot-ID coloreado (a vs c) en `Biblioteca/test/two_slots_render/` para veredicto del usuario.

Verificacion: 54/54 tests (reasociacion: rebind cerca de prediccion, rechazo lejos, gating de borde, teleport-reset; crowd: agregados sintenticos; wire crowd bundle; kit isolation). Memoria de supervision ft1 eliminada (hito 3 cerrado).

Pendiente (usuario): veredicto visual sobre los renders de slots; decision de tuning (`appearance_thresh`, `track_buffer`) tras uso real; reenvio del kit 1.2 a Nico.
---

> **Nota de merge (2026-07-18, Claude):** desde aca abajo, entradas escritas por
> Nico en el espejo AlterMundi (linea paralela, numeracion propia S6-S15 que
> colisiona con la de arriba; se preservan sin renumerar). Integradas por merge
> al detectar el push rechazado en el espejo.

## 2026-07-18 - S6 - Re-arquitectura del ecosistema Beacon: arranca la orquestacion (Wave 1 completa)

El usuario aprobo ejecutar el plan de `Biblioteca/rearquitectura-ecosistema-beacon/` (Fable) en modo orquestado: CompAII (Hermes/kimi-k3) despacha builds por ia-bridge y audita cada resultado; Codex Sol (gpt-5.6-sol xhigh) toma la ruta critica que el plan original asignaba a Claude (sin tokens). Documentos del modo en `Biblioteca/beacon-ecosystem-orchestration/` (README, ORCHESTRATION, GOALS, briefs/). Ledger: board Kanban `beacon-ecosystem-orch`.

Infra previa (plano 2, ya en `feat/hermes-support` de ia-bridge-mcp, pusheado): `--effort`/`--max-turns` ahora llegan de verdad al agente (eran no-ops); codex con `-s workspace-write` (antes sandbox read-only: builds "exitosos" que no escribian); grok effort `high` (el CLI no acepta `max`); timeout default 3600 desde config; CLIs symlinkados en `~/.local/bin` (los shells no interactivos no veian `~/.npm-global/bin` — causa probable de fallos historicos de Robin).

Wave 1 (5/5 cards done, todo auditado antes de commit):
- T0.1 (codex Sol): `webui.py` de beacon-spatial vuelve a parsear; conflictos de merge resueltos conservando sensores + fix de ruta de grabacion. Verificado en vivo: Flask bootea, GET / y POST /control responden 200. Commit `ea8202f`.
- T0.2 (kimi): digital-beacon saneado — dir `: RTK && ` (0 archivos), 37 symlinks rotos + `normalized_analysis/`, `.venv` duplicado (843 MB). `data/uploads/` y `sample_manager.py` intactos.
- T0.3 (grok): README de beacon-spatial alineado al motor real (13 bandas SC, puerto 57120), tabla OSC de MEMORY.md corregida al esquema `/beacon/*/N`, `beacon-osc.ANNOTATIONS.md` para direcciones sin destino. Commit `aa90637` (+ `.grokignore`).
- T2.1 (kimi): `harmonic-shaper` scaffolded y publicado — `nicoechaniz/harmonic-shaper` + `AlterMundi/harmonic-shaper`, `origin` con doble pushurl (esquema espejo, usuario decidio cuentas propias en vez de Mar-IA-no). Commit `f6b01ab`.
- T6.1 (kimi): `ARCHIVE.md` en harmonic-beacon-tines, commiteado `bdb1984` y pusheado.

Nota de proceso: el board se opera manual (dispatcher off); las transiciones las hace CompAII al despachar/auditar (single-writer). Status validos de este Kanban: no usar `in_progress` (termino Lattice) — usar `running`.

## 2026-07-18 - S7 - Fase F0 completa + F1 en marcha (waves 2-3)

F0 (saneamiento) cerrado al 100%: webui.py reparado (ea8202f), digital-beacon sin basura, docs alineados (aa90637), beacon-spatial con root = solo stack vigente (d816b7b).

Wave 2: harmonic-weaver scaffolded (269bba3, repos nicoechaniz + AlterMundi, doble pushurl). T0.4 commiteado con dedupe byte-verificado.

T1.1 (ruta critica, codex Sol): plantillas de contratos AMBOS planos en harmonic-weaver (a42fbc7) — Source Frame v1 (canales normalizados + estados observed|held|invalid generalizados) e Instrument Control v1 (namespaces nativos + state_sync bidireccional obligatorio + voice_model_alias OPCIONAL = resolucion del hibrido D1 del INFORME_CRUZADO). Codec stdlib copiable + 4/4 golden tests. Detalle menor: pyproject necesitaba [tool.pytest.ini_options] pythonpath=["src"] para que pytest corra sin install (agregado).

Wave 3 en curso: T1.2 (codex Sol: manifiesto beacon-spatial + /beacon/state dump + host/puerto configurables), T4.1 (codex Sol: CORE_DESIGN + stage contract draft), T1.3 cerrada (grok): shaper.contract.json formalizando la superficie EXISTENTE (/digital/* + broadcast /beacon/*), con discrepancias reporte-vs-codigo documentadas (el codigo gana), codec byte-identico, 7/7 tests (a1218f8). digital-beacon con .grokignore (fa6dca7).

Nota de proceso: codex Sol corre builds en paralelo en repos distintos sin conflicto; si aparece rate-limit, el fallback es re-dispatch secuencial.

## 2026-07-18 - S8 - T1.2: beacon-spatial ya es instrumento formal (F1 completa para MVP)

T1.2 (codex Sol) cerrada y verificada E2E EN VIVO por CompAII (el sandbox de codex no podia abrir UDP; la verificacion real se hizo desde el orquestador): scsynth + sclang boot reales, `OSCdefs registered: 71`, request `/beacon/state` con contract_id correcto -> dump atomico de 73 mensajes (begin + 66 valores + end), con `/beacon/master`=1.5 y `/beacon/gain/3`=2.2 reflejados. Commit `2a9d314`.

Entregado: `beacon_spatial.contract.json` + golden (69 OSCdefs formalizados, sin voice_model_alias — el contraejemplo canonico del hibrido D1), dump de estado bidireccional gateado por contract_id con cola por requester, `/hello` con rebroadcast 1 Hz, listen configurable via BEACON_OSC_HOST/PORT (loopback por default, 0.0.0.0 abre remoto), tests 6/6, conftest.py para pytest sin hacks.

F1 (contratos) queda completa para el MVP: beacon-spatial + shaper tienen manifiesto formal; harmonic-weaver define las plantillas. F2 (extraccion del shaper) es la proxima fase grande.

## 2026-07-18 - S9 - Wave 4 extraction and source drivers

T2.2 closed: the digital-beacon Shaper is now the standalone `harmonic-shaper` package (`795972d`). The extraction includes the 32-voice engine, state store, OSC receiver, API/WebSocket state surface, MIDI controls, and pure NumPy renderer. Audit evidence: isolated editable installation, 13 passing tests plus one optional-dependency skip, CLI argument surface, and a live headless HTTP API mutation/panic-release probe. No audible-output claim was made; R24 validation remains part of T4.5.

T3.1 closed: `nature/` was migrated into beacon-spatial (`4532fa9`): ResonantFilter, SampleLayer, and the minimal vendorized `harmonic_mask` implementation. The source-tree `nh_analysis` dependency is absent. Audit evidence: 13 passing tests and a real synthetic separation probe with finite output and exact harmonic-plus-residual reconstruction.

T4.3a and T4.3c closed in harmonic-weaver (`5616a2f`): HarMoCAP and ECG source drivers, including focus/state propagation, stream gating, lease behavior, ECG edge-trigger semantics, and 30 passing combined tests at integration.

T4.3b was not closed: Kimi returned an explicit quota 403 after creating an untested partial MIDI driver. The partial work is being recovered through the active Codex GPT lane; it is not committed or accepted.

## 2026-07-18 - S10 - Wave 5 en curso: T2.3, T2.4, T3.2 cerradas

T4.3b recovered and closed: Codex rebuilt the partial MIDI driver (untracked file from the exhausted Kimi run was input, not trusted output). `harmonic-weaver` `d0d38f9`: hot-plug tolerant driver, lazy mido import, 10 focused tests, 40-test suite, real no-hardware probe emitting complete invalid Source Frame channels.

T2.3 closed: native MIDI-note harmonic source in harmonic-shaper (`fefe142`). Dependency-free mapping ported from NaturalHarmony (`harmonics.py`/`key_mapper.py`); `--slave` remains optional; `/digital/*` unchanged. Audit evidence: 43 focused tests, 57-test suite, headless VoiceParameterStore probes, and an explicit same-band collision regression (notes 0 and 12 share band 1; superseded note-off must not silence the current owner).

T3.2 closed: nature sample player in beacon-spatial (`39831c8`). `\sample_player` SynthDef mixed into the 13-band path; `/beacon/nature/load|gain|stop` with strict path validation; manifest extended to 74 OSCdefs with atomic state dump carrying nature fields. Audit evidence: 17 tests including a real UDP OSC-string type probe (sclang decodes OSC `s` as Symbol — the original handler's String-only guard rejected valid packets; now both textual types accepted, numerics/blobs still rejected) and a full orchestrator E2E: real scsynth+sclang, generated WAV load → gain 0.35 → state dump with active path → stop → empty path. Audible listening explicitly unconfirmed.

T2.4 closed: clipping characterized, not hidden (`7f1dfc2`). Headless smoke suite with measured peak/RMS/full-scale counts for one-voice, 32-voice, and rapid-transition scenarios; live callback vs pure reference equivalence proven sample-exact in steady sections. Real fix: `synth_pure` erased release-tail gains (read -120 dB from inactive frames); now holds last active gain until envelope ends. Shared `soft_limit` (tanh*1.05*0.95) used by both renderers. Decision documented in `docs/CLIPPING_DIAGNOSIS.md`: keep 1/sqrt(N) + bounded limiter, no arbitrary normalization. 63 tests + 1 skip.

Wave 5 remaining in flight: T4.2 (weaver engine, critical path, Codex Sol), T3.3 (beacon-only modulation split, Grok). Process note: this session ran gpt-5.6-terra then k3; both repairs (T3.2 string-type, T2.3 collision test) were dispatched as focused follow-up builds rather than accepting partially verified work.


## 2026-07-18 - S11 - Wave 5 closed + archives complete (F6 done)

T3.3 closed: beacon-only modulation split in beacon-spatial (`0a40191`). Four presets (spectrum-projection, harmonic-projection, consonance-gate, timbre-filter) validated against the formal 13-band manifest; band 0/14..32/q-on-13 rejected at validate time. Behavioral audit: all preset emissions in-contract, EWMA direction, runtime no-shaper-import check. Shaper-half explicitly deferred to F5.

T4.2 closed — the critical path engine (`4b625b9`). Audit found the WS test silently skipped (fastapi undeclared in system python); isolated venv with declared deps gave 52 tests + 4 subtests with the WS round trip actually running. Live verification: uvicorn boot, real TCP WS handshake/gate/snapshot, route emit to native capability, panic latch gating routes, panic_reset safety dispatch to 5 voices, clear/recover. Evidence reports written by the engine itself.

T3.4 closed (`de2768c`): both nature WAVs moved to beacon-spatial assets (gitignored, SHA-256 MANIFEST tracked); hashes verified.

T6.2 closed by CompAII: §6 migration map fully verified on disk. T6.3 closed: ARCHIVE.md committed and pushed in digital-beacon (`ccce16c`, incl. final-state legacy gain fix a71a832) and NaturalHarmony (`22bd2ee`). F6 complete: tines + digital-beacon + NaturalHarmony all archived with destination maps.

Remaining: T4.4 (patchbay, Codex in flight) → T4.5 (e2e rehearsal, never descoped; brief written with pre-verified inventory: 659 MB file-mode WAV present, two_persons fixture, ECG simulator, frogs sample in assets).


## 2026-07-18 - S12 - T4.4 + T4.5: plan complete

T4.4 closed: web patchbay (`b2f6796`). Codex reported honestly that its sandbox blocked loopback sockets, so the mandatory browser validation ran from the orchestrator: headless Chrome via CDP, populated engine, channel select -> patch created (verified in DOM and cross-checked against engine state over a second WS client), UI PANIC -> engine panic_active, clear/recover. Screenshots committed in reports/t44-patchbay-audit/. 54 tests + 4 subtests in isolated venv.

T4.5 closed — the never-descoped gate: FULL REHEARSAL PASS live (`6d84203`, run t45-20260718T112715Z). 46/46 assertions, 125.3 s, exit 0. Beacon-spatial (file mode, 659 MB source) + headless shaper + weaver with 3 drivers + HarMoCAP two_persons replay + deterministic ECG stream. Event-demo scene: focus subject -> 5 shaper harmonics (wrists/ankles/head), crowd -> beacon master, ECG -> nature gain pulses, frogs sample loaded. Scene hot-swap to sparse and back; global panic latched (shaper voices released, beacon silence profile, routes gated 3 s) and clean recovery. Audio evidence: SC-recorded master WAV 109.3 s, 96.1% non-silence, all finite, peak 0.22. Audible human monitoring explicitly unverified, as declared.

Two real bugs found by live audit, not by the agents: (1) runner.py Path.resolve() dereferenced the venv symlink and child processes lost site-packages (orchestrator fix); (2) LiveOSCTransport used asdict() on engine-frozen mappingproxy bindings -> TypeError after sendto on every route output, metrics counting 39736 phantom transport errors (Codex repair with regression test using real engine-frozen bindings).

PLAN COMPLETE: all 26 Kanban cards done. F0-F4 + F6 of the beacon ecosystem re-architecture executed and verified. Remaining explicitly unverified (by design): human audible monitoring, R24 live input, real MIDI hardware, live people/cameras.


## 2026-07-18 - S13 - Live test: cámara Logitech + auris R24

Primer ensayo físico con Nicolás. Hardware: Logitech C920e (640x480 MJPEG), R24 auriculares (beacon file mode), notebook cam fallback. Software: beacon-spatial (file, 659MB), harmonic-shaper (audio real, sin --slave), weaver rehearsal runtime (lease_ms=2500, drivers harmocap+midi+ecg), HarMoCAP YOLO26m-pose CUDA (RTX 2060, fallback cu126 tras crash cu130).

Stack: beacon via start-beacon.sh --file, shaper via /tmp/harmonic-shaper-audit venv con sounddevice, weaver runtime con fuentes instaladas + event-demo scene (7 rutas: 5 shaper + crowd beacon + ecg nature).

Resultados:
- Beacon crowd → master: FUNCIONA. 172 escrituras a /beacon/master con valores variables (0.38-0.73) sincronizados al movimiento corporal. Confirmación de ruteo vivo.
- Shaper 5 voces (muñecas/tobillos/cabeza): NO DISPARAN. Ni con rutas directas (sin agregadores, min_confidence=0), ni con hold_then_reset. Causa no aislada completamente. La ruta crowd (mismo motor, misma escena) sí evalúa; la diferencia parece estar en el tipo de canal (features vs keypoints) o en cómo el engine almacena los valores de keypoints de slots presentes. El diagnóstico en vivo fue interrumpido para guardar estado.
- ECG: sin simulador corriendo, ruta a nature_gain queda en default 0.08. No probado.
- Audio shaper: motor de audio corriendo (sounddevice PipeWire) pero sin voces activadas. Auriculares solo recibían el beacon file.

Issues encontrados:
1. **Engine source lease recovery**: si el source harmocap pierde presencia >2500ms, el engine marca gate "absent" y NUNCA se recupera sin re-hello. El rehearsal no lo mostraba porque el fixture era continuo. En vivo, cualquier pausa (crash CUDA, persona fuera de cuadro) rompe el source permanentemente. Fix temporal: lease_ms=300000. Fix real: auto-recovery en el engine o re-hello periódico desde el runtime.
2. **CUDA crash cu126 en RTX 2060**: torch 2.13.0+cu126 crasheó a los ~4.5 min con "illegal instruction" (probablemente un kernel sm_75 faltante en esa build). Requiere instalar torch cu124 (matching driver 550) o CPU para sesiones largas.
3. **Path.resolve() en venv**: runner.py dereferenciaba el symlink del venv → subprocesos perdían site-packages. Fixeado (no usar resolve en REHEARSAL_PYTHON).
4. **LiveOSCTransport + mappingproxy**: ya resuelto en T4.5 repair (dict explícito en vez de asdict()).

Próximos pasos para el /new:
- Debug gear: ¿por qué las rutas shaper no emiten cuando crowd sí? Hipótesis: _channels_for_present_slot vs feature channels vs state del keypoint. Reproducir en test con fixture real.
- Grabar sesión de HarMoCAP + audio SC para evidencia reproducible.
- Probar con cámara integrada a 720p para mejor encuadre de cuerpo entero.
- Ajustar escena para usar features (no keypoints) si el bloqueo es específico de keypoints.

## 2026-07-18 - S14 - Diagnóstico shaper: causa raíz encontrada y fixeada

Diagnóstico offline con evidencia de la sesión viva (sin cámara): replay de `/tmp/live-test-session2.jsonl` (grabación real, 52k frames) a través del driver + engine reales con escena event-demo y clock virtual.

Hallazgos:

1. **La cadena shaper funciona con datos vivos.** Con el manifiesto corregido, las 5 voces disparan: N5 (cabeza) 23822 writes, N1 11895, N2 8616, N3 3569, N4 3115. El patrón refleja observabilidad real: nariz 97% OBSERVED, muñecas medias, tobillos mayormente fuera de cuadro a 640x480.
2. **Causa raíz del fallo en vivo (dos bugs combinados):**
   a. `weaver_runtime.harmocap_manifest()` declaraba TODAS las features con rango (0,1), pero `verticality` es signada (-1,1) según `schema.FEATURE_RANGES` del productor. Datos vivos producen verticality negativa (el fixture two_persons nunca lo hizo, por eso T4.5 pasó): 3243 frames de la sesión real violaban el rango.
   b. `HarMoCAPDriver._emit` no atrapaba excepciones del consumidor: el raise de validación del engine mataba el thread del listener UDP. Sin listener, no hay más ingesta NI re-hello posible → gate "absent" permanente. Esto unifica todos los síntomas S13: crowd solo escribió en una ventana de 3 s (+157 a +160 s, antes de morir el thread), y las pruebas posteriores (ruta directa nariz, min_confidence=0, hold_then_reset) corrieron contra un source muerto.
3. **Fixes aplicados en harmonic-weaver (working tree, sin commit):** bounds verticality (-1,1) en el manifiesto del runtime + `_emit` atrapa excepciones del callback y las cuenta en `stats.callback_errors`. Tests de regresión en `tests/test_harmocap_driver.py` (TestCallbackResilience) y `tests/test_rehearsal_harness.py` (feature ranges). Suite: 61 passed + 4 subtests. Repro offline post-fix: 0 excepciones, 52291 instrument writes.
4. **Procesos huerfanos de S13 limpiados:** harmocap realtime (pid 897655, seguía grabando a /tmp 2h10m), weaver runtime (901237), shaper (888437). SIGTERM limpio, puertos 8765/8080 libres.

Observaciones para la escena (no bugs): foco saltó entre slots 0-4 por falsos positivos de YOLO en la sala (la escena solo mira slots 0-1); tobillos fuera de cuadro a 640x480 — considerar 720p o encuadre más amplio; aggregators con slots 0/1 solamente pierden al sujeto cuando cae en slot >= 2.

Pendientes sin cambios: lease recovery del engine (source absent no se recupera sin re-hello), torch cu126 en RTX 2060 (instalar cu124 o CPU), ensayo audible del shaper (A2 de la auditoría de Fable — S13 no lo cubrió porque las voces nunca dispararon).

## 2026-07-18 - S14b - Triage auditoría Fable + limpieza de stack

**Stack apagado:** se encontró un SuperCollider del beacon vivo (scsynth 867943 + sclang beacon.scd 868097, era lo que sonaba), más el launcher start-beacon.sh y webui.py. Todo SIGTERM limpio. Verificado: sin procesos beacon/shaper/weaver/harmocap, SuperCollider fuera de pipewire.

**Fixes S14 commiteados:** harmonic-weaver `b5b5221`, pusheado y verificado en ambos remotos (nicoechaniz + AlterMundi).

**Auditoría Fable ejecutada:**
- A4: beacon-spatial ahora tiene pushurl dual (nicoechaniz + AlterMundi). Espejo `AlterMundi/beacon-spatial` creado (público). Verificado por ls-remote: main `de2768c` y sensors `6c57986` presentes en AMBOS remotos — el riesgo de pérdida de datos queda cerrado.
- A5: digital-beacon limpio. PNGs de análisis (espectrogramas/waveforms de frogs, regenerables desde el WAV canónico en beacon-spatial) borrados; symlink roto `data/sources/2_Sesion_Minerval_extra.wav` (gitignored, apuntaba a ruta voice-analysis inexistente) eliminado. Working tree limpio; no hubo nada trackeado que commitear.
- A1, A2, A3, B6, B7, B9, C10 + lease recovery: cards F5-* creadas en triage en board `beacon-ecosystem-orch` (t_c0ede1e0, t_db173939, t_4beb6d46, t_b92791c3, t_e299befb, t_597f9f26, t_5f850e95, t_a86ca0f8).

**torch/CUDA:** downgrade a torch 2.6.0+cu124 en `.venv` (ultralytics 8.4.100 solo requiere torch>=1.8). Resultado de soaks GPU (YOLO26m-pose, track, imágenes random): 1 crash intermitente (illegal instruction, <6 min) de 3 corridas — 4 min con CUDA_LAUNCH_BLOCKING=1 PASS (4368 inf), 7 min async PASS (4466 inf). El crash NO es determinista: no es un build sin sm_75 (cu124 lo incluye y la mayoría de corridas pasa). Hipótesis revisada: driver 550.163.01 viejo o hardware marginal; no se descarta rareza bajo carga. Recomendación: correr el ensayo en vivo y observar; fallback CPU disponible; update de driver como mantenimiento separado.

**Pendiente para Nico:** re-ensayo en vivo (card F5-A2) — con los fixes, las voces del shaper deberían disparar; además cubre el ensayo audible (Fable A2).


## 2026-07-18 - S15 - start-live-stack.sh: el stack en vivo en un comando

Tras el apagon (sin perdida: todo estaba commiteado), se construyo el launcher que faltaba para el re-ensayo en vivo (F5-A2). harmonic-weaver `0f735db`, pusheado a nicoechaniz + AlterMundi.

- `scripts/start-live-stack.sh`: levanta beacon-spatial -> shaper -> weaver runtime -> push de escena -> HarMoCAP realtime (+ ECG sim opcional) con gates de readiness reales entre etapas (OSC hello contra el contrato vivo, HTTP API, TCP WS), bootstrap de venvs (uv sync para weaver, venv+pip -e para shaper), preflight de puertos, teardown en orden inverso ante Ctrl-C o muerte de cualquier componente, pidfile + `--stop <run-id|latest>` para corridas detached. Opciones documentadas en el header y `--help`.
- `rehearsal/push_scene.py`: CLI standalone para upsert/switch de escenas por Stage WS (reusa el StageClient del runner).
- `rehearsal/weaver_runtime.py`: nuevo arg `--lease-ms` (default 2500) cableado a los tres manifests de fuentes. El default en vivo es 300000 para que un dropout transitorio no trabe el gate en absent permanente (la recuperacion de lease del engine sigue abierta, card F5-ENG).

Smoke test E2E real (2 corridas): (1) GPU — stack completo arriba, escena event-demo activa, las 5 rutas del shaper dispararon con datos de camara reales (fix S14 confirmado en vivo), pero el crash intermitente CUDA (illegal instruction, RTX 2060 + driver 550) mato harmocap a los ~60s y el script bajo todo limpiamente, sin huerfanos. (2) `--harmocap-device cpu` (nueva opcion, CUDA_VISIBLE_DEVICES="" solo para ese proceso) — corrida sostenida 90s+, 26 writes a instrumentos en 78s, 520 frames grabados, cero crashes, `--stop` verificado con teardown completo.

La opcion `--harmocap-device cpu` queda como fallback operativo mientras el crash CUDA intermitente no se resuelva (hipotesis: driver 550.163.01 viejo; update de driver pendiente como mantenimiento separado).

Pendiente sin cambios: re-ensayo en vivo con Nico (F5-A2, ahora es un solo comando), ensayo audible del shaper, lease recovery del engine.

## 2026-07-18 - S6b - Autoauditoria H4 aplicada + hallazgos de campo de Nico integrados

Autoauditoria adversarial post-implementacion (agente independiente sobre el commit de H4): 1 hallazgo alto, 7 medios, 3 bajos. Todos los accionables aplicados:

- **A1 (alto)**: la rama "salida por borde" del matcher de reasociacion no gateaba distancia — cualquier entrada por el mismo borde a cualquier altura podia fusionarse con el slot ausente (el error exacto que la capa debia impedir). Fix: gate de distancia tambien en la rama edge + test de regresion que aisla el caso (A entra por arriba-izq, B por abajo-izq → slot nuevo).
- **M2**: gates y features de crowd median en coords anisotropicas (x/ancho): en 16:9 el gate x era ~1.78x mas permisivo. Fix: distancias isotropicas (aspect propagado a `SlotManager.update()` y `CrowdAggregator`).
- **M6**: `_exit_edge_of` aproximaba semiancho con sqrt(area)/2 (sesgo con bboxes de persona, altas). Fix: w/2, h/2 reales.
- **M1**: `model: auto` del tracker NO reusa features del detector con backend TensorRT — ultralytics degrada silenciosamente a descargar `yolo26n-cls.pt`. Fix: encoder ReID pineado explicito (mismo encoder en Mac .pt y 3090 .engine; verificado que reproduce los numeros de la eval).
- **M3**: el test de gating por borde pasaba aunque el mecanismo estuviera roto (el gate interior producia los mismos resultados). Fix: umbrales que aislan el mecanismo.
- **M4**: `config_hash` no cubria `reacquisition` ni `mode`. Fix: agregados al hash.
- **M5**: el receptor de referencia consumia `/crowd` sin gating de handshake ni contabilidad. Fix: gatea y cuenta; regla documentada en spec.
- **M7**: `CrowdAggregator` computaba flow/qom contra baselines fuera de ventana tras gaps. Fix: push-antes-de-leer + clear en escena vacia.
- B1/B2 documentados (ruido de qom con conteos cambiantes; semantica n_persons en docstring).

**Re-validacion post-fix** (tabla actualizada en `tracking_identity_eval.json`): (a) 55.7/56.3 → (b) 45.8/50.5 → (c) **14.3/10.4** slot-switches/min (221/653 rebinds). Las configs a y b REPRODUCEN exacto (banco estable); c empeoro levemente vs la corrida pre-fix (11.0/8.3) porque los gates estrictos rechazan reasociaciones que antes pasaban — parte de esas eran precisamente las fusiones A1/M2. Para musica, fusionar identidades es peor que separarlas: trade-off correcto. 55/55 tests.

**Integracion del merge con Nico**: el espejo AlterMundi traia 12 commits de Nico (ecosistema harmonic-weaver/shaper/beacon-spatial + ensayo fisico en vivo consumiendo HarMoCAP 1.1). Merge resuelto (BITACORA con doble numeracion S6 documentada; su realtime_metrics preservado como `realtime_metrics_nico_v4l2.json`). De su bitacora S14 salio un hallazgo que nos toca: `verticality` es el UNICO rango firmado (-1..1) y ningun fixture lo ejercitaba — su manifiesto con bounds (0,1) paso todos los tests y exploto con datos vivos. Fix nuestro: fase C2 de inversion en la sesion sintetica (min verticality -0.97, con assert de invariante en el generador), nota en spec, kit regenerado. Coordinacion pendiente cuando vuelva Mariano: el salto a contrato 1.2 gatea el stream para el kit 1.1 que Nico usa en vivo — hay que sincronizar actualizacion de kit + manifiesto del driver harmocap en harmonic-weaver.

Addendum S6b — descomposicion del overhead del modo grupo (video 1, capa 3 activa; `reports/20260717_e71e14a/group_mode_overhead.json`):

| Variante | IDs unicos | sw/min | fps 3090 |
|---|---|---|---|
| ReID + GMC (config actual) | 214 | **14.3** | 33.5 |
| ReID, sin GMC | 262 | 16.5 | 46.0 |
| sin ReID, con GMC | 209 | 18.8 | 63.9 |
| sin ReID, sin GMC | 226 | 17.7 | **135.0** |

Lectura: la REASOCIACION DE SLOTS (capa 3) hace el trabajo pesado — sin ReID ni GMC igual da 17.7 sw/min (vs 55.7 del baseline ByteTrack). ReID+GMC compran la mejora marginal 17.7→14.3 a costo ~4x de fps. Implicancia para Mac/mps: `with_reid: False` + `gmc_method: none` es un modo grupo viable (~4x mas barato, identidad casi igual). El bench es cámara en mano; con cámara fija el aporte de GMC deberia caer. Config default se mantiene (máxima identidad en 3090, 33 fps = tiempo real); el knob queda documentado para decision del usuario.

## 2026-07-19 - S16 - Shaper silencioso: causa raíz resuelta (JACK vs ALSA plugin)

El shaper nunca sonó en ningún ensayo en vivo (S13, S14, corridas posteriores). Diagnóstico por capas con evidencia:

1. Voces activas con freq/gain correctos, master 0.8, stream linkeado a la R24, sin errores en log. Silencio.
2. Tono pw-cat directo al sink R24: AUDIBLE. Cadena PipeWire->R24->auris OK.
3. Recorder tap dentro del callback: rms=0.32, cadencia real-time — el DSP genera señal. Silencio igual.
4. Historial: sesión 20260718_113431 quedó sin resolver en el mismo punto; pw-top mostraba el stream python idle (rate ---).
5. aplay -D default (mismo PCM ALSA->PipeWire que usa PortAudio): AUDIBLE. aplay -M (mmap): también reproduce sin error.
6. Hipótesis de Nico (correcta): "usabas jack sobre pipewire". PortAudio del venv expone host API JACK bajo pw-jack. Prueba con engine directo: device 'R24 Analog Stereo' + sr 48000 (JACK impone el rate del server, -9997 con otro): SONO.

Fixes commiteados: harmonic-shaper (audio_engine adopta el sample rate del server JACK al detectar hostapi JACK; 64/64 tests) + harmonic-weaver start-live-stack.sh (shaper bajo pw-jack con --device "R24 Analog Stereo", opcion --shaper-device y env SHAPER_DEVICE). Verificación E2E en vivo: nota MIDI -> voz 4 activa 161.6 Hz -> AUDIBLE por la R24. Confirmado por Nico.

Gap de diseño descubierto en el camino (pendiente): las rutas del weaver solo escriben /digital/harmonic/{n}/gain — nunca activan la voz ni setean frecuencia, y el motor solo renderiza voces activas. Para que el cuerpo suene por el weaver hace falta voice_on en el surface nativo o auto-activación en el handler de gain (freq = n*f1). También: nota MIDI enviada por Midi Through quedo sonando sin parar tras note_off (investigar release path del NativeMidiNoteSource; panic por API la libero).

Quirks R24 documentados en MEMORY.md: tras boot unclean, wireplumber no perfila la R24 (fix: restart wireplumber + re-link manual de SuperCollider:out_*).

## 2026-07-19 - S17 - Playable harmonic-series keyboard banks

The native keyboard mapping was corrected from the legacy NaturalHarmony hybrid mapper, which selected a 12-key harmonic prototype and then octave-adapted it toward 12-TET. That behavior was incompatible with a directly playable harmonic series.

Physical calibration captured from the keyboard MIDI port:

| Transpose position | Lowest physical key | Next key |
|---|---:|---:|
| Minimum | MIDI 24 | MIDI 25 |
| Maximum | MIDI 72 | MIDI 73 |

`harmonic-shaper` now defaults to configured `sequential_banks`: MIDI `24..55` maps momentarily to `n=1..32`, and MIDI `72..103` maps to the same partials as toggle/sustain. Every selected partial is exactly `f1*n`; no 12-TET or octave adaptation remains in this mode. Notes outside the configured banks are ignored to prevent intermediate transpose positions from silently reverting to a tempered behavior. The bank starts and size are generic config/CLI values, not a device-name dependency; the former mapper remains available only as explicit `legacy_hybrid` compatibility mode.

Verification: 70 shaper tests pass, including new mapping/lifecycle/safety coverage. Live MIDI E2E through the running JACK/R24 shaper passed: MIDI 24 started `n=1 @ 40.4 Hz` and released on note-off; MIDI 72 started `n=1 @ 40.4 Hz`, survived its note-off, and released on the second press. Reference: `harmonic-shaper/docs/NATIVE_MIDI_HARMONIC_BANKS.md`.

## 2026-07-19 - S18 - Live HarMoCAP to Harmonic Shaper integration

The live integration path was exercised from a V4L2 camera through HarMoCAP OSC, harmonic-weaver, and the audible JACK/R24 Shaper. The promoted ft2 engine and fallback checkpoint were not present locally, so the launcher now accepts an explicit `--harmocap-checkpoint` for a single run without changing `configs/model.yaml`. The validated live run used the locally available `yolo26m-pose.pt`; it is integration evidence only, not a replacement evaluation for ft2.

Evidence before the runtime stopped: 827 recorded HarMoCAP frames, 2,923 instrument-route records, active Shaper partials at exact `f1*n`, and direct user confirmation that movement produced a musical audible response. The scripted hardware-free rehearsal also passed completely (`t45-20260719T092417Z`), including focused-subject partials `1..5`, panic release/rearm, and finite non-silent audio evidence.

The live camera process later stopped on `RuntimeError: CUDA error: an illegal memory access was encountered` in Ultralytics BoT-SORT ReID. This is an open stability failure in the CUDA/ReID path, separate from the validated OSC-to-audio control path. No claim of sustained GPU stability is made.
