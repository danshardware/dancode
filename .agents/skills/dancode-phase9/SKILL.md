---
name: dancode-phase9
description: Dan's standardized methodology Phase 9 — Documentation Update. Keep the project docs accurate after the feature lands.
trigger: "/dancode-phase9"
---

The following feature has been implemented: <feature branch name>

Read these documents:
- AGENTS.md
- Any other .md files under docs/
- Any README.md files that would be affected by this feature

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
