---
name: dancode-phase2
description: Dan's standardized methodology Phase 2 — Jank Control. Find every place where a low-reasoning coding model could take a lazy shortcut, game tests, or produce technically-passing code that causes long-term problems.
trigger: "/dancode-phase2"
---

Read all files under Planning/<FeatureName>/ and audit them for implementation risk.

Consider any input from the user when auditing the plan files.

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
Check against AGENTS.md and CONSTITUTION.md for coding conventions or non-negotiable rules

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
