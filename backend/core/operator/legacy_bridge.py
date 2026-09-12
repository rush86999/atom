"""Legacy browser tool bridge — retirement of the old dual-mode dispatch.

History: mcp_service.execute_tool carried a "Computer Use Execution
(Dual Mode: Desktop Bridge vs Cloud Headless)" chain for
browser_navigate/click/type/screenshot (+ unadvertised tab/proxy/monitor
names). Both modes were dead in production:

- cloud: imported core.cloud_browser_service, a module that no longer
  exists → always "Error: Cloud browser service not available."
- desktop: called notification_manager.send_to_desktop, which
  ConnectionManager does not implement → AttributeError; the covpush
  tests only passed because they mocked it and emptied the registry.

Worse, the desktop fallback returned "[SIMULATION] Navigated to X"
strings — agents recorded fake successes from a browser that never
moved. Retired 2026-09-12.

This bridge routes the four advertised legacy names to the REAL governed
Playwright path (tools/browser_tool.py: SSRF guard on navigate, locator
match-confidence on click, BrowserAudit everywhere) using a shared
per-agent session, and answers every other legacy name with an explicit
retirement error — never a simulation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Names that get real delegation.
LEGACY_DELEGATED = frozenset({
    "browser_navigate", "browser_click", "browser_type", "browser_screenshot",
})

# Every name the old chain handled; anything not delegated is retired.
LEGACY_BROWSER_TOOL_NAMES = frozenset({
    "browser_navigate", "browser_click", "browser_type", "browser_screenshot",
    "browser_new_tab", "browser_switch_tab", "browser_click_coords",
    "list_browser_tabs", "browser_save_session", "browser_set_proxy",
    "browser_monitor", "browser_wait_for_selector",
    "browser_extract_content", "browser_upload_file",
    "browser_download_file",
})

# shared-session key → browser session id. BrowserSessionManager owns the
# real lifecycle (TTL cleanup); stale ids here are detected and re-created.
_shared_sessions: Dict[str, str] = {}


def _funcs():
    """Indirection so tests can stub the browser functions without a
    Playwright install."""
    import tools.browser_tool as browser_tool
    return browser_tool


def _shared_key(context: Dict[str, Any]) -> str:
    return (context.get("agent_id") or context.get("user_id")
            or "shared-legacy-browser")


async def _shared_session_id(context: Dict[str, Any]) -> Optional[str]:
    """Get-or-create the per-agent browser session used by legacy calls."""
    funcs = _funcs()
    key = _shared_key(context)
    session_id = _shared_sessions.get(key)
    if session_id and funcs.get_browser_manager().get_session(session_id):
        return session_id
    user_id = context.get("user_id") or "system"
    agent_id = context.get("agent_id")
    created = await funcs.browser_create_session(
        user_id=user_id, agent_id=agent_id)
    if not created.get("success"):
        return None
    _shared_sessions[key] = created["session_id"]
    return created["session_id"]


def _retired(tool_name: str) -> Dict[str, Any]:
    return {
        "success": False,
        "error": (
            f"{tool_name} was retired (2026-09-12): the old cloud/desktop "
            f"dispatch no longer exists. Use the governed browser tools "
            f"(browser_create_session + browser_navigate/click/fill_form/"
            f"screenshot) or the computer-use operator "
            f"(operator_start_task)."
        ),
        "retired": True,
    }


async def dispatch_legacy_browser_tool(tool_name: str,
                                       arguments: Dict[str, Any],
                                       context: Optional[Dict[str, Any]] = None
                                       ) -> Any:
    """Route one legacy browser_* call to the real governed path."""
    context = context or {}
    if tool_name not in LEGACY_BROWSER_TOOL_NAMES:
        return _retired(tool_name)

    try:
        funcs = _funcs()
    except Exception as exc:
        return {"success": False,
                "error": f"browser automation unavailable "
                         f"({type(exc).__name__}: {exc})"}

    if tool_name not in LEGACY_DELEGATED:
        return _retired(tool_name)

    session_id = await _shared_session_id(context)
    if not session_id:
        return {"success": False,
                "error": "could not open a browser session for the legacy "
                         "browser tool call"}
    user_id = context.get("user_id") or "system"
    agent_id = context.get("agent_id")

    if tool_name == "browser_navigate":
        url = arguments.get("url")
        if not url:
            return {"success": False, "error": "url is required"}
        return await funcs.browser_navigate(session_id, url, user_id=user_id)

    if tool_name == "browser_click":
        selector = arguments.get("selector")
        if selector:
            return await funcs.browser_click(
                session_id, selector, user_id=user_id,
                agent_id=agent_id)
        coords = [arguments.get("x"), arguments.get("y")]
        if coords[0] is None or coords[1] is None:
            return {"success": False,
                    "error": "selector or x/y coordinates are required"}
        session = funcs.get_browser_manager().get_session(session_id)
        x = max(0, int(coords[0]))
        y = max(0, int(coords[1]))
        await session.page.mouse.click(x, y)
        return {"success": True, "session_id": session_id,
                "coordinates": [x, y]}

    if tool_name == "browser_type":
        text = arguments.get("text")
        if text is None:
            return {"success": False, "error": "text is required"}
        selector = arguments.get("selector")
        if selector:
            return await funcs.browser_fill_form(
                session_id, {selector: text}, user_id=user_id,
                agent_id=agent_id)
        session = funcs.get_browser_manager().get_session(session_id)
        await session.page.keyboard.type(str(text))
        return {"success": True, "session_id": session_id}

    if tool_name == "browser_screenshot":
        return await funcs.browser_screenshot(session_id, user_id=user_id)

    return _retired(tool_name)
