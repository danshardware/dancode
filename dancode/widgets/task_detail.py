"""Task detail widget — main panel showing phase progress and live log."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label, RichLog

from dancode.config import (
    FeatureTask,
    TaskPhase,
    TaskStatus,
    PHASE_NAMES,
)


class ApproveGate(Message):
    """User clicked Approve on a waiting gate."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class CancelTask(Message):
    """User clicked Cancel on a task."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class PauseResumeTask(Message):
    """User clicked Pause/Resume."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class OpenFeedbackModal(Message):
    """User clicked Feedback — open modal to inject steering."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class ViewDiff(Message):
    """User wants to see the git diff for this task."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class TaskDetailWidget(Widget):
    """Right-side detail panel for the selected task."""

    DEFAULT_CSS = """
    TaskDetailWidget {
        height: 1fr;
        padding: 0 1;
    }
    TaskDetailWidget #phase-breadcrumb {
        height: 1;
        margin-bottom: 1;
        color: $text-muted;
    }
    TaskDetailWidget #task-title {
        text-style: bold;
        margin-bottom: 1;
    }
    TaskDetailWidget #log {
        height: 1fr;
        border: solid $primary-darken-2;
    }
    TaskDetailWidget #actions {
        height: 3;
        margin-top: 1;
        layout: horizontal;
    }
    TaskDetailWidget Button {
        margin-right: 1;
        min-width: 14;
    }
    TaskDetailWidget #blocked-reason {
        color: red;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._task: FeatureTask | None = None

    def compose(self) -> ComposeResult:
        yield Label("", id="task-title")
        yield Label("", id="phase-breadcrumb")
        yield RichLog(id="log", highlight=True, markup=True, wrap=True, max_lines=200)
        yield Label("", id="blocked-reason")
        yield Widget(id="actions")

    def show_task(self, task: FeatureTask) -> None:
        """Display a (new) task in the detail panel."""
        self._task = task
        self._refresh_header()
        self._refresh_actions()

    def update_task(self, task: FeatureTask) -> None:
        """Update an already-displayed task (status/phase changed)."""
        self._task = task
        self._refresh_header()
        self._refresh_actions()

    def append_log(self, line: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(line)

    def _refresh_header(self) -> None:
        if not self._task:
            return
        task = self._task
        title = self.query_one("#task-title", Label)
        title.update(f"[bold]{task.feature_name}[/bold]  [{task.status}]")

        breadcrumb = self.query_one("#phase-breadcrumb", Label)
        parts = []
        for phase in TaskPhase:
            name = PHASE_NAMES[phase]
            if phase == task.phase:
                parts.append(f"[bold reverse] {phase}: {name} [/]")
            elif phase < task.phase:
                parts.append(f"[dim] {phase}: {name} [/]")
            else:
                parts.append(f" {phase}: {name} ")
        breadcrumb.update(" → ".join(parts))

        blocked = self.query_one("#blocked-reason", Label)
        if task.status == TaskStatus.BLOCKED and task.blocked_reason:
            blocked.update(f"[red]BLOCKED: {task.blocked_reason}[/red]")
        else:
            blocked.update("")

    def _refresh_actions(self) -> None:
        if not self._task:
            return
        task = self._task
        actions = self.query_one("#actions", Widget)
        # Remove existing buttons
        for btn in list(actions.query(Button)):
            btn.remove()

        # Pause/Resume (only when running or waiting)
        if task.status in (TaskStatus.RUNNING, TaskStatus.WAITING):
            actions.mount(Button("[p] Pause/Resume", id="btn-pause", variant="default"))

        # Feedback (only when running)
        if task.status == TaskStatus.RUNNING:
            actions.mount(Button("[f] Feedback", id="btn-feedback", variant="primary"))

        # View diff (if worktree exists)
        if task.worktree_path:
            actions.mount(Button("[v] Diff", id="btn-diff", variant="default"))

        # Approve gate (only when waiting)
        if task.status == TaskStatus.WAITING:
            actions.mount(Button("[a] Approve", id="btn-approve", variant="success"))

        # Cancel (not done/cancelled)
        if task.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
            actions.mount(Button("[x] Cancel", id="btn-cancel", variant="error"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self._task:
            return
        task_id = self._task.task_id
        btn_id = event.button.id
        if btn_id == "btn-pause":
            self.post_message(PauseResumeTask(task_id))
        elif btn_id == "btn-feedback":
            self.post_message(OpenFeedbackModal(task_id))
        elif btn_id == "btn-diff":
            self.post_message(ViewDiff(task_id))
        elif btn_id == "btn-approve":
            self.post_message(ApproveGate(task_id))
        elif btn_id == "btn-cancel":
            self.post_message(CancelTask(task_id))
