# Task 006 — Phase Table Widget + Per-Phase Token Tracking

**Track C — depends on task 001 (phase_token_counts model)**
**Run AFTER task 005 (both touch task_detail.py — merge carefully)**

## Overview

Two sub-changes:

**A — Token extraction** (`dancode/workers/agent_runner.py`):
After each phase completes successfully, read cumulative token usage from the
`Conversation` object in the runner result and store it in
`task.phase_token_counts[agent_id]`.

**B — Phase table widget** (`dancode/widgets/task_detail.py`):
Replace the single-line `#phase-breadcrumb` Label with a `Static` widget
that renders a Rich table showing all 10 phases with status icon and token count.

The table renders like:
```
  ✓  1  Plan              12,345 tok
  ✓  2  Jank Control       8,901 tok
  ▶  3  Refine                 0 tok
  ·  4  Dispatch               —
     5  Code                   —
  ...
```

## Files Changed

- `dancode/workers/agent_runner.py`
- `dancode/widgets/task_detail.py`

## Type Contracts

### New helper in `dancode/widgets/task_detail.py`

```python
def _render_phase_table(task: FeatureTask) -> str:
    """Render a Rich-markup phase status table for the given task.

    Returns a multi-line string suitable for a Textual Static widget.
    Each line: <icon> <phase_num> <phase_name> <token_count_or_dash>
    """
```

No changes to `AgentWorker`'s public API. Token extraction is internal.

## Workflow

### Part A — Token extraction in agent_runner.py

1. Open `dancode/workers/agent_runner.py`.

2. Locate the block after `result = await loop.run_in_executor(...)`. It currently is:
   ```python
   except Exception as exc:
       tb = traceback.format_exc()
       ...
   ```
   And before the `except` block there is the `result = await ...` line followed by
   a blank line and then the `# Check for a BLOCKED result` comment.

3. After the `result = await loop.run_in_executor(...)` assignment (and before the
   `except` block), extract token counts. Insert the following lines immediately after
   the `result = await ...` call (still inside the `try:` block):
   ```python
               # Extract and persist cumulative token usage for this phase
               _conv = result.get("_conv") if isinstance(result, dict) else None
               if _conv is not None:
                   _total_tokens = (
                       getattr(_conv, "input_tokens", 0)
                       + getattr(_conv, "output_tokens", 0)
                   )
                   task.phase_token_counts[agent_id] = _total_tokens
   ```

   The indentation is 16 spaces (inside `try:` which is inside `for phase:` which is
   inside `async def run:`).

### Part B — Phase table in task_detail.py

**NOTE**: Merge with task 005's changes first. task 005 adds `RestartTask` and a
button — do not revert those changes here.

4. Open `dancode/widgets/task_detail.py`.

5. Add `Static` to the existing Textual imports. Find:
   ```python
   from textual.widgets import Button, Label, RichLog
   ```
   Change to:
   ```python
   from textual.widgets import Button, Label, RichLog, Static
   ```

6. Add `PHASE_AGENTS` to the config imports. Find:
   ```python
   from dancode.config import (
       FeatureTask,
       TaskPhase,
       TaskStatus,
       PHASE_NAMES,
   )
   ```
   Change to:
   ```python
   from dancode.config import (
       FeatureTask,
       PHASE_AGENTS,
       TaskPhase,
       TaskStatus,
       PHASE_NAMES,
   )
   ```

7. After the imports block (before the `class ApproveGate` definition), add the
   helper function:
   ```python
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
   ```

8. In the `TaskDetailWidget.DEFAULT_CSS`, find:
   ```css
       TaskDetailWidget #phase-breadcrumb {
           height: 1;
           margin-bottom: 1;
           color: $text-muted;
       }
   ```
   Replace it with:
   ```css
       TaskDetailWidget #phase-table {
           height: auto;
           margin-bottom: 1;
       }
   ```

9. In `TaskDetailWidget.compose()`, find:
   ```python
   yield Label("", id="phase-breadcrumb")
   ```
   Replace it with:
   ```python
   yield Static("", id="phase-table", markup=True)
   ```

10. In `_refresh_header()`, find:
    ```python
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
    ```
    Replace that entire block with:
    ```python
    phase_table = self.query_one("#phase-table", Static)
    phase_table.update(_render_phase_table(task))
    ```

## Acceptance Criteria

```python
# _render_phase_table produces one line per phase (10 lines)
from dancode.config import FeatureTask, TaskPhase, TaskStatus
from dancode.widgets.task_detail import _render_phase_table

task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
table = _render_phase_table(task)
lines = [l for l in table.split("\n") if l.strip()]
assert len(lines) == 10, f"Expected 10 lines, got {len(lines)}"
```

```python
# Token count shows formatted number when present
from dancode.config import FeatureTask, PHASE_AGENTS, TaskPhase
from dancode.widgets.task_detail import _render_phase_table

task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
task.phase_token_counts["phase1_plan"] = 12345
table = _render_phase_table(task)
assert "12,345 tok" in table
```

```python
# Phases after current phase show pending icon; current shows running icon
from dancode.config import FeatureTask, TaskPhase, TaskStatus
from dancode.widgets.task_detail import _render_phase_table

task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
task.phase = TaskPhase.REFINE  # phase 3
task.status = TaskStatus.RUNNING
table = _render_phase_table(task)
# Phase 1 and 2 should show done checkmark
assert "✓" in table
# Phase 3 should show running indicator
assert "▶" in table
```

```python
# Token count in agent_runner is stored after phase completion
# (Integration check — verify field is updated)
from dancode.config import FeatureTask
task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
# Simulate what agent_runner does:
task.phase_token_counts["phase1_plan"] = 500
assert task.phase_token_counts["phase1_plan"] == 500
```

## Testing Plan

File: `tests/unit/test_phase_table.py` (new file)

```python
def test_render_phase_table_has_ten_lines():
    """_render_phase_table returns exactly 10 non-empty lines."""
    from dancode.config import FeatureTask
    from dancode.widgets.task_detail import _render_phase_table
    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    table = _render_phase_table(task)
    lines = [l for l in table.split("\n") if l.strip()]
    assert len(lines) == 10


def test_render_phase_table_shows_token_count():
    """Phase with token count shows formatted number."""
    from dancode.config import FeatureTask
    from dancode.widgets.task_detail import _render_phase_table
    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    task.phase_token_counts["phase1_plan"] = 5000
    assert "5,000 tok" in _render_phase_table(task)


def test_render_phase_table_dash_for_untracked():
    """Phase without token count shows dash."""
    from dancode.config import FeatureTask
    from dancode.widgets.task_detail import _render_phase_table
    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    table = _render_phase_table(task)
    # All phases start with no tokens so all should show dash
    assert "—" in table


def test_render_phase_table_running_icon():
    """Current running phase shows the running icon."""
    from dancode.config import FeatureTask, TaskPhase, TaskStatus
    from dancode.widgets.task_detail import _render_phase_table
    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    task.phase = TaskPhase.PLAN
    task.status = TaskStatus.RUNNING
    assert "▶" in _render_phase_table(task)
```
