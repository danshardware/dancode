"""Git worktree management tools for dancode workflow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools import ToolContext, tool


def _run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a git command; return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


@tool
def git_worktree_create(repo_path: str, branch: str, dest_path: str, context: ToolContext) -> str:
    """Create a new git worktree for a feature branch.

    Creates the branch if it does not exist.
    If the branch is already checked out in another worktree, returns that
    existing path so the caller can use it directly.
    Returns the worktree path on success, or [ERROR] on failure.
    """
    repo = Path(repo_path).resolve()
    dest = Path(dest_path).resolve()

    if dest.exists():
        return f"[ERROR] Destination already exists: {dest}"

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Check if branch exists
    rc, _, _ = _run_git(["rev-parse", "--verify", branch], str(repo))
    if rc != 0:
        # Branch doesn't exist — create worktree with new branch based on HEAD
        rc, out, err = _run_git(["worktree", "add", "-b", branch, str(dest)], str(repo))
    else:
        # Branch exists — attempt to add worktree; may fail if branch already checked out
        rc, out, err = _run_git(["worktree", "add", str(dest), branch], str(repo))
        if rc != 0 and "already checked out" in err:
            # Branch is live in another worktree; find and return that path
            _, wt_list, _ = _run_git(["worktree", "list", "--porcelain"], str(repo))
            wt_path: str | None = None
            for line in wt_list.splitlines():
                if line.startswith("worktree "):
                    wt_path = line[9:]
                elif line.startswith("branch ") and line[7:].removeprefix("refs/heads/") == branch:
                    return f"Branch already checked out at: {wt_path}"

    if rc != 0:
        return f"[ERROR] git worktree add failed: {err}"
    return f"Worktree created: {dest} (branch: {branch})"


@tool
def git_worktree_remove(worktree_path: str, context: ToolContext) -> str:
    """Remove a git worktree at the given path.

    Uses --force to handle unclean states. Does not delete the branch itself.
    """
    path = Path(worktree_path).resolve()

    # Find repo root by walking up to find .git
    repo = path
    while repo != repo.parent:
        if (repo / ".git").exists() or (repo / ".git").is_file():
            break
        repo = repo.parent
    else:
        return f"[ERROR] Could not find git repo root from: {worktree_path}"

    # The actual repo root for a worktree has a .git file (not dir)
    # Walk up from worktree to find the main repo
    rc, main_root, err = _run_git(["rev-parse", "--show-toplevel"], str(path))
    if rc != 0:
        return f"[ERROR] Cannot resolve repo root: {err}"

    # The main worktree root may differ; use git worktree list to find main
    rc, out, err = _run_git(["worktree", "list", "--porcelain"], main_root)
    if rc != 0:
        return f"[ERROR] Cannot list worktrees: {err}"

    # Find first (main) worktree path
    lines = out.splitlines()
    main_worktree = lines[0].replace("worktree ", "").strip() if lines else main_root

    rc, out, err = _run_git(["worktree", "remove", "--force", str(path)], main_worktree)
    if rc != 0:
        return f"[ERROR] git worktree remove failed: {err}"
    return f"Worktree removed: {path}"


@tool
def git_list_worktrees(repo_path: str, context: ToolContext) -> str:
    """List all git worktrees for a repository. Returns a JSON array of worktree info objects."""
    repo = Path(repo_path).resolve()
    rc, out, err = _run_git(["worktree", "list", "--porcelain"], str(repo))
    if rc != 0:
        return f"[ERROR] git worktree list failed: {err}"

    worktrees = []
    current: dict = {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[len("worktree "):].strip()}
        elif line.startswith("HEAD "):
            current["head"] = line[5:].strip()
        elif line.startswith("branch "):
            current["branch"] = line[7:].strip()
        elif line == "bare":
            current["bare"] = True
        elif line == "":
            if current:
                worktrees.append(current)
                current = {}
    if current:
        worktrees.append(current)

    return json.dumps(worktrees, indent=2)


@tool
def git_squash_merge(repo_path: str, branch: str, message: str, context: ToolContext) -> str:
    """Squash-merge a feature branch into the current branch of the main worktree.

    Runs tests after merging (uv run pytest tests/ -v --tb=short) and aborts on failure.
    Returns the merge result or [ERROR] with reason.
    """
    repo = Path(repo_path).resolve()

    # Squash merge
    rc, out, err = _run_git(["merge", "--squash", branch], str(repo))
    if rc != 0:
        # Abort the merge state
        _run_git(["merge", "--abort"], str(repo))
        return f"[ERROR] Squash merge failed: {err}"

    # Commit
    rc, out, err = _run_git(["commit", "-m", message], str(repo))
    if rc != 0:
        return f"[ERROR] Commit after squash merge failed: {err}"

    return f"Squash merged branch '{branch}' with message: {message!r}"
