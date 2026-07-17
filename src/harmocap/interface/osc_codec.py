"""osc_codec — codec OSC 1.0 canónico de HarMoCAP. SOLO biblioteca estándar.

ESTE ARCHIVO ES EL ÚNICO ENCODER/DECODER DEL CONTRATO (autoauditoría #3).
`scripts/build_nico_kit.py` lo copia IDÉNTICO al kit portable; los golden
vectors verifican igualdad byte a byte entre pipeline y kit. No importar aquí
nada fuera de la stdlib (el kit corre sin numpy/scipy/ultralytics).

Implementa:
- Mensajes y bundles OSC 1.0 (encode/decode) con typetags i,f,s,b,h,d.
- Layouts binarios normativos de los blobs (big-endian, r3 #3):
    keypoints    : 17 × struct(">fff")   (x_iso, y_iso, conf)          = 204 B
    kp_state     : 17 × struct(">BIQ")   (estado, age_frames, age_us)  = 221 B
    features     : struct(">21f")        (orden canónico)              =  84 B
    feat_state   : struct(">21B")                                      =  21 B
    calibration  : struct(">6f")         (CALIBRATION_PARAM_ORDER)     =  24 B
- Hashes normativos (r6 #7, r7 #5, r7 #6): SHA-256 truncado a 128 bits hex.
- Construcción del bundle por-frame, /hello y /calibration del contrato v1.

Sistema de coordenadas (addendum #2): x_iso = x_px/frame_h, y_iso = y_px/frame_h,
origen arriba-izquierda, x→derecha, y→abajo, sin espejo.
"""
from __future__ import annotations

import hashlib
import json
import struct

OSC_NAMESPACE = "/harmocap/v1"
LAYOUT_VERSION = "1"
N_KEYPOINTS = 17
N_FEATURES = 21
N_CALIB_PARAMS = 6
MAX_DATAGRAM_BYTES = 1200  # aserción ejecutable (r8 #8)

_IMMEDIATELY = b"\x00\x00\x00\x00\x00\x00\x00\x01"  # timetag OSC "immediately"

# --------------------------------------------------------------------------
# OSC 1.0 primitivas (stdlib pura)
# --------------------------------------------------------------------------

def _pad4(b: bytes) -> bytes:
    return b + b"\x00" * ((4 - len(b) % 4) % 4)


def _enc_string(s: str) -> bytes:
    return _pad4(s.encode("utf-8") + b"\x00")


def _enc_blob(b: bytes) -> bytes:
    return struct.pack(">i", len(b)) + _pad4(b)


def encode_message(address: str, args: list) -> bytes:
    """Codifica un mensaje OSC. Tipos: int→i, float→f, str→s, bytes→b,
    ('h', int)→int64, ('d', float)→float64."""
    typetags = ","
    payload = b""
    for a in args:
        if isinstance(a, tuple):
            tag, val = a
            if tag == "h":
                typetags += "h"
                payload += struct.pack(">q", val)
            elif tag == "d":
                typetags += "d"
                payload += struct.pack(">d", val)
            else:
                raise ValueError(f"tag no soportado: {tag}")
        elif isinstance(a, bool):
            raise ValueError("bool no permitido: usar int explícito")
        elif isinstance(a, int):
            typetags += "i"
            payload += struct.pack(">i", a)
        elif isinstance(a, float):
            typetags += "f"
            payload += struct.pack(">f", a)
        elif isinstance(a, str):
            typetags += "s"
            payload += _enc_string(a)
        elif isinstance(a, (bytes, bytearray)):
            typetags += "b"
            payload += _enc_blob(bytes(a))
        else:
            raise ValueError(f"tipo no soportado: {type(a)}")
    return _enc_string(address) + _enc_string(typetags) + payload


def encode_bundle(messages: list[bytes], timetag: bytes = _IMMEDIATELY) -> bytes:
    """Bundle OSC atómico con timetag `immediately` (r4 #6)."""
    out = _enc_string("#bundle") + timetag
    for m in messages:
        out += struct.pack(">i", len(m)) + m
    return out


def _dec_string(data: bytes, ofs: int) -> tuple[str, int]:
    end = data.index(b"\x00", ofs)
    s = data[ofs:end].decode("utf-8")
    ofs = end + 1
    ofs += (4 - ofs % 4) % 4
    return s, ofs


