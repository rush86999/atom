"""Bounds on the tool catalog an agent renders into its ReAct prompt.

Bug class this closes (2026-09-16 data-access audit, gap #4): the tool
catalog is the one list that grew without a ceiling. Two unbounded paths:

1. ``session_tools`` — every ``mcp_tool_search`` appends its top-5 results
   and NOTHING ever evicts; a twenty-search session carried ~100 stale tool
   definitions in EVERY subsequent prompt for the rest of the run.
2. the rendered ``AVAILABLE TOOLS`` block — core tools + session tools +
   (for agents with an explicit ``allowed_tools`` list) the whole configured
   set, serialized verbatim with no cap.

The mature-harness consensus (Claude Code/Cursor/Devin tool surfaces, MCP
tool-RAG discussions, Speakeasy/Lunar tool-overload writeups): dozens of
tool schemas in context measurably degrade tool selection; the fix is a
bounded always-visible core + lazy retrieval for the tail. This repo
already has the retrieval half (``mcp_tool_search``); this module is the
bounding half.

Pure functions, env-tunable, importable from both agent loops without
cycles.
"""
import json
import os
from typing import Any, Dict, List, Tuple

_DEFAULT_SESSION_CAP = 40
_DEFAULT_PROMPT_CAP = 120


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except (TypeError, ValueError):
        return default


def session_tool_cap() -> int:
    """Max lazily-loaded tools carried in one agent session (FIFO beyond it)."""
    return max(0, _env_int("ATOM_AGENT_SESSION_TOOLS_CAP", _DEFAULT_SESSION_CAP))


def prompt_tool_cap() -> int:
    """Max tool entries rendered into one AVAILABLE TOOLS block."""
    return max(1, _env_int("ATOM_AGENT_TOOL_PROMPT_CAP", _DEFAULT_PROMPT_CAP))


def trim_session_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupe by name, then FIFO-trim to ``session_tool_cap``.

    Newest tools survive (they answer the CURRENT question); the oldest
    lazily-loaded entries drop off first. A cap of 0 disables lazy
    accumulation entirely (core tools only).
    """
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for tool in tools:
        name = tool.get("name")
        if name in seen:
            continue
        seen.add(name)
        deduped.append(tool)
    cap = session_tool_cap()
    if cap <= 0:
        return []
    if len(deduped) <= cap:
        return deduped
    return deduped[-cap:]


def render_tool_catalog(tools: List[Dict[str, Any]]) -> Tuple[str, int]:
    """JSON name+description block for ``tools``, capped at ``prompt_tool_cap``.

    Returns ``(rendered_json, hidden_count)``. Over the cap the block keeps
    the first ``cap`` entries and the caller should surface ``hidden_count``
    with the mcp_tool_search pointer (see the agent loops) — a model that
    cannot see a tool must at least be told the catalog continues.
    """
    cap = prompt_tool_cap()
    shown = tools[:cap]
    rendered = json.dumps(
        [{"name": t.get("name"), "description": t.get("description", "")}
         for t in shown],
        indent=2,
        default=str,
    )
    return rendered, max(0, len(tools) - len(shown))
