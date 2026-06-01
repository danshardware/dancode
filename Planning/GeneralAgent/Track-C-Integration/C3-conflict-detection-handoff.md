## Overview
Add a mechanism to detect when the general agent's proposed changes conflict with an ongoing
feature task. If a conflict is detected, the agent should inject feedback into the task's
worktree via `.dancode-feedback.md` instead of making direct edits. Modifies
`tools/agent_tools.py` to add `check_task_conflicts` and `inject_task_feedback`.
Depends on: B2 (tool registry must exist).

## Files Changed
- `tools/agent_tools.py` → add `check_task_conflicts`, `inject_task_feedback`

**Note**: This file uses the `@tool` decorator from `tools`. New functions must also use `@tool` decorator and follow existing patterns (e.g., `context: ToolContext` as last parameter).

## Type Contracts
```python
# tools/agent_tools.py
from __future__ import annotations
from tools import tool, ToolContext

@tool
def check_task_conflicts(
    target_files: list[str],
    context: ToolContext,
) -> str:
    """
    Check if any files are part of an ongoing task's worktree.

    Args:
        target_files: List of file paths (relative to repo root).

    Returns:
        "No conflicts detected." or "Conflicts detected with task <id> (<name>): <files>".
        On exception: "[ERROR] ..." — never raises.
    """
    ...

@tool
def inject_task_feedback(
    task_id: str,
    feedback: str,
    context: ToolContext,
) -> str:
    """
    Write feedback to a task's worktree .dancode-feedback.md file.

    Args:
        task_id: Task ID to inject feedback into.
        feedback: Feedback message (plain text or markdown).

    Returns:
        "Feedback injected into task <id>." or "[ERROR] ..." if task not found
        or no worktree — never raises.
    """
    ...
```

Usage:
```python
# Check conflicts
conflict_summary = check_task_conflicts(["dancode/config.py", "dancode/app.py"], context)
# Returns: "Conflicts detected with task abc123 (add-user-auth): dancode/config.py"

# Inject feedback
result = inject_task_feedback("abc123", "Please add a 'role' field to the User model.", context)
# Returns: "Feedback injected into task abc123."
```

## Workflow
1. Open `tools/agent_tools.py`.
2. Verify `from __future__ import annotations` is at the top (already present from earlier tasks).
3. Add import: `from pathlib import Path`.
4. Add `@tool` decorated function `check_task_conflicts(target_files: list[str], context: ToolContext) -> str`:
   - Docstring: `"""Check if any files are part of an ongoing task's worktree. Args: target_files (list of paths relative to repo root). Returns "No conflicts detected." or conflict summary. On exception: "[ERROR] ..." — never raises."""`
   - Wrap entire function body in try/except; on any exception, return `f"[ERROR] {type(e).__name__}: {e}"`.
   - Get `repo_path = Path(context.shared.get("repo_path"))`.
   - Get `config, slug = load_or_create_project(str(repo_path), context.shared.get("clone_url", ""))`.
   - Filter `running_tasks = [t for t in config.tasks if t.status == TaskStatus.RUNNING and t.worktree_path]`.
   - Initialize empty conflicts list: `conflicts = []`.
   - For each `target_file` in `target_files`:
     - Resolve to absolute path: `abs_target = (repo_path / target_file).resolve()`.
     - For each `task` in `running_tasks`:
       - Resolve `worktree_root = Path(task.worktree_path).resolve()`.
       - Check if `abs_target` is under `worktree_root` (use `abs_target.is_relative_to(worktree_root)` or check `.parents`).
       - If yes, record conflict: `conflicts.append((task.task_id, task.feature_name, target_file))`.
   - If conflicts found:
     - Build markdown summary: `"Conflicts detected:\n" + "\n".join(f"- Task {tid} ({name}): {file}" for tid, name, file in conflicts)`.
     - Return summary.
   - Else:
     - Return `"No conflicts detected."`.
5. Add `@tool` decorated function `inject_task_feedback(task_id: str, feedback: str, context: ToolContext) -> str`:
   - Docstring: `"""Write feedback to a task's worktree .dancode-feedback.md file. Args: task_id, feedback. Returns success message or "[ERROR] ..." if task not found or no worktree — never raises."""`
   - Wrap entire function body in try/except; on any exception, return `f"[ERROR] {type(e).__name__}: {e}"`.
   - Get `repo_path`, load `config, slug`.
   - Get `task = config.get_task(task_id)`.
   - If `task is None`, return `f"[ERROR] task '{task_id}' not found."`.
   - If `task.worktree_path is None`, return `f"[ERROR] task '{task_id}' has no worktree."`.
   - Write `feedback` to `Path(task.worktree_path) / ".dancode-feedback.md"` using `.write_text()`.
   - Return `f"Feedback injected into task {task_id}."`.
