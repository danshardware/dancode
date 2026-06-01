## Overview
Add a `ChatSession` data model and session list UI to the left sidebar, allowing users to create
new chat sessions and switch between them. Modifies `dancode/config.py` to add `ChatSession` and
`ProjectConfig.chat_sessions`. Updates `dancode/widgets/task_list.py` to show a "General Chat"
item at the top of the list. Depends on: A1 (ChatPanelWidget must exist).

## Files Changed
- `dancode/config.py` → add `ChatSession` model, add `chat_sessions: list[ChatSession]` to `ProjectConfig`
- `dancode/widgets/task_list.py` → add "General Chat" list item, handle selection
- `dancode/app.py` → handle `ChatSessionSelected` message, mount/unmount `ChatPanelWidget`

## Type Contracts
```python
# dancode/config.py
from __future__ import annotations
from pydantic import BaseModel, Field

class ChatSession(BaseModel):
    """Represents a single chat session with message history."""
    session_id: str
    created_at: str  # ISO 8601 timestamp
    messages: list[dict] = Field(default_factory=list)  # [{"role": str, "content": str}, ...]
    status: str = "active"  # "active" | "archived"

class ProjectConfig(BaseModel):
    """Project configuration including tasks and chat sessions."""
    clone_url: str
    local_path: str
    tasks: list[FeatureTask] = Field(default_factory=list)
    chat_sessions: list[ChatSession] = Field(default_factory=list)
    # ... rest unchanged

# dancode/widgets/task_list.py
from textual.message import Message

class ChatSessionSelected(Message):
    """Posted when user selects the General Chat item."""
    def __init__(self, session_id: str | None) -> None:
        """Initialize with optional session_id (None = create new)."""
        super().__init__()
        self.session_id = session_id
```

Usage:
```python
config.chat_sessions.append(ChatSession(session_id="abc123", created_at="2025-01-15T10:00:00Z"))
config.save(slug)
```

## Workflow
1. Open `dancode/config.py`.
2. Add `from __future__ import annotations` at the top if not already present.
3. Add `ChatSession(BaseModel)` class after `FeatureTask`:
   - Fields: `session_id: str`, `created_at: str`, `messages: list[dict]`, `status: str = "active"`.
   - Add docstring: `"""Represents a single chat session with message history."""`.
4. In `ProjectConfig`, add `chat_sessions: list[ChatSession] = Field(default_factory=list)`.
5. Open `dancode/widgets/task_list.py`.
6. At the top of `TaskListWidget.compose()`, insert a synthetic `ListItem` with `id="general-chat-item"`:
   ```python
   yield ListItem(Label("[bold magenta]💬 General Chat[/bold magenta]"), id="general-chat-item")
   ```
7. In `watch_tasks()`, **after** clearing the list and appending the General Chat item, append task items.
8. In `on_list_view_selected`, check if `event.item.id == "general-chat-item"`:
   - Post `ChatSessionSelected(session_id=None)` to signal "open or create a chat session".
9. Open `dancode/app.py`.
10. Add `on_chat_session_selected(event: ChatSessionSelected)` handler:
    - If `event.session_id is None`:
      - Create a new `ChatSession` with a fresh UUID (12-char hex), current ISO timestamp.
      - Append to `self._config.chat_sessions`.
      - Save config.
    - Get or create the target session.
    - Try to query `#chat-panel-widget`; if it doesn't exist:
      - Remove `#task-detail-widget` if present.
      - Mount `ChatPanelWidget(session_id=session.session_id, id="chat-panel-widget")` in `#main-area`.
    - If it exists, update its `session_id` and call `clear_history()`, then load messages from `session.messages`.
11. Ensure that selecting a task item removes the chat panel and shows the task detail widget again.

## Acceptance Criteria
1. `ProjectConfig.chat_sessions` is a list of `ChatSession` instances that persists through save/load cycle. Test must create config, add session, save, load fresh, and verify `loaded.chat_sessions[0].session_id == original.session_id`.
2. `TaskListWidget` shows "💬 General Chat" as the first item in the list (above all task items). Test must query the `ListView` children and verify the first `ListItem` has `id="general-chat-item"`.
3. Clicking "General Chat" when no sessions exist creates a new session with `len(session.session_id) == 12` and `session.session_id.isalnum()`, and `datetime.fromisoformat(session.created_at)` does not raise.
4. The chat panel is mounted in the main area. Test must verify `app.query_one("#chat-panel-widget", ChatPanelWidget)` does not raise.
5. Selecting a task from the list removes the chat panel from the DOM. Test must select a task, then verify `app.query_one("#chat-panel-widget")` raises `NoMatches`, AND `app.query_one("#task-detail-widget", TaskDetailWidget)` succeeds.
6. `ProjectConfig.save()` persists chat sessions including `messages` list. Test must add a session with `messages=[{"role": "user", "content": "hello"}]`, save, load, and verify `loaded.chat_sessions[0].messages == [{"role": "user", "content": "hello"}]`.

## Testing Plan
- **Unit test**: `tests/unit/test_chat_session.py`
  - `test_chat_session_model`: Instantiate `ChatSession(session_id="abc", created_at="2025-01-01T00:00:00Z")`, assert `session.session_id == "abc"` AND `session.created_at == "2025-01-01T00:00:00Z"` AND `session.messages == []` AND `session.status == "active"`.
  - `test_project_config_with_chat_sessions`: Create `ProjectConfig(clone_url="", local_path="/tmp")`, add `ChatSession(session_id="xyz", created_at="2025-01-01T00:00:00Z", messages=[{"role": "user", "content": "hi"}])`, call `save("test_slug")`, call `ProjectConfig.load("test_slug")`, assert `loaded.chat_sessions[0].session_id == "xyz"` AND `loaded.chat_sessions[0].messages == [{"role": "user", "content": "hi"}]`.
  - `test_chat_session_default_status`: Create `ChatSession(session_id="a", created_at="2025-01-01T00:00:00Z")` without explicit status, assert `session.status == "active"`.
- **Integration test**: `tests/integration/test_chat_session_selection.py`
  - Create `ProjectConfig` with no chat sessions and one task.
  - Mount `DancodeApp` in test mode using Textual pilot.
  - Query `#task-list` ListView, get first child, verify `child.id == "general-chat-item"`.
  - Simulate clicking the "General Chat" item.
  - Assert `len(app._config.chat_sessions) == 1`.
  - Assert `len(app._config.chat_sessions[0].session_id) == 12` AND `app._config.chat_sessions[0].session_id.isalnum()`.
  - Assert `datetime.fromisoformat(app._config.chat_sessions[0].created_at)` does not raise.
  - Assert `app.query_one("#chat-panel-widget", ChatPanelWidget)` succeeds (no exception).
  - Simulate selecting a task item.
  - Assert `app.query_one("#chat-panel-widget")` raises `NoMatches`.
  - Assert `app.query_one("#task-detail-widget", TaskDetailWidget)` succeeds.
- No external calls — all assertions on app state and widget tree.
