---
name: dancode-phase1
description: Dan's standardized methodology Phase 1 — Plan. Produce a set of plan files that a low-reasoning coding model can execute mechanically without having to invent anything.
trigger: "/dancode-phase1"
---

See the user's input for what we are trying to build

Read the AGENTS.md at the root of the repo for codebase conventions before proposing anything.

Your job is to come up with a complete specification for the feature or features being discussed and write a detailed plan on how to implement them. This plan will be out of your hands immediately after it's complete and validated by other agents, so it needs to be thorough and document your key assumptions and understanding.

Follow this process strictly — do not skip ahead:

1. Ask me targeted questions in batches of 2-5 about scope, constraints, and goals. Wait for answers before continuing. You may repeat this as much as is needed until your understanding of the problem and solution is crystal clear. Try to use any built-in tooling for presenting questions effectively.

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

**Output:** A `Planning/<FeatureName>/` directory tree saved to disk.
