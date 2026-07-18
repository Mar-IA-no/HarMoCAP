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
