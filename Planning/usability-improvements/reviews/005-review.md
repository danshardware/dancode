# Task 005 Review — Wire Restart into Task Detail + App

## Summary

Task 005 was supposed to wire the RestartModal (from task 004) into the TUI by:
1. Adding a RestartTask message and [r] Restart button in task_detail.py
2. Adding on_restart_task and on_restart_options handlers in app.py

## Diff Analysis

### Changes Present in the Diff

**dancode/widgets/task_detail.py:**
- ✅ Added `RestartTask` message class (lines 32-36)
- ✅ Added [r] Restart button for DONE/CANCELLED tasks (lines 177-179)
- ✅ Added handler for `btn-restart` to post RestartTask message (lines 196-197)

**dancode/app.py:**
- ✅ Added imports for RestartModal, RestartOptions
- ✅ Added import for RestartTask
- ✅ Added keyboard binding for "r" restart action
- ✅ Added `action_restart_selected()` method
- ✅ Added help text for the restart action

### All Required Items Present

All handlers required by the spec are present in app.py:

1. ✅ **`on_restart_task` handler** — Opens RestartModal when the [r] button posts a RestartTask message
2. ✅ **`on_restart_options` handler** — Cancels existing worker, resets task state (phase, status, blocked_reason), clears session_ids and token counts for phases >= restart_phase when clear_history is set, persists config, starts new worker
3. ✅ **Test file `tests/unit/test_restart_wiring.py`** — Exists and covers RestartTask message, button visibility logic, and clear_history phase filtering

### Functional Analysis

The implementation is complete and correct:

1. **Button flow**: Clicking [r] in task_detail.py posts `RestartTask(...)`, which is handled by `on_restart_task` in app.py — opens the RestartModal correctly.

2. **Modal result flow**: When RestartModal dismisses with RestartOptions, `on_restart_options` handles it — cancels any existing worker, resets phase/status/history as configured, persists state, and starts a new worker.

3. **Keyboard shortcut**: `action_restart_selected()` provides the same modal flow via the `r` binding.

All tests pass (`uv run pytest tests/ -v` exits 0).

## Verdict

All spec requirements are implemented and functional.

VERDICT: PASS