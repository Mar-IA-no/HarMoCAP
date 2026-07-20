# AGENTS.md - HarMoCAP

> Documento operativo para todo agente que trabaje en este proyecto.

## Que es este proyecto

HarMoCAP desarrolla un sistema de pose estimation y tracking corporal basado inicialmente en Ultralytics YOLO26m-pose. El primer hito usa COCO8-pose para validar el workflow de ML; luego el proyecto evaluara datasets mas grandes y diversos, con foco inicial en Roboflow y Kaggle. El objetivo operativo es trackear en tiempo real el movimiento de una o varias personas y exponer sus variables corporales a un modulador que controle en tiempo real la armonia utilizada por Harmonic Beacon.

Tipo: desarrollo de software.

El sistema se construye por capas separables:

- percepcion: deteccion de persona y keypoints;
- temporalidad: tracking, identidad, suavizado y manejo de oclusiones;
- representacion: variables de movimiento y estado corporal;
- modulacion: mapeo explicito, auditable y de baja latencia hacia Harmonic Beacon.

La utilidad ingenieril de una capa no constituye por si misma una validacion de las hipotesis teoricas de Harmonic Information Theory o Harmonic Beacon.

## Lectura obligatoria al iniciar una sesion

1. Este archivo (`AGENTS.md`).
2. Las ultimas 2-3 entradas de `BITACORA.md`.
3. `Biblioteca/INDEX.md`.
4. `/mnt/m2-1TB/MENSAJES_RECURSIVOS.md` y el mapa colectivo cuando el trabajo cruce proyectos.

`PENDIENTES.md` pertenece exclusivamente al usuario y no se lee ni modifica salvo pedido directo.

## Directivas de maximo nivel

Las directivas universales viven en la memoria persistente de cada agente. Para Codex, la ubicacion vigente es `/root/.codex/memories/mariano_global_directives_2026-07-09.md`; los agentes nuevos deben autoanotarselas siguiendo la Fase 3 de `mandinga_init_workspace`.

Antes de implementar cambios significativos se documenta un plan y se espera aprobacion del usuario. Los claims numericos, metodologicos y de rendimiento deben poder rastrearse a un artefacto. Las observaciones se separan de las hipotesis, y las decisiones GO/NO-GO corresponden al usuario.

## Roles activos

- Claude: puede actuar como implementador o auditor segun la asignacion casuistica del usuario.
- Codex: puede actuar como implementador o auditor segun la asignacion casuistica del usuario.

No hay ownership permanente por agente. La tarea o el usuario define el rol activo, el archivo canonico y quien audita. La bitacora se actualiza por el agente que tenga el rol auditor o por instruccion explicita del usuario.

## Comunicacion entre roles

- `NOTAS_CLAUDE-CODEX.md`: canal de Claude para Codex.
- `NOTAS_CODEX-CLAUDE.md`: canal de Codex para Claude.
- `BITACORA.md`: registro cronologico de decisiones y estados observados.
- `PENDIENTES.md`: archivo exclusivo del usuario.

## Flujo Git y espejos

El repositorio principal es `nicoechaniz/HarMoCAP`, remoto local `origin`. El espejo de la organizacion es `AlterMundi/HarMoCAP`, remoto local `altermundi`.

`origin` tiene dos `pushurl` (nicoechaniz primero, AlterMundi despues): el flujo normal `git push` publica ambos. Tras cada push se verifica que ambos remotos queden en el mismo commit; si el push a AlterMundi rebota porque la linea de Mariano avanzo primero, se mergea `altermundi/main` antes de reintentar (verificado 2026-07-19 que los trabajos no se pisan; ante conflicto en artefactos de `reports/`, preservar ambas versiones como archivos separados).

## Fuentes conceptuales y tecnicas

- Documentacion de pose Ultralytics: `https://docs.ultralytics.com/tasks/pose#train`.
- Harmonic Information Theory: `/mnt/m2-1TB/editorial-altermundi/harmonic-information-theory/Hamonic_Information_Theory_Foundations_ES.md`, especialmente el capitulo 12.
- Marco conceptual Beacon-HIT: `/mnt/m2-1TB/editorial-altermundi/beacon-pmp-wellness-product/documentos/05_marco_conceptual_beacon_hit/MARCO_CONCEPTUAL_BEACON_HIT.md`.
- Protocolo operativo Beacon: `/mnt/m2-1TB/editorial-altermundi/beacon-pmp-wellness-product/documentos/03_protocolo_operativo_experiencia_beacon/PROTOCOLO_OPERATIVO_EXPERIENCIA_BEACON.md`.

El sistema de captura corporal no debe convertirse automaticamente en una afirmacion clinica ni en una promesa de efecto armonico. Cada transformacion entre movimiento y parametros musicales debe quedar documentada como decision de diseno y evaluada por separado.

## Catalogo editorial padre

`/mnt/m2-1TB/editorial-altermundi/AGENTS.md`

Las directivas del catalogo padre se heredan junto con el contrato de memoria colectiva de `/mnt/m2-1TB/AGENTS.md`.

## Mensajes recursivos (estructura multi-agente)

<!-- puntero-mensajes-recursivos: no duplicar; canal en /mnt/m2-1TB/MENSAJES_RECURSIVOS.md -->
Este proyecto forma parte de la estructura multi-agente con raiz en `/mnt/m2-1TB`. Su canal de directivas es `/mnt/m2-1TB/MENSAJES_RECURSIVOS.md`, append-only y administrado solo por los agentes raiz.

Al arrancar una sesion, se leen los mensajes posteriores al ultimo integrado, se interpretan segun este proyecto y se registra en `BITACORA.md` la forma `mensaje recursivo NNN integrado`.
