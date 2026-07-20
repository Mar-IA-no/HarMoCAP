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
from harmocap.identity import SlotManager
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
                 osc_destinations: list[tuple[str, int]] | None = None,
                 mode: str = "group",
                 checkpoint: str | Path | None = None):
        self.repo = Path(repo_root)
        cfg = lambda name: yaml.safe_load((self.repo / "configs" / f"{name}.yaml").read_text())
        self.cfg_model = cfg("model")
        self.cfg_smooth = cfg("smoothing")
        cfg_ident_full = cfg("identity")
        self.cfg_ident = cfg_ident_full["slot"]
        self.cfg_reacq = cfg_ident_full.get("reacquisition", {})
        self.cfg_feat = cfg("features")
        self.cfg_osc = cfg("osc")["osc"]

        # H4: perfil de modo (group|crowd) sobreescribe model/tracker/identity
        self.mode = mode
        mode_file = self.repo / "configs" / "modes" / f"{mode}.yaml"
        mode_cfg = yaml.safe_load(mode_file.read_text())
        ov = mode_cfg.get("overrides", {})
        if "model" in ov:
            m_ov = dict(ov["model"])
            m_ov.pop("imgsz_fallback", None)
            self.cfg_model["model"].update(m_ov)
            self._imgsz_fallback = ov["model"].get("imgsz_fallback")
        else:
            self._imgsz_fallback = None
        if "tracker" in ov:
            self.cfg_model["tracker"]["name"] = ov["tracker"]["name"]
        if "identity" in ov:
            self.cfg_reacq["enabled"] = ov["identity"].get(
                "reacquisition_enabled", self.cfg_reacq.get("enabled", True))

        if checkpoint is not None:
            candidate = Path(checkpoint)
            if not candidate.is_absolute():
                candidate = self.repo / candidate
            if not candidate.is_file():
                raise FileNotFoundError(f"HarMoCAP checkpoint not found: {candidate}")
            self.cfg_model["model"]["realtime_checkpoint"] = str(candidate)

        manifest = (self.repo / "schemas" / "osc_contract.v1.json")
        import json as _json
        man = _json.loads(manifest.read_text())
        self.contract_id = osc_codec.contract_id_from_manifest(man)
        # h4 M4: mode y reacquisition DEBEN entrar al hash — dos runs con gates
        # distintos no pueden compartir config_hash (trazabilidad del contrato)
        self.config_hash = osc_codec.canonical_json_hash(
            {"model": self.cfg_model, "smoothing": self.cfg_smooth,
             "identity": self.cfg_ident, "features": self.cfg_feat,
             "reacquisition": self.cfg_reacq, "mode": self.mode})

        self.stream_id = new_stream_id()
        m = self.cfg_model["model"]
        from harmocap.perception import resolve_device
        eff_imgsz = m["imgsz"]
        if self._imgsz_fallback and not resolve_device(m["device"]).startswith("cuda"):
            eff_imgsz = self._imgsz_fallback   # crowd en mps/cpu: 960 (sin engine)
        tracker_name = self.cfg_model["tracker"]["name"]
        if "/" in tracker_name:                # tracker propio (configs/…): ruta absoluta
            tracker_name = str(self.repo / tracker_name)
        self.backend = PoseBackend(
            realtime_checkpoint=str(self.repo / m["realtime_checkpoint"]),
            fallback_checkpoint=m["fallback_checkpoint"], device=m["device"],
            imgsz=eff_imgsz, conf=m["conf"], max_det=m["max_det"],
            tracker=tracker_name)

        self.camera = LatchingCamera(source)
        self._oe = self.cfg_smooth["one_euro"]
        self._ks = self.cfg_smooth["keypoint_state"]
        self.slots = SlotManager(
            max_slots=self.cfg_ident.get("max_slots", 8),
            occlusion_grace_ms=self.cfg_ident["occlusion_grace_ms"],
            release_timeout_ms=self.cfg_ident["release_timeout_ms"],
            acquire_rule=self.cfg_ident["acquire_rule"],
            auto_focus_switch_ratio=self.cfg_ident.get("auto_focus_switch_ratio", 1.20),
            tombstone_repeat_frames=self.cfg_ident["tombstone_repeat_frames"],
            reacquisition=self.cfg_reacq)
        from harmocap.crowd import CrowdAggregator
        self.crowd = CrowdAggregator()
        self.last_crowd: dict = {}
        self.calib = CalibrationManager(self.cfg_feat["calibration"]["fallback"],
                                        period_ms=self.cfg_feat["calibration"]["period_ms"])
        # instancias POR SLOT (contrato 1.1): se crean/resetean con slot_reset
        self._smoothers: dict[int, KeypointSmoother] = {}
        self._features: dict[int, FeatureExtractor] = {}

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
            control_port=self.cfg_osc.get("control_port"),
            on_select=self.slots.select_focus)   # /control/select → foco
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

    # -- instancias por slot ---------------------------------------------------
    def _slot_state(self, slot_id: int, reset: bool
                    ) -> tuple[KeypointSmoother, FeatureExtractor]:
        if slot_id not in self._smoothers:
            self._smoothers[slot_id] = KeypointSmoother(
                mincutoff=self._oe["mincutoff"], beta=self._oe["beta"],
                dcutoff=self._oe["dcutoff"],
                conf_threshold=self._ks["conf_threshold"],
                held_timeout_ms=self._ks["held_timeout_ms"],
                conf_decay_per_s=self._ks["conf_decay_per_s"])
            self._features[slot_id] = FeatureExtractor(
                self.cfg_feat["windows"], self.calib)
        elif reset:
            self._smoothers[slot_id].reset()
            self._features[slot_id].reset()
        return self._smoothers[slot_id], self._features[slot_id]

    # -- un paso del loop (multi-slot, contrato 1.1) ---------------------------
    def step(self) -> bool:
        got = self.camera.get_latest()
        if got is None:
            return self.camera.alive
        frame_img, captured_frame_id, captured_at_us = got
        self.metrics["frames"] += 1

        dets, raw_boxes, speed, (w, h) = self.backend.track_frame(frame_img)
        events = self.slots.update(dets, captured_at_us,
                                   aspect=w / h if h else 16 / 9)
        focused = self.slots.focused_slot
        # H4b: agregados de multitud sobre detecciones CRUDAS (recall)
        self.last_crowd = self.crowd.update(raw_boxes, captured_at_us,
                                            aspect=w / h if h else 16 / 9)

        persons: list[PersonState] = []
        persons_wire: list[dict] = []
        calib_observed = False
        for ev in events:
            if ev.detection is not None:
                smoother, features = self._slot_state(ev.slot_id, ev.slot_reset)
                smoothed = smoother.update(ev.detection.keypoints_iso,
                                           captured_at_us)
                if not calib_observed:     # calibración global: primer slot presente
                    torso = features._torso_height(
                        [(s[0], s[1]) for s in smoothed],
                        [s[3] for s in smoothed])
                    if self.calib.observe(torso, captured_at_us, captured_frame_id):
                        self._publish_calibration()   # generación nueva (r7 #4)
                    calib_observed = True
                vals, states = features.extract(smoothed, captured_at_us)
                kd = tuple(KeypointData(x=s[0], y=s[1], conf=s[2], state=s[3],
                                        age_frames=s[4], age_us=s[5])
                           for s in smoothed)
                is_focused = ev.slot_id == focused
                p = PersonState(
                    slot_id=ev.slot_id, present=True, keypoints=kd,
                    bbox=ev.detection.bbox_xywhn, features=tuple(vals),
                    feature_states=tuple(states),
                    provisional=self.calib.profile.state == "calibrating",
                    focused=is_focused)
                persons.append(p)
                persons_wire.append({
                    "slot_id": p.slot_id, "present": True, "focused": is_focused,
                    "keypoints_blob": osc_codec.pack_keypoints(
                        [(k.x, k.y, k.conf) for k in kd]),
                    "kp_state_blob": osc_codec.pack_kp_state(
                        [(k.state, k.age_frames, k.age_us) for k in kd]),
                    "bbox": list(p.bbox),
                    "features_blob": osc_codec.pack_features(list(vals)),
                    "feat_state_blob": osc_codec.pack_feat_state(list(states)),
                })
            elif ev.emit_tombstone:
                persons.append(PersonState(
                    slot_id=ev.slot_id, present=False,
                    keypoints=(), bbox=(0.0, 0.0, 0.0, 0.0),
                    features=(0.0,) * N_FEATURES,
                    feature_states=(int(KpState.INVALID),) * N_FEATURES))
                persons_wire.append({"slot_id": ev.slot_id, "present": False})

        processed_at_us = mono_us()
        mf = MovementFrame(
            stream_id=self.stream_id, captured_frame_id=captured_frame_id,
            captured_at_us=captured_at_us, processed_at_us=processed_at_us,
            frame_w=w, frame_h=h, fps=self.camera.profile()["fps"],
            calibration_generation=self.calib.profile.generation,
            calibration_state=self.calib.profile.state, persons=tuple(persons))

        envs = self.emitter.emit(mf, persons_wire, crowd=self.last_crowd)
        if envs:
            last = envs[-1]
            self.metrics["emitted"] += len(envs)
            self.metrics["lat_sw_ms"].append((last.sent_at_us - captured_at_us) / 1e3)
            if self._prev_sent_us is not None and self._prev_cap_us is not None:
                jitter = abs((last.sent_at_us - self._prev_sent_us)
                             - (captured_at_us - self._prev_cap_us)) / 1e3
                self.metrics["jitter_ms"].append(jitter)   # |Δsent−Δcaptured|
            self._prev_sent_us, self._prev_cap_us = last.sent_at_us, captured_at_us

        if self.recorder:
            self.recorder.put(frame_to_dict(
                mf, self.calib.profile, contract_id=self.contract_id,
                config_hash=self.config_hash,
                model_id=Path(self.backend.loaded_checkpoint).name,
                crowd=self.last_crowd))
        # frame para el overlay opcional (run_realtime --show)
        self.last_frame_img = frame_img
        self.last_persons = persons
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
            "focused_slot": self.slots.focused_slot,
            "focus_mode": self.slots.focus_mode,
        }

    def close(self) -> None:
        self.camera.stop()
        self.emitter.close()
        if self.recorder:
            self.recorder.close()
