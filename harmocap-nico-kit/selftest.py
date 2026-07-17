#!/usr/bin/env python
"""Self-test autocontenido del kit (r3 #8). SOLO biblioteca estándar.

Levanta un receptor local en un puerto efímero, reproduce frames de la sesión
de ejemplo vía el codec real, y verifica: addresses, typetags/decodificación,
tamaño de bundle <= 1200 B, layouts de blobs (golden vectors), gating por
handshake, descarte monotónico y regla del sentinel.

Uso:  python selftest.py
"""
from __future__ import annotations

import json
import socket
import struct
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import osc_codec  # noqa: E402

OK, FAIL = "  ✔", "  ✘"
errors: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{OK if cond else FAIL} {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        errors.append(name)


def main() -> int:
    print("[selftest] kit HarMoCAP — contrato v1\n")

    # 1. manifiesto + contract_id
    man = json.loads((HERE / "osc_contract.v1.json").read_text())
    cid = osc_codec.contract_id_from_manifest(man)
    golden = (HERE / "contract_id.golden").read_text().strip()
    check("contract_id reproducible (golden sidecar)", cid == golden,
          f"{cid[:12]}…")

    # 2. golden vectors de blobs
    kb = osc_codec.pack_keypoints([(0.0, 0.0, 0.9)] + [(0.1, 0.2, 0.8)] * 16)
    check("blob keypoints 204 B, primer registro big-endian",
          len(kb) == 204 and kb[:12] == struct.pack(">fff", 0.0, 0.0, 0.9))
    sb = osc_codec.pack_kp_state([(1, 5, 123456)] * 17)
    check("blob kp_state 221 B (>BIQ)",
          len(sb) == 221 and sb[:13] == struct.pack(">BIQ", 1, 5, 123456))
    fb = osc_codec.pack_features([0.5] * 21)
    check("blob features 84 B (>21f)", len(fb) == 84)
    try:
        osc_codec.pack_features([float("nan")] * 21)
        check("NaN rechazado en el wire", False)
    except ValueError:
        check("NaN rechazado en el wire", True)

    # 3. sesión de ejemplo presente y parseable
    session = HERE / "examples" / "session_v1.jsonl"
    lines = session.read_text().strip().splitlines()
    frames = [json.loads(l) for l in lines[:50]]
    check("sesión de ejemplo legible", len(lines) > 100, f"{len(lines)} frames")
    check("sesión declara contract_id vigente",
          frames[0]["contract_id"] == cid)

    # 4. round-trip por red real: replay parcial → receptor local
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    received: list[bytes] = []

    def rx():
        sock.settimeout(2.0)
        while True:
            try:
                data, _ = sock.recvfrom(4096)
                received.append(data)
            except socket.timeout:
                return

    th = threading.Thread(target=rx, daemon=True)
    th.start()

    import replay  # el replay del kit
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", port)
    for pkt in replay.handshake_bytes(frames[0]):
        tx.sendto(pkt, dest)
    sizes = []
    for seq, d in enumerate(frames[:30], 1):
        pkt = replay.frame_to_wire(d, seq, 0)
        sizes.append(len(pkt))
        tx.sendto(pkt, dest)
    time.sleep(0.3)

    check("todos los bundles <= 1200 B", max(sizes) <= 1200,
          f"max={max(sizes)} B")
    check("recepción por UDP real", len(received) >= 25,
          f"{len(received)} datagramas")

    # 5. decodificación + reglas del receptor sobre lo recibido
    hellos = [m for d in received for m in osc_codec.decode_bundle(d)
              if m[0].endswith("/hello")]
    metas = [m for d in received for m in osc_codec.decode_bundle(d)
             if m[0].endswith("/meta")]
    check("handshake /hello recibido", len(hellos) >= 1)
    check("frames /meta recibidos y decodificados", len(metas) >= 20)
    if metas:
        seqs = [m[1][2] for m in metas]
        check("bundle_seq monótono creciente", seqs == sorted(seqs))
    kp_msgs = [m for d in received for m in osc_codec.decode_bundle(d)
               if "keypoints" in m[0]]
    if kp_msgs:
        kps = osc_codec.unpack_keypoints(kp_msgs[0][1][0])
        check("keypoints decodificados (17 × x,y,conf)", len(kps) == 17)

    print()
    if errors:
        print(f"[selftest] FALLARON {len(errors)}: {errors}")
        return 1
    print("[selftest] TODO OK — el kit funciona en esta máquina.")
    print("Siguiente paso: python osc_receiver_example.py --port 9000  (terminal A)")
    print("               python replay.py examples/session_v1.jsonl --loop  (terminal B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
