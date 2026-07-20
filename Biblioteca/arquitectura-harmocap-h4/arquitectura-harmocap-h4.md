# HarMoCAP: arquitectura del sistema y del problema de la identidad

> **Qué es este documento.** Informe narrado del estado del sistema (redactado 2026-07-19 al cierre del hito 4; actualizado 2026-07-20 con la validación sobre banco ampliado, la corrida extremo a extremo y el cierre del hito 5): la arquitectura por capas, el funcionamiento de los trackers, la capa propia de reasociación de identidad, los dos modos operativos, el contrato con el consumidor y las direcciones de trabajo abiertas. No es especificación normativa — esa vive en `schemas/osc_contract.v1.json` y `docs/INTERFACE_SPEC.md` — ni bitácora de decisiones — esa es `BITACORA.md` (S4-S6b). Es la explicación de conjunto que ninguno de esos documentos da por separado. Todo número citado se traza a un artefacto en `reports/20260717_e71e14a/` o a los logs de las corridas de prueba.

## 1. El problema que organiza el diseño

Un sistema que traduce movimiento corporal en modulación sonora tiene un punto de falla que no es la precisión de los keypoints sino la **continuidad de la identidad**. Cuando dos personas bailan y una ocluye a la otra, o cuando alguien sale un instante de cuadro, el detector las recupera sin problema — pero como *personas nuevas*. Para un mapeo musical eso es una discontinuidad falsa: la voz que seguía a esa persona se corta y renace de cero, sin que en la escena haya pasado nada. La observación de campo que fijó el rumbo del hito 4 fue exactamente esa: la detección era buena y el tracking no alcanzaba.

El diseño responde con una distinción que ordena todo lo demás: **el track no es la persona**. El track es lo que el tracker logra sostener — una hipótesis geométrica o de apariencia con vida útil limitada. La persona, para el sistema, es el **slot**: una de ocho identidades estables (0-7) que el consumidor recibe por el wire y a la que asocia una voz. Entre track y slot media una capa propia, auditable, cuyos umbrales viven en configuración y no en código. Esa mediación es la contribución arquitectónica central del hito.

## 2. La arquitectura por capas

```
cámara / video ──► capture ──► percepción ──► identidad ──► suavizado ──► features ──► interfaz OSC ──► consumidor
                   (último     (YOLO26-pose   (8 slots +    (One-Euro     (21 vars      (contrato 1.2)
                    frame)      + tracker)     reasociación)  causal)       + crowd)
```

| Capa | Módulo | Responsabilidad | Frontera |
|---|---|---|---|
| Captura | `capture.py` | hilo lector que retiene solo el último frame; reloj monótono | aísla la latencia de I/O |
| Percepción | `perception.py` | detección + tracking; coords isotrópicas | único módulo que importa `ultralytics` |
| Identidad | `identity.py` | slots estables, foco, **reasociación** | track_id entra, slot_id sale |
| Suavizado | `smoothing.py` | One-Euro time-aware; estados observed→held→invalid | por slot |
| Representación | `features.py`, `crowd.py` | 21 variables por persona + 8 agregados de multitud | causal estricto |
| Interfaz | `interface/` | codec, emisor UDP, grabación, replay | el contrato es la única superficie pública |

Dos invariantes atraviesan todas las capas. **Causalidad**: ningún cálculo usa datos futuros — filtros one-sided, ventanas trailing, derivadas hacia atrás — porque el sistema es de tiempo real y una feature que "mira adelante" en grabación mentiría en vivo. **Isotropía**: toda coordenada se normaliza por la altura del frame (x ∈ [0, ancho/alto], y ∈ [0,1]), de modo que distancias y ángulos no se distorsionan con el aspect ratio; la autoauditoría del hito encontró — y corrigió — los dos lugares donde este invariante se había roto (gates del matcher y agregados de multitud, BITACORA S6b).

## 3. Cómo trabaja cada tracker

### 3.1 ByteTrack: geometría con memoria corta

