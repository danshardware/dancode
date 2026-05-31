---
name: dancode-consolidate
description: Dan's standardized methodology: consolidate completed task branches back into the feature branch
trigger: "/dancode-consolidate"
---
You are consolidating completed task branches back into the feature branch.

Check the user input and the Planning/ directory tree to determine which 
feature and task branches are ready for consolidation. 
You should have a list of task branches in the order they should be merged, 
based on the git history.

For each task branch:
1. Checkout <feature-branch-name>
2. Run: git merge --no-ff <task-branch> -m "Merge <task-id>: <task title>"
3. If there are merge conflicts:
   a. Read both sides of each conflict.
   b. The feature branch is the base — task branch changes take precedence UNLESS
      they conflict with another already-merged task's changes.
   c. Resolve and commit. Do not silently discard either side.

After all merges:
1. After merging, run the full test suite for the feature: uv run pytest tests/ -v
2. Report: CONSOLIDATION COMPLETE or BLOCKED: <reason>
3. Suggest the user run the dancode-docs skill to update the documentation for the feature, if needed.
