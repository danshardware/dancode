#!/usr/bin/env python3
"""
Run the Phase 4 → 5 → 6 code loop for a feature, going as far as possible
without human intervention.

If phase 6 finds QA failures, the loop automatically:
  1. Creates a revision dispatch file for each failing task (original dispatch
     + QA review notes appended, so OpenHands knows what to fix)
  2. Resets that task's status in phase5_status.md so phase 5 re-attempts it
  3. Re-runs phase 5 → phase 6 up to --max-retries times

The loop only stops on human input when:
  - Phase 4 fails to create dispatch files
  - Phase 5 has a BLOCKED task (OpenHands couldn't start or complete it)
  - QA failures persist after all retries are exhausted

Usage:
    uv run python3 scripts/run_loop.py --repo /path/to/repo --feature my-feature
    uv run python3 scripts/run_loop.py --repo /path/to/repo --feature my-feature --max-retries 5
    uv run python3 scripts/run_loop.py --repo /path/to/repo --feature my-feature --start-phase 5
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# ── Must set COUNCIL_DATA_DIR before any engine import ──────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("COUNCIL_DATA_DIR", str(Path.home() / ".config" / "dancode"))

from engine import paths  # noqa: E402
from engine.runner import AgentRunner  # noqa: E402

LOGS_DIR = Path(os.environ["COUNCIL_DATA_DIR"]) / "logs"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _runner(agent_id: str) -> AgentRunner:
    return AgentRunner(agent_id=agent_id, logs_dir=str(LOGS_DIR))


def _base_overrides(repo: str, feature: str, openhands_model: str) -> dict:
    return {
        "repo_path": repo,
        "feature_name": feature,
        "openhands_model": openhands_model,
        "_extra_allowed_paths": [repo, str(Path(repo).parent / f"{feature}-worktrees")],
    }


def _check_phase5_status(repo: str, feature: str) -> tuple[list[str], list[str]]:
    """Return (done_tasks, blocked_tasks) from phase5_status.md."""
    status_file = Path(repo) / "Planning" / feature / "phase5_status.md"
    if not status_file.exists():
        return [], []
    content = status_file.read_text()
    done = re.findall(r"^\W*([\w-]+)\W+DONE", content, re.MULTILINE | re.IGNORECASE)
    blocked = re.findall(r"^\W*([\w-]+)\W+BLOCKED", content, re.MULTILINE | re.IGNORECASE)
    return done, blocked


def _check_qa_results(repo: str, feature: str) -> tuple[list[str], list[str], list[str]]:
    """Return (passing_tasks, failing_tasks, unreviewed_tasks) from reviews/ directory."""
    reviews_dir = Path(repo) / "Planning" / feature / "reviews"
    if not reviews_dir.exists():
        return [], [], []
    passing, failing, unreviewed = [], [], []
    for review_file in sorted(reviews_dir.glob("*-review.md")):
        content = review_file.read_text()
        task_id = review_file.stem.replace("-review", "")
        if re.search(r"VERDICT:\s*PASS", content, re.IGNORECASE):
            passing.append(task_id)
        elif re.search(r"VERDICT:\s*FAIL", content, re.IGNORECASE):
            failing.append(task_id)
        else:
            unreviewed.append(task_id)
    return passing, failing, unreviewed


def _reset_task_for_revision(repo: str, feature: str, task_id: str) -> None:
    """
    Prepare a failing task for a phase 5 retry:
    1. Mark it NEEDS_REVISION in phase5_status.md (so phase 5 re-attempts it).
    2. Create a revision dispatch file that includes the original dispatch
       plus the QA review notes, so OpenHands knows exactly what to fix.
    """
    plan_dir = Path(repo) / "Planning" / feature

    # 1. Update phase5_status.md
    status_file = plan_dir / "phase5_status.md"
    if status_file.exists():
        content = status_file.read_text()
        # Replace "task-id  DONE" with "task-id  NEEDS_REVISION" (case-insensitive)
        content = re.sub(
            rf"({re.escape(task_id)}\W+)DONE",
            r"\1NEEDS_REVISION",
            content,
            flags=re.IGNORECASE,
        )
        status_file.write_text(content)

    # 2. Build revision dispatch: original dispatch + QA failure notes appended
    dispatch_files = list(plan_dir.glob(f"dispatch/**/{task_id}-dispatch.md"))
    review_file = plan_dir / "reviews" / f"{task_id}-review.md"

    if not dispatch_files:
        return  # nothing to revise from — phase 5 will have to figure it out

    original_dispatch = dispatch_files[0]
    revision_path = original_dispatch.parent / f"{task_id}-dispatch-revision.md"

    review_text = review_file.read_text() if review_file.exists() else "(review file not found)"
    revision_path.write_text(
        original_dispatch.read_text()
        + "\n\n"
        + "---\n"
        + "## QA REVISION REQUIRED\n\n"
        + "The previous implementation failed QA. Read the review below and fix "
        + "every FAIL item before committing.\n\n"
        + review_text
    )

    # Point the dispatch entry at the revision file (overwrite the original path reference)
    # Phase 5 picks up dispatch files by scanning the dispatch/ directory, so renaming
    # the original to the revision name is the simplest signal.
    original_dispatch.replace(original_dispatch.parent / f"{task_id}-dispatch.md.bak")
    revision_path.rename(original_dispatch)


# ── Phase runners ────────────────────────────────────────────────────────────

def run_phase4(repo: str, feature: str, openhands_model: str) -> bool:
    """Generate dispatch files. Skipped if SCHEDULE.md already exists."""
    schedule = Path(repo) / "Planning" / feature / "dispatch" / "SCHEDULE.md"
    if schedule.exists():
        print("  [phase 4] SCHEDULE.md already exists — skipped.")
        return True

    print("  Running phase 4 (dispatch)…")
    _runner("phase4_dispatch").run(
        prompt=f"Generate dispatch files for feature: {feature}",
        shared_overrides=_base_overrides(repo, feature, openhands_model),
    )
    if not schedule.exists():
        print("\nERROR: Phase 4 finished but SCHEDULE.md was not created.")
        print(f"  Check: {schedule}")
        print("  Inspect the agent log in:", LOGS_DIR / "phase4_dispatch")
        return False
    print("  [phase 4] Done — dispatch files created.")
    return True


def run_phase5(repo: str, feature: str, openhands_model: str) -> tuple[bool, list[str]]:
    """
    Run coding tasks. Returns (can_continue, blocked_tasks).
    can_continue is True even with some blocked tasks as long as at least
    one task completed (QA can still run on those).
    """
    print("  Running phase 5 (code)…")
    _runner("phase5_code").run(
        prompt=f"Execute coding tasks for feature: {feature}",
        shared_overrides=_base_overrides(repo, feature, openhands_model),
    )
    done_tasks, blocked_tasks = _check_phase5_status(repo, feature)

    if blocked_tasks:
        print(f"  [phase 5] BLOCKED tasks ({len(blocked_tasks)}):")
        for task_id in blocked_tasks:
            dispatch_files = list(
                Path(repo).glob(f"Planning/{feature}/dispatch/**/{task_id}-dispatch.md")
            )
            hint = f"  → {dispatch_files[0].relative_to(repo)}" if dispatch_files else ""
            print(f"    ✗ {task_id}{hint}")

    if done_tasks:
        print(f"  [phase 5] Done tasks ({len(done_tasks)}): {', '.join(done_tasks)}")
        return True, blocked_tasks

    print("  [phase 5] No tasks completed. Cannot proceed to QA.")
    return False, blocked_tasks


def run_phase6(repo: str, feature: str, openhands_model: str) -> tuple[bool, list[str]]:
    """Run QA reviews. Returns (all_passed, failing_tasks)."""
    print("  Running phase 6 (QA)…")
    _runner("phase6_qa").run(
        prompt=f"QA review for feature: {feature}",
        shared_overrides=_base_overrides(repo, feature, openhands_model),
    )
    passing, failing, _ = _check_qa_results(repo, feature)

    if passing:
        print(f"  [phase 6] Passing ({len(passing)}): {', '.join(passing)}")
    if failing:
        print(f"  [phase 6] Failing ({len(failing)}): {', '.join(failing)}")

    return len(failing) == 0 and len(passing) > 0, failing


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the phase 4→5→6 code loop, auto-retrying QA failures."
    )
    parser.add_argument("--repo", required=True, help="Absolute path to the target git repo")
    parser.add_argument("--feature", required=True, help="Feature name (matches Planning/<feature>/)")
    parser.add_argument(
        "--start-phase", type=int, default=4, choices=[4, 5, 6], metavar="{4,5,6}",
        help="Resume from this phase (default: 4)",
    )
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Max phase 5→6 retry cycles for QA failures (default: 3)",
    )
    parser.add_argument(
        "--openhands-model", default="minimax.minimax-m2.5",
        help="Model string passed to OpenHands (default: minimax.minimax-m2.5)",
    )
    args = parser.parse_args()

    repo = str(Path(args.repo).resolve())
    feature = args.feature
    model = args.openhands_model

    plan_dir = Path(repo) / "Planning" / feature
    if not plan_dir.exists():
        print(f"ERROR: Planning directory not found: {plan_dir}")
        print("       Run phases 1–3 first to generate the plan.")
        sys.exit(1)

    print(f"\ndancode — Phase 4→5→6 loop")
    print(f"  Repo:        {repo}")
    print(f"  Feature:     {feature}")
    print(f"  Model:       {model}")
    print(f"  Resume:      phase {args.start_phase}")
    print(f"  Max retries: {args.max_retries}")
    print()

    # ── Phase 4 ──────────────────────────────────────────────────────────────
    if args.start_phase <= 4:
        print("─── Phase 4: Dispatch ───────────────────────────────────────")
        if not run_phase4(repo, feature, model):
            print("\nStopped at phase 4. Fix the issue above and re-run.")
            sys.exit(1)

    # ── Phase 5 → 6 retry loop ───────────────────────────────────────────────
    attempt = 0
    max_attempts = args.max_retries + 1  # first run + N retries
    start_at_5 = args.start_phase <= 5

    while attempt < max_attempts:
        is_retry = attempt > 0

        if start_at_5 or is_retry:
            label = f"Phase 5: Code{'  [retry ' + str(attempt) + '/' + str(args.max_retries) + ']' if is_retry else ''}"
            print(f"─── {label} {'─' * max(0, 47 - len(label))}")
            can_continue, blocked = run_phase5(repo, feature, model)

            if not can_continue:
                # Zero tasks completed — retrying won't help without human input
                print("\nStopped: no tasks completed in phase 5.")
                if blocked:
                    _print_blocked_instructions(repo, feature, blocked)
                sys.exit(1)

            if blocked and not is_retry:
                # Some blocked, some done — warn but continue to QA the done ones
                print()
                _print_blocked_instructions(repo, feature, blocked)
                print("  Continuing to QA on the completed tasks…\n")

        print("─── Phase 6: QA ─────────────────────────────────────────────")
        all_passed, failing = run_phase6(repo, feature, model)

        if all_passed:
            break  # ← success

        attempt += 1
        if attempt >= max_attempts:
            break

        # ── Auto-retry: prep revision dispatch files, then loop ──────────────
        print(f"\n  Auto-retry {attempt}/{args.max_retries}: preparing revision dispatches…")
        for task_id in failing:
            _reset_task_for_revision(repo, feature, task_id)
            print(f"    ↺ {task_id} — dispatch updated with QA review notes")
        print()
        start_at_5 = True  # always run phase 5 on retry iterations

    # ── Final result ─────────────────────────────────────────────────────────
    _, final_failing, _ = _check_qa_results(repo, feature)

    if final_failing:
        print()
        print(f"  Max retries ({args.max_retries}) exhausted. {len(final_failing)} task(s) still failing QA:")
        for task_id in final_failing:
            review = plan_dir / "reviews" / f"{task_id}-review.md"
            print(f"    ✗ {task_id}  — {review.relative_to(repo)}")
        print()
        print("  Manual fix required. Read the review files above, fix the code in")
        print(f"  the worktree at ../{feature}-worktrees/<task-id>/, then re-run:")
        print(f"    uv run python3 scripts/run_loop.py --repo {repo} --feature {feature} --start-phase 6")
        sys.exit(1)

    print()
    print("═══════════════════════════════════════════════════════════════")
    print("  Loop complete — all tasks passed QA.")
    print("  Next: run phase 7 (Consolidate) to merge worktrees.")
    print("═══════════════════════════════════════════════════════════════")


def _print_blocked_instructions(repo: str, feature: str, blocked: list[str]) -> None:
    print("  ── BLOCKED tasks require manual attention ──────────────────")
    for task_id in blocked:
        worktree = Path(repo).parent / f"{feature}-worktrees" / task_id
        dispatch_files = list(
            Path(repo).glob(f"Planning/{feature}/dispatch/**/{task_id}-dispatch.md")
        )
        print(f"  Task: {task_id}")
        if dispatch_files:
            print(f"    Dispatch: {dispatch_files[0].relative_to(repo)}")
        print(f"    Worktree: {worktree}")
    print()
    print("  Options: edit the dispatch prompt, fix the plan, or implement manually.")
    print(f"  Re-run:  uv run python3 scripts/run_loop.py --repo {repo} --feature {feature} --start-phase 5")


if __name__ == "__main__":
    main()
