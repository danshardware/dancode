"""Event stream worker — tails the project JSONL log and posts Textual messages.

Runs in a Textual background worker at ≤10 Hz.  The main app reacts to
EventLogLine messages to update task status and the live log panel.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from textual.message import Message


class EventLogLine(Message):
    """Posted whenever a new line appears in the project event log."""

    def __init__(self, raw: str, parsed: dict | None) -> None:
        super().__init__()
        self.raw = raw          # Original text line
        self.parsed = parsed    # Decoded JSON dict, or None if not valid JSON


async def tail_event_log(slug: str, callback) -> None:  # type: ignore[type-arg]
    """
    Async generator that tail-reads ~/.config/dancode/logs/<slug>.jsonl.

    Calls callback(EventLogLine) for each new line, throttled to ≤10 Hz.
    Designed to be run as a Textual worker via asyncio.

    The loop exits when a line contains {"type": "dancode_stop"}.
    """
    from dancode.config import LOGS_DIR
    log_path = LOGS_DIR / f"{slug}.jsonl"

    # Wait for the log file to appear (agent may not have started yet)
    while not log_path.exists():
        await asyncio.sleep(0.5)

    min_interval = 0.1  # 10 Hz cap

    with log_path.open("r", encoding="utf-8") as fh:
        # Jump to end so we only tail new lines
        fh.seek(0, 2)

        while True:
            line = fh.readline()
            if line:
                line = line.rstrip("\n")
                parsed: dict | None = None
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    pass
                await callback(EventLogLine(raw=line, parsed=parsed))
                if parsed and parsed.get("type") == "dancode_stop":
                    return
            else:
                await asyncio.sleep(min_interval)
