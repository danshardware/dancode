"""Bedrock LLM bridge — wraps conversation.Conversation for agent block use."""

from __future__ import annotations

import re
import sys
import os
import time
from typing import Any

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conversation.conversation import Conversation, Message, BedrockTool

_RETRY_EXCEPTIONS = (
    "ReadTimeoutError",
    "ConnectTimeoutError",
    "EndpointConnectionError",
    "ServiceUnavailableError",
    "ThrottlingException",
    "ModelTimeoutException",
)


class LLMUnavailableError(Exception):
    """Raised when all retry attempts for a transient LLM/network error are exhausted."""
    pass


def call_llm(
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    tools: list[BedrockTool] | None = None,
    max_retries: int = 3,
    tool_callback=None,
) -> tuple[dict[str, Any], int, int]:
    """
    Call Bedrock, handle any native tool-use loop, then parse the final text as YAML.
    Retries up to max_retries times on transient network/throttle errors.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return _call_once(model_id, system_prompt, messages, tools, tool_callback=tool_callback)
        except Exception as exc:
            exc_name = type(exc).__name__
            exc_str = str(exc)
            is_transient = any(r in exc_str or r in exc_name for r in _RETRY_EXCEPTIONS)
            if is_transient and attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s
                print(f"[llm] Transient error ({exc_name}), retrying in {wait}s… "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                last_exc = exc
            elif is_transient:
                # All retries exhausted on a connectivity/throttle error
                raise LLMUnavailableError(
                    f"LLM unavailable after {max_retries} attempts: {exc_name}: {exc_str}"
                ) from exc
            else:
                raise
    raise LLMUnavailableError(f"LLM unavailable: {last_exc}") from last_exc  # type: ignore[misc]


def _call_once(
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    tools: list[BedrockTool] | None = None,
    tool_callback=None,
) -> tuple[dict[str, Any], int, int]:
    conv = Conversation(
        model_id=model_id,
        system_prompts=system_prompt,
        tools=tools or [],
    )

    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            conv.conversation.append(Message(msg["role"], text=content))
        else:
            conv.conversation.append(Message(msg["role"], content=content))

    # Bedrock requires the conversation to end with a user turn. If the last
    # message is from the assistant (e.g. summary from a previous block), strip
    # trailing assistant messages so the model can produce the next turn cleanly.
    while conv.conversation and conv.conversation[-1].role == "assistant":
        conv.conversation.pop()

    tool_calls: list = []
    _role, text = conv.call_model(tool_event_log=tool_calls, tool_callback=tool_callback)
    text = text.strip()  # Strip trailing/leading whitespace for Bedrock validation
    parsed = _parse_yaml_response(text)
    parsed["_raw_response"] = text
    parsed["_tool_calls"] = tool_calls
    return parsed, conv.input_tokens, conv.output_tokens


def call_llm_conv(
    conv: "Conversation",
    context_window: int | None = None,
    include_tools: bool = True,
    tool_event_log: list | None = None,
    tool_callback=None,
    max_retries: int = 3,
) -> tuple[dict[str, Any], int, int]:
    """Call Bedrock using a persistent Conversation object (reused across turns).

    Handles retries for transient errors, rolling back conversation state on
    each failure so the object remains clean for the next attempt.

    Returns (parsed, input_tokens_delta, output_tokens_delta).
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        # Snapshot state for rollback
        conv_len = len(conv.conversation)
        tok_in_before = conv.input_tokens
        tok_out_before = conv.output_tokens
        try:
            tool_calls: list = tool_event_log if tool_event_log is not None else []
            _role, text = conv.call_model(
                tool_event_log=tool_calls,
                tool_callback=tool_callback,
                context_window=context_window,
                include_tools=include_tools,
            )
            text = text.strip()
            parsed = _parse_yaml_response(text)
            parsed["_raw_response"] = text
            parsed["_tool_calls"] = tool_calls
            return (
                parsed,
                conv.input_tokens - tok_in_before,
                conv.output_tokens - tok_out_before,
            )
        except Exception as exc:
            # Rollback conversation and token state before any retry
            del conv.conversation[conv_len:]
            conv.input_tokens = tok_in_before
            conv.output_tokens = tok_out_before
            exc_name = type(exc).__name__
            exc_str = str(exc)
            is_transient = any(r in exc_str or r in exc_name for r in _RETRY_EXCEPTIONS)
            if is_transient and attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"[llm] Transient error ({exc_name}), retrying in {wait}s… "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                last_exc = exc
            elif is_transient:
                raise LLMUnavailableError(
                    f"LLM unavailable after {max_retries} attempts: {exc_name}: {exc_str}"
                ) from exc
            else:
                raise
    raise LLMUnavailableError(f"LLM unavailable: {last_exc}") from last_exc  # type: ignore[misc]


