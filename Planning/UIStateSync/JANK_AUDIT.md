# JANK AUDIT — UIStateSync

Audited on: 2026-06-02

---

## RISK 1 — Missing Explicitness (CRITICAL)

**LOCATION:** `Track-A-Pause/A2-agent-worker-pause.md` → Step 8 — between-phase pause check

**PROBLEM:** Step 8 placement instruction ("Insert it after all the result-processing code") had no exact code anchor, making it easy for a coding model to insert in the wrong place (e.g. inside the `while True` loop) or skip it entirely.

**FIX APPLIED:** Rewrote Step 8 with an exact anchor line (`self._post(LogLine(task.task_id, f"Phase {phase} complete."))`) and added the complete surrounding context block. Added an explicit criterion to Acceptance Criteria verifying the check is OUTSIDE the `while True` loop.

---

## RISK 2 — Long-Term Debt

**LOCATION:** `Track-A-Pause/A2-agent-worker-pause.md` → Step 3 (`pause()`)

**PROBLEM:** `loop.call_later(30, self._force_stop)` used a bare magic number. No constant, no comment explaining the value.

**FIX APPLIED:** Step 3 now instructs adding `_PAUSE_FORCE_STOP_TIMEOUT: int = 30` as a module-level constant in `agent_runner.py`, and the `call_later` uses that constant. Reference updated in Acceptance Criteria.

---

## RISK 3 — Missing Explicitness

**LOCATION:** `Track-A-Pause/A3-app-pause-handler.md` → Step 1 — `on_pause_resume_task` body

**PROBLEM:** The new handler silently returns when `task.status` is `WAITING` or `BLOCKED` — a behavior change from the old code (which resumed WAITING/BLOCKED tasks). No notification, no documentation. Users pressing [p] on a human-gate task would see nothing happen.

**FIX APPLIED:** Added an `else` branch that calls `self.notify(...)` with a `severity="warning"` message explaining that WAITING tasks need the reply box and BLOCKED tasks need [r]. Updated Acceptance Criteria to verify the `else`/notify path.

---

## RISK 4 — Self-Sabotage

**LOCATION:** `Track-B-LogStream/B2-jsonl-tail-and-session-id.md` → Step 4

**PROBLEM:** Step 4 showed the complete `while True:` block as its reference structure. A coding model that uses that block as a full replacement would silently discard A2 Step 8's between-phase pause check (which sits AFTER the `while True` loop, inside the `for` loop) — the check is not visible in B2's snippet.

**FIX APPLIED:** Rewrote Step 4 to explicitly say "update only the `try` block and its `finally` clause — do NOT replace the entire `while True` loop or the `for phase in phases:` loop." The replacement snippet now annotates new lines with `# NEW` comments, making it clear what to add vs. what to leave alone.

---

## RISK 5 — Test Gaming

**LOCATION:** `Track-B-LogStream/B2-jsonl-tail-and-session-id.md` → Testing Plan → `test_forced_session_id_consumed_by_runner`

**PROBLEM:** The original test replaced `runner.run` with a `fake_run` that manually called `so.pop(...)` itself, then asserted the key was gone. This is a tautology — the test proved nothing about whether `engine/runner.py` was actually changed.

**FIX APPLIED:** Replaced with `test_forced_session_id_in_runner_source` which uses `inspect.getsource(AgentRunner.run)` to assert that `_forced_session_id` and `.pop(` are present in the real source of `engine.runner.AgentRunner.run`. This fails if the actual file was not edited.
