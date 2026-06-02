# UI State Synchronization — Execution Map

**Goal:** Make the dancode TUI reliably mirror actual execution state. Fix three broken
integration points without restructuring the architecture (stay within Textual
message-passing).

---

## Problem Summary

| # | Problem | Root Cause |
|---|---------|------------|
| 1 | Pausing a job is a hard cancel+restart | `PauseResumeTask` cancels the worker instead of pausing it; `AgentWorker` has no pause mechanism |
| 2 | Log panel is blank/stale when switching tasks; engine-internal events are invisible | No per-task log buffer; `event_stream.py` wired to non-existent path; engine logs go to JSONL only |
| 3 | Human gate is discovered by accident (buried in log) | Reply mode writes questions to the main log and doesn't hide it |

---

## Directory Structure

```
Planning/UIStateSync/
  README.md                         ← this file
  Track-A-Pause/
    A1-task-status-paused.md        ← add PAUSED enum value
    A2-agent-worker-pause.md        ← pause/resume/force-stop mechanism
    A3-app-pause-handler.md         ← rewrite on_pause_resume_task
    A4-widget-paused-rendering.md   ← PAUSED style in list + detail
  Track-C-HumanGate/
    C1-reply-box-restructure.md     ← questions-display + log hide/show
    C2-remove-approve-gate.md       ← delete dead ApproveGate code
  Track-B-LogStream/
    B1-per-task-log-buffer.md       ← buffer + replay on task switch
    B2-jsonl-tail-and-session-id.md ← pre-gen session_id + JSONL tail
    B3-delete-event-stream.md       ← delete unused event_stream.py
```

---

## Execution Order

**These tracks are NOT parallel.** All three share `app.py`; A and B share
`agent_runner.py`; A and C share `task_detail.py`. The mandatory order is:

```
Track A  (A1 → A2 → A3 → A4)
              ↓
Track C  (C1 → C2)
              ↓
Track B  (B1 → B2 → B3)
```

Each task in a track may start as soon as the previous task's acceptance criteria pass.

---

## Files Touched

| File | Tasks |
|------|-------|
| `dancode/config.py` | A1 |
| `dancode/workers/agent_runner.py` | A2, B2 |
| `dancode/app.py` | A3, C2, B1 |
| `dancode/widgets/task_list.py` | A4 |
| `dancode/widgets/task_detail.py` | A4, C1, C2, B1 |
| `engine/runner.py` | B2 |
| `dancode/workers/event_stream.py` | B3 (deleted) |

---

## Key Design Decisions

1. **Pause is between-phase by default.** A pause request clears `_pause_event` and
   posts PAUSED status immediately. The current phase continues in the executor thread
   but the worker blocks before starting the next phase. A 30-second timer triggers a
   force-cancel of the asyncio task if the phase does not complete naturally; the phase
   then re-runs from scratch on resume.

2. **No Approve button.** The human-reply inline box is the only reply path. The
   `ApproveGate` message class, `on_approve_gate` handler, and all references are
   deleted. (Phase-8 REVIEW gates still use `pending_checkpoint`; users submit via
   the inline box.)

3. **JSONL tail provides engine-internal visibility.** The worker pre-generates a
   session_id so the log path is known before the phase starts. A coroutine tails the
   JSONL file concurrently with the executor and posts `LogLine` for key events.

4. **Per-task log buffer (500-line cap) prevents blank log on task switch.** When the
   user selects a different task the buffer is replayed into the log widget.

---

## Out of Scope

- Mid-phase interruption of a running LLM call (force-stop restarts the phase).
- Replacing Textual message-passing with an observable state bus.
- Structural UI changes beyond the reply-mode toggle and PAUSED rendering.
