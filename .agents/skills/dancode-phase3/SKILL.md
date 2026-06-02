---
name: dancode-phase3
description: Dan's standardized methodology Phase 3 — Refine. Ensure every plan file has enough explicit detail that a coding model with no memory of this conversation can execute it correctly on the first attempt.
trigger: "/dancode-phase3"
---
Consider all user input and context when refining the plan files.
Read all files under Planning/<FeatureName>/ and apply the following checks.
Edit the plan files in-place. Do not add narrative — only add precision.

1. Every function in "Type Contracts" must have:
   - A one-line docstring written exactly as the coding model should write it
   - All parameter types resolved (no "dict-like" or "see above")
   - A short (3–8 line) usage example if the function is non-trivial

2. Every "Workflow" step must start with a file path in backticks. If a step
   does not reference a specific file, it is too vague — make it specific.

3. Every "Acceptance Criteria" bullet must include a sample assertion:
   assert <thing> == <expected_value>
   or a CLI command + expected output. Remove any bullet that cannot be
   expressed this way.

4. Every "Testing Plan" test must name the file it lives in and include a
   complete function stub (just the def line, docstring, and assert skeleton).
   The coding model will fill in the body.

5. Check for implicit assumptions:
   - Does the plan assume a config key exists? Add the key name and default value.
   - Does the plan assume a directory exists? Add the mkdir call to the workflow.
   - Does the plan assume a prior task ran? Move the dependency to "Overview → depends on".

6. Verify that the README.md execution map is still accurate after any additions.
   Update it if needed.

You may work back and forth with the user to clarify any ambiguities or gather additional details needed to make the plan fully explicit.
