## Overview

Rewrites the `on_pause_resume_task` handler in `dancode/app.py` to use the new
`AgentWorker.pause()` and `AgentWorker.resume()` methods instead of hard-cancelling
and restarting the worker.

**Before this task**, `on_pause_resume_task` cancels the worker and asyncio task when
pausing, and creates a brand-new worker when resuming. **After this task**, it calls
`worker.pause()` (which suspends the existing coroutine between phases) and
`worker.resume()` (which unblocks it), leaving the worker alive throughout.

The `TaskStatusChanged` messages posted by `pause()`/`resume()` flow through the
existing `on_task_status_changed` handler, which handles config save and UI refresh.
No additional list-refresh calls are needed in `on_pause_resume_task`.

Upstream dependencies:
- A1 complete (`TaskStatus.PAUSED` exists).
- A2 complete (`AgentWorker.pause()` and `AgentWorker.resume()` exist).

---

## Files Changed

- `dancode/app.py` — modified: `on_pause_resume_task` method body replaced.
- `dancode/app.py` — modified: `action_help` — remove the `a — Approve gate` shortcut
  line (it will be fully removed in C2, but removing the misleading help text here
  avoids confusion while A-track work is in flight).

---

## Type Contracts

No new signatures. The method signature of `on_pause_resume_task` is unchanged:

```python
def on_pause_resume_task(self, event: PauseResumeTask) -> None: ...
```

---

## Workflow

### Step 1 — Replace `on_pause_resume_task`

`dancode/app.py` — Find the existing `on_pause_resume_task` method (currently ~25 lines; it pops the
worker and asyncio task from dicts and cancels them). Replace the entire method body
with:

```python
def on_pause_resume_task(self, event: PauseResumeTask) -> None:
    task = self._config.get_task(event.task_id)
    worker = self._agent_workers.get(event.task_id)
    if not task or not worker:
        return
    if task.status == TaskStatus.PAUSED:
        worker.resume()
    elif task.status == TaskStatus.RUNNING:
        worker.pause()
    else:
        # WAITING (human gate) and BLOCKED tasks are not controlled via [p].
        # WAITING tasks must be replied to via the inline reply box.
        # BLOCKED tasks must be restarted via [r].
        self.notify(
            "Use the reply box to respond, or [r] to restart a blocked task.",
            title="Cannot pause/resume",
            severity="warning",
        )
    # TaskStatusChanged posted by pause()/resume() flows through
    # on_task_status_changed, which saves config and refreshes the task list.
```

Do not call `tl.tasks = ...` here — `on_task_status_changed` handles that.
Do not pop the worker or asyncio task from the dicts — the worker stays alive.

### Step 2 — Remove misleading help text

`dancode/app.py` — In `action_help`, find the line:
```python
"  a        — Approve gate\n"
```
Delete that line from the help string. (The Approve gate is being fully removed in C2.)

---

## Acceptance Criteria

- `assert len([l for l in inspect.getsource(DancodeApp.on_pause_resume_task).splitlines() if l.strip()]) <= 15` (excluding def line, docstring, and blank lines).
- When `task.status == TaskStatus.PAUSED`, only `worker.resume()` is called — no
  `worker.cancel()`, no `asyncio_task.cancel()`, no new worker created.
- When `task.status == TaskStatus.RUNNING`, only `worker.pause()` is called.
- When `task.status` is neither `PAUSED` nor `RUNNING` (e.g. WAITING or BLOCKED),
  `self.notify(...)` is called with `severity="warning"` — no worker method is called:
  `assert 'severity="warning"' in inspect.getsource(DancodeApp.on_pause_resume_task)`.
- `assert 'self._agent_workers.pop' not in inspect.getsource(DancodeApp.on_pause_resume_task)`.
- `assert 'self._agent_tasks.pop' not in inspect.getsource(DancodeApp.on_pause_resume_task)`.
- `assert '"Approve gate"' not in inspect.getsource(DancodeApp.action_help)`.
- All existing tests pass.

---

## Testing Plan

No new unit tests are needed for this handler directly — it delegates entirely to
`worker.pause()`/`worker.resume()` whose behaviour is tested in A2. Integration-level
verification:

```
Manual check: start a task, let it enter RUNNING, press [p].
Expected: status changes to PAUSED. Press [p] again.
Expected: status changes back to RUNNING and the worker continues.
```

Add one structural test to `tests/unit/test_agent_worker_messages.py` to confirm the
method no longer touches the worker registry:

```python
def test_on_pause_resume_task_does_not_pop_worker(monkeypatch):
    """on_pause_resume_task must call pause()/resume(), not cancel the worker."""
    # This is a static analysis check — verify the source does not contain
    # the old cancel pattern inside on_pause_resume_task.
    import inspect
    from dancode.app import DancodeApp
    src = inspect.getsource(DancodeApp.on_pause_resume_task)
    assert "worker.cancel()" not in src
    assert "asyncio_task.cancel()" not in src
    assert "worker.pause()" in src
    assert "worker.resume()" in src
```
