"""File-based async mailbox for agent-to-agent communication."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Mailbox:
    def __init__(self, messages_dir: str | None = None) -> None:
        from engine.paths import MESSAGES_DIR
        self.messages_dir = Path(messages_dir) if messages_dir is not None else MESSAGES_DIR

    def send(
        self,
        target_agent: str,
        prompt: str,
        from_agent: str,
        from_session: str,
        reply_to_session: str | None = None,
    ) -> str:
        """Write a message to target_agent's inbox. Returns the message ID."""
        msg_id = uuid.uuid4().hex[:12]
        inbox = self.messages_dir / target_agent / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "msg_id": msg_id,
            "from_agent": from_agent,
            "from_session": from_session,
            "reply_to_session": reply_to_session,
            "prompt": prompt,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        msg_path = inbox / f"{msg_id}.yaml"
        import yaml
        with msg_path.open("w", encoding="utf-8") as fh:
            yaml.dump(payload, fh, default_flow_style=False)
        return msg_id

    def poll_inbox(self, agent_id: str) -> list[dict[str, Any]]:
        """Return all unprocessed messages for agent_id (does not delete them)."""
        inbox = self.messages_dir / agent_id / "inbox"
        if not inbox.exists():
            return []
        import yaml
        messages = []
        for path in sorted(inbox.glob("*.yaml")):
            with path.open(encoding="utf-8") as fh:
                msg = yaml.safe_load(fh)
            msg["_path"] = str(path)
            messages.append(msg)
        return messages

    def mark_processed(self, message_path: str) -> None:
        """Move a processed message to the agent's processed/ directory."""
        src = Path(message_path)
        dest = src.parent.parent / "processed" / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)

    def has_reply(self, agent_id: str, reply_to_session: str) -> dict[str, Any] | None:
        """Check if any inbox message is a reply for the given session. Returns message or None."""
        for msg in self.poll_inbox(agent_id):
            if msg.get("reply_to_session") == reply_to_session:
                return msg
        return None
