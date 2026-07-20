#!/usr/bin/env python
"""Lanza la interfaz web local de HarMoCAP.

Uso:
    python scripts/webapp.py            # abre localhost:7860 en el navegador
    python scripts/webapp.py --port 8000
    python scripts/webapp.py --share    # link temporal público (Gradio)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from harmocap.webapp.app import main  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-fetch", action="store_true",
                    help="no intentar bajar los modelos que falten al arrancar")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--host", default="127.0.0.1",
                    help="interfaz donde escuchar (default 127.0.0.1 = solo esta "
                         "máquina; pasar la IP de una VPN para acceso remoto en red confiable)")
    ap.add_argument("--share", action="store_true",
                    help="link temporal público vía relay de Gradio. EVITAR con "
                         "video de personas: pasa por un tercero (por defecto NO)")
    args = ap.parse_args()
    if not args.no_fetch:
        # plug-and-play: un clon fresco no trae los modelos (binarios pesados);
        # se bajan solos la primera vez desde el release.
        from fetch_models import ensure_models
        print("Verificando modelos…")
        if not ensure_models():
            print("Aviso: falta el modelo de pose y no se pudo bajar. "
                  "Corré `python scripts/fetch_models.py` o revisá tu conexión.")
    main(share=args.share, port=args.port, host=args.host)
