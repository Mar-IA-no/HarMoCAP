# Biblioteca - HarMoCAP

> Toda investigacion bibliografica, consulta a modelos, output de subagentes o paper descargado se archiva aqui.

## Convencion

Un subdirectorio por tema de investigacion. Cada tema puede contener:

```text
Biblioteca/<tema>/
├── README.md
├── SINTESIS.md
├── INFORME_CRUZADO.md
├── BIBLIOGRAFIA.md
├── reportes_agentes/
└── papers/
```

Los reportes crudos de subagentes se conservan por separado. Los papers pesados suelen quedar excluidos por `.gitignore` y se registran en un `MANIFEST.md`.

## Indice de temas

| Tema | Fecha inicio | Estado | Resumen |
|---|---|---|---|
| [rearquitectura-ecosistema-beacon](rearquitectura-ecosistema-beacon/README.md) | 2026-07-18 | en_curso | Relevamiento de 6 proyectos (HarMoCAP como referencia + NaturalHarmony, beacon-spatial, digital-beacon, tines, cymatic-control) y propuesta de arquitectura objetivo: dashboard de patcheo fuentes→instrumentos. GO del usuario 2026-07-18, en ejecucion orquestada. |
| [beacon-ecosystem-orchestration](beacon-ecosystem-orchestration/README.md) | 2026-07-18 | en_curso | Ejecucion orquestada del plan de re-arquitectura: CompAII despacha via ia-bridge con auditoria por build, Codex Sol en ruta critica. Kanban `beacon-ecosystem-orch` como ledger. GOALS.md es el documento autoritativo. |
| [crowd-counting-densidad](crowd-counting-densidad/README.md) | 2026-07-20 | cerrado | Estado del arte de conteo de multitud por mapas de densidad en tiempo real. Candidato ZIP (MIT, MobileNetV4, pesos QNRF/NWPU); riesgo dominante = resolución; arquitectura de régimen doble deteccion/densidad; flujo por NVOFA. |
| [arquitectura-harmocap-h4](arquitectura-harmocap-h4/arquitectura-harmocap-h4.md) | 2026-07-19 | cerrado | Informe narrado de la arquitectura al cierre del hito 4: capas, trackers (ByteTrack, BoT-SORT+ReID), capa de reasociacion de slots, modos grupo/masa, contrato 1.2, evidencia comparativa y limites declarados. |

## Estados validos

- `en_curso`
- `cerrado`
- `pausado`
- `descartado`
