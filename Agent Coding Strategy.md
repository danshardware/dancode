# Lightweight Agent Coding Strategy

This document is a prompt stack for developing new features using AI coding agents. Work through the phases in order. Phases marked **(reasoning model)** need a capable model (Sonnet, Opus). Phases marked **(coding model)** are designed to be safe for weaker models because the plan does all the thinking for them.

---

## Phase 1 — Plan **(reasoning model)**

**Goal:** Produce a set of plan files that a low-reasoning coding model can execute mechanically without having to invent anything.

**Send this prompt:**

```
We are planning the following feature: $FEATURE_DESCRIPTION

Read the AGENTS.md at the root of the repo for codebase conventions before proposing anything.

Your job is to come up with a complete specification for the fetaure or features being discussed and write a detailed plan on how to implement them. This plan will be out of your hands immediately after it's complete and validated by other agents, so it needs to be thorough and document your key assumptions and understanding.

Follow this process strictly — do not skip ahead:

1. Ask me targeted questions in batches of 2-5 about scope, constraints, and goals. Wait for answers before continuing. You may repeat this as much as is needed until your understanding of the problem and soution is crystal clear.

2. Draft an outline of what tracks of work need to happen. A track is a sequence of tasks that must run one-after-the-other. Multiple tracks may run in parallel if they have no shared files. Present the tracks, explain the parallelism, and ask me to confirm before writing anything.

3. Write the plan. Each track gets a directory. Each task in a track gets a numbered markdown file. Use this file structure:

   Planning/<FeatureName>/
     README.md                   ← execution map and dependency summary
     Track-A-<short-name>/
       A1-<task-slug>.md
       A2-<task-slug>.md
     Track-B-<short-name>/
       B1-<task-slug>.md
   
   Tracks may be nested up to 5 levels deep if a parallel group only unlocks after
   a specific earlier task completes. Make the nesting explicit in README.md.

4. Each task file MUST contain all of these sections — no exceptions:

   ## Overview
   One paragraph. What this task does, why it exists, which file(s) it touches.
   State what must already be done before this task starts (upstream dependencies).
   Document Key assumptions and design intent.

   ## Files Changed
   Bullet list: path → what changes (new file | modified | deleted).

   ## Type Contracts
   Exact function/class signatures for anything new or changed. Include:
   - Parameter names and types
   - Return type
   - Any mutations to shared state or files (written as: `shared["key"] → value`)
   No hand-waving. If a function is non-trivial, include a short usage example.

   ## Workflow
   Numbered step-by-step implementation instructions. Each step must be a single
   concrete action (not "implement the logic" — say what the logic IS).
   Include code snippets wherever a coding model could get it wrong.

   ## Acceptance Criteria
   Bullet list of testable, binary pass/fail checks. Every criterion must be
   observable without running the full system (check a file, run a test, assert
   a return value). No subjective criteria ("works correctly", "looks right").

   ## Testing Plan
   Exact test function names, what they assert, and representative input/output
   values. If the test requires a real AWS call, say so. If it can use a 
   fake/fixture, provide the fixture.
```

**Output:** A `Planning/<FeatureName>/` directory tree saved to disk.

---

## Phase 2 — Jank Control **(reasoning model)**

**Goal:** Find every place where a low-reasoning coding model could take a lazy shortcut, game tests, or produce technically-passing code that causes long-term problems.

**Send this prompt:**

```
Read all files under Planning/<FeatureName>/ and audit them for implementation risk.

You are looking for these specific failure modes — check each one explicitly:

### Lazy Stub Risk
Flag any task that could be "satisfied" by a function that returns a hardcoded value
or raises NotImplementedError. If the acceptance criteria can be passed by a stub,
rewrite the criteria so they can't.

### Test Gaming Risk
Flag any test that passes if the implementation does nothing (e.g. an empty function
returning None would pass). Flag tests that only check the return value but not the
side effect, or vice versa. Flag tests that could pass on mocks but fail on real code.
For each: propose a concrete test that can't be gamed.

### Self-Sabotage Risk
Flag tasks where the described approach would break existing functionality. Check:
- Does this task import from or modify a file that another parallel track also modifies?
- Does any type contract break an existing call site?
- Does any new function shadow or replace an existing one with a different signature?
- Will the new function limit how the code is eventually deployed or greatly limit 
   functional options when deployed (examples: Require on-disk storage while everything
   else is remote object storage, or adds a new DB technology that would complicate
   deployment)

### Convention Violations
Check against AGENTS.md conventions:
- Tools must return str, last param must be context: ToolContext
- Engine modules must start with `from __future__ import annotations`
- Imports of heavy deps (boto3, requests) must be inside functions, not at module top
- Error handling: tools return "[ERROR] ..." strings, not raise
- File paths touching data/ must go through _assert_path_allowed

### Missing Explicitness
Flag any step that says "implement X" without saying what X looks like. The coding
model has no reasoning. If the plan says "validate the input", it MUST also say
exactly what valid looks like, what the error message is, and which code path fires.

### Long-Term Debt Risk
Flag any instruction that defers a real problem (TODO, placeholder, hardcoded limit,
copy-paste of an existing block with "adjust as needed"). It must either specify 
how to arrive at the stable value or make it a documented configuration variable.

For each flag: output a block with:
  RISK: <category>
  LOCATION: <file> → <section>
  PROBLEM: one sentence
  FIX: concrete edit to apply to the plan file

After listing all risks, apply every FIX directly to the relevant plan files.
```