def _regex_extract_fields(text: str) -> dict[str, Any]:
    """Regex-based fallback for extracting agent response fields when YAML.safe_load fails.

    Handles the common case where a plain scalar value contains ': ' (colon-space)
    which is forbidden in YAML plain scalars and causes safe_load to raise.  Only
    works for flat (non-nested) key: value action_input fields.
    """
    result: dict[str, Any] = {}
    action_m = re.search(r"^action\s*:\s*(\S+)", text, re.MULTILINE)
    if not action_m:
        return result
    result["action"] = action_m.group(1).strip().rstrip("#").strip()

    reasoning_m = re.search(r'^reasoning\s*:\s*"?(.+?)"?\s*$', text, re.MULTILINE)
    if reasoning_m:
        result["reasoning"] = reasoning_m.group(1)

    # Extract action_input block: indented lines immediately under 'action_input:'
    ai_block_m = re.search(
        r"^action_input\s*:\s*\n((?:[ \t]+.*(?:\n|$))+)", text, re.MULTILINE
    )
    if ai_block_m:
        ai: dict[str, str] = {}
        for line in ai_block_m.group(1).splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Split on first ': ' to capture key and the full rest-of-line as value.
            # This correctly preserves ': ' within the value itself (e.g. commit messages).
            kv_m = re.match(r"^([\w][\w_-]*)\s*:\s*(.*)", stripped)
            if kv_m:
                val = kv_m.group(2).strip()
                # Strip surrounding quotes if the LLM quoted the whole value
                if len(val) >= 2 and (
                    (val[0] == '"' and val[-1] == '"')
                    or (val[0] == "'" and val[-1] == "'")
                ):
                    val = val[1:-1]
                ai[kv_m.group(1)] = val
        if ai:
            result["action_input"] = ai
    return result


def _parse_yaml_response(text: str) -> dict[str, Any]:
    """Extract and parse YAML from an LLM response, trying multiple strategies."""
    # Strategy 1: fenced ```yaml ... ``` block
    fenced = re.search(r"```(?:yaml)?\s*\n(.*?)```", text, re.DOTALL)
    if fenced:
        try:
            result = yaml.safe_load(fenced.group(1).strip())
            if isinstance(result, dict):
                return result
        except Exception:
            pass
        # Strategy 1b: YAML parse of fenced block failed (e.g. unquoted values containing
        # ': ') — fall back to regex extraction which handles colon-space correctly.
        extracted = _regex_extract_fields(fenced.group(1).strip())
        if extracted.get("action"):
            return extracted

    # Strategy 2: parse the whole response as YAML
    try:
        result = yaml.safe_load(text.strip())
        if isinstance(result, dict) and "action" in result:
            return result
    except Exception:
        pass

    # Strategy 3: find the first YAML-like block (lines until a blank line)
    for block in re.split(r"\n{2,}", text):
        block = block.strip()
        if block.startswith("reasoning:") or block.startswith("action:"):
            try:
                result = yaml.safe_load(block)
                if isinstance(result, dict) and "action" in result:
                    return result
            except Exception:
                pass

    # Strategy 4: pull out just the action: line
    action_match = re.search(r"^action\s*:\s*(\S+)", text, re.MULTILINE)
    if action_match:
        action = action_match.group(1).strip().rstrip("#").strip()
        reasoning_match = re.search(r"^reasoning\s*:\s*(.+)", text, re.MULTILINE)
        result: dict[str, Any] = {"action": action}
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1).strip().strip('"')
        return result

    return {"action": "default", "raw_response": text}