ByteTrack asocia por movimiento puro. Cada track vivo mantiene un filtro de Kalman que predice su bbox en el frame siguiente; la asociación se resuelve por IoU contra esas predicciones. Su aporte distintivo es la **doble pasada**: primero las detecciones confiables (conf ≥ 0.25), después los tracks huérfanos contra las detecciones de baja confianza (0.1-0.25). Esa segunda pasada es la razón por la que el sistema infiere con conf 0.05: una persona semi-ocluida detectada débilmente mantiene su track vivo en vez de romperlo (−16 % de churn de IDs medido en el barrido de hiperparámetros, `sweep/`).

Sus límites son estructurales, no de tuning. El buffer de memoria (~1 s por defecto) es más corto que una oclusión de baile; la predicción de Kalman diverge en cuanto la persona cambia de dirección detrás de la que la tapa; y una salida de cuadro no deja ninguna bbox contra la cual computar IoU al regreso. ByteTrack no tiene concepto de "la misma persona" — solo de rectángulos que se mueven suave.

### 3.2 BoT-SORT + ReID: apariencia y compensación de cámara

El modo grupo reemplaza el tracker por BoT-SORT con dos agregados:

- **ReID**: cada detección se recorta y pasa por un encoder (`yolo26n-cls.pt`, pineado explícitamente para que Mac y 3090 usen el mismo — el `auto` de ultralytics degradaba en silencio con backend TensorRT) que produce un embedding de apariencia. La asociación combina IoU y distancia coseno; un track ocluido cuya geometría ya no alcanza puede recuperarse porque su apariencia reaparece. `appearance_thresh 0.8` mantiene el criterio conservador: solo similitudes altas fusionan.
- **GMC** (`sparseOptFlow`): estima el movimiento de la cámara entre frames y corrige las predicciones antes de asociar, para que un paneo no rompa todos los IoU a la vez. Es una pieza para cámara en mano; en instalación con cámara fija se apaga (`gmc_method: none`).

`track_buffer 120` (~4 s) le da tiempo a la apariencia de actuar. El costo del conjunto es la contrapartida: el trade-off exacto está medido en §5.

El techo de ReID también está declarado: el encoder es un clasificador genérico, no un modelo de re-identificación entrenado sobre personas. En multitud de vestimenta uniforme, la apariencia deja de discriminar. La capa siguiente existe, en parte, para no depender de ella.

### 3.3 La reasociación de slots: la capa propia

La capa 3 opera donde los trackers ya fallaron: un track murió y su persona reaparece con track_id nuevo. En lugar de apariencia usa tres evidencias geométricas, cada una con su *gate* — umbral de aceptación, término que se conserva en todo el proyecto por su uso en la configuración — en `configs/identity.yaml → reacquisition`:

| Evidencia | Mecanismo | Gate |
|---|---|---|
| posición | predicción (último centro + velocidad EMA × Δt) con incertidumbre creciente | `0.35 + 0.15·Δt` (fracción del alto) |
| tamaño | ratio de áreas entre la bbox perdida y la candidata | ≤ 1.8 |
| borde de salida | si la bbox tocaba un borde al perderse, la reaparición debe ocurrir cerca de **ese** borde y cerca de la última posición | ≤ 0.30 al borde, + gate de posición |

El ciclo de vida del slot hace de sustrato: al perder su track, el slot no se libera sino que atraviesa `OCCLUDED` (gracia de oclusión) y `RELEASING` (ventana de espera) antes de emitir tombstones y quedar libre. Durante esa ventana, todo track nuevo se evalúa contra todos los slots ausentes **antes** de recibir un slot libre — el orden importa: si la asignación libre corriera primero, el track recién nacido ocuparía un slot vacío y la reasociación llegaría tarde. Los pares que pasan los gates se resuelven por asignación greedy determinista (distancia, con desempate total por slot y track). El ganador recupera su slot_id: para el consumidor, la persona nunca dejó de ser quien era. Si el salto de posición supera el umbral de teleport (0.25), el suavizador y los buffers de features se resetean — las muestras previas a la oclusión producirían derivadas espurias — pero la identidad se conserva.

