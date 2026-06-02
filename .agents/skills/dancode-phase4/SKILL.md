---
name: dancode-phase4
description: Dan's standardized methodology Phase 4 — Dispatch. Produce one prompt per task file that a coding model can be handed directly, plus a plain-English execution schedule for the human.
trigger: "/dancode-phase4"
---

Read Planning/<FeatureName>/README.md and all task files.

For each task file, produce a self-contained dispatch prompt. Write each prompt to:
  Planning/<FeatureName>/dispatch/<track>/<task-id>-dispatch.md

Each dispatch prompt must contain exactly:

---
TASK: <task file title>
SOURCE PLAN: Planning/<FeatureName>/<track>/<task-file>.md
---

Read the source plan file listed above. Then:

1. Read every file listed in the "Files Changed" section of the plan.
   Do not edit anything yet — understand first.

2. Write the tests described in "Testing Plan". Run them. Ensure 
   they run and fail due to lack of implementation. You may add stubs in the places
   stated in the Workflow Section of the plan so to avoid errors, but write 
   no additional code.

3. Implement the changes described in the "Workflow" section step by step.
   After each numbered step, stop and verify the change compiles / imports
   cleanly before continuing.

4. Run the tests and ensure the one you have worked on are now passing.
   Fix issues as necessary, but ensure you are not modifying tests so they
   pass under looser criteria.

5. Repeat steps 3 and 4 until all "Acceptance Criteria" is satisfied. For 
   each item, output the assertion or command and its result. If any criterion
   fails, fix it now. Do not move on with a failing criterion.

6. Commit with message: "<task-id>: <task title> — <one-line description of what was done>"

7. Final commit with message: "<task-id>: <task title> — complete"

Do not proceed to the next task. Stop here and report: DONE or BLOCKED: <reason>.
---

After generating all dispatch prompts, output a human-readable execution schedule:

## Execution Schedule

Create the following git worktrees:

- `git worktree add -b "<featurename>-track-<track designation>" /path/to/worktrees/track-<designation>`
- `git worktree add -b "<featurename>-track-<track designation>" /path/to/worktrees/track-<designation>`
- `git worktree add -b "<featurename>-track-<track designation>" /path/to/worktrees/track-<designation>`

Run these in parallel (no shared files):
  Track A: A1 → A2 → A3
  Track B: B1 → B2

After all above complete, run:
  Track C: C1 → C2

[Continue for each dependency level]

Total estimated tasks: N
