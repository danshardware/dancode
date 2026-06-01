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
import subprocess
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


def _parse_schedule_by_track(repo: str, feature: str) -> dict[str, list[dict]]:
    """Parse SCHEDULE.md and return tasks grouped by track name.

    Looks for SCHEDULE.md in the main repo first, then in per-track worktrees.
    Dispatch file paths in the returned dict are absolute paths pointing to
    whichever location the SCHEDULE.md was found in.
    """
    from collections import OrderedDict
    tracks: dict[str, list[dict]] = OrderedDict()
    seen_tasks: set[str] = set()

    # Candidate SCHEDULE.md locations: main repo + all track worktrees
    candidates = [Path(repo) / "Planning" / feature / "dispatch" / "SCHEDULE.md"]
    worktrees_dir = Path(repo).parent / f"{feature}-worktrees"
    if worktrees_dir.exists():
        candidates += sorted(
            worktrees_dir.glob(f"*/Planning/{feature}/dispatch/SCHEDULE.md")
        )

    for schedule_file in candidates:
        if not schedule_file.exists():
            continue
        # root is the repo/worktree root containing this SCHEDULE.md
        root = schedule_file.parent.parent.parent.parent
        content = schedule_file.read_text()
        for m in re.finditer(r"-\s+Task\s+([\w-]+):\s+(dispatch/[\w./-]+)", content):
            task_id = m.group(1)
            if task_id in seen_tasks:
                continue
            seen_tasks.add(task_id)
            rel_path = m.group(2)           # e.g. "dispatch/track-a/001-foo.md"
            abs_dispatch = str(root / "Planning" / feature / rel_path)
            parts = rel_path.split("/")
            track_name = parts[1] if len(parts) >= 3 else "track-a"
            tracks.setdefault(track_name, []).append({
                "task_id": task_id,
                "dispatch_file": abs_dispatch,
            })
    return tracks


def _ensure_track_worktree(repo: str, feature: str, track_name: str) -> str:
    """Return the worktree path for a track branch, creating it if needed.

    Branch: <feature>-<track_name>  e.g. usability-improvements-track-a
    Dest:   <repo>/../<feature>-worktrees/<track_name>/
    """
    branch = f"{feature}-{track_name}"
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo, capture_output=True, text=True,
    )
    current = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current = line[9:]
        elif line.startswith("branch ") and line[7:].removeprefix("refs/heads/") == branch:
            return current  # already checked out — return existing path

    dest = Path(repo).parent / f"{feature}-worktrees" / track_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    rc = subprocess.run(["git", "rev-parse", "--verify", branch],
                        cwd=repo, capture_output=True).returncode
    if rc == 0:
        r = subprocess.run(["git", "worktree", "add", str(dest), branch],
                           cwd=repo, capture_output=True, text=True)
    else:
        r = subprocess.run(["git", "worktree", "add", "-b", branch, str(dest)],
                           cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {r.stderr.strip()}")
    return str(dest)


def _git_commit(worktree: str, message: str) -> bool:
    """Stage all changes and commit. Returns True if a commit was made."""
    subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True)
    r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=worktree, capture_output=True)
    if r.returncode == 0:
        return False  # nothing staged
    r = subprocess.run(["git", "commit", "-m", message], cwd=worktree, capture_output=True)
    return r.returncode == 0


def _run_openhands(worktree: str, model_id: str,
                   dispatch_file: str = "", dispatch_content: str = "") -> bool:
    """Run OpenHands headless in worktree. Returns True on clean exit."""
    wt = Path(worktree)
    if dispatch_content:
        df = wt / ".openhands-dispatch.md"
        df.write_text(dispatch_content)
        dispatch_path = str(df)
    else:
        dispatch_path = dispatch_file

    litellm_model = model_id if model_id.startswith("bedrock/") else f"bedrock/{model_id}"
    env = os.environ.copy()
    env["LLM_MODEL"] = litellm_model
    env.setdefault("LLM_API_KEY", "bedrock")

    cmd = ["openhands", "--headless", "--json", "--always-approve",
           "--override-with-envs", "-f", dispatch_path]
    r = subprocess.run(cmd, cwd=str(wt), env=env)
    return r.returncode == 0


