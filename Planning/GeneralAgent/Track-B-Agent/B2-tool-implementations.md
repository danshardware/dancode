## Overview
Create tool implementations for the general agent: `read_task_status` (reads current task state),
`create_feature_tasks` (adds new tasks to ProjectConfig in pending state), and `execute_command`
(runs git/shell commands with guardrails). Modifies `tools/agent_tools.py`. Depends on: none.

## Files Changed
- `tools/agent_tools.py` → add `read_task_status`, `create_feature_tasks`, `execute_command`

**Note**: This file already contains `spawn_agent` and `send_message` functions and uses the `@tool` decorator from `tools`. New functions must also use `@tool` decorator and follow existing patterns. The file already has `from __future__ import annotations` at the top.

## Type Contracts
```python
# tools/agent_tools.py
from __future__ import annotations
from tools import tool, ToolContext

@tool
def read_task_status(context: ToolContext) -> str:
    """
    Read the status of all tasks in the current project.

    Returns a markdown summary with task ID, feature name, phase, status,
    and blocked reason (if any). Never raises — returns "[ERROR] ..." on exception.
    """
    ...

@tool
def create_feature_tasks(
    tasks: list[dict],
    context: ToolContext,
) -> str:
    """
    Create new feature tasks in PENDING state.

    Args:
        tasks: List of dicts with keys: feature_name (str), feature_description (str),
               openhands_model (str, optional, defaults to "minimax.minimax-m2.5").

    Returns:
        "Created N tasks: <names>" or "[ERROR] ..." on validation failure — never raises.
    """
    ...

@tool
def execute_command(
    command: str,
    context: ToolContext,
    cwd: str | None = None,
) -> str:
    """
    Execute a shell command with guardrails.

    Args:
        command: Command string (base command must be in allowed_commands).
        cwd: Working directory (defaults to repo_path).

    Returns:
        stdout + stderr, or "[ERROR] ..." if command not allowed or timeout — never raises.
    """
    ...
```

Usage:
```python
# Status query
status = read_task_status(context)
# Returns: "## Tasks\n- abc123: feature-x | Phase 5 | RUNNING\n- def456: feature-y | Phase 2 | WAITING | ..."

# Task creation
result = create_feature_tasks(context, [
    {"feature_name": "add-login", "feature_description": "Add user login page"},
    {"feature_name": "fix-bug-123", "feature_description": "Fix null pointer in handler"},
])
# Returns: "Created 2 tasks: add-login, fix-bug-123"

# Execute command
output = execute_command(context, "git log -1 --oneline", cwd="/path/to/repo")
# Returns: "abc1234 Last commit message"
```

## Workflow
1. Open `tools/agent_tools.py`.
2. Verify `from __future__ import annotations` is at the top (already present from earlier tasks).
3. Add imports after existing imports: `import subprocess`, `import shlex`, `import uuid`.
4. Add import: `from dancode.config import ProjectConfig, FeatureTask, TaskStatus, TaskPhase, PHASE_NAMES, load_or_create_project`.
5. Add `@tool` decorated function `read_task_status(context: ToolContext) -> str`:
   - Docstring: `"""Read the status of all tasks in the current project. Returns a markdown summary with task ID, feature name, phase, status, and blocked reason (if any). Never raises — returns "[ERROR] ..." on exception."""`
   - Wrap entire function body in try/except; on any exception, return `f"[ERROR] {type(e).__name__}: {e}"`.
   - Get `repo_path = context.shared.get("repo_path")`.
   - Get `clone_url = context.shared.get("clone_url", "")`.
   - Call `config, slug = load_or_create_project(repo_path, clone_url)`.
   - If `config.tasks` is empty, return `"No tasks found."`.
   - Build a markdown summary:
     - Iterate over `config.tasks`.
     - For each task: `- {task.task_id}: {task.feature_name} | Phase {task.phase} ({PHASE_NAMES[task.phase]}) | {task.status.upper()}`
     - If `task.status == TaskStatus.BLOCKED`, append `| Reason: {task.blocked_reason}`.
     - If `task.status == TaskStatus.WAITING` and `task.pending_questions`, append `| Waiting for reply: {task.pending_questions}`.
   - Return the markdown string.
6. Add `@tool` decorated function `create_feature_tasks(tasks: list[dict], context: ToolContext) -> str`:
   - Docstring: `"""Create new feature tasks in PENDING state. Args: tasks (list of dicts with keys: feature_name, feature_description, openhands_model). Returns "Created N tasks: <names>" or "[ERROR] ..." on validation failure — never raises."""`
   - Wrap entire function body in try/except; on any exception, return `f"[ERROR] {type(e).__name__}: {e}"`.
   - Get `repo_path`, `clone_url`, load `config, slug`.
   - Validate `tasks` is a non-empty list; if not, return `"[ERROR] 'tasks' must be a non-empty list of dicts."`.
   - Iterate over `tasks`:
     - Extract `feature_name`, `feature_description`, `openhands_model` (default `"minimax.minimax-m2.5"`).
     - Validate `feature_name` and `feature_description` are non-empty strings; if not, return `"[ERROR] Each task must have 'feature_name' and 'feature_description'."`.
     - Generate `task_id = uuid.uuid4().hex[:8]`.
     - Create `FeatureTask(task_id=task_id, feature_name=feature_name, feature_description=feature_description, openhands_model=openhands_model, phase=TaskPhase.PLAN, status=TaskStatus.PENDING)`.
     - Append to `config.tasks`.
   - Call `config.save(slug)`.
   - Return `f"Created {len(tasks)} tasks: {', '.join(t['feature_name'] for t in tasks)}"`.
