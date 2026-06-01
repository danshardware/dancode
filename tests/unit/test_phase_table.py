"""Tests for the phase table widget."""

from dancode.config import FeatureTask

from dancode.widgets.task_detail import _render_phase_table


def test_render_phase_table_has_ten_lines():
    """_render_phase_table returns exactly 10 non-empty lines."""
    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    table = _render_phase_table(task)
    lines = [l for l in table.split("\n") if l.strip()]
    assert len(lines) == 10


def test_render_phase_table_shows_token_count():
    """Phase with token count shows formatted number."""
    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    task.phase_token_counts["phase1_plan"] = 5000
    assert "5,000 tok" in _render_phase_table(task)


def test_render_phase_table_dash_for_untracked():
    """Phase without token count shows dash."""
    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    table = _render_phase_table(task)
    # All phases start with no tokens so all should show dash
    assert "—" in table


def test_render_phase_table_running_icon():
    """Current running phase shows the running icon."""
    from dancode.config import TaskPhase, TaskStatus

    task = FeatureTask(task_id="t", feature_name="f", feature_description="d")
    task.phase = TaskPhase.PLAN
    task.status = TaskStatus.RUNNING
    assert "▶" in _render_phase_table(task)