"""Unit tests for dancode/config.py."""

from __future__ import annotations

import pytest

from dancode.config import (
    FeatureTask,
    ProjectConfig,
    TaskPhase,
    TaskStatus,
    load_or_create_project,
    repo_slug,
)


# ---------------------------------------------------------------------------
# repo_slug
# ---------------------------------------------------------------------------


def test_repo_slug_strips_git_suffix():
    slug = repo_slug("/some/local/path", "git@github.com:org/repo.git")
    assert ".git" not in slug
    assert "repo" in slug


def test_repo_slug_https():
    slug = repo_slug("/some/local/path", "https://github.com/org/repo")
    assert "github.com" in slug
    assert "org" in slug
    assert "repo" in slug


def test_repo_slug_local_path():
    slug = repo_slug("/home/user/myrepo", None)
    assert slug  # non-empty
    assert "/" not in slug  # filesystem-safe
    assert "myrepo" in slug


# ---------------------------------------------------------------------------
# FeatureTask defaults
# ---------------------------------------------------------------------------


def test_feature_task_defaults():
    task = FeatureTask(
        task_id="abc123",
        feature_name="my-feature",
        feature_description="add something",
    )
    assert task.phase == TaskPhase.PLAN
    assert task.status == TaskStatus.PENDING
    assert task.worktree_path is None
    assert task.feature_branch is None
    assert task.blocked_reason is None
    assert task.session_ids == {}


# ---------------------------------------------------------------------------
# ProjectConfig round-trip
# ---------------------------------------------------------------------------


def test_project_config_round_trip():
    config = ProjectConfig(
        clone_url="https://github.com/org/repo",
        local_path="/tmp/repo",
        tasks=[
            FeatureTask(
                task_id="abc",
                feature_name="feat",
                feature_description="do stuff",
            )
        ],
    )
    raw = config.model_dump_json()
    restored = ProjectConfig.model_validate_json(raw)
    assert restored == config


# ---------------------------------------------------------------------------
# load_or_create_project
# ---------------------------------------------------------------------------


def test_load_or_create_project_creates(tmp_path, monkeypatch):
    monkeypatch.setattr("dancode.config.PROJECTS_DIR", tmp_path)
    config, slug = load_or_create_project("/tmp/newrepo", None)
    assert config.local_path == "/tmp/newrepo"
    assert config.tasks == []
    assert slug  # non-empty


def test_load_or_create_project_loads(tmp_path, monkeypatch):
    monkeypatch.setattr("dancode.config.PROJECTS_DIR", tmp_path)
    # Create and persist a project with one task
    config1, slug = load_or_create_project("/tmp/persistrepo", None)
    config1.tasks.append(
        FeatureTask(task_id="zz", feature_name="f", feature_description="d")
    )
    config1.save(slug)
    # Reload — should find the saved file
    config2, slug2 = load_or_create_project("/tmp/persistrepo", None)
    assert slug == slug2
    assert len(config2.tasks) == 1
    assert config2.tasks[0].task_id == "zz"


def test_feature_task_phase_token_counts_default():
    """phase_token_counts defaults to empty dict."""
    task = FeatureTask(task_id="t1", feature_name="feat", feature_description="desc")
    assert task.phase_token_counts == {}


def test_feature_task_phase_token_counts_roundtrip():
    """phase_token_counts survives JSON round-trip via model_dump_json."""
    import json
    task = FeatureTask(task_id="t1", feature_name="feat", feature_description="desc")
    task.phase_token_counts["phase1_plan"] = 999
    raw = task.model_dump_json()
    loaded = FeatureTask.model_validate_json(raw)
    assert loaded.phase_token_counts["phase1_plan"] == 999
