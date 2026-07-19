"""M4 — aislamiento y sincronía del kit (r3 #6, r3 #9).

- test_kit_isolation: copia SOLO harmocap-nico-kit/ a un directorio limpio y
  corre el selftest con el Python del sistema SIN el repo en sys.path ni venv
  del proyecto → demuestra que corre sin harmocap.*, numpy, scipy, opencv,
  ultralytics (stdlib pura).
- test_kit_in_sync: el kit no divergió de las fuentes canónicas (checksum).
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
KIT = REPO / "harmocap-nico-kit"

# Python del SISTEMA (sin harmocap instalado) — simulación honesta de la
# máquina de Nico; fallback al intérprete actual si no existe.
SYS_PYTHON = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable


@pytest.fixture(scope="module")
def kit_built():
    if not KIT.exists():
        subprocess.run([sys.executable, str(REPO / "scripts" / "build_nico_kit.py")],
                       check=True)
    return KIT


def test_kit_isolation(kit_built, tmp_path):
    """El kit corre en un directorio limpio, sin el repo, con stdlib pura."""
    dest = tmp_path / "kit"
    shutil.copytree(kit_built, dest)
    # entorno mínimo: python del sistema, sin el repo en path, cwd aislado
    proc = subprocess.run(
        [SYS_PYTHON, "-I", "selftest.py"],   # -I: isolated (sin sys.path del user)
        cwd=dest, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"selftest falló:\n{proc.stdout}\n{proc.stderr}"
    assert "TODO OK" in proc.stdout


def test_kit_scripts_run_as_main_under_isolated_python(kit_built, tmp_path):
    """replay/receiver como SCRIPT con `-I` (Python>=3.11: -I implica -P y no
    agrega el dir del script a sys.path — regresión real detectada en smoke)."""
    dest = tmp_path / "kit3"
    shutil.copytree(kit_built, dest)
    for script in ("replay.py", "osc_receiver_example.py"):
        proc = subprocess.run([SYS_PYTHON, "-I", script, "--help"],
                              cwd=dest, capture_output=True, text=True,
                              timeout=60)
        assert proc.returncode == 0, f"{script}: {proc.stderr}"


def test_kit_never_imports_heavy_deps(kit_built, tmp_path):
    """Ningún módulo del kit importa numpy/scipy/cv2/ultralytics/harmocap."""
    dest = tmp_path / "kit2"
    shutil.copytree(kit_built, dest)
    probe = dest / "_probe.py"
    probe.write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).parent))\n"
        "import osc_codec, replay, osc_receiver_example, selftest\n"
        "bad = [m for m in sys.modules\n"
        "       if m.split('.')[0] in ('numpy','scipy','cv2','ultralytics',\n"
        "                              'harmocap','torch','pythonosc')]\n"
        "assert not bad, f'imports prohibidos: {bad}'\n"
        "print('ISOLATION OK')\n")
    proc = subprocess.run([SYS_PYTHON, "-I", "_probe.py"],
                          cwd=dest, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "ISOLATION OK" in proc.stdout


def test_kit_in_sync(kit_built):
    """El kit es byte-idéntico a sus fuentes canónicas (r3 #9)."""
    pairs = [
        ("src/harmocap/interface/osc_codec.py", "osc_codec.py"),
        ("src/harmocap/interface/replay.py", "replay.py"),
        ("schemas/osc_contract.v1.json", "osc_contract.v1.json"),
        ("schemas/movement_frame.v1.schema.json", "movement_frame.v1.schema.json"),
        ("docs/INTERFACE_SPEC.md", "INTERFACE_SPEC.md"),
        ("examples/session_v1.jsonl", "examples/session_v1.jsonl"),
    ]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for src, dst in pairs:
        assert sha(REPO / src) == sha(kit_built / dst), \
            f"kit divergió de la fuente canónica: {dst} (regenerar con build_nico_kit)"


def test_kit_has_license_and_version(kit_built):
    """Licencia y VERSION+checksum presentes (r4 #10, r5 #11)."""
    assert (kit_built / "LICENSE").exists()
    assert "MIT" in (kit_built / "LICENSE").read_text()
    assert (kit_built / "THIRD_PARTY_NOTICES").exists()
    v = (kit_built / "VERSION").read_text()
    assert "content-sha256:" in v
