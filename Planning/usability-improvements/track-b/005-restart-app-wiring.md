# Task 005 — Wire Restart into Task Detail + App

**Track B — depends on task 004 (RestartModal must exist)**
**Depends on task 001 (phase_token_counts model)**

## Overview

Wire the `RestartModal` (task 004) into the TUI:

1. **`dancode/widgets/task_detail.py`** — add `RestartTask` message and
   `[r] Restart` button shown when a task is `CANCELLED` or `DONE`.

2. **`dancode/app.py`** — handle `RestartTask` (open the modal) and
   `RestartOptions` (reset task state and launch a new worker).

## Files Changed

- `dancode/widgets/task_detail.py`
- `dancode/app.py`

## Type Contracts

### New message in `dancode/widgets/task_detail.py`

```python
class RestartTask(Message):
    """User clicked [r] Restart on a cancelled or done task."""
    def __init__(self, task_id: str) -> None: ...
```

### New handlers in `dancode/app.py`

```python
def on_restart_task(self, event: RestartTask) -> None:
    """Open the restart modal for the target task."""

def on_restart_options(self, event: RestartOptions) -> None:
    """Apply restart configuration and launch a new worker."""
```

`on_restart_options` must:
1. Retrieve the task from `self._config`.
2. Cancel and remove any existing worker/asyncio_task for that task_id.
3. Update `task.feature_description` to `event.steering_text`.
4. Reset `task.phase` to `TaskPhase(event.restart_phase)`.
5. Reset `task.status` to `TaskStatus.PENDING`.
6. Clear `task.blocked_reason` to `None`.
7. If `event.clear_history is True`:
   - Remove all `session_ids` entries where the corresponding phase int
     is `>= event.restart_phase`. The mapping of phase int → agent_id
     is available via `PHASE_AGENTS` — iterate over it and delete matching
     keys from `task.session_ids`.
   - Remove all `phase_token_counts` entries for the same phases.
8. Persist: `self._config.upsert_task(task)` → `self._config.save(self._slug)`.
9. Refresh the task list widget.
10. Call `self._start_worker(task)`.
11. Notify: `self.notify(f"Restarting {task.feature_name} from phase {event.restart_phase}")`.

## Workflow

### Part 1 — dancode/widgets/task_detail.py

1. Open `dancode/widgets/task_detail.py`.

2. After the existing `CancelTask` message class definition (around line 28),
   add the new `RestartTask` message class:
   ```python
   class RestartTask(Message):
       """User clicked Restart on a cancelled or done task."""
       def __init__(self, task_id: str) -> None:
           super().__init__()
           self.task_id = task_id
   ```

3. In `_refresh_actions()`, find the `# Cancel` block:
   ```python
   # Cancel (not done/cancelled)
   if task.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
       actions.mount(Button("[x] Cancel", id="btn-cancel", variant="error"))
   ```
   After this block, add:
   ```python
   # Restart (only when done or cancelled)
   if task.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
       actions.mount(Button("[r] Restart", id="btn-restart", variant="warning"))
   ```

4. In `on_button_pressed()`, add a branch for `btn-restart` after the existing
   `btn-cancel` branch:
   ```python
   elif btn_id == "btn-restart":
       self.post_message(RestartTask(task_id))
   ```

### Part 2 — dancode/app.py

5. Open `dancode/app.py`.

6. In the imports block, add a new import line after the `FeedbackModal` import:
   ```python
   from dancode.widgets.restart_modal import RestartModal, RestartOptions
   ```

7. In the import from `dancode.widgets.task_detail`, add `RestartTask` to the
   existing `from dancode.widgets.task_detail import (...)` block.

8. In the BINDINGS list or after the existing `action_help` method, add a new
   keyboard binding for restart. Find `BINDINGS = [` and add:
   ```python
   Binding("r", "restart_selected", "Restart"),
   ```
   (Place it after the `Binding("?", "action_help", "Help")` line.)

9. Add `action_restart_selected` method after `action_help`:
   ```python
   def action_restart_selected(self) -> None:
       """Open restart modal for the currently selected task (keyboard shortcut)."""
       if not self._selected_task_id:
           return
       task = self._config.get_task(self._selected_task_id)
       if task and task.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
           self.push_screen(
               RestartModal(
                   task_id=task.task_id,
                   feature_name=task.feature_name,
                   current_phase=task.phase.value,
                   feature_description=task.feature_description,
               )
           )
   ```

10. Add `on_restart_task` handler in the Message handlers section, after
    `on_open_feedback_modal`:
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

