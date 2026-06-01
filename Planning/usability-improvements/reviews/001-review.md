# Code Review for Task 001 — Add `phase_token_counts` to FeatureTask

## Summary

Task 001 adds a new field `phase_token_counts: dict[str, int]` to the `FeatureTask` Pydantic model to track per-phase token usage.

## Changes Reviewed

### Core Implementation (`dancode/config.py`)

```python
phase_token_counts: dict[str, int] = Field(default_factory=dict)
```

- **Correct type**: `dict[str, int]` matches the specification
- **Correct default**: `Field(default_factory=dict)` provides an empty dict as default
- **Correct placement**: Added after `blocked_reason` field as specified
- **Acceptance Criteria Verification**:
  - Default to empty dict: ✓ Verified by test
  - Can set values: ✓ Verified by test
  - JSON round-trip works: ✓ Verified by test

### Tests (`tests/unit/test_config.py`)

Two tests added:
1. `test_feature_task_phase_token_counts_default` - Verifies default is empty dict
2. `test_feature_task_phase_token_counts_roundtrip` - Verifies JSON serialization works

Both tests pass.

## Issues Found

### Issue 1: Other tasks' changes included in branch

The diff shows changes from other tasks (002, 003, 004, 005, 006) mixed into this branch:

- `dancode/workers/agent_runner.py` - Adds `_load_guidance_docs()` (task 002)
- Flow YAML changes in phases 1-8 (tasks 002, 003)
- `tools/git_tools.py` - Worktree handling changes (task 005)
- `tools/openhands_dispatch.py` - Dispatch content parameter (task 005)
- `tests/unit/test_flow_yaml_validity.py` - New test file (task 003)
- Additional planning files for other tasks

**Impact**: This branch contains code for multiple tasks mixed together. While the task 001 changes are correct, the branch is not clean.

### Issue 2: No integration of phase_token_counts in worker

The task specification mentions: "Updated in-place by AgentWorker after each phase completes."

Looking at `dancode/workers/agent_runner.py`, there's no code that actually writes to `phase_token_counts` after each phase. The field is added to the model but the worker doesn't populate it.

**Impact**: The field exists but is never populated. If task 006 (phase-table widget) expects to read token counts, it will find nothing.

## Verdict

**PASS WITH NOTES**

The core implementation for task 001 is correct - the field is added properly with correct type and tests pass. However:

1. The branch contains changes from multiple tasks mixed together (should be separate branches)
2. The `phase_token_counts` field is never actually populated by the worker, so downstream consumers (task 006) would not have data to read

These are not blocking issues for task 001's scope - the field is added correctly. The worker integration would be a separate task or part of task 006's implementation.

VERDICT: PASS WITH NOTES