# INTERFACE_SPEC — Contrato HarMoCAP → Nico (v1)

> **Este es el documento que define cómo HarMoCAP entrega los datos de movimiento
> corporal.** La fuente de verdad machine-readable es `osc_contract.v1.json`
> (mismo directorio); este documento la explica. Si algo difiere, manda el JSON.
> Versión del contrato: `schema 1.0.0 · feature_set 1.0.0 · layout 1`.

## Qué recibís

Un stream **OSC 1.0 sobre UDP** que describe, ~30 veces por segundo, el estado
corporal de una persona trackeada por cámara: **17 keypoints** (esqueleto COCO)
y **21 variables de movimiento** ya normalizadas y listas para mapear a sonido.
Además, cada sesión puede entregarse **grabada** como archivo `.jsonl` (una
línea JSON por frame) que el `replay.py` del kit reproduce por OSC con el
timing original — así desarrollás tu mapeo sin cámara ni GPU.

**Nota clave:** los datos llegan a tasa de video (~30 Hz), muy por debajo de la
tasa de audio. **Interpolá/suavizá en tu motor de sonido** para que la
modulación no suene escalonada.

## Los tres tipos de paquete

| Paquete | Cuándo llega | Qué trae |
|---|---|---|
| `/harmocap/v1/hello` | ~1 Hz + al cambiar algo | identidad del stream y del contrato, estado de calibración, tamaño del frame |
| `/harmocap/v1/calibration` | ~1 Hz + al calibrar/congelar | los **parámetros de calibración** (escalas reales usadas) |
| bundle por frame | ~30 Hz | `/meta` + mensajes por persona (keypoints, estados, bbox, features) |

Cada frame es **un bundle OSC atómico**: o lo recibís entero o no lo recibís.
Todos los mensajes de un bundle comparten `captured_frame_id` y `bundle_seq`.

## Reglas que tu receptor DEBE implementar

1. **Gating:** no consumas frames hasta tener el `/hello` **y** el
   `/calibration` cuya tupla `(contract_id, calibration_generation,
   calibration_hash)` coincida con la del frame. Si `/hello` y `/calibration`
   difieren entre sí, descartá esa generación y esperá ambos coincidentes.
2. **Scope por `stream_id`:** todos los contadores (`captured_frame_id`,
   `bundle_seq`), leases y generaciones valen **dentro de un `stream_id`**
   (aleatorio por arranque del emisor). Si ves un `stream_id` nuevo: reseteá tu
   estado y aceptá el stream nuevo.
3. **Descarte monotónico:** dentro del mismo `stream_id`, descartá cualquier
   bundle con `bundle_seq` ≤ al último aplicado (paquetes UDP viejos/reordenados).
4. **Lease de presencia:** si no llegan datos de un slot por más de **2000 ms**,
   tratalo como ausente aunque no hayas visto el tombstone (`present=0` se
   repite ~15 frames, pero UDP puede perderlos todos).
5. **Features inválidas:** cuando `feat_state[i] = 2` (invalid), el valor de
   `features[i]` es un **sentinel 0.0 que DEBE ignorarse** (retené tu último
   valor válido o silenciá ese parámetro). Nunca vas a recibir NaN.
6. **Provisional:** mientras `calibration_state = "calibrating"` (primeros ~5 s)
   las features usan escalas por defecto; tratalas como provisionales si te
   importa la precisión del rango.

## Sistema de coordenadas

- **Isotrópico:** `x = x_px / alto_del_frame`, `y = y_px / alto_del_frame`.
  Así los ángulos y trayectorias no se distorsionan en 16:9.
- Origen **arriba-izquierda**; x crece a la derecha, **y crece hacia abajo**.
- `y ∈ [0,1]`; `x ∈ [0, ancho/alto]` (≈1.78 en 16:9). `frame_w`/`frame_h`
  llegan en `/hello`.
- **Sin espejo**: con cámara frontal, la izquierda del sujeto aparece a la
  derecha de la imagen (como en un video normal, no como en un espejo).

## Los blobs binarios

