## Overview
Add helper methods to `ProjectConfig` for managing chat sessions: `get_chat_session()`,
`add_chat_session()`, `get_or_create_chat_session()`. Modifies `dancode/config.py`.
Depends on: A2 (ChatSession model must exist).

## Files Changed
- `dancode/config.py` → add helper methods to `ProjectConfig`

## Type Contracts
```python
# dancode/config.py
class ProjectConfig(BaseModel):
    """Project configuration including tasks and chat sessions."""
    clone_url: str
    local_path: str
    tasks: list[FeatureTask] = Field(default_factory=list)
    chat_sessions: list[ChatSession] = Field(default_factory=list)

    def save(self, slug: str) -> None:
        """Persist config to <slug>.json in PROJECTS_DIR."""
        ...

    @classmethod
    def load(cls, slug: str) -> "ProjectConfig | None":
        """Load config from <slug>.json, return None if not found."""
        ...

    def get_task(self, task_id: str) -> FeatureTask | None:
        """Return the task with matching ID, or None if not found."""
        ...

    def upsert_task(self, task: FeatureTask) -> None:
        """Insert or update a task by ID."""
        ...

    def get_chat_session(self, session_id: str) -> ChatSession | None:
        """Return the session with matching ID, or None if not found."""
        ...

    def add_chat_session(self, session: ChatSession) -> None:
        """Append a new chat session to the list."""
        ...

    def get_or_create_chat_session(self) -> ChatSession:
        """
        Return the most recent active chat session, or create a new one.

        Creates a new session with 12-char hex ID and ISO timestamp if none exist.
        Does NOT save — caller must call save().
        """
        ...
```

Usage:
```python
config, slug = load_or_create_project("/path/to/repo", None)

# Get existing session
session = config.get_chat_session("abc123")

# Create new session
new_session = ChatSession(session_id=uuid.uuid4().hex[:12], created_at=datetime.utcnow().isoformat())
config.add_chat_session(new_session)
config.save(slug)

# Get or create
session = config.get_or_create_chat_session()
config.save(slug)
```

## Workflow
1. Open `dancode/config.py`.
2. Verify `from __future__ import annotations` is at the top of the file (add if not present).
3. Add imports at the top: `import uuid`, `from datetime import datetime` (if not already present).
4. In `ProjectConfig`, after `upsert_task()`, add `get_chat_session(self, session_id: str) -> ChatSession | None`:
   - Docstring: `"""Return the session with matching ID, or None if not found."""`
   - Body: `return next((s for s in self.chat_sessions if s.session_id == session_id), None)`.
5. Add `add_chat_session(self, session: ChatSession) -> None`:
   - Docstring: `"""Append a new chat session to the list."""`
   - Body: `self.chat_sessions.append(session)`.
6. Add `get_or_create_chat_session(self) -> ChatSession`:
   - Docstring: `"""Return the most recent active chat session, or create a new one. Creates a new session with 12-char hex ID and ISO timestamp if none exist. Does NOT save — caller must call save()."""`
   - Body:
     - Filter `active_sessions = [s for s in self.chat_sessions if s.status == "active"]`.
     - If `active_sessions` is not empty:
       - Sort by `created_at` descending: `active_sessions.sort(key=lambda x: x.created_at, reverse=True)`.
       - Return the most recent session: `return active_sessions[0]`.
     - Else:
       - Generate a new `session_id = uuid.uuid4().hex[:12]`.
       - Create `new_session = ChatSession(session_id=session_id, created_at=datetime.utcnow().isoformat())`.
       - `self.chat_sessions.append(new_session)`.
       - Return `new_session`.

## Acceptance Criteria
1. `get_chat_session(session_id)` returns the matching `ChatSession` or `None` if not found. Test must verify returned object's `session_id` field matches input when found.
2. `add_chat_session(session)` appends the session to `chat_sessions`. Test must verify `len(config.chat_sessions)` increased by exactly 1 AND the new session is `config.chat_sessions[-1]`.
3. `get_or_create_chat_session()` returns the most recent active session if one exists. Test must add two sessions with different `created_at` timestamps and verify the returned session's `created_at` is the later timestamp.
4. If no active sessions exist, `get_or_create_chat_session()` creates a new session with a 12-character hex ID (verify `len(session.session_id) == 12` and `session.session_id.isalnum()`) and valid ISO 8601 timestamp (verify `datetime.fromisoformat(session.created_at)` does not raise).
5. The new session is appended to `chat_sessions` (verify `len(config.chat_sessions)` increased) — caller must save the config.
6. `get_or_create_chat_session()` ignores sessions with `status != "active"` when finding the most recent. Test must add one archived session and one active session, call `get_or_create_chat_session()`, and verify the returned session is the active one.

## Testing Plan
- **Unit test**: `tests/unit/test_project_config_chat_helpers.py`
  - `test_get_chat_session_found`: Add 2 sessions to config, call `get_chat_session(session_id_2)`, assert `returned.session_id == session_id_2`.
  - `test_get_chat_session_not_found`: Call `get_chat_session("nonexistent")`, assert returns `None` (use `is None` check).
  - `test_add_chat_session`: Record `before_len = len(config.chat_sessions)`, call `add_chat_session(new_session)`, assert `len(config.chat_sessions) == before_len + 1` AND `config.chat_sessions[-1] is new_session`.
  - `test_get_or_create_chat_session_existing`: Add two active sessions with timestamps "2025-01-01T00:00:00Z" and "2025-01-02T00:00:00Z", call `get_or_create_chat_session()`, assert `returned.created_at == "2025-01-02T00:00:00Z"`.
  - `test_get_or_create_chat_session_new`: Call `get_or_create_chat_session()` on a config with no sessions, assert `len(returned.session_id) == 12` AND `returned.session_id.isalnum()` AND `datetime.fromisoformat(returned.created_at)` does not raise AND `returned.status == "active"`.
  - `test_get_or_create_ignores_archived`: Add session A with `status="archived"`, add session B with `status="active"`, call `get_or_create_chat_session()`, assert `returned.session_id == B.session_id`.
- No external calls — all assertions on in-memory `ProjectConfig` state.
