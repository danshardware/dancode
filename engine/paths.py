"""Central path resolution for the Council runtime.

All mutable state (logs, memory, messages, workspace, shared knowledge,
schedules) lives under DATA_DIR, which maps to the mounted data volume in
production.  Read-only config (agents, flows, config YAML) supports an
override layer: a file at DATA_DIR/<subdir>/<filename> shadows the built-in
copy at the repo root, so operators can customise without rebuilding the image.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Root directories
# ---------------------------------------------------------------------------

#: Repository root (two levels up from this file: engine/ → repo root)
REPO_ROOT: Path = Path(__file__).parent.parent

#: Mutable data root.  Override with the COUNCIL_DATA_DIR environment variable.
DATA_DIR: Path = Path(os.environ.get("COUNCIL_DATA_DIR", "data"))

# ---------------------------------------------------------------------------
# State paths (always inside DATA_DIR — these are the mount-point sub-trees)
# ---------------------------------------------------------------------------

LOGS_DIR: Path = DATA_DIR / "logs"
MEMORY_DB_DIR: Path = DATA_DIR / "memory_db"
MESSAGES_DIR: Path = DATA_DIR / "messages"
WORKSPACE_DIR: Path = DATA_DIR / "workspace"
SHARED_KNOWLEDGE_DIR: Path = DATA_DIR / "shared_knowledge"

#: Persistent schedule definitions written at runtime by schedule_tools.
SCHEDULES_PATH: Path = DATA_DIR / "config" / "schedules.yaml"

# ---------------------------------------------------------------------------
# Startup initialisation
# ---------------------------------------------------------------------------

_REQUIRED_DIRS: tuple[Path, ...] = (
    LOGS_DIR,
    MEMORY_DB_DIR,
    MESSAGES_DIR,
    WORKSPACE_DIR,
    SHARED_KNOWLEDGE_DIR,
    DATA_DIR / "agents",
    DATA_DIR / "flows",
    DATA_DIR / "config",
)


def init_data_dirs() -> None:
    """Create all required data directories if they do not exist.

    Called once at application startup (run.py) so the data volume is always
    in a consistent state whether it is brand-new or already populated.
    """
    for directory in _REQUIRED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)

    _ensure_data_git_repo()


def _ensure_data_git_repo() -> None:
    """Initialise DATA_DIR as a git repository if it is not already one.

    The ops agent commits config changes via `git -C data/ ...`.  If the data
    volume has never been initialised as a repo (e.g. fresh install), those
    commits silently fail.  This ensures the repo always exists before any
    agent runs.
    """
    import subprocess

    git_dir = DATA_DIR / ".git"
    if git_dir.is_dir():
        return  # already a repo

    try:
        subprocess.run(
            ["git", "init", str(DATA_DIR)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(DATA_DIR), "commit", "--allow-empty",
             "-m", "chore: initialise data repository"],
            check=True,
            capture_output=True,
            text=True,
            env={**__import__("os").environ,
                 "GIT_AUTHOR_NAME": "Council",
                 "GIT_AUTHOR_EMAIL": "council@local",
                 "GIT_COMMITTER_NAME": "Council",
                 "GIT_COMMITTER_EMAIL": "council@local"},
        )
    except Exception as exc:  # noqa: BLE001
        # Non-fatal — log a warning but don't prevent startup
        import logging
        logging.getLogger(__name__).warning(
            "Could not initialise git repo in data directory %s: %s", DATA_DIR, exc
        )


# ---------------------------------------------------------------------------
# Override-aware file resolution
# ---------------------------------------------------------------------------


def resolve(subdir: str, filename: str) -> Path:
    """Return the path to a config/agent/flow file.

    Checks DATA_DIR/<subdir>/<filename> first; falls back to the built-in
    copy at REPO_ROOT/<subdir>/<filename>.  This lets operators drop override
    files into the mounted data volume without rebuilding the container image.

    Args:
        subdir:   Sub-directory name, e.g. ``"agents"``, ``"flows"``,
                  ``"config"``.
        filename: File name including extension, e.g. ``"ceo.yaml"``.

    Returns:
        The resolved :class:`~pathlib.Path`.  The file may not exist if
        neither location has it — callers are responsible for the error.
    """
    override = DATA_DIR / subdir / filename
    if override.exists():
        return override
    return REPO_ROOT / subdir / filename
