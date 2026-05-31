---
name: dancode-code
description: Dan's standardized methodology for coding
trigger: "/dancode-code"
---

Read the source plan file the user provides. Check the Planning/ directory tree. 
If they don't provide it or you can't find it, 
ask for clarifications. Determine the task ID based on file name or content.

Then:

1. Create a git branch named `FEATURE/<task-id>` based off the current
   branch. If the branch already exists, check it out.

2. Read every file listed in the "Files Changed" section of the plan.
   Do not edit anything yet — understand first.

3. Implement the changes described in the "Workflow" section step by step.
   After each numbered step, stop and verify the change compiles / imports
   cleanly before continuing.

4. Commit with message: "<task-id>: <task title> — initial implementation"

5. Write the tests described in "Testing Plan". Run them. Fix any failures.

6. Commit with message: "<task-id>: <task title> — tests passing"

7. Verify every item in "Acceptance Criteria" is satisfied. For each item,
   output the assertion or command and its result.

8. If any criterion fails, fix it now. Do not move on with a failing criterion.

9. Final commit with message: "<task-id>: <task title> — complete"

Do not proceed to the next task. Stop here and report: DONE or BLOCKED: <reason>.
