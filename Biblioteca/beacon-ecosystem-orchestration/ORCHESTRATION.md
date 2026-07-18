# Orchestration — execution mechanics

> 2026-07-18. Supersedes the agent-assignment and wave mechanics of `../rearquitectura-ecosistema-beacon/ROADMAP.md`. Task definitions, sizes, and dependencies are inherited unchanged.

## Roles

- **CompAII (Hermes, kimi-k3, thinking xhigh):** orchestrator. Dispatches briefs via ia-bridge `/build`, audits every returned build (diff + tests + real verification), maintains the Kanban board and BITACORA, fixes delegation infrastructure when it blocks. Does not write implementation code while delegation capacity exists.
- **Codex Sol** (`gpt-5.6-sol`, `model_reasoning_effort=xhigh`): critical path and delicate work — contract templates, router core design+implementation, merge resolution, SuperCollider/DSP integration, clipping diagnosis, e2e rehearsal.
- **Grok** (`grok-4.5`, `--effort max`): well-specified medium tasks — manifests from templates, migrations with known destinations, drivers from specs, checklist verifications.
- **kimi-cli** (`kimi-code/k3`): pure mechanics — scaffolding, deletions, document moves, ARCHIVE.md from written checklists. Requires edit-capability validation in T0.2 smoke test; if it fails, its tasks fall to Grok.
- **Hermes/deepseek-v4-flash:** reserve via ia-bridge.

## Dispatch channel

`ia-bridge-mcp` (`~/Projects/ia-bridge-mcp`), `build.sh --task "<brief>" --agent codex|grok|kimi|hermes [--with-review] [--timeout-seconds N] [--model ...]`. Verified on this machine 2026-07-18. For Codex Sol tasks: `--model gpt-5.6-sol` + `model_reasoning_effort=xhigh`.

Timeouts: default 600 s is too short for M/L tasks — set per-task (S: 900, M: 1800, L: 3600) and tune from observed durations; every timeout fix is logged under the infra plane.

## Golden rules

1. **Briefs cite reports as spec.** No derived agent re-explores the repos. If a brief is insufficient, the failure belongs to the brief — fix the brief, redispatch.
2. **No commit without audit.** Derived agents work in the working tree; CompAII audits `git diff` + build log, runs tests, performs real verification (audio renders / contract validates / UI responds), then commits.
3. **Kanban is the ledger.** Every task is a card; workers report via `kanban_complete`/`kanban_block`; state survives sessions.
4. **Escalation:** any task that fails twice via delegation → CompAII diagnoses whether the failure is brief, agent, or infrastructure; infrastructure failures route to the infra plane with unblock priority.
5. **Cross-audit without Claude:** critical-path outputs (contracts, router core) get a blind `/second-opinion` review via ia-bridge in addition to CompAII's audit.

## Task → agent assignment (updated)

| Task | Agent | Notes |
|------|-------|-------|
| T0.1 webui.py merge fix | **Codex Sol** | delicate merge, keep both features |
| T0.2 digital-beacon cleanup | kimi | smoke test for edit capability |
| T0.3 beacon-spatial docs | Grok | report 03 §2 is the spec |
| T0.4 beacon-spatial reorder | kimi | depends T0.1 |
| T1.1 contract templates (both planes) | **Codex Sol** | reconcile with Anii's BCP v1 first |
| T1.2 beacon-spatial manifest + bidirectional state | **Codex Sol** | 69 OSCdefs formalization |
| T1.3 shaper manifest | Grok | from T1.1 template |
| T2.1 harmonic-shaper scaffolding | kimi | |
| T2.2 shaper extraction + fork reconciliation | **Codex Sol** | largest migration |
| T2.3 note source port | Grok | brief cites `harmonics.py`/`key_mapper.py` |
| T2.4 tests + clipping diagnosis | **Codex Sol** | escalate to issue if deep |
| T3.1 resonant_filter + sample_layer migration | Grok | vendorize `nh_analysis.mask` |
| T3.2 sample_player → beacon.scd, `/beacon/nature/*` | **Codex Sol** | SuperCollider; verify with rendered audio |
| T3.3 sample_modulator split | Grok + CompAII review of the cut | |
| T3.4 samples move | kimi | |
| T4.1 weaver core design | **Codex Sol** | cites `digital_beacon/api.py` as primary implementation reference |
| T4.2 headless routing engine | **Codex Sol** | |
| T4.3a HarMoCAP driver | Grok | nico-kit is the spec |
| T4.3b MIDI driver | kimi | |
| T4.3c ECG driver | Grok | wrap `ECGProcessor` |
| T4.4 web patchbay client | **Codex Sol** | over interaction sketch; §6 criterion: patching feels like performance |
| T4.5 e2e integration + rehearsal | **Codex Sol** + CompAII final verification | never descoped |
| T6.1–T6.3 archives | kimi / Grok (T6.2 verification) | |

## Waves (dispatch-time parallelism, not session parallelism)

1. **Wave 1:** T0.1 (Codex Sol) ∥ T0.2 + T0.3 + T2.1 + T6.1 (kimi/Grok) — plus smoke test of every arm.
2. **Wave 2:** T1.1 (Codex Sol) ∥ T0.4 (kimi).
3. **Wave 3:** T1.2 (Codex Sol) ∥ T1.3 (Grok) ∥ T4.1 (Codex Sol, sequential after T1.1).
4. **Wave 4:** T2.2 (Codex Sol) ∥ T3.1 (Grok) ∥ T4.3a/c (Grok) ∥ T4.3b (kimi).
5. **Wave 5:** T4.2 (Codex Sol) ∥ T2.3, T3.3 (Grok) ∥ T2.4, T3.2 (Codex Sol).
6. **Wave 6:** T4.4 (Codex Sol) ∥ T3.4 (kimi) → T4.5.
7. **Close:** T6.2, T6.3; BITACORA; double-push verified on both remotes.

Critical path: **T1.1 → T4.1 → T4.2 → T4.5** (all Codex Sol, audited by CompAII). Descope order under pressure: T4.4 (editable route table instead of visual matrix), T2.4 (clipping → issue). Never T4.5.
