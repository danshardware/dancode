---
name: dancode-phase7
description: Dan's standardized methodology Phase 7 — Consolidation. Merge all task branches back into the feature branch cleanly.
trigger: "/dancode-phase7"
---

You are consolidating completed task branches back into the feature branch.

Ensure you know what feature branch and task branches are under review. Ask the user if need be. You can use the execution schedule in `Planning/<feature-name>/` to determine the order.

Task branches to merge (in this order — respect the execution schedule):
<list from Execution Schedule, in dependency order>

For each task branch:
1. Checkout <feature-branch-name>
2. Run: git merge --no-ff <task-branch> -m "Merge <task-id>: <task title>"
3. If there are merge conflicts:
   a. Read both sides of each conflict.
   b. The feature branch is the base — task branch changes take precedence UNLESS
      they conflict with another already-merged task's changes.
   c. Resolve and commit. Do not silently discard either side.
4. Run the tests in full
5. If any test fails, stop and report: MERGE CONFLICT ISSUE: <details>

After all merges:
6. Run the full test suite one final time.
7. Report: CONSOLIDATION COMPLETE or BLOCKED: <reason>
