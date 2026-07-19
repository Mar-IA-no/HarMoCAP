"""M4 — contrato de wire: round-trips, golden vectors, tamaños, interop (plan M4)."""
import json
import math
import struct
from pathlib import Path

import pytest

from harmocap.interface import osc_codec
from harmocap.schema import N_FEATURES, N_KEYPOINTS

REPO = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((REPO / "schemas" / "osc_contract.v1.json").read_text())


# ---------------------------------------------------------------- golden vectors
def test_golden_vector_keypoints():
    kps = [(i * 0.1, i * 0.05, 0.9) for i in range(N_KEYPOINTS)]
    blob = osc_codec.pack_keypoints(kps)
    assert len(blob) == 204
    # golden: primer registro conocido byte a byte
    assert blob[:12] == struct.pack(">fff", 0.0, 0.0, 0.9)
    out = osc_codec.unpack_keypoints(blob)
    for (x, y, c), (x2, y2, c2) in zip(kps, out):
        assert x2 == pytest.approx(x, abs=1e-6)
        assert c2 == pytest.approx(c, abs=1e-6)


def test_golden_vector_kp_state():
    st = [(1, 5, 123_456)] * N_KEYPOINTS
    blob = osc_codec.pack_kp_state(st)
    assert len(blob) == N_KEYPOINTS * 13 == 221
    assert blob[:13] == struct.pack(">BIQ", 1, 5, 123_456)
    assert osc_codec.unpack_kp_state(blob) == st


def test_golden_vector_features_and_state():
    vals = [i / N_FEATURES for i in range(N_FEATURES)]
    blob = osc_codec.pack_features(vals)
    assert len(blob) == 84
    out = osc_codec.unpack_features(blob)
    assert out == pytest.approx(vals, abs=1e-6)
    st = [0, 1, 2] * 7
    assert osc_codec.unpack_feat_state(osc_codec.pack_feat_state(st)) == st


def test_nan_rejected_in_wire():
    vals = [0.0] * N_FEATURES
    vals[3] = float("nan")
    with pytest.raises(ValueError, match="NaN"):
        osc_codec.pack_features(vals)


# ---------------------------------------------------------------- OSC round-trip
def _person_wire(slot=0, focused=True):
    return {
        "slot_id": slot, "present": True, "focused": focused,
        "keypoints_blob": osc_codec.pack_keypoints(
            [(0.5, 0.5, 0.9)] * N_KEYPOINTS),
        "kp_state_blob": osc_codec.pack_kp_state(
            [(0, 4_000_000, 4_000_000_000)] * N_KEYPOINTS),  # peor caso: valores grandes
        "bbox": [0.5, 0.5, 0.3, 0.8],
        "features_blob": osc_codec.pack_features([0.5] * N_FEATURES),
        "feat_state_blob": osc_codec.pack_feat_state([0] * N_FEATURES),
    }


def _bundle(**over):
    kw = dict(stream_id="aabbccdd00112233", captured_frame_id=42, bundle_seq=7,
              n_persons=1, fps=30.0, contract_id="c" * 32,
              calibration_generation=2, calibration_state="frozen",
              captured_at_us=1_000_000, processed_at_us=1_010_000,
              queued_for_send_at_us=1_012_000, person=_person_wire())
    kw.update(over)
    return osc_codec.build_person_bundle(**kw)


def test_person_bundle_roundtrip_float32_tolerance():
    """OscFrame ↔ OSC(bundle por persona): float32 con tolerancia (finding #15)."""
    data = _bundle()
    msgs = dict(osc_codec.decode_bundle(data))
    meta = msgs["/harmocap/v1/meta"]
    assert meta[0] == "aabbccdd00112233"
    assert meta[1] == 42 and meta[2] == 7          # captured_frame_id, bundle_seq
    assert meta[4] == pytest.approx(30.0, abs=1e-4)  # fps es float32
    kps = osc_codec.unpack_keypoints(msgs["/harmocap/v1/person/0/keypoints"][0])
    assert kps[0][0] == pytest.approx(0.5, abs=1e-6)
    assert msgs["/harmocap/v1/person/0/present"] == [1]
    assert msgs["/harmocap/v1/person/0/focused"] == [1]   # contrato 1.1


