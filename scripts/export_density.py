#!/usr/bin/env python
"""H6 — exporta el modelo de densidad ZIP a un ONNX autocontenido.

Desacopla producción del repositorio de ZIP: el backend de densidad corre con
onnxruntime + numpy, sin torch ni el paquete `models` de ZIP (que arrastra la
rama CLIP con open_clip/peft). El ONNX es un artefacto de build regenerable,
gitignoreado como el engine TensorRT.

Requiere el repo de ZIP y los checkpoints en outputs/zip_eval/ (ver
scripts de descarga). Uso: python scripts/export_density.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import onnx
import torch

REPO = Path(__file__).resolve().parent.parent
ZIP_DIR = REPO / "outputs" / "zip_eval" / "ZIP"
sys.path.insert(0, str(ZIP_DIR))

# ZIP importa la rama CLIP al cargar `models`; acá solo usamos EBC/MobileNetV4.
for _dep in ("open_clip", "peft"):
    if _dep not in sys.modules:
        try:
            __import__(_dep)
        except ImportError:
            _m = types.ModuleType(_dep)
            _m.__file__ = f"<stub {_dep}>"
            _m.__path__ = []                          # type: ignore[attr-defined]
            _m.__getattr__ = lambda n: (              # type: ignore[attr-defined]
                (_ for _ in ()).throw(AttributeError(n)) if n.startswith("__")
                else (lambda *a, **k: (_ for _ in ()).throw(RuntimeError(_dep))))
            sys.modules[_dep] = _m

CHECKPOINTS = {
    "qnrf_n": REPO / "outputs/zip_eval/qnrf_n/ebc_n_best/best_mae.pth",
    "nwpu_n": REPO / "outputs/zip_eval/nwpu_n/best_mae.pth",
}
OUT_DIR = REPO / "outputs" / "density"


def export(name: str, ckpt: Path) -> Path:
    from models import get_model
    model = get_model(model_info_path=str(ckpt))
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    model.load_state_dict(state["weights"])
    model.eval()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT_DIR / f"zip_{name}.onnx"
    dummy = torch.randn(1, 3, 384, 640)
    torch.onnx.export(
        model, dummy, str(tmp), input_names=["img"], output_names=["density"],
        dynamic_axes={"img": {0: "b", 2: "h", 3: "w"},
                      "density": {0: "b", 2: "dh", 3: "dw"}},
        opset_version=18, do_constant_folding=True)
    # consolidar pesos externos en un solo archivo (portable)
    m = onnx.load(str(tmp))
    onnx.save_model(m, str(tmp), save_as_external_data=False)
    sidecar = OUT_DIR / f"zip_{name}.onnx.data"
    if sidecar.exists():
        sidecar.unlink()
    return tmp


def verify(name: str, onnx_path: Path, ckpt: Path) -> None:
    """El ONNX debe reproducir el torch original (conteo y campo)."""
    import numpy as np
    import onnxruntime as ort
    from models import get_model
    model = get_model(model_info_path=str(ckpt))
    model.load_state_dict(torch.load(ckpt, map_location="cpu",
                                     weights_only=False)["weights"])
    model.eval()
    x = torch.randn(1, 3, 384, 640)
    with torch.no_grad():
        ref = model(x)
        ref = (ref[0] if isinstance(ref, (tuple, list)) else ref).numpy()
    sess = ort.InferenceSession(str(onnx_path))
    out = sess.run(None, {"img": x.numpy()})[0]
    diff = float(np.abs(ref - out).max())
    assert diff < 1e-3, f"{name}: ONNX difiere del torch en {diff}"
    size_mb = onnx_path.stat().st_size / 1e6
    print(f"  {name}: {size_mb:.1f} MB · suma {out.sum():.1f} · max_diff {diff:.1e} ✓")


def main() -> int:
    for name, ckpt in CHECKPOINTS.items():
        if not ckpt.exists():
            print(f"  {name}: checkpoint ausente ({ckpt}) — omitido")
            continue
        print(f"[export] {name} …")
        path = export(name, ckpt)
        verify(name, path, ckpt)
    print(f"[export] → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
