# Goals — the two planes

> Source document for the `/goal` to be reviewed by the user before launch.

## Plane 1 — Execute the re-architecture plan

Execute all tasks T0.1–T6.3 inherited from `../rearquitectura-ecosistema-beacon/ROADMAP.md` under the mechanics of `ORCHESTRATION.md`:

- F0–F4 complete = the event scenario works: analog beacon sounding through beacon-spatial + harmonic-shaper + harmonic-weaver MVP, live mappings, focus subject controlling one harmonic per limb + head, hot-swappable scenes + global panic, full rehearsal with simulators (no people, no hardware).
- F6 complete = tines, digital-beacon, NaturalHarmony archived with `ARCHIVE.md`, nothing useful left without a destination.
- Every task closed only after CompAII's audit: diff reviewed, tests green, real verification performed (audio renders, contract validates, UI responds).
- BITACORA.md updated per task; double-push (Mar-IA-no + AlterMundi) verified at each merge point.

## Plane 2 — Delegation infrastructure hardening

Make the ia-bridge / Robin / Kanban circuit work flawlessly, using this plan as the test bench:

- **ia-bridge:** eliminate spurious timeouts (per-task timeout policy, observed-duration tuning); verify every configured arm (codex, grok, kimi, hermes) with real pings; fix adapter argument drift when CLIs change.
- **Robin workers:** fix the known failure modes — workers that spawn but never call `kanban_complete`/`kanban_block`, dispatcher that misses ready tasks after a worker crash.
- **Kanban:** board as the durable ledger for this plan; workers report through kanban tools, never raw SQL as a permanent path.
- **Permissions:** derived agents can write to every directory their tasks require and read everything the briefs cite.
- **End state:** any task that *should* be delegated *can* be delegated without manual babysitting. We paid for all these CLIs; the circuit must extract their full value.

## Guard — the planes do not compete

Plane 2 takes priority **only when it blocks real delegation**. If nothing is broken, infrastructure is not touched. No infinite infrastructure projects eating the event timeline.

## Success criteria (observable)

1. `beacon-spatial/webui.py` parses and serves; `/control` responds. (F0)
2. Every active instrument publishes a `*.contract.json` with hash `contract_id` + golden sidecar; the weaver gates connections on it. (F1)
3. `pip install -e .` clean on harmonic-shaper; synth renders audio standalone, no NaN/clipping in smoke render. (F2)
4. A nature sample plays mixed into the spatializer, OSC-controlled via `/beacon/nature/*`. (F3)
5. Full rehearsal script runs end-to-end with simulators; audible audio modulated by simulated sources; scenes hot-swapped; panic kills everything. (F4)
6. Archive checklist verified: nothing in report 04 §6 left unmigrated. (F6)
7. Zero manual interventions in the delegation circuit during the final three waves. (Plane 2)

## Non-goals (for this /goal)

- F5 items (EEG/HR drivers, audio→modulation, phone sensors, surge-bridge extraction, mobile client, Quest/WebXR) — specified in the original plan, not executed here.
- Nature Lab generative layer — noted as a post-event candidate only.