def _get_verdict(review_path: Path) -> str:
    """Return 'PASS', 'FAIL', or '' if no verdict found."""
    if not review_path.exists() or not review_path.stat().st_size:
        return ""
    content = review_path.read_text()
    if re.search(r"VERDICT:\s*PASS", content, re.IGNORECASE):
        return "PASS"
    if re.search(r"VERDICT:\s*FAIL", content, re.IGNORECASE):
        return "FAIL"
    return ""


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


def run_phase5(repo: str, feature: str, openhands_model: str,
               max_qa_retries: int = 3) -> tuple[bool, list[str]]:
    """
    Per-track, per-task: create one worktree per track, then for each task:
      1. Check dispatch file exists.
      2. Run code (OpenHands) → commit.
      3. Run QA (OpenHands) → commit.
      4. Check verdict: if PASS → done; if FAIL → retry up to max_qa_retries.
      5. Copy review from worktree to main repo; record status.

    Returns (can_continue, blocked_tasks).
    """
    tracks = _parse_schedule_by_track(repo, feature)
    if not tracks:
        print("  [phase 5] ERROR: no tasks found in SCHEDULE.md")
        return False, []

    done_tasks: list[str] = []
    blocked_tasks: list[str] = []
    plan_dir = Path(repo) / "Planning" / feature

    for track_name, tasks in tracks.items():
        print(f"\n  [phase 5] Track: {track_name} ({len(tasks)} task(s))")

        # One worktree for the whole track
        try:
            worktree = _ensure_track_worktree(repo, feature, track_name)
        except RuntimeError as e:
            print(f"  [phase 5] ✗ {track_name}: worktree creation failed: {e}")
            for t in tasks:
                blocked_tasks.append(t["task_id"])
                _write_task_status(plan_dir, t["task_id"],
                                   "BLOCKED: track worktree failed")
            continue

        print(f"  [phase 5]   worktree: {worktree}")

        for task in tasks:
            task_id = task["task_id"]
            dispatch_file = task["dispatch_file"]

            if not Path(dispatch_file).exists():
                print(f"  [phase 5] ✗ {task_id}: dispatch file not found: {dispatch_file}")
                blocked_tasks.append(task_id)
                _write_task_status(plan_dir, task_id, "BLOCKED: dispatch file not found")
                continue

            # Reviews live in BOTH the worktree (committed) and main repo (untracked)
            main_review = plan_dir / "reviews" / f"{task_id}-review.md"
            wt_review = (Path(worktree) / "Planning" / feature
                         / "reviews" / f"{task_id}-review.md")

            # Sync review from worktree to main repo if needed
            if not main_review.exists() and wt_review.exists():
                main_review.parent.mkdir(parents=True, exist_ok=True)
                main_review.write_text(wt_review.read_text())

            # Skip if already PASS from a previous run
            if _get_verdict(main_review) == "PASS":
                print(f"  [phase 5] [{task_id}] already PASS — skipping")
                done_tasks.append(task_id)
                _write_task_status(plan_dir, task_id, "DONE")
                continue

            # dispatch_file may point to the main repo OR a worktree;
            # normalise to worktree path for QA prompt.
            wt = Path(worktree)
            disp = Path(dispatch_file)
            try:
                wt_dispatch_file = wt / disp.relative_to(wt)
            except ValueError:
                try:
                    wt_dispatch_file = wt / disp.relative_to(Path(repo))
                except ValueError:
                    wt_dispatch_file = disp  # fallback: use as-is

            verdict = ""
            for attempt in range(max_qa_retries + 1):
                retry_label = f" (retry {attempt}/{max_qa_retries})" if attempt else ""

                # ── Code ────────────────────────────────────────────────────
                print(f"  [phase 5] [{task_id}] coding{retry_label}…")
                # Read dispatch content and prepend branch-safety override so
                # OpenHands does NOT create or switch branches.
                raw_dispatch = Path(dispatch_file).read_text()
                safe_dispatch = (
                    "CRITICAL OVERRIDE: You are working inside a git worktree.\n"
                    "Do NOT run 'git checkout', 'git switch', or 'git branch' to "
                    "create or switch branches.\n"
                    "Work directly on the current branch for ALL commits.\n"
                    "Ignore any numbered step that says to create or check out a "
                    "branch named FEATURE/... — replace it with: commit directly "
                    "to the current branch.\n\n"
                    + raw_dispatch
                )
                _run_openhands(worktree, openhands_model, dispatch_content=safe_dispatch)
                committed = _git_commit(worktree, f"task {task_id}: code attempt {attempt + 1}")
                if committed:
                    print(f"  [phase 5] [{task_id}] committed code changes")

                # ── QA ──────────────────────────────────────────────────────
                print(f"  [phase 5] [{task_id}] QA review{retry_label}…")
                # Show all code changes since main, listing only code dirs
                # (exclusion pathspecs are unreliable across git versions)
                diff_cmd = (
                    "git diff $(git merge-base HEAD main 2>/dev/null "
                    "|| git rev-parse HEAD~5) HEAD "
                    "-- dancode/ tests/ flows/ tools/ engine/ agents/"
                )
                qa_prompt = (
                    f"Review the code changes in this repository for task {task_id}.\n"
                    f"1. Run: git log --oneline -10\n"
                    f"2. Run: {diff_cmd}\n"
                    f"   (shows all code changes since branching from main)\n"
                    f"3. Read the task spec at: {wt_dispatch_file}\n"
                    f"4. Write your complete review to this exact absolute path:\n"
                    f"   {wt_review}\n"
                    f"   (create parent directories if needed)\n"
                    f"End the review file with EXACTLY ONE of:\n"
                    f"VERDICT: PASS\n"
                    f"VERDICT: PASS WITH NOTES\n"
                    f"VERDICT: FAIL\n"
                    f"(If FAIL, list each blocking issue starting with '- ')\n"
                )
                _run_openhands(worktree, openhands_model, dispatch_content=qa_prompt)
                committed = _git_commit(worktree, f"task {task_id}: QA review attempt {attempt + 1}")
                if committed:
                    print(f"  [phase 5] [{task_id}] committed QA review")

                # OpenHands writes review to wt_review (worktree path);
                # sync to main_review so _check_qa_results can find it.
                if wt_review.exists() and wt_review.stat().st_size:
                    main_review.parent.mkdir(parents=True, exist_ok=True)
                    main_review.write_text(wt_review.read_text())

                verdict = _get_verdict(main_review) or _get_verdict(wt_review)
                if verdict == "PASS":
                    break
                if attempt < max_qa_retries:
                    print(f"  [phase 5] [{task_id}] QA {verdict or 'no verdict'} — retrying…")

            # ── Ensure review is synced to main repo ──────────────────────
            if wt_review.exists() and wt_review.stat().st_size:
                main_review.parent.mkdir(parents=True, exist_ok=True)
                main_review.write_text(wt_review.read_text())

            # ── Record status ────────────────────────────────────────────
            if verdict == "PASS":
                _write_task_status(plan_dir, task_id, "DONE")
                done_tasks.append(task_id)
                print(f"  [phase 5] [{task_id}] DONE")
            else:
                reason = f"QA {verdict}" if verdict else "no verdict in review"
                _write_task_status(plan_dir, task_id, f"BLOCKED: {reason}")
                blocked_tasks.append(task_id)
                print(f"  [phase 5] [{task_id}] BLOCKED: {reason}")

    if blocked_tasks:
        print(f"\n  [phase 5] BLOCKED: {', '.join(blocked_tasks)}")
    if done_tasks:
        print(f"  [phase 5] DONE:    {', '.join(done_tasks)}")
        return True, blocked_tasks

    print("  [phase 5] No tasks completed.")
    return False, blocked_tasks