7. Add `@tool` decorated function `execute_command(command: str, context: ToolContext, cwd: str | None = None) -> str`:
   - Docstring: `"""Execute a shell command with guardrails. Args: command (str, base must be in allowed_commands), cwd (working dir, defaults to repo_path). Returns stdout + stderr, or "[ERROR] ..." if command not allowed or timeout — never raises."""`
   - Parse `command` to extract the base command: `base_command = shlex.split(command)[0]`.
   - Check if base command is in `context.allowed_commands`.
   - If not allowed, return `f"[ERROR] command '{base_command}' not in allowed_commands: {context.allowed_commands}"`.
   - Default `cwd` to `context.shared.get("repo_path")`.
   - Wrap the subprocess call in try/except:
     - Run `subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30)`.
     - Return `result.stdout + result.stderr`.
   - On `subprocess.TimeoutExpired`: return `"[ERROR] Command timed out after 30 seconds."`.
   - On `subprocess.CalledProcessError as e`: return `f"[ERROR] Command failed with exit code {e.returncode}: {e.stderr}"`.
   - On any other `Exception as e`: return `f"[ERROR] {type(e).__name__}: {e}"` — never raise.
8. **Do NOT** manually add to `TOOL_REGISTRY` — the `@tool` decorator handles registration automatically.

## Acceptance Criteria
1. `read_task_status(context)` returns a markdown summary of all tasks in the project. Test must verify output contains task_id, phase, and status strings for each task — not just check that a string was returned.
2. `create_feature_tasks(tasks, context)` creates new `FeatureTask` instances in `PENDING` state and saves them to the project config. Test must reload config from disk and verify tasks exist with expected task_ids AND status == PENDING.
3. `execute_command(command, cwd, context)` runs the command if it is in `allowed_commands` and returns stdout/stderr. Verify by running a command with observable side effect (e.g., `touch /tmp/test_file_$RANDOM`) and asserting the file exists AND the return string is non-empty.
4. `execute_command` rejects commands not in `allowed_commands` with an error message starting with `"[ERROR]"` and containing the rejected command name.
5. All functions use the `@tool` decorator (which auto-registers them). Test must verify functions are present in `_REGISTRY` after import.
6. All tools return `"[ERROR] <message>"` on any exception — they do not raise. Test must force an exception path and verify return type is `str` starting with `"[ERROR]"`.

## Testing Plan
- **Unit test**: `tests/unit/test_general_agent_tools.py`
  - `test_read_task_status`: Create a `ProjectConfig` with 2 tasks (one RUNNING, one WAITING), call `read_task_status`, assert the output contains both task IDs and statuses.
  - `test_create_feature_tasks`: Call `create_feature_tasks` with 2 task dicts, reload the config, assert 2 new tasks exist with PENDING status AND that each task has a unique 8-character task_id.
  - `test_execute_command_allowed`: Call `execute_command` with `"touch /tmp/test_exec_cmd_{unique_suffix}.txt"` where `unique_suffix` is `uuid.uuid4().hex[:8]`, assert the file exists afterward using `Path.exists()`, AND assert the return value is a `str` (not None).
  - `test_execute_command_blocked`: Call `execute_command` with `"rm -rf /"`, assert error message starts with `"[ERROR]"` AND contains `"rm"`.
  - `test_execute_command_timeout`: Patch `subprocess.run` to raise `subprocess.TimeoutExpired(cmd="sleep", timeout=30)`, call `execute_command` with `"sleep 60"`, assert return value starts with `"[ERROR]"` and contains `"timeout"` (case-insensitive), and no exception propagates to caller.
  - `test_tool_returns_error_on_exception`: Patch `subprocess.run` to raise `OSError("disk full")`, call `execute_command`, assert return value starts with `"[ERROR]"`, contains `"OSError"`, AND assert no exception propagates (test completes without pytest catching an exception).
- **Integration test**: `tests/integration/test_general_agent_tools.py`
  - Create a real `ProjectConfig` backed by a temp directory.
  - Call `create_feature_tasks` to add tasks.
  - Call `read_task_status` and assert task summaries.
  - Call `execute_command` to run `git log` in a test repo, assert output is non-empty.
- No real Bedrock calls — all tools are pure Python functions.
