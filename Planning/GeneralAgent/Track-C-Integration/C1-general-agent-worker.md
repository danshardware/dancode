## Overview
Wire the general agent into the TUI by adding a `GeneralAgentWorker` that runs in the background,
handling `ChatMessageSent` events. The worker calls `AgentRunner("general_agent")` and streams
agent responses back to the chat panel. Modifies `dancode/workers/general_agent_worker.py` (new file),
`dancode/app.py` (add message handler). Depends on: B1 (agent definition must exist), A1+A2 (chat UI must exist).

## Files Changed
- `dancode/workers/general_agent_worker.py` → new file
- `dancode/app.py` → add `on_chat_message_sent` handler, instantiate `GeneralAgentWorker`

## Type Contracts
```python
# dancode/workers/general_agent_worker.py
from __future__ import annotations
import asyncio
from textual.message import Message

class ChatAgentReply(Message):
    """Posted when the general agent sends a reply."""
    def __init__(self, session_id: str, content: str) -> None:
        """Initialize with session ID and reply content."""
        super().__init__()
        self.session_id = session_id
        self.content = content

class ChatAgentWaiting(Message):
    """Posted when the general agent is waiting for human approval."""
    def __init__(self, session_id: str, plan: str) -> None:
        """Initialize with session ID and the plan awaiting approval."""
        super().__init__()
        self.session_id = session_id
        self.plan = plan

class GeneralAgentWorker:
    """
    Drives the general agent in a background thread.

    Each chat session gets its own worker. Calls AgentRunner.run() in an executor
    and streams responses back via posted messages.
    """

    def __init__(
        self,
        session_id: str,
        repo_path: str,
        slug: str,
        post,  # callable(Message)
    ) -> None:
        """Initialize worker for a session with repo context and message callback."""
        ...

    def cancel(self) -> None:
        """Signal the worker to stop (sets internal cancelled flag)."""
        ...

    async def run(self, prompt: str) -> None:
        """Run the agent with the given prompt; post ChatAgentReply or ChatAgentWaiting on completion or suspension."""
        ...
```

Usage:
```python
# In dancode/app.py
worker = GeneralAgentWorker(
    session_id="abc123",
    repo_path="/path/to/repo",
    slug="my-repo",
    post=self._post_from_thread,
)
task = asyncio.create_task(worker.run("where are we at with feature X?"))
self._chat_workers[session_id] = (worker, task)

# Listen for replies
def on_chat_agent_reply(self, event: ChatAgentReply) -> None:
    session = self._config.get_chat_session(event.session_id)
    session.messages.append({"role": "assistant", "content": event.content})
    self._config.save(self._slug)
    chat_widget = self.query_one("#chat-panel-widget", ChatPanelWidget)
    chat_widget.append_message("assistant", event.content)
```

## Workflow
1. Create `dancode/workers/general_agent_worker.py`.
2. Add `from __future__ import annotations` as the first import line.
3. Import: `import asyncio`, `import traceback`, `from pathlib import Path`, `from textual.message import Message`.
4. Define `ChatAgentReply(Message)` with `session_id: str`, `content: str` and docstring.
5. Define `ChatAgentWaiting(Message)` with `session_id: str`, `plan: str` and docstring.
6. Define `GeneralAgentWorker`:
   - Docstring: `"""Drives the general agent in a background thread. Each chat session gets its own worker. Calls AgentRunner.run() in an executor and streams responses back via posted messages."""`
   - `__init__(self, session_id, repo_path, slug, post)`:
     - Store all parameters as instance variables.
     - Set `self._cancelled = False`.
   - `cancel(self)`:
     - Docstring: `"""Signal the worker to stop (sets internal cancelled flag)."""`
     - Set `self._cancelled = True`.
   - `async run(self, prompt: str)`:
     - Docstring: `"""Run the agent with the given prompt; post ChatAgentReply or ChatAgentWaiting on completion or suspension."""`
     - Import `from engine.runner import AgentRunner` inside the function.
     - Import `from dancode.config import LOGS_DIR` inside the function.
     - Build `shared_overrides`:
       - `_extra_allowed_paths: [str(repo_path)]`
       - `repo_path: str(repo_path)`
       - `slug: self._slug`
     - Create `runner = AgentRunner("general_agent", logs_dir=str(LOGS_DIR))`.
     - Get event loop: `loop = asyncio.get_event_loop()`.
     - Run `result = await loop.run_in_executor(None, runner.run, prompt, "main", None, None, None, None, shared_overrides)`.
     - Check if `result.get("suspended")`:
       - Extract `plan = result.get("action_input", {}).get("plan", "No plan provided.")`.
       - Post `ChatAgentWaiting(self._session_id, plan)`.
       - Return (wait for user approval).
     - Check if `result.get("_run_error")`:
       - Post `ChatAgentReply(self._session_id, "[ERROR] Agent encountered an error.")`.
       - Return.
     - Extract final assistant message from `result.get("messages", [])` (last message with role="assistant").
     - Post `ChatAgentReply(self._session_id, final_message_content)`.
     - On exception:
       - Capture traceback using `traceback.format_exc()`.
       - Post `ChatAgentReply(self._session_id, f"[ERROR] {exc}\n{tb}")`.
