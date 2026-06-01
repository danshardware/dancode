"""Agent runner worker — drives phase agents in a background thread.

Each FeatureTask gets its own AgentWorker.  The worker advances through
phases (1 → 10) calling AgentRunner.run() for each phase in sequence.
It posts TaskStatusChanged messages back to the app as state changes.
"""

from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from textual.message import Message

if TYPE_CHECKING:
    from dancode.config import FeatureTask, TaskPhase


def _load_guidance_docs(repo_root: Path) -> tuple[str, str]:
    """Load AGENTS.md and skill SKILL.md files from the dancode repo root.

    Returns:
        agents_md: Content of AGENTS.md.
        coding_standards: Concatenated content of all .agents/skills/*/SKILL.md files,
            each prefixed with a header line showing the skill name.
    """
    agents_md_path = repo_root / "AGENTS.md"
    agents_md = agents_md_path.read_text(encoding="utf-8") if agents_md_path.exists() else ""

    skills_dir = repo_root / ".agents" / "skills"
    skill_parts: list[str] = []
    if skills_dir.exists():
        for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
            skill_name = skill_file.parent.name
            content = skill_file.read_text(encoding="utf-8")
            skill_parts.append(f"=== SKILL: {skill_name} ===\n{content}")
    coding_standards = "\n\n".join(skill_parts)

    return agents_md, coding_standards


class TaskStatusChanged(Message):
    """Posted when a task's status or phase changes."""
    def __init__(self, task_id: str, phase: "TaskPhase | None", status: str, reason: str = "") -> None:
        super().__init__()
        self.task_id = task_id
        self.phase = phase
        self.status = status
        self.reason = reason


