"""Mustache prompt rendering — resolves {{config.*}} and {{state.*}} in system prompts."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml
import chevron


class TemplateRenderError(KeyError):
    """Raised when a template variable cannot be resolved."""
    pass


# Keys from shared state that must never be forwarded to the LLM.
# Also excludes any key beginning with "_".
_FORBIDDEN_STATE_KEYS: frozenset[str] = frozenset({
    "logger",
    "tool_context",
    "agent_config",
})


@functools.lru_cache(maxsize=1)
def _load_config_dir() -> dict[str, Any]:
    """Load all YAMLs from the config/ directory, keyed by file stem.

    Respects the DATA_DIR override layer: a file at DATA_DIR/config/<stem>.yaml
    shadows the built-in copy at REPO_ROOT/config/<stem>.yaml.
    Cached on first call (config is not expected to change within a session).
    """
    from engine.paths import DATA_DIR, REPO_ROOT

    builtin_dir = REPO_ROOT / "config"
    override_dir = DATA_DIR / "config"

    stems: set[str] = set()
    if builtin_dir.is_dir():
        stems.update(p.stem for p in builtin_dir.glob("*.yaml"))
    if override_dir.is_dir():
        stems.update(p.stem for p in override_dir.glob("*.yaml"))

    result: dict[str, Any] = {}
    for stem in stems:
        override_path = override_dir / f"{stem}.yaml"
        builtin_path = builtin_dir / f"{stem}.yaml"
        path = override_path if override_path.exists() else builtin_path
        with path.open(encoding="utf-8") as fh:
            result[stem] = yaml.safe_load(fh) or {}
    return result


def _build_state_context(shared: dict) -> dict:
    """Build the 'state' namespace from shared, stripping forbidden and private keys."""
    return {
        k: v
        for k, v in shared.items()
        if k not in _FORBIDDEN_STATE_KEYS and not k.startswith("_")
    }


def render_prompt(template: str, shared: dict) -> str:
    """
    Render a Mustache template string using config and state namespaces.

    Supported syntax:
        {{config.schedules.daily_run_time}}   — from config/<file>.yaml
        {{state.current_task}}                — from shared state (top-level or nested)
        {{state.messages.0.content}}          — dot-notation into nested structures
        {{#state.todo_list}}...{{/state.todo_list}} — Mustache sections/loops

    Raises:
        TemplateRenderError: if a referenced variable is missing.
    """
    # Fast path — skip work if there are no mustache tokens
    if "{{" not in template:
        return template

    context = {
        "config": _load_config_dir(),
        "state": _build_state_context(shared),
    }

    try:
        return chevron.render(template, context, warn=False)
    except Exception as exc:
        raise TemplateRenderError(
            f"Failed to render prompt template: {exc}\n"
            f"Template (first 200 chars): {template[:200]}"
        ) from exc
