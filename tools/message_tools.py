"""Tools for checking an agent's own inbox."""

from __future__ import annotations

from tools import ToolContext, tool


@tool
def check_inbox(context: ToolContext) -> str:
    """Check this agent's inbox for pending messages. Returns a YAML summary."""
    from engine.mailbox import Mailbox
    import yaml
    mailbox = Mailbox()
    messages = mailbox.poll_inbox(context.agent_id)
    if not messages:
        return "inbox: empty"
    summary = [
        {
            "msg_id": m["msg_id"],
            "from": m.get("from_agent"),
            "prompt_preview": str(m.get("prompt", ""))[:120],
            "sent_at": m.get("sent_at"),
        }
        for m in messages
    ]
    return yaml.dump({"inbox": summary}, default_flow_style=False)


@tool
def mark_message_processed(msg_id: str, context: ToolContext) -> str:
    """Move a message from inbox to processed after handling it."""
    from engine.mailbox import Mailbox
    import yaml
    mailbox = Mailbox()
    messages = mailbox.poll_inbox(context.agent_id)
    for msg in messages:
        if msg.get("msg_id") == msg_id:
            mailbox.mark_processed(msg["_path"])
            return f"Message {msg_id} marked as processed."
    return f"No pending message with id={msg_id} found."
