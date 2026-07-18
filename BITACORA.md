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
