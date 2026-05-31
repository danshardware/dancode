"""Inline guardrails for the search_web and scrape_url tools.

Each check runs call_llm() in a fresh, isolated context — completely separate
from the agent's conversation history — so guardrail tokens never inflate the
main context window.

Public API:
  pre_search(query)          -> (verdict, reason)   LLM + blacklist
  post_search(query, results)-> (verdict, reason)   LLM
  pre_scrape(url)            -> (verdict, reason)   blacklist only (no LLM)
  post_scrape(url, content)  -> (verdict, reason)   LLM
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "browser_guardrails.yaml"
_config: dict | None = None


def _get_config() -> dict:
    """Load browser guardrails config, preferring a DATA_DIR override."""
    from engine.paths import resolve as _resolve
    global _config
    if _config is None:
        override_path = _resolve("config", "browser_guardrails.yaml")
        load_path = override_path if override_path.exists() else _CONFIG_PATH
        with open(load_path, encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def run_guardrail(system_prompt: str, user_content: str, *, model_id: str) -> tuple[str, str]:
    """Run one guardrail LLM call in an isolated context.

    Returns (verdict, reason).
    verdict is one of: 'approved', 'rejected', 'suspicious'.
    Falls back to 'approved' on infrastructure failure so guardrail outages
    never silently block legitimate work.
    """
    from engine.llm import call_llm
    try:
        parsed, _in_tok, _out_tok = call_llm(
            model_id=model_id,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        verdict = str(parsed.get("verdict", "approved")).lower().strip()
        reason = str(parsed.get("reason", ""))
        logger.info("guardrail verdict=%s reason=%s", verdict, reason)
        return verdict, reason
    except Exception as exc:
        logger.warning("guardrail LLM call failed (%s) — defaulting to approved", exc)
        return "approved", f"guardrail unavailable: {exc}"


def check_blacklists(text: str) -> tuple[bool, str]:
    """Check text against the blocked_patterns and blocked_domains from config.

    Returns (blocked, reason). blocked=True means the content is forbidden.
    Uses only regex/string matching — no LLM cost.
    """
    config = _get_config()
    guardrails = config.get("browser_guardrails", {})
    text_lower = text.lower()

    for pattern in guardrails.get("blocked_patterns", []):
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True, f"Matches blocked pattern: {pattern}"

    for domain in guardrails.get("blocked_domains", []):
        if domain.lower() in text_lower:
            return True, f"Matches blocked domain: {domain}"

    return False, ""


def pre_search(query: str) -> tuple[str, str]:
    """Pre-execution guardrail for search_web.

    Runs a blacklist fast-path first (free), then an LLM topic-appropriateness
    check in a fresh context. Returns (verdict, reason).
    """
    blocked, reason = check_blacklists(query)
    if blocked:
        return "rejected", reason

    config = _get_config()
    section = config.get("search_guardrails", {})
    system_prompt = section.get("pre_execution_prompt", "")
    model_id = section.get("model_id", "us.amazon.nova-lite-v1:0")

    if not system_prompt:
        return "approved", ""

    return run_guardrail(
        system_prompt=system_prompt,
        user_content=f"Proposed search query: {query}",
        model_id=model_id,
    )


def post_search(query: str, results: str) -> tuple[str, str]:
    """Post-execution guardrail for search_web.

    Checks that results are safe, relevant, and injection-free.
    Returns (verdict, reason).
    """
    config = _get_config()
    section = config.get("search_guardrails", {})
    system_prompt = section.get("post_execution_prompt", "")
    model_id = section.get("model_id", "us.amazon.nova-lite-v1:0")

    if not system_prompt:
        return "approved", ""

    user_content = (
        f"Original search query: {query}\n\n"
        f"Search results to validate:\n{results[:3000]}"
    )
    return run_guardrail(
        system_prompt=system_prompt,
        user_content=user_content,
        model_id=model_id,
    )


def pre_scrape(url: str) -> tuple[str, str]:
    """Pre-execution guardrail for scrape_url.

    Blacklist-only check (no LLM) as specified — uses the existing
    blocked_patterns and blocked_domains from browser_guardrails config.
    Returns (verdict, reason).
    """
    blocked, reason = check_blacklists(url)
    if blocked:
        return "rejected", reason
    return "approved", ""


def post_scrape(url: str, content: str) -> tuple[str, str]:
    """Post-execution guardrail for scrape_url.

    Checks scraped content for injection attempts, malware links, and
    other unwanted material. Returns (verdict, reason).
    """
    config = _get_config()
    section = config.get("scrape_guardrails", {})
    system_prompt = section.get("post_execution_prompt", "")
    model_id = section.get("model_id", "us.amazon.nova-lite-v1:0")

    if not system_prompt:
        return "approved", ""

    user_content = (
        f"Source URL: {url}\n\n"
        f"Scraped content to validate:\n{content[:3000]}"
    )
    return run_guardrail(
        system_prompt=system_prompt,
        user_content=user_content,
        model_id=model_id,
    )
