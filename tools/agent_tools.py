"""Agent communication tools."""

from __future__ import annotations

from tools import ToolContext, tool


@tool
def spawn_agent(target_agent: str, prompt: str, context: ToolContext) -> str:
    """Spawn a sub-agent synchronously and return its result. Blocks until complete.

    If the sub-agent suspends to wait for human input (e.g. it needs clarification),
    its question is posted to Discord automatically via the forwarded channel context,
    and this tool returns a notice so the parent agent can inform the user.
    """
    from engine.runner import AgentRunner
    from engine.block import SuspendExecution
    runner = AgentRunner(agent_id=target_agent)
    # Forward channel context so the sub-agent can post to Discord and suspend.
    shared_overrides: dict = {}
    if context.channel_context is not None:
        shared_overrides["channel_context"] = context.channel_context
    if context._channel_adapter is not None:
        shared_overrides["_channel_adapter"] = context._channel_adapter
    if context._discord_loop is not None:
        shared_overrides["_discord_loop"] = context._discord_loop
    try:
        shared = runner.run(prompt=prompt, shared_overrides=shared_overrides or None)
    except SuspendExecution:
        return (
            f"[Agent '{target_agent}' has asked a clarifying question in Discord "
            f"and is waiting for a reply. It will continue once the human responds.]"
        )
    messages = shared.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return str(msg.get("content", ""))
    return f"[Agent '{target_agent}' completed with no assistant output]"


@tool
def send_message(target_agent: str, prompt: str, context: ToolContext) -> str:
    """Send an async message to another agent's mailbox. Returns immediately."""
    from engine.mailbox import Mailbox
    mailbox = Mailbox()
    msg_id = mailbox.send(
        target_agent=target_agent,
        prompt=prompt,
        from_agent=context.agent_id,
        from_session=context.session_id,
    )
    return f"Message queued for '{target_agent}' (id={msg_id})"
