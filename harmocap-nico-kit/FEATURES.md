# FEATURES — definición y fórmula de cada variable de movimiento (v1)

> Fuente canónica de las **decisiones de diseño** de la capa de representación
> (AGENTS.md: cada transformación movimiento→parámetro es una decisión de
> diseño auditable). Implementación: `src/harmocap/features.py`. Cambiar una
> fórmula/ventana/escala **bumpea `feature_set_version`** aunque no cambien los
> addresses OSC.

## Principios

1. **Causalidad estricta:** ningún cómputo usa frames futuros. Derivadas con
   estimador retrospectivo (diferencias causales trailing) usando **Δt real de
   `captured_at`** — el pipeline descarta frames y el muestreo es irregular;
   usar índices de frame sesgaría las derivadas justo bajo carga.
2. **Ventanas en milisegundos**, no en frames: `velocity 120 ms · accel 200 ms ·
   jerk 300 ms · qom 400 ms` (configurable en `configs/features.yaml`).
3. **Normalización espacial:** longitudes ÷ **altura de torso** (distancia
   punto-medio-hombros ↔ punto-medio-caderas, en coords isotrópicas); áreas ÷
   **torso²**. Posición referida al centro de caderas. Esto da invarianza a la
   escala de la persona y a su distancia/posición en el frame (verificada por
   tests).
4. **Rango acotado:** toda feature no naturalmente acotada se lleva a [0,1] con
   un divisor de calibración + clipping. La ausencia es `null` + estado
   `invalid` (jamás NaN); en el wire el sentinel es 0.0 + `feat_state=2`.
5. **Prioridad posturales > cinemáticas** (Poyo-Solanas 2020: 84 % vs 61 % de
   poder predictivo emocional; ver pack de investigación, CROSS_REPORT §D.3).

## Dominio operativo

Cámara **fija**, **~frontal**, cuerpo suficientemente visible (torso ≥ ~15 %
del alto del frame). Fuera de eso las features degradan sin aviso del modelo
(el 2D no es invariante al punto de vista; pack §D.5). Con vista lateral
fuerte, `symmetry`, `contraction` y los ángulos pierden sentido.

## Calibración

Perfil **fijo por sesión** por generaciones (nunca min/max adaptativo online,
que cambiaría el significado de una misma entrada a mitad de sesión):

- Generación 1 = **fallback fijo** (valores por defecto documentados en
  `configs/features.yaml`), estado `calibrating` (~5 s).
- Al congelar: generación 2 con `torso_height_norm` = mediana medida; estado
  `frozen`. Cada cambio efectivo de escalas incrementa la generación.
- Los parámetros viajan por `/calibration` y quedan en la grabación .jsonl.

## Catálogo (fórmulas)

Notación: `p_i` = keypoint i (coords isotrópicas suavizadas por One-Euro),
`T` = altura de torso, `Δw(x)` = diferencia trailing de x en la ventana w.

| Feature | Fórmula | Divisor / clip | Linaje |
|---|---|---|---|
| `qom` | media de `‖Δ₄₀₀(p_i)‖/Δt/T` sobre keypoints válidos | ÷ `vmax_hand`, clip 0..1 | proxy del QoM de silueta (Camurri/EyesWeb); acá por velocidad media de keypoints |
| `contraction` | `1 − (d̄ − 0.5)/1.5`, con `d̄` = media de `‖p_ext − centro_caderas‖/T` para muñecas+tobillos | clip 0..1 | Contraction Index (EyesWeb) adaptado a esqueleto |
| `expansion` | área del **hull convexo** de keypoints válidos ÷ T² ÷ 6 | clip 0..1 | kinesphere 2D (EMOKINE convex hull) |
| `vel_hand_l/r` | `‖Δ₁₂₀(p_muñeca)‖/Δt/T` | ÷ `vmax_hand`, clip | cinemática básica |
| `vel_center` | ídem centro de caderas | ÷ `vmax_center`, clip | ídem |
| `smoothness_l/r` | `1/(1+jerk/jerk_ref)`; jerk = derivada trailing de la aceleración trailing de la velocidad de muñeca (unidades T/s³) | — | jerk como inverso de suavidad (EMOKINE); NO es el jerk adimensional integral (decisión: menor latencia) |
| `symmetry` | `1 − media(‖ |x_L−eje| − |x_R−eje| ‖)/T` sobre pares hombro/codo/muñeca/cadera; eje = media de x de hombros+caderas | clip 0..1 | Poyo-Solanas |
| `verticality` | `cos(eje_torso, vertical)` = `−t_y/‖t‖` con `t = p_hombros_medio − p_caderas_medio` (y hacia abajo) | nativo -1..1 | postural clásico |
| `angle_*` | `arccos` en la articulación entre los dos segmentos adyacentes, ÷ π | nativo 0..1 | ángulos articulares estándar |
| `laban_weight_proxy` | media de `(v/T)²` para manos+centro ÷ `energy_ref` | clip 0..1 | Effort-Weight ≈ energía cinética (Dance Style Recognition 2025). **PROXY** |
| `laban_time_proxy` | media de `|Δ₂₀₀(v)|/Δt` ÷ `accel_ref` | clip 0..1 | Effort-Time ≈ aceleración media. **PROXY** |
| `laban_space_proxy` | `desplazamiento/longitud_de_camino` de muñecas en 300 ms (1 = recto) | nativo 0..1 | Effort-Space (directness). **PROXY**; polaridad elegida: 1 = directo |

**Sobre los proxies Laban:** no existe una formalización canónica única de
Laban (el pack lo marca en disputa, especialmente Flow y Weight). Estas tres
variables son operacionalizaciones cinemáticas **inspiradas** en Effort; el
sufijo `_proxy` es deliberado para que nadie las lea como medición Laban. El
Effort-Flow no se emite en v1 (su formalización es la más disputada).

## Propagación de validez

Cada feature declara sus keypoints requeridos (`_FEATURE_DEPS`). Estado de la
feature = peor estado de sus dependencias (`invalid` > `held` > `observed`).
`invalid` ⇒ valor sentinel 0.0 en wire que el receptor debe ignorar.

## Agregados

Media/MAD/máx en ventana trailing de 1 s se calculan internamente pero **NO
viajan en v1** (presupuesto MTU; r4 #2). Incorporarlos al wire = bump de
`feature_set_version` + nueva entrada en el manifiesto.