---

## Phase 3 — Refine **(reasoning model)**

**Goal:** Ensure every plan file has enough explicit detail that a coding model with no memory of this conversation can execute it correctly on the first attempt.

**Send this prompt:**

```
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
```

---

## Phase 4 — Dispatch **(produces human-readable output)**

**Goal:** Produce one prompt per task file that a coding model can be handed directly, plus a plain-English execution schedule for the human.

**Send this prompt:**

```
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

5. Repeat steps 3 and 4 until all "Aceeptence Criteria" is satisfied. For 
   each item, output the assertion or command and its result. If any criterion
   fails, fix it now. Do not move on with a failing criterion.

6. Commit with message: "<task-id>: <task title> — <one-line decription of what was done>"   

7. Final commit with message: "<task-id>: <task title> — complete"

Do not proceed to the next task. Stop here and report: DONE or BLOCKED: <reason>.
---

After generating all dispatch prompts, output a human-readable execution schedule:

## Execution Schedule

Create the following git worktrees:

- `git worktree create -b "<featurename>-track-<track designation>" /path/to/worktrees/track-<designation>`
- `git worktree create -b "<featurename>-track-<track designation>" /path/to/worktrees/track-<designation>`
- `git worktree create -b "<featurename>-track-<track designation>" /path/to/worktrees/track-<designation>`

Run these in parallel (no shared files):
  Track A: A1 → A2 → A3
  Track B: B1 → B2

After all above complete, run:
  Track C: C1 → C2

[Continue for each dependency level]

Total estimated tasks: N
```

---

## Phase 5 — QA **(coding model or reasoning model, per change)**

**Goal:** Independently verify that the code produced matches the plan, follows standards, and cannot be passed by a fake implementation.

**Send this prompt for each completed task branch:**

```
You are a code reviewer. You have no stake in whether this code passes — your job
is to find real problems.

Branch under review: <feature-slug>/<task-id>
Source plan: Planning/<FeatureName>/<track>/<task-file>.md

Read the plan file. Read every file listed in "Files Changed" 
on the branch and check the files changed in git.
Then work through each check below and report your finding for each.

--- PRIOR REVIEW CHECK ---
Check Planning/<FeatureName>/reviews/ for any earlier review files for this task-id.
If any exist:
  - List every FAIL and PASS WITH NOTES item from each prior review.
  - For each prior issue, determine whether the current code addresses it.
  - Mark each as: RESOLVED / STILL PRESENT / REGRESSION (was fixed, now broken again).
  - If any issue is STILL PRESENT or is a REGRESSION, it is automatically a FAIL in the verdict below.
  - If no prior reviews exist, state "No prior reviews found" and continue.

--- STANDARDS CHECK ---
1. Type hints: every new or modified function has full type annotations. Yes/No + missing list.
2. Docstrings: every public function has a PEP 257 docstring. Yes/No + missing list.
3. `from __future__ import annotations` present at top of every engine/ or tools/ file changed. Yes/No.
4. Heavy imports (boto3, requests, chromadb) are inside functions, not at module top. Yes/No + violations.
5. Tools return str (or dict if JSON output is explicit intent). Yes/No + violations.
6. Tools have `context: ToolContext` as last parameter. Yes/No + violations.
7. File-accessing tools call `_assert_path_allowed` before any read/write. Yes/No + violations.
8. Tools return "[ERROR] ..." strings on failure — they do not raise. Yes/No + violations.

--- ACCEPTANCE CRITERIA CHECK ---
For each criterion in the plan's "Acceptance Criteria":
  State the criterion → PASS / FAIL / CANNOT VERIFY (explain why)

--- TEST INTEGRITY CHECK ---
For each test in the plan's "Testing Plan":
  - Does the test exist at the named file and function? Yes/No.
  - Would a stub implementation (returning None or a hardcoded value) pass this test? Yes/No + explain.
  - Does the test assert on the actual side effect (file written, message appended, etc.)? Yes/No.
  - Run the test mentally: given the implementation, does it actually pass? Yes/No.

--- SCOPE CHECK ---
9. Does the code change any file NOT listed in "Files Changed"? If yes, list them.
10. Does the implementation match the "Type Contracts" exactly (same signature, same mutations)? Yes/No + diffs.
11. Any hardcoded values, magic numbers, or TODO markers? List them.
12. Any copy-pasted code blocks that could be a shared function? List them.

--- VERDICT ---
PASS — all checks clear, no action required.
PASS WITH NOTES — minor issues, acceptable to merge after noting.
FAIL — list blocking issues.

Save this review to: Planning/<FeatureName>/reviews/<task-id>-review.md
```

