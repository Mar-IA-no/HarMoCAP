# HarMoCAP — Manual de uso: qué se puede medir y cómo usarlo

> Este documento describe **todo lo que HarMoCAP puede medir de un cuerpo en movimiento y de una multitud**, y el camino mínimo para poner cada cosa a funcionar. No explica cómo funcionan las cosas por dentro —eso vive en `docs/FEATURES.md` y en la especificación del contrato— sino qué entregan y cómo tomarlas. Está escrito para quien va a *usar* las señales: un diseñador de sonido, un artista, alguien que arma una instalación.

---

## 1. Qué es, en una frase

HarMoCAP mira a una o varias personas por una cámara y, treinta veces por segundo, entrega un flujo de números que describen cómo se mueven sus cuerpos y cómo se comporta la masa cuando hay mucha gente. Esos números salen por red (OSC sobre UDP) listos para conectar a un motor de sonido, de luz o de lo que se quiera modular en tiempo real.

No hace falta cámara ni GPU para *desarrollar* contra él: hay un kit portable que reproduce sesiones grabadas exactamente como el sistema en vivo.

---

## 2. Lo que se puede medir de UNA persona

Por cada persona en escena —hasta ocho a la vez— el sistema entrega veinticuatro variables, todas normalizadas y listas para mapear. Se agrupan en cuatro familias.

### Energía y movimiento global

| Variable | Qué dice | 1 significa… |
|---|---|---|
| `qom` | cuánto se mueve el cuerpo entero | mucho movimiento |
| `vel_center` | qué tan rápido se desplaza la persona por el espacio | desplazamiento veloz |
| `vel_hand_l` / `vel_hand_r` | velocidad de cada mano | mano a máxima velocidad |
| `smoothness_l` / `smoothness_r` | qué tan suave o entrecortado es el movimiento de cada mano | movimiento fluido |

### Forma del cuerpo (postura)

| Variable | Qué dice | 1 significa… |
|---|---|---|
| `contraction` | cuánto se cierra el cuerpo sobre sí mismo | encogido, extremidades cerca del centro |
| `expansion` | cuánto espacio ocupa el cuerpo | abierto en estrella |
| `symmetry` | si la postura es simétrica respecto del eje del cuerpo | perfectamente simétrico |
| `verticality` | orientación del cuerpo — **es la única que va de -1 a 1** | 1 erguido · 0 horizontal · -1 invertido (cabeza abajo) |

### Ángulos de las articulaciones

Ocho variables (`angle_elbow_l/r`, `angle_knee_l/r`, `angle_shoulder_l/r`, `angle_hip_l/r`). Cada una dice cuán extendida está esa articulación: cerca de 1 el miembro está estirado, cerca de 0 está plegado. Son las señales **más estables y expresivas** del set —cambian de forma limpia y predecible— y son un buen lugar para empezar un mapeo.

### Cualidad del movimiento (inspiradas en Laban)

| Variable | Qué dice |
|---|---|
| `laban_weight_proxy` | cuánta energía cinética pone el cuerpo |
| `laban_time_proxy` | qué tan súbito es el movimiento (golpes de aceleración) |
| `laban_space_proxy` | si las manos van directas a un punto o vagan errantes |

Son operacionalizaciones inspiradas en el sistema Laban, no mediciones del Laban canónico.

### Ritmo del cuerpo

| Variable | Qué dice |
|---|---|
| `tempo_bpm` | el pulso del cuerpo en BPM — **va en BPM reales, no de 0 a 1**; 0 significa "sin pulso detectable" |
| `beat_phase` | en qué punto del pulso está ahora mismo (0 a 1, avanza como una rampa) |
| `tempo_conf` | qué tan confiable es el pulso detectado |

El ritmo es una señal **intermitente**: aparece cuando el movimiento es periódico y no antes. Se usa mirando `tempo_conf` y el estado, nunca asumiendo que siempre está.

---

## 3. Lo que se puede medir de la MULTITUD

Además de las personas individuales, en cada cuadro llega un paquete aparte que describe a la masa como un solo instrumento. Trece señales:

| Señal | Qué dice |
|---|---|
| `crowd_count` | cuántas personas detecta en crudo (distinto de las 8 con identidad) |
| `crowd_qom` | cuánto se mueve la masa en conjunto |
| `density` | qué fracción del cuadro ocupa la gente |
| `centroid_x` / `centroid_y` | dónde está el centro de masa del grupo |
| `flow_x` / `flow_y` | hacia dónde deriva el grupo |
| `dispersion` | 0 = apiñados · 1 = desparramados |
| `crowd_tempo_bpm` / `crowd_beat_phase` / `crowd_tempo_conf` | el pulso colectivo de la masa |
| `mass_present` | **toda** la gente en cuadro, incluso la que es tan chica o lejana que la detección no la ve |
| `mass_active` | cuánta de esa masa se está moviendo |

