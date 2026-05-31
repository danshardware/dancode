# dancode

A multi-agent coding workflow orchestrator backed by AWS Bedrock.

Point it at a git repo, describe a feature, and it drives a 10-phase
AI pipeline from planning through finalization — managing parallel git
worktrees, invoking OpenHands for coding tasks, and keeping you in
control at every human gate.

## Quickstart

```bash
uv sync
dancode /path/to/your/repo
```

Press **n** to create a new feature. Dancode handles the rest.

## Requirements

- Python 3.12+
- AWS credentials with Bedrock access (`AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` or an IAM role)
- [OpenHands](https://github.com/All-Hands-AI/OpenHands) installed and on `$PATH`

## The 10-phase pipeline

| Phase | Name | Model |
|---|---|---|
| 1 | Plan | Claude Sonnet |
| 2 | Jank Control | Claude Opus |
| 3 | Refine | Claude Sonnet |
| 4 | Dispatch | Nova Lite |
| 5 | Code (OpenHands) | MiniMax M2.5 |
| 6 | QA | Nova Lite |
| 7 | Consolidate | Claude Sonnet |
| 8 | Human Review | Claude Sonnet |
| 9 | Docs | DeepSeek V3 |
| 10 | Finalize | Nova Lite |

## Session state

Progress is saved to `~/.config/dancode/projects/<repo-slug>.json`.
Restart dancode at any time and it resumes where it left off.

## Docker

```bash
REPO_PATH=/path/to/repo docker compose up
```

AWS credentials are inherited from the host environment.

## Debug a single agent

```bash
dancode --agent phase1_plan --prompt "add user authentication"
```
