"""Pipeline de tiempo real — orquesta las etapas (plan, Arquitectura del MVP).

captura (hilo, último frame) → percepción+representación (loop principal) →
fan-out broadcast a OSC (rama RT) y recorder (rama no bloqueante) (r2 #3).

Instrumentación (finding #10): timestamps por etapa desde la adquisición,
percentiles p50/p95/p99, jitter |Δsent−Δcaptured| (r5 #8), edad del frame al
emitir y drops por cola. El GIL se sortea con hilos de I/O + loop principal;
si la etapa CPU-bound satura se migra a proceso (decisión por medición).
"""
from __future__ import annotations

import statistics
from pathlib import Path

import yaml

from harmocap.capture import LatchingCamera, mono_us
from harmocap.features import CalibrationManager, FeatureExtractor
from harmocap.identity import PrincipalSlot
from harmocap.interface import osc_codec
from harmocap.interface.osc_emitter import OscEmitter
from harmocap.interface.recorder import Recorder, frame_to_dict
from harmocap.perception import PoseBackend
from harmocap.schema import (
    CALIBRATION_PARAM_ORDER, KeypointData, KpState, MovementFrame, N_FEATURES,
    N_KEYPOINTS, PersonState, new_stream_id,
)
from harmocap.smoothing import KeypointSmoother


def _percentiles(xs: list[float]) -> dict:
    if not xs:
        return {}
    s = sorted(xs)
    pick = lambda q: s[min(len(s) - 1, int(q * len(s)))]
    return {"p50": pick(0.50), "p95": pick(0.95), "p99": pick(0.99),
            "mean": statistics.fmean(s), "n": len(s)}