def test_bundle_size_under_mtu_worst_case_any_slot():
    """<=1200 B por bundle de persona, peor caso, para CUALQUIER slot (1.1)."""
    for slot in (0, 7):
        data = _bundle(person=_person_wire(slot=slot), n_persons=8,
                       captured_frame_id=2**40, bundle_seq=2**40)
        assert len(data) <= osc_codec.MAX_DATAGRAM_BYTES, (slot, len(data))


def test_focused_flag_roundtrip():
    data = _bundle(person=_person_wire(focused=False))
    msgs = dict(osc_codec.decode_bundle(data))
    assert msgs["/harmocap/v1/person/0/focused"] == [0]


def test_control_select_build_and_parse():
    """/control/select: build+parse (contrato 1.1)."""
    for slot in (0, 7, -1):
        data = osc_codec.build_select(slot)
        (addr, args), = osc_codec.decode_bundle(data)
        assert addr == "/harmocap/v1/control/select"
        assert args == [slot]


def test_tombstone_bundle_form():
    """present=0 → SOLO meta + present, sin payload (r4 #11)."""
    data = _bundle(n_persons=0, person={"slot_id": 0, "present": False})
    msgs = osc_codec.decode_bundle(data)
    addrs = [a for a, _ in msgs]
    assert "/harmocap/v1/person/0/present" in addrs
    assert not any("keypoints" in a or "features" in a or "focused" in a
                   for a in addrs)
    assert len(data) <= osc_codec.MAX_DATAGRAM_BYTES


def test_hello_and_calibration_size_and_roundtrip():
    hello = osc_codec.build_hello(
        stream_id="aabbccdd00112233", schema_version="1.0.0",
        feature_set_version="1.0.0", producer_version="0.1.0",
        model_id="yolo26m-pose.engine", config_hash="a" * 32,
        contract_id="c" * 32, calibration_generation=2,
        calibration_state="frozen", calib_hash="b" * 32,
        effective_from_frame_id=100, frame_w=1280, frame_h=720)
    assert len(hello) <= osc_codec.MAX_DATAGRAM_BYTES
    (addr, args), = osc_codec.decode_bundle(hello)
    assert addr == "/harmocap/v1/hello"
    assert args[0] == "aabbccdd00112233" and args[-2:] == [1280, 720]

    params = [0.28, 3.0, 1.5, 40.0, 4.0, 8.0]
    blob = osc_codec.pack_calibration_params(params)
    cal = osc_codec.build_calibration(
        stream_id="aabbccdd00112233", generation=2,
        calib_hash=osc_codec.calibration_hash(blob),
        effective_from_frame_id=100, params_blob=blob)
    assert len(cal) <= osc_codec.MAX_DATAGRAM_BYTES
    (addr, args), = osc_codec.decode_bundle(cal)
    assert addr == "/harmocap/v1/calibration"
    assert osc_codec.unpack_calibration_params(args[-1]) == pytest.approx(params, abs=1e-6)


# ---------------------------------------------------------------- hashes
def test_contract_id_excludes_self_reference():
    m1 = {"a": 1, "contract_id": "x", "golden_hash": "y"}
    m2 = {"a": 1}
    assert osc_codec.contract_id_from_manifest(m1) == \
        osc_codec.contract_id_from_manifest(m2)


def test_contract_id_matches_sidecar_golden():
    """El golden hash vive en un fixture sidecar, no en el manifiesto (r8 #7)."""
    cid = osc_codec.contract_id_from_manifest(MANIFEST)
    sidecar = REPO / "schemas" / "contract_id.golden"
    assert sidecar.exists(), "generar con scripts/build_nico_kit.py"
    assert sidecar.read_text().strip() == cid


def test_calibration_hash_over_blob_bytes():
    blob = osc_codec.pack_calibration_params([0.28, 3.0, 1.5, 40.0, 4.0, 8.0])
    h1 = osc_codec.calibration_hash(blob)
    assert len(h1) == 32 and int(h1, 16) >= 0
    blob2 = osc_codec.pack_calibration_params([0.29, 3.0, 1.5, 40.0, 4.0, 8.0])
    assert osc_codec.calibration_hash(blob2) != h1


