---
name: dancode-human
description: Dan's standardized methodology: Human Review
trigger: "/dancode-human"
---

Read all files in Planning/<FeatureName>/ and the diff of <feature-branch-name>
against main. If you can't determine the right Feature, ask for clarification.

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