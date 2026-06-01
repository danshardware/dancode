"""Task detail widget — main panel showing phase progress and live log."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.binding import Binding
from textual.widgets import Button, Label, RichLog, Static, TextArea

from dancode.config import (
    FeatureTask,
    PHASE_AGENTS,
    TaskPhase,
    TaskStatus,
    PHASE_NAMES,
)


_STATUS_ICONS = {
    "done": "[green]✓[/green]",
    "running": "[bold cyan]▶[/bold cyan]",
    "waiting": "[yellow]⏸[/yellow]",
    "blocked": "[red]✗[/red]",
    "cancelled": "[dim]✗[/dim]",
    "pending": "[dim] [/dim]",
}


def _render_phase_table(task: FeatureTask) -> str:
    """Return Rich-markup string of all 10 phases with status and token counts."""
    lines: list[str] = []
    for phase in TaskPhase:
        agent_id = PHASE_AGENTS[phase]
        tokens = task.phase_token_counts.get(agent_id)
        tok_str = f"{tokens:,} tok" if tokens is not None else "—"

        if phase < task.phase:
            icon = _STATUS_ICONS["done"]
            name_style = "[dim]"
            name_end = "[/dim]"
        elif phase == task.phase:
            icon = _STATUS_ICONS.get(task.status.value, _STATUS_ICONS["pending"])
            name_style = "[bold]"
            name_end = "[/bold]"
        else:
            icon = _STATUS_ICONS["pending"]
            name_style = "[dim]"
            name_end = "[/dim]"

        lines.append(
            f" {icon}  {phase.value:>2}  {name_style}{PHASE_NAMES[phase]:<18}{name_end}"
            f"  [dim]{tok_str}[/dim]"
        )
    return "\n".join(lines)


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


class RestartTask(Message):
    """User clicked Restart on a cancelled or done task."""
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



class InlineReplySubmitted(Message):
    """User submitted a reply via the inline reply box (WAITING state)."""
    def __init__(self, task_id: str, reply: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.reply = reply


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
    TaskDetailWidget #phase-table {
        height: auto;
        margin-bottom: 1;
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
    """

    BINDINGS = [
        Binding("ctrl+s", "submit_reply", "Submit reply", show=False),
    ]

    def __init__(self, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._current_feature: FeatureTask | None = None

    def compose(self) -> ComposeResult:
        from textual.containers import Container
        yield Label("", id="task-title")
        yield Static("", id="phase-table", markup=True)
        yield RichLog(id="log", highlight=True, markup=True, wrap=True, max_lines=200)
        with Container(id="reply-box"):
            yield Label("[bold]Agent is waiting for your reply:[/bold]")
            yield TextArea(id="reply-area")
            yield Button("Submit reply [Ctrl+S]", id="btn-reply-submit", variant="warning")
        yield Label("", id="blocked-reason")
        yield Widget(id="actions")

    def show_task(self, task: FeatureTask) -> None:
        """Display a (new) task in the detail panel."""
        self._current_feature = task
        self._refresh_header()
        self._refresh_reply_box()
        self._refresh_actions()

    def update_task(self, task: FeatureTask) -> None:
        """Update an already-displayed task (status/phase changed)."""
        self._current_feature = task
        self._refresh_header()
        self._refresh_reply_box()
        self._refresh_actions()

    def append_log(self, line: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(line)

    def _refresh_reply_box(self) -> None:
        if not self._current_feature:
            return
        waiting = (
            self._current_feature.status == TaskStatus.WAITING
            and bool(self._current_feature.pending_checkpoint)
        )
        reply_box = self.query_one("#reply-box")
        reply_box.display = waiting
        if waiting:
            questions = self._current_feature.pending_questions
            if not questions and self._current_feature.pending_checkpoint:
                # Recover questions from checkpoint for sessions saved before
                # pending_questions was introduced
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
            if questions:
                log = self.query_one("#log", RichLog)
                log.clear()
                log.write(
                    f"[yellow]Agent is waiting for your reply:[/yellow]\n\n"
                    f"{questions}"
                )
            self.query_one("#reply-area", TextArea).focus()

    def _refresh_header(self) -> None:
        if not self._current_feature:
            return
        task = self._current_feature
        title = self.query_one("#task-title", Label)
        title.update(f"[bold]{task.feature_name}[/bold]  [{task.status}]")

        phase_table = self.query_one("#phase-table", Static)
        phase_table.update(_render_phase_table(task))

        blocked = self.query_one("#blocked-reason", Label)
        if task.status == TaskStatus.BLOCKED and task.blocked_reason:
            blocked.update(f"[red]BLOCKED: {task.blocked_reason}[/red]")
        else:
            blocked.update("")

    def _refresh_actions(self) -> None:
        if not self._current_feature:
            return
        task = self._current_feature
        actions = self.query_one("#actions", Widget)
        # Remove existing buttons
        for btn in list(actions.query(Button)):
            btn.remove()

        # Pause/Resume (only when running or waiting)
        if task.status in (TaskStatus.RUNNING, TaskStatus.WAITING):
            actions.mount(Button("[p] Pause/Resume", id="btn-pause", variant="default"))

        # Feedback (only when running, not waiting — waiting uses inline box)
        if task.status == TaskStatus.RUNNING:
            actions.mount(Button("[f] Feedback", id="btn-feedback", variant="primary"))

        # View diff (if worktree exists)
        if task.worktree_path:
            actions.mount(Button("[v] Diff", id="btn-diff", variant="default"))

        # Cancel (not done/cancelled)
        if task.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
            actions.mount(Button("[x] Cancel", id="btn-cancel", variant="error"))

        # Restart (always available)
        actions.mount(Button("[r] Restart", id="btn-restart", variant="warning"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self._current_feature:
            return
        task_id = self._current_feature.task_id
        btn_id = event.button.id
        if btn_id == "btn-pause":
            self.post_message(PauseResumeTask(task_id))
        elif btn_id == "btn-feedback":
            self.post_message(OpenFeedbackModal(task_id))
        elif btn_id == "btn-diff":
            self.post_message(ViewDiff(task_id))
        elif btn_id == "btn-reply-submit":
            self.action_submit_reply()
        elif btn_id == "btn-cancel":
            self.post_message(CancelTask(task_id))
        elif btn_id == "btn-restart":
            self.post_message(RestartTask(task_id))

    def action_submit_reply(self) -> None:
        """Submit the inline reply to the waiting agent."""
        if not self._current_feature:
            return
        reply = self.query_one("#reply-area", TextArea).text.strip()
        if not reply:
            return
        self.post_message(InlineReplySubmitted(self._current_feature.task_id, reply))
        self.query_one("#reply-area", TextArea).clear()
