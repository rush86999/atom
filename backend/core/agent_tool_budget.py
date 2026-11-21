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
bounding half. The prompt projection also carries bounded registered
parameter *names* (never defaults/examples/nested descriptions) so a model
does not have to guess argument keys.

Pure functions. The session and prompt caps stay env-tunable; per-tool
parameter hints use fixed small bounds. Importable from both agent loops
without cycles.
"""
import json
import os
from typing import Any, Dict, List, Tuple

_DEFAULT_SESSION_CAP = 40
_DEFAULT_PROMPT_CAP = 120
_PARAM_NAME_CAP = 12
_PARAM_BYTES_CAP = 256


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


def _names_from_parameters(value: Any) -> List[str]:
    """Project parameter names from a flat mapping or MCP object schema.

    Registered tools pass name -> type mappings; MCP tools pass an object
    schema whose ``properties`` hold the names. Only keys are copied, so
    types and other metadata values never reach the prompt.
    """
    if not isinstance(value, dict):
        return []
    properties = value.get("properties")
    if isinstance(properties, dict):
        return [k for k in properties if isinstance(k, str)]
    if value.get("type") == "object":
        return []
    return [k for k, v in value.items()
            if isinstance(k, str) and isinstance(v, str)]


def _registered_parameter_names(tool: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    seen = set()
    for key in ("parameters", "inputSchema"):
        for name in _names_from_parameters(tool.get(key)):
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _bound_parameter_names(names: List[str]) -> List[str]:
    bounded: List[str] = []
    for name in names[:_PARAM_NAME_CAP]:
        candidate = bounded + [name]
        size = len(json.dumps(
            candidate, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8"))
        if size > _PARAM_BYTES_CAP:
            break
        bounded = candidate
    return bounded


def render_tool_catalog(tools: List[Dict[str, Any]]) -> Tuple[str, int]:
    """JSON name+description+parameter-name block for ``tools``.

    Parameter names come only from registered metadata and are bounded per
    tool (both count and serialized bytes). Names are omitted when metadata
    supplies none, so tools without registrations keep the old projection.
    Returns ``(rendered_json, hidden_count)``. Over the cap the block keeps
    the first ``cap`` entries and the caller should surface ``hidden_count``
    with the mcp_tool_search pointer (see the agent loops) — a model that
    cannot see a tool must at least be told the catalog continues.
    """
    cap = prompt_tool_cap()
    shown = tools[:cap]
    projected: List[Dict[str, Any]] = []
    for tool in shown:
        entry = {
            "name": tool.get("name"),
            "description": tool.get("description", ""),
        }
        parameter_names = _bound_parameter_names(
            _registered_parameter_names(tool)
        )
        if parameter_names:
            entry["parameter_names"] = parameter_names
        projected.append(entry)
    rendered = "[\n" + ",\n".join(
        json.dumps(entry, default=str) for entry in projected
    ) + "\n]"
    return rendered, max(0, len(tools) - len(shown))
