---
name: dancode-phase8
description: Dan's standardized methodology Phase 8 — Human Review. Give the human a clear summary of what changed, why, and how to validate it manually.
trigger: "/dancode-phase8"
---

Ensure you know which feature branch and task branches are under review. Ask the user if need be.
Read all files in Planning/<FeatureName>/ and the diff of <feature-branch-name> against main or the bracnh the user tells you we are merging into.

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
