## Overview

Adds visual representation of `TaskStatus.PAUSED` to both the task-list sidebar and
the task detail panel.

Both widgets use lookup dicts (`_STATUS_STYLE` / `_STATUS_SYMBOL` in `task_list.py`;
`_STATUS_ICONS` in `task_detail.py`) that are keyed by `TaskStatus` or its string
value. Without this task, a PAUSED task would fall through to the default `"?"` symbol
and `"white"` style, producing confusing output.

Upstream dependencies:
- A1 complete (`TaskStatus.PAUSED` exists).
- A2 and A3 complete (PAUSED status is now actually emitted).

Key assumption: `WAITING` already uses `"⏸"` as its symbol. Using the same glyph for
PAUSED (but in magenta vs yellow) is intentional — the color distinguishes the two
states. Magenta = user-initiated pause; yellow = system waiting for human input.

---

## Files Changed

- `dancode/widgets/task_list.py` — modified: add `TaskStatus.PAUSED` to `_STATUS_STYLE`
  and `_STATUS_SYMBOL`.
- `dancode/widgets/task_detail.py` — modified: add `"paused"` to `_STATUS_ICONS`.

---

## Type Contracts

No new functions or classes. Changes are dict literal additions:

```python
# task_list.py
_STATUS_STYLE: dict[TaskStatus, str]   # adds TaskStatus.PAUSED → "bold magenta"
_STATUS_SYMBOL: dict[TaskStatus, str]  # adds TaskStatus.PAUSED → "⏸"

# task_detail.py
_STATUS_ICONS: dict[str, str]          # adds "paused" → "[magenta]⏸[/magenta]"
```

---

## Workflow

### Step 1 — Update `_STATUS_STYLE` in `task_list.py`

`dancode/widgets/task_list.py` — Find:
```python
_STATUS_STYLE = {
    TaskStatus.RUNNING:   "bold green",
    TaskStatus.WAITING:   "bold yellow",
    TaskStatus.BLOCKED:   "bold red",
    TaskStatus.DONE:      "dim",
    TaskStatus.PENDING:   "white",
    TaskStatus.CANCELLED: "dim red",
}
```

Add one entry after `TaskStatus.WAITING`:
```python
    TaskStatus.PAUSED:    "bold magenta",
```

### Step 2 — Update `_STATUS_SYMBOL` in `task_list.py`

`dancode/widgets/task_list.py` — Find:
```python
_STATUS_SYMBOL = {
    TaskStatus.RUNNING:   "▶",
    TaskStatus.WAITING:   "⏸",
    TaskStatus.BLOCKED:   "✗",
    TaskStatus.DONE:      "✓",
    TaskStatus.PENDING:   "○",
    TaskStatus.CANCELLED: "⊘",
}
```

Add one entry after `TaskStatus.WAITING`:
```python
    TaskStatus.PAUSED:    "⏸",
```

### Step 3 — Update `_STATUS_ICONS` in `task_detail.py`

`dancode/widgets/task_detail.py` — Find:
```python
_STATUS_ICONS = {
    "done": "[green]✓[/green]",
    "running": "[bold cyan]▶[/bold cyan]",
    "waiting": "[yellow]⏸[/yellow]",
    "blocked": "[red]✗[/red]",
    "cancelled": "[dim]✗[/dim]",
    "pending": "[dim] [/dim]",
}
```

Add one entry after `"waiting"`:
```python
    "paused": "[magenta]⏸[/magenta]",
```

---

## Acceptance Criteria

- `assert _STATUS_STYLE[TaskStatus.PAUSED] == "bold magenta"`.
- `assert _STATUS_SYMBOL[TaskStatus.PAUSED] == "⏸"`.
- `assert _STATUS_ICONS["paused"] == "[magenta]⏸[/magenta]"`.
- `assert _make_item(FeatureTask(task_id='x', feature_name='f', feature_description='d', status=TaskStatus.PAUSED)) is not None` (does not raise).
- `assert isinstance(_render_phase_table(FeatureTask(task_id='x', feature_name='f', feature_description='d', status=TaskStatus.PAUSED, phase=TaskPhase.CODE)), str)` (does not raise).

---

## Testing Plan

Add to `tests/unit/test_phase_table.py` (or create the file if it doesn't exist for
the task_list rendering):

```python
from dancode.config import FeatureTask, TaskPhase, TaskStatus
from dancode.widgets.task_list import _STATUS_STYLE, _STATUS_SYMBOL
from dancode.widgets.task_detail import _STATUS_ICONS, _render_phase_table


def test_paused_in_task_list_dicts():
    assert TaskStatus.PAUSED in _STATUS_STYLE
    assert TaskStatus.PAUSED in _STATUS_SYMBOL
    assert _STATUS_STYLE[TaskStatus.PAUSED] == "bold magenta"


def test_paused_in_status_icons():
    assert "paused" in _STATUS_ICONS
    assert _STATUS_ICONS["paused"] == "[magenta]⏸[/magenta]"


def test_render_phase_table_paused_task():
    task = FeatureTask(
        task_id="x",
        feature_name="feat",
        feature_description="desc",
        status=TaskStatus.PAUSED,
        phase=TaskPhase.CODE,
    )
    rendered = _render_phase_table(task)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
```

No real AWS calls. No fixtures beyond inline helpers.