La regla de diseño que gobierna los umbrales merece enunciarse porque no es simétrica: **fusionar dos identidades es peor que separarlas**. Un slot que salta de una persona a otra inyecta al mapeo una discontinuidad disfrazada de continuidad; un slot nuevo solo reinicia una voz. Los gates parten conservadores por eso, y el hallazgo más serio de la autoauditoría (A1, BITACORA S6b) fue precisamente un camino — la rama de salida por borde — que carecía de gate de distancia y habilitaba la fusión que la capa debía impedir. La corrección estricta costó métrica bruta (14.3 vs 11.0 switches/min pre-fix) y ese costo es correcto: parte de lo que la versión permisiva "recuperaba" eran fusiones.

## 4. Los dos modos: perfiles, no ramas

Las dos necesidades operativas — grupo chico con identidad sagrada, masa donde importa el recall — se resuelven como perfiles de configuración (`configs/modes/`) que sobreescriben modelo, tracker e identidad sobre el mismo pipeline. No hay bifurcación de código; el `config_hash` que viaja en el handshake refleja el modo y lo vuelve trazable.

| | grupo (default) | masa |
|---|---|---|
| resolución de inferencia | 640 | 1280 (engine dinámico) |
| tracker | BoT-SORT + ReID | ByteTrack |
| reasociación de slots | activa | inactiva |
| qué protege | la identidad de ≤8 personas | el conteo y los agregados |

En ambos modos se emiten los 8 slots **y** el mensaje `/crowd` (contrato 1.2): ocho agregados por frame calculados sobre *todas* las detecciones crudas — incluidas las que no llegan a slot — porque en masa el recall es el dato. `crowd_count` cuenta detecciones; `n_persons` de `/meta` cuenta slots: la distinción está en el contrato porque confundirlas es el error natural de un consumidor.

## 5. La evidencia

La validación comparativa (`scripts/eval_tracking.py`, resultados en `tracking_identity_eval.json`) usa dos videos de baile con oclusiones y cruces reales. La métrica principal — slot-switches por minuto: cuántas veces un slot se reinicia desde cero — es un proxy sin ground truth: no distingue un switch legítimo de uno espurio, y por eso sirve para comparar configuraciones sobre el mismo material, no como medida absoluta de calidad.

| Configuración | IDs únicos (v1 / v2) | switches/min (v1 / v2) | fps proceso (RTX 3090) |
|---|---|---|---|
| (a) ByteTrack | 255 / 850 | 55.7 / 56.3 | 123-136 |
| (b) BoT-SORT + ReID, buffer 120 | 214 / 849 | 45.8 / 50.5 | 30-33 |
| (c) (b) + reasociación de slots | 214 / 849 | **14.3 / 10.4** | 30-33 |

La reducción es monótona y el grueso lo aporta la capa 3. La descomposición del overhead (`group_mode_overhead.json`, video 1, capa 3 siempre activa) precisa dónde está el costo y dónde el beneficio:

| Variante | switches/min | fps |
|---|---|---|
| ReID + GMC (config actual) | 14.3 | 33.5 |
| ReID, sin GMC | 16.5 | 46.0 |
| sin ReID, con GMC | 18.8 | 63.9 |
| sin ReID, sin GMC | 17.7 | 135.0 |

Dos lecturas salen de esa tabla. Primero: la reasociación geométrica sola resuelve la mayoría de las roturas (55.7 → 17.7) a costo casi nulo — en baile, la persona suele reaparecer cerca de donde estaba o por donde salió. Segundo: ReID y GMC compran el margen restante (17.7 → 14.3) — los cruces largos donde dos candidatos plausibles compiten y solo la apariencia desambigua — a un costo de ~4× en throughput. En la 3090 ese costo cabe (33 fps sigue siendo tiempo real a 30); en hardware sin CUDA la variante sin ReID ni GMC es el modo grupo recomendado. El banco es cámara en mano; con cámara fija el aporte de GMC debería caer, y esa verificación queda abierta. La inspección visual del caso señalado en campo — dos personas cruzándose — está disponible como renders comparados con slot-id coloreado en `Biblioteca/test/two_slots_render/`.

### 5.1 Banco ampliado y corrida extremo a extremo

La validación se extendió al conjunto completo de material (`Biblioteca/videos_people_dancing`: cinco videos de baile con dos a ocho personas, dos videos de pogo con multitud densa), en tres pasadas complementarias cuyos artefactos quedan como renders comparables: identidad (`videos_people_dancing_slots/`, cada video con tracker anterior y con las tres capas) y modos (`videos_people_dancing_modos/`, cada video en grupo y en masa, este último con los agregados de multitud sobrepuestos en el cuadro).

