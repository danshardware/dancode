# The Phase 4→5→6 Code Loop

Phases 4, 5, and 6 have no human gates. Run them with a single command.
The script goes as far as it can and stops only when it genuinely cannot proceed
(a task is BLOCKED or fails QA). Re-run after fixing to resume from where it stopped.

You are responsible for phases 1–3 (plan) and 7–10 (consolidate → release).

---

## Prerequisites

After phase 3 finishes, confirm these exist in the target repo:

```
Planning/<feature-name>/
  README.md
  <track>/
    <task-id>-<name>.md    ← one file per coding task
```

Each task file must have: **Objective**, **Files Changed**, **Workflow**,
**Testing Plan**, **Acceptance Criteria**. Fix any gaps before running.

---

## Run the loop

```bash
uv run python3 scripts/run_loop.py \
  --repo /path/to/your/repo \
  --feature your-feature-name
```

The script runs phases 4 → 5 → 6, and if QA fails it automatically retries up to 3
times (configurable with `--max-retries`). It only stops for human input when a task
is BLOCKED (OpenHands couldn't start or complete it) or all retries are exhausted.

---

## What the script does

| Phase | What happens | Skipped if |
|-------|-------------|------------|
| 4 (Dispatch) | Reads plan, writes `dispatch/` files + `SCHEDULE.md` | `SCHEDULE.md` already exists |
| 5 (Code) | Creates git worktrees, runs OpenHands per task, writes `phase5_status.md` | — |
| 6 (QA) | Reads `phase5_status.md`, runs OpenHands QA reviewer per task, writes `reviews/` | — |

Phases 5 and 6 are **re-entrant**: re-running skips tasks already marked DONE.

---

## When the script stops

### Phase 5 — task BLOCKED

OpenHands couldn't complete the task. The script tells you which task and where its
dispatch file is. Fix one of:

- **The dispatch prompt** (`Planning/<feature>/dispatch/<track>/<task-id>-dispatch.md`) —
  add more context, clarify the steps
- **The plan itself** (`Planning/<feature>/<track>/<task-file>.md`) — then re-run
  phase 4 to regenerate the dispatch file
- **Do it manually** in the worktree, commit, then edit `phase5_status.md` to mark DONE

Resume from phase 5:

```bash
uv run python3 scripts/run_loop.py \
  --repo /path/to/your/repo \
  --feature your-feature-name \
  --start-phase 5
```

If some tasks finished and some were blocked, the script still runs QA on the
completed ones before stopping.

### Phase 6 — task FAIL

The QA reviewer found a blocking issue. The script **automatically retries** up to
`--max-retries` times (default 3). On each retry it:

1. Appends the full review notes to the dispatch file so OpenHands knows exactly what to fix
2. Resets the task status in `phase5_status.md` so phase 5 re-attempts it
3. Re-runs phase 5 → phase 6

If all retries are exhausted and the task still fails, the script stops and prints the
review file path. Fix the code manually in the worktree, then re-run:

```bash
uv run python3 scripts/run_loop.py \
  --repo /path/to/your/repo \
  --feature your-feature-name \
  --start-phase 6
```

Increase `--max-retries` if you want more automatic attempts before it gives up:

```bash
uv run python3 scripts/run_loop.py --repo /path/to/repo --feature my-feature --max-retries 5
```



## Happy path output

```
dancode — Phase 4→5→6 loop
  Repo:    /path/to/repo
  Feature: my-feature
  Model:   minimax.minimax-m2.5

─── Phase 4: Dispatch ───────────────────────────────────────
  [phase 4] Done — dispatch files created.
─── Phase 5: Code ───────────────────────────────────────────
  [phase 5] Done tasks (3): task-01, task-02, task-03
─── Phase 6: QA ─────────────────────────────────────────────
  [phase 6] Passing tasks (3): task-01, task-02, task-03

═══════════════════════════════════════════════════════════════
  Loop complete — all tasks passed QA.
  Next: run phase 7 (Consolidate) to merge worktrees.
═══════════════════════════════════════════════════════════════
```

---

## The loop in practice

For a feature with 3 tasks where task-02 fails QA:

```
First run:
  phase 4 → SCHEDULE.md + dispatch files created
  phase 5 → task-01 DONE, task-02 DONE, task-03 DONE
  phase 6 → task-01 PASS, task-02 FAIL, task-03 PASS
  script exits 1, prints review path for task-02

You read reviews/task-02-review.md, identify the issue.

Re-run with --start-phase 5:
  phase 5 → task-01 SKIPPED (already DONE), task-02 retried, task-03 SKIPPED
  phase 6 → task-01 SKIPPED, task-02 PASS, task-03 SKIPPED
  script exits 0 → proceed to phase 7
```

---

## Monitoring during a run

```bash
# Tail the latest phase log in real time
tail -f ~/.config/dancode/logs/phase5_code/$(ls -t ~/.config/dancode/logs/phase5_code/ | head -1)

# List all worktrees created
git -C /path/to/your/repo worktree list
```
