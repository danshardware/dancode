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
