# Crowd counting por mapas de densidad — investigación para el modo masa

> Investigación de estado del arte (2024-2026) sobre estimación de multitud por mapas de densidad en tiempo real, con vistas a reemplazar o complementar la rama de detección del modo masa de HarMoCAP. Agente Explore, 2026-07-20. Reporte crudo completo en `reportes_agentes/01-sota-crowd-counting.md`.

## Por qué se abrió esta investigación

El modo masa (contrato 1.2) deriva sus agregados de las bboxes que entrega YOLO26-pose. La corrida sobre material de pogo mostró el límite esperado: donde la multitud se vuelve densa y las personas ocupan diez píxeles, la detección deja de encontrarlas y el conteo miente por defecto. La pregunta que motiva la investigación no es cuál es el mejor modelo de conteo publicado, sino si un modelo de densidad mejora lo que ya tenemos **en nuestro punto de operación**: video comprimido de 640×360, cámara en mano, sin dataset propio anotado.

## Conclusiones que cambian el diseño

**El paradigma correcto es la regresión de densidad, no la detección ni los métodos por puntos.** Un mapa de densidad es un campo espacial continuo: el conteo es su integral, el centroide su primer momento, la dispersión el segundo, y el flujo la derivada temporal de ese campo. Todas las señales que el modo masa necesita salen de la misma salida, sin lógica de asociación que introduzca discontinuidades — condición que importa cuando la señal modula sonido. Los métodos por puntos entregan longitud variable (fricción para exportar a TensorRT) y momentos ruidosos entre cuadros.

**Detección y densidad ganan en regímenes distintos, y el cruce está medido.** Sobre video real de multitud (benchmark HAJJv2, 167 cuadros anotados a mano), la detección supera a los métodos de densidad en el conteo global pero colapsa en la banda densa, donde el método por puntos degrada con gracia y queda tres veces mejor. La lectura arquitectónica es un régimen doble antes que un reemplazo: la rama de detección conserva su ventaja mientras la gente sea grande — y además entrega identidad, que la densidad no puede dar — y la rama de densidad toma el relevo cuando la escena se satura.

**El candidato es ZIP.** Licencia MIT, pesos publicados para cuatro datasets en cinco variantes, backbone MobileNetV4 en las variantes chicas, y una salida que además del mapa de tasa entrega un mapa de ceros estructurales utilizable como máscara de masa. El margen de latencia frente a un presupuesto de 30 ms es de uno a dos órdenes de magnitud. La elección de checkpoint no es indiferente: la evidencia de transferencia entre datasets favorece los entrenados en UCF-QNRF o NWPU-Crowd y desaconseja el de ShanghaiTech A, que es justamente el que la mayoría de los repositorios publica por defecto.

**El riesgo dominante es la resolución, no la compresión.** La literatura mide que bajar la escala degrada mucho más que degradar la calidad de compresión, y nuestro punto de operación queda debajo del codo de esa curva. A eso se suman el desplazamiento de dominio, la ausencia de ajuste fino y cabezas en el límite inferior de lo detectable. Son cuatro degradaciones que la literatura mide por separado — entre 1,5 y 3 veces cada una — y que aquí se acumulan sin que nadie haya medido su composición. No existe además ningún despliegue documentado de esta familia de modelos sobre video de recital con cámara en mano; ese silencio también informa.

**Consecuencia de diseño: la escala absoluta no es confiable, la dinámica relativa sí.** Para modular música importa que la señal suba cuando entra gente y baje cuando se vacía, no que el número coincida con la cantidad de personas. Normalizar contra un percentil rodante de la propia sesión convierte una debilidad irreducible en una decisión de diseño explícita.

**El flujo de masa tiene una solución barata en el hardware que ya está.** La RTX 3090 incluye un acelerador de flujo óptico en silicio, independiente de los núcleos de cómputo, expuesto por OpenCV: no compite con la inferencia. La receta de campo es flujo óptico denso ponderado por el mapa de densidad, del que sale además la divergencia — expansión o compresión de la masa —, una señal musical que hoy no existe en el contrato. El techo es conocido y aceptable: ningún algoritmo de flujo supera el 76% de precisión de trayectoria en escenas densas, y para una señal agregada y suave eso alcanza.

## Qué queda descartado

La difusión aplicada al conteo es incompatible con tiempo real. La inferencia por mosaicos exige un número de pasadas que no cabe en el presupuesto y carece de precedente en conteo de multitud. Los métodos de conteo sin supervisión basados en modelos de lenguaje visual producen errores de cuatro veces el valor real. Y dos de los repositorios más citados del campo tienen problemas de licencia que los excluyen de un proyecto con vocación pública: uno restringe el uso a investigación académica pese a aparentar licencia permisiva, y otro no publica licencia alguna.

## Verificación de procedencia

El agente que produjo el reporte crudo admitió, en un mensaje posterior a la entrega, haber narrado un avance antes de tenerlo. Esa admisión obliga a tratar el informe como no confiable hasta comprobarlo, de modo que las afirmaciones que sostienen la recomendación se verificaron contra la fuente primaria:

- **ZIP**: repositorio existente bajo licencia MIT, cinco variantes con los conteos de parámetros reportados (0,81 M a 105,6 M) y pesos publicados para los cuatro datasets. El paper existe con el título, los autores y la fecha citados, y su método es efectivamente una verosimilitud de Poisson inflada en cero sobre conteos por bloque — de donde salen tanto el mapa de tasa como el mapa de ceros estructurales que el diseño aprovecha.
- **HAJJv2-CrowdCount**: el benchmark existe con el identificador citado, compara los tres paradigmas indicados y reporta los valores exactos que el informe atribuye, incluida la inversión del ranking en la banda densa.

Ambas verificaciones coinciden hasta el decimal con lo reportado. Los números de MAE por dataset de la tabla comparativa no se verificaron uno por uno: quien los use como criterio de decisión debería confirmarlos contra el paper correspondiente.

## Estado

Investigación **cerrada**. La decisión de implementar depende de una verificación previa sobre material propio: sin medir el error en nuestro punto de operación, no hay forma de distinguir una señal de densidad de ruido caro.
