"""OpenHands headless dispatch tool for dancode workflow."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tools import ToolContext, tool


@tool
def openhands_dispatch(
    worktree_path: str,
    model_id: str,
    context: ToolContext,
    dispatch_file: str = "",
    dispatch_content: str = "",
) -> str:
    """Run OpenHands in headless mode against a dispatch prompt.

    Spawns: openhands --headless --json --always-approve -f <dispatch_file>
    in the given worktree directory, with LLM_MODEL overridden to model_id.

    Provide EITHER dispatch_file (path to an existing .md file) OR
    dispatch_content (inline prompt text — written to .openhands-dispatch.md
    inside the worktree before running).

    Streams JSONL events to the session log and returns "DONE" on success
    or "BLOCKED: <reason>" if OpenHands exits with an error.

    model_id example: "minimax.minimax-m2.5" or "us.anthropic.claude-haiku-*"
    """
    worktree = Path(worktree_path).resolve()
    if not worktree.exists():
        return f"[ERROR] Worktree path not found: {worktree_path}"

    if dispatch_content:
        dispatch = worktree / ".openhands-dispatch.md"
        dispatch.write_text(dispatch_content)
    elif dispatch_file:
        dispatch = Path(dispatch_file).resolve()
        if not dispatch.exists():
            return f"[ERROR] Dispatch file not found: {dispatch_file}"
    else:
        return "[ERROR] Provide either dispatch_file or dispatch_content."

    # LiteLLM requires the "bedrock/" provider prefix for Bedrock models
    litellm_model = model_id if model_id.startswith("bedrock/") else f"bedrock/{model_id}"
    env = os.environ.copy()
    env["LLM_MODEL"] = litellm_model
    # --override-with-envs requires LLM_API_KEY; Bedrock uses IAM auth, so any value works
    env.setdefault("LLM_API_KEY", "bedrock")

    cmd = [
        "openhands",
        "--headless",
        "--json",
        "--always-approve",
        "--override-with-envs",
        "-f", str(dispatch),
    ]

    last_line = ""
    error_lines: list[str] = []

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(worktree),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            if not line:
                continue
            last_line = line

            # Try to parse as JSONL event and log it; keep raw line for TUI
            try:
                event = json.loads(line)
                event_type = event.get("type", "raw")
                if event_type == "action":
                    context.todo_list.append(
                        {"source": "openhands", "action": event.get("action"), "data": event}
                    )
            except json.JSONDecodeError:
                # Non-JSON output (e.g. startup messages) — log as-is
                if "error" in line.lower() or "blocked" in line.lower():
                    error_lines.append(line)

        process.wait()
        rc = process.returncode

    except FileNotFoundError:
        return "[ERROR] 'openhands' command not found. Is openhands-ai installed?"
    except Exception as exc:
        return f"[ERROR] Failed to run OpenHands: {exc}"

    if rc == 0:
        return "DONE"

    reason = "; ".join(error_lines[-3:]) if error_lines else last_line or "unknown error"
    return f"BLOCKED: {reason}"
