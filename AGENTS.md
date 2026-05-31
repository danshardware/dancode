# AGENTS.md — dancode project reference

This file is the canonical reference for LLM agents operating in this codebase.
Read this before writing any code.

---

## What dancode is

`dancode` is a Python TUI application that orchestrates a 10-phase AI-driven software
development workflow on top of a target git repository. It manages parallel git worktrees,
coordinates multiple AWS Bedrock models per phase, and invokes OpenHands for the actual
coding tasks in phases 5 and 6.

It is **not** a general-purpose coding tool. It is a workflow orchestrator whose job is to
produce a fully-reviewed, merged feature branch from a plain-English feature description.

---

## Directory layout

```
dancode/                   Python package (TUI + config + workers)
  cli.py                   Entry point — resolves repo, validates Bedrock, launches TUI
  app.py                   Textual application (DancodeApp)
  config.py                Pydantic models + session persistence
  bedrock_check.py         Startup AWS validation
  widgets/
    task_list.py           Left-panel task list
    task_detail.py         Right-panel task detail + action buttons
    new_feature_modal.py   Modal to create a new FeatureTask
    feedback_modal.py      Modal to inject steering text into a running agent
  workers/
    agent_runner.py        AgentWorker — drives phases 1→10 in a background thread

engine/                    The council framework (do not edit without understanding it)
  runner.py                AgentRunner — synchronous, runs a single agent flow
  paths.py                 Resolves DATA_DIR; must be set via COUNCIL_DATA_DIR env var
                           BEFORE importing engine. DATA_DIR is frozen at import time.
  logger.py                Logger(logs_dir, agent_id, session_id) → JSONL log files
  block.py                 Block types: LLMBlock, ToolCallBlock, HumanReplyBlock, etc.

flows/                     Flow YAML definitions (phase1_plan.yaml … phase10_finalize.yaml)
agents/                    Agent YAML definitions (phase1_plan.yaml … phase10_finalize.yaml)
tools/                     Tool implementations (list_files, read_file, write_file, etc.)
config/                    Shared model and tool config files
```

---

## Data / state layout

```
~/.config/dancode/
  projects/<repo-slug>.json    Persisted ProjectConfig (tasks, phases, statuses)
  logs/<agent_id>/<session>.jsonl   Per-agent JSONL log files written by engine/logger.py
```

The `COUNCIL_DATA_DIR` environment variable must be set to `~/.config/dancode` before
any `engine.*` import. This is done at the top of `dancode/cli.py` — do not move or
reorder that line.

---

## The 10-phase pipeline

Each phase is represented by:
- An agent YAML: `agents/phase<N>_<name>.yaml` — model, tools, system prompt skeleton
- A flow YAML: `flows/phase<N>_<name>.yaml` — the block graph the agent follows

| Phase | Enum | Agent ID | Model | Purpose |
|-------|------|----------|-------|---------|
| 1 | PLAN | `phase1_plan` | Claude Sonnet 4.5 | Ask clarifying questions, produce `Planning/<feature>/` |
| 2 | JANK | `phase2_jank` | Claude Opus 4.5 | Critique and harden the plan |
| 3 | REFINE | `phase3_refine` | Claude Sonnet 4.5 | Resolve jank notes, finalize plan |
| 4 | DISPATCH | `phase4_dispatch` | Nova Lite | Read plan, write per-task dispatch prompts + SCHEDULE.md |
| 5 | CODE | `phase5_code` | Nova Lite (coordinator) + MiniMax M2.5 (OpenHands) | Create worktrees, run OpenHands per task |
| 6 | QA | `phase6_qa` | Nova Lite (coordinator) + MiniMax M2.5 (OpenHands) | Run OpenHands QA reviewer per task, write reviews |
| 7 | CONSOLIDATE | `phase7_consolidate` | Claude Sonnet 4.5 | Merge worktrees back to feature branch |
| 8 | REVIEW | `phase8_review` | Claude Sonnet 4.5 | Human-in-the-loop gate, changelogs |
| 9 | DOCS | `phase9_docs` | DeepSeek V3.2 | Write/update documentation |
| 10 | FINALIZE | `phase10_finalize` | Nova Lite | Final checks, tag, branch cleanup |

