"""Shared pytest fixtures for dancode tests."""

from __future__ import annotations

import importlib
import subprocess

import pytest


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a minimal real git repo under tmp_path and return its Path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, check=True, capture_output=True,
    )
    (repo / "README.md").write_text("# smoke\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo, check=True, capture_output=True,
    )
    return repo


@pytest.fixture
def council_data_dir(tmp_path, monkeypatch):
    """Set COUNCIL_DATA_DIR to a temp dir and reload engine.paths so DATA_DIR updates.

    Using importlib.reload() is safe here because pytest runs tests sequentially
    by default and the monkeypatch fixture restores the env var after the test.
    """
    data_dir = tmp_path / "council_data"
    data_dir.mkdir()
    monkeypatch.setenv("COUNCIL_DATA_DIR", str(data_dir))

    import engine.paths as paths_mod
    importlib.reload(paths_mod)

    yield data_dir

    # Restore original state so subsequent tests see the real DATA_DIR.
    importlib.reload(paths_mod)
