# dancode — Test Plan

This document describes how to verify each component works before trusting it in a
live run. Tests are organised from smallest/cheapest to largest/most expensive.
Run cheaper tests first; only proceed to integration tests after unit tests pass.

---

## Test philosophy

We have **zero confidence** in the current state of the app. The goal is to build
confidence bottom-up:

1. **Unit tests** — pure Python, no AWS, no file I/O, fast
2. **Integration tests** — real file I/O, real git, no AWS
3. **Agent smoke tests** — real AWS Bedrock, single phase, controlled input
4. **End-to-end tests** — full 10-phase run on a throwaway repo

Do not skip levels. A failing unit test invalidates all integration results.

---

## Level 1 — Unit tests (no AWS, no disk)

### 1a. `tests/unit/test_config.py`

Test `dancode/config.py` in isolation.

| Test | What to assert |
|------|----------------|
| `test_repo_slug_strips_git_suffix` | `repo_slug("git@github.com:org/repo.git")` == `"github.com_org_repo"` |
| `test_repo_slug_https` | `repo_slug("https://github.com/org/repo")` == `"github.com_org_repo"` |
| `test_repo_slug_local_path` | `repo_slug("/home/user/myrepo")` == something stable (no crash) |
| `test_feature_task_defaults` | A `FeatureTask` with only required fields has `phase=PLAN`, `status=PENDING` |
| `test_project_config_round_trip` | `ProjectConfig.model_dump_json()` → `model_validate_json()` produces equal object |
| `test_load_or_create_project_creates` | When slug file doesn't exist, returns new `ProjectConfig` |
| `test_load_or_create_project_loads` | When slug file exists (written by test), loads it correctly |

### 1b. `tests/unit/test_bedrock_check.py`

Mock `boto3.client` and verify behaviour.

| Test | What to assert |
|------|----------------|
| `test_passes_when_bedrock_responds` | `check_bedrock()` returns `True` when `list_foundation_models()` succeeds |
| `test_fails_on_client_error` | Returns `False` (or raises a known exception) when boto3 raises `ClientError` |
| `test_no_maxresults_param` | Confirm `list_foundation_models` is called with no keyword arguments |

### 1c. `tests/unit/test_agent_worker_messages.py`

Test the `AgentWorker` message types directly — no running agent.

| Test | What to assert |
|------|----------------|
| `test_task_status_changed_fields` | `TaskStatusChanged` carries `task_id`, `phase`, `status`, `reason` |
| `test_log_line_fields` | `LogLine` carries `task_id`, `line` |

---

## Level 2 — Integration tests (disk + git, no AWS)

### 2a. `tests/integration/test_paths.py`

Verify `engine/paths.py` resolution logic.

| Test | What to assert |
|------|----------------|
| `test_data_dir_set_before_import` | Setting `COUNCIL_DATA_DIR` before import makes `paths.DATA_DIR` point to that dir |
| `test_resolve_prefers_data_dir` | `paths.resolve("agents", "phase1_plan.yaml")` finds the file in `agents/` of the repo |
| `test_resolve_falls_back_to_repo_root` | When file not in DATA_DIR, falls back to `REPO_ROOT/<subdir>/<file>` |
| `test_init_data_dirs_creates_subdirs` | `init_data_dirs()` creates the expected subdirectories under DATA_DIR |

**Note:** `COUNCIL_DATA_DIR` must be set in the test process environment **before**
the first `import engine.paths`. Use a `conftest.py` fixture that sets the env var
and reloads the module, or run each test in a subprocess.

### 2b. `tests/integration/test_git_worktree.py`

Use `tmp_path` (pytest fixture) to create a real git repo and test worktree operations.

| Test | What to assert |
|------|----------------|
| `test_worktree_created_at_expected_path` | After phase5 runs `git_worktree_create`, the worktree directory exists |
| `test_feature_branch_exists_in_worktree` | `git -C <worktree> branch --show-current` == `FEATURE/<task-id>` |
| `test_worktree_removed_on_cancel` | (If cancel logic is implemented) worktree is cleaned up |

### 2c. `tests/integration/test_session_persistence.py`

| Test | What to assert |
|------|----------------|
| `test_save_and_reload_preserves_all_fields` | Save a `ProjectConfig` with 2 tasks, reload, assert equality |
| `test_phase_advances_on_reload` | Mutate `task.phase`, save, reload — phase is preserved |
| `test_status_blocked_on_reload` | Set `status=BLOCKED`, `blocked_reason="x"`, save, reload — both preserved |

