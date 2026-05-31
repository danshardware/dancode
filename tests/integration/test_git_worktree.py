"""Integration tests for git worktree tools (real git, no AWS).

Uses the tmp_git_repo fixture from conftest.py which creates a real git repo
with an initial commit.
"""

from __future__ import annotations

import subprocess

import pytest

from tools import ToolContext
from tools.git_tools import git_worktree_create, git_worktree_remove


@pytest.fixture
def ctx():
    return ToolContext(agent_id="test", session_id="test-session")


def test_worktree_created_at_expected_path(tmp_git_repo, ctx):
    dest = tmp_git_repo.parent / "worktrees" / "task-001"
    result = git_worktree_create(
        repo_path=str(tmp_git_repo),
        branch="feature/task-001",
        dest_path=str(dest),
        context=ctx,
    )
    assert not result.startswith("[ERROR]"), result
    assert dest.is_dir()


def test_feature_branch_exists_in_worktree(tmp_git_repo, ctx):
    dest = tmp_git_repo.parent / "worktrees" / "task-002"
    git_worktree_create(
        repo_path=str(tmp_git_repo),
        branch="feature/task-002",
        dest_path=str(dest),
        context=ctx,
    )
    proc = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "feature/task-002"


def test_worktree_removed_after_create(tmp_git_repo, ctx):
    dest = tmp_git_repo.parent / "worktrees" / "task-003"
    git_worktree_create(
        repo_path=str(tmp_git_repo),
        branch="feature/task-003",
        dest_path=str(dest),
        context=ctx,
    )
    assert dest.is_dir()

    result = git_worktree_remove(worktree_path=str(dest), context=ctx)
    assert not result.startswith("[ERROR]"), result
    assert not dest.is_dir()