### Human gates

Phases 1, 2, 3, and 8 contain `human_reply` blocks that pause execution and wait for
user input. The TUI surfaces these as **WAITING** status. Use the **[f] Feedback** button
to supply the reply.

Phases 4, 5, 6, 7, 9, and 10 are fully automated — they should run start to finish
without human input.

---

## Key data models (dancode/config.py)

```python
class TaskPhase(int, Enum):   # 1–10
class TaskStatus(str, Enum):  # pending | running | waiting | blocked | done | cancelled

class FeatureTask(BaseModel):
    task_id: str              # short UUID
    feature_name: str         # slug, used as directory name in Planning/
    feature_description: str  # plain English
    worktree_path: str | None # path to the git worktree for this feature
    feature_branch: str | None
    phase: TaskPhase          # current phase
    status: TaskStatus        # current status
    openhands_model: str      # model string passed to openhands_dispatch
    session_ids: dict[str, str]   # phase_name → engine session_id
    blocked_reason: str | None
```

---

## Worker lifecycle (dancode/workers/agent_runner.py)

`AgentWorker` is instantiated per `FeatureTask`. Its `run()` coroutine:

1. Iterates over `TaskPhase` values from `task.phase` through 10.
2. For each phase: posts `TaskStatusChanged(RUNNING)`, calls
   `AgentRunner.run()` in a thread executor.
3. On `HumanReplyRequired` or similar: posts `TaskStatusChanged(WAITING)`.
4. On unhandled exception: posts `TaskStatusChanged(BLOCKED)` + `LogLine` with traceback.
5. On completion of all phases: posts `TaskStatusChanged(DONE)`.

The worker is stored in `app._agent_workers[task_id]`. The asyncio task handle is in
`app._agent_tasks[task_id]`. The done callback on the asyncio task calls
`app._on_worker_done()` which surfaces any unhandled exception as a TUI notification.

---

## Conventions for new code in this repo

- **No secrets in code.** AWS creds come from env vars or IAM role only.
- **No `import engine.*` before `COUNCIL_DATA_DIR` is set.** Always check cli.py ordering.
- **Pydantic models for all persisted state.** Never write raw dicts to JSON.
- **Post `TaskStatusChanged` and `LogLine` messages** from workers — never call TUI
  methods directly from a thread.
- **`TextArea` widgets** must not use `language=` unless the tree-sitter grammar package
  is verified to be installed. (`tree-sitter-markdown` is NOT installed.)
- **Textual internal names:** Do not use `self._workers` or `self._tasks` as attribute
  names on `App` subclasses — Textual uses those internally. Prefer `_agent_*`.
- **`client.list_foundation_models()`** takes no keyword arguments. `maxResults` is
  invalid and will raise.

---

## Flow YAML conventions

Flow files live in `flows/`. Block types:

- `llm` — calls the agent's model; LLM picks the next `action` from its YAML response
- `tool_call` — executes a named tool, result goes back to the `llm` block
- `human_reply` — pauses and waits; the reply is injected into shared state
- `END` — terminal block; phase is complete

Transitions are keyed by the `action` value in the LLM's YAML response. A `default`
transition catches any unrecognised action.

---

## Environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COUNCIL_DATA_DIR` | yes | `data/` | Root for agents/, flows/, logs/ |
| `AWS_REGION` | yes | — | Bedrock region |
| `AWS_ACCESS_KEY_ID` | yes* | — | AWS creds (*or IAM role) |
| `AWS_SECRET_ACCESS_KEY` | yes* | — | AWS creds |
| `OPENHANDS_API_KEY` | no | — | If OpenHands requires an API key |

---

## Running locally

```bash
# Install
uv sync

# Run TUI against a repo
dancode /path/to/target/repo

# Debug a single agent phase directly
dancode --agent phase1_plan --prompt "add user auth"

# Run tests
uv run pytest tests/
```
