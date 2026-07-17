#!/usr/bin/env python
"""Genera harmocap-nico-kit/ desde las fuentes canónicas (r3 #9).

El kit NUNCA se edita a mano: este script copia manifiesto/schema/docs/codec/
replay/ejemplos desde sus ubicaciones canónicas, regenera el golden sidecar,
escribe VERSION con checksum del contenido, y produce LICENSE +
THIRD_PARTY_NOTICES. `tests/test_kit_isolation.py` verifica que el resultado
corre sin el repo y `test_kit_in_sync` que no divergió.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KIT = REPO / "harmocap-nico-kit"

# (origen canónico, destino relativo al kit)
COPIES = [
    ("src/harmocap/interface/osc_codec.py", "osc_codec.py"),
    ("src/harmocap/interface/replay.py", "replay.py"),
    ("scripts/kit_src/osc_receiver_example.py", "osc_receiver_example.py"),
    ("scripts/kit_src/selftest.py", "selftest.py"),
    ("scripts/kit_src/README.md", "README.md"),
    ("schemas/osc_contract.v1.json", "osc_contract.v1.json"),
    ("schemas/contract_id.golden", "contract_id.golden"),
    ("schemas/movement_frame.v1.schema.json", "movement_frame.v1.schema.json"),
    ("docs/INTERFACE_SPEC.md", "INTERFACE_SPEC.md"),
    ("docs/FEATURES.md", "FEATURES.md"),
    ("LICENSE", "LICENSE"),
    ("examples/session_v1.jsonl", "examples/session_v1.jsonl"),
    ("examples/fixtures/lifecycle.jsonl", "examples/fixtures/lifecycle.jsonl"),
    ("examples/fixtures/calibration.jsonl", "examples/fixtures/calibration.jsonl"),
    ("examples/fixtures/stream_restart.jsonl", "examples/fixtures/stream_restart.jsonl"),
]

REQUIREMENTS = "python-osc==1.9.3\n"

THIRD_PARTY = """\
THIRD PARTY NOTICES — harmocap-nico-kit

El kit corre con la biblioteca estándar de Python. Dependencia opcional:

- python-osc 1.9.3 — Unlicense (dominio público) — https://github.com/attwad/python-osc
  Se instala vía requirements.txt solo si querés usarla en tu propio receptor.

El kit NO incluye ni depende de ultralytics (AGPL-3.0) ni de ningún otro
componente del pipeline de percepción.
"""


def main() -> int:
    if KIT.exists():
        shutil.rmtree(KIT)
    (KIT / "examples" / "fixtures").mkdir(parents=True)

    # regenerar el golden sidecar antes de copiar (fuente: manifiesto canónico)
    sys.path.insert(0, str(REPO / "src"))
    from harmocap.interface import osc_codec
    man = json.loads((REPO / "schemas" / "osc_contract.v1.json").read_text())
    (REPO / "schemas" / "contract_id.golden").write_text(
        osc_codec.contract_id_from_manifest(man) + "\n")

    for src, dst in COPIES:
        s, d = REPO / src, KIT / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)

    (KIT / "requirements.txt").write_text(REQUIREMENTS)
    (KIT / "THIRD_PARTY_NOTICES").write_text(THIRD_PARTY)

    # VERSION con checksum del contenido (r4 #10)
    h = hashlib.sha256()
    for p in sorted(KIT.rglob("*")):
        if p.is_file() and p.name != "VERSION":
            h.update(p.relative_to(KIT).as_posix().encode())
            h.update(p.read_bytes())
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                cwd=REPO, capture_output=True, text=True
                                ).stdout.strip()
    except OSError:
        commit = "unknown"
    (KIT / "VERSION").write_text(
        f"harmocap-nico-kit 0.1.0\ncommit: {commit}\n"
        f"content-sha256: {h.hexdigest()}\n")

    print(f"[kit] generado en {KIT}")
    print((KIT / "VERSION").read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
