"""Unit tests for AgentWorker message types (TaskStatusChanged, LogLine)."""

from __future__ import annotations

from dancode.config import TaskPhase
from dancode.workers.agent_runner import LogLine, TaskStatusChanged


def test_task_status_changed_fields():
    msg = TaskStatusChanged(
        task_id="abc",
        phase=TaskPhase.PLAN,
        status="running",
        reason="test reason",
    )
    assert msg.task_id == "abc"
    assert msg.phase == TaskPhase.PLAN
    assert msg.status == "running"
    assert msg.reason == "test reason"


def test_task_status_changed_default_reason():
    msg = TaskStatusChanged(task_id="xyz", phase=TaskPhase.CODE, status="blocked")
    assert msg.reason == ""


def test_log_line_fields():
    msg = LogLine(task_id="def", line="some agent log output")
    assert msg.task_id == "def"
    assert msg.line == "some agent log output"


def test_load_guidance_docs_returns_nonempty():
    """_load_guidance_docs reads AGENTS.md and skill files from repo root."""
    from pathlib import Path
    from dancode.workers.agent_runner import _load_guidance_docs

    # Navigate from tests/unit/ → tests/ → repo root
    repo_root = Path(__file__).parent.parent.parent
    agents_md, coding_standards = _load_guidance_docs(repo_root)

    assert isinstance(agents_md, str)
    assert len(agents_md) > 0
    assert isinstance(coding_standards, str)
    assert len(coding_standards) > 0


def test_load_guidance_docs_missing_dir(tmp_path):
    """_load_guidance_docs returns empty strings gracefully when files are absent."""
    from dancode.workers.agent_runner import _load_guidance_docs

    agents_md, coding_standards = _load_guidance_docs(tmp_path)
    assert agents_md == ""
    assert coding_standards == ""