class LogLine(Message):
    """Posted when an agent emits a log line for a task."""
    def __init__(self, task_id: str, line: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.line = line


class AgentWorker:
    """
    Drives a FeatureTask through its phase pipeline.

    Call `start()` to run in a background asyncio task.
    The worker posts Textual messages via the `post` callback.
    """

    def __init__(
        self,
        task: "FeatureTask",
        repo_path: str,
        slug: str,
        post,  # callable(Message)
    ) -> None:
        self._task = task
        self._repo_path = repo_path
        self._slug = slug
        self._post = post
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    async def run(self) -> None:
        from dancode.config import TaskPhase, TaskStatus, PHASE_AGENTS, LOGS_DIR
        from engine.runner import AgentRunner

        task = self._task
        repo = Path(self._repo_path)

        # Advance from the task's current phase through phase 10
        phases = [p for p in TaskPhase if p >= task.phase]

        for phase in phases:
            if self._cancelled:
                break

            agent_id = PHASE_AGENTS[phase]
            task.phase = phase
            task.status = TaskStatus.RUNNING
            self._post(TaskStatusChanged(task.task_id, phase, "running"))

            # Build the shared state for Mustache templates
            shared_overrides: dict = {
                "_extra_allowed_paths": [str(repo)],
                "repo_path": str(repo),
                "feature_name": task.feature_name,
                "feature_description": task.feature_description,
                "feature_branch": task.feature_branch or f"feature/{task.feature_name}-{task.task_id}",
                "openhands_model": task.openhands_model,
                "_tui_mode": True,
            }

            # Inject guidance docs for planning phases (1-3)
            if phase in (TaskPhase.PLAN, TaskPhase.JANK, TaskPhase.REFINE):
                _repo_root = Path(__file__).parent.parent.parent
                _agents_md, _coding_standards = _load_guidance_docs(_repo_root)
                shared_overrides["agents_md"] = _agents_md
                shared_overrides["coding_standards"] = _coding_standards

            log_path = LOGS_DIR / f"{self._slug}.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Determine resume parameters if the task was suspended at a human gate
            _resume_session_id: str | None = None
            _resume_messages: list | None = None
            _resume_block: str | None = None
            if task.pending_checkpoint and task.pending_reply:
                try:
                    from engine.state import load_checkpoint
                    _cp = load_checkpoint(task.pending_checkpoint)
                    _resume_session_id = _cp.get("session_id")
                    _resume_messages = list(_cp.get("messages", []))
                    _resume_block = _cp.get("_suspend_block") or _cp.get("_current_block_id")
                    shared_overrides["_tui_pending_reply"] = task.pending_reply
                    task.pending_checkpoint = None
                    task.pending_reply = None
                except Exception as exc:
                    self._post(LogLine(task.task_id, f"[yellow]Could not load checkpoint for resume: {exc}. Restarting phase.[/yellow]"))
                    task.pending_checkpoint = None
                    task.pending_reply = None

            try:
                # AgentRunner.run() is synchronous — run in executor
                loop = asyncio.get_running_loop()
                runner = AgentRunner(agent_id=agent_id, logs_dir=str(log_path.parent))
                result = await loop.run_in_executor(
                    None,
                    lambda r=runner, s=shared_overrides,
                           sid=_resume_session_id, msgs=_resume_messages,
                           rb=_resume_block: r.run(
                        prompt=task.feature_description,
                        session_id=sid,
                        prior_messages=msgs,
                        resume_from_block=rb,
                        shared_overrides=s,
                    ),
                )

                # Extract and persist cumulative token usage for this phase
                _conv = result.get("_conv") if isinstance(result, dict) else None
                if _conv is not None:
                    _total_tokens = (
                        getattr(_conv, "input_tokens", 0)
                        + getattr(_conv, "output_tokens", 0)
                    )
                    task.phase_token_counts[agent_id] = _total_tokens
            except Exception as exc:
                tb = traceback.format_exc()
                self._post(LogLine(task.task_id, f"[ERROR] Phase {phase}: {exc}\n{tb}"))
                task.status = TaskStatus.BLOCKED
                task.blocked_reason = str(exc)
                self._post(TaskStatusChanged(task.task_id, phase, "blocked", str(exc)))
                return

            # Check for input guardrail rejection — block the task instead of advancing
            if isinstance(result, dict) and result.get("_input_rejected"):
                reason = "Input guardrail rejected the feature description for this phase."
                task.status = TaskStatus.BLOCKED
                task.blocked_reason = reason
                self._post(TaskStatusChanged(task.task_id, phase, "blocked", reason))
                self._post(LogLine(task.task_id, f"[red]Phase {phase} blocked: guardrail rejected the input.[/red]"))
                return

            # Check for a suspended result (human_reply block waiting for input)
            if isinstance(result, dict) and result.get("suspended"):
                task.pending_checkpoint = result.get("checkpoint_path")
                task.status = TaskStatus.WAITING
                # Show the agent's questions in the log panel
                action_input = result.get("action_input", {})
                if isinstance(action_input, dict):
                    questions = action_input.get("questions") or action_input.get("message") or ""
                else:
                    questions = str(action_input) if action_input else ""
                task.pending_questions = questions or None
                self._post(TaskStatusChanged(task.task_id, phase, "waiting"))
                if questions:
                    self._post(LogLine(task.task_id, f"[yellow]Agent is waiting for your reply:[/yellow]\n\n{questions}"))
                else:
                    self._post(LogLine(task.task_id, "[yellow]Agent is waiting for your input. Type your reply below.[/yellow]"))
                return

            # Check for a BLOCKED result via shared state (set by openhands_dispatch)
            openhands_result = result.get("openhands_result", "") if isinstance(result, dict) else ""
            if isinstance(openhands_result, str) and openhands_result.startswith("BLOCKED"):
                task.status = TaskStatus.BLOCKED
                task.blocked_reason = openhands_result
                self._post(TaskStatusChanged(task.task_id, phase, "blocked", openhands_result))
                return

            self._post(LogLine(task.task_id, f"Phase {phase} complete."))

        if not self._cancelled:
            task.status = TaskStatus.DONE
            self._post(TaskStatusChanged(task.task_id, None, "done"))
