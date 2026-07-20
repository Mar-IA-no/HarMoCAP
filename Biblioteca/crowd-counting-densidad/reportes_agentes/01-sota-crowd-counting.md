# Crowd counting por mapas de densidad en tiempo real — estado del arte 2024-2026

> Reporte crudo de agente Explore, 2026-07-20. Encargo: evaluar si un modelo de densidad mejora la rama de detección del modo masa de HarMoCAP en su punto de operación real (640x360, cámara en mano, sin dataset propio). Los claims de paper están marcados como tales.

**Adelanto de conclusión: sí en régimen denso, pero con una advertencia de resolución que domina todo el análisis.**

## 1. Tabla comparativa de candidatos

| Modelo | Año / venue | Repo | Licencia | Pesos | MAE SHA / SHB / QNRF | Deps | ONNX/TRT |
|---|---|---|---|---|---|---|---|
| **ZIP / EBC-ZIP** | 2025 (arXiv 2506.19955) | `Yiming-M/ZIP` | **MIT** | **4 datasets x 5 variantes** | **47.8 / 5.5 / 69.4** | timm, limpio | no documentado |
| **CLIP-EBC** | ICME'25 (arXiv 2403.09281) | `Yiming-M/CLIP-EBC` | **MIT** | SHA/SHB/QNRF/NWPU + HF | 52.5 / 6.6 / 80.3 | CLIP, medio | no documentado |
| **APGCC** | ECCV'24 | `AaronCIH/APGCC` | **MIT** | solo SHA | 48.8 / 5.6 / 80.1 | limpio | no |
| **PET** | ICCV'23 | `cxliu0/PET` | **MIT** | 5 datasets | 49.1 / 6.2 / n/d | limpio, sin CUDA custom | no (salida variable) |
| **DM-Count** | NeurIPS'20 | `cvlab-stonybrook/DM-Count` | **MIT** | 4 datasets | — / — / 85.6 | PyTorch limpio | trivial (VGG) |
| **STEERER** | ICCV'23 | `taohan10200/STEERER` | MIT | 8 datasets | 55.6 / 6.8 / 76.7 | HRNet+MMCV+`vision.cpp` | fricción alta |
| **CLTR** | ECCV'22 | `dk-liang/CLTR` | MIT | solo NWPU | 56.9 / 6.5 / 85.8 | mmcv, abandonado 2023 | posible |
| **P2PNet** | ICCV'21 | `TencentYoutuResearch/...` | **SOLO ACADÉMICO** | solo SHA | 52.7 / 6.3 / 85.3 | limpio | sí, con parches |
| **CSRNet** | CVPR'18 | `leeyeehoo/CSRNet-pytorch` | **SIN LICENCIA** | SHA/SHB | 68.2 / 10.6 / — | Python 2.7 | trivial si se reimplementa |
| **CrowdDiff** | CVPR'24 | `dylran/crowddiff` | MIT | sí | no verificable | difusión | incompatible RT |
| **LIMM** | 2025 | `tianhangpan/LIMM` | sin licencia | **repo vacío** | 50.8 / 6.5 / 76.4 | — | — |

Verificación directa: ZIP tiene repo público MIT con pesos en releases para ShanghaiTech A/B, UCF-QNRF y NWPU-Crowd en las cinco variantes (último release 28-jun-2025) y demo en HF Spaces.

## 2. Velocidad

Tabla de EBC-ZIP a 1024x768. **Procedencia: aparece en la v1 del paper y fue ELIMINADA en la v3**, que solo reporta FLOPs. Orientativa, no reproducida.

| Variante | Backbone | Params | GFLOPs @HD | FPS 3090 (claim v1) | MAE SHB |
|---|---|---|---|---|---|
| Pico | MobileNetV4-S-0.5x | 0.81M | 6.46 | ~1012 | 8.23 |
| Nano | MobileNetV4-S | 3.36M | 24.7 | ~548 | 7.74 |
| Tiny | MobileNetV4-M | 10.6M | 61.6 | ~250 | 6.67 |
| Small | MobileCLIP-S1 | 33.7M | 243 | ~51 | 5.88 |
| Base | CLIP-ConvNeXt-B | 106M | 801 | — | 5.51 |

Aun descontando optimismo, Nano y Tiny tienen 1-2 órdenes de magnitud de margen sobre 30 ms; a 640x360 el costo cae otro ~3x. Los transformer-based (PET, CLTR, STEERER) cuestan decenas de ms; CrowdDiff está fuera de discusión.

## 3. Paradigmas: cuál da centroide, dispersión y flujo

