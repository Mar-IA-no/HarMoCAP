# DATASET_ROADMAP — hacia un dataset más grande que coco8-pose (plan M5)

> Exploración para el hito de fine-tuning POSTERIOR al MVP. En este MVP no se
> entrena con datasets grandes. Fuentes: pack de investigación
> `editorial-altermundi/Biblioteca/yolo-pose-a-modulacion-sonora-tiempo-real/`
> (QUANTITATIVE_DATA §6, CROSS_REPORT §G.3), verificar licencias caso a caso
> antes de usar.

## Clasificación por licencia (r2 #14)

### Aptos para producto (verificados en el pack)

| Dataset | Licencia | Qué aporta | Compatibilidad de esqueleto |
|---|---|---|---|
| **CrowdPose** | CC BY 4.0 | ~20k imágenes multi-persona con oclusión — el caso difícil de HarMoCAP | ⚠️ **14 keypoints** (no COCO-17): requiere mapeo semántico + conversión de labels + `kpt_shape` propio |
| **AIST++** | CC BY 4.0 | ~5.2 h de **danza multi-vista con música alineada** — la joya para movimiento expresivo | ⚠️ formato SMPL 3D, NO labels YOLO: pipeline de conversión (proyección 2D + formato YOLO-pose) |

### Candidatos pendientes de revisión asset-level

| Dataset | Problema | Uso posible |
|---|---|---|
| **COCO-Pose completo** (~57k img, 17 kp) | anotaciones CC BY, pero **imágenes bajo Flickr ToU** (zona gris comercial) | fine-tuning interno de investigación; para producto revisar asset-level |
| **Roboflow Universe** (varios) | licencias mixtas por dataset (CC BY / Public Domain / otras); calidad variable (auto-anotados) | formato YOLO-pose DIRECTO (cero conversión); shortlist candidata a armar cuando se defina el dominio (escena, iluminación) |
| **Kaggle** | los mirrors NO cambian la licencia original (MPII sigue siendo no-comercial en Kaggle) | verificar por dataset |

### Descartados para producto (no-comerciales, del pack)

MPII · COCO-WholeBody · Halpe · Human3.6M · MPI-INF-3DHP · AMASS · HumanML3D ·
Motion-X (mixta → tratar como no comercial) · AGORA (asumido).

## Compatibilidad de esqueletos (r8 #11 — `flip_idx` solo NO alcanza)

Antes de cualquier fine-tuning con un dataset nuevo, auditar:

1. **`kpt_shape`**: COCO=17×3; CrowdPose=14; decidir si se convierte al
   esqueleto COCO-17 (recomendado: el contrato v1 está fijado en 17) o se
   reentrena la head con otro `kpt_shape` (rompería el contrato → bump mayor).
2. **Mapeo semántico**: qué keypoint del dataset corresponde a cuál de los 17
   (documento de mapeo por dataset; los no mapeables → visibilidad 0).
3. **`flip_idx`**: reescribir la lista de espejos L/R para el orden final
   (crítico: sin él, `fliplr` augmenta mal — pack §B.4).
4. **Head de pose + conversión de labels**: generar labels formato YOLO-pose
   (`class cx cy w h kpt…` normalizado) y validar visualmente una muestra.

## Plan de fine-tuning propuesto (hito posterior, GO/NO-GO del usuario)

1. **Definir el dominio objetivo** (escena Beacon: interior, 1-4 personas,
   cámara fija frontal) y grabar un set propio de validación (~200 frames
   anotados) — la métrica que importa es EN NUESTRO dominio.
2. **Baseline**: yolo26m-pose COCO-pretrained (el actual) medido sobre ese set.
3. **Ronda 1**: fine-tune con CrowdPose convertido (mejora esperada: oclusión
   multi-persona). Transfer desde los pesos COCO, `flip_idx` auditado.
4. **Ronda 2 (opcional)**: augmentación con clips AIST++ proyectados si el
   dominio es danza/movimiento expresivo.
5. Comparar SIEMPRE contra el baseline en el set propio; decisión GO/NO-GO del
   usuario con números (protocolo `validate-hyperparams` para comparabilidad).
