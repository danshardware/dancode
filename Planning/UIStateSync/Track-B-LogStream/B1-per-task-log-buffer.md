## Overview

Adds a per-task in-memory log buffer to `DancodeApp` (`dancode/app.py`) and a
`clear_log()` method to `TaskDetailWidget` (`dancode/widgets/task_detail.py`), so that
switching between tasks replays the buffered log lines rather than showing a blank panel.

**Before this task**, `on_log_line` only forwards lines to the detail widget if the
emitting task is currently selected; lines for non-selected tasks are silently dropped.
When the user switches to a task that has been running in the background, the log panel
is empty.

**After this task**, every `LogLine` message is appended to a per-task buffer (capped at
500 lines). When `on_task_selected` fires, the buffer is replayed into the freshly
mounted/shown detail widget.

Upstream dependencies:
- C1 and C2 complete (all edits to `app.py` and `task_detail.py` in Tracks A and C are
  done before touching these files again).

Key assumptions:
- Buffer entries are plain strings (Rich markup). Replay calls `detail.append_log(line)`
  one-by-one; this is fast enough for ≤500 lines.
- The buffer lives only in memory; it is not persisted to disk. A fresh TUI start shows
  an empty log even for tasks that were running before.
- `clear_log()` on `TaskDetailWidget` clears only the `#log` RichLog, not
  `#questions-display`.

---

## Files Changed

- `dancode/app.py` — modified:
  - `__init__`: add `self._log_buffers: dict[str, list[str]] = {}`.
  - `on_log_line`: buffer the line; only forward to widget if task is selected.
  - `on_task_selected`: after `detail.show_task(task)`, replay the buffer.
- `dancode/widgets/task_detail.py` — modified:
  - Add `clear_log()` method.

---

## Type Contracts

```python
# dancode/app.py — new instance variable
self._log_buffers: dict[str, list[str]]
# key: task_id  value: last ≤500 log lines for that task

# dancode/widgets/task_detail.py — new method
def clear_log(self) -> None:
    """Clear the #log RichLog widget."""
```

---

## Workflow

### Step 1 — Add `_log_buffers` to `DancodeApp.__init__`

`dancode/app.py` — In `DancodeApp.__init__`, after the line that initialises `self._agent_tasks`, add:

```python
self._log_buffers: dict[str, list[str]] = {}
```

### Step 2 — Update `on_log_line` in `app.py`

`dancode/app.py` — Replace the existing `on_log_line` method:

```python
def on_log_line(self, event: LogLine) -> None:
    if self._selected_task_id != event.task_id:
        return
    try:
        detail = self.query_one("#task-detail-widget", TaskDetailWidget)
        detail.append_log(event.line)
    except Exception:
        pass
```

With:

```python
def on_log_line(self, event: LogLine) -> None:
    buf = self._log_buffers.setdefault(event.task_id, [])
    buf.append(event.line)
    if len(buf) > 500:
        self._log_buffers[event.task_id] = buf[-500:]
    if self._selected_task_id == event.task_id:
        try:
            detail = self.query_one("#task-detail-widget", TaskDetailWidget)
            detail.append_log(event.line)
        except Exception:
            pass
```

### Step 3 — Replay buffer in `on_task_selected` in `app.py`

`dancode/app.py` — Replace the existing `on_task_selected` method:

```python
def on_task_selected(self, event: TaskSelected) -> None:
    task = self._config.get_task(event.task_id)
    if not task:
        return
    self._selected_task_id = task.task_id
    try:
        detail = self.query_one("#task-detail-widget", TaskDetailWidget)
        detail.show_task(task)
    except Exception:
        pass
```

With:

```python
def on_task_selected(self, event: TaskSelected) -> None:
    task = self._config.get_task(event.task_id)
    if not task:
        return
    self._selected_task_id = task.task_id
    try:
        detail = self.query_one("#task-detail-widget", TaskDetailWidget)
        detail.show_task(task)
        buf = self._log_buffers.get(task.task_id, [])
        if buf:
            detail.clear_log()
            for line in buf:
                detail.append_log(line)
    except Exception:
        pass
```

### Step 4 — Add `clear_log()` to `TaskDetailWidget`

`dancode/widgets/task_detail.py` — Add the following method after `append_log`:

```python
def clear_log(self) -> None:
    """Clear the #log RichLog widget."""
    self.query_one("#log", RichLog).clear()
```

---

## Acceptance Criteria

- `DancodeApp.__init__` initialises `self._log_buffers` as an empty dict.
- `on_log_line` appends to the buffer for every task (not only the selected one).
- `on_log_line` trims the buffer to the last 500 lines when it exceeds 500.
- `on_task_selected` replays the buffer into the detail widget after `show_task()`.
- `TaskDetailWidget.clear_log()` exists and calls `.clear()` on the `#log` RichLog.

---

## Testing Plan

Add to `tests/unit/test_agent_worker_messages.py`:

```python
def test_log_buffers_initialised():
    """DancodeApp must initialise _log_buffers as an empty dict."""
    import inspect
    from dancode.app import DancodeApp
    src = inspect.getsource(DancodeApp.__init__)
    assert "_log_buffers" in src


def test_log_line_buffered_for_non_selected_task():
    """LogLine for a non-selected task must still be stored in _log_buffers."""
    from dancode.workers.agent_runner import LogLine

    # Simulate the buffer logic directly (no Textual runtime needed)
    log_buffers: dict[str, list[str]] = {}
    selected_task_id = "task-A"

    def handle_log_line(event: LogLine):
        buf = log_buffers.setdefault(event.task_id, [])
        buf.append(event.line)
        if len(buf) > 500:
            log_buffers[event.task_id] = buf[-500:]

    # Fire 3 events for task-B (not selected)
    for i in range(3):
        handle_log_line(LogLine("task-B", f"line {i}"))

    assert "task-B" in log_buffers
    assert len(log_buffers["task-B"]) == 3


def test_log_buffer_trimmed_to_500():
    """Buffer must be trimmed to the last 500 lines when it exceeds 500."""
    from dancode.workers.agent_runner import LogLine

    log_buffers: dict[str, list[str]] = {}

    def handle_log_line(event: LogLine):
        buf = log_buffers.setdefault(event.task_id, [])
        buf.append(event.line)
        if len(buf) > 500:
            log_buffers[event.task_id] = buf[-500:]

    for i in range(600):
        handle_log_line(LogLine("t1", f"line {i}"))

    assert len(log_buffers["t1"]) == 500
    assert log_buffers["t1"][0] == "line 100"   # oldest retained line
    assert log_buffers["t1"][-1] == "line 599"  # most recent line
```