Sobre las dos últimas (`mass_present` y `mass_active`): son la mejor forma de capturar una multitud entera —un recital, un pogo— donde contar cabeza por cabeza es imposible. No son un conteo exacto: son una escala relativa a la propia sesión, que sube cuando entra o se agita gente y baja cuando se vacía. Un recital lleno pero quieto da presencia alta y actividad baja; un pogo, ambas altas. Solo llegan en el modo masa (ver más abajo).

---

## 4. Elegir a quién seguir: el foco

Cuando hay varias personas, una está marcada como **la focal** —la protagonista—. Por defecto es la más grande en cámara, y el sistema cambia de protagonista solo cuando otra la supera con holgura, para que la elección no titile.

Se puede tomar el control del foco de dos maneras:

- **Desde el teclado**, con la ventana de visualización abierta (`--show`): teclas `1` a `8` pinean a esa persona, `0` vuelve a automático.
- **Desde la red**, mandando un mensaje `/harmocap/v1/control/select` al puerto de control (9001 por defecto) con un número: `0` a `7` fija esa persona, `-1` vuelve a automático.

Si la persona pineada se va de escena, el foco vuelve solo a automático. Cada persona llega marcada con un indicador `focused`, así que del lado del sonido se puede decidir: mapear solo a la focal, mezclar el grupo, o cruzar las dos cosas (por ejemplo, la focal lleva la melodía y la energía del grupo lleva la densidad armónica).

---

## 5. Los dos modos de trabajo

El sistema corre en uno de dos modos, según qué te importe:

| | **Modo grupo** (por defecto) | **Modo masa** |
|---|---|---|
| Para qué | seguir con seguridad a un grupo chico (≤8 personas) | capturar una multitud grande |
| Qué prioriza | que cada persona conserve su identidad aunque se cruce, se tape o salga y vuelva | ver a toda la gente, aunque no se distinga quién es quién |
| Qué entrega de más | identidad estable persona por persona | las señales de masa (`mass_present`, `mass_active`) |

En **ambos** modos llegan las personas individuales y el paquete de multitud; la diferencia es cuánto esfuerzo pone en la identidad de cada uno versus en ver a la masa entera.

---

## 6. La forma más fácil: la interfaz web local

Para quien no quiera tocar la línea de comandos, el proyecto trae una **interfaz gráfica que corre en la propia máquina**:

```bash
python scripts/webapp.py
```

Eso abre el navegador en una página local (nada sale del equipo). Ahí, en cuatro pasos: **cargás** un video —o grabás con la webcam—; **elegís** el modo (grupo o masa), qué dibujar sobre el video (puntos, esqueleto, caja, número de identidad, silueta, mapa de densidad) y qué variables exportar; le das **procesar**, con barra de progreso; y **ves** el video con overlay más los gráficos de cada variable en el tiempo, con botones para **descargar** la sesión grabada y los CSV.

Procesa con el hardware que tenga la máquina hasta donde alcance: en una con placa de video va rápido, en una sin placa tarda más, pero siempre corre. La página lo dice de entrada.

### Correr en una máquina sin placa NVIDIA (por ejemplo, una Mac)

El sistema corre en cualquier máquina, pero hay que tener en cuenta que **dos archivos pesados no viajan con el repositorio** (están excluidos a propósito): el modelo entrenado y el modelo de densidad. Un clon fresco necesita:

1. **El modelo entrenado** (imprescindible). En una Mac o un equipo sin placa NVIDIA, el sistema usa el modelo portable `harmocap-m-pose-ft2.pt` —la versión rápida compilada solo sirve en placas NVIDIA—. Ese archivo hay que copiarlo a la raíz del clon; sin él, no hay modelo que cargar.

2. **El modelo de densidad** (opcional, para las señales de masa). Los archivos `outputs/density/*.onnx` habilitan `mass_present` y `mass_active` en el modo masa. Si no están, el modo masa igual funciona, solo que esas dos señales llegan en cero.

3. **Las dependencias**: instalar desde `requirements.txt`, **no** desde `requirements.lock` —ese está fijado a las versiones de la placa NVIDIA del servidor y no sirve en otra máquina—. En una Mac, la instalación estándar de PyTorch ya trae el soporte de Apple Silicon.