- **Density-map / blockwise** (ZIP, CLIP-EBC, DM-Count, CSRNet): la salida ES un campo espacial. ZIP con bloque B=16 sobre 640x360 da grilla ~40x22. Centroide = primer momento; dispersión = segundo momento; flujo = derivada temporal o flujo óptico ponderado. Continuo por construcción, sin matching que introduzca discontinuidades. **Paradigma correcto para este caso.**
- **Point-based** (P2PNet, APGCC, CLTR, PET): salida de longitud variable (fricción ONNX/TensorRT); momentos sobre puntos que aparecen y desaparecen son ruidosos.
- **Detección**: colapsa en densidad (ver §6).

Bonus de ZIP: además del mapa de tasa lambda emite un **mapa de ceros estructurales pi** (probabilidad de fondo) = máscara de masa gratis.

## 4. Crowd flow

**La RTX 3090 tiene NVOFA**, acelerador de flujo óptico en silicio (Turing/Ampere/Ada), expuesto como `cv2.cuda.NvidiaOpticalFlow_2_0`. Corre independiente de CUDA cores y SMs: no compite con la inferencia. NVIDIA declara 2-3 ms/frame (resolución no especificada), granularidad de bloque 4x4.

| Método | Latencia | Nota |
|---|---|---|
| **NVOFA (3090)** | ~2-3 ms (claim NVIDIA) | silicio dedicado |
| **DIS (OpenCV CPU)** | ~1.7 ms @1024x436, 1 core | libera la GPU |
| Farnebäck | ~8 ms CPU / 31 ms GPU | |
| NeuFlow v2 | ~15 ms en RTX 2080 | no se justifica |
| TV-L1 | >300 ms CPU | descartado |

**No existe modelo dedicado de crowd flow maduro con pesos y latencia demostrada.** La práctica es componer densidad x flujo genérico. El benchmark CrowdFlow documenta un techo duro: ningún algoritmo supera 76% de tracking accuracy en trayectorias densas.

Receta: flujo denso (NVOFA o DIS) -> promedio ponderado por densidad -> vector global + divergencia (expansión/compresión de la masa).

## 5. Generalización sin fine-tune — el riesgo real

Cross-dataset estricto, baseline DM-Count:

| Transferencia | MAE | vs in-domain |
|---|---|---|
| QNRF -> SHA | 73.4 | **~1.23x** (la mejor) |
| QNRF -> SHB | 14.3 | ~1.9x |
| SHA -> SHB | 23.1 | ~3x |
| SHB -> SHA | 143.9 | ~2.4x |
| SHB -> QNRF | 203.0 | ~2.4x |
| SHA -> NWPU | 146.9 (MSE 563.8) | catastrófico |

Degradación 1.5-3x, asimétrica. El MSE desproporcionado indica que fuera de distribución el modelo ocasionalmente delira. **QNRF y NWPU generalizan mejor; ShanghaiTech A es el peor source** — y es el checkpoint por defecto de la mayoría de los repos.

**Downscaling: el factor dominante** (SasNet sobre ShanghaiTech, original 1024x768):

| Escala | MAE | | Calidad JPEG | MAE |
|---|---|---|---|---|
| 100% | 6.35 | | q=75 | 6.35 |
| 80% | 7.55 | | q=30 | 6.80 |
| 70% | 9.02 | | q=15 | 8.10 |
| 60% | 10.74 | | q=5 | 13.67 |

Conclusión textual del paper: *"decreasing resolution has a much higher impact than decreasing image quality"*. Caveat que empeora todo: en cada punto de esa curva **fine-tunearon 100 épocas sobre las imágenes degradadas**. Son números del mejor caso con adaptación.

640x360 = ~62% de ancho / ~47% de alto del baseline: **debajo del codo**, sin adaptación, con domain shift, cabezas de ~10 px (100 px2) contra ~36 px2 donde los detectores pierden features. **Cuatro degradaciones acumuladas que nadie midió juntas.**

**Zero-shot no salva**: CrowdCLIP y CLIP-Count sobre imagen con GT=177 predicen 780 y 673. SAM con resolución adaptativa: SHA 102.6 / QNRF 182.3 (~2x peor que supervisado), y su truco es zoomear, que a 640x360 no hay.

**No se encontró ningún deployment industrial de density-map sobre video de conciertos con cámara en mano.** Los despliegues documentados en festivales usan RF/Wi-Fi sensing o visión estéreo.

## 6. Detección tileada (SAHI) vs density maps

SAHI: sin ningún trabajo que lo use para crowd counting ni comparación contra density maps; vive en small object detection aéreo. +5-7% AP a costa de N forward passes; reportes de usuarios hablan de segundos por imagen. Con 30 ms hay margen para 2-3 tiles, no para 9-16.

**Evidencia directa de que la detección colapsa — benchmark HAJJv2-CrowdCount** (video real de Hajj, 167 frames anotados a mano, 56 a ~1700 personas/frame). El dato más valioso del informe por ser evaluación zero-shot honesta sobre video de campo:

| Modelo | MAE global | MAE en banda densa (300-1000) |
|---|---|---|
| SAM3Count (segmentación) | **70.4** | >300 |
| YOLO-World (detección) | 92.0 | >300 |
| APGCC (point-based) | 152.9 | **114.9** |