La tercera pasada atraviesa el sistema entero hasta el consumidor: el productor emitiendo por UDP y el receptor del kit — Python del sistema, aislado, sin acceso al repositorio — decodificando el contrato 1.2 completo.

| | grupo (baile, 30 s) | masa (pogo, 30 s) |
|---|---|---|
| backend | engine dinámico, 640 | mismo engine, 1280 |
| bundles emitidos → recibidos | 6971 → 6971 | 2295 → 2295 |
| perdidos / gateados | 0 / 0 | 0 / 0 |
| latencia software p50 / p95 / p99 (ms) | 31.2 / 55.7 / 67.2 | 9.9 / 12.7 / 13.7 |
| jitter p50 / p99 (ms) | 1.9 / 27.1 | 0.2 / 2.1 |
| ocupación observada | 6 slots (mediana), picos de 8 | crowd_count mediana 2, pico 18 |

Tres hechos que la corrida vuelve visibles. El **engine dinámico** cumple lo que prometía: una misma sesión sirvió 640 y 1280 sin recompilar ni degradar al checkpoint PyTorch — el modo masa habría caído en silencio con el engine estático anterior. La **inversión de latencia entre modos** es contraintuitiva y real: el modo masa a 1280 resulta más barato que el modo grupo a 640, porque el costo dominante no es la resolución de inferencia sino la apariencia y la compensación de cámara; el modo grupo sigue dentro de los umbrales candidatos (40/60/90 ms) pero su jitter en la cola alta (27 ms en p99) marca el límite del margen disponible. Y el conteo de multitud bajo en el clip de pogo tiene explicación de encuadre antes que de modelo: los primeros treinta segundos son planos cortos, no la toma amplia; el render completo del mismo video muestra el conteo siguiendo la masa cuando el plano abre. Esa distinción importa porque un agregado de multitud mide lo que la cámara muestra, no lo que hay en el lugar.

## 6. La frontera: el contrato como única superficie

Todo lo anterior queda detrás de una sola superficie pública: el stream OSC/UDP versionado por `contract_id` (hash del manifiesto machine-readable). Un bundle atómico por persona por frame (≤1200 B: 17 keypoints con estados, 21 features con estados, bbox), un bundle `/crowd`, handshake `/hello`+`/calibration` con gating, y un canal de control entrante para elegir el foco. El consumidor desarrolla contra un kit portable de stdlib pura — receptor de referencia, replay de sesiones grabadas, fixtures que ejercitan cada camino del contrato, incluido el único rango firmado (`verticality`, -1..1), cuya ausencia en los fixtures originales produjo un fallo real en el primer consumidor: sus bounds (0,1) pasaron todos los tests y rompieron con datos vivos. El fixture de inversión que hoy llega a -0.97 existe por ese episodio.

El cambio de contract_id entre versiones es deliberado: un kit viejo *gatea* (ignora) un stream nuevo en vez de malinterpretarlo. La migración 1.1 → 1.2 del consumidor en producción es el punto de sincronización vivo entre las dos líneas de desarrollo, que comparten repositorio y avanzan en paralelo sin superposición de archivos verificada.

## 7. Lo que el sistema no resuelve

El resto queda a la vista. La identidad por apariencia tiene techo con vestimenta uniforme y el encoder actual no es un ReID especializado. La métrica de identidad es un proxy: una evaluación con ground truth anotado daría la medida absoluta que este banco no puede dar. Los umbrales de reasociación están calibrados sobre dos videos de baile y una regla de asimetría — el ajuste fino sobre material propio de instalación (cámara fija, luz controlada) está por hacerse. La capa de percepción entrega, en el mejor caso, keypoints 2D frontales: fuera de su dominio operativo (vista lateral fuerte, cuerpo chico en cuadro) las features degradan sin aviso, y esa degradación es hoy responsabilidad del operador, no del sistema. Y el tempo, incorporado al contrato en el hito 5, se declara solo en una fracción de los cuadros: el pulso corporal existe cuando el movimiento es periódico y no antes, de modo que el consumidor debe tratarlo como señal intermitente y gatearla por su confianza.

