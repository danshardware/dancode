# Task 001 — Add `phase_token_counts` to FeatureTask

**Track A — can run in parallel with 002 and 003**

## Overview

`FeatureTask` currently has no field for tracking per-phase token usage.
The phase-table widget (task 006) reads per-phase token counts from the task model.
The worker (task 006 also) writes to this field after each phase completes.

This task adds the field so that 004, 005, and 006 can all reference it without
stepping on each other.

## Files Changed

- `dancode/config.py`

## Type Contracts

```python
class FeatureTask(BaseModel):
    # ... existing fields unchanged ...
    phase_token_counts: dict[str, int] = Field(default_factory=dict)
    # Keys: PHASE_AGENTS values e.g. "phase1_plan", "phase2_jank", etc.
    # Values: total tokens consumed (input + output combined) for that phase run.
    # Updated in-place by AgentWorker after each phase completes.
```

## Workflow

1. Open `dancode/config.py`.
2. Locate the `FeatureTask` class definition.
3. After the `blocked_reason: Optional[str] = None` field (the last field in the class),
   add exactly one new line:
   ```python
       phase_token_counts: dict[str, int] = Field(default_factory=dict)
   ```
4. Do not touch any other field or import. No other files change in this task.

## Acceptance Criteria

```python
from dancode.config import FeatureTask
t = FeatureTask(task_id="x", feature_name="f", feature_description="d")
assert t.phase_token_counts == {}
t.phase_token_counts["phase1_plan"] = 1234
assert t.phase_token_counts["phase1_plan"] == 1234
# Serialise and round-trip
import json
d = json.loads(t.model_dump_json())
assert d["phase_token_counts"] == {"phase1_plan": 1234}
```

## Testing Plan

File: `tests/unit/test_config.py`

```python
def test_feature_task_phase_token_counts_default():
    """phase_token_counts defaults to empty dict."""
    from dancode.config import FeatureTask
    task = FeatureTask(task_id="t1", feature_name="feat", feature_description="desc")
    assert task.phase_token_counts == {}


def test_feature_task_phase_token_counts_roundtrip():
    """phase_token_counts survives JSON round-trip via model_dump_json."""
    import json
    from dancode.config import FeatureTask
    task = FeatureTask(task_id="t1", feature_name="feat", feature_description="desc")
    task.phase_token_counts["phase1_plan"] = 999
    raw = task.model_dump_json()
    loaded = FeatureTask.model_validate_json(raw)
    assert loaded.phase_token_counts["phase1_plan"] == 999
```
