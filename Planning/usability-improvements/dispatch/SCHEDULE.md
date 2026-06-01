### Scheduling Overview

**Tasks that can run in parallel (no shared files):**

- Task 001: Add `phase_token_counts` to FeatureTask
- Task 002: Inject guidance docs into planning agents (Phases 1–3)
- Task 003: Strengthen Phase 2 (Jank) + Phase 3 (Refine) with coding standards

**Tasks that must run sequentially (with dependency explanation):**

- Task 004: Restart Modal Widget
  - Depends on Task 001: Add `phase_token_counts` to FeatureTask

- Task 005: Wire Restart into Task Detail + App
  - Depends on Task 004: Restart Modal Widget
  - Depends on Task 001: Add `phase_token_counts` to FeatureTask

- Task 006: Phase Table Widget + Per-Phase Token Tracking
  - Depends on Task 005: Wire Restart into Task Detail + App
  - Depends on Task 001: Add `phase_token_counts` to FeatureTask

### Execution Plan

1. Start with Task 001: Add `phase_token_counts` to FeatureTask
2. Then Task 002: Inject guidance docs into planning agents (Phases 1–3)
3. Then Task 003: Strengthen Phase 2 (Jank) + Phase 3 (Refine) with coding standards
4. After these three, Task 004: Restart Modal Widget
5. Followed by Task 005: Wire Restart into Task Detail + App
6. Finally, Task 006: Phase Table Widget + Per-Phase Token Tracking

Ensure to test each task individually before moving to the next one.
