# Task 004 — Restart Modal Widget

**Track B — depends on task 001 (phase_token_counts model must exist)**
**Run before task 005**

## Overview

A new `RestartModal` Textual `ModalScreen` that allows the user to restart a
cancelled or completed task. It presents:
- A phase picker (Select widget) — which phase to restart from
- An editable text area pre-filled with the current `feature_description`
- A checkbox: "Clear conversation history from this phase onward"

On submit it emits a `RestartOptions` message. On cancel it closes silently.

## Files Changed

- `dancode/widgets/restart_modal.py` (new file — create from scratch)

## Type Contracts

```python
class RestartOptions(Message):
    """Emitted when the user submits the restart dialog."""
    def __init__(
        self,
        task_id: str,
        restart_phase: int,          # TaskPhase int value (1–10)
        steering_text: str,          # New/edited feature_description to use
        clear_history: bool,         # If True, clear session_ids for phase >= restart_phase
    ) -> None: ...


class RestartModal(ModalScreen):
    """Modal for configuring and confirming a task restart."""
    def __init__(self, task_id: str, feature_name: str, current_phase: int,
                 feature_description: str) -> None: ...
    def compose(self) -> ComposeResult: ...
    def on_button_pressed(self, event: Button.Pressed) -> None: ...
    def action_cancel(self) -> None: ...
    def action_submit(self) -> None: ...
```

## Workflow

1. Create `dancode/widgets/restart_modal.py` with the following exact content:

```python
"""Restart modal — lets the user configure a task restart."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Select, TextArea

from dancode.config import PHASE_NAMES, TaskPhase


class RestartOptions(Message):
    """Posted when the user submits the restart configuration."""

    def __init__(
        self,
        task_id: str,
        restart_phase: int,
        steering_text: str,
        clear_history: bool,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.restart_phase = restart_phase
        self.steering_text = steering_text
        self.clear_history = clear_history


class RestartModal(ModalScreen):
    """Modal for configuring a task restart."""

    DEFAULT_CSS = """
    RestartModal {
        align: center middle;
    }
    RestartModal > #dialog {
        width: 72;
        height: auto;
        max-height: 36;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    RestartModal #title {
        text-style: bold;
        margin-bottom: 1;
    }
    RestartModal Select {
        margin-bottom: 1;
    }
    RestartModal TextArea {
        height: 8;
        margin-bottom: 1;
    }
    RestartModal Checkbox {
        margin-bottom: 1;
    }
    RestartModal #actions {
        layout: horizontal;
        align: right middle;
        height: 3;
    }
    RestartModal Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Restart"),
    ]

    def __init__(
        self,
        task_id: str,
        feature_name: str,
        current_phase: int,
        feature_description: str,
    ) -> None:
        super().__init__()
        self._task_id = task_id
        self._feature_name = feature_name
        self._current_phase = current_phase
        self._feature_description = feature_description

    def compose(self) -> ComposeResult:
        phase_options = [
            (f"{phase.value}: {PHASE_NAMES[phase]}", phase.value)
            for phase in TaskPhase
        ]
        with Container(id="dialog"):
            yield Label(
                f"[bold]Restart:[/bold] {self._feature_name}", id="title"
            )
            yield Label("Restart from phase:")
            yield Select(
                options=phase_options,
                value=self._current_phase,
                id="phase-select",
            )
            yield Label("Steering / feature description (editable):")
            yield TextArea(self._feature_description, id="steering-text")
            yield Checkbox(
                "Clear conversation history from selected phase onward",
                id="clear-history",
                value=False,
            )
            with Container(id="actions"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("[ctrl+s] Restart", id="btn-restart", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Cancel and Restart button clicks."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-restart":
            self.action_submit()

    def action_cancel(self) -> None:
        """Dismiss without emitting anything."""
        self.dismiss()

    def action_submit(self) -> None:
        """Emit RestartOptions and dismiss."""
        phase_select = self.query_one("#phase-select", Select)
        steering_area = self.query_one("#steering-text", TextArea)
        clear_cb = self.query_one("#clear-history", Checkbox)

        restart_phase = int(phase_select.value) if phase_select.value is not Select.BLANK else self._current_phase
        steering_text = steering_area.text.strip() or self._feature_description
        clear_history = bool(clear_cb.value)

        self.post_message(
            RestartOptions(
                task_id=self._task_id,
                restart_phase=restart_phase,
                steering_text=steering_text,
                clear_history=clear_history,
            )
        )
        self.dismiss()
```

2. Do not modify any other file in this task.

## Acceptance Criteria

```python
# RestartOptions message carries correct data
from dancode.widgets.restart_modal import RestartOptions
msg = RestartOptions("abc", 3, "new desc", True)
assert msg.task_id == "abc"
assert msg.restart_phase == 3
assert msg.steering_text == "new desc"
assert msg.clear_history is True
```

```python
# RestartModal can be instantiated without error
from dancode.widgets.restart_modal import RestartModal
modal = RestartModal("tid", "my-feature", 5, "original description")
assert modal._task_id == "tid"
assert modal._current_phase == 5
```

```python
# BINDINGS include escape → cancel and ctrl+s → submit
from dancode.widgets.restart_modal import RestartModal
binding_keys = [b.key for b in RestartModal.BINDINGS]
assert "escape" in binding_keys
assert "ctrl+s" in binding_keys
```

## Testing Plan

File: `tests/unit/test_restart_modal.py` (new file)

```python
def test_restart_options_fields():
    """RestartOptions carries all submitted fields."""
    from dancode.widgets.restart_modal import RestartOptions
    msg = RestartOptions("t1", 2, "steering", False)
    assert msg.task_id == "t1"
    assert msg.restart_phase == 2
    assert msg.steering_text == "steering"
    assert msg.clear_history is False


def test_restart_modal_instantiation():
    """RestartModal can be instantiated with valid arguments."""
    from dancode.widgets.restart_modal import RestartModal
    modal = RestartModal("t1", "feat", 4, "desc")
    assert modal._task_id == "t1"
    assert modal._feature_name == "feat"
    assert modal._current_phase == 4
    assert modal._feature_description == "desc"


def test_restart_modal_bindings():
    """RestartModal has escape and ctrl+s bindings."""
    from dancode.widgets.restart_modal import RestartModal
    keys = {b.key for b in RestartModal.BINDINGS}
    assert "escape" in keys
    assert "ctrl+s" in keys
```
