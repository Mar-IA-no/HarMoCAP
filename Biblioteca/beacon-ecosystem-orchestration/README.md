# Beacon Ecosystem — Orchestrated Execution

- **Started:** 2026-07-18
- **Status:** pending user GO on /goal
- **Question:** How to execute the beacon ecosystem re-architecture plan with CompAII as persistent orchestrator, delegating all implementation via ia-bridge `/build`, while hardening the delegation infrastructure (ia-bridge / Robin / Kanban) as a first-class workstream.

## Relationship to the original plan

This folder restructures — without modifying — the plan produced by Claude Code (Fable) at
`../rearquitectura-ecosistema-beacon/`:

| Artifact there | Role here |
|---|---|
| `SINTESIS.md` | Analysis, target architecture, closed decisions (§5), user vision (§6). **Unchanged; still authoritative on the "what" and "why".** |
| `ROADMAP.md` | Task list T0.1–T6.3 with sizes and dependencies. **Task definitions inherited verbatim; agent assignments and wave mechanics superseded by `ORCHESTRATION.md` here.** |
| `INFORME_CRUZADO.md` | Reconciliation with Anii's BCP v1; T1.1 scope already updated (both contract planes). |
| `reportes_agentes/` | **The spec.** Briefs cite these reports; no derived agent re-explores the repos. |

## What changed vs. the original plan

1. **Executor model:** one-shot parallel session with Claude on the critical path → persistent orchestration by CompAII with discrete, auditable `/build` dispatches.
2. **Critical path agent:** Claude → **Codex Sol** (`gpt-5.6-sol`, `model_reasoning_effort=xhigh`). Reason: Fable's token budget is exhausted (2026-07-18).
3. **State of truth:** Hermes Kanban board (not session memory). Any session can resume the plan from the board.
4. **Verification:** every build returns → CompAII audits diff + runs tests + performs real verification (audio renders, contract validates, UI responds) → only then the card closes. "The agent said it works" is never sufficient.
5. **Second plane:** ia-bridge / Robin / Kanban hardening runs as a parallel workstream with unblock-priority (see `GOALS.md`).

## Contents

- `ORCHESTRATION.md` — execution mechanics, task-to-agent assignment, waves, audit protocol.
- `GOALS.md` — the two planes, success criteria, guards; source of the `/goal` to be reviewed by the user.
- `kanban/` — seed cards for the board (initial task graph).
- `briefs/` — self-contained dispatch briefs, one per task, citing `reportes_agentes/` as spec. Generated before each dispatch, committed after audit.
