---
name: dancode-finish
description: Dan's standardized methodology: finish the feature branch and prepare for release
trigger: "/dancode-finish"
---

Check the user input and the Planning/ directory tree to determine which 
feature and task branches are ready for consolidation. 
You should have a list of task branches in the order they should be merged, 
based on the git history.

Steps:

1. Checkout <feature-branch-name>. Confirm you are on it.

2. Run the full test suite: uv run pytest tests/ -v
   All tests must pass. If any fail, stop and report: BLOCKED: <test name and error>.

3. Check for any uncommitted changes: git status
   If any exist, review them. If they are leftover debug code or scratch files, remove them.
   If they are real changes, commit them with an appropriate message before continuing.

4. Prepare the squash commit message:
   a. Run: git log main..<feature-branch-name> --oneline
   b. Read Planning/<FeatureName>/REVIEW.md for the "What Changed" summary.
   c. Compose a commit message in this format and print it for human review:
      <short imperative title, max 72 chars>
      
      <What this feature does in 2–4 sentences. No jargon.>
      
      Changes:
      - <task-id>: <one-line summary>
      - <task-id>: <one-line summary>
      [one line per task]
      
      Tests: <number> tests added/modified, all passing.

5. Check if a version number exists in pyproject.toml under [project] version.
   If it does, increment the patch version (e.g. 0.1.0 → 0.1.1) unless the feature
   adds a new user-facing capability, in which case increment minor (0.1.0 → 0.2.0).
   Commit the version bump separately: "chore: bump version to X.Y.Z"

6. Do NOT push or merge to main yourself. Output the composed commit message and
   the exact commands the human should run to land it:

   git checkout main
   git merge --squash <feature-branch-name>
   git commit -m "<composed message above>"
   git push origin main

   Then stop and report: READY FOR MERGE.