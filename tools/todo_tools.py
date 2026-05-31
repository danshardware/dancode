"""To-do list tool for agent task tracking.

The list lives on ToolContext.todo_list (a plain Python list shared with
shared["_todo_list"]) so it is automatically persisted in every checkpoint
and restored on --resume with no extra plumbing.

Each item is a dict:
    { "id": int, "title": str, "status": "todo" | "in_progress" | "done" }

Single-operation tool — the agent picks an operation and provides the
relevant parameters.  Unused parameters are ignored.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from tools import ToolContext, tool

_console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_id(items: list[dict]) -> int:
    return max((it["id"] for it in items), default=0) + 1


def _counts(items: list[dict]) -> tuple[int, int, int]:
    done = sum(1 for it in items if it["status"] == "done")
    inprogress = sum(1 for it in items if it["status"] == "in_progress")
    total = len(items)
    return done, inprogress, total


def _progress_bar(done: int, total: int, width: int = 20) -> str:
    if total == 0:
        return "░" * width
    filled = round(done / total * width)
    return "▓" * filled + "░" * (width - filled)


def _header(items: list[dict]) -> str:
    done, inprog, total = _counts(items)
    bar = _progress_bar(done, total)
    return f"{bar} {done}/{total} done" + (f"  ({inprog} in progress)" if inprog else "")


def _status_style(status: str) -> str:
    return {"todo": "white", "in_progress": "bold yellow", "done": "dim strike"}.get(status, "white")


def _render_list(items: list[dict], highlight_ids: set[int] | None = None) -> None:
    """Print the full todo list as a rich table."""
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
    table.add_column("ID", style="dim", width=4)
    table.add_column("Status", width=12)
    table.add_column("Title")

    status_labels = {"todo": "○ todo", "in_progress": "● in progress", "done": "✓ done"}
    for it in items:
        style = _status_style(it["status"])
        if highlight_ids and it["id"] in highlight_ids:
            style = "bold green"
        table.add_row(
            str(it["id"]),
            Text(status_labels.get(it["status"], "? no status"), style=style),
            Text(it["title"], style=style),
        )

    _console.print(f"[dim]{_header(items)}[/dim]")
    _console.print(table)


def _render_context(items: list[dict], target_id: int, context_n: int = 2) -> None:
    """Print target item plus `context_n` neighbours on each side."""
    idx = next((i for i, it in enumerate(items) if it["id"] == target_id), None)
    if idx is None:
        return
    start = max(0, idx - context_n)
    end = min(len(items), idx + context_n + 1)
    _render_list(items[start:end], highlight_ids={target_id})


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
def todo_list(
    operation: str,
    context: ToolContext,
    title: str = "",
    items: list = [],
    item_id: int = 0,
    position: int = -1,
    status: str = "",
) -> str:
    """Manage a session to-do list for tracking research tasks.

    operation: add | bulk_add | get_next | mark | modify | delete | show
    title:    item text (for add / modify)
    items:    list of title strings for bulk_add, e.g. ["task 1", "task 2"]
    item_id:  numeric ID of the item to act on (for mark / modify / delete)
    position: 0-based insert position for add (-1 = append, default)
    status:   new status for mark operation: in_progress | done | todo
    """
    lst = context.todo_list
    # Bedrock sometimes delivers numeric params as strings despite the schema,
    # and occasionally wraps the value in quotes e.g. "'1'" — strip them first.
    if isinstance(item_id, str):
        item_id = int(item_id.strip("'\""))
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        pass
    try:
        position = int(position)
    except (TypeError, ValueError):
        position = -1

    # ── add ──────────────────────────────────────────────────────────────────
    if operation == "add":
        if not title:
            return "Error: 'title' is required for add."
        new_item = {"id": _next_id(lst), "title": title, "status": "todo"}
        if position < 0 or position >= len(lst):
            lst.append(new_item)
        else:
            lst.insert(position, new_item)
        _console.print(f"[green]+ Added:[/green] [{new_item['id']}] {title}")
        _render_context(lst, new_item["id"])
        return f"Added item {new_item['id']}: {title}"

    # ── bulk_add ─────────────────────────────────────────────────────────────
    if operation == "bulk_add":
        if not items:
            return "Error: 'items' list is empty or not provided."
        # Some models pass a string despite the array schema — handle gracefully
        if isinstance(items, str):
            import json as _json
            try:
                items = _json.loads(items)
            except _json.JSONDecodeError:
                # Assume comma-separated
                items = [s.strip() for s in items.split(",") if s.strip()]
        if not isinstance(items, list):
            return f"Error: 'items' must be a list of strings, got {type(items).__name__}."
        added = []
        for t in items:
            new_item = {"id": _next_id(lst), "title": str(t), "status": "todo"}
            lst.append(new_item)
            added.append(new_item["id"])
        _console.print(f"[green]Populated todo list with {len(added)} items.[/green]")
        _render_list(lst)
        return f"Added {len(added)} items: IDs {added}"

    # ── get_next ─────────────────────────────────────────────────────────────
    if operation == "get_next":
        # Return the first in_progress item (already started), or the first todo
        nxt = next((it for it in lst if it["status"] == "in_progress"), None)
        if nxt is None:
            nxt = next((it for it in lst if it["status"] == "todo"), None)
        if nxt is None:
            remaining = sum(1 for it in lst if it["status"] != "done")
            if remaining == 0:
                _console.print("[bold green]All tasks complete![/bold green]")
                return "ALL_DONE"
            return "No pending tasks found."
        if nxt["status"] != "in_progress":
            nxt["status"] = "in_progress"
        done, _, total = _counts(lst)
        _console.print(
            f"[bold yellow]Next:[/bold yellow] [{nxt['id']}] {nxt['title']}  "
            f"[dim]{_progress_bar(done, total, 12)} {done}/{total}[/dim]"
        )
        return f"Next task — ID {nxt['id']}: {nxt['title']}"

    # ── mark ─────────────────────────────────────────────────────────────────
    if operation == "mark":
        if status not in ("todo", "in_progress", "done"):
            return "Error: 'status' must be todo | in_progress | done."
        it = next((x for x in lst if x["id"] == item_id), None)
        if it is None:
            return f"Error: item {item_id} not found."
        it["status"] = status
        if status == "done":
            _console.print(f"[dim strike]✓ Done:[/dim strike] [{it['id']}] {it['title']}")
            # Show what's coming next
            nxt = next((x for x in lst if x["status"] in ("todo", "in_progress")), None)
            if nxt:
                _console.print(f"[bold yellow]Up next:[/bold yellow] [{nxt['id']}] {nxt['title']}")
            else:
                _console.print("[bold green]All tasks complete![/bold green]")
        else:
            _console.print(f"[yellow]● Marked {status}:[/yellow] [{it['id']}] {it['title']}")
        return f"Item {item_id} marked {status}."

    # ── modify ───────────────────────────────────────────────────────────────
    if operation == "modify":
        if not title:
            return "Error: 'title' is required for modify."
        it = next((x for x in lst if x["id"] == item_id), None)
        if it is None:
            return f"Error: item {item_id} not found."
        old = it["title"]
        it["title"] = title
        _console.print(f"[cyan]✎ Modified [{item_id}]:[/cyan] {old} → {title}")
        _render_context(lst, item_id)
        return f"Item {item_id} updated: {title}"

    # ── delete ───────────────────────────────────────────────────────────────
    if operation == "delete":
        it = next((x for x in lst if x["id"] == item_id), None)
        if it is None:
            return f"Error: item {item_id} not found."
        lst.remove(it)
        _console.print(f"[red]✗ Deleted:[/red] [{item_id}] {it['title']}")
        _render_context(lst, item_id)
        return f"Deleted item {item_id}: {it['title']}"

    # ── show ─────────────────────────────────────────────────────────────────
    if operation == "show":
        if not lst:
            return "Todo list is empty."
        _render_list(lst)
        return "\n".join(
            f"[{it['id']}] ({it['status']}) {it['title']}" for it in lst
        )

    return f"Error: unknown operation '{operation}'. Valid: add | bulk_add | get_next | mark | modify | delete | show"
