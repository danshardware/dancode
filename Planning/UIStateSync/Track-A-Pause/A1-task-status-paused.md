## Overview

Adds `PAUSED = "paused"` to the `TaskStatus` enum in `dancode/config.py`.

`PAUSED` is a transient status: a worker that is paused will emit a `TaskStatusChanged`
message with status `"paused"` when it suspends between phases, and will emit `"running"`
again when it resumes. Because `on_task_status_changed` saves the config on every status
change, a PAUSED task **will** be written to disk. On the next TUI startup, any task whose
persisted status is `"paused"` should be treated the same as `"pending"` (worker not
started). The `on_mount` handler in `app.py` only auto-resumes `RUNNING` tasks, so PAUSED
tasks will correctly remain idle on restart.

No migration is needed — `Pydantic` will raise `ValidationError` on unknown enum values
only if strict mode is used; the project uses the default `str` coercion for `TaskStatus`,
so old JSON without `"paused"` is unaffected.

**Upstream dependencies:** None. This is the first task.

**Key assumption:** `TaskStatus` is a `str` enum, so `TaskStatus("paused")` works without
any special deserialisation code.

---

## Files Changed

- `dancode/config.py` — modified: add `PAUSED = "paused"` to `TaskStatus` enum.

---

## Type Contracts

```python
class TaskStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    WAITING   = "waiting"
    PAUSED    = "paused"   # NEW — add after WAITING
    BLOCKED   = "blocked"
    DONE      = "done"
    CANCELLED = "cancelled"
```

No other signatures change.

---

## Workflow

1. Open `dancode/config.py`.
2. Locate the `TaskStatus` class (currently 6 members: PENDING, RUNNING, WAITING,
   BLOCKED, DONE, CANCELLED).
3. Add one line after `WAITING = "waiting"`:
   ```python
   PAUSED    = "paused"
   ```
4. Do not change anything else — no imports, no other classes.

---

## Acceptance Criteria

- `from dancode.config import TaskStatus; TaskStatus("paused")` does not raise.
- `TaskStatus.PAUSED.value == "paused"`.
- `len(TaskStatus) == 7`.
- All existing tests in `tests/unit/test_config.py` continue to pass.

---

## Testing Plan

Add one test function to `tests/unit/test_config.py`:

```python
def test_task_status_paused_exists():
    assert TaskStatus.PAUSED == TaskStatus("paused")
    assert TaskStatus.PAUSED.value == "paused"
    assert len(TaskStatus) == 7
```

No real AWS calls required. No fixtures needed beyond the existing import.
