"""Agent state serialisation — checkpoint shared state to/from disk."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SKIP_KEYS = {"logger", "tool_context", "_conv"}
_CHECKPOINT_SUBDIR = "_checkpoints"
_WORKSPACE_CONTENT_LIMIT = 8192   # bytes — include full text below this size
_WORKSPACE_PREVIEW_CHARS = 500    # chars shown for files above the limit


def save_checkpoint(shared: dict, checkpoint_path: str | Path) -> None:
    """Serialise shared state (excluding unpicklable objects) to a JSON file."""
    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialisable = {k: v for k, v in shared.items() if k not in _SKIP_KEYS}
    with path.open("w", encoding="utf-8") as fh:
        json.dump(serialisable, fh, indent=2, default=str)


def load_checkpoint(checkpoint_path: str | Path) -> dict[str, Any]:
    """Load a previously saved checkpoint. Returns the raw dict (caller re-attaches live objects)."""
    path = Path(checkpoint_path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def checkpoint_path_for(logs_dir: str, agent_id: str, session_id: str) -> Path:
    return Path(logs_dir) / agent_id / f"{session_id}_checkpoint.json"


# ---------------------------------------------------------------------------
# Session workspace checkpoints (one file per LLM turn, named by timestamp)
# ---------------------------------------------------------------------------

def save_session_checkpoint(shared: dict, workspace_path: str | Path) -> Path:
    """Write a timestamped checkpoint to <workspace>/_checkpoints/.

    Called automatically after every LLM turn so that resume() can restore the
    richest possible conversation state even after a mid-run crash.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cp_dir = Path(workspace_path) / _CHECKPOINT_SUBDIR
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_path = cp_dir / f"checkpoint_{ts}.json"
    serialisable = {k: v for k, v in shared.items() if k not in _SKIP_KEYS}
    with cp_path.open("w", encoding="utf-8") as fh:
        json.dump(serialisable, fh, indent=2, default=str)
    return cp_path


def latest_session_checkpoint(workspace_path: str | Path) -> Path | None:
    """Return the most recent checkpoint file under <workspace>/_checkpoints/, or None."""
    cp_dir = Path(workspace_path) / _CHECKPOINT_SUBDIR
    if not cp_dir.exists():
        return None
    files = sorted(cp_dir.glob("checkpoint_*.json"))
    return files[-1] if files else None


def workspace_file_summary(workspace_path: str | Path) -> str:
    """Build a human-readable summary of files the agent previously wrote.

    Small files (< _WORKSPACE_CONTENT_LIMIT bytes) are included in full.
    Larger files get a short preview.  The _checkpoints/ subdirectory is skipped.
    Returns an empty string if the workspace is empty or absent.
    """
    root = Path(workspace_path)
    if not root.exists():
        return ""

    sections: list[str] = []
    for fpath in sorted(root.rglob("*")):
        if not fpath.is_file():
            continue
        # Skip the internal checkpoints directory
        if _CHECKPOINT_SUBDIR in fpath.parts:
            continue
        rel = fpath.relative_to(root)
        size = fpath.stat().st_size
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            sections.append(f"### {rel} ({size:,} bytes)\n[unreadable]")
            continue

        if size <= _WORKSPACE_CONTENT_LIMIT:
            sections.append(f"### {rel} ({size:,} bytes)\n{text}")
        else:
            sections.append(
                f"### {rel} ({size:,} bytes)\n{text[:_WORKSPACE_PREVIEW_CHARS]}"
                f"\n... [truncated — {size:,} bytes total]"
            )

    return "\n\n".join(sections)
