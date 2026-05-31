"""dancode CLI entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the repo root (parent of dancode/) is on sys.path so engine/tools imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Set COUNCIL_DATA_DIR BEFORE importing engine.paths — it reads the env var at module level.
from dancode.config import CONFIG_DIR as _CONFIG_DIR
os.environ.setdefault("COUNCIL_DATA_DIR", str(_CONFIG_DIR))

from engine import paths


def _resolve_repo(target: str) -> tuple[str, str | None]:
    """
    Resolve local_path and clone_url from a file path or remote URL.

    Returns (local_path, clone_url_or_None).
    Exits if the path doesn't exist or isn't a git repo.
    """
    import git as gitpython

    p = Path(target).expanduser().resolve()
    if not p.exists():
        print(f"ERROR: Path does not exist: {target}")
        sys.exit(1)

    try:
        repo = gitpython.Repo(str(p), search_parent_directories=True)
    except gitpython.exc.InvalidGitRepositoryError:
        print(f"ERROR: Not a git repository: {p}")
        sys.exit(1)

    local_path = str(repo.working_dir)

    clone_url: str | None = None
    try:
        clone_url = repo.remotes.origin.url
    except (AttributeError, IndexError):
        pass  # local-only repo — no remote

    return local_path, clone_url


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dancode",
        description="Multi-agent coding workflow orchestrator.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Path to the git repository (default: current directory)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Discard saved session state for this project and start fresh.",
    )
    parser.add_argument(
        "--agent",
        help="[Debug] Run a single agent directly without launching the TUI.",
    )
    parser.add_argument(
        "--prompt",
        help="[Debug] Prompt to use when --agent is specified.",
    )
    args = parser.parse_args()

    # Debug mode: run a single agent directly
    if args.agent:
        if not args.prompt:
            print("ERROR: --prompt is required when using --agent")
            sys.exit(1)
        from engine.runner import AgentRunner
        paths.init_data_dirs()
        runner = AgentRunner(agent_id=args.agent)
        runner.run(prompt=args.prompt)
        return

    # Validate AWS Bedrock before going further
    from dancode.bedrock_check import validate_bedrock
    validate_bedrock()

    local_path, clone_url = _resolve_repo(args.target)

    from dancode.config import load_or_create_project
    config, slug = load_or_create_project(local_path, clone_url)

    if args.reset:
        confirm = input(
            f"Reset session for '{Path(local_path).name}'? "
            f"All task progress will be lost. [y/N] "
        )
        if confirm.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)
        config.tasks.clear()
        config.save(slug)

    # Point the council DATA_DIR to our dancode config dir for this project
    # so logs/workspace go to ~/.config/dancode/logs/ and workspace/.
    from dancode.config import LOGS_DIR
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    paths.init_data_dirs()

    from dancode.app import DancodeApp
    app = DancodeApp(config=config, slug=slug, repo_path=local_path)
    app.run()


if __name__ == "__main__":
    main()
