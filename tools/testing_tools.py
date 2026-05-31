"""Tools for testing and iterating on Council agents.

Provides log inspection, checkpoint manipulation, and test-run control so
the Agent Creator can iterate on a new agent's behaviour without touching
production data or external services.

All paths resolve through engine.paths and are fully local.  AgentRunner is
imported lazily so the tools can be imported without a running LLM session.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import paths as _paths
from tools import ToolContext, tool


# ---------------------------------------------------------------------------
# Path accessors (functions so tests can monkeypatch them)
# ---------------------------------------------------------------------------

def _LOGS_DIR() -> Path:
    return _paths.LOGS_DIR


def _WORKSPACE_DIR() -> Path:
    return _paths.WORKSPACE_DIR


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log_path(agent_id: str, session_id: str) -> Path:
    return _LOGS_DIR() / agent_id / f"{session_id}.jsonl"


def _workspace_path(agent_id: str, session_id: str) -> Path:
    return _WORKSPACE_DIR() / agent_id / session_id


def _checkpoints_dir(agent_id: str, session_id: str) -> Path:
    return _workspace_path(agent_id, session_id) / "_checkpoints"


def _sorted_checkpoints(agent_id: str, session_id: str) -> list[Path]:
    cp_dir = _checkpoints_dir(agent_id, session_id)
    if not cp_dir.exists():
        return []
    return sorted(cp_dir.glob("checkpoint_*.json"))


def _parse_checkpoint_ts(cp_path: Path) -> datetime:
    """Parse datetime from checkpoint filename: checkpoint_20260422T134512Z.json"""
    stem = cp_path.stem  # "checkpoint_20260422T134512Z"
    ts_str = stem.split("_", 1)[1]  # "20260422T134512Z"
    return datetime.strptime(ts_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def _parse_log_ts(ts_str: str) -> datetime:
    """Parse datetime from log event ts field: 2026-04-22T13:45:12Z"""
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _extract_original_prompt(log_path: Path) -> str:
    """Return the prompt field from the first session_start event in the log."""
    if not log_path.exists():
        return "Test run"
    for raw in log_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(raw)
            if record.get("event") == "session_start":
                return record.get("prompt", "Test run")
        except json.JSONDecodeError:
            continue
    return "Test run"


def _summarise_run(shared: dict) -> str:
    msgs = shared.get("messages", [])
    last_assistant = next(
        (m["content"] for m in reversed(msgs) if m.get("role") == "assistant"),
        "(no assistant output)",
    )
    return (
        f"session_id: {shared.get('session_id')}\n"
        f"iterations: {shared.get('iteration', 0)}\n"
        f"last_output: {str(last_assistant)[:600]}"
    )


def _deep_merge(base: dict, patch: dict) -> None:
    """Recursively merge patch into base in-place."""
    for k, v in patch.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def list_agent_sessions(agent_id: str, context: ToolContext) -> str:
    """List all test sessions for an agent with log path, workspace path, and checkpoint info."""
    logs_dir = _LOGS_DIR() / agent_id
    workspace_dir = _WORKSPACE_DIR() / agent_id

    sessions: list[str] = []
    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.jsonl")):
            session_id = log_file.stem
            ws = workspace_dir / session_id
            cps = _sorted_checkpoints(agent_id, session_id)
            newest_cp = cps[-1].name if cps else "none"
            sessions.append(
                f"session: {session_id}\n"
                f"  log: {log_file}\n"
                f"  workspace: {ws}\n"
                f"  latest_checkpoint: {newest_cp}\n"
                f"  checkpoint_count: {len(cps)}"
            )

    if not sessions:
        return f"No sessions found for agent '{agent_id}'"
    return "\n\n".join(sessions)


@tool
def read_session_log(agent_id: str, session_id: str, context: ToolContext) -> str:
    """Read and format a session JSONL trace log for review. Shows block, event, and key fields per line."""
    log_path = _log_path(agent_id, session_id)
    if not log_path.exists():
        return f"No log found at {log_path}"

    raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    formatted: list[str] = []
    for raw in raw_lines:
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            formatted.append(f"[MALFORMED] {raw[:200]}")
            continue

        ts = record.get("ts", "?")
        block = record.get("block", "—")
        event = record.get("event", "?")
        skip = {"ts", "block", "event", "agent_id", "session_id", "messages"}
        extras = {k: v for k, v in record.items() if k not in skip}
        extra_str = "  ".join(
            f"{k}={str(v)[:120]}" for k, v in extras.items()
        )
        formatted.append(f"[{ts}] [{block}] {event}  {extra_str}".rstrip())

    if not formatted:
        return f"Log for {agent_id}/{session_id} is empty"

    _MAX_LINES = 300
    if len(formatted) > _MAX_LINES:
        formatted = [f"[log truncated — showing last {_MAX_LINES} of {len(formatted)} events]"] + formatted[-_MAX_LINES:]

    return "\n".join(formatted)


@tool
def agent_test(agent_id: str, session_id: str, block_name: str, action: str, context: ToolContext) -> str:
    """Run a test on an agent session. action='restart' wipes state and reruns from scratch. action='resume' rewinds to block_name and continues."""
    from engine.runner import AgentRunner

    if action == "restart":
        log_path = _log_path(agent_id, session_id)
        # Read original prompt before erasing
        prompt = _extract_original_prompt(log_path)

        if log_path.exists():
            log_path.unlink()
        ws = _workspace_path(agent_id, session_id)
        if ws.exists():
            shutil.rmtree(ws)

        runner = AgentRunner(agent_id=agent_id)
        shared = runner.run(prompt=prompt, session_id=session_id)
        return _summarise_run(shared)

    elif action == "resume":
        log_path = _log_path(agent_id, session_id)
        if not log_path.exists():
            return f"No log found for {agent_id}/{session_id}"

        lines = log_path.read_text(encoding="utf-8").splitlines()

        # Walk backwards to find the last event for this block
        cut_index: int | None = None
        cut_ts: datetime | None = None
        for i in range(len(lines) - 1, -1, -1):
            try:
                record = json.loads(lines[i])
            except json.JSONDecodeError:
                continue
            if record.get("block") == block_name:
                cut_index = i
                ts_str = record.get("ts")
                if ts_str:
                    cut_ts = _parse_log_ts(ts_str)
                break

        if cut_index is None:
            return f"Block '{block_name}' not found in log for {agent_id}/{session_id}"

        # Trim log to cut_index (inclusive)
        with log_path.open("w", encoding="utf-8") as fh:
            for line in lines[: cut_index + 1]:
                fh.write(line + "\n")

        # Remove checkpoints newer than the cut timestamp
        if cut_ts is not None:
            for cp in _sorted_checkpoints(agent_id, session_id):
                try:
                    if _parse_checkpoint_ts(cp) > cut_ts:
                        cp.unlink()
                except Exception:
                    pass

        # Load prior conversation turns from the latest surviving checkpoint
        prior_messages: list[Any] | None = None
        remaining = _sorted_checkpoints(agent_id, session_id)
        if remaining:
            try:
                cp_data = json.loads(remaining[-1].read_text(encoding="utf-8"))
                prior_messages = cp_data.get("_conv_turns") or cp_data.get("messages")
            except Exception:
                pass

        runner = AgentRunner(agent_id=agent_id)
        shared = runner.run(
            prompt="",
            session_id=session_id,
            prior_messages=prior_messages,
            resume_from_block=block_name,
        )
        return _summarise_run(shared)

    else:
        return f"Unknown action '{action}'. Use 'restart' or 'resume'."


@tool
def agent_test_modify(
    agent_id: str,
    session_id: str,
    action: str,
    patch_json: str = "{}",
    context: ToolContext = None,  # type: ignore[assignment]
) -> str:
    """Modify a test session's checkpoints or log. action: remove_last_run | remove_last_turn | modify_checkpoint"""
    if action == "remove_last_run":
        checkpoints = _sorted_checkpoints(agent_id, session_id)
        if not checkpoints:
            return f"No checkpoints found for {agent_id}/{session_id}"

        newest = checkpoints[-1]

        # Trim log entries written after the previous checkpoint's timestamp
        if len(checkpoints) >= 2:
            prev_ts = _parse_checkpoint_ts(checkpoints[-2])
            log_path = _log_path(agent_id, session_id)
            if log_path.exists():
                raw_lines = log_path.read_text(encoding="utf-8").splitlines()
                kept: list[str] = []
                for raw in raw_lines:
                    try:
                        record = json.loads(raw)
                        event_ts = _parse_log_ts(record["ts"])
                        if event_ts <= prev_ts:
                            kept.append(raw)
                    except Exception:
                        kept.append(raw)  # preserve malformed lines
                with log_path.open("w", encoding="utf-8") as fh:
                    for line in kept:
                        fh.write(line + "\n")

        removed_name = newest.name
        newest.unlink()
        return f"Removed checkpoint: {removed_name}"

    elif action == "remove_last_turn":
        log_path = _log_path(agent_id, session_id)
        if not log_path.exists():
            return f"No log found for {agent_id}/{session_id}"

        lines = log_path.read_text(encoding="utf-8").splitlines()
        # Filter empty lines that may trail the file
        lines = [l for l in lines if l.strip()]
        if not lines:
            return "Log is empty, nothing to remove"

        removed = lines[-1]
        with log_path.open("w", encoding="utf-8") as fh:
            for line in lines[:-1]:
                fh.write(line + "\n")
        return f"Removed: {removed[:300]}"

    elif action == "modify_checkpoint":
        checkpoints = _sorted_checkpoints(agent_id, session_id)
        if not checkpoints:
            return f"No checkpoints found for {agent_id}/{session_id}"

        newest = checkpoints[-1]
        try:
            patch = json.loads(patch_json)
        except json.JSONDecodeError as exc:
            return f"Invalid patch_json: {exc}"

        data: dict = json.loads(newest.read_text(encoding="utf-8"))
        _deep_merge(data, patch)
        newest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

        return f"Modified checkpoint {newest.name}: updated keys {list(patch.keys())}"

    else:
        return f"Unknown action '{action}'. Use: remove_last_run | remove_last_turn | modify_checkpoint"