def decode_message(data: bytes) -> tuple[str, list]:
    address, ofs = _dec_string(data, 0)
    typetags, ofs = _dec_string(data, ofs)
    args: list = []
    for tag in typetags[1:]:
        if tag == "i":
            args.append(struct.unpack_from(">i", data, ofs)[0]); ofs += 4
        elif tag == "f":
            args.append(struct.unpack_from(">f", data, ofs)[0]); ofs += 4
        elif tag == "h":
            args.append(struct.unpack_from(">q", data, ofs)[0]); ofs += 8
        elif tag == "d":
            args.append(struct.unpack_from(">d", data, ofs)[0]); ofs += 8
        elif tag == "s":
            s, ofs = _dec_string(data, ofs); args.append(s)
        elif tag == "b":
            n = struct.unpack_from(">i", data, ofs)[0]; ofs += 4
            args.append(data[ofs:ofs + n]); ofs += n + (4 - n % 4) % 4
        else:
            raise ValueError(f"typetag no soportado: {tag}")
    return address, args


def decode_bundle(data: bytes) -> list[tuple[str, list]]:
    """Decodifica un bundle (o un mensaje suelto) a [(address, args), ...]."""
    if not data.startswith(b"#bundle\x00"):
        return [decode_message(data)]
    ofs = 8 + 8  # '#bundle\0' + timetag
    out = []
    while ofs < len(data):
        n = struct.unpack_from(">i", data, ofs)[0]; ofs += 4
        out.append(decode_message(data[ofs:ofs + n])); ofs += n
    return out


# --------------------------------------------------------------------------
# Blobs normativos (big-endian; golden vectors en tests)
# --------------------------------------------------------------------------

def pack_keypoints(kps: list[tuple[float, float, float]]) -> bytes:
    """17 × (x_iso, y_iso, conf) float32 big-endian."""
    if len(kps) != N_KEYPOINTS:
        raise ValueError(f"esperaba {N_KEYPOINTS} keypoints, recibí {len(kps)}")
    return b"".join(struct.pack(">fff", x, y, c) for x, y, c in kps)


def unpack_keypoints(blob: bytes) -> list[tuple[float, float, float]]:
    if len(blob) != N_KEYPOINTS * 12:
        raise ValueError(f"blob keypoints: longitud {len(blob)} != {N_KEYPOINTS*12}")
    return [struct.unpack_from(">fff", blob, i * 12) for i in range(N_KEYPOINTS)]


def pack_kp_state(states: list[tuple[int, int, int]]) -> bytes:
    """17 × (estado uint8, age_frames uint32, age_us uint64) big-endian."""
    if len(states) != N_KEYPOINTS:
        raise ValueError(f"esperaba {N_KEYPOINTS} estados")
    return b"".join(struct.pack(">BIQ", s, af, au) for s, af, au in states)


def unpack_kp_state(blob: bytes) -> list[tuple[int, int, int]]:
    size = struct.calcsize(">BIQ")
    if len(blob) != N_KEYPOINTS * size:
        raise ValueError(f"blob kp_state: longitud {len(blob)} != {N_KEYPOINTS*size}")
    return [struct.unpack_from(">BIQ", blob, i * size) for i in range(N_KEYPOINTS)]


def pack_features(values: list[float]) -> bytes:
    """K floats en orden canónico. Feature invalid → sentinel 0.0 (r5 #5); el
    receptor DEBE ignorar el valor cuando feat_state=INVALID. Nunca NaN."""
    if len(values) != N_FEATURES:
        raise ValueError(f"esperaba {N_FEATURES} features")
    for v in values:
        if v != v:  # NaN check sin math
            raise ValueError("NaN prohibido en el wire (r4 #14)")
    return struct.pack(f">{N_FEATURES}f", *values)


def unpack_features(blob: bytes) -> list[float]:
    if len(blob) != N_FEATURES * 4:
        raise ValueError(f"blob features: longitud {len(blob)} != {N_FEATURES*4}")
    return list(struct.unpack(f">{N_FEATURES}f", blob))


def pack_feat_state(states: list[int]) -> bytes:
    if len(states) != N_FEATURES:
        raise ValueError(f"esperaba {N_FEATURES} estados de feature")
    return struct.pack(f">{N_FEATURES}B", *states)


def unpack_feat_state(blob: bytes) -> list[int]:
    if len(blob) != N_FEATURES:
        raise ValueError("blob feat_state: longitud incorrecta")
    return list(struct.unpack(f">{N_FEATURES}B", blob))


def pack_calibration_params(params: list[float]) -> bytes:
    if len(params) != N_CALIB_PARAMS:
        raise ValueError(f"esperaba {N_CALIB_PARAMS} parámetros de calibración")
    return struct.pack(f">{N_CALIB_PARAMS}f", *params)


def unpack_calibration_params(blob: bytes) -> list[float]:
    if len(blob) != N_CALIB_PARAMS * 4:
        raise ValueError("blob calibration: longitud incorrecta")
    return list(struct.unpack(f">{N_CALIB_PARAMS}f", blob))


