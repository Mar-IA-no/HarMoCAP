# HarMoCAP — Project Memory

> Last updated: 2026-07-18. Session: k3 (S14 diagnosis + Fable audit triage).

## Status

Beacon ecosystem re-architecture: **COMPLETE** (26/26 Kanban cards done). F0-F4 + F6 executed across 4 repos. Next-stage items tracked as F5-* cards (triage) on board `beacon-ecosystem-orch`.

## Active repos

| Repo | Branch | Head | Role |
|------|--------|------|------|
| harmonic-weaver | main | b5b5221 | Routing engine + Stage WS + patchbay + rehearsal harness |
| beacon-spatial | main | de2768c (+ sensors 6c57986) | 13-band binaural + nature layer + modulation presets |
| harmonic-shaper | main | 7f1dfc2 | Standalone additive synth 32-voice |
| harmonic-beacon-tines | main | — | Archived |

## Live test findings (S13, root-caused S14)

- Crowd→beacon master routing WORKS with live camera.
- Shaper voices NOT firing: ROOT CAUSE = weaver manifest declared all features (0,1) but producer `verticality` is signed (-1,1); engine range validation raised and the uncaught exception killed the driver UDP listener thread → permanent absent gate. Fixed in harmonic-weaver b5b5221 (+ regression tests). Offline replay of recorded live session: 0 exceptions, all 5 voices fire.
- CUDA cu126 crash on RTX 2060 (~4.5 min): FIXED by downgrade to torch 2.6.0+cu124 in `.venv` (ultralytics 8.4.100 needs only torch>=1.8). 6-min GPU soak: PASS.
- Engine source lease no auto-recovery: still open → card F5-ENG (t_a86ca0f8).
- Scene design notes: focus bounced across slots 0-4 (YOLO false positives in room) while event-demo watches slots 0-1 only; ankles out of frame at 640x480 → consider 720p framing.

## Useful artifacts

- `/tmp/repro_shaper_routes.py` — offline replay of recorded HarMoCAP jsonl sessions through the real weaver driver + engine (no camera/audio/network). NOTE: /tmp is volatile; re-create from BITACORA S14 description if lost.
- Live session recordings: `/tmp/live-test-session.jsonl`, `/tmp/live-test-session2.jsonl` (also volatile).

## Quick-start for /new

Load BITACORA.md (entries S12–S14), then the rehearsal harness in harmonic-weaver/rehearsal/.