def _write_task_status(plan_dir: Path, task_id: str, status: str) -> None:
    """Append or update a task status line in phase5_status.md."""
    status_file = plan_dir / "phase5_status.md"
    existing = status_file.read_text() if status_file.exists() else ""
    lines = [l for l in existing.splitlines() if not re.match(rf"^\s*{re.escape(task_id)}\s", l)]
    lines.append(f"{task_id}  {status}")
    status_file.write_text("\n".join(lines) + "\n")


def run_phase6(repo: str, feature: str, openhands_model: str) -> tuple[bool, list[str]]:
    """Generate the QA summary report from reviews written by phase 5.
    Returns (all_passed, failing_tasks).
    """
    print("  Running phase 6 (QA report)…")
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
        description="Run the phase 4→5→6 code loop."
    )
    parser.add_argument("--repo", required=True, help="Absolute path to the target git repo")
    parser.add_argument("--feature", required=True, help="Feature name (matches Planning/<feature>/)")
    parser.add_argument(
        "--start-phase", type=int, default=4, choices=[4, 5, 6], metavar="{4,5,6}",
        help="Resume from this phase (default: 4)",
    )
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Max code→QA retries per task (default: 3)",
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
    print(f"  Max retries: {args.max_retries} per task")
    print()

    # ── Phase 4 ──────────────────────────────────────────────────────────────
    if args.start_phase <= 4:
        print("─── Phase 4: Dispatch ───────────────────────────────────────")
        if not run_phase4(repo, feature, model):
            print("\nStopped at phase 4. Fix the issue above and re-run.")
            sys.exit(1)

    # ── Phase 5: code + QA per task (retries inline) ─────────────────────────
    if args.start_phase <= 5:
        print("─── Phase 5: Code + QA ──────────────────────────────────────")
        can_continue, blocked = run_phase5(repo, feature, model,
                                           max_qa_retries=args.max_retries)
        if not can_continue:
            print("\nStopped: no tasks completed in phase 5.")
            if blocked:
                _print_blocked_instructions(repo, feature, blocked)
            sys.exit(1)
        if blocked:
            print()
            _print_blocked_instructions(repo, feature, blocked)

    # ── Phase 6: QA summary report ────────────────────────────────────────────
    print("─── Phase 6: QA Report ──────────────────────────────────────")
    all_passed, failing = run_phase6(repo, feature, model)

    # ── Final result ──────────────────────────────────────────────────────────
    if failing:
        print()
        print(f"  {len(failing)} task(s) failed QA:")
        for task_id in failing:
            review = plan_dir / "reviews" / f"{task_id}-review.md"
            print(f"    ✗ {task_id}  — {review.relative_to(repo)}")
        print()
        print("  Manual fix required. Read the review files above, fix the code")
        print(f"  in the track worktree, then re-run with --start-phase 6.")
        sys.exit(1)

    print()
    print("═══════════════════════════════════════════════════════════════")
    print("  Loop complete — all tasks passed QA.")
    print("  Next: run phase 7 (Consolidate) to merge worktrees.")
    print("═══════════════════════════════════════════════════════════════")


def _print_blocked_instructions(repo: str, feature: str, blocked: list[str]) -> None:
    print("  ── BLOCKED tasks require manual attention ──────────────────")
    for task_id in blocked:
        dispatch_files = list(
            Path(repo).glob(f"Planning/{feature}/dispatch/**/{task_id}-*.md")
        )
        print(f"  Task: {task_id}")
        if dispatch_files:
            print(f"    Dispatch: {dispatch_files[0].relative_to(repo)}")
    print()
    print("  Options: edit the dispatch prompt, fix the plan, or implement manually.")
    print(f"  Worktrees are at: {Path(repo).parent / (feature + '-worktrees')}/")
    print(f"  Re-run: uv run python3 scripts/run_loop.py --repo {repo} --feature {feature} --start-phase 5")


if __name__ == "__main__":
    main()
