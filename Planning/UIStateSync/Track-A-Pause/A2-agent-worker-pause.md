## Overview

Adds a proper pause/resume mechanism to `AgentWorker` in
`dancode/workers/agent_runner.py`.

**Before this task**, pressing Pause hard-cancels the worker and the next Resume
restarts the phase from scratch with a new worker. **After this task**, pausing suspends
the worker coroutine between phases (the current phase finishes naturally) and resumes it
without creating a new worker. A 30-second force-cancel is applied if the current phase
does not finish within that window; the phase then re-runs from scratch when resumed.

Upstream dependencies:
- A1 must be complete (`TaskStatus.PAUSED` exists).

Key assumptions:
- `AgentWorker.__init__` is always called from the Textual event loop, so
  `asyncio.Event()` created in `__init__` binds to the correct loop (Python 3.10+
  event-loop-less Event creation).
- Cancelling an `asyncio.Task` while it is blocked in `run_in_executor` raises
  `CancelledError` in the coroutine without stopping the underlying executor thread.
  The executor thread runs to completion but its result is discarded. The phase
  re-runs from scratch on resume.
- `asyncio.CancelledError` does NOT inherit from `Exception` in Python 3.8+, so the
  existing `except Exception` handler does not accidentally swallow it.

---

## Files Changed

- `dancode/workers/agent_runner.py` — modified: `AgentWorker.__init__`, `cancel()`,
  `run()` (retry loop + between-phase check); new methods: `pause()`, `resume()`,
  `_force_stop()`.

---

## Type Contracts

```python
class AgentWorker:
    _pause_event: asyncio.Event        # set = running, clear = paused
    _own_task: asyncio.Task | None     # the asyncio Task running self.run()
    _pause_timer_handle: asyncio.TimerHandle | None  # 30s force-stop handle

    def __init__(
        self,
        task: "FeatureTask",
        repo_path: str,
        slug: str,
        post,       # callable(Message)
    ) -> None: ...

    def cancel(self) -> None:
        """Signal the worker to stop cleanly. Also unblocks a paused worker."""

    def pause(self) -> None:
        """
        Request a pause.
        - Clears _pause_event (worker will block before next phase or on CancelledError).
        - Posts TaskStatusChanged(task_id, current_phase, "paused") immediately.
        - Schedules _force_stop() via call_later(30, ...) and stores the handle.
        Must be called from the event loop thread (Textual message handler).
        """

    def resume(self) -> None:
        """
        Unblock a paused worker.
        - Cancels the 30s timer if still pending.
        - Sets _pause_event (unblocks await _pause_event.wait()).
        - Posts TaskStatusChanged(task_id, current_phase, "running").
        Must be called from the event loop thread.
        """

    def _force_stop(self) -> None:
        """Called by call_later after 30s — cancels the own asyncio Task."""

    async def run(self) -> None: ...
```

Mutations to shared state / messages posted:

| Trigger | Message posted |
|---------|---------------|
| `pause()` called | `TaskStatusChanged(task_id, task.phase, "paused")` |
| `resume()` called | `TaskStatusChanged(task_id, task.phase, "running")` |
| `CancelledError` caught after force-stop, awaiting resume | `TaskStatusChanged(task_id, task.phase, "paused")` (redundant but explicit) |
| Resume after force-stop, before phase re-run | `TaskStatusChanged(task_id, task.phase, "running")` |

---

## Workflow

### Step 1 — Add new instance variables to `__init__`

In `AgentWorker.__init__`, after `self._cancelled = False`, add:

```python
self._pause_event: asyncio.Event = asyncio.Event()
self._pause_event.set()          # set = not paused
self._own_task: asyncio.Task | None = None
self._pause_timer_handle: asyncio.TimerHandle | None = None
```

### Step 2 — Update `cancel()`

Replace the existing `cancel()` body:

```python
def cancel(self) -> None:
    self._cancelled = True
    self._pause_event.set()   # unblock a paused worker so it can exit
```

### Step 3 — Add `pause()`

```python
def pause(self) -> None:
    """Request a pause between phases (or force-stop after 30s)."""
    self._pause_event.clear()
    loop = asyncio.get_event_loop()
    self._pause_timer_handle = loop.call_later(30, self._force_stop)
    self._post(TaskStatusChanged(self._task.task_id, self._task.phase, "paused"))
```

### Step 4 — Add `resume()`

```python
def resume(self) -> None:
    """Unblock a paused worker and continue from the next phase."""
    if self._pause_timer_handle is not None:
        self._pause_timer_handle.cancel()
        self._pause_timer_handle = None
    self._pause_event.set()
    self._post(TaskStatusChanged(self._task.task_id, self._task.phase, "running"))
```

### Step 5 — Add `_force_stop()`

```python
def _force_stop(self) -> None:
    """Force-cancel the worker coroutine after the 30s pause timeout fires."""
    self._pause_timer_handle = None   # already fired
    if self._own_task and not self._own_task.done():
        self._own_task.cancel()
```

### Step 6 — Store `_own_task` at the start of `run()`

At the very first line inside `async def run(self)`, before any other code:

```python
self._own_task = asyncio.current_task()
```

### Step 7 — Wrap the executor call in a retry loop

Find the existing `try` block that contains `run_in_executor`. Replace it with a
`while True:` retry loop. The structure must be:

