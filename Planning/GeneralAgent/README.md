# General Agent Feature — Planning

This directory contains the planning documents for adding a **general agent** to dancode.
The general agent is a conversational assistant that operates outside the rigid 10-phase
workflow, handling status queries, task creation, quick fixes, and debugging.

---

## Execution Map

### Track A — UI Components
Adds chat UI to the TUI: left sidebar item, chat panel, session management.

```
A1 [chat-panel-widget]
  ↓
A2 [session-management] ← depends on A1
```

**Critical path**: A1 → A2  
**Estimated effort**: 6 hours (2 tasks × 3 hours)

### Track B — Agent Definition & Tools
Defines the general agent YAML, flow, system prompt, and tool implementations.

```
B1 [agent-definition-flow]
  ↓
B2 [tool-implementations] ← depends on B1
  ↓
B3 [system-prompt-template] ← depends on B1
```

**Critical path**: B1 → B2 → B3  
**Estimated effort**: 9 hours (3 tasks × 3 hours)

### Track C — Integration
Wires the agent into the TUI, adds conflict detection, and implements approval flow.

```
C1 [general-agent-worker] ← depends on B1, A1+A2
  ↓
C2 [config-helpers] ← depends on A2
  ↓
C3 [conflict-detection-handoff] ← depends on B2, C1
  ↓
C4 [approval-ui] ← depends on C1
```

**Critical path**: (A2 + B1) → C1 → C2 → C3 → C4  
**Estimated effort**: 12 hours (4 tasks × 3 hours)

---

## Dependency Summary

- **A1** (chat-panel-widget): No dependencies (pure UI component).
- **A2** (session-management): Depends on A1.
- **B1** (agent-definition-flow): No dependencies (YAML definitions).
- **B2** (tool-implementations): Depends on B1 (agent must exist to register tools).
- **B3** (system-prompt-template): Depends on B1 (modifies agent YAML).
- **C1** (general-agent-worker): Depends on B1 (agent), A1+A2 (chat UI).
- **C2** (config-helpers): Depends on A2 (ChatSession model).
- **C3** (conflict-detection-handoff): Depends on B2 (tools), C1 (worker).
- **C4** (approval-ui): Depends on C1 (worker).

**Parallelization strategy**:
- Tracks A and B can run in parallel (no cross-dependencies until C1).
- Once A2 and B1 are complete, C1 can start.
- C2, C3, C4 run sequentially after C1.

**Total estimated effort**: 27 hours (8 tasks)  
**Critical path**: A1 → A2 → C1 → C2 → C3 → C4 (21 hours if sequential)

---

## Key Design Decisions

1. **Plan/Execute Cycle**: The general agent follows a strict plan/execute pattern with
   mandatory human approval before making changes. This prevents accidental destructive
   operations (e.g. force-pushing, deleting files).

2. **Conflict Detection**: Before executing a fix, the agent checks if target files are
   part of an ongoing task's worktree. If a conflict is detected, the agent injects
   feedback into the task via `.dancode-feedback.md` instead of making direct edits.

3. **Session Management**: Each chat session has its own `ChatSession` model stored in
   `ProjectConfig`. Sessions persist across TUI restarts. The "General Chat" item in
   the task list opens the most recent active session or creates a new one.

4. **Agent Capabilities**:
   - **Status queries**: Uses `read_task_status` tool + inspects log JSONL files.
   - **Task creation**: Parses user-provided ticket descriptions, calls `create_feature_tasks`.
   - **Quick fixes**: Writes files or executes commands after human approval.
   - **General Q&A**: Answers questions about the codebase using `read_file` / `list_files`.

5. **Model Selection**: Uses Claude Sonnet 4.5 for reasoning (same as phases 1, 3, 7, 8).
   This model has strong instruction-following and can handle the open-ended nature of
   the general agent's tasks.

6. **Workspace Isolation**: General agent workspace is session-scoped:
   `data/workspace/general_agent/<session_id>/`. This prevents file clashes if multiple
   chat sessions run concurrently.

