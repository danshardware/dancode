"""Tool registry for the Council agent system."""

from __future__ import annotations

import functools
import inspect
import sys
import os
from dataclasses import dataclass, field
from typing import Callable, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conversation.conversation import BedrockTool


@dataclass
class ToolContext:
    agent_id: str
    session_id: str
    allowed_paths: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)
    fetched_cache: set[str] = field(default_factory=set)
    todo_list: list = field(default_factory=list)
    # Channel context forwarded from shared state so sub-agents spawned via
    # spawn_agent() can post to Discord and suspend correctly.
    channel_context: dict | None = None
    _channel_adapter: object | None = None
    _discord_loop: object | None = None


_REGISTRY: dict[str, Callable] = {}

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def tool(func: Callable) -> Callable:
    """Register a function as an agent tool. The last parameter must be `context: ToolContext`."""
    _REGISTRY[func.__name__] = func
    return func


def get_tool(name: str, context: ToolContext) -> BedrockTool | None:
    """Return a BedrockTool for `name` with ToolContext pre-bound, or None if not found."""
    func = _REGISTRY.get(name)
    if func is None:
        return None
    return _make_bedrock_tool(func, context)


def list_tools() -> list[str]:
    return list(_REGISTRY.keys())


def _make_bedrock_tool(func: Callable, context: ToolContext) -> BedrockTool:
    sig = inspect.signature(func)
    params_without_context = {
        k: v for k, v in sig.parameters.items() if k != "context"
    }

    @functools.wraps(func)
    def wrapper(**kwargs: Any) -> Any:
        return func(**kwargs, context=context)

    props: dict[str, dict] = {}
    required: list[str] = []
    for pname, param in params_without_context.items():
        ann = func.__annotations__.get(pname, str)
        props[pname] = {
            "type": _TYPE_MAP.get(ann, "string"),
            "description": f"Parameter '{pname}'",
        }
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    tool_spec = {
        "name": func.__name__,
        "description": func.__doc__ or "",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": props,
                "required": required,
            }
        },
    }
    return BedrockTool(wrapper, tool_spec=tool_spec)


def _load_all_tools() -> None:
    """Import all tool submodules so their @tool decorators register into _REGISTRY."""
    import importlib
    from pathlib import Path
    tools_dir = Path(__file__).parent
    for path in sorted(tools_dir.glob("*.py")):
        if path.stem not in ("__init__",):
            importlib.import_module(f"tools.{path.stem}")


_load_all_tools()
