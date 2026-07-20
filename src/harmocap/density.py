"""Conteo de masa por mapa de densidad (H6, contrato 1.4) — backend ONNX.

Complementa la rama de detección del modo masa: donde la gente es chica y
numerosa, la detección deja de encontrarla (medido: YOLO ve 4 personas donde
hay ~70) y el mapa de densidad la localiza. Corre con onnxruntime + numpy, sin
torch ni el paquete de ZIP.

Emite dos señales sobre la masa (decisión de diseño A+C del usuario):
  - masa PRESENTE : conteo total del mapa de densidad — toda la gente en cuadro.
  - masa ACTIVA   : densidad ponderada por movimiento local — cuánta de esa masa
                    se mueve. Separa "hay mucha gente" de "la gente se agita",
                    que para modular sonido son cosas distintas.

El movimiento local se estima por diferencia de cuadros (causal, sin flujo
óptico): |I_t - I_{t-1}| agrupado a la grilla del mapa. No distingue dirección
—eso lo dará el flujo en una iteración posterior— pero sí magnitud de agitación.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
_BLOCK = 32          # el mapa de densidad de ZIP submuestrea por 32


class DensityBackend:
    """Envuelve el ONNX de densidad. Devuelve el mapa crudo por cuadro."""

    def __init__(self, onnx_path: str | Path, providers: list[str] | None = None,
                 min_edge: int = 448):
        import onnxruntime as ort
        self.min_edge = min_edge      # no bajar de acá: la resolución degrada el modelo
        prov = providers or (["CUDAExecutionProvider", "CPUExecutionProvider"]
                             if "CUDAExecutionProvider" in ort.get_available_providers()
                             else ["CPUExecutionProvider"])
        self.session = ort.InferenceSession(str(onnx_path), providers=prov)
        self.input_name = self.session.get_inputs()[0].name
        self.provider = self.session.get_providers()[0]

    def infer(self, rgb: np.ndarray) -> np.ndarray:
        """rgb: HxWx3 uint8. Devuelve el mapa de densidad (dh x dw) float32."""
        h, w = rgb.shape[:2]
        scale = max(self.min_edge / min(h, w), 1.0)
        if scale > 1.0:
            import cv2
            rgb = cv2.resize(rgb, (round(w * scale), round(h * scale)),
                             interpolation=cv2.INTER_CUBIC)
            h, w = rgb.shape[:2]
        ph, pw = (_BLOCK - h % _BLOCK) % _BLOCK, (_BLOCK - w % _BLOCK) % _BLOCK
        if ph or pw:
            rgb = np.pad(rgb, ((0, ph), (0, pw), (0, 0)))
        x = rgb.astype(np.float32).transpose(2, 0, 1) / 255.0
        x = ((x - _MEAN) / _STD)[None]
        out = self.session.run(None, {self.input_name: x})[0]
        return np.asarray(out).squeeze().astype(np.float32)