# --------------------------------------------------------------------------
# Hashes normativos (r6 #7, r7 #5, r7 #6)
# --------------------------------------------------------------------------

def canonical_json_hash(obj: dict, exclude_keys: tuple[str, ...] = ()) -> str:
    """SHA-256 truncado a 128 bits hex sobre JSON canónico (claves ordenadas,
    sin espacios, sin NaN/Inf, UTF-8). exclude_keys se quitan antes (sin
    autorreferencia: contract_id, golden_hash, expected_contract_id)."""
    clean = {k: v for k, v in obj.items() if k not in exclude_keys}
    payload = json.dumps(clean, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def contract_id_from_manifest(manifest: dict) -> str:
    return canonical_json_hash(
        manifest, exclude_keys=("contract_id", "golden_hash", "expected_contract_id"))


def calibration_hash(params_blob: bytes) -> str:
    """Sobre los BYTES normativos del blob + descriptor de layout (r7 #5)."""
    descriptor = f"calibration:v{LAYOUT_VERSION}:>{N_CALIB_PARAMS}f".encode()
    return hashlib.sha256(descriptor + params_blob).hexdigest()[:32]


# --------------------------------------------------------------------------
# Construcción de los paquetes del contrato v1
# --------------------------------------------------------------------------

def build_hello(*, stream_id: str, schema_version: str, feature_set_version: str,
                producer_version: str, model_id: str, config_hash: str,
                contract_id: str, calibration_generation: int,
                calibration_state: str, calib_hash: str,
                effective_from_frame_id: int, frame_w: int, frame_h: int) -> bytes:
    """/hello: identidad del contrato + identidad de calibración. Cabe en 1
    datagrama (los órdenes se derivan del manifiesto vía contract_id, r6 #2).
    frame_w/frame_h viajan aquí (addendum #2)."""
    msg = encode_message(f"{OSC_NAMESPACE}/hello", [
        stream_id, schema_version, feature_set_version, producer_version,
        model_id, config_hash, contract_id, LAYOUT_VERSION,
        calibration_generation, calibration_state, calib_hash,
        ("h", effective_from_frame_id), frame_w, frame_h,
    ])
    return encode_bundle([msg])


def build_calibration(*, stream_id: str, generation: int, calib_hash: str,
                      effective_from_frame_id: int, params_blob: bytes) -> bytes:
    """/calibration: los PARÁMETROS viven exclusivamente aquí (r7 #1)."""
    msg = encode_message(f"{OSC_NAMESPACE}/calibration", [
        stream_id, generation, calib_hash, ("h", effective_from_frame_id), params_blob,
    ])
    return encode_bundle([msg])


def build_frame_bundle(*, stream_id: str, captured_frame_id: int, bundle_seq: int,
                       n_persons: int, fps: float, contract_id: str,
                       calibration_generation: int, calibration_state: str,
                       captured_at_us: int, processed_at_us: int,
                       queued_for_send_at_us: int,
                       persons: list[dict]) -> bytes:
    """Bundle atómico por frame. persons: [{slot_id, present, keypoints_blob,
    kp_state_blob, bbox(4 floats), features_blob, feat_state_blob}].
    Tombstone (present=0): SOLO el mensaje present (r4 #11)."""
    msgs = [encode_message(f"{OSC_NAMESPACE}/meta", [
        stream_id, ("h", captured_frame_id), ("h", bundle_seq), n_persons,
        float(fps), contract_id, calibration_generation, calibration_state,
        ("h", captured_at_us), ("h", processed_at_us), ("h", queued_for_send_at_us),
    ])]
    for p in persons:
        base = f"{OSC_NAMESPACE}/person/{p['slot_id']}"
        if not p["present"]:
            msgs.append(encode_message(f"{base}/present", [0]))
            continue
        msgs.append(encode_message(f"{base}/present", [1]))
        msgs.append(encode_message(f"{base}/keypoints", [p["keypoints_blob"]]))
        msgs.append(encode_message(f"{base}/kp_state", [p["kp_state_blob"]]))
        msgs.append(encode_message(f"{base}/bbox", [float(v) for v in p["bbox"]]))
        msgs.append(encode_message(f"{base}/features", [p["features_blob"]]))
        msgs.append(encode_message(f"{base}/feat_state", [p["feat_state_blob"]]))
    bundle = encode_bundle(msgs)
    if len(bundle) > MAX_DATAGRAM_BYTES:
        raise ValueError(
            f"bundle {len(bundle)} B > {MAX_DATAGRAM_BYTES} B (r8 #8): revisar K/persons")
    return bundle
