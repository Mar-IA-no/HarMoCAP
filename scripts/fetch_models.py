#!/usr/bin/env python
"""Descarga los modelos que el repo NO versiona (son binarios pesados).

Los modelos entrenados no van en git (inflarían la historia para siempre); se
publican como assets del release y se bajan la primera vez que hacen falta. Así
un clon fresco queda listo para usar sin copiar nada a mano.

Uso:
    python scripts/fetch_models.py            # baja lo que falte
    python scripts/fetch_models.py --force    # rebaja aunque exista
    from harmocap... import ensure_models; ensure_models()   # desde código
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Repos públicos de donde bajar (se prueban en orden). Cualquiera de los dos
# sirve: son espejos, y el clon de uno puede bajar del release del otro.
SOURCE_REPOS = ["Mar-IA-no/HarMoCAP", "AlterMundi/HarMoCAP"]
RELEASE_TAG = "models-v1"

# nombre del asset → (ruta local relativa al repo, sha256, obligatorio)
MODELS = {
    "harmocap-m-pose-ft2.pt": (
        "harmocap-m-pose-ft2.pt",
        "80eae9b99ab5710ec6c0bd366acefa0e116482e98c9bba3803b62bf984fc0bcc",
        True,   # imprescindible: es el modelo de pose (fallback en Mac/CPU)
    ),
    "zip_qnrf_n.onnx": (
        "outputs/density/zip_qnrf_n.onnx",
        "7199772cdbe86a41a1384af847a028c15edd0e83653665a65922c5d8535b091b",
        False,  # opcional: habilita las señales de masa por densidad
    ),
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(asset: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for repo in SOURCE_REPOS:
        url = f"https://github.com/{repo}/releases/download/{RELEASE_TAG}/{asset}"
        try:
            print(f"  bajando {asset} de {repo} …", flush=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            with urllib.request.urlopen(url, timeout=60) as r, tmp.open("wb") as f:
                total = int(r.headers.get("Content-Length", 0))
                got = 0
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b); got += len(b)
                    if total:
                        print(f"\r    {got*100//total}%", end="", flush=True)
            print()
            tmp.replace(dest)
            return True
        except Exception as e:
            print(f"    falló en {repo}: {e}")
    return False


def ensure_models(force: bool = False, verbose: bool = True) -> bool:
    """Baja los modelos que falten. Devuelve True si están todos los obligatorios."""
    ok = True
    for asset, (rel, sha, required) in MODELS.items():
        dest = REPO / rel
        if dest.is_file() and not force:
            if _sha256(dest) == sha:
                if verbose:
                    print(f"  ✓ {rel} (ya está)")
                continue
            if verbose:
                print(f"  ! {rel} existe pero el hash no coincide; rebajando")
        if not _download(asset, dest):
            msg = f"  ✗ no se pudo bajar {asset}"
            print(msg + (" (OBLIGATORIO)" if required else " (opcional)"))
            ok = ok and not required
            continue
        if _sha256(dest) != sha:
            print(f"  ✗ {rel}: hash no coincide tras bajar (¿release corrupto?)")
            ok = ok and not required
        elif verbose:
            print(f"  ✓ {rel} (descargado)")
    return ok


def main() -> int:
    force = "--force" in sys.argv
    print("HarMoCAP — descarga de modelos")
    ok = ensure_models(force=force)
    if ok:
        print("Listo: los modelos obligatorios están disponibles.")
        return 0
    print("Faltan modelos obligatorios — revisá tu conexión o el release.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