7. **Tool Permissions**:
   - Can read entire dancode repo (`read_paths: [agents/, flows/, config/]`).
   - Can write to target repo via `_extra_allowed_paths` (injected at runtime).
   - CANNOT write to dancode system files (no `write_paths` entry).
   - Can execute: `git`, `grep`, `find`, `cat`, `ls`.

---

## Testing Strategy

- **Unit tests**: Each task has unit tests for its new components (models, widgets, tools).
- **Integration tests**: Full flow tests (e.g. send a chat message, assert agent responds).
- **No real Bedrock calls**: All tests use mocked `AgentRunner.run()` / `call_llm()` to
  avoid external dependencies and costs.

---

## Open Questions

1. **Session archiving**: Should old chat sessions be auto-archived after N days?
   - **Decision**: Add a `status: str = "active"` field to `ChatSession`. Future work can
     implement archiving logic. For now, all sessions remain active.

2. **Multi-session concurrency**: Can the general agent handle multiple sessions at once?
   - **Decision**: Yes. Each session gets its own worker and session-scoped workspace.
     Workers are stored in `app._chat_workers[session_id]`.

3. **Agent memory**: Should the agent remember context across sessions?
   - **Decision**: No. Each session is independent. If cross-session memory is needed,
     future work can add a shared "memory" file that all sessions read/write.

4. **Rate limiting**: Should we limit how often the user can invoke the agent?
   - **Decision**: No rate limiting for now. If abuse becomes an issue, add a cooldown
     check in `on_chat_message_sent`.

---

## Self-Sabotage Audit — Parallel Modification Check

### Files Modified by Multiple Tasks
| File | Modified By | Sections |
|------|-------------|----------|
| `dancode/config.py` | A2, C2 | A2: adds `ChatSession` model, `chat_sessions` field. C2: adds helper methods. **Non-overlapping** — A2 adds class/field, C2 adds methods to existing class. |
| `dancode/app.py` | A2, C1, C4 | A2: `on_chat_session_selected`. C1: `on_chat_message_sent`, `on_chat_agent_reply`, `on_chat_agent_waiting`, `_chat_workers` dict. C4: `on_chat_approval_submitted`. **Non-overlapping** — each task adds distinct handlers. |
| `tools/agent_tools.py` | B2, C3 | B2: adds `read_task_status`, `create_feature_tasks`, `execute_command`. C3: adds `check_task_conflicts`, `inject_task_feedback`. **Non-overlapping** — each task adds distinct functions. |
| `flows/general_agent.yaml` | B1, C3 | B1: creates file with initial blocks. C3: adds conflict-detection blocks. **Requires coordination** — C3 modifies file created by B1. C3 depends on B1 completing first. |

### Mitigation
- Execute Track A and Track B in parallel.
- Track C must start only after A2 and B1 are complete (dependency enforced in plan).
- C3 modifies `flows/general_agent.yaml` — reviewer must verify B1 is merged before C3 runs.

---

## Files Touched

| File | Change Type | Track |
|------|-------------|-------|
| `dancode/widgets/chat_panel.py` | new file | A1 |
| `dancode/config.py` | modified (add ChatSession, helpers) | A2, C2 |
| `dancode/widgets/task_list.py` | modified (add General Chat item) | A2 |
| `dancode/app.py` | modified (add chat handlers) | A2, C1, C4 |
| `agents/general_agent.yaml` | new file | B1, B3 |
| `flows/general_agent.yaml` | new file | B1, C3 |
| `tools/agent_tools.py` | modified (add 5 new tools) | B2, C3 |
| `dancode/workers/general_agent_worker.py` | new file | C1 |

**Total**: 8 files (3 new, 5 modified)

---

## Rollout Plan

1. **Phase 1**: Track A (UI components) — can be merged independently.
2. **Phase 2**: Track B (agent definition) — can be merged after A is complete.
3. **Phase 3**: Track C (integration) — final integration, requires A + B.

Each phase can be code-reviewed and tested in isolation before merging.
