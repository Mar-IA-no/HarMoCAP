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
