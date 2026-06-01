# Task 006 Review — Phase Table Widget + Per-Phase Token Tracking

## Summary

This task implements two related features:
- **A**: Token extraction from the Conversation object after each phase completes, stored in `task.phase_token_counts[agent_id]`
- **B**: A phase table widget that displays all 10 phases with status icons and token counts

## Files Reviewed

| File | Changes |
|------|---------|
| `dancode/widgets/task_detail.py` | Added Static, PHASE_AGENTS imports, _STATUS_ICONS dict, _render_phase_table() function, updated CSS and compose |
| `dancode/workers/agent_runner.py` | Added token extraction logic after phase completion |
| `tests/unit/test_phase_table.py` | New test file with 4 tests |

## Implementation Details

### Part A — Token Extraction (agent_runner.py)

```python
# Extract and persist cumulative token usage for this phase
_conv = result.get("_conv") if isinstance(result, dict) else None
if _conv is not None:
    _total_tokens = (
        getattr(_conv, "input_tokens", 0)
        + getattr(_conv, "output_tokens", 0)
    )
    task.phase_token_counts[agent_id] = _total_tokens
```

This is correctly placed after the `result = await loop.run_in_executor(...)` call and before the `except` block. The implementation:
- Checks if result is a dict (defensive)
- Safely extracts `_conv` from result
- Uses `getattr` with defaults for safety
- Stores total (input + output) tokens by agent_id

### Part B — Phase Table Widget (task_detail.py)

1. **Imports**: Added `Static` and `PHASE_AGENTS` as required
2. **_STATUS_ICONS**: Proper status icon mapping for done/running/waiting/blocked/cancelled/pending
3. **_render_phase_table()**: Correctly iterates through all 10 phases, shows:
   - Done phases: checkmark icon, dimmed name
   - Current phase: status icon based on task status, bold name
   - Future phases: pending icon, dimmed name
   - Token counts: formatted with commas, or "—" for untracked
4. **CSS**: Changed from fixed height `1` to `height: auto`
5. **compose()**: Replaced `Label` with `Static` widget
6. **_refresh_header()**: Properly simplified to use `_render_phase_table()`

### Tests

All 4 tests pass:
- `test_render_phase_table_has_ten_lines` ✓
- `test_render_phase_table_shows_token_count` ✓
- `test_render_phase_table_dash_for_untracked` ✓
- `test_render_phase_table_running_icon` ✓

## Notes

1. **Test value discrepancy**: The test `test_render_phase_table_shows_token_count` uses 5000 tokens while the spec example uses 12345. This is functionally equivalent and doesn't affect the test's validity.

2. **Task 005 merge**: The task spec notes this should be merged with task 005. The implementation appears clean and doesn't revert any task 005 changes (no RestartTask button visible in the diff).

3. **Edge case handling**: The code properly handles:
   - Missing `_conv` in result (checks with isinstance)
   - Missing token attributes (getattr with defaults of 0)
   - Untracked phases (shows "—" instead of "0 tok")
   - All 6 status types through _STATUS_ICONS dictionary

## Acceptance Criteria Verification

| Criteria | Status |
|----------|--------|
| 10 lines for 10 phases | ✓ Pass |
| Token count formatted with commas | ✓ Pass |
| Phases after current show pending | ✓ Pass |
| Current phase shows running icon | ✓ Pass |
| Token extraction in agent_runner | ✓ Pass |

## Verdict

The implementation is clean, complete, and follows the task specification. All tests pass.

VERDICT: PASS