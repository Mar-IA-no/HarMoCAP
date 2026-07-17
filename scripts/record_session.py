#!/usr/bin/env python
"""M4 — graba una sesión .jsonl para Nico (atajo de run_realtime con --record).

PRIVACIDAD (addendum #4): la salida va a outputs/sessions/ (gitignored). Una
trayectoria corporal real es dato conductual: NO publicar sin consentimiento
documentado. El ejemplo versionado del kit es SINTÉTICO (examples/).

Uso:
    python scripts/record_session.py --source 0 --seconds 120 --name ensayo1
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="0")
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--name", default=time.strftime("session_%Y%m%d_%H%M%S"))
    args = ap.parse_args()

    out = REPO / "outputs" / "sessions" / f"{args.name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(REPO / "scripts" / "run_realtime.py"),
           "--source", args.source, "--seconds", str(args.seconds),
           "--record", str(out)]
    print(f"[record] → {out}")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
