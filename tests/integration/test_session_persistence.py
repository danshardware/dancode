"""Integration tests for ProjectConfig persistence (disk I/O, no AWS)."""

from __future__ import annotations

import pytest

from dancode.config import FeatureTask, ProjectConfig, TaskPhase, TaskStatus


@pytest.fixture(autouse=True)
def isolated_projects_dir(tmp_path, monkeypatch):
    """Redirect PROJECTS_DIR to a temp directory for all tests in this module."""
    monkeypatch.setattr("dancode.config.PROJECTS_DIR", tmp_path)
    return tmp_path


def _make_config(local_path: str = "/tmp/repo") -> tuple[ProjectConfig, str]:
    """Return (config, slug) with a deterministic local path."""
    from dancode.config import load_or_create_project
    return load_or_create_project(local_path, None)


def test_save_and_reload_preserves_all_fields(tmp_path):
    config, slug = _make_config("/tmp/myrepo")
    config.tasks.append(
        FeatureTask(
            task_id="t1",
            feature_name="auth",
            feature_description="add auth",
            phase=TaskPhase.CODE,
            status=TaskStatus.RUNNING,
        )
    )
    config.tasks.append(
        FeatureTask(
            task_id="t2",
            feature_name="logging",
            feature_description="add logging",
        )
    )
    config.save(slug)

    loaded = ProjectConfig.load(slug)
    assert loaded is not None
    assert loaded == config
    assert len(loaded.tasks) == 2


def test_phase_advances_on_reload(tmp_path):
    config, slug = _make_config("/tmp/phaserepo")
    task = FeatureTask(task_id="p1", feature_name="feat", feature_description="desc")
    config.tasks.append(task)
    config.save(slug)

    # Mutate and re-save
    config.tasks[0].phase = TaskPhase.DISPATCH
    config.save(slug)

    loaded = ProjectConfig.load(slug)
    assert loaded is not None
    assert loaded.tasks[0].phase == TaskPhase.DISPATCH


def test_status_blocked_on_reload(tmp_path):
    config, slug = _make_config("/tmp/blockedrepo")
    task = FeatureTask(task_id="b1", feature_name="feat", feature_description="desc")
    task.status = TaskStatus.BLOCKED
    task.blocked_reason = "openhands timed out"
    config.tasks.append(task)
    config.save(slug)

    loaded = ProjectConfig.load(slug)
    assert loaded is not None
    assert loaded.tasks[0].status == TaskStatus.BLOCKED
    assert loaded.tasks[0].blocked_reason == "openhands timed out"