Los datos densos viajan como blobs OSC **big-endian** (layouts exactos y golden
vectors en el manifiesto):

| Blob | Layout | Bytes |
|---|---|---|
| `keypoints` | 17 × `>fff` = (x, y, conf) | 204 |
| `kp_state` | 17 × `>BIQ` = (estado, age_frames, age_µs) | 221 |
| `features` | `>21f` en el orden canónico | 84 |
| `feat_state` | `>21B` | 21 |
| `calibration.params` | `>6f` | 24 |

En Python: `struct.unpack(">fff", blob[i*12:(i+1)*12])`. El
`osc_receiver_example.py` del kit ya decodifica todo.

**Estados** (por keypoint y por feature): `0 = observed` (dato real del modelo),
`1 = held` (dato retenido de la última observación; `conf` decae), `2 = invalid`
(ignorar). `conf` es la **confiabilidad efectiva**: solo en `observed` coincide
con la confianza del modelo YOLO.

## Las 21 features (orden canónico, rangos, polaridad)

| # | Feature | Rango | Qué significa (1 = …) |
|---|---|---|---|
| 0 | `qom` | 0..1 | mucho movimiento corporal global |
| 1 | `contraction` | 0..1 | cuerpo contraído (extremidades cerca del centro) |
| 2 | `expansion` | 0..1 | cuerpo expandido (área que ocupa el esqueleto) |
| 3 | `vel_hand_l` | 0..1 | mano izquierda a velocidad máxima calibrada |
| 4 | `vel_hand_r` | 0..1 | ídem derecha |
| 5 | `vel_center` | 0..1 | el centro del cuerpo se desplaza rápido |
| 6 | `smoothness_l` | 0..1 | movimiento suave de mano izq (0 = entrecortado) |
| 7 | `smoothness_r` | 0..1 | ídem derecha |
| 8 | `symmetry` | 0..1 | postura simétrica respecto del eje corporal |
| 9 | `verticality` | **-1..1** | 1 erguido · 0 horizontal · -1 invertido |
| 10-11 | `angle_elbow_l/r` | 0..1 | brazo extendido (0 = plegado); ángulo/π |
| 12-13 | `angle_knee_l/r` | 0..1 | pierna extendida |
| 14-15 | `angle_shoulder_l/r` | 0..1 | brazo levantado/alejado del torso |
| 16-17 | `angle_hip_l/r` | 0..1 | apertura pierna-torso |
| 18 | `laban_weight_proxy` | 0..1 | energía cinética alta (**proxy**, no Laban canónico) |
| 19 | `laban_time_proxy` | 0..1 | movimiento súbito (aceleración media alta; **proxy**) |
| 20 | `laban_space_proxy` | 0..1 | trayectoria de manos directa (1) vs errante (0); **proxy** |

Las tres últimas son **operacionalizaciones cinemáticas inspiradas en Laban**,
no mediciones del sistema Laban canónico (no existe formalización única).
Sugerencia de diseño (de la investigación): las variables **posturales**
(contracción, ángulos, simetría, verticalidad) son más estables y expresivas
que las puramente cinemáticas — buen lugar para empezar el mapeo.

## Dominio operativo (importante)

Las features 2D son robustas con **cámara fija, aproximadamente frontal y
cuerpo suficientemente visible** (torso ≥ ~15 % del alto del frame). Fuera de
ese dominio (vista lateral fuerte, perspectiva extrema) **degradan sin aviso**.

## Flujo recomendado para desarrollar tu mapeo

1. `pip install -r requirements.txt` (solo `python-osc`; el kit funciona
   también con stdlib pura).
2. `python selftest.py` — verifica el kit entero en tu máquina.
3. Terminal A: `python osc_receiver_example.py --port 9000`
   Terminal B: `python replay.py examples/session_v1.jsonl --port 9000 --loop`
4. Reemplazá el receptor de ejemplo por tu motor: cada address y blob están
   documentados acá y en el manifiesto; los fixtures de `examples/fixtures/`
   ejercitan tombstones, oclusión, reinicio de stream y calibración para que
   pruebes todos los caminos de tu receptor sin cámara.
