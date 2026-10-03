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

## 5. Los cuatro presets

Un preset es una combinación de ajustes elegida para un caso de uso. Se elige uno y listo; si hace falta, después se abren las perillas a mano.

| | **Esencial** | **Pocas personas** | **Grupo** | **Masa** |
|---|---|---|---|---|
| Para qué | trackeo básico en tiempo real | 1 a 4 personas, identidad firme | hasta 8 personas | multitud grande |
| Qué prioriza | velocidad | que cada persona conserve su identidad aunque se cruce o se tape | identidad en un grupo | ver a toda la gente, aunque no se distinga quién es quién |
| Cuesta | muy poco | medio | alto | alto |
| Entrega de más | — | — | variables de multitud | además, las señales de masa (`mass_present`, `mass_active`) |

**Cuál elegir.** Si la máquina no tiene placa de video (una Mac, por ejemplo) y querés ver el movimiento en vivo, **Esencial**. Si te importa que dos o tres personas no se confundan entre sí, **Pocas personas**. **Grupo** y **Masa** son para escenas realmente pobladas: en una escena de dos personas rinden peor *y* van más lento, porque buscan detectar todo lo que puedan y terminan inventando gente donde no hay.

Por línea de comandos (punto 7) los modos siguen siendo dos, `group` y `crowd`, que se corresponden con los presets **Grupo** y **Masa**.

Medición sobre dos videos de baile (proxy de identidad sin ground truth, en una RTX 3090; los números concretos están en `reports/preset_comparison.json`): Esencial corrió a 124–158 fps, Pocas personas a 35–42, Grupo a 31–32. En uno de los videos, Grupo produjo **cuatro veces más saltos de identidad** que Esencial.

---

## 6. La forma más fácil: la interfaz web local

Para quien no quiera tocar la línea de comandos, el proyecto trae una **interfaz gráfica que corre en la propia máquina**:

```bash
python scripts/webapp.py
```

Eso abre el navegador en una página local (nada sale del equipo), con dos pestañas. Al abrirla detecta el hardware y propone el preset que le corresponde: **Grupo** si hay placa NVIDIA, **Esencial** si no.

**Procesar un video** — **cargás** un video —o grabás con la webcam— y, si querés, indicás desde y hasta qué segundo procesar; **elegís** el preset y, si hace falta, abrís los parámetros; **elegís** qué dibujar y qué exportar; le das **procesar**; y **ves** el video con el render, los gráficos de cada variable en el tiempo, y los botones para **descargar** la sesión, los CSV y la configuración exacta de la corrida.

Para analizar un **archivo original** necesitás `ffprobe` (paquete FFmpeg) en el `PATH`. El recorte usa los segundos PTS del medio, incluso si el primer cuadro no empieza en cero o hay huecos. JSONL y CSV conservan PTS, base de tiempo, índice fuente y SHA-256. Si falta el PTS o la decodificación no coincide con el inventario, la corrida falla explícitamente; el manifiesto identifica una decodificación incompleta y el JSONL parcial se rotula `.partial.jsonl`. El MP4 dibujado tiene FPS constante: es una vista previa, no una fuente para medir fase. Ver [tiempo y procedencia offline](VIDEO_OFFLINE_TIME.md).

**En vivo (webcam)** — procesa la cámara **en tiempo real** y va mostrando el render y las variables mientras la persona se mueve. La cámara es la del navegador (la de tu máquina), aunque el procesamiento corra en otra máquina por la red. Los mismos controles de preset, parámetros y render están disponibles y se aplican al instante: cambiar el render es inmediato; cambiar un parámetro de procesamiento recarga el modelo y tarda unos segundos.

### Las perillas: cuánto cuesta y qué se ve

**Parámetros de procesamiento** — definen cuánto trabaja la máquina por cuadro. De mayor a menor impacto:

- **Modelo de pose**: *Nano* (rápido) o *Medium* (preciso). Es la decisión más pesada de todas.
- **Seguimiento de identidad**: *ByteTrack* (barato) · *BoT-SORT liviano* · *BoT-SORT + ReID* (identidad máxima, pero corre una segunda red por cada caja detectada: con muchas detecciones se vuelve carísimo).
- **Resolución de proceso**: de 320 a 1280 px. Más resolución = se ve gente más chica y lejana, y cuesta más.
- **Detecciones máximas por cuadro** y **confianza mínima**: bajar la confianza y subir el máximo hace que el sistema vea más gente en una multitud, pero en una escena de dos personas inventa detecciones que ensucian la identidad.
- **Personas a seguir (slots)**: cuántas identidades sostiene a la vez.
- **Variables de multitud** y **mapa de densidad**: el mapa de densidad es caro; se calcula 1 de cada N cuadros.
- **Procesar 1 de cada N cuadros**: divide el trabajo por N a cambio de resolución temporal.
- **Suavizado**: no cambia el costo, cambia cuánto tiembla o cuánto se atrasa el esqueleto.

El botón **Estimar velocidad con esta config** mide los primeros cuadros del video y dice cuántos fps saca, si alcanza para tiempo real y cuánto tardaría el video entero — antes de lanzarlo.

**Render** — no afecta nada de lo que se mide, solo lo que se ve:

- **Fondo**: video original, video oscurecido (con cuánto), o **negro** — para exportar solo los esqueletos sobre negro.
- **Qué dibujar**: puntos, esqueleto, caja, número de identidad, silueta, mapa de densidad.
- **Grosor de línea**, **tamaño de punto**, **un color por persona** o color único.
- **Estelas**: los cuerpos dejan rastro durante los milisegundos que indiques.
- **Escala de salida** y **datos sobre la imagen** (fps, personas, foco).
- **Generar video de salida**: apagalo si solo querés los datos — se procesa bastante más rápido.

Cada corrida deja un `run_config.json` con la configuración exacta y el modelo realmente cargado, así un resultado se puede repetir tal cual.

### Clonar y correr en cualquier máquina (incluida una Mac)

El proyecto es **plug-and-play**: se clona, se instalan las dependencias, y la primera vez que se lanza la interfaz web, **los modelos que faltan se descargan solos**. Los modelos entrenados no viajan dentro del repositorio (son binarios pesados que inflarían su historia), pero están publicados aparte y se bajan automáticamente.

Los pasos, una sola vez:

```bash
git clone <repo> && cd HarMoCAP
pip install -r requirements.txt      # NO requirements.lock (fijado a la placa del servidor)
python scripts/webapp.py             # baja los modelos si faltan y abre la interfaz
```

Si preferís bajar los modelos por adelantado, sin abrir la interfaz:

```bash
python scripts/fetch_models.py
```

Notas para máquinas sin placa NVIDIA (una Mac, por ejemplo):

- Anda igual, con el modelo portable; la versión compilada rápida es solo para placas NVIDIA y el sistema usa la portable automáticamente.
- Va **más lento** que en una máquina con placa; la barra de progreso lo muestra.
- La **cámara web funciona** cuando el sistema corre local (no cuando se accede a un servidor remoto, que buscaría la cámara del servidor).
- En una Mac, la instalación estándar de PyTorch ya trae el soporte de Apple Silicon.

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
Esta ruta ritma el archivo como **cámara simulada** y usa reloj monotónico de llegada. Para estudiar fase o intervalos originales del video, usá **Procesar un video** en la webapp y sus datos JSONL/CSV.

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
