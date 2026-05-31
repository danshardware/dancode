"""DancodeApp — main Textual application."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer, Header, Label

from dancode.config import (
    FeatureTask,
    ProjectConfig,
    TaskStatus,
    LOGS_DIR,
)
from dancode.widgets.feedback_modal import FeedbackModal, FeedbackSubmitted
from dancode.widgets.new_feature_modal import NewFeatureModal, NewFeatureRequested
from dancode.widgets.task_detail import (
    ApproveGate,
    CancelTask,
    OpenFeedbackModal,
    PauseResumeTask,
    TaskDetailWidget,
    ViewDiff,
)
from dancode.widgets.task_list import OpenEditor, TaskListWidget, TaskSelected
from dancode.workers.agent_runner import AgentWorker, LogLine, TaskStatusChanged


class DancodeApp(App):
    """Main dancode TUI."""

    TITLE = "dancode"
    SUB_TITLE = "multi-agent coding workflow"

    CSS = """
    Screen {
        layout: horizontal;
    }
    #main-area {
        width: 1fr;
        height: 1fr;
        layout: vertical;
    }
    #empty-label {
        align: center middle;
        color: $text-muted;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("n", "new_feature", "New Feature"),
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]

    def __init__(
        self,
        config: ProjectConfig,
        slug: str,
        repo_path: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._slug = slug
        self._repo_path = repo_path
        self._selected_task_id: str | None = None
        self._workers: dict[str, AgentWorker] = {}
        self._asyncio_tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]

    # ------------------------------------------------------------------ Layout

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield TaskListWidget(id="task-list-widget")
            with Container(id="main-area"):
                if self._config.tasks:
                    yield TaskDetailWidget(id="task-detail-widget")
                else:
                    yield Label(
                        "Press [bold]n[/bold] to create your first feature.",
                        id="empty-label",
                    )
        yield Footer()

    def on_mount(self) -> None:
        tl = self.query_one("#task-list-widget", TaskListWidget)
        tl.tasks = list(self._config.tasks)
        # Auto-resume any running tasks
        for task in self._config.tasks:
            if task.status in (TaskStatus.RUNNING,):
                self._start_worker(task)

    # ------------------------------------------------------------------ Actions

    def action_new_feature(self) -> None:
        self.push_screen(NewFeatureModal())

    def action_help(self) -> None:
        help_lines = (
            "[bold]Keyboard shortcuts[/bold]\n"
            "  n        — New feature\n"
            "  e        — Open editor at selected task's worktree\n"
            "  q        — Quit\n"
            "  p        — Pause/Resume selected task\n"
            "  f        — Give feedback to running agent\n"
            "  v        — View diff\n"
            "  a        — Approve gate\n"
            "  x        — Cancel task\n"
        )
        from textual.widgets import RichLog
        try:
            log = self.query_one("#log", RichLog)
            log.write(help_lines)
        except Exception:
            self.notify(help_lines, title="Help")

    # ------------------------------------------------------------------ Worker management

    def _start_worker(self, task: FeatureTask) -> None:
        if task.task_id in self._workers:
            return  # already running

        worker = AgentWorker(
            task=task,
            repo_path=self._repo_path,
            slug=self._slug,
            post=self._post_from_thread,
        )
        self._workers[task.task_id] = worker

        asyncio_task = asyncio.get_event_loop().create_task(worker.run())
        self._asyncio_tasks[task.task_id] = asyncio_task

    def _post_from_thread(self, message) -> None:  # type: ignore[override]
        """Thread-safe message post (called from executor threads)."""
        self.call_from_thread(self.post_message, message)

    # ------------------------------------------------------------------ Message handlers

    def on_new_feature_requested(self, event: NewFeatureRequested) -> None:
        task = event.task
        self._config.upsert_task(task)
        self._config.save(self._slug)

        # Update task list
        tl = self.query_one("#task-list-widget", TaskListWidget)
        tl.tasks = list(self._config.tasks)

        # Replace empty label if present
        try:
            self.query_one("#empty-label").remove()
            self.query_one("#main-area", Container).mount(
                TaskDetailWidget(id="task-detail-widget")
            )
        except Exception:
            pass

        # Show detail panel
        try:
            detail = self.query_one("#task-detail-widget", TaskDetailWidget)
            detail.show_task(task)
        except Exception:
            pass

        self._selected_task_id = task.task_id
        self._start_worker(task)

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

    def on_task_status_changed(self, event: TaskStatusChanged) -> None:
        task = self._config.get_task(event.task_id)
        if not task:
            return
        task.status = TaskStatus(event.status)
        if event.phase is not None:
            task.phase = event.phase
        if event.reason:
            task.blocked_reason = event.reason
        self._config.upsert_task(task)
        self._config.save(self._slug)

        tl = self.query_one("#task-list-widget", TaskListWidget)
        tl.tasks = list(self._config.tasks)

        if self._selected_task_id == task.task_id:
            try:
                detail = self.query_one("#task-detail-widget", TaskDetailWidget)
                detail.update_task(task)
            except Exception:
                pass

        if event.status == "done":
            self.notify(f"{task.feature_name} complete!", title="Done")
        elif event.status == "blocked":
            self.notify(
                f"{task.feature_name} blocked: {event.reason}",
                title="Blocked",
                severity="error",
            )

    def on_log_line(self, event: LogLine) -> None:
        if self._selected_task_id != event.task_id:
            return
        try:
            detail = self.query_one("#task-detail-widget", TaskDetailWidget)
            detail.append_log(event.line)
        except Exception:
            pass

    def on_open_editor(self, event: OpenEditor) -> None:
        editor = os.environ.get("EDITOR", "code")
        subprocess.Popen([editor, event.worktree_path])

    def on_open_feedback_modal(self, event: OpenFeedbackModal) -> None:
        task = self._config.get_task(event.task_id)
        if task:
            self.push_screen(FeedbackModal(task.task_id, task.feature_name))

    def on_feedback_submitted(self, event: FeedbackSubmitted) -> None:
        task = self._config.get_task(event.task_id)
        if not task or not task.worktree_path:
            self.notify("No worktree found for this task.", severity="warning")
            return
        fb_path = Path(task.worktree_path) / ".dancode-feedback.md"
        try:
            fb_path.write_text(event.feedback, encoding="utf-8")
            self.notify("Feedback written to worktree.", title="Feedback")
        except OSError as exc:
            self.notify(str(exc), severity="error")

    def on_approve_gate(self, event: ApproveGate) -> None:
        task = self._config.get_task(event.task_id)
        if not task:
            return
        task.status = TaskStatus.RUNNING
        task.blocked_reason = None
        self._config.upsert_task(task)
        self._config.save(self._slug)
        tl = self.query_one("#task-list-widget", TaskListWidget)
        tl.tasks = list(self._config.tasks)
        # Remove old worker entry so we can restart
        self._workers.pop(event.task_id, None)
        self._start_worker(task)
        self.notify(f"Resumed {task.feature_name}", title="Approved")

    def on_cancel_task(self, event: CancelTask) -> None:
        task = self._config.get_task(event.task_id)
        if not task:
            return
        worker = self._workers.pop(event.task_id, None)
        if worker:
            worker.cancel()
        asyncio_task = self._asyncio_tasks.pop(event.task_id, None)
        if asyncio_task:
            asyncio_task.cancel()
        task.status = TaskStatus.CANCELLED
        self._config.upsert_task(task)
        self._config.save(self._slug)
        tl = self.query_one("#task-list-widget", TaskListWidget)
        tl.tasks = list(self._config.tasks)

    def on_pause_resume_task(self, event: PauseResumeTask) -> None:
        task = self._config.get_task(event.task_id)
        if not task:
            return
        if task.status == TaskStatus.RUNNING:
            worker = self._workers.pop(event.task_id, None)
            if worker:
                worker.cancel()
            asyncio_task = self._asyncio_tasks.pop(event.task_id, None)
            if asyncio_task:
                asyncio_task.cancel()
            task.status = TaskStatus.WAITING
            self._config.upsert_task(task)
            self._config.save(self._slug)
            self.notify("Task paused.", title="Paused")
        elif task.status in (TaskStatus.WAITING, TaskStatus.BLOCKED):
            task.status = TaskStatus.RUNNING
            task.blocked_reason = None
            self._config.upsert_task(task)
            self._config.save(self._slug)
            self._workers.pop(event.task_id, None)
            self._start_worker(task)
            self.notify("Task resumed.", title="Resumed")
        tl = self.query_one("#task-list-widget", TaskListWidget)
        tl.tasks = list(self._config.tasks)

    def on_view_diff(self, event: ViewDiff) -> None:
        task = self._config.get_task(event.task_id)
        if not task or not task.worktree_path:
            self.notify("No worktree found.", severity="warning")
            return
        try:
            result = subprocess.run(
                ["git", "diff", "main...HEAD"],
                cwd=task.worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            diff = result.stdout or "(no diff)"
        except Exception as exc:
            diff = str(exc)
        try:
            detail = self.query_one("#task-detail-widget", TaskDetailWidget)
            detail.append_log("\n--- git diff main...HEAD ---\n" + diff[:5000])
        except Exception:
            pass
