# Evaluación de FreeMoCap como fuente de mejoras para HarMoCAP

> Revisión del repositorio `freemocap/freemocap` y su ecosistema (`skellytracker`, `skellyforge`, `aniposelib`, `skellycam`, `skelly_synchronize`) para decidir si aporta algo reutilizable a HarMoCAP. Fecha: 2026-07-20. Fuentes revisadas: los repositorios citados, su `pyproject.toml` y el código de filtrado de `skellyforge`.

## Conclusión

FreeMoCap no ofrece nada que mejore el sistema en su forma actual. Es un sistema de captura de diseño casi opuesto al nuestro en cada eje, y dos bloqueos —la licencia y la no causalidad de su procesamiento— impiden reutilizar su código. La única pieza con valor es `aniposelib`, y solo de forma condicional a una decisión que hoy no está en el roadmap: mover el proyecto hacia captura tridimensional multicámara.

## La distancia de diseño

FreeMoCap es un sistema de captura de movimiento de grado investigación, gratuito y sin marcadores, orientado a reconstrucción tridimensional a partir de varias cámaras, operado por una interfaz gráfica y procesado fuera de línea. HarMoCAP es lo contrario término a término: monocámara, bidimensional, en tiempo real, sin interfaz, con la latencia como preocupación central y una salida que es un flujo de variables por OSC. No comparten propósito, y esa diferencia de propósito es la que vuelve inaplicable el grueso del repositorio.

| Eje | FreeMoCap | HarMoCAP |
|---|---|---|
| Procesamiento | fuera de línea, por lotes, con GUI | tiempo real, sin interfaz |
| Cámaras | multicámara | monocámara |
| Salida | reconstrucción 3D | variables 2D por OSC |
| Latencia | no es una preocupación | el eje del diseño |
| Licencia | AGPL-3.0 | MIT / público |

## Los dos bloqueos duros

**La licencia.** `freemocap`, `skellytracker` y `skellyforge` son AGPL-3.0. Es la misma razón por la que HarMoCAP mantiene Ultralytics fuera del kit portable: no puede incorporarse ese código a un proyecto de vocación pública sin arrastrar la obligación de licencia recíproca. Sirve como lectura de referencia, no como código a tomar.

**La causalidad.** El filtrado de `skellyforge` usa `scipy.signal.filtfilt`: un Butterworth de fase cero aplicado en dos pasadas, hacia adelante y hacia atrás. Necesita la grabación entera y mira el futuro de cada muestra, exactamente lo que el invariante de causalidad de HarMoCAP prohíbe, porque una feature que mira adelante en grabación mentiría en vivo. Su suavizado no es trasladable a tiempo real. El dato es informativo por sí mismo: confirma que la mayor parte del suavizado de captura fuera de línea es inservible para un sistema de streaming.

## La única pieza con valor: aniposelib

`aniposelib` —la librería de calibración de cámaras y triangulación que FreeMoCap usa por debajo— es BSD-2-Clause, permisiva y usable; funciona de forma independiente del resto del ecosistema; y es un componente maduro, heredado del proyecto Anipose.

Su relevancia es condicional y futura. HarMoCAP entrega hoy keypoints bidimensionales frontales, y su propia documentación declara que fuera del dominio frontal las features degradan sin aviso: los ángulos que emite son proyecciones planas, no ángulos reales del cuerpo. Si en algún momento Harmonic Beacon requiriera variables corporales tridimensionales verdaderas —profundidad, ángulos reales, orientación en el espacio—, el camino técnico es la triangulación multicámara, y `aniposelib` es precisamente esa pieza con una licencia que el proyecto puede usar. No es una necesidad presente: HarMoCAP es monocámara de baja latencia por elección de diseño. Queda anotada como la respuesta disponible al día en que la pregunta por el 3D se plantee.

## Lo que confirma sin aportar

La arquitectura de trackers de `skellytracker` valida la nuestra sin agregarle nada. Abstrae varios backends de pose —MediaPipe, YOLO, RTMPose— tras una clase base común, que es el mismo patrón del `PoseBackend` de HarMoCAP: un único módulo que aísla la librería de percepción del resto del sistema. Ver el mismo patrón en un proyecto independiente refuerza que la separación de capas está bien elegida.

`skellytracker` integra además RTMPose, que es el modelo que la investigación previa de HarMoCAP sobre conteo de multitud había señalado como la alternativa seria a YOLO en escenas densas. No es un aporte de FreeMoCap —RTMPose es de OpenMMLab— pero verlo integrado en un sistema de captura real refuerza que, si alguna vez se cambiara de detector, RTMPose es el candidato a evaluar primero.

## Una idea, no un préstamo

FreeMoCap impone longitudes de hueso constantes en su post-proceso: un cuerpo rígido no cambia de proporciones entre cuadros, de modo que una longitud que se aparta de la esperada delata un keypoint mal ubicado. HarMoCAP observó un problema emparentado —el parpadeo de los keypoints faciales que llegó a anular la feature de energía— y una restricción causal de esa clase, que rechace posiciones incompatibles con la longitud esperada del segmento corporal, podría estabilizar la percepción. Pero es una idea a construir respetando la causalidad, no código a tomar del post-proceso fuera de línea de FreeMoCap.

## Registro de decisión

No se incorpora nada de FreeMoCap al sistema. Se conserva `aniposelib` como referencia para un eventual frente de captura tridimensional multicámara, hoy fuera del roadmap. La restricción causal de longitud de hueso queda como idea de mejora de percepción, independiente de este repositorio.