La cámara web sí funciona cuando el sistema corre local (no así cuando se accede a un servidor remoto, que buscaría la cámara del servidor).

## 7. Cómo poner cada cosa a funcionar por línea de comandos (MVP de cada opción)

Todos los comandos se corren desde la raíz del proyecto, con el entorno del proyecto activo. (Todo esto también está detrás de la interfaz web del punto anterior; esta sección es para quien prefiere la terminal o automatizar.)

### Ver el sistema funcionando con una cámara

```bash
python scripts/run_realtime.py --source 0 --show
```

Abre la webcam, dibuja los esqueletos y empieza a emitir por OSC al puerto 9000. Con `--show` se ven las personas numeradas y se elige el foco con el teclado. Es el arranque más rápido para comprobar que todo anda.

### Elegir el modo

```bash
python scripts/run_realtime.py --source 0 --mode group    # grupo chico, identidad firme (default)
python scripts/run_realtime.py --source 0 --mode crowd    # multitud, señales de masa
```

### Correr sobre un video en vez de una cámara

```bash
python scripts/run_realtime.py --source ruta/al/video.mp4 --mode crowd
```

Sirve para probar contra material grabado sin depender de una cámara en vivo.

### Recibir las señales del otro lado

En la máquina que va a usar los datos, se levanta un receptor OSC escuchando el puerto 9000. El kit trae uno de ejemplo, listo para reemplazar por tu propio mapeo:

```bash
python osc_receiver_example.py --port 9000
```

### Grabar una sesión y volver a reproducirla

```bash
# grabar mientras corre
python scripts/run_realtime.py --source 0 --record sesion.jsonl

# reproducir después, sin cámara ni GPU, con el timing original
python replay.py sesion.jsonl --port 9000
```

Esto es clave para desarrollar el mapeo de sonido: se graba una vez con cámara y después se itera infinitas veces reproduciendo, sin necesidad de la cámara ni de una placa de video.

---

## 8. El kit portable: desarrollar sin cámara ni GPU

Para quien va a construir el mapeo de sonido, el sistema entrega un **kit autocontenido** (`harmocap-nico-kit/`) que corre en cualquier máquina, sin cámara, sin placa de video y sin las dependencias pesadas del sistema de captura. Trae:

- un **receptor de ejemplo** que decodifica todas las señales y las imprime, listo para reemplazar por el mapeo propio;
- un **reproductor** de sesiones grabadas;
- **sesiones y fixtures de ejemplo** que ejercitan todos los caminos (una persona, varias personas, cambio de foco, multitud, entradas y salidas de escena);
- un **autotest** que verifica que todo funciona en la máquina de destino.

El flujo recomendado para empezar: instalar el kit, correr el autotest, y en dos terminales lanzar el receptor y el reproductor de la sesión de ejemplo. A partir de ahí se reemplaza el receptor de ejemplo por el motor propio.

---

## 9. Cosas importantes al usar las señales

Unas pocas reglas prácticas que conviene tener presentes:

- **Los datos llegan a ritmo de video (~30 por segundo), muy por debajo del ritmo del audio.** Hay que interpolar o suavizar del lado del sonido para que la modulación no suene escalonada.
- **Algunas señales pueden marcarse como "no disponibles" por momentos.** Cuando una parte del cuerpo no se ve, o cuando el pulso todavía no es detectable, esa señal llega marcada como inválida: conviene retener el último valor bueno o silenciar ese parámetro, en vez de usar el cero que llega.
- **El sistema anda mejor con cámara fija, más o menos de frente, y con el cuerpo suficientemente visible.** Fuera de eso (vista muy de costado, cuerpo muy chico en el cuadro) las señales pierden precisión sin avisar.
- **`verticality` va de -1 a 1 y `tempo_bpm` va en BPM reales.** El resto de las variables van de 0 a 1. Vale revisar los rangos antes de mapear.

---

## 10. Resumen: el menú completo

**De cada persona (hasta 8):** energía global, velocidad de manos y de cuerpo, suavidad, contracción, expansión, simetría, verticalidad, ocho ángulos de articulaciones, tres cualidades de movimiento tipo Laban, y el pulso del cuerpo (BPM, fase, confianza).

**De la multitud:** conteo, energía colectiva, densidad, centro de masa, deriva, dispersión, pulso colectivo, y la masa entera presente y activa.

**Control:** elección del protagonista por teclado o por red.

**Formas de usarlo:** en vivo con cámara, sobre video grabado, o reproduciendo sesiones guardadas sin cámara ni GPU mediante el kit portable.
