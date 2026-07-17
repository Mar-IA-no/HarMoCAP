"""Contrato de datos de HarMoCAP — MovementFrame inmutable + órdenes canónicos.

Fuente de verdad del contrato de wire: schemas/osc_contract.v1.json (manifiesto).
Este módulo define las dataclasses y constantes que TODO el pipeline comparte.

Decisiones de diseño (plan v10 + addendum):
- MovementFrame es INMUTABLE (r2 #2): la telemetría de envío vive en TransportEnvelope.
- Coordenadas ISOTRÓPICAS (addendum #2): x_iso = x_px/frame_h, y_iso = y_px/frame_h.
  Origen arriba-izquierda, x→derecha, y→abajo, SIN espejo.
- stream_id por arranque (addendum #1): scoping de seq/lease/tombstone/generaciones.
- captured_frame_id (con huecos por drops) ≠ bundle_seq (cuenta emisiones) (addendum #5).
- Estados por keypoint y por feature: {observed, held, invalid}; 'imputed' RESERVADO v1.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import IntEnum

SCHEMA_VERSION = "1.0.0"
FEATURE_SET_VERSION = "1.0.0"
LAYOUT_VERSION = "1"
PRODUCER_VERSION = "0.1.0"
OSC_NAMESPACE = "/harmocap/v1"

# Orden canónico COCO-17 (idéntico al de YOLO-pose / COCO keypoints).
KEYPOINT_ORDER: tuple[str, ...] = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
)
N_KEYPOINTS = len(KEYPOINT_ORDER)  # 17

# Orden canónico de features v1 (K=21). Los agregados _mean/_mad/_max se calculan
# internamente pero NO viajan en v1 (acotado por MTU, r4 #2); sumarlos al wire
# requiere bump de FEATURE_SET_VERSION. Nombres Laban con sufijo _proxy (addendum #7):
# son operacionalizaciones cinemáticas, no mediciones Laban canónicas.
FEATURE_ORDER: tuple[str, ...] = (
    "qom", "contraction", "expansion",
    "vel_hand_l", "vel_hand_r", "vel_center",
    "smoothness_l", "smoothness_r",
    "symmetry", "verticality",
    "angle_elbow_l", "angle_elbow_r", "angle_knee_l", "angle_knee_r",
    "angle_shoulder_l", "angle_shoulder_r", "angle_hip_l", "angle_hip_r",
    "laban_weight_proxy", "laban_time_proxy", "laban_space_proxy",
)
N_FEATURES = len(FEATURE_ORDER)  # 21

# Rangos/polaridad documentados (también en el manifiesto y en INTERFACE_SPEC.md).
FEATURE_RANGES: dict[str, tuple[float, float]] = {
    **{name: (0.0, 1.0) for name in FEATURE_ORDER},
    "verticality": (-1.0, 1.0),
}


class KpState(IntEnum):
    """Estado por keypoint y por feature. 'imputed'=3 RESERVADO, no se emite en v1."""
    OBSERVED = 0
    HELD = 1
    INVALID = 2
    _RESERVED_IMPUTED = 3


class CalibrationState:
    CALIBRATING = "calibrating"
    FROZEN = "frozen"


def new_stream_id() -> str:
    """Identidad de instancia del stream: aleatoria por arranque del proceso (addendum #1)."""
    return secrets.token_hex(8)  # 64 bits hex


@dataclass(frozen=True)
class KeypointData:
    """Un keypoint en coordenadas isotrópicas + estado de validez."""
    x: float            # x_px / frame_h  (rango [0, frame_w/frame_h])
    y: float            # y_px / frame_h  (rango [0, 1])
    conf: float         # confiabilidad EFECTIVA causal: = conf YOLO solo en OBSERVED (r6 #5)
    state: int          # KpState
    age_frames: int     # frames desde la última observación real
    age_us: int         # microsegundos desde la última observación real


@dataclass(frozen=True)
class PersonState:
    """Estado emitible de una persona (slot estable, no track_id efímero)."""
    slot_id: int
    present: bool
    keypoints: tuple[KeypointData, ...]          # len == N_KEYPOINTS si present
    bbox: tuple[float, float, float, float]      # xc, yc, w, h normalizados (boxes.xywhn)
    features: tuple[float, ...]                  # len == N_FEATURES, orden FEATURE_ORDER
    feature_states: tuple[int, ...]              # len == N_FEATURES, KpState por feature
    provisional: bool = False                    # True durante calibration_state=calibrating


@dataclass(frozen=True)
class CalibrationProfile:
    """Perfil de calibración por generación (r5 #4, r6 #1, r7 #4).

    params en ORDEN CANÓNICO del manifiesto (CALIBRATION_PARAM_ORDER).
    El hash se calcula sobre los bytes normativos del blob (r7 #5) — ver osc_codec.
    """
    generation: int
    state: str                       # CalibrationState
    effective_from_frame_id: int
    params: tuple[float, ...]        # len == len(CALIBRATION_PARAM_ORDER)


CALIBRATION_PARAM_ORDER: tuple[str, ...] = (
    "torso_height_norm", "vmax_hand", "vmax_center", "jerk_ref", "energy_ref", "accel_ref",
)


@dataclass(frozen=True)
class MovementFrame:
    """Frame INMUTABLE del contrato. Es lo que se serializa a OSC y a .jsonl.

    No contiene sent_at (r4 #5, r5 #1): el instante de envío real vive en
    TransportEnvelope, del lado del emisor.
    """
    stream_id: str
    captured_frame_id: int       # con huecos por drops (addendum #5)
    captured_at_us: int          # reloj monótono, µs
    processed_at_us: int
    frame_w: int                 # tamaño del frame original (addendum #2)
    frame_h: int
    fps: float
    calibration_generation: int
    calibration_state: str
    persons: tuple[PersonState, ...]

    @property
    def n_persons(self) -> int:
        """Slots emitidos con present=True (addendum #5), no detecciones brutas."""
        return sum(1 for p in self.persons if p.present)


@dataclass
class TransportEnvelope:
    """Telemetría del emisor, separada del frame inmutable (r5 #2)."""
    bundle_seq: int              # cuenta EMISIONES (mide pérdida UDP, addendum #5)
    queued_for_send_at_us: int
    sent_at_us: int = 0
    wire_bytes: int = 0
