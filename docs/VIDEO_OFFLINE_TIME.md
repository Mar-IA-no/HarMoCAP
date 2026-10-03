# Tiempo y procedencia del video offline

Plan de implementación para [HarMoCAP #3](https://github.com/Mar-IA-no/HarMoCAP/issues/3).

## Contrato

`process_video` es análisis offline del archivo original. Antes de cargar el
modelo, obtiene con `ffprobe` el `pts` de cada cuadro en orden
de presentación y la base de tiempo del stream. Rechaza el medio si esos PTS
faltan, se repiten o retroceden: no sustituye silenciosamente `cuadro/FPS` por
una medición. Conserva el SHA-256 del archivo, índice fuente (base cero), PTS
en ticks, base de tiempo y segundos derivados del PTS. La selección
`t_start <= PTS < t_end` usa segundos absolutos del medio; `t_end=0` deja el
extremo abierto. `frame_stride` cuenta sólo cuadros elegibles por PTS.
Se registra también el PTS del **primer cuadro decodificado del medio completo**,
incluso si el recorte comienza después. Un consumidor puede calcular
`tiempo_relativo = (PTS_cuadro - PTS_origen) × base_de_tiempo` sin elegir
accidentalmente el primer cuadro del recorte como nuevo origen.
El SHA-256 se verifica antes y después de inspeccionar los PTS y al terminar
la decodificación; si el medio cambia, la corrida queda marcada como fallida.

La decodificación OpenCV recorre el archivo secuencialmente desde el principio,
para que el cuadro decodificado de índice `i` corresponda al PTS de índice `i`
obtenido por `ffprobe`. Si la lectura termina antes, falla y declara el índice;
no entrega una sesión parcial como si fuera completa. El JSONL incluye el
contador procesado `frame` por compatibilidad, pero ese contador nunca es el
índice del medio. Los derivados temporales, las series y las estelas reciben
el tiempo PTS real. `processed_elapsed_us` es un reloj monotónico **relativo
al inicio de esta corrida**, distinto del PTS: mide desempeño de procesamiento,
no captura óptica ni tiempo del movimiento.

El manifiesto registra los denominadores: cuadros informados por `ffprobe`,
fuera de recorte, elegibles, omitidos por stride, procesados y fallas de
decodificación. Los CSV conservan las columnas de procedencia. El MP4 renderizado
por OpenCV tiene FPS constante y es **una vista previa**, no una copia de la
cronología original; para fase/audio se usa JSONL/CSV más el original.

`LatchingCamera` procesa una fuente como cámara simulada: su reloj monotónico y
su cadencia `1/FPS` modelan llegada en vivo. Esa ruta no sirve para inferir
intervalos originales del archivo. Tampoco se interpretan todavía estos PTS
como prueba de Laban, HIT, eficiencia o belleza; sólo evitan una distorsión
temporal introducida por el instrumento.

## Verificación prevista

Videos sintéticos CFR con origen desplazado y VFR con hueco comprueban recorte,
índices, intervalos y procedencia. Casos sin PTS y con PTS no monótonos
comprueban el rechazo explícito. Una prueba sin modelo de pose comprueba el
tiempo recibido por los componentes temporales, el JSONL, el CSV y los
denominadores. Ninguna prueba requiere cámara ni personas.
