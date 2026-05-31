---
name: dancode-docs
description: Dan's standardized methodology: update documentation for the feature
trigger: "/dancode-docs"
---

Determine the feature that has been developed from human input or git
history. Check the Planning/ directory tree for the feature specification 
and review files.
If they don't provide it or you can't find it, ask for clarifications.

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
