"""Tool discovery tools — list and search the registered tool registry."""
from __future__ import annotations
from tools import ToolContext, tool, _REGISTRY


@tool
def list_tools(context: ToolContext) -> str:
    """List all registered tools with their name and description.

    Returns a formatted string: one tool per line in the format:
      <name>: <description>
    """
    lines = []
    for name, func in sorted(_REGISTRY.items()):
        doc = (func.__doc__ or "No description.").strip().split("\n")[0]
        lines.append(f"{name}: {doc}")
    return "\n".join(lines) if lines else "(no tools registered)"


@tool
def search_tools(query: str, context: ToolContext) -> str:
    """Search registered tools by semantic description.

    Returns the subset of tools relevant to the query, with their names
    and descriptions. Uses keyword matching to find relevant tools.

    Example queries:
      "file reading and writing"
      "web browsing and scraping"
      "memory storage and retrieval"
      "scheduling and timing"

    Returns:
        str: Newline-separated list of matching tools in format 'name: description'.
             Returns '(no matching tools)' if no tools match.
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    results = []

    for name, func in sorted(_REGISTRY.items()):
        doc = (func.__doc__ or "").lower()
        # Check if any query word appears in the tool name or description
        if any(word in name.lower() or word in doc for word in query_words):
            first_line = (func.__doc__ or "No description.").strip().split("\n")[0]
            results.append(f"{name}: {first_line}")

    return "\n".join(results) if results else "(no matching tools)"