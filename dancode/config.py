"""Global config models for dancode — persisted to ~/.config/dancode/."""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".config" / "dancode"
PROJECTS_DIR = CONFIG_DIR / "projects"
LOGS_DIR = CONFIG_DIR / "logs"


class TaskPhase(int, Enum):
    PLAN = 1
    JANK = 2
    REFINE = 3
    DISPATCH = 4
    CODE = 5
    QA = 6
    CONSOLIDATE = 7
    REVIEW = 8
    DOCS = 9
    FINALIZE = 10


PHASE_NAMES = {
    TaskPhase.PLAN: "Plan",
    TaskPhase.JANK: "Jank Control",
    TaskPhase.REFINE: "Refine",
    TaskPhase.DISPATCH: "Dispatch",
    TaskPhase.CODE: "Code",
    TaskPhase.QA: "QA",
    TaskPhase.CONSOLIDATE: "Consolidate",
    TaskPhase.REVIEW: "Human Review",
    TaskPhase.DOCS: "Docs",
    TaskPhase.FINALIZE: "Finalize",
}

PHASE_AGENTS = {
    TaskPhase.PLAN: "phase1_plan",
    TaskPhase.JANK: "phase2_jank",
    TaskPhase.REFINE: "phase3_refine",
    TaskPhase.DISPATCH: "phase4_dispatch",
    TaskPhase.CODE: "phase5_code",
    TaskPhase.QA: "phase6_qa",
    TaskPhase.CONSOLIDATE: "phase7_consolidate",
    TaskPhase.REVIEW: "phase8_review",
    TaskPhase.DOCS: "phase9_docs",
    TaskPhase.FINALIZE: "phase10_finalize",
}


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"   # at a human gate
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class FeatureTask(BaseModel):
    task_id: str
    feature_name: str
    feature_description: str
    worktree_path: Optional[str] = None
    feature_branch: Optional[str] = None
    phase: TaskPhase = TaskPhase.PLAN
    status: TaskStatus = TaskStatus.PENDING
    openhands_model: str = "minimax.minimax-m2.5"
    session_ids: dict[str, str] = Field(default_factory=dict)  # phase_name → session_id
    blocked_reason: Optional[str] = None


class ProjectConfig(BaseModel):
    clone_url: str
    local_path: str
    tasks: list[FeatureTask] = Field(default_factory=list)

    def save(self, slug: str) -> None:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path = PROJECTS_DIR / f"{slug}.json"
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, slug: str) -> "ProjectConfig | None":
        path = PROJECTS_DIR / f"{slug}.json"
        if not path.exists():
            return None
        return cls.model_validate_json(path.read_text())

    def get_task(self, task_id: str) -> FeatureTask | None:
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def upsert_task(self, task: FeatureTask) -> None:
        for i, t in enumerate(self.tasks):
            if t.task_id == task.task_id:
                self.tasks[i] = task
                return
        self.tasks.append(task)


def repo_slug(local_path: str, clone_url: str | None) -> str:
    """Return a stable filesystem-safe slug for a repo."""
    if clone_url:
        # Normalize: strip scheme, trailing .git, replace non-alnum with _
        key = re.sub(r"^(https?://|git@|ssh://)", "", clone_url)
        key = re.sub(r"\.git$", "", key)
        key = re.sub(r"[^a-zA-Z0-9._-]", "_", key)
        return key[:80]
    # Local-only repo: hash the absolute path
    digest = hashlib.sha256(local_path.encode()).hexdigest()[:12]
    stem = Path(local_path).name
    return f"{stem}_{digest}"


def load_or_create_project(local_path: str, clone_url: str | None) -> tuple[ProjectConfig, str]:
    """Load existing ProjectConfig or create a new one. Returns (config, slug)."""
    slug = repo_slug(local_path, clone_url)
    config = ProjectConfig.load(slug)
    if config is None:
        config = ProjectConfig(clone_url=clone_url or "", local_path=local_path)
    return config, slug