class HarmocapPipeline:
    def __init__(self, repo_root: str | Path, *, source: int | str = 0,
                 record_to: str | Path | None = None,
                 osc_destinations: list[tuple[str, int]] | None = None):
        self.repo = Path(repo_root)
        cfg = lambda name: yaml.safe_load((self.repo / "configs" / f"{name}.yaml").read_text())
        self.cfg_model = cfg("model")
        self.cfg_smooth = cfg("smoothing")
        self.cfg_ident = cfg("identity")["slot"]
        self.cfg_feat = cfg("features")
        self.cfg_osc = cfg("osc")["osc"]

        manifest = (self.repo / "schemas" / "osc_contract.v1.json")
        import json as _json
        man = _json.loads(manifest.read_text())
        self.contract_id = osc_codec.contract_id_from_manifest(man)
        self.config_hash = osc_codec.canonical_json_hash(
            {"model": self.cfg_model, "smoothing": self.cfg_smooth,
             "identity": self.cfg_ident, "features": self.cfg_feat})

        self.stream_id = new_stream_id()
        m = self.cfg_model["model"]
        self.backend = PoseBackend(
            realtime_checkpoint=str(self.repo / m["realtime_checkpoint"]),
            fallback_checkpoint=m["fallback_checkpoint"], device=m["device"],
            imgsz=m["imgsz"], conf=m["conf"], max_det=m["max_det"],
            tracker=self.cfg_model["tracker"]["name"])

        self.camera = LatchingCamera(source)
        oe = self.cfg_smooth["one_euro"]; ks = self.cfg_smooth["keypoint_state"]
        self.smoother = KeypointSmoother(
            mincutoff=oe["mincutoff"], beta=oe["beta"], dcutoff=oe["dcutoff"],
            conf_threshold=ks["conf_threshold"],
            held_timeout_ms=ks["held_timeout_ms"],
            conf_decay_per_s=ks["conf_decay_per_s"])
        self.slot = PrincipalSlot(
            occlusion_grace_ms=self.cfg_ident["occlusion_grace_ms"],
            release_timeout_ms=self.cfg_ident["release_timeout_ms"],
            acquire_rule=self.cfg_ident["acquire_rule"],
            tombstone_repeat_frames=self.cfg_ident["tombstone_repeat_frames"])
        self.calib = CalibrationManager(self.cfg_feat["calibration"]["fallback"],
                                        period_ms=self.cfg_feat["calibration"]["period_ms"])
        self.features = FeatureExtractor(self.cfg_feat["windows"], self.calib)

        dests = osc_destinations or [(d["host"], d["port"])
                                     for d in self.cfg_osc["destinations"]]
        prof = self.camera.profile()
        self.emitter = OscEmitter(
            destinations=dests, contract_id=self.contract_id,
            config_hash=self.config_hash,
            model_id=Path(self.backend.loaded_checkpoint).name,
            stream_id=self.stream_id,
            frame_w=prof["width"], frame_h=prof["height"],
            hello_rebroadcast_s=self.cfg_osc["hello_rebroadcast_s"],
            control_port=self.cfg_osc.get("control_port"))
        self._publish_calibration()

        self.recorder = Recorder(record_to) if record_to else None
        self.metrics = {"lat_sw_ms": [], "jitter_ms": [], "frames": 0,
                        "emitted": 0}
        self._prev_sent_us: int | None = None
        self._prev_cap_us: int | None = None

    # -- calibración -----------------------------------------------------------
    def _publish_calibration(self) -> None:
        p = self.calib.profile
        blob = osc_codec.pack_calibration_params(list(p.params))
        self.emitter.set_calibration(
            generation=p.generation, state=p.state,
            effective_from_frame_id=p.effective_from_frame_id, params_blob=blob)

    # -- un paso del loop ------------------------------------------------------
    def step(self) -> bool:
        got = self.camera.get_latest()
        if got is None:
            return self.camera.alive
        frame_img, captured_frame_id, captured_at_us = got
        self.metrics["frames"] += 1

        dets, speed, (w, h) = self.backend.track_frame(frame_img)
        det, emit_tombstone, slot_reset = self.slot.update(dets, captured_at_us)
        if slot_reset:
            self.smoother.reset()
            self.features.reset()

        persons: list[PersonState] = []
        persons_wire: list[dict] = []
        if det is not None:
            smoothed = self.smoother.update(det.keypoints_iso, captured_at_us)
            torso = self.features._torso_height(
                [(s[0], s[1]) for s in smoothed], [s[3] for s in smoothed])
            froze = self.calib.observe(torso, captured_at_us, captured_frame_id)
            if froze:
                self._publish_calibration()   # generación nueva al congelar (r7 #4)
            vals, states = self.features.extract(smoothed, captured_at_us)
            kd = tuple(KeypointData(x=s[0], y=s[1], conf=s[2], state=s[3],
                                    age_frames=s[4], age_us=s[5]) for s in smoothed)
            p = PersonState(
                slot_id=self.slot.SLOT_ID, present=True, keypoints=kd,
                bbox=det.bbox_xywhn, features=tuple(vals),
                feature_states=tuple(states),
                provisional=self.calib.profile.state == "calibrating")
            persons.append(p)
            persons_wire.append({
                "slot_id": p.slot_id, "present": True,
                "keypoints_blob": osc_codec.pack_keypoints(
                    [(k.x, k.y, k.conf) for k in kd]),
                "kp_state_blob": osc_codec.pack_kp_state(
                    [(k.state, k.age_frames, k.age_us) for k in kd]),
                "bbox": list(p.bbox),
                "features_blob": osc_codec.pack_features(list(vals)),
                "feat_state_blob": osc_codec.pack_feat_state(list(states)),
            })
        elif emit_tombstone:
            persons.append(PersonState(
                slot_id=self.slot.SLOT_ID, present=False,
                keypoints=(), bbox=(0.0, 0.0, 0.0, 0.0),
                features=(0.0,) * N_FEATURES,
                feature_states=(int(KpState.INVALID),) * N_FEATURES))
            persons_wire.append({"slot_id": self.slot.SLOT_ID, "present": False})

        processed_at_us = mono_us()
        mf = MovementFrame(
            stream_id=self.stream_id, captured_frame_id=captured_frame_id,
            captured_at_us=captured_at_us, processed_at_us=processed_at_us,
            frame_w=w, frame_h=h, fps=self.camera.profile()["fps"],
            calibration_generation=self.calib.profile.generation,
            calibration_state=self.calib.profile.state, persons=tuple(persons))

        env = self.emitter.emit(mf, persons_wire)
        self.metrics["emitted"] += 1
        self.metrics["lat_sw_ms"].append((env.sent_at_us - captured_at_us) / 1e3)
        if self._prev_sent_us is not None and self._prev_cap_us is not None:
            jitter = abs((env.sent_at_us - self._prev_sent_us)
                         - (captured_at_us - self._prev_cap_us)) / 1e3
            self.metrics["jitter_ms"].append(jitter)   # |Δsent−Δcaptured| (r5 #8)
        self._prev_sent_us, self._prev_cap_us = env.sent_at_us, captured_at_us

        if self.recorder:
            self.recorder.put(frame_to_dict(
                mf, self.calib.profile, contract_id=self.contract_id,
                config_hash=self.config_hash,
                model_id=Path(self.backend.loaded_checkpoint).name))
        return True

    # -- reporte GO/NO-GO ------------------------------------------------------
    def report(self) -> dict:
        return {
            "backend": self.backend.info(),
            "capture_profile": self.camera.profile(),
            "capture_dropped": self.camera.dropped,
            "recorder_dropped": self.recorder.dropped if self.recorder else None,
            "frames": self.metrics["frames"],
            "emitted": self.metrics["emitted"],
            "lat_sw_ms": _percentiles(self.metrics["lat_sw_ms"]),
            "jitter_ms": _percentiles(self.metrics["jitter_ms"]),
            "stream_id": self.stream_id,
            "contract_id": self.contract_id,
        }

    def close(self) -> None:
        self.camera.stop()
        self.emitter.close()
        if self.recorder:
            self.recorder.close()