```python
while True:
    try:
        loop = asyncio.get_running_loop()
        runner = AgentRunner(agent_id=agent_id, logs_dir=str(LOGS_DIR))
        result = await loop.run_in_executor(
            None,
            lambda r=runner, s=shared_overrides,
                   sid=_resume_session_id, msgs=_resume_messages,
                   rb=_resume_block: r.run(
                prompt=task.feature_description,
                session_id=sid,
                prior_messages=msgs,
                resume_from_block=rb,
                shared_overrides=s,
            ),
        )
        # Phase completed naturally — disarm force-stop timer
        if self._pause_timer_handle is not None:
            self._pause_timer_handle.cancel()
            self._pause_timer_handle = None

        # Extract token usage
        _conv = result.get("_conv") if isinstance(result, dict) else None
        if _conv is not None:
            _total_tokens = (
                getattr(_conv, "input_tokens", 0)
                + getattr(_conv, "output_tokens", 0)
            )
            task.phase_token_counts[agent_id] = _total_tokens

    except asyncio.CancelledError:
        # Force-stop timer fired; pause_event is already clear
        self._pause_timer_handle = None
        self._post(TaskStatusChanged(task.task_id, task.phase, "paused"))
        await self._pause_event.wait()     # blocks until resume() or cancel()
        if self._cancelled:
            return
        # Resume: clear resume params so the phase re-runs from scratch
        _resume_session_id = None
        _resume_messages = None
        _resume_block = None
        task.status = TaskStatus.RUNNING
        self._post(TaskStatusChanged(task.task_id, task.phase, "running"))
        continue   # retry the while loop (re-run the phase)

    except Exception as exc:
        tb = traceback.format_exc()
        self._post(LogLine(task.task_id, f"[ERROR] Phase {phase}: {exc}\n{tb}"))
        task.status = TaskStatus.BLOCKED
        task.blocked_reason = str(exc)
        self._post(TaskStatusChanged(task.task_id, phase, "blocked", str(exc)))
        return

    break  # executor succeeded, exit retry loop
```

> **Important:** The `except asyncio.CancelledError` clause MUST appear before
> `except Exception` because `CancelledError` does not inherit from `Exception`
> in Python 3.8+. The ordering matters for clarity; Python will NOT accidentally
> catch it with `except Exception`, but placing CancelledError first is correct style.

Also update the existing `logs_dir` setup. Replace:
```python
log_path = LOGS_DIR / f"{self._slug}.jsonl"
log_path.parent.mkdir(parents=True, exist_ok=True)
```
with:
```python
LOGS_DIR.mkdir(parents=True, exist_ok=True)
```
(The `AgentRunner` and its `Logger` create per-agent subdirectories themselves.)

### Step 8 — Add between-phase pause check

After the `while True:` retry loop (i.e., after the phase result has been processed and
before `continue` advances to the next phase), add this block. Insert it after all the
result-processing code (guardrail check, suspension check) and before the `for` loop
naturally advances to the next phase:

```python
# Between-phase pause: block here if the user requested a pause
if not self._pause_event.is_set():
    await self._pause_event.wait()
    if self._cancelled:
        break
```

This is sufficient because `pause()` already posted PAUSED and `resume()` will post
RUNNING when `_pause_event` is set again.

---

## Acceptance Criteria

- `AgentWorker` has methods `pause()`, `resume()`, and `_force_stop()`.
- `AgentWorker.__init__` sets `_pause_event` (set), `_own_task = None`,
  `_pause_timer_handle = None`.
- `cancel()` calls `self._pause_event.set()` in addition to setting `_cancelled`.
- Calling `pause()` followed immediately by `resume()` on a worker that has not yet
  started does not raise.
- The `run()` coroutine stores `asyncio.current_task()` in `self._own_task` as its
  first statement.
- The executor call is inside a `while True:` loop; a caught `CancelledError` clears
  resume params, posts paused+running, and retries via `continue`.
- All existing `tests/unit/test_agent_worker_messages.py` tests pass.

---

## Testing Plan

Add to `tests/unit/test_agent_worker_messages.py`:

```python
import asyncio
import pytest
from unittest.mock import MagicMock
from dancode.config import FeatureTask, TaskPhase, TaskStatus
from dancode.workers.agent_runner import AgentWorker, TaskStatusChanged


def _make_worker():
    task = FeatureTask(
        task_id="t1",
        feature_name="feat",
        feature_description="desc",
    )
    messages = []
    worker = AgentWorker(
        task=task,
        repo_path="/tmp",
        slug="test-slug",
        post=messages.append,
    )
    return worker, task, messages


def test_agent_worker_pause_event_initially_set():
    worker, _, _ = _make_worker()
    assert worker._pause_event.is_set()


def test_agent_worker_cancel_sets_pause_event():
    worker, _, _ = _make_worker()
    worker._pause_event.clear()
    worker.cancel()
    assert worker._pause_event.is_set()
    assert worker._cancelled is True


@pytest.mark.asyncio
async def test_agent_worker_pause_posts_paused_status():
    worker, task, messages = _make_worker()
    task.phase = TaskPhase.PLAN
    # pause() requires running event loop (call_later)
    worker.pause()
    # Disarm the 30s timer immediately to avoid side-effects
    if worker._pause_timer_handle:
        worker._pause_timer_handle.cancel()
    assert any(
        isinstance(m, TaskStatusChanged) and m.status == "paused"
        for m in messages
    )
    assert not worker._pause_event.is_set()


@pytest.mark.asyncio
async def test_agent_worker_resume_posts_running_and_sets_event():
    worker, task, messages = _make_worker()
    task.phase = TaskPhase.PLAN
    worker.pause()
    if worker._pause_timer_handle:
        worker._pause_timer_handle.cancel()
    messages.clear()
    worker.resume()
    assert worker._pause_event.is_set()
    assert any(
        isinstance(m, TaskStatusChanged) and m.status == "running"
        for m in messages
    )
```

These tests require `pytest-asyncio`. No real AWS calls. No fixtures beyond the inline
helpers above.