# ---------------------------------------------------------------- interop
def test_python_osc_can_parse_our_bundle():
    """Interop: el parser de python-osc entiende nuestros bundles (Nico puede
    usar python-osc del otro lado)."""
    from pythonosc.osc_bundle import OscBundle
    data = _bundle()
    b = OscBundle(data)
    contents = list(b)
    addrs = [m.address for m in contents]
    assert "/harmocap/v1/meta" in addrs
    assert "/harmocap/v1/person/0/keypoints" in addrs


# ---------------------------------------------------------------- jsonl schema
def test_jsonl_roundtrip_and_schema():
    """MovementFrame ↔ jsonl (r4 #5) + validación jsonschema (r7 #9)."""
    import jsonschema

    from harmocap.interface.recorder import frame_to_dict
    from harmocap.schema import (
        CalibrationProfile, KeypointData, MovementFrame, PersonState,
    )
    kd = tuple(KeypointData(x=0.5, y=0.5, conf=0.9, state=0, age_frames=0,
                            age_us=0) for _ in range(N_KEYPOINTS))
    p = PersonState(slot_id=0, present=True, keypoints=kd,
                    bbox=(0.5, 0.5, 0.3, 0.8), features=(0.5,) * N_FEATURES,
                    feature_states=(0,) * N_FEATURES)
    mf = MovementFrame(stream_id="aabbccdd00112233", captured_frame_id=1,
                       captured_at_us=1_000_000, processed_at_us=1_010_000,
                       frame_w=1280, frame_h=720, fps=30.0,
                       calibration_generation=1,
                       calibration_state="calibrating", persons=(p,))
    calib = CalibrationProfile(generation=1, state="calibrating",
                               effective_from_frame_id=0,
                               params=(0.28, 3.0, 1.5, 40.0, 4.0, 8.0))
    d = frame_to_dict(mf, calib, contract_id="c" * 32, config_hash="a" * 32,
                      model_id="test")
    # serialización sin NaN (r3 #5)
    line = json.dumps(d, allow_nan=False)
    schema = json.loads((REPO / "schemas" / "movement_frame.v1.schema.json").read_text())
    jsonschema.validate(json.loads(line), schema)


def test_math_isfinite_everywhere_in_synthetic_session():
    """Si existe la sesión sintética, no contiene NaN/Inf y valida el schema."""
    import jsonschema
    path = REPO / "examples" / "session_v1.jsonl"
    if not path.exists():
        pytest.skip("sesión sintética aún no generada")
    schema = json.loads((REPO / "schemas" / "movement_frame.v1.schema.json").read_text())
    lines = path.read_text().strip().splitlines()
    assert len(lines) > 100
    for i in (0, len(lines) // 2, -1):     # muestreo: inicio/medio/fin
        d = json.loads(lines[i])
        jsonschema.validate(d, schema)
        for person in d["persons"]:
            for v in person.get("features", []):
                assert v is None or math.isfinite(v)


# ---------------------------------------------------------------- crowd (1.2)
def test_crowd_bundle_roundtrip_and_size():
    crowd = {"crowd_count": 42, "crowd_qom": 0.31, "density": 0.55,
             "centroid_x": 0.9, "centroid_y": 0.48, "flow_x": -0.2,
             "flow_y": 0.05, "dispersion": 0.61}
    data = osc_codec.build_crowd_bundle(
        stream_id="aabbccdd00112233", captured_frame_id=100, bundle_seq=7,
        crowd=crowd)
    assert len(data) <= osc_codec.MAX_DATAGRAM_BYTES
    (addr, args), = osc_codec.decode_bundle(data)
    assert addr == "/harmocap/v1/crowd"
    assert args[0] == "aabbccdd00112233" and args[1] == 100 and args[2] == 7
    assert args[3] == 42                       # crowd_count int
    assert args[4] == pytest.approx(0.31, abs=1e-4)
    assert args[10] == pytest.approx(0.61, abs=1e-4)
