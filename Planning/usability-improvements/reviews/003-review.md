# Code Review: Task 003 — Strengthen Phase 2 (Jank) + Phase 3 (Refine) with coding standards

## Summary

This review evaluates the code changes for task 003 which adds coding standards compliance checks to Phase 2 (Jank) and Phase 3 (Refine) flow YAML files.

## Changes Reviewed

### Core Task Changes (flows/)

**flows/phase2_jank.yaml**
- Added "Coding Standards Compliance" section that references `{{state.coding_standards}}`
- The section instructs the agent to check every task file against the coding standards
- Includes specific output format (RISK, LOCATION, PROBLEM, FIX) for violations

**flows/phase3_refine.yaml**
- Added item 7 to the checklist that cross-checks the completed plan against coding standards
- References `{{state.coding_standards}}` as required

### Test Coverage

**tests/unit/test_flow_yaml_validity.py** (new file)
- Contains `test_phase2_jank_yaml_valid()` - verifies YAML parses and `coding_standards` is present
- Contains `test_phase3_refine_yaml_valid()` - verifies YAML parses and `coding_standards` is present

## Verification Results

| Acceptance Criteria | Status |
|---------------------|--------|
| `grep -c "coding_standards" flows/phase2_jank.yaml` returns 1 | ✅ PASS (returns 1) |
| `grep -c "coding_standards" flows/phase3_refine.yaml` returns 1 | ✅ PASS (returns 1) |
| YAML files parse correctly with correct IDs | ✅ PASS |

Both YAML files:
- Parse cleanly as valid YAML
- Contain the expected `coding_standards` placeholders
- Maintain proper block structure

## Additional Observations

The diff includes changes from other tasks (001, 002) which appear to be from parallel development:
- `dancode/config.py` - `phase_token_counts` field (task 002)
- `dancode/workers/agent_runner.py` - `_load_guidance_docs` function (task 002)
- Various other flow files (phase1, phase4, phase5, phase7, phase8)
- Additional test files

This is expected given the task description notes it can "run in parallel with 001 and 002".

## Conclusion

The implementation correctly fulfills the task requirements:
1. Phase 2 flow now includes coding standards compliance checking
2. Phase 3 flow now includes a reminder to verify coding standards compliance
3. Tests were added as specified in the testing plan
4. All acceptance criteria pass

The changes are minimal and focused on the specified files, with proper YAML indentation and template variable usage.

VERDICT: PASS