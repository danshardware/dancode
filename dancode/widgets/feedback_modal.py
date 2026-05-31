"""Feedback modal — lets the user inject steering text into a running task."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea


class FeedbackSubmitted(Message):
    """Posted when the user submits feedback for a task."""
    def __init__(self, task_id: str, feedback: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.feedback = feedback


class FeedbackModal(ModalScreen):
    """Modal for entering steering text / feedback for a running agent."""

    DEFAULT_CSS = """
    FeedbackModal {
        align: center middle;
    }
    FeedbackModal > #dialog {
        width: 70;
        height: auto;
        max-height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    FeedbackModal TextArea {
        height: 10;
        margin: 1 0;
    }
    FeedbackModal #actions {
        layout: horizontal;
        align: right middle;
        height: 3;
    }
    FeedbackModal Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Submit"),
    ]

    def __init__(self, task_id: str, feature_name: str) -> None:
        super().__init__()
        self._task_id = task_id
        self._feature_name = feature_name

    def compose(self) -> ComposeResult:
        with self.app.compose_context():  # type: ignore[attr-defined]
            pass
        # Build the dialog directly
        from textual.containers import Container
        with Container(id="dialog"):
            yield Label(f"Feedback for: [bold]{self._feature_name}[/bold]")
            yield Label(
                "This text will be written to .dancode-feedback.md in the worktree "
                "and sent to the running agent as a HumanReply.",
                classes="muted",
            )
            yield TextArea(id="feedback-input", language="markdown")
            with Container(id="actions"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Submit [Ctrl+S]", id="btn-submit", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-submit":
            self.action_submit()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_submit(self) -> None:
        feedback = self.query_one("#feedback-input", TextArea).text.strip()
        if feedback:
            self.post_message(FeedbackSubmitted(self._task_id, feedback))
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()