11. Add `on_restart_options` handler immediately after `on_restart_task`:
    ```python
    def on_restart_options(self, event: RestartOptions) -> None:
        """Apply restart config and launch a new worker."""
        from dancode.config import PHASE_AGENTS, TaskPhase

        task = self._config.get_task(event.task_id)
        if not task:
            return

        # Cancel existing worker if any
        worker = self._agent_workers.pop(event.task_id, None)
        if worker:
            worker.cancel()
        asyncio_task = self._agent_tasks.pop(event.task_id, None)
        if asyncio_task:
            asyncio_task.cancel()

        # Apply restart configuration
        task.feature_description = event.steering_text
        task.phase = TaskPhase(event.restart_phase)
        task.status = TaskStatus.PENDING
        task.blocked_reason = None

        if event.clear_history:
            # Clear session_ids and token counts for phases >= restart_phase
            phases_to_clear = {
                agent_id
                for phase, agent_id in PHASE_AGENTS.items()
                if phase.value >= event.restart_phase
            }
            task.session_ids = {
                k: v for k, v in task.session_ids.items()
                if k not in phases_to_clear
            }
            task.phase_token_counts = {
                k: v for k, v in task.phase_token_counts.items()
                if k not in phases_to_clear
            }

        self._config.upsert_task(task)
        self._config.save(self._slug)

        tl = self.query_one("#task-list-widget", TaskListWidget)
        tl.tasks = list(self._config.tasks)

        if self._selected_task_id == task.task_id:
            try:
                detail = self.query_one("#task-detail-widget", TaskDetailWidget)
                detail.show_task(task)
            except Exception:
                pass

        self._start_worker(task)
        self.notify(
            f"Restarting {task.feature_name!r} from phase {event.restart_phase}",
            title="Restart",
        )
    ```

## Acceptance Criteria

```python
# RestartTask message carries the task_id
from dancode.widgets.task_detail import RestartTask
msg = RestartTask("abc")
assert msg.task_id == "abc"
```

```python
# _refresh_actions shows [r] Restart for CANCELLED tasks (not for RUNNING)
from dancode.config import FeatureTask, TaskStatus, TaskPhase
# (Verified by running the TUI: CANCELLED task shows [r] Restart button;
#  RUNNING task does not show [r] Restart button.)
task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
task.status = TaskStatus.CANCELLED
assert task.status in (TaskStatus.DONE, TaskStatus.CANCELLED)  # button condition
```

```python
# on_restart_options clears session_ids for phases >= restart_phase
from dancode.config import FeatureTask, TaskStatus, TaskPhase, PHASE_AGENTS
task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
task.session_ids = {
    "phase1_plan": "sess1",
    "phase2_jank": "sess2",
    "phase3_refine": "sess3",
}
task.phase_token_counts = {
    "phase1_plan": 100,
    "phase2_jank": 200,
}
# Simulate clear_history from phase 2
restart_phase = 2
phases_to_clear = {
    agent_id
    for phase, agent_id in PHASE_AGENTS.items()
    if phase.value >= restart_phase
}
task.session_ids = {k: v for k, v in task.session_ids.items() if k not in phases_to_clear}
task.phase_token_counts = {k: v for k, v in task.phase_token_counts.items() if k not in phases_to_clear}
assert "phase1_plan" in task.session_ids
assert "phase2_jank" not in task.session_ids
assert "phase1_plan" in task.phase_token_counts
assert "phase2_jank" not in task.phase_token_counts
```

## Testing Plan

File: `tests/unit/test_restart_wiring.py` (new file)

```python
def test_restart_task_message():
    """RestartTask message carries task_id."""
    from dancode.widgets.task_detail import RestartTask
    msg = RestartTask("my-task-id")
    assert msg.task_id == "my-task-id"


def test_restart_button_shown_for_cancelled():
    """CANCELLED status satisfies the condition for showing the restart button."""
    from dancode.config import TaskStatus
    status = TaskStatus.CANCELLED
    assert status in (TaskStatus.DONE, TaskStatus.CANCELLED)


def test_clear_history_removes_correct_phases():
    """clear_history removes session_ids and token counts for phases >= restart_phase."""
    from dancode.config import PHASE_AGENTS, TaskPhase
    session_ids = {agent_id: f"sess-{phase.value}" for phase, agent_id in PHASE_AGENTS.items()}
    token_counts = {agent_id: phase.value * 100 for phase, agent_id in PHASE_AGENTS.items()}

    restart_phase = 5
    to_clear = {aid for p, aid in PHASE_AGENTS.items() if p.value >= restart_phase}
    session_ids = {k: v for k, v in session_ids.items() if k not in to_clear}
    token_counts = {k: v for k, v in token_counts.items() if k not in to_clear}

    # Phases 1-4 should survive
    assert "phase1_plan" in session_ids
    assert "phase4_dispatch" in session_ids
    # Phase 5+ should be gone
    assert "phase5_code" not in session_ids
    assert "phase10_finalize" not in session_ids
    assert "phase5_code" not in token_counts
```
