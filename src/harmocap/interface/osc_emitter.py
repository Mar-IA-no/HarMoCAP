"""Emisor OSC — rama de tiempo real (plan M4).

Usa EXCLUSIVAMENTE osc_codec (el encoder canónico único, autoauditoría #3).
- Bundle atómico por frame, timetag immediately (r4 #6).
- /hello + /calibration en rebroadcast periódico (~1 Hz) + on-change (r5 #2).
- bundle_seq cuenta EMISIONES (≠ captured_frame_id, addendum #5).
- Telemetría en TransportEnvelope: sent_at fuera del frame (r5 #2).
- Puerto de control opcional para /hello/request: respuesta a destinos
  CONFIGURADOS, no al origen del datagrama (r6 #3).
"""
from __future__ import annotations

import socket
import threading

from harmocap.capture import mono_us
from harmocap.interface import osc_codec
from harmocap.schema import (
    FEATURE_SET_VERSION, MovementFrame, PRODUCER_VERSION, SCHEMA_VERSION,
    TransportEnvelope,
)


class OscEmitter:
    def __init__(self, *, destinations: list[tuple[str, int]], contract_id: str,
                 config_hash: str, model_id: str, stream_id: str,
                 frame_w: int, frame_h: int,
                 hello_rebroadcast_s: float = 1.0, control_port: int | None = None):
        self.destinations = destinations
        self.contract_id = contract_id
        self.config_hash = config_hash
        self.model_id = model_id
        self.stream_id = stream_id
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.hello_rebroadcast_us = hello_rebroadcast_s * 1e6
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._seq = 0
        self._last_hello_us = 0
        self._calibration: dict | None = None   # {generation,state,hash,effective,params_blob}
        self.envelopes: list[TransportEnvelope] = []   # telemetría (acotada)
        self._control: threading.Thread | None = None
        self._control_running = False
        if control_port is not None:
            self._start_control(control_port)

    # -- calibración (r7 #1: los params SOLO viajan en /calibration) ----------
    def set_calibration(self, *, generation: int, state: str,
                        effective_from_frame_id: int, params_blob: bytes) -> None:
        self._calibration = {
            "generation": generation, "state": state,
            "hash": osc_codec.calibration_hash(params_blob),
            "effective": effective_from_frame_id, "params_blob": params_blob,
        }
        self._broadcast_handshake()   # on-change

    # -- handshake -------------------------------------------------------------
    def _hello_bytes(self) -> bytes:
        c = self._calibration or {"generation": 0, "state": "calibrating",
                                  "hash": "0" * 32, "effective": 0}
        return osc_codec.build_hello(
            stream_id=self.stream_id, schema_version=SCHEMA_VERSION,
            feature_set_version=FEATURE_SET_VERSION,
            producer_version=PRODUCER_VERSION, model_id=self.model_id,
            config_hash=self.config_hash, contract_id=self.contract_id,
            calibration_generation=c["generation"], calibration_state=c["state"],
            calib_hash=c["hash"], effective_from_frame_id=c["effective"],
            frame_w=self.frame_w, frame_h=self.frame_h)

    def _calibration_bytes(self) -> bytes | None:
        c = self._calibration
        if c is None:
            return None
        return osc_codec.build_calibration(
            stream_id=self.stream_id, generation=c["generation"],
            calib_hash=c["hash"], effective_from_frame_id=c["effective"],
            params_blob=c["params_blob"])

    def _broadcast_handshake(self) -> None:
        self._send(self._hello_bytes())
        cal = self._calibration_bytes()
        if cal is not None:
            self._send(cal)
        self._last_hello_us = mono_us()

    # -- emisión por frame -----------------------------------------------------
    def emit(self, frame: MovementFrame, persons_wire: list[dict]) -> TransportEnvelope:
        """persons_wire: dicts listos para osc_codec.build_frame_bundle."""
        now = mono_us()
        if now - self._last_hello_us > self.hello_rebroadcast_us:
            self._broadcast_handshake()   # rebroadcast periódico (r5 #2)
        self._seq += 1
        env = TransportEnvelope(bundle_seq=self._seq, queued_for_send_at_us=now)
        bundle = osc_codec.build_frame_bundle(
            stream_id=frame.stream_id,
            captured_frame_id=frame.captured_frame_id, bundle_seq=self._seq,
            n_persons=frame.n_persons, fps=frame.fps,
            contract_id=self.contract_id,
            calibration_generation=frame.calibration_generation,
            calibration_state=frame.calibration_state,
            captured_at_us=frame.captured_at_us,
            processed_at_us=frame.processed_at_us,
            queued_for_send_at_us=env.queued_for_send_at_us,
            persons=persons_wire)
        self._send(bundle)
        env.sent_at_us = mono_us()
        env.wire_bytes = len(bundle)
        self.envelopes.append(env)
        if len(self.envelopes) > 10_000:          # acotar telemetría en memoria
            del self.envelopes[:5_000]
        return env

    def _send(self, data: bytes) -> None:
        for host, port in self.destinations:
            self._sock.sendto(data, (host, port))

    # -- puerto de control (/hello/request, r6 #3) -----------------------------
    def _start_control(self, port: int) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind(("0.0.0.0", port))
        srv.settimeout(0.5)
        self._control_running = True

        def loop():
            while self._control_running:
                try:
                    data, _addr = srv.recvfrom(2048)
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    for addr, _args in osc_codec.decode_bundle(data):
                        if addr == f"{osc_codec.OSC_NAMESPACE}/hello/request":
                            self._broadcast_handshake()  # a destinos configurados
                except Exception:
                    continue
            srv.close()

        self._control = threading.Thread(target=loop, daemon=True,
                                         name="harmocap-osc-control")
        self._control.start()

    def close(self) -> None:
        self._control_running = False
        if self._control:
            self._control.join(timeout=1.5)
        self._sock.close()
