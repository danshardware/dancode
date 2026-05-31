---
name: dancode-revise
description: Dan's standardized methodology: fix yo shit
trigger: "/dancode-revise"
---
Find the feature specification and review files. Check the Planning/ directory tree.
If they don't provide it or you can't find it, 
ask for clarifications. Determine the task ID based on file name or content.

Read: Planning/<FeatureName>/reviews/<task-id>-review.md

You are fixing the issues identified in the review above. Work through each
FAIL item in order. For each:

1. Read the specific file and line(s) cited.
2. Make only the change described. Do not refactor anything else.
3. After each fix, run the relevant test from the "Testing Plan" section of the
   source plan. If it passes, move on. If it fails, fix the test failure before
   moving to the next issue.

After all FAIL items are addressed:
4. Re-run the full test suite for this module: uv run pytest tests/ -k "<relevant test file stem>" -v
5. If any test that was previously passing is now failing, fix it. Do not delete tests.
6. Commit: "<task-id>: address review findings"

Do not close the task or merge anything. Report: RESOLVED or STILL BLOCKED: <reason>.