## Overview

Deletes `dancode/workers/event_stream.py`.

`event_stream.py` defines `tail_event_log()` and `EventLogLine`, which tail a
`~/.config/dancode/logs/<slug>.jsonl` file and call a callback for each new line.
This file was never wired into `app.py` — no `app.py` handler imports or calls it.
It is superseded by the `_tail_engine_log` coroutine added in B2, which tails the
correct per-agent/per-session JSONL files and posts typed `LogLine` messages.

Keeping the dead file risks a future developer mistakenly wiring it up and
introducing a second, conflicting log-tailing path.

Upstream dependencies:
- B2 complete (the replacement tail coroutine exists in `agent_runner.py`).

Key assumption: `event_stream.py` is not imported by any other file in the codebase.
Verify this with `grep -r "event_stream" dancode/` before deleting.

---

## Files Changed

- `dancode/workers/event_stream.py` — **deleted**.

---

## Type Contracts

Deletions only. After this task:

```
# These no longer exist:
dancode.workers.event_stream.EventLogLine
dancode.workers.event_stream.tail_event_log
```

---

## Workflow

### Step 1 — Confirm no imports

`dancode/workers/event_stream.py` — Run:
```bash
grep -r "event_stream" dancode/ tests/
```

Expected output: zero matches (the file is standalone and not imported anywhere).
If any matches appear, remove those imports first before deleting the file.

### Step 2 — Delete the file

`dancode/workers/event_stream.py` — Delete:

```bash
rm dancode/workers/event_stream.py
```

### Step 3 — Confirm `__init__.py` does not re-export it

`dancode/workers/__init__.py` — Open and verify it does not import from `event_stream`.
If it does, remove that import.

---

## Acceptance Criteria

- `dancode/workers/event_stream.py` does not exist.
- `grep -r "event_stream" dancode/ tests/` returns zero matches.
- All existing tests pass.

---

## Testing Plan

No new test functions needed. The criterion is file absence.

```python
def test_event_stream_module_deleted():
    """event_stream.py must not exist after B3."""
    from pathlib import Path
    p = Path(__file__).parent.parent.parent / "dancode" / "workers" / "event_stream.py"
    assert not p.exists(), "event_stream.py should have been deleted in B3"
```

Place in `tests/unit/test_agent_worker_messages.py`.
