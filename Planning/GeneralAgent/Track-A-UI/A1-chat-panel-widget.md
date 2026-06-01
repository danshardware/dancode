## Overview
Create `ChatPanelWidget` in `dancode/widgets/chat_panel.py`. Displays chat message history
in a scrollable log and provides an input field for user messages. Posts `ChatMessageSent`
when the user submits a message. Depends on: none (base UI component).

## Files Changed
- `dancode/widgets/chat_panel.py` → new file

## Type Contracts
```python
# dancode/widgets/chat_panel.py
from __future__ import annotations
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Input
from textual.widget import Widget

class ChatMessageSent(Message):
    """Posted when the user sends a chat message."""
    def __init__(self, session_id: str, message: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.message = message

class ChatPanelWidget(Widget):
    """Displays chat history and an input field for new messages."""

    def __init__(self, session_id: str, **kwargs) -> None:
        """Initialize the chat panel for a given session."""
        super().__init__(**kwargs)
        self.session_id = session_id

    def compose(self) -> ComposeResult:
        """Yield header, scrollable log, and input field."""
        ...

    def append_message(self, role: str, content: str) -> None:
        """Append a message to the chat log with role-specific formatting."""
        ...

    def clear_history(self) -> None:
        """Remove all messages from the chat log."""
        ...

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user pressing Enter; post ChatMessageSent if non-empty."""
        ...
```

Usage:
```python
chat_widget = ChatPanelWidget(session_id="abc123", id="chat-panel-widget")
self.mount(chat_widget)

# Append messages from session history
for msg in session.messages:
    chat_widget.append_message(msg["role"], msg["content"])

# Listen for ChatMessageSent
def on_chat_message_sent(self, event: ChatMessageSent) -> None:
    # Pass event.message to the general agent
    ...
```

## Workflow
1. Create `dancode/widgets/chat_panel.py`.
2. Add `from __future__ import annotations` as the first import line.
3. Import: `from textual.app import ComposeResult`; `from textual.containers import Container, Vertical`;
   `from textual.message import Message`; `from textual.widgets import Header, Input, RichLog, Static`.
4. Define `ChatMessageSent(Message)` with `session_id: str` and `message: str`.
5. Define `ChatPanelWidget(Widget)`:
   - Class variable `DEFAULT_CSS`:
     ```css
     ChatPanelWidget {
         layout: vertical;
         height: 1fr;
     }
     ChatPanelWidget RichLog {
         height: 1fr;
         border: solid $primary-darken-2;
     }
     ChatPanelWidget Input {
         dock: bottom;
         width: 100%;
     }
     ```
   - `__init__(self, session_id: str, **kwargs)`:
     - Store `self.session_id = session_id`.
   - `compose()`:
     - Yield `Header("💬 General Chat")`.
     - Yield `RichLog(id="chat-log", wrap=True, highlight=True)`.
     - Yield `Input(placeholder="Type your message...", id="chat-input")`.
   - `append_message(role: str, content: str)`:
     - Query `#chat-log` → `log: RichLog`.
     - Format message with role prefix:
       - `user` → `[bold cyan]You:[/bold cyan] {content}`
       - `assistant` → `[bold green]Agent:[/bold green] {content}`
       - `system` → `[dim italic]{content}[/dim italic]`
     - `log.write(formatted_message)`.
   - `clear_history()`:
     - Query `#chat-log` → `log.clear()`.
   - `on_input_submitted(event: Input.Submitted)`:
     - Get `input_widget = self.query_one("#chat-input", Input)`.
     - `message = event.value.strip()`.
     - If empty, return.
     - Post `ChatMessageSent(self.session_id, message)`.
     - `input_widget.value = ""` (clear the input).
6. Add docstrings to all methods matching the refined Type Contracts section.

## Acceptance Criteria
1. `ChatPanelWidget` can be instantiated with a `session_id`.
2. `append_message()` displays messages in the chat log with role-specific formatting. Test must verify the message text appears in the `RichLog` content, not just that the method didn't raise.
3. Typing a message and pressing Enter posts `ChatMessageSent` with the correct `session_id` and `message`. Test must capture the posted message and assert both fields.
4. The input field is cleared after submitting a message (assert `input_widget.value == ""`).
5. `clear_history()` removes all messages from the log. Test must verify log content is empty after clear, not just that clear() was called.
6. Empty messages (whitespace only) do NOT post `ChatMessageSent`.

## Testing Plan
- **Unit test**: `tests/unit/test_chat_panel.py`
  - `test_chat_panel_instantiation`: Create `ChatPanelWidget(session_id="test123")`, assert `widget.session_id == "test123"`.
  - `test_append_message_user`: Mount widget, call `append_message("user", "hello")`, query `#chat-log` RichLog, access its `lines` or render its content, assert the string `"hello"` appears in the output.
  - `test_append_message_assistant`: Mount widget, call `append_message("assistant", "world")`, verify `"world"` appears AND `"Agent:"` prefix appears (check for role formatting).
  - `test_clear_history`: Mount widget, call `append_message("user", "test")`, call `clear_history()`, query `#chat-log`, verify `len(log.lines) == 0` or equivalent empty check.
  - `test_empty_message_not_posted`: Mount widget in test app with a message capture list, simulate `Input.Submitted` event with `value="   "` (whitespace), assert the capture list is empty (no `ChatMessageSent` posted).
- **Integration test**: `tests/integration/test_chat_input.py`
  - Create a test app class that stores received `ChatMessageSent` events in a list.
  - Mount `ChatPanelWidget(session_id="sess123")` in the test app.
  - Simulate typing "test message" into `#chat-input` and pressing Enter (use Textual pilot).
  - Assert exactly 1 message was captured.
  - Assert `captured[0].session_id == "sess123"`.
  - Assert `captured[0].message == "test message"`.
  - Query `#chat-input` Input widget, assert `input_widget.value == ""` after submission.
- No external calls — all assertions on widget state and message queue.
