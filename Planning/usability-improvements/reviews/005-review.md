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

### Missing from the Diff (Required by Spec)

The task spec explicitly requires these handlers in app.py, but they are NOT present:

1. **Missing: `on_restart_task` handler**
   - Should handle the RestartTask message when user clicks the [r] button
   - Required code (from spec):
     ```python
     def on_restart_task(self, event: RestartTask) -> None:
         """Open restart modal when [r] button is pressed in the detail panel."""
         task = self._config.get_task(event.task_id)
         if not task:
             return
         self.push_screen(
             RestartModal(
                 task_id=task.task_id,
                 feature_name=task.feature_name,
                 current_phase=task.phase.value,
                 feature_description=task.feature_description,
             )
         )
     ```

2. **Missing: `on_restart_options` handler**
   - Should handle RestartOptions from modal and actually restart the task
   - Required code is ~60 lines that: cancels existing worker, resets task state, clears history, persists, and starts new worker
   - See spec lines 150-208 for full implementation

3. **Missing test file**: The task spec requires `tests/unit/test_restart_wiring.py` but it does not exist.

### Functional Analysis

The current implementation is broken:

1. **Button flow broken**: Clicking [r] button in task_detail.py posts `RestartTask(...)` message, but there's NO `on_restart_task` handler in app.py to receive it. The message will be silently ignored.

2. **Modal result flow broken**: Even if on_restart_task were added, when RestartModal returns RestartOptions, there's NO `on_restart_options` handler to process it. The restart cannot complete.

3. **Keyboard shortcut partial**: The `action_restart_selected()` method works for keyboard shortcut, but without the handlers above, it also cannot complete the restart flow.

## Verdict

The code changes implement only half of the wiring. The button and keyboard shortcut can open the RestartModal (via action_restart_selected), but:
- Button clicks cannot trigger the modal (no on_restart_task handler)
- Modal results cannot restart the task (no on_restart_options handler)

This is a **FAIL** - the core restart functionality is incomplete and non-functional.

## Blocking Issues

- Missing `on_restart_task` handler in app.py to respond to RestartTask messages
- Missing `on_restart_options` handler in app.py to process RestartOptions and restart the task
- Missing test file `tests/unit/test_restart_wiring.py`

VERDICT: FAIL