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

§ 2026-07-18 — NVIDIA driver upgraded 550.163.01 → 610.43.02 (CUDA repo, DKMS, rebooted, verified). This targets the torch/cu124 intermittent illegal-instruction crash hypothesis. Next live/soak run doubles as the smoke test: if no crash on driver 610, close the infra issue; if it crashes, hypothesis dead, keep CPU fallback.

## Live audio routing quirks (R24)
- After an unclean boot, WirePlumber may not profile the R24 even though ALSA sees it (card exists, PCM OK, device missing from wpctl/GNOME). Fix: `systemctl --user restart wireplumber` — the R24 node appears and becomes default sink (it is the configured default).
- pw-jack (scsynth) does NOT re-link its outputs after a wireplumber restart: manually `pw-link SuperCollider:out_1 <R24 sink>:playback_FL` and `out_2 -> playback_FR`. sounddevice (shaper) re-links itself to the default sink automatically.

## Shaper silent via sounddevice — ROOT CAUSE SOLVED (2026-07-19)
PortAudio/sounddevice through the PipeWire ALSA plugin renders SILENCE on this host (links exist, callback runs at real-time cadence, DSP verified non-silent via recorder tap rms=0.32, nothing reaches ears; aplay through the same ALSA 'default' PCM IS audible). The audible path is JACK under pw-jack — the historical working setup. Fixes: harmonic-shaper audio_engine adopts the JACK server sample rate (else PaErrorCode -9997); start-live-stack.sh launches the shaper via `pw-jack ... --device "R24 Analog Stereo"` (override: --shaper-device / SHAPER_DEVICE env). JACK server runs at 48000 Hz; R24 device substring must be unique ('R24' alone matches the 8-ch Surround node first -> invalid channels).