7. Open `dancode/app.py`.
8. Add import: `from dancode.workers.general_agent_worker import GeneralAgentWorker, ChatAgentReply, ChatAgentWaiting`.
9. In `DancodeApp.__init__`, add `self._chat_workers: dict[str, tuple[GeneralAgentWorker, asyncio.Task]] = {}`.
10. Add message handler `on_chat_message_sent(self, event: ChatMessageSent)`:
    - Get `session = next((s for s in self._config.chat_sessions if s.session_id == event.session_id), None)`.
    - If not found, log error and return.
    - Append user message to `session.messages`: `{"role": "user", "content": event.message}`.
    - Save config: `self._config.save(self._slug)`.
    - Update chat panel: `chat_widget = self.query_one("#chat-panel-widget", ChatPanelWidget)`.
    - `chat_widget.append_message("user", event.message)`.
    - Check if a worker is already running for this session (check `event.session_id in self._chat_workers`):
      - If yes, log warning and return (don't spawn multiple workers).
    - Create `worker = GeneralAgentWorker(event.session_id, self._repo_path, self._slug, self._post_from_thread)`.
    - Create `task = asyncio.create_task(worker.run(event.message))`.
    - Store in `self._chat_workers[event.session_id] = (worker, task)`.
    - Add done callback: `task.add_done_callback(lambda t: self._chat_workers.pop(event.session_id, None))`.
11. Add message handler `on_chat_agent_reply(self, event: ChatAgentReply)`:
    - Get `session = next((s for s in self._config.chat_sessions if s.session_id == event.session_id), None)`.
    - Append assistant message: `session.messages.append({"role": "assistant", "content": event.content})`.
    - Save config.
    - Update chat panel: `chat_widget.append_message("assistant", event.content)`.
12. Add message handler `on_chat_agent_waiting(self, event: ChatAgentWaiting)`:
    - Append system message to chat panel: `chat_widget.append_message("system", f"Agent is waiting for approval:\n{event.plan}")`.
    - Update chat session: append a system message to `session.messages`.
    - Save config.

## Acceptance Criteria
1. `GeneralAgentWorker` can be instantiated with a session_id, repo_path, slug, and post callable.
2. `run(prompt)` calls `AgentRunner("general_agent").run()` in a background thread executor. Test must patch `AgentRunner.run` and verify it is called with expected arguments.
3. On success, posts `ChatAgentReply` with the agent's final assistant message content extracted from the result. Test must verify the `content` field is a non-empty string from the last assistant message in `result["messages"]`.
4. On suspended (human_reply block), posts `ChatAgentWaiting` with the agent's plan extracted from result. Test must verify `plan` field matches `result["action_input"]["plan"]`.
5. On exception, posts `ChatAgentReply` with content starting with `"[ERROR]"` and including the exception message AND a traceback snippet. Test must force an exception via mocked `AgentRunner.run` and verify content format.
6. `DancodeApp` handles `ChatMessageSent` by: appending user message to session (verify `session.messages[-1]["role"] == "user"`), saving config (verify file mtime changed or mock `save()`), creating a worker, and running the agent.
7. `DancodeApp` handles `ChatAgentReply` by: appending assistant message to session (verify `session.messages[-1]["role"] == "assistant"`), saving config, and updating the chat panel (verify `append_message` was called).
8. Only one worker runs per session at a time. Test must send two `ChatMessageSent` events in rapid succession, verify only one worker is created, and verify a warning is logged for the second attempt.

## Testing Plan
- **Unit test**: `tests/unit/test_general_agent_worker.py`
  - `test_worker_instantiation`: Create `GeneralAgentWorker`, assert `session_id`, `repo_path`, `slug`, `post` are set.
  - `test_worker_run_success`: Mock `AgentRunner.run()` to return `{"messages": [{"role": "assistant", "content": "test reply"}]}`, call `worker.run("test prompt")`, capture posted messages, assert `ChatAgentReply` is posted with `content == "test reply"`.
  - `test_worker_run_suspended`: Mock `AgentRunner.run()` to return `{"suspended": True, "action_input": {"plan": "test plan"}}`, call `worker.run`, assert `ChatAgentWaiting` is posted with `plan == "test plan"`.
  - `test_worker_run_error`: Mock `AgentRunner.run()` to raise `RuntimeError("boom")`, call `worker.run`, assert `ChatAgentReply` is posted with content starting with `"[ERROR]"` and containing `"boom"`.
  - `test_worker_cancel`: Call `worker.cancel()`, assert `worker._cancelled == True`.
- **Integration test**: `tests/integration/test_general_agent_integration.py`
  - Create a `ProjectConfig` with a chat session.
  - Mount `DancodeApp` in test mode.
  - Post `ChatMessageSent(session_id, "test message")`.
  - Assert a worker is created in `app._chat_workers[session_id]`.
  - Mock `AgentRunner.run()` to return a synthetic response.
  - Wait for worker completion.
  - Assert session's `messages` list has 2 entries: user message and assistant reply.
  - Assert chat panel shows both messages.
  - Post another `ChatMessageSent` while worker is running (before completion), assert warning is logged and no second worker is created.
- No real Bedrock calls — use mocked `AgentRunner.run()` to return synthetic responses.
