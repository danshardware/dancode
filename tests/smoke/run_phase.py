#!/usr/bin/env python3
"""Smoke test runner — execute a single dancode phase against a real repo.

Usage
-----
    uv run python3 tests/smoke/run_phase.py \\
        --phase phase1_plan \\
        --repo /tmp/smoke-target \\
        --feature "add a health-check endpoint" \\
        --auto-reply "1. REST API. 2. No auth. 3. Done."

Prerequisites
-------------
* AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (or IAM role)
* COUNCIL_DATA_DIR set (defaults to ~/.config/dancode if unset)
* Target repo must have at least one commit
* Phase 4+ require Planning/<feature>/ output from earlier phases
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# COUNCIL_DATA_DIR must be set before any engine.* import
# ---------------------------------------------------------------------------
_DEFAULT_DATA_DIR = str(Path.home() / ".config" / "dancode")
os.environ.setdefault("COUNCIL_DATA_DIR", _DEFAULT_DATA_DIR)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single dancode phase for smoke testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--phase",
        required=True,
        help="Agent ID to run, e.g. phase1_plan, phase4_dispatch",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Absolute path to the target git repository",
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="Feature name / prompt — passed as the agent's initial prompt",
    )
    parser.add_argument(
        "--auto-reply",
        dest="auto_reply",
        default=None,
        help=(
            "Text to inject into human_reply blocks automatically. "
            "Only applicable to phases 1/2/3/8."
        ),
    )
    parser.add_argument(
        "--openhands-model",
        dest="openhands_model",
        default="minimax.minimax-m2.5",
        help="Model string forwarded to openhands_dispatch (phases 5/6).",
    )
    return parser.parse_args()


def _make_slug(repo_path: str) -> str:
    import hashlib
    digest = hashlib.sha256(repo_path.encode()).hexdigest()[:12]
    stem = Path(repo_path).name
    return f"{stem}_{digest}"


def main() -> None:
    args = _parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"ERROR: {repo} is not a git repository (no .git found).")
        sys.exit(1)

    from engine.runner import AgentRunner

    slug = _make_slug(str(repo))
    feature_slug = args.feature.lower().replace(" ", "-")[:60]

    shared_overrides: dict = {
        "_extra_allowed_paths": [str(repo)],
        "repo_path": str(repo),
        "feature_name": feature_slug,
        "feature_description": args.feature,
        "feature_branch": f"feature/{feature_slug}",
        "openhands_model": args.openhands_model,
    }

    logs_dir = Path(os.environ["COUNCIL_DATA_DIR"]) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Patch HumanReplyBlock if --auto-reply was provided
    if args.auto_reply:
        _patch_human_reply(args.auto_reply)

    print(f"[smoke] Running {args.phase} against {repo}")
    print(f"[smoke] Feature: {args.feature}")
    if args.auto_reply:
        print(f"[smoke] Auto-reply: {args.auto_reply[:80]}...")

    runner = AgentRunner(agent_id=args.phase, logs_dir=str(logs_dir))
    try:
        result = runner.run(
            prompt=args.feature,
            shared_overrides=shared_overrides,
        )
        print(f"\n[smoke] Phase {args.phase} completed.")
        if isinstance(result, dict):
            for k, v in result.items():
                print(f"  {k}: {str(v)[:120]}")
    except Exception as exc:
        import traceback
        print(f"\n[smoke] FAILED: {exc}")
        traceback.print_exc()
        sys.exit(1)


def _patch_human_reply(reply_text: str) -> None:
    """Monkey-patch HumanReplyBlock so it returns reply_text without blocking."""
    try:
        import engine.block as block_mod

        _original_cls = block_mod.HumanReplyBlock

        class _AutoReplyBlock(_original_cls):  # type: ignore[misc]
            def run(self, shared_state: dict, context=None) -> dict:  # noqa: ANN001
                print(f"[smoke] Auto-injecting human reply: {reply_text[:60]}...")
                shared_state["human_reply"] = reply_text
                return shared_state

        block_mod.HumanReplyBlock = _AutoReplyBlock
        print("[smoke] HumanReplyBlock patched for auto-reply.")
    except (ImportError, AttributeError) as exc:
        print(f"[smoke] WARNING: Could not patch HumanReplyBlock: {exc}")


if __name__ == "__main__":
    main()
