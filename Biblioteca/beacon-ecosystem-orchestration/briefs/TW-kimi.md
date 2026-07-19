# TW — harmonic-weaver repo scaffolding

Agent: kimi. Size: S. Wave: 2.
Target: NEW directory ~/Projects/harmonic-weaver (does not exist yet — create it).
Context: harmonic-weaver will be the headless modulation patchbay of the Harmonic Beacon ecosystem (sources → transformations → instruments, scenes + global panic, contract-manifest-driven, thin-client UIs over WebSocket). This task is ONLY the empty scaffold.

## Task

Create the repository skeleton:

```
harmonic-weaver/
├── pyproject.toml          # setuptools; name "harmonic-weaver", version 0.1.0, requires-python >=3.10; MIT
├── LICENSE                 # MIT license text, copyright "AlterMundi contributors"
├── README.md               # purpose: headless modulation router/patchbay for the beacon ecosystem; status: scaffold; all UIs are thin clients of the same contract-manifest protocol (web first, mobile/Quest later)
├── BITACORA.md             # header + one line: repo scaffolded 2026-07-18
├── .gitignore              # venv/, .venv/, __pycache__/, *.pyc, *.wav, .env, *.egg-info/, dist/, build/
├── src/harmonic_weaver/__init__.py   # __version__ = "0.1.0"
├── contracts/.gitkeep      # contract templates and manifests live here
├── configs/.gitkeep
├── docs/.gitkeep
└── tests/.gitkeep
```

Then: `git init -b main`, `git add -A`, single commit `chore: repo scaffolding (conventions from HarMoCAP ecosystem)`.

## Acceptance criteria

1. `pip install -e . --no-deps` succeeds inside a throwaway venv under /tmp.
2. `git log --oneline` shows exactly one commit on branch `main`; `git status` clean.
3. No remotes — the orchestrator wires GitHub.

## Constraints

- No code copied from anywhere. No venv inside the repo. English everywhere.

## Report

Tree, pip check output, git log line.
