# Jank Control Audit — GeneralAgent Feature

**Date**: 2025-01-16  
**Auditor**: Phase 2 Jank Control  
**Status**: PASSED WITH FIXES APPLIED

---

## Summary

All plan files have been reviewed and updated to address the following risk categories:

1. **Lazy Stub Risk** — Acceptance criteria now specify concrete verifications
2. **Test Gaming Risk** — Tests now verify side effects, not just return values
3. **Self-Sabotage Risk** — Parallel modification conflicts documented and mitigated
4. **Convention Violations** — Tool signatures and decorator usage corrected
5. **Missing Explicitness** — Validation rules and error formats now specified

---

## Fixes Applied

### A1-chat-panel-widget.md
- Added criterion 6: Empty messages do NOT post ChatMessageSent
- Testing: Added specific assertions for RichLog content verification
- Testing: Added test for empty message rejection

### A2-session-management.md
- Criteria now verify DOM presence/absence explicitly
- Testing: Added assertions for session_id format (12-char hex) and ISO timestamp
- Testing: Added test for widget mounting/unmounting verification

### B1-agent-definition-flow.md
- Added criteria 7-8: YAML parse verification and system_prompt presence
- Testing: Added transition completeness check
- Testing: Clarified mock usage for integration tests

### B2-tool-implementations.md
- **CRITICAL FIX**: Changed `context` to be last parameter (matches existing tools)
- **CRITICAL FIX**: Added `@tool` decorator requirement (existing pattern)
- **CRITICAL FIX**: Removed manual TOOL_REGISTRY registration (decorator handles it)
- Added validation for empty/invalid inputs
- Added try/except wrappers returning `[ERROR]` strings
- Testing: Added side-effect verification (file creation check)
- Testing: Added timeout and exception handling tests

### B3-system-prompt-template.md
- Added criterion 5: No unsubstituted placeholders after rendering
- Testing: Added helper function unit tests

### C1-general-agent-worker.md
- Added criteria for error handling and concurrent request rejection
- Testing: Added error case and cancel tests

### C2-config-helpers.md
- Added criterion 6: Archived sessions are ignored
- Testing: Added specific assertions for length, format, and edge cases

### C3-conflict-detection-handoff.md
- **CRITICAL FIX**: Changed `context` to be last parameter
- **CRITICAL FIX**: Added `@tool` decorator requirement
- Added try/except wrappers returning `[ERROR]` strings
- Testing: Added tests for error returns vs exceptions

### C4-approval-ui.md
- Added criterion 6: hide_approval_prompt() is idempotent
- Testing: Added idempotency test and DOM verification

### README.md
- Added "Self-Sabotage Audit" section documenting parallel file modifications
- Documented non-overlapping changes and coordination requirements

---

## Risk Register (All Addressed)

| Risk | Location | Resolution |
|------|----------|------------|
| Stub could return hardcoded task list | B2 | Acceptance criteria require side-effect verification |
| Test passes on empty function | A1 test_append_message | Must verify content in RichLog |
| Tests mock too much | C1 integration | Mock only AgentRunner, verify real message flow |
| Parallel modification of config.py | A2 + C2 | Non-overlapping sections documented |
| Parallel modification of app.py | A2 + C1 + C4 | Distinct handlers, no overlap |
| Parallel modification of agent_tools.py | B2 + C3 | Distinct functions, no overlap |
| Flow YAML modified by two tasks | B1 + C3 | C3 depends on B1; sequential execution |
| Tool signature mismatch | B2, C3 | Fixed: context is last parameter |
| Missing @tool decorator | B2, C3 | Fixed: decorator required |
| Tools raise exceptions | B2, C3 | Fixed: try/except returning `[ERROR]` |

---

## Convention Compliance Checklist

- [x] `from __future__ import annotations` — explicitly verified in B2 workflow
- [x] Heavy imports inside functions — subprocess imported at module level (acceptable for stdlib)
- [x] Tools return str — all tools return str, `[ERROR]` prefix on failure
- [x] Tools have `context: ToolContext` as last parameter — fixed in all tool signatures
- [x] File-accessing tools use `_assert_path_allowed` — not applicable (tools use context.allowed_commands)
- [x] Tools return `[ERROR]` strings on failure — verified in all tool implementations
- [x] Pydantic models for persisted state — ChatSession uses BaseModel

---

## Remaining TODOs (Out of Scope)

1. Session archiving logic — deferred, `status` field added for future use
2. Cross-session memory — deferred, each session is independent
3. Rate limiting — deferred, no cooldown implemented

These are documented in README.md "Open Questions" as intentional deferrals with clear rationale.

---

## Verdict

**PASS** — All blocking issues resolved. Plan is ready for execution.