**El ranking se invierte en régimen denso.** Textualmente sobre YOLO-World: *"misses small background figures below its resolution limit"*. Valida la arquitectura: el `CrowdAggregator` sobre YOLO está bien para ralo-medio y va a mentir en el pogo denso.

Detectores de cabezas listos si se quiere mejorar la rama de detección: `Owen718/Head-Detection-Yolov8` (CrowdHuman), `Abcfsa/YOLOv8_head_detector` (SCUT-HEAD).

## 7. Recomendación

**Probar primero: ZIP (Nano o Tiny), checkpoint UCF-QNRF o NWPU-Crowd.** `github.com/Yiming-M/ZIP` — MIT, pesos completos, activo, demo en HF para validar en 10 minutos.

1. Único con MIT + pesos completos + MobileNetV4 (exportable vía timm) + SOTA real.
2. Salida nativa = campo espacial -> centroide, dispersión y flujo como momentos.
3. Mapa pi = máscara de masa gratis.
4. Margen de latencia de 1-2 órdenes.
5. **Checkpoint QNRF o NWPU, nunca ShanghaiTech A** (única decisión con evidencia cuantitativa: QNRF->SHA degrada solo 1.23x).

**Segundo: CLIP-EBC** como control. Si ZIP-Nano y CLIP-EBC coinciden en nuestro video, hay confianza; si divergen, estamos fuera de distribución.

**Flujo: NVOFA vía `cv2.cuda.NvidiaOpticalFlow_2_0`**, fallback DIS en CPU.

**Antes de nada — el paso que no es opcional: anotar manualmente 30-50 frames de material propio.** No para fine-tune: para saber si el error es del 20% o del 300%. Sin eso no hay forma de distinguir "estoy midiendo densidad" de "estoy modulando ruido". Media jornada, decide el GO/NO-GO.

**Mitigación de resolución:** trabajar a máxima resolución nativa, no 640x360. Si la fuente es genuinamente 640x360, upscalear al mínimo de entrenamiento (min edge >= 448): no recupera información pero evita salirse del régimen del modelo.

## 8. Riesgos

1. **Resolución (alto).** Cuatro degradaciones acumuladas sin medición conjunta.
2. **Saltos de conteo entre frames (medio).** Modelos por-frame sin coherencia temporal; con domain shift, MSE alto indica outliers catastróficos ocasionales. **Para modular audio es fatal.** Mitigación obligatoria: filtro temporal (mediana + EMA o Kalman 1D) y clamp de tasa de cambio.
3. **Cámara en mano (medio).** El flujo óptico mediría movimiento de cámara. Mitigación: restar ego-motion (homografía sobre fondo, o excluir zonas de masa vía mapa pi). El repo ya tiene GMC en modo grupo, probablemente reutilizable.
4. **Sin benchmark de referencia (alto, irreducible).** No existe dataset de recital/pogo con cámara en mano. Documentar como limitación.
5. **Escala absoluta no calibrable.** Mitigación de diseño: **normalizar contra percentil rodante de la propia sesión**. Para modular música importa la dinámica relativa.

## 9. Qué NO vale la pena

- **CrowdDiff**: difusión multi-hipótesis, incompatible con tiempo real.
- **SAHI / slicing**: N forward passes, sin precedente en conteo.
- **P2PNet**: licencia limita a *"only for the purpose of academic research"* pese a aparentar BSD; GitHub lo marca NOASSERTION. Excluido.
- **CSRNet (repo leeyeehoo)**: sin LICENSE = todos los derechos reservados; además Python 2.7 / PyTorch 0.4. Reimplementable desde el paper (VGG16 + dilated conv).
- **LIMM**: repo vacío.
- **STEERER**: MIT y buenos pesos, pero HRNet + MMCV + extensión nativa; fricción desproporcionada.
- **CrowdCLIP / CLIP-Count / SAM zero-shot**: errores de 4x.
- **Optical flow deep (RAFT, NeuFlow, SEA-RAFT)**: precisión sub-pixel irrelevante para movimiento agregado, teniendo NVOFA ocioso.
- **CLTR / DM-Count como opción principal**: DM-Count sirve de baseline exportable; CLTR abandonado desde 2023.

## Nota de arquitectura

Lo que hay en `crowd.py` no se tira. La lectura más sólida de la evidencia (HAJJv2, §6) es un **régimen doble**: detección/pose para densidad baja-media (donde funciona y además da identidad), density map para densidad alta (donde la detección colapsa). Precedente publicado: DecideNet (arXiv 1712.06679), que combina ambas ramas con atención porque cada una gana en un régimen distinto. Aquí el switch puede ser más simple: cruzar al mapa de densidad cuando el conteo de detecciones supera un umbral, con banda de histéresis y crossfade para que la señal OSC no salte.
