# Task 002 — Inject guidance docs into planning agents (Phases 1–3)

**Track A — can run in parallel with 001 and 003**

## Overview

`agents_md` is referenced in phase 1–3 flow templates via `{{state.agents_md}}` but is
never populated in `shared_overrides` — it renders as an empty string today.

This task wires up two new shared-state keys for phases 1–3:
- `agents_md`: content of `AGENTS.md` at the dancode repo root
- `coding_standards`: concatenation of all `.agents/skills/*/SKILL.md` files

Both are injected only for phases PLAN (1), JANK (2), and REFINE (3).

## Files Changed

- `dancode/workers/agent_runner.py`

## Type Contracts

```python
def _load_guidance_docs(repo_root: Path) -> tuple[str, str]:
    """Load guidance documents from the dancode installation root.

    Returns:
        agents_md: Content of AGENTS.md.
        coding_standards: Concatenated content of all .agents/skills/*/SKILL.md files,
            each prefixed with a header line showing the skill name.
    """
```

`repo_root` is `Path(__file__).parent.parent.parent` from inside `agent_runner.py`
(navigates: `dancode/workers/` → `dancode/` → repo root).

## Workflow

1. Open `dancode/workers/agent_runner.py`.

2. Add the following import at the top, after the existing imports:
   ```python
   from pathlib import Path
   ```
   (Check if `Path` is already imported — it is via `from pathlib import Path` on line ~13.
   If already present, skip this step.)

3. After the import block and before the `AgentWorker` class, add the helper function:
   ```python
   def _load_guidance_docs(repo_root: Path) -> tuple[str, str]:
       """Load AGENTS.md and skill SKILL.md files from the dancode repo root."""
       agents_md_path = repo_root / "AGENTS.md"
       agents_md = agents_md_path.read_text(encoding="utf-8") if agents_md_path.exists() else ""

       skills_dir = repo_root / ".agents" / "skills"
       skill_parts: list[str] = []
       if skills_dir.exists():
           for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
               skill_name = skill_file.parent.name
               content = skill_file.read_text(encoding="utf-8")
               skill_parts.append(f"=== SKILL: {skill_name} ===\n{content}")
       coding_standards = "\n\n".join(skill_parts)

       return agents_md, coding_standards
   ```

4. In `AgentWorker.run()`, locate the `shared_overrides` dict that is built before
   calling `runner.run()`. It currently looks like:
   ```python
   shared_overrides: dict = {
       "_extra_allowed_paths": [str(repo)],
       "repo_path": str(repo),
       "feature_name": task.feature_name,
       "feature_description": task.feature_description,
       "feature_branch": ...,
       "openhands_model": task.openhands_model,
   }
   ```

5. After that dict is built, add the guidance injection block for phases 1–3:
   ```python
   if phase in (TaskPhase.PLAN, TaskPhase.JANK, TaskPhase.REFINE):
       _repo_root = Path(__file__).parent.parent.parent
       _agents_md, _coding_standards = _load_guidance_docs(_repo_root)
       shared_overrides["agents_md"] = _agents_md
       shared_overrides["coding_standards"] = _coding_standards
   ```

   Place this block immediately after the `shared_overrides` dict definition and before
   the `log_path` assignment.

6. Do not change any other part of the file.

## Acceptance Criteria

```python
# Verify _load_guidance_docs returns non-empty strings when called from the repo root
from pathlib import Path
from dancode.workers.agent_runner import _load_guidance_docs

repo_root = Path(__file__).parent.parent.parent.parent  # adjust for test location
agents_md, coding_standards = _load_guidance_docs(repo_root)

assert len(agents_md) > 100, "AGENTS.md should have content"
assert "phase" in agents_md.lower(), "AGENTS.md should mention phases"
assert len(coding_standards) > 100, "Skills should have content"
assert "SKILL:" in coding_standards, "Skills block should have headers"
```

```python
# Verify guidance is injected for PLAN phase but NOT for CODE phase
# (Integration-level check: inspect shared_overrides built in run())
from dancode.config import TaskPhase
# TaskPhase.PLAN (1), TaskPhase.JANK (2), TaskPhase.REFINE (3) → inject
# TaskPhase.DISPATCH (4) and above → do NOT inject
assert TaskPhase.PLAN in (TaskPhase.PLAN, TaskPhase.JANK, TaskPhase.REFINE)
assert TaskPhase.CODE not in (TaskPhase.PLAN, TaskPhase.JANK, TaskPhase.REFINE)
```

## Testing Plan

File: `tests/unit/test_agent_worker_messages.py`

```python
def test_load_guidance_docs_returns_nonempty():
    """_load_guidance_docs reads AGENTS.md and skill files from repo root."""
    from pathlib import Path
    from dancode.workers.agent_runner import _load_guidance_docs

    # Navigate from tests/unit/ → tests/ → repo root
    repo_root = Path(__file__).parent.parent.parent
    agents_md, coding_standards = _load_guidance_docs(repo_root)

    assert isinstance(agents_md, str)
    assert len(agents_md) > 0
    assert isinstance(coding_standards, str)
    assert len(coding_standards) > 0


def test_load_guidance_docs_missing_dir(tmp_path):
    """_load_guidance_docs returns empty strings gracefully when files are absent."""
    from dancode.workers.agent_runner import _load_guidance_docs

    agents_md, coding_standards = _load_guidance_docs(tmp_path)
    assert agents_md == ""
    assert coding_standards == ""
```
