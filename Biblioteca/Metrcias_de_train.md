  Cómo leería los losses para este proyecto

  La clave: nuestro consumidor final no es un benchmark — es la capa de features de movimiento y la máquina de estados observed/held/invalid. Eso cambia qué loss importa:

  1. val/pose_loss es el proxy #1. Es error de localización de keypoints en el set de oclusión/multitud — exactamente lo que las features consumen (ángulos, velocidades, simetría se degradan con error de
  localización, no con error de bbox). En ft2 bajó monótono 0.961→0.897: eso es lo que valida el run para nuestro caso, más que el mAP en sí. Además el loss se mueve antes que el mAP y por iteración — fue
  el smoking gun del run roto (train pose_loss subiendo era la degradación visible en tiempo real).
  2. val/kobj_loss es el proxy #2, y está subvalorado. Es la calidad de la confianza por keypoint — el input directo de nuestra máquina observed→held→invalid y del campo conf que Nico recibe. Un kobj mal
  calibrado = estados de validez mentirosos = features contaminadas con hold-last incorrectos. En ft2: 0.476→0.297, mejora fuerte — significa que el modelo fine-tuneado sabe mejor cuándo no sabe, que para
  un sistema en vivo con oclusión vale tanto como la precisión misma.
  3. box/cls/dfl importan solo vía tracking: estabilidad de cajas → estabilidad de IDs de ByteTrack → estabilidad de slots. Con box mAP50 0.88 estable, no son el cuello. Los miraría solo si aparecieran ID
  switches en producción.
  4. La brecha train↔val como alarma de dominio: nuestro riesgo real es sobreajustar a CrowdPose y degradar el dominio general (fue exactamente el problema de ft1). La brecha creciente en pose_loss sería
  la señal temprana — antes de pagar un eval COCO completo.
  5. Lo que los losses NO te dan (y propondría para el hito siguiente): son promedios sobre los 17 keypoints, pero nuestras features pesan desproporcionadamente muñecas y torso (velocidad de manos,
  verticalidad, contracción). Un eval custom con OKS por-keypoint (error en muñecas vs. error en orejas) sería la métrica más indicativa de todas para este proyecto — barata de armar sobre el harness de
  eval que ya tenemos.

  En síntesis: para perseguir los objetivos de HarMoCAP, ordenaría el tablero así: val/pose_loss (localización bajo oclusión) → val/kobj_loss (honestidad de la confianza) → brecha train/val (deriva de
  dominio) → box solo si el tracking molesta; y como próxima inversión, OKS por-keypoint con foco en muñecas.