## 8. Direcciones abiertas

Las líneas de trabajo que siguen se ordenan por la relación entre lo que cuestan y lo que destraban, no por su ambición. Ninguna está comprometida: son el mapa de decisiones disponible.

| Dirección | Qué destraba | Estado (2026-07-20) |
|---|---|---|
| Features de tempo y fase del movimiento | periodicidad corporal en el contrato: sincronizar armonía al pulso real | **hecha** (contrato 1.3) |
| Conteo de masa por mapas de densidad | ve a la gente que la detección no ve — el público entero, no solo quien baila | **verificada, pendiente de integrar** |
| Ground truth anotado sobre clips cortos | convierte el proxy en medida absoluta (IDF1, ID-switches) y habilita ajustar con fundamento umbrales hoy fijados por criterio conservador | abierta, escala baja |
| Encoder de re-identificación dedicado | ataca el techo declarado de la apariencia en los cruces largos | abierta, depende de la anterior |
| Conmutación automática de modo | opera la instalación sin intervención, por histéresis sobre el conteo de multitud | abierta, escala baja |
| Medición con estímulo físico | firma el umbral de latencia extremo a extremo que hoy sigue abierto | abierta, requiere cámara real |
| Ajuste fino sobre el dominio de instalación | modelo y umbrales sobre la escena efectiva en vez de material de terceros | abierta, requiere material propio |

Las dos primeras se ejecutaron y conviene registrar qué enseñaron, porque ambas corrigieron la expectativa con que se habían planteado.

El **tempo** resultó menos una cuestión de algoritmo que de elección de señal. La variable de energía que el sistema ya emitía era inservible como entrada: viaja recortada y promediada sobre una ventana del orden del período que se quiere medir, de modo que su propio filtro borraba la banda de interés. Lo que lleva el pulso es el rebote vertical de la cadera, y medirlo contra el tempo de la música del propio video devolvió la razón musical correcta donde la velocidad global del cuerpo no lo hacía. La validación externa — cinco personas trackeadas por separado convergiendo a la mitad exacta del pulso musical — es la primera referencia verdadera que el proyecto pudo usar. El alcance también quedó medido: la señal se declara en una fracción pequeña de los cuadros, y esa intermitencia es parte del contrato, no un defecto a esconder.

La **densidad** enseñó algo sobre el método de validación antes que sobre el modelo. La comparación automática contra la rama de detección arrojó desacuerdos de hasta treinta veces y correlación nula, lo que leído literalmente cerraba la puerta. La inspección visual de los mapas mostró lo contrario: el modelo localiza cabezas individuales y encuentra al público sentado que la detección ignora por completo. El error estaba en la premisa — usar como referencia justamente aquello cuya ceguera se quería medir. Queda por decidir, y es una decisión de diseño y no técnica, si la masa que interesa es toda la gente en cuadro o solo quien ocupa la pista.

Instrumentar el tempo produjo además un hallazgo sobre lo ya entregado: tres de las features agregadas viajaban marcadas como inválidas en el noventa por ciento de los cuadros de video real, porque exigían los diecisiete keypoints y los faciales se pierden con frecuencia en escena de baile. Eran features que ya se calculaban sobre el subconjunto disponible, de modo que la regla estricta de validez no correspondía a cómo estaban construidas. La lección es de arquitectura antes que de código: **una regla de validez uniforme sobre features heterogéneas silencia justamente a las más robustas**, y conviene que cada feature declare qué necesita para ser creíble.

---

*Fuentes: `BITACORA.md` S4-S7 · `reports/20260717_e71e14a/{tracking_identity_eval,group_mode_overhead,engine_build,realtime_metrics}.json` · `configs/{model,identity,tracker_group}.yaml`, `configs/modes/` · `docs/INTERFACE_SPEC.md` · `scripts/{eval_tracking,render_slots,render_modes}.py` · sesiones `outputs/sessions/e2e_{group,crowd}.jsonl` · `reports/20260717_e71e14a/{tempo_validation,density_gate}.json` · `Biblioteca/{crowd-counting-densidad,densidad_overlay}/` · commits `1c18a1a`, `536a264`, `c6eea53`, `9dd0687`, `6b0d54e`.*
