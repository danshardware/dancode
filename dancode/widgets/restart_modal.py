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