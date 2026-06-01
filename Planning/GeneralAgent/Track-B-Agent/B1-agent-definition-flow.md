## Overview
Create the general agent definition and flow YAML files. The agent uses Claude Sonnet 4.5 for reasoning,
can read the entire dancode repo, has access to all standard tools (file, git, command), and follows
a plan/execute cycle with mandatory human approval before taking action. Depends on: none (agent definition).

## Files Changed
- `agents/general_agent.yaml` → new file
- `flows/general_agent.yaml` → new file

## Type Contracts
```yaml
# agents/general_agent.yaml
id: general_agent
name: General Agent
description: |
  General-purpose assistant for debugging, quick fixes, and miscellaneous tasks.
  Operates outside the rigid 10-phase workflow.

flows:
  main: general_agent

max_iterations: 30

model_defaults:
  provider: bedrock
  model_id: us.anthropic.claude-sonnet-4-5-20250929-v1:0

permissions:
  workspace_paths:
    - data/workspace/general_agent/
  read_paths:
    - agents/
    - flows/
    - config/
    - Planning/
    - dancode/
    - tools/
  write_paths: []  # Can write to target repo via _extra_allowed_paths, not to dancode system files
  allowed_commands:
    - git
    - grep
    - find
    - cat
    - ls

context_files:
  - glob: "AGENTS.md"
    tag: system_reference

system_prompt: |
  You are the general-purpose assistant for the dancode project. Your role is to:
  - Answer questions about ongoing tasks and features
  - Create new feature tasks from user-provided descriptions (e.g. Jira tickets)
  - Answer general coding questions about the dancode codebase
  - Perform quick fixes and small changes to the source repo

  Before taking any action that modifies files, you MUST:
  1. Explain your plan in detail
  2. Wait for human approval

  You have read access to the entire dancode repo via read_file and list_files.
  You can execute git commands to inspect history and status.
  You can write files in the target repo.

  When the user asks "where are we at with <feature>?", use read_task_status to
  gather current task state, then summarize.

  When the user says "I have the following tickets: <list>", parse them and call
  create_feature_tasks to add them as pending tasks.

  For quick changes that don't impact other features, apply them directly to the
  parent branch (usually main) and commit. For substantive changes, create a new
  feature task instead.

  <system_reference>
  {{context_injection}}
  </system_reference>
```

```yaml
# flows/general_agent.yaml
start: A1_classify

blocks:
  A1_classify:
    type: llm
    prompt: |
      Classify the user's request. Choose one action:
      - status_query: User asking about task progress
      - task_creation: User providing tickets to create
      - general_query: Asking questions about the codebase
      - quick_fix: Requesting a small code change
    transitions:
      status_query: A2_status_query
      task_creation: A3_task_creation
      general_query: A4_general_query
      quick_fix: A5_plan_fix
      default: A4_general_query

  A2_status_query:
    type: tool_call
    tool: read_task_status
    transitions:
      default: A6_respond

  A3_task_creation:
    type: llm
    prompt: "Parse the user's ticket descriptions and prepare task creation parameters."
    transitions:
      default: A7_create_tasks

  A7_create_tasks:
    type: tool_call
    tool: create_feature_tasks
    transitions:
      default: A6_respond

  A4_general_query:
    type: llm
    prompt: "Answer the user's question based on your knowledge of the dancode codebase."
    transitions:
      default: A6_respond

  A5_plan_fix:
    type: llm
    prompt: "Outline the changes you will make. Respond with action: execute to proceed, or action: respond to decline."
    transitions:
      execute: A8_human_approval
      default: A6_respond

  A8_human_approval:
    type: human_reply
    prompt: "Review the plan. Reply 'approve' to proceed, or provide alternative instructions."
    transitions:
      default: A9_execute_fix

  A9_execute_fix:
    type: tool_call
    tool: execute_command
    transitions:
      default: A6_respond

  A6_respond:
    type: llm
    prompt: "Summarize the result and provide a user-friendly response."
    transitions:
      default: END
```

## Workflow
1. Create `agents/general_agent.yaml`.
2. Set `id: general_agent`, `name: General Agent`.
3. Set `max_iterations: 30`.
4. Set `model_defaults.provider: bedrock`, `model_defaults.model_id: us.anthropic.claude-sonnet-4-5-20250929-v1:0`.
5. Add `permissions`:
   - `workspace_paths: [data/workspace/general_agent/]`
   - `read_paths: [agents/, flows/, config/, Planning/, dancode/, tools/]`
   - `write_paths: []` (general agent writes to target repo via `_extra_allowed_paths`, not to system files)
   - `allowed_commands: [git, grep, find, cat, ls]`
6. Add `context_files`:
   - `glob: "AGENTS.md"`, `tag: system_reference`
7. Set `system_prompt` as shown in Type Contracts above (multi-line YAML string with instructions for all four use cases).
8. Create `flows/general_agent.yaml`.
9. Set `start: A1_classify`.
10. Add block `A1_classify`:
    - `type: llm`
    - `prompt: "Classify the user's request..."`
    - Transitions: `status_query: A2_status_query`, `task_creation: A3_task_creation`, `general_query: A4_general_query`, `quick_fix: A5_plan_fix`, `default: A4_general_query`.
11. Add block `A2_status_query`:
    - `type: tool_call`, `tool: read_task_status`
    - Transitions: `default: A6_respond`.
12. Add block `A3_task_creation`:
    - `type: llm`
    - `prompt: "Parse the user's ticket descriptions and prepare task creation parameters."`
    - Transitions: `default: A7_create_tasks`.
13. Add block `A7_create_tasks`:
    - `type: tool_call`, `tool: create_feature_tasks`
    - Transitions: `default: A6_respond`.
14. Add block `A4_general_query`:
    - `type: llm`
    - `prompt: "Answer the user's question based on your knowledge of the dancode codebase."`
    - Transitions: `default: A6_respond`.
15. Add block `A5_plan_fix`:
    - `type: llm`
    - `prompt: "Outline the changes you will make. Respond with action: execute to proceed, or action: respond to decline."`
    - Transitions: `execute: A8_human_approval`, `default: A6_respond`.
16. Add block `A8_human_approval`:
    - `type: human_reply`
    - `prompt: "Review the plan. Reply 'approve' to proceed, or provide alternative instructions."`
    - Transitions: `default: A9_execute_fix`.
17. Add block `A9_execute_fix`:
    - `type: tool_call`, `tool: execute_command`
    - Transitions: `default: A6_respond`.
18. Add block `A6_respond`:
    - `type: llm`
    - `prompt: "Summarize the result and provide a user-friendly response."`
    - Transitions: `default: END`.

## Acceptance Criteria
1. `agents/general_agent.yaml` exists at the expected path and defines `id: general_agent`. Test must verify `Path("agents/general_agent.yaml").exists()` AND `data["id"] == "general_agent"`.
2. Agent has `allowed_commands` containing at least `["git", "grep", "find", "cat", "ls"]`. Test must verify `set(["git", "grep", "find", "cat", "ls"]).issubset(set(data["permissions"]["allowed_commands"]))`.
3. `flows/general_agent.yaml` defines a flow with `data["start"] == "A1_classify"`.
4. The flow includes blocks named: `A1_classify`, `A2_status_query`, `A3_task_creation`, `A7_create_tasks`, `A4_general_query`, `A5_plan_fix`, `A6_respond`. Test must verify each name is a key in `data["blocks"]`.
5. `A8_human_approval` has `type: human_reply`. Test must verify `data["blocks"]["A8_human_approval"]["type"] == "human_reply"`.
6. Block `A6_respond` has a transition to `END`. Test must verify `"END" in data["blocks"]["A6_respond"]["transitions"].values()`.
7. Loading both YAML files with `yaml.safe_load()` succeeds without raising exceptions (test must try/except and fail on any exception).
8. The agent YAML includes a `system_prompt` key with a non-empty string value. Test must verify `"system_prompt" in data` AND `len(data["system_prompt"].strip()) > 0`.

## Testing Plan
- **Unit test**: `tests/unit/test_general_agent_yaml.py`
  - `test_general_agent_yaml_exists`: Assert `Path("agents/general_agent.yaml").exists()`.
  - `test_general_agent_yaml_valid`: Load with `yaml.safe_load()`, assert no exception, assert `data["id"] == "general_agent"`.
  - `test_general_agent_allowed_commands`: Load agent YAML, assert `{"git", "grep", "find", "cat", "ls"}.issubset(set(data["permissions"]["allowed_commands"]))`.
  - `test_general_agent_has_system_prompt`: Load agent YAML, assert `"system_prompt" in data` AND `len(data["system_prompt"].strip()) > 100` (non-trivial content).
  - `test_general_agent_flow_start`: Load `flows/general_agent.yaml`, assert `data["start"] == "A1_classify"`.
  - `test_general_agent_flow_blocks_exist`: Load flow, assert all required block names are keys in `data["blocks"]`: `["A1_classify", "A2_status_query", "A3_task_creation", "A7_create_tasks", "A4_general_query", "A5_plan_fix", "A6_respond", "A8_human_approval", "A9_execute_fix"]`.
  - `test_flow_transitions_complete`: For each block in `data["blocks"]`, if `block["type"] != "END"`, assert `"transitions" in block`, and for each transition target, assert the target exists in `data["blocks"]` or equals `"END"`.
  - `test_a8_is_human_reply`: Load flow, assert `data["blocks"]["A8_human_approval"]["type"] == "human_reply"`.
- **Integration test**: `tests/integration/test_general_agent_run.py`
  - Create `AgentRunner("general_agent")`.
  - Patch `engine.llm.call_llm` to return `{"action": "status_query"}` on first call.
  - Call `runner.run("where are we at with feature X?")` and capture the result.
  - Assert `result.get("block_visits", {}).get("A2_status_query", 0) >= 1` (block was visited).
  - Reset mocks, patch to return `{"action": "quick_fix"}` then `{"action": "execute"}`.
  - Call `runner.run("change variable foo to bar")`.
  - Assert `result.get("suspended") == True` OR `"A8_human_approval" in result.get("block_visits", {})`.
- No real Bedrock calls — use mocked `call_llm` to return synthetic YAML responses.
