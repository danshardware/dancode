"""Task list widget — left sidebar showing all feature tasks at a glance."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from dancode.config import FeatureTask, TaskPhase, TaskStatus, PHASE_NAMES


_STATUS_STYLE = {
    TaskStatus.RUNNING:   "bold green",
    TaskStatus.WAITING:   "bold yellow",
    TaskStatus.BLOCKED:   "bold red",
    TaskStatus.DONE:      "dim",
    TaskStatus.PENDING:   "white",
    TaskStatus.CANCELLED: "dim red",
}

_STATUS_SYMBOL = {
    TaskStatus.RUNNING:   "▶",
    TaskStatus.WAITING:   "⏸",
    TaskStatus.BLOCKED:   "✗",
    TaskStatus.DONE:      "✓",
    TaskStatus.PENDING:   "○",
    TaskStatus.CANCELLED: "⊘",
}


class TaskSelected(Message):
    """Posted when the user selects a task in the list."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


class OpenEditor(Message):
    """Posted when the user presses 'e' to open the editor at a worktree."""
    def __init__(self, worktree_path: str) -> None:
        super().__init__()
        self.worktree_path = worktree_path


class TaskListWidget(Widget):
    """Left-sidebar task list with keyboard navigation."""

    DEFAULT_CSS = """
    TaskListWidget {
        width: 36;
        border-right: solid $primary-darken-2;
    }
    TaskListWidget > Label#header {
        background: $primary-darken-3;
        width: 100%;
        padding: 0 1;
        text-style: bold;
    }
    TaskListWidget ListView {
        height: 1fr;
    }
    """

    tasks: reactive[list[FeatureTask]] = reactive([], layout=True)

    def compose(self) -> ComposeResult:
        yield Label("  Tasks", id="header")
        yield ListView(id="task-list")

    def watch_tasks(self, new_tasks: list[FeatureTask]) -> None:
        lv = self.query_one("#task-list", ListView)
        lv.clear()
        for task in new_tasks:
            lv.append(self._make_item(task))

    def _make_item(self, task: FeatureTask) -> ListItem:
        style = _STATUS_STYLE.get(task.status, "white")
        symbol = _STATUS_SYMBOL.get(task.status, "?")
        phase_name = PHASE_NAMES.get(task.phase, str(task.phase))
        name = task.feature_name[:20]
        label = f"[{style}]{symbol}[/] {name}\n  [{style}]Phase {task.phase}: {phase_name}[/]"
        item = ListItem(Label(label), id=f"task-{task.task_id}")
        return item

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id and event.item.id.startswith("task-"):
            task_id = event.item.id[len("task-"):]
            self.post_message(TaskSelected(task_id))

    def on_key(self, event) -> None:  # type: ignore[override]
        if event.key == "e":
            lv = self.query_one("#task-list", ListView)
            if lv.highlighted_child and lv.highlighted_child.id:
                task_id = lv.highlighted_child.id[len("task-"):]
                task = next((t for t in self.tasks if t.task_id == task_id), None)
                if task and task.worktree_path:
                    self.post_message(OpenEditor(task.worktree_path))

    def refresh_task(self, task: FeatureTask) -> None:
        """Update a single task row without rebuilding the whole list."""
        for i, t in enumerate(self.tasks):
            if t.task_id == task.task_id:
                self.tasks[i] = task
                break
        # Trigger reactive re-render
        self.tasks = list(self.tasks)
