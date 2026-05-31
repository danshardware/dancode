# usability-improvements — Feature Overview

## What this feature does

Four usability improvements to the dancode TUI and pipeline:

1. **Guidance doc injection** — Wire AGENTS.md and all `.agents/skills/*/SKILL.md` files
   into `shared_overrides` for phases 1–3 so planning agents actually read the project
   conventions before writing plans.

2. **Phase 2 standards enforcement** — Strengthen the Phase 2 (Jank) prompt to explicitly
   audit plans against the coding standards defined in the skill files.

3. **Task restart** — Add `[r] Restart` button for cancelled/done tasks that opens a modal
   to pick a restart phase, optionally edit steering text, and optionally clear
   conversation history from that phase forward.

4. **Phase table widget** — Replace the single-line phase breadcrumb with a per-phase
   table showing status icons and cumulative token counts.

## Dependency graph

```
          ┌─────────────────────────┐
          │  (all parallel, no deps) │
          └────────────┬────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
  001-model       002-guidance   003-flow-updates
  (config.py)     (agent_runner) (flows yamls)
        │
        ├─────────────────────┐
        ▼                     ▼
  004-restart-modal     006-phase-table
        │
        ▼
  005-restart-wiring
  (task_detail + app)
```

Note: Tasks 005 and 006 both touch `dancode/widgets/task_detail.py`.
Run 006 AFTER 005 to avoid merge conflicts (or co-ordinate the merge manually).

## Tracks

| Track | Tasks | Parallel? |
|-------|-------|-----------|
| A — Foundations | 001, 002, 003 | Yes — no file conflicts |
| B — Restart | 004 → 005 | Sequential within track |
| C — Phase table | 006 | After 001; after 005 if sharing task_detail.py |

## Definitions

- **feature_name**: `usability-improvements`
- **repo slug**: dancode (this repo itself)
- **Planning root**: `Planning/usability-improvements/`