---

## Phase 6 — Revise **(coding model)**

**Goal:** Give the coding agent a precise, actionable fix list based on the QA review. No ambiguity.

**Send this prompt for each FAIL or PASS WITH NOTES review:**

```
Read: Planning/<FeatureName>/reviews/<task-id>-review.md
Branch: <feature-slug>/<task-id>

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
```

---

## Phase 7 — Consolidation **(coding model)**

**Goal:** Merge all task branches back into the feature branch cleanly.

**Send this prompt after all tasks in a track are QA-passed:**

```
You are consolidating completed task branches back into the feature branch.

Feature branch: <feature-branch-name>
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
4. Run: uv run pytest tests/ -v
5. If any test fails, stop and report: MERGE CONFLICT ISSUE: <details>

After all merges:
6. Run the full test suite one final time.
7. Report: CONSOLIDATION COMPLETE or BLOCKED: <reason>
```

---

## Phase 8 — Human Review **(produces human-readable output)**

**Goal:** Give the human a clear summary of what changed, why, and how to validate it manually.

**Send this prompt:**

```
Read all files in Planning/<FeatureName>/ and the diff of <feature-branch-name> against main.

Produce a human review document at: Planning/<FeatureName>/REVIEW.md

The document must contain:

## What Changed
For each task (in execution order):
  ### <task-id>: <task title>
  - Files modified: <list>
  - What it does in one plain sentence.
  - Before / After: show the key code change (not the full diff, just the important part).

## How to Validate Manually
A numbered list of steps a non-technical reviewer can follow to confirm the feature
works correctly in a running system. Use real CLI commands and expected outputs.
Example:
  1. Run: uv run run.py --agent concierge --prompt "Hello"
     Expected: agent responds without error, session log appears at data/logs/concierge/*.jsonl

## Known Limitations
Anything the implementation intentionally does not handle, and why.

## Test Coverage Summary
List each test file touched and what it covers.
```

---

## Phase 9 — Documentation Update **(reasoning model)**

**Goal:** Keep the project docs accurate after the feature lands.

**Send this prompt:**

```
The following feature has been implemented: <feature branch name>

Read these documents:
- AGENTS.md
- docs/project-onboarding.md
- docs/how-to-add-tools.md
- docs/how-to-create-agents.md
- Any other .md files under docs/

Read the review document at: Planning/<FeatureName>/REVIEW.md

For each document:
1. Identify any section that describes behaviour that this feature changed.
2. Identify any new capability (new tool, new block type, new config key, new agent)
   that is not yet mentioned in the docs.
3. Identify any warning or limitation in the docs that this feature resolves.

For each identified issue, make the minimum edit to the doc that makes it accurate.
Rules:
- Do not restructure sections that are not affected.
- Do not add examples unless an existing section already has examples.
- Do not add new top-level sections unless the feature introduces a genuinely new concept
  with no home in the existing structure.
- Update tables (tool reference, block type reference) by adding/editing rows only.

After editing, list every file you changed and summarise what you updated in each.
```

---

## Phase 10 — Finalization **(coding model)**

**Goal:** Land the feature branch on main cleanly with no commit history.

**Send this prompt:**

```
You are finalising feature branch: <feature-branch-name>

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
```