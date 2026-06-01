## Overview
Add UI affordances for approving the general agent's plans. When the agent reaches the
`human_reply` block and posts `ChatAgentWaiting`, the chat panel should display an approval
button. Clicking the button injects "approve" as the human reply and resumes the agent.
Modifies `dancode/widgets/chat_panel.py` and `dancode/app.py`. Depends on: C1 (GeneralAgentWorker must exist).

## Files Changed
- `dancode/widgets/chat_panel.py` → add approval button when agent is waiting
- `dancode/app.py` → handle `ChatApprovalSubmitted` message

## Type Contracts
```python
# dancode/widgets/chat_panel.py
from __future__ import annotations
from textual.message import Message

class ChatApprovalSubmitted(Message):
    """Posted when the user approves the agent's plan."""
    def __init__(self, session_id: str) -> None:
        """Initialize with session ID that requires approval."""
        super().__init__()
        self.session_id = session_id

class ChatPanelWidget(Widget):
    # ... existing methods ...

    def show_approval_prompt(self, plan: str) -> None:
        """
        Display the agent's plan and an [Approve] button.

        Mounts a container with the plan text and a success-variant button above the input field.
        """
        ...

    def hide_approval_prompt(self) -> None:
        """Remove the approval button container (idempotent — no-op if not present)."""
        ...
```

Usage:
```python
# In dancode/app.py, on_chat_agent_waiting handler
def on_chat_agent_waiting(self, event: ChatAgentWaiting) -> None:
    chat_widget = self.query_one("#chat-panel-widget", ChatPanelWidget)
    chat_widget.show_approval_prompt(event.plan)

# Listen for approval
def on_chat_approval_submitted(self, event: ChatApprovalSubmitted) -> None:
    # Inject "approve" reply and resume worker
    worker, task = self._chat_workers.get(event.session_id)
    # ... resume logic ...
```

## Workflow
1. Open `dancode/widgets/chat_panel.py`.
2. Add import: `from textual.widgets import Button`, `from textual.containers import Container`.
3. Add `ChatApprovalSubmitted(Message)` with `session_id: str` field and docstring.
4. Update `DEFAULT_CSS` in `ChatPanelWidget` to include:
   ```css
   ChatPanelWidget #approval-container {
       height: auto;
       padding: 1;
       background: $boost;
       border: solid $warning;
   }
   ChatPanelWidget #approval-container Button {
       width: 20;
   }
   ```
5. Add `show_approval_prompt(self, plan: str)`:
   - Docstring: `"""Display the agent's plan and an [Approve] button. Mounts a container with the plan text and a success-variant button above the input field."""`
   - Check if `#approval-container` already exists via try/query; if yes, remove it.
   - Create a `Container(id="approval-container")`:
     - Add `Static(f"[bold yellow]Agent is waiting for approval:[/bold yellow]\n\n{plan}")`.
     - Add `Button("Approve", id="approve-button", variant="success")`.
   - Mount the container **above** the input field using `self.mount_before(container, self.query_one("#chat-input"))`.
6. Add `hide_approval_prompt(self)`:
   - Docstring: `"""Remove the approval button container (idempotent — no-op if not present)."""`
   - Try to query `#approval-container` and remove it; silently ignore `NoMatches` exception.
7. Add `on_button_pressed(self, event: Button.Pressed)`:
   - If `event.button.id == "approve-button"`:
     - Post `ChatApprovalSubmitted(self.session_id)`.
     - Call `self.hide_approval_prompt()`.
8. Open `dancode/app.py`.
9. Add import: `from dancode.widgets.chat_panel import ChatApprovalSubmitted`.
10. In `on_chat_agent_waiting(self, event: ChatAgentWaiting)`:
    - Try to query `#chat-panel-widget`.
    - If found, call `chat_widget.show_approval_prompt(event.plan)`.
11. Add `on_chat_approval_submitted(self, event: ChatApprovalSubmitted)`:
    - Get `worker, task = self._chat_workers.get(event.session_id)`.
    - If not found, log warning and return.
    - Get `session = self._config.get_chat_session(event.session_id)`.
    - Append user message: `session.messages.append({"role": "user", "content": "approve"})`.
    - Save config: `self._config.save(self._slug)`.
    - Call `AgentRunner.resume()` with `extra_messages=[{"role": "user", "content": "approve"}]` in a background executor.
    - Post `ChatAgentReply` with the final result.
12. Ensure `hide_approval_prompt()` is called when the agent resumes or the reply is posted.

## Acceptance Criteria
1. `ChatPanelWidget.show_approval_prompt(plan)` displays the plan text and an [Approve] button in a visible container. Test must query `#approval-container` and assert it exists, AND verify the plan text appears in a child widget's content.
2. Clicking [Approve] posts `ChatApprovalSubmitted` with the correct session_id. Test must capture posted messages with a message handler and assert the `session_id` field matches the widget's `session_id`.
3. `DancodeApp.on_chat_approval_submitted` resumes the agent by calling `AgentRunner.resume()` with "approve" as the human reply. Test must patch `AgentRunner.resume` and verify it was called with `extra_messages` containing `{"role": "user", "content": "approve"}`.
4. The approval prompt container is removed from the DOM after the user clicks [Approve]. Test must verify `query_one("#approval-container")` raises `NoMatches` after button click.
5. The agent proceeds to execute the plan (flow transitions from `A8_human_approval` to `A9_execute_fix`). Test must verify via mocked `AgentRunner.resume` or flow state inspection.
6. `hide_approval_prompt()` is idempotent — calling it when no prompt exists does not raise. Test must call `hide_approval_prompt()` twice in succession with no `show_approval_prompt()` call between, and assert no exception is raised.

## Testing Plan
- **Unit test**: `tests/unit/test_chat_approval.py`
  - `test_show_approval_prompt`: Create `ChatPanelWidget`, call `show_approval_prompt("test plan")`, query `#approval-container`, assert it exists and contains "test plan" text.
  - `test_hide_approval_prompt`: Show approval prompt, call `hide_approval_prompt()`, assert `query_one("#approval-container")` raises `NoMatches`.
  - `test_hide_approval_prompt_idempotent`: Call `hide_approval_prompt()` without showing first, assert no exception raised.
  - `test_approve_button_click`: Mount widget, show approval prompt, simulate clicking the approve button, capture posted messages, assert `ChatApprovalSubmitted` is posted with correct `session_id`.
- **Integration test**: `tests/integration/test_general_agent_approval.py`
  - Create a `ProjectConfig` with a chat session.
  - Mount `DancodeApp` with the session.
  - Post `ChatAgentWaiting(session_id, "test plan")`.
  - Assert approval prompt is displayed (query `#approval-container` succeeds).
  - Simulate clicking [Approve] button.
  - Mock `AgentRunner.resume()` to capture arguments.
  - Assert `on_chat_approval_submitted` was called.
  - Assert `AgentRunner.resume()` was called with extra_messages containing `{"role": "user", "content": "approve"}`.
  - Assert approval prompt is removed from DOM.
- Use mocked `AgentRunner.resume()` to avoid real Bedrock calls.
