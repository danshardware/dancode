"""AgentRunner — loads an agent definition + flow and drives execution."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

import yaml
from rich.console import Console
from rich.rule import Rule

import traceback

from engine.block import MaxIterationsError, SuspendExecution
from engine.llm import LLMUnavailableError
from engine.flow_loader import load_flow
from engine.logger import Logger
from engine import paths
from tools import ToolContext

_console = Console()


def _resolve_path(p: str) -> str:
    """Rewrite paths that start with 'data/' to be under DATA_DIR.

    This allows agent YAMLs to declare paths like 'data/agents/' regardless
    of whether COUNCIL_DATA_DIR points inside or outside the repo root.
    Paths that don't start with 'data/' are returned unchanged (they are
    repo-relative source directories such as 'agents/', 'flows/', 'config/').
    """
    if p.startswith("data/") or p == "data":
        suffix = p[len("data/"):] if p.startswith("data/") else ""
        resolved = str(paths.DATA_DIR / suffix) if suffix else str(paths.DATA_DIR)
        # Preserve trailing slash convention used by the rest of the runner
        if p.endswith("/") and not resolved.endswith("/"):
            resolved += "/"
        return resolved
    return p


def _sanitise_user_input(prompt: str) -> str:
    """
    Neutralise [SYSTEM] injection attempts in raw user input.
    Replaces the prefix so downstream handlers see it is user-supplied.
    """
    import re
    return re.sub(
        r'(?i)\[SYSTEM\]',
        '[USER-SUPPLIED-SYSTEM]',
        prompt,
    )


def _resolve_guardrail_prompt(
    agent_config: dict,
    key: Literal["input", "output"],
    system_defaults: dict,
) -> str:
    """
    Return the guardrail prompt to use for `key` ("input" or "output").

    Priority:
    1. agent_config["guardrails"][key] if the key is explicitly present
       (empty string "" means "disabled" — skip the guardrail entirely)
    2. system_defaults["input_safety"] / system_defaults["output_safety"]
    3. "" (empty — caller should skip the guardrail check)
    """
    guardrails = agent_config.get("guardrails", {})
    if key in guardrails:
        # Explicit override in agent config — honour it even if empty (= disabled)
        return (guardrails[key] or "").strip()
    fallback_key = "input_safety" if key == "input" else "output_safety"
    return (system_defaults.get(fallback_key, "") or "").strip()


class AgentRunner:
    def __init__(
        self,
        agent_id: str,
        logs_dir: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.logs_dir = Path(logs_dir) if logs_dir is not None else paths.LOGS_DIR

    def run(
        self,
        prompt: str,
        flow_name: str = "main",
        session_id: str | None = None,
        prior_messages: list | None = None,
        resume_from_block: str | None = None,
        resume_todo_list: list | None = None,
        shared_overrides: dict | None = None,
    ) -> dict:
        """
        Run the agent with the given prompt.

        Args:
            prompt:          Initial user message.
            flow_name:       Key from agent YAML `flows:` section (default "main").
            session_id:      Optional; auto-generated if not provided.
            shared_overrides: Optional dict merged into shared state after it is
                              built.  Used by channel gateways to inject
                              ``channel_context`` and ``_channel_adapter``.

        Returns:
            The final shared state dict.
        """
        session_id = session_id or uuid.uuid4().hex[:12]

        # Load agent definition
        agent_config = self._load_agent()

        # Resolve flow file name
        flow_file_key = agent_config["flows"].get(flow_name)
        if flow_file_key is None:
            raise ValueError(
                f"Agent '{self.agent_id}' has no flow named '{flow_name}'"
            )
        flow_path = paths.resolve("flows", f"{flow_file_key}.yaml")

        # Load flow
        flow, flow_config, block_instances = load_flow(flow_path)

        # When resuming mid-flow, restart from the last completed block rather
        # than the flow's start node.  Silently falls back to start if the block
        # isn't found (e.g. flow was restructured since the checkpoint).
        if resume_from_block and resume_from_block in block_instances:
            flow.start_node = block_instances[resume_from_block]
            _console.print(f"[dim]Resuming from block: {resume_from_block}[/dim]")
        elif resume_from_block:
            _console.print(
                f"[yellow]Warning:[/yellow] resume_from_block '{resume_from_block}' "
                "not found in flow — starting from beginning."
            )

        # Iteration cap: lower of agent vs flow
        agent_max = agent_config.get("max_iterations", 50)
        flow_max = flow_config.get("max_iterations", 25)
        max_iterations = min(agent_max, flow_max)

        # Session-scoped workspace: workspace/ceo/ → workspace/ceo/<session_id>/
        # This prevents file clashes when the same agent runs concurrently.
        _base_paths = agent_config.get("permissions", {}).get("workspace_paths", [])
        session_workspace_paths = [
            str(Path(_resolve_path(p).rstrip("/")) / session_id) + "/"
            for p in _base_paths
        ]
        for _sp in session_workspace_paths:
            Path(_sp).mkdir(parents=True, exist_ok=True)

        # read_paths are shared (not session-scoped) — used for read-only access
        # to source directories such as agents/, flows/, config/.
        _read_paths = [_resolve_path(p) for p in agent_config.get("permissions", {}).get("read_paths", [])]

        # write_paths are shared (not session-scoped) — stable writable directories
        # such as data/agents/, data/flows/. Pre-created so the agent can write
        # immediately without needing to know the session id.
        _write_paths = [_resolve_path(p) for p in agent_config.get("permissions", {}).get("write_paths", [])]
        for _wp in _write_paths:
            Path(_wp).mkdir(parents=True, exist_ok=True)

        all_allowed_paths = session_workspace_paths + _read_paths + _write_paths

        # Allow callers to inject additional writable paths at runtime (e.g. the
        # target git repo root for Planning/ output) without needing to hard-code
        # them in the agent YAML.
        _runtime_paths: list[str] = (shared_overrides or {}).pop("_extra_allowed_paths", [])
        for _rp in _runtime_paths:
            Path(_rp).mkdir(parents=True, exist_ok=True)
            all_allowed_paths.append(_rp)

        # Build shared state
        # When resuming, seed the conversation with prior history so the agent
        # can continue without repeating work already done.
        # Sanitise user input to neutralise [SYSTEM] injection attempts
        _safe_prompt = _sanitise_user_input(prompt)
        initial_messages: list = prior_messages if prior_messages else [{"role": "user", "content": _safe_prompt}]
        # todo_list lives in BOTH shared and ToolContext (same reference) so:
        #   - tools can mutate it via context.todo_list
        #   - checkpoints capture it automatically via shared["_todo_list"]
        _todo_list: list = list(resume_todo_list) if resume_todo_list else []
        shared: dict = {
            "agent_id": self.agent_id,
            "session_id": session_id,
            "logs_dir": str(self.logs_dir),
            "agent_config": agent_config,
            "write_paths": _write_paths,
            "read_paths": _read_paths,
            "max_iterations": max_iterations,
            "iteration": 0,
            "block_visits": {},
            "action": None,
            "action_input": {},
            "messages": initial_messages,
            "_conv": None,
            "_conv_turns": list(initial_messages),
            "initial_prompt": _safe_prompt,
            "_todo_list": _todo_list,
            "context_injection": _load_context_files(agent_config),
            "logger": Logger(str(self.logs_dir), self.agent_id, session_id),
            "tool_context": ToolContext(
                agent_id=self.agent_id,
                session_id=session_id,
                allowed_paths=all_allowed_paths,
                allowed_commands=agent_config.get("permissions", {}).get(
                    "allowed_commands", []
                ),
                todo_list=_todo_list,
            ),
        }

        # Set up the guardrail prompts (used by A2 and A3)
        from engine.template import _load_config_dir
        _guardrail_defaults = _load_config_dir().get("guardrails", {})

        # Resolve both guardrail prompts using per-agent overrides if available
        shared["_input_guardrail_prompt"] = _resolve_guardrail_prompt(
            agent_config, "input", _guardrail_defaults
        )
        shared["_output_guardrail_prompt"] = _resolve_guardrail_prompt(
            agent_config, "output", _guardrail_defaults
        )

        # Merge any overrides from the calling context (e.g. channel gateway)
        if shared_overrides:
            shared.update(shared_overrides)

        # Propagate channel context into ToolContext so spawn_agent() can forward it.
        tc: ToolContext = shared["tool_context"]
        tc.channel_context = shared.get("channel_context")
        tc._channel_adapter = shared.get("_channel_adapter")
        tc._discord_loop = shared.get("_discord_loop")

        _console.print(Rule(f"[bold green]Council — {self.agent_id} — {session_id}[/bold green]"))
        _console.print(f"[dim]Flow: {flow_file_key}  |  Max iterations: {max_iterations}[/dim]\n")

        with shared["logger"]:
            shared["logger"].log_event(
                shared,
                "session_start",
                flow=flow_file_key,
                flow_name=flow_name,
                prompt=prompt,
                resumed=prior_messages is not None,
            )

            # -------------------------------------------------
            # Step 1 — Run the input guardrail check if configured (prompt resolved earlier)
            # -------------------------------------------------
            # Skip guardrail check on resume (prior_messages indicates resume path)
            if shared["_input_guardrail_prompt"] and not prior_messages:
                should_proceed = _check_input_guardrail(
                    prompt=prompt,
                    guardrail_prompt=shared["_input_guardrail_prompt"],
                    model_id="us.amazon.nova-lite-v1:0",
                    shared=shared,
                )
                if not should_proceed:
                    return shared

            # -------------------------------------------------
            # Step 2 — Run the flow
            # -------------------------------------------------
            try:
                flow._run(shared)
            except MaxIterationsError as exc:
                shared["logger"].log_event(
                    shared, "max_iterations_reached", error=str(exc)
                )
                _console.print(
                    f"\n[bold red]Max iterations reached:[/bold red] {exc}"
                )
                shared["_run_error"] = True
                _dispatch_on_error("max_iterations", exc, flow, flow_config, block_instances, shared)
            except LLMUnavailableError as exc:
                tb = traceback.format_exc()
                shared["logger"].log_event(
                    shared, "llm_offline", error=str(exc), traceback=tb
                )
                _console.print(f"\n[bold red]LLM unavailable:[/bold red] {exc}")
                shared["_run_error"] = True
                _dispatch_on_error("llm_offline", exc, flow, flow_config, block_instances, shared)
            except SuspendExecution as exc:
                shared["logger"].log_event(
                    shared, "session_suspended", checkpoint=exc.checkpoint_path
                )
                _console.print(
                    f"\n[bold yellow]Session suspended.[/bold yellow] "
                    f"Checkpoint: {exc.checkpoint_path}"
                )
                shared["suspended"] = True
                shared["checkpoint_path"] = exc.checkpoint_path
            except Exception as exc:
                tb = traceback.format_exc()
                shared["logger"].log_event(
                    shared, "unhandled_error", error=str(exc), traceback=tb
                )
                _console.print(f"\n[bold red]Unhandled error:[/bold red] {exc}")
                _console.print(f"[dim]{tb}[/dim]")
                shared["_run_error"] = True
                _dispatch_on_error("unhandled", exc, flow, flow_config, block_instances, shared)
            except BaseException as exc:
                # Catches KeyboardInterrupt, SystemExit etc. — log then re-raise
                shared["logger"].log_event(
                    shared, "session_interrupted", error=type(exc).__name__
                )
                _console.print(f"\n[yellow]Session interrupted ({type(exc).__name__})[/yellow]")
                raise
            finally:
                shared["logger"].log_event(
                    shared,
                    "session_end",
                    total_iterations=shared["iteration"],
                )

            # Post-session: summarise conversation + reconcile facts into memory.
            # Must run inside the `with logger` block so the file handle is still open.
            if agent_config.get("post_session_flow") and not shared.get("suspended"):
                from engine.post_session_runner import PostSessionRunner
                PostSessionRunner().run_after_session(shared)

        _console.print(Rule("[dim]Session complete[/dim]"))

        return shared

    def resume(
        self,
        session_id: str,
        shared_overrides: dict | None = None,
        extra_messages: list | None = None,
    ) -> dict:
        """Resume a crashed or incomplete session.

        Recovery order:
        1. Latest timestamped checkpoint from <workspace>/_checkpoints/ (richest state)
        2. ``messages`` snapshot from the last session_end in the JSONL log (fallback)

        In both cases the workspace file listing is injected as a [SYSTEM] message
        so the agent knows exactly what it already produced and can continue without
        re-doing completed work.  The iteration counter always resets to 0.

        ``extra_messages`` are appended *after* all checkpoint/listing injection,
        letting callers inject a human reply or system notice without duplicating
        the resume logic.
        """
        log_path = self.logs_dir / self.agent_id / f"{session_id}.jsonl"
        if not log_path.exists():
            raise FileNotFoundError(
                f"No log found for session '{session_id}' "
                f"(looked in {log_path})"
            )

        events: list[dict] = []
        with log_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

        # Use the LAST session_start so that flow_switch sub-flows are resumed
        # correctly (the sub-flow appends its own session_start after the outer one).
        start_event = next((e for e in reversed(events) if e["event"] == "session_start"), None)
        if start_event is None:
            raise ValueError(f"No session_start found in log for '{session_id}'")

        prompt: str = start_event["prompt"]
        flow_name: str = start_event.get("flow_name", "main")

        # Derive session workspace path (same logic as run())
        agent_config = self._load_agent()
        _base_paths = agent_config.get("permissions", {}).get("workspace_paths", [])
        session_workspace = Path(_resolve_path(_base_paths[0]).rstrip("/")) / session_id if _base_paths else None

        # --- 1. Try latest workspace checkpoint ---
        prior_messages: list | None = None
        resume_from_block: str | None = None
        resume_todo_list: list | None = None
        checkpoint_source = "none"
        if session_workspace:
            from engine.state import latest_session_checkpoint, load_checkpoint as _load_cp
            cp_path = latest_session_checkpoint(session_workspace)
            if cp_path:
                try:
                    cp_data = _load_cp(cp_path)
                    prior_messages = cp_data.get("_conv_turns") or cp_data.get("messages")
                    resume_from_block = cp_data.get("_last_block_id")
                    resume_todo_list = cp_data.get("_todo_list")
                    checkpoint_source = cp_path.name
                except Exception as exc:
                    _console.print(f"[yellow]Warning:[/yellow] could not load checkpoint {cp_path}: {exc}")

        # --- 2. Fall back to JSONL session_end snapshot ---
        if not prior_messages:
            snapshot_event = next(
                (e for e in reversed(events)
                 if e["event"] in ("session_end", "unhandled_error") and "messages" in e),
                start_event,
            )
            prior_messages = snapshot_event.get("messages") or [{"role": "user", "content": prompt}]
            checkpoint_source = f"jsonl:{snapshot_event['event']}"

        # --- 3. Inject workspace file listing so agent knows what it already made ---
        if session_workspace:
            from engine.state import workspace_file_summary
            summary = workspace_file_summary(session_workspace)
            if summary:
                prior_messages = list(prior_messages)  # ensure mutable copy
                prior_messages.append({
                    "role": "user",
                    "content": (
                        "[SYSTEM] Resuming previous session. "
                        "The following files already exist in your workspace from prior work — "
                        "do NOT redo research that is already captured here. "
                        "Review these and continue from where you left off:\n\n"
                        + summary
                    ),
                })

        # --- 4. Append caller-supplied extra messages (e.g. human reply, timeout notice) ---
        if extra_messages:
            prior_messages = list(prior_messages)  # ensure mutable
            prior_messages.extend(extra_messages)

        _console.print(
            f"[bold yellow]Resuming session[/bold yellow] [dim]{session_id}[/dim]  "
            f"[dim](source: {checkpoint_source} | {len(prior_messages)} messages"
            + (f" | block: {resume_from_block}" if resume_from_block else "")
            + "[/dim]"
        )

        return self.run(
            prompt=prompt,
            flow_name=flow_name,
            session_id=session_id,
            prior_messages=prior_messages,
            resume_from_block=resume_from_block,
            resume_todo_list=resume_todo_list,
            shared_overrides=shared_overrides,
        )

    def _load_agent(self) -> dict:
        """Load agent YAML, preferring a DATA_DIR override over the built-in."""
        path = paths.resolve("agents", f"{self.agent_id}.yaml")
        if not path.exists():
            raise FileNotFoundError(f"Agent definition not found: {path}")
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)


def _load_context_files(agent_config: dict) -> str:
    """Read files matching context_files globs from agent config and return XML-tagged blocks."""
    import glob as _glob
    entries: list[dict] = agent_config.get("context_files", [])
    if not entries:
        return ""
    parts: list[str] = []
    for entry in entries:
        pattern = entry.get("glob", "")
        tag = entry.get("tag", "context")
        if not pattern:
            continue
        matched = sorted(_glob.glob(pattern, recursive=True))
        if not matched:
            continue
        chunks: list[str] = []
        for fpath in matched:
            try:
                with open(fpath, encoding="utf-8") as fh:
                    chunks.append(fh.read().strip())
            except UnicodeDecodeError:
                with open(fpath, encoding="latin-1") as fh:
                    chunks.append(fh.read().strip())
            except OSError:
                pass
        if chunks:
            parts.append(f"<{tag}>\n" + "\n\n".join(chunks) + f"\n</{tag}>")
    return "\n\n".join(parts)


def _dispatch_on_error(
    error_type: str,
    exc: Exception,
    flow,
    flow_config: dict,
    block_instances: dict,
    shared: dict,
) -> None:
    """Run the on_error recovery block for the given error_type, if configured."""
    on_error = flow_config.get("on_error", {})
    handler = on_error.get(error_type)
    if not handler:
        return

    start_block = handler.get("start")
    if not start_block or start_block not in block_instances:
        _console.print(
            f"[yellow]on_error.{error_type}: recovery block '{start_block}' not found — skipping.[/yellow]"
        )
        return

    # Inject a system message so the recovery block understands the situation
    shared.setdefault("messages", []).append({
        "role": "user",
        "content": (
            f"[SYSTEM] The session encountered an error ({error_type}): {exc}. "
            "A recovery flow is now running. Use the workspace files already written "
            "to produce the best output you can."
        ),
    })
    shared["iteration"] = 0  # fresh budget for the recovery flow
    shared.pop("_grace_mode", None)
    shared.pop("_iteration_warned", None)

    _console.print(
        f"\n[bold yellow]Running on_error recovery:[/bold yellow] "
        f"{error_type} → [cyan]{start_block}[/cyan]"
    )
    flow.start_node = block_instances[start_block]
    try:
        flow._run(shared)
    except Exception as recovery_exc:
        import traceback as _tb
        _console.print(
            f"[bold red]Recovery flow also failed:[/bold red] {recovery_exc}\n"
            + _tb.format_exc()
        )

    # Always print the resume hint so the user knows they can continue manually
    agent_id = shared.get("agent_id", "?")
    session_id = shared.get("session_id", "?")
    _console.print(
        f"\n[bold cyan]To resume this session manually:[/bold cyan]\n"
        f"  uv run run.py --agent {agent_id} --resume {session_id}"
    )


def _check_input_guardrail(
    prompt: str,
    guardrail_prompt: str,
    model_id: str,
    shared: dict,
) -> bool:
    """
    Run the input safety guardrail against `prompt`.

    Returns True if execution should proceed, False if rejected.
    Side-effects:
      - On warn: appends a [SYSTEM] warning to shared["messages"]
      - On rejected: appends a [SYSTEM] refusal to shared["messages"]
    """
    from engine.llm import call_llm

    parsed, _, _ = call_llm(
        model_id=model_id,
        system_prompt=guardrail_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    verdict = parsed.get("verdict", "approved")
    reason = parsed.get("reason", "")

    if verdict == "rejected":
        # Append a user-facing refusal as if the assistant said it
        shared["messages"].append({
            "role": "assistant",
            "content": (
                "I'm sorry, I can't help with that request. "
                f"({reason})"
            ),
        })
        shared["_input_rejected"] = True
        shared["logger"].log_event(shared, "input_guardrail_rejected", reason=reason)
        return False

    if verdict == "warn":
        # Append a [SYSTEM] warning directly to messages
        # Note: _push_message cannot be used here because shared["_conv"] is None
        shared["messages"].append({
            "role": "user",
            "content": f"[SYSTEM] Input safety advisory: {reason}. Treat this request with additional caution."
        })
        shared["logger"].log_event(shared, "input_guardrail_warned", reason=reason)

    return True