6. **Do NOT** manually add to `TOOL_REGISTRY` — the `@tool` decorator handles registration automatically.
7. Open `flows/general_agent.yaml`.
8. Update block `A5_plan_fix`:
   - Add transition: `check_conflicts: A5a_check_conflicts`.
   - Keep existing transitions: `execute: A8_human_approval`, `default: A6_respond`.
9. Add new block `A5a_check_conflicts`:
   ```yaml
   A5a_check_conflicts:
     type: tool_call
     tool: check_task_conflicts
     transitions:
       default: A5b_handle_conflicts
   ```
10. Add block `A5b_handle_conflicts`:
    ```yaml
    A5b_handle_conflicts:
      type: llm
      prompt: "Review conflicts. If conflicts exist, respond with action: inject_feedback. If no conflicts, respond with action: proceed."
      transitions:
        inject_feedback: A5c_inject_feedback
        proceed: A8_human_approval
        default: A6_respond
    ```
11. Add block `A5c_inject_feedback`:
    ```yaml
    A5c_inject_feedback:
      type: tool_call
      tool: inject_task_feedback
      transitions:
        default: A6_respond
    ```

## Acceptance Criteria
1. `check_task_conflicts(target_files, context)` returns "No conflicts detected." if no running tasks have worktrees overlapping with `target_files`. Test must verify exact string equality.
2. `check_task_conflicts(target_files, context)` returns a conflict summary listing task_id, feature_name, and conflicting file if any `target_file` is under a running task's worktree. Test must verify the returned string contains all three values (task_id, feature_name, file path).
3. `inject_task_feedback(task_id, feedback, context)` writes feedback to `.dancode-feedback.md` in the task's worktree. Test must read the file back with `Path.read_text()` and assert exact content equality with the input feedback string.
4. `inject_task_feedback` returns a string starting with `"[ERROR]"` and containing `"not found"` if task_id does not exist.
5. `inject_task_feedback` returns a string starting with `"[ERROR]"` and containing `"no worktree"` if task has `worktree_path=None`.
6. The general agent flow includes the conflict-checking path: `A5_plan_fix` → `A5a_check_conflicts` → `A5b_handle_conflicts` → `A5c_inject_feedback` → `A6_respond`. Test must load `flows/general_agent.yaml` and verify these block names exist and transitions are correctly wired.
7. All tools return `"[ERROR] ..."` on exceptions — never raise. Test must force an exception (e.g., mock `Path.write_text` to raise `PermissionError`) and verify return type is `str` starting with `"[ERROR]"`.

## Testing Plan
- **Unit test**: `tests/unit/test_conflict_detection.py`
  - `test_check_task_conflicts_no_conflict`: Create a `ProjectConfig` with a running task (worktree at `/tmp/worktree_abc`), call `check_task_conflicts(["/other/path/file.py"], context)`, assert `result == "No conflicts detected."` (exact string match).
  - `test_check_task_conflicts_with_conflict`: Create a task with worktree `/tmp/worktree_abc`, call `check_task_conflicts(["/tmp/worktree_abc/src/file.py"], context)`, assert result contains `"Conflicts detected"`, the task_id, AND the file path `/tmp/worktree_abc/src/file.py`.
  - `test_inject_task_feedback_success`: Create a task with worktree at a temp directory (`tmp_path` fixture), call `inject_task_feedback(task_id, "Please fix X", context)`, then `assert (tmp_path / ".dancode-feedback.md").read_text() == "Please fix X"`.
  - `test_inject_task_feedback_task_not_found`: Call `inject_task_feedback("nonexistent", "text", context)`, assert `result.startswith("[ERROR]")` and `"not found" in result`.
  - `test_inject_task_feedback_no_worktree`: Create a task with `worktree_path=None`, call `inject_task_feedback(task_id, "text", context)`, assert `result.startswith("[ERROR]")` and `"no worktree" in result`.
  - `test_inject_task_feedback_exception`: Patch `Path.write_text` to raise `PermissionError("read-only")`, call `inject_task_feedback`, assert return value starts with `"[ERROR]"` and contains `"PermissionError"`, and no exception propagates.
- **Integration test**: `tests/integration/test_general_agent_conflict_flow.py`
  - Create a `ProjectConfig` with a running task and a worktree at a temp directory.
  - Mock `call_llm` to: classify as `quick_fix`, then return `check_conflicts` action, then return `inject_feedback` action.
  - Run the general agent with a prompt to modify a file in the worktree path.
  - Assert `check_task_conflicts` was called (via tool call log or mock).
  - Assert `inject_task_feedback` was called.
  - Assert `.dancode-feedback.md` was created in the worktree with non-empty content.
- No real Bedrock calls — use mocked `AgentRunner.run()` to simulate the flow.
