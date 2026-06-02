## Overview

Removes all `ApproveGate`-related code from `dancode/widgets/task_detail.py` and
`dancode/app.py`.

Per design decision: the human-reply inline box is the only reply path. The `ApproveGate`
message class, the `on_approve_gate` handler, and the import in `app.py` are dead code
once C1 is complete (the inline reply box handles all WAITING states). Removing them
eliminates an unused code path and clarifies that there is exactly one reply mechanism.

The `on_approve_gate` handler in `app.py` currently restarts the worker on
`WAITING` tasks via `_start_worker` — but after Track A the worker stays alive through
pauses, and after Track C the correct reply path is always `_handle_reply`. Keeping this
dead path risks confusion.

Upstream dependencies:
- C1 complete (reply box restructure done — no overlap during editing of `task_detail.py`).

Key assumptions:
- No flow YAML or agent code calls `ApproveGate` directly; it is a pure UI message.
- Searching the codebase confirms `ApproveGate` is only referenced in `task_detail.py`
  and `app.py`.

---

## Files Changed

- `dancode/widgets/task_detail.py` — modified:
  - Delete the `ApproveGate` class definition.
  - Remove the `"btn-approve"` case from `on_button_pressed`.
  - (No approve button was being mounted in `_refresh_actions`, so nothing to remove
    there.)
- `dancode/app.py` — modified:
  - Remove `ApproveGate` from the import of `dancode.widgets.task_detail`.
  - Delete the `on_approve_gate` method.
  - Update `action_help` to remove the `a — Approve gate` shortcut line (if not already
    removed in A3).

---

## Type Contracts

Deletions only. After this task:

```python
# task_detail.py — ApproveGate class NO LONGER EXISTS
# app.py — on_approve_gate method NO LONGER EXISTS
# app.py — ApproveGate NOT imported from dancode.widgets.task_detail
```

---

## Workflow

### Step 1 — Delete `ApproveGate` from `task_detail.py`

Find and delete the entire class:

```python
class ApproveGate(Message):
    """User clicked Approve on a waiting gate."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id
```

### Step 2 — Remove `"btn-approve"` case from `on_button_pressed`

In `on_button_pressed`, if there is a case:
```python
elif btn_id == "btn-approve":
    self.post_message(ApproveGate(task_id))
```
Delete those two lines. (Check that this case exists; if it was never added, skip.)

### Step 3 — Remove `ApproveGate` from the import in `app.py`

Find:
```python
from dancode.widgets.task_detail import (
    ApproveGate,
    CancelTask,
    InlineReplySubmitted,
    OpenFeedbackModal,
    PauseResumeTask,
    RestartTask,
    TaskDetailWidget,
    ViewDiff,
)
```

Remove `ApproveGate,` from this import block.

### Step 4 — Delete `on_approve_gate` from `app.py`

Find and delete the entire method:

```python
def on_approve_gate(self, event: ApproveGate) -> None:
    task = self._config.get_task(event.task_id)
    if not task:
        return
    task.status = TaskStatus.RUNNING
    task.blocked_reason = None
    self._config.upsert_task(task)
    self._config.save(self._slug)
    tl = self.query_one("#task-list-widget", TaskListWidget)
    tl.tasks = list(self._config.tasks)
    # Remove old worker entry so we can restart
    self._agent_workers.pop(event.task_id, None)
    self._start_worker(task)
    self.notify(f"Resumed {task.feature_name}", title="Approved")
```

### Step 5 — Remove `a — Approve gate` from `action_help`

In `action_help`, if the string `"  a        — Approve gate\n"` is still present
(it should have been removed in A3), delete it now. If already absent, skip.

---

## Acceptance Criteria

- `ApproveGate` class does NOT exist in `dancode/widgets/task_detail.py`.
- `on_approve_gate` method does NOT exist in `dancode/app.py`.
- `ApproveGate` is NOT imported anywhere in `dancode/app.py`.
- `grep -r "ApproveGate" dancode/` returns zero matches.
- All existing tests pass (no test references `ApproveGate`).

---

## Testing Plan

No new test functions needed — the criterion is absence of code.

Add one negative test to confirm it is gone:

```python
def test_approve_gate_class_deleted():
    """ApproveGate must not exist in task_detail after removal."""
    import dancode.widgets.task_detail as td
    assert not hasattr(td, "ApproveGate")


def test_approve_gate_not_imported_in_app():
    import dancode.app as app_module
    assert not hasattr(app_module, "ApproveGate")
```

Place these in `tests/unit/test_agent_worker_messages.py` or a new file
`tests/unit/test_approve_gate_removed.py`.