---

## Level 3 — Agent smoke tests (real AWS, controlled inputs)

Run these manually. They cost money. Keep prompts small.

### Setup

```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export COUNCIL_DATA_DIR=~/.config/dancode
```

Create a throwaway git repo:

```bash
mkdir /tmp/smoke-target && cd /tmp/smoke-target
git init && echo "# smoke" > README.md && git add . && git commit -m "init"
```

### 3a. Phase 1 — Plan smoke test

```bash
uv run python3 tests/smoke/run_phase.py \
  --phase phase1_plan \
  --repo /tmp/smoke-target \
  --feature "add a health-check endpoint" \
  --auto-reply "1. REST API. 2. No auth. 3. Returns 200 with JSON {status: ok}. 4. No files off-limits. 5. Done when GET /health returns 200."
```

Expected: agent runs gather_context → ask_questions → (reply injected) → draft_tracks →
write_plan → END. `Planning/add-a-health-check-endpoint/` directory created in the repo.

### 3b. Phase 4 — Dispatch smoke test (requires phase 1 output)

```bash
uv run python3 tests/smoke/run_phase.py \
  --phase phase4_dispatch \
  --repo /tmp/smoke-target \
  --feature "add-a-health-check-endpoint"
```

Expected: `Planning/.../dispatch/SCHEDULE.md` and per-task dispatch files created.

### 3c. Phase 5 — Code smoke test (requires phase 4 output, requires OpenHands)

```bash
uv run python3 tests/smoke/run_phase.py \
  --phase phase5_code \
  --repo /tmp/smoke-target \
  --feature "add-a-health-check-endpoint"
```

Expected: Worktrees created, OpenHands invoked per task, `phase5_status.md` written.

### 3d. Phase 6 — QA smoke test (requires phase 5 output)

```bash
uv run python3 tests/smoke/run_phase.py \
  --phase phase6_qa \
  --repo /tmp/smoke-target \
  --feature "add-a-health-check-endpoint"
```

Expected: QA dispatch files created, OpenHands runs reviews, `reviews/<task-id>-review.md` written.

---

## Level 4 — TUI integration tests

These are manual because Textual's test driver is complex. Run dancode against the
smoke-target repo and verify each UI action by hand.

| Step | Action | Expected |
|------|--------|----------|
| Launch | `dancode /tmp/smoke-target` | TUI loads, no traceback, "Press n to create feature" |
| New feature | Press `n`, fill form, submit | Task appears in left panel with status PENDING |
| Auto-start | Task should move to RUNNING immediately | Phase 1 label visible |
| Waiting gate | Phase 1 hits `wait_for_answers` | Status changes to WAITING |
| Feedback | Press `f`, type answers, submit | Status changes back to RUNNING |
| Approve | Press `a` | Phase advances (if approve gate is wired) |
| Cancel | Press `c` on a RUNNING task | Status changes to CANCELLED |
| Quit | Press `q` | App exits cleanly, no traceback |
| Restart | `dancode /tmp/smoke-target` again | Task still shows in list with last known phase/status |

---

## Suggested file structure

```
tests/
  README.md                      (this file)
  conftest.py                    (shared fixtures: tmp git repo, env var setup)
  unit/
    test_config.py
    test_bedrock_check.py
    test_agent_worker_messages.py
  integration/
    test_paths.py
    test_git_worktree.py
    test_session_persistence.py
  smoke/
    run_phase.py                 (CLI helper: run a single phase with optional auto-reply)
  e2e/
    README.md                    (manual walkthrough steps)
```

---

## Running tests

```bash
# Unit + integration only (fast, no AWS)
uv run pytest tests/unit tests/integration -v

# All automated tests
uv run pytest tests/ -v --ignore=tests/smoke --ignore=tests/e2e

# Single file
uv run pytest tests/unit/test_config.py -v
```

---

## Known gaps to fix before trusting the smoke tests

1. **`tests/smoke/run_phase.py` does not exist yet** — needs to be written.
2. **`human_reply` blocks in phases 1/2/3** are blocking — the smoke runner needs an
   `--auto-reply` mechanism (inject reply text into `shared_state` before the block runs,
   or patch `HumanReplyBlock.run()` in tests).
3. **`engine/paths.py` import-time evaluation** — any test that imports `engine` must
   set `COUNCIL_DATA_DIR` first. Use a `conftest.py` autouse fixture.
4. **Phase 5/6 require OpenHands** to be installed and on `$PATH`. Skip these tests
   if `which openhands` fails.
