"""New feature modal — collects feature name, description, and options."""

from __future__ import annotations

import uuid

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, TextArea

from dancode.config import FeatureTask


_MODEL_OPTIONS = [
    ("minimax.minimax-m2.5 (default)", "minimax.minimax-m2.5"),
    ("us.anthropic.claude-haiku-3-5-20241022-v1:0 (faster)", "us.anthropic.claude-haiku-3-5-20241022-v1:0"),
    ("us.anthropic.claude-sonnet-4-5-20250929-v1:0 (quality)", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
]


class NewFeatureRequested(Message):
    """Posted when the user submits a new feature request."""
    def __init__(self, task: FeatureTask) -> None:
        super().__init__()
        self.task = task


class NewFeatureModal(ModalScreen):
    """Modal for creating a new feature task."""

    DEFAULT_CSS = """
    NewFeatureModal {
        align: center middle;
    }
    NewFeatureModal > #dialog {
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    NewFeatureModal Input {
        margin: 0 0 1 0;
    }
    NewFeatureModal TextArea {
        height: 8;
        margin: 0 0 1 0;
    }
    NewFeatureModal #actions {
        layout: horizontal;
        align: right middle;
        height: 3;
        margin-top: 1;
    }
    NewFeatureModal Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Submit"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("[bold]New Feature[/bold]")
            yield Label("Feature name (slug, no spaces):")
            yield Input(placeholder="e.g. user-auth-oauth", id="name-input")
            yield Label("Description (what this feature should do):")
            yield TextArea(id="desc-input")
            yield Label("OpenHands coding model:")
            yield Select(
                options=[(label, value) for label, value in _MODEL_OPTIONS],
                value="minimax.minimax-m2.5",
                id="model-select",
            )
            with Container(id="actions"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Create [Ctrl+S]", id="btn-submit", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-submit":
            self.action_submit()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_submit(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        desc = self.query_one("#desc-input", TextArea).text.strip()
        model = self.query_one("#model-select", Select).value or "minimax.minimax-m2.5"

        if not name or not desc:
            return  # silently ignore — user needs to fill both fields

        task = FeatureTask(
            task_id=str(uuid.uuid4())[:8],
            feature_name=name,
            feature_description=desc,
            openhands_model=str(model),
        )
        self.post_message(NewFeatureRequested(task))
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()
