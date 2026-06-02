## Overview

Restructures the `#reply-box` container in `TaskDetailWidget`
(`dancode/widgets/task_detail.py`) so that when the agent is waiting for a human reply,
the main log is hidden and the reply box takes its place, displaying the agent's
questions in a scrollable `RichLog` (`#questions-display`) above the text-input area.

**Before this task**, the reply box is hidden below the log (not in place of it), the
agent's questions are written into the main log (which is not cleared on task switch),
and the reply box contains a static `Label` that says "Agent is waiting for your reply:"
regardless of what the agent actually asked.

**After this task**, when `status == WAITING` and `pending_checkpoint` is set:
- The main `#log` widget is hidden (`display = False`).
- The `#reply-box` is shown in its place (`height: 1fr`).
- The agent's questions are written into `#questions-display` (a `RichLog` inside
  the reply box).
- When the task transitions back to RUNNING (reply submitted), the log is shown again
  and the reply box is hidden.

Upstream dependencies:
- A1–A4 complete (no shared-file conflict with Track C).

Key assumption: Textual's `display = False` on a widget removes it from layout
completely. Two sibling widgets both having `height: 1fr` and one being hidden means
the visible one fills all available vertical space.

---

## Files Changed

- `dancode/widgets/task_detail.py` — modified:
  - `DEFAULT_CSS`: update `#reply-box` rules; add `#questions-display` rule; remove
    the `Label` rule inside `#reply-box`.
  - `compose()`: replace the `Label` inside `#reply-box` with a
    `RichLog(id="questions-display")`.
  - `_refresh_reply_box()`: rewrite to hide/show `#log` and write questions to
    `#questions-display` instead of `#log`.

---

## Type Contracts

No new public methods. One internal method changes signature/behaviour:

```python
def _refresh_reply_box(self) -> None:
    """
    Show or hide the reply box based on whether the task is waiting at a human gate.

    When waiting (status == WAITING and pending_checkpoint is set):
      - self.query_one("#log").display = False
      - self.query_one("#reply-box").display = True
      - writes questions to self.query_one("#questions-display")
      - focuses #reply-area

    When not waiting:
      - self.query_one("#log").display = True
      - self.query_one("#reply-box").display = False
    """
```

No mutations to `shared` state. No messages posted.

---

## Workflow

### Step 1 — Update `DEFAULT_CSS`

Find and replace the relevant CSS rules. The current CSS for `#reply-box` and the
Label inside it is:

```css
TaskDetailWidget #reply-box {
    height: auto;
    margin-top: 1;
    border: solid $warning;
    padding: 0 1;
}
TaskDetailWidget #reply-box Label {
    color: $warning;
    margin-bottom: 1;
}
TaskDetailWidget #reply-area {
    height: 5;
    margin-bottom: 1;
}
```

Replace with:

```css
TaskDetailWidget #reply-box {
    display: none;
    height: 1fr;
    layout: vertical;
    border: solid $warning;
    padding: 0 1;
}
TaskDetailWidget #questions-display {
    height: 1fr;
    border: solid $warning-darken-2;
    margin-bottom: 1;
}
TaskDetailWidget #reply-area {
    height: 5;
    margin-bottom: 1;
}
```

Notes:
- `display: none` as the default state means the widget is invisible until
  `reply_box.display = True` is set in Python.
- Remove the `TaskDetailWidget #reply-box Label` block entirely (no Label remains
  inside `#reply-box` after Step 2).

### Step 2 — Update `compose()`

Inside `compose()`, find the `with Container(id="reply-box"):` block:

```python
with Container(id="reply-box"):
    yield Label("[bold]Agent is waiting for your reply:[/bold]")
    yield TextArea(id="reply-area")
    yield Button("Submit reply [Ctrl+S]", id="btn-reply-submit", variant="warning")
```

Replace with:

```python
with Container(id="reply-box"):
    yield RichLog(id="questions-display", highlight=False, markup=True, wrap=True,
                  max_lines=100)
    yield TextArea(id="reply-area")
    yield Button("Submit reply [Ctrl+S]", id="btn-reply-submit", variant="warning")
```

`RichLog` is already imported at the top of the file. No new import needed.

### Step 3 — Rewrite `_refresh_reply_box()`

Replace the entire `_refresh_reply_box` method with:

```python
def _refresh_reply_box(self) -> None:
    if not self._current_feature:
        return
    waiting = (
        self._current_feature.status == TaskStatus.WAITING
        and bool(self._current_feature.pending_checkpoint)
    )
    log = self.query_one("#log", RichLog)
    reply_box = self.query_one("#reply-box")
    if waiting:
        log.display = False
        reply_box.display = True
        q_display = reply_box.query_one("#questions-display", RichLog)
        q_display.clear()
        questions = self._current_feature.pending_questions
        if not questions and self._current_feature.pending_checkpoint:
            # Recover questions from checkpoint for sessions saved before
            # pending_questions was introduced.
            try:
                from engine.state import load_checkpoint
                cp = load_checkpoint(self._current_feature.pending_checkpoint)
                action_input = cp.get("action_input", {})
                if isinstance(action_input, dict):
                    questions = (
                        action_input.get("questions")
                        or action_input.get("message")
                        or ""
                    )
                else:
                    questions = str(action_input) if action_input else ""
                if questions:
                    self._current_feature.pending_questions = questions
            except Exception:
                pass
        q_display.write(questions or "Agent is waiting for your reply.")
        self.query_one("#reply-area", TextArea).focus()
    else:
        log.display = True
        reply_box.display = False
```

---

## Acceptance Criteria

- `TaskDetailWidget.compose()` yields a `RichLog` with `id="questions-display"` inside
  `#reply-box`. No `Label` is yielded inside `#reply-box`.
- `DEFAULT_CSS` contains `TaskDetailWidget #questions-display` with `height: 1fr`.
- `DEFAULT_CSS` does NOT contain `TaskDetailWidget #reply-box Label`.
- `DEFAULT_CSS` for `#reply-box` sets `display: none` and `layout: vertical`.
- `_refresh_reply_box()` sets `log.display = False` and `reply_box.display = True`
  when waiting, and the reverse when not waiting.
- `_refresh_reply_box()` writes questions to `#questions-display`, NOT to `#log`.

---

## Testing Plan

Add to `tests/unit/test_restart_modal.py` or a new file
`tests/unit/test_task_detail_widget.py`:

```python
import pytest
from textual.app import App, ComposeResult
from dancode.config import FeatureTask, TaskPhase, TaskStatus
from dancode.widgets.task_detail import TaskDetailWidget


class _TestApp(App):
    def compose(self) -> ComposeResult:
        yield TaskDetailWidget(id="detail")


@pytest.mark.asyncio
async def test_reply_box_hidden_by_default():
    async with _TestApp().run_test() as pilot:
        reply_box = pilot.app.query_one("#reply-box")
        assert not reply_box.display


@pytest.mark.asyncio
async def test_questions_display_present():
    """#questions-display RichLog must exist inside #reply-box."""
    from textual.widgets import RichLog
    async with _TestApp().run_test() as pilot:
        q = pilot.app.query_one("#questions-display", RichLog)
        assert q is not None


@pytest.mark.asyncio
async def test_log_shown_when_not_waiting():
    async with _TestApp().run_test() as pilot:
        detail = pilot.app.query_one("#detail", TaskDetailWidget)
        task = FeatureTask(
            task_id="t1",
            feature_name="feat",
            feature_description="desc",
            status=TaskStatus.RUNNING,
        )
        detail.show_task(task)
        await pilot.pause()
        log = pilot.app.query_one("#log")
        assert log.display
```
