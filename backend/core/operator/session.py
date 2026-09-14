"""OperatorSession — the browser actuation backend for the computer-use
operator.

Built on the production Playwright sessions from tools/browser_tool.py
(BrowserSessionManager: 1920x1080 chromium contexts, TTL cleanup) rather
than a second browser stack. Selector-based actions and navigation
delegate to the governed browser_tool functions (SSRF guard, locator
match-confidence, BrowserAudit); coordinate/keyboard actions act on the
Playwright page directly with the same audit trail.

Safety model (mirrors ai/lux_model.py LuxModel — same contract, browser):
- governance_callback: async (action_type, details) -> bool. The loop
  treats one False as a HARD stop — it is policy, not a retryable failure.
- RISKY_ACTION_KEYWORDS: money/checkout actions are hard-stopped here
  (carried over from browser_engine/agent.py _validate_action_safety).
- Every action writes a BrowserAudit row (best-effort, never raises) —
  audits open their own short-lived DB session when the caller has none,
  so the MCP dispatch path (which never forwards a db) still gets the
  durable trail.
- Navigations run the sandbox egress-allowlist check (the same Phase D
  validation dispatched tool calls get) before reaching Playwright.
- Coordinates are clamped to the viewport.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

# Money/irreversible-action keywords — hard stop, carried over from
# browser_engine/agent.py _validate_action_safety.
RISKY_ACTION_KEYWORDS = ("pay", "send money", "transfer", "tax", "checkout")

# Parameter keys whose values are free TEXT the model types into a page —
# ordinary content, not the model choosing a money target. "$5 tax" or a
# payments@ email in typed text must not abort the task; payment-shaped
# numbers (cards) still do.
_FREE_TEXT_KEYS = frozenset({"text"})

# High-signal payment patterns applied to free-text values only.
_RISKY_TEXT_PATTERNS = (
    # 16-digit card numbers (4-4-4-4, spaced/dashed/flat)
    re.compile(r"\b(?:\d[ -]?){15}\d\b"),
)

# Action vocabulary the browser backend understands. The desktop backend
# (LuxModel's ComputerActionType) differs on purpose: navigate/press_key
# are browser-shaped, open_app/close_app are desktop-shaped.
BROWSER_ACTIONS = frozenset({
    "navigate", "click", "type", "press_key", "scroll",
    "find_element", "wait", "screenshot",
})

# Playwright key names for common aliases the model may emit.
_KEY_ALIASES = {
    "cmd": "Meta", "command": "Meta", "meta": "Meta", "win": "Meta",
    "ctrl": "Control", "control": "Control",
    "alt": "Alt", "option": "Alt", "opt": "Alt",
    "shift": "Shift", "esc": "Escape", "escape": "Escape",
    "enter": "Enter", "return": "Enter", "tab": "Tab", "space": " ",
    "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft",
    "right": "ArrowRight", "backspace": "Backspace", "delete": "Delete",
}

VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080

# Observation text budget: enough for the model to read the page, small
# enough to keep per-step token cost bounded alongside the screenshot.
_PAGE_TEXT_BUDGET = 4000


@dataclass
class Observation:
    """One look at the controlled environment."""
    screenshot_b64: str = ""          # downscaled JPEG, raw base64
    url: str = ""
    title: str = ""
    page_text: str = ""
    viewport: Tuple[int, int] = (VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
    error: Optional[str] = None


def encode_screenshot_for_model(png_bytes: bytes, max_edge: int = 1568) -> str:
    """PNG bytes → downscaled quality-85 JPEG, raw base64.

    Same cost contract as LuxModel.encode_screenshot_for_model: a 1920x1080
    PNG is ~MBs; at frontier-model input prices that dominates every step.
    The routing layer wraps raw base64 in the data:image/jpeg URL itself.
    """
    if not PIL_AVAILABLE:
        return base64.b64encode(png_bytes).decode("utf-8")
    img = Image.open(io.BytesIO(png_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _audit(db, agent_id: Optional[str], user_id: Optional[str],
           session_id: str, action: str, status: str,
           error: Optional[str] = None) -> None:
    """BrowserAudit row for an operator action (best-effort, never raises).

    Opens its own short-lived DB session when the caller has none (same
    idiom as goals/goal_run_events) — the MCP dispatch path never puts a
    db in the tool context, and audits must persist anyway.
    """
    try:
        from core.audit_service import AuditService
        metadata: Dict[str, Any] = {"status": status, "surface": "operator"}
        if error:
            metadata["error"] = str(error)[:500]

        def _write(session) -> None:
            AuditService().create_browser_audit(
                db=session,
                agent_id=agent_id,
                agent_execution_id=None,
                user_id=user_id or "system",
                session_id=session_id,
                action=f"operator_{action}",
                metadata=metadata,
            )
            session.commit()

        if db is not None:
            _write(db)
        else:
            from core.database import get_db_session
            with get_db_session() as own:
                _write(own)
    except Exception as exc:
        logger.debug(f"operator audit skipped ({action}/{status}): {exc}")


def _guardrail_hit(action_type: str, parameters: Dict[str, Any]) -> Optional[str]:
    """Return the matched risky signal, or None when the action is safe.

    Structured fields (url/selector/coordinates/...) encode the model's
    CHOICE of target, so the full money/checkout keyword list applies to
    them. Free-text values (typed text) are page content — "Total tax:
    $5" or a payments@vendor.com email is ordinary work, not a money
    action — so they are scanned for high-signal payment shapes (card
    numbers) only. A hit from either scan is a hard stop.
    """
    parameters = parameters or {}
    structured = " ".join(
        str(v) for k, v in parameters.items() if k not in _FREE_TEXT_KEYS
    )
    haystack = f"{action_type} {structured}".lower()
    for keyword in RISKY_ACTION_KEYWORDS:
        if keyword in haystack:
            return keyword
    for key in _FREE_TEXT_KEYS:
        value = parameters.get(key)
        if value is None:
            continue
        for pattern in _RISKY_TEXT_PATTERNS:
            if pattern.search(str(value)):
                return f"payment-shaped number in '{key}'"
    return None


class OperatorSession:
    """Browser actuation backend for the operator loop.

    The loop (loop.py) only needs ``observe`` / ``execute`` / ``close``;
    keeping the backend swappable is what lets the desktop backend
    (LuxModel's pyautogui executor) slot in later without loop changes.
    """

    def __init__(
        self,
        user_id: str = "system",
        agent_id: Optional[str] = None,
        db=None,
        governance_callback: Optional[Any] = None,
    ):
        self.user_id = user_id
        self.agent_id = agent_id
        self.db = db
        self.governance_callback = governance_callback
        self.session_id: Optional[str] = None
        self._manager = None
        # Sandbox egress policy for in-loop navigations (lazily issued —
        # the same tier-floor policy the dispatch gate would issue).
        self._egress_policy = None

    # ------------------------------------------------------------ lifecycle

    async def start(self, start_url: Optional[str] = None) -> Dict[str, Any]:
        """Open the Playwright session (governed like any browser session)."""
        from tools.browser_tool import get_browser_manager, browser_navigate

        self._manager = get_browser_manager()
        session = await self._manager.create_session(
            user_id=self.user_id,
            agent_id=self.agent_id,
        )
        self.session_id = session.session_id
        result: Dict[str, Any] = {"session_id": self.session_id}
        if start_url:
            # Same egress validation the dispatch gate runs on the
            # start_url argument — the initial navigation must not be the
            # one unvalidated jump into the browser.
            denial = self._egress_denial(str(start_url))
            if denial:
                result["navigate"] = {
                    "success": False, "blocked_by_governance": True,
                    "error": f"navigation blocked by egress policy: {denial}",
                }
                return result
            nav = await browser_navigate(
                self.session_id, start_url, user_id=self.user_id)
            result["navigate"] = nav
        return result

    async def close(self) -> None:
        if self._manager and self.session_id:
            try:
                await self._manager.close_session(self.session_id)
            except Exception as exc:
                logger.warning(f"operator session close failed: {exc}")
        self.session_id = None

    def _page(self):
        session = (self._manager or None) and self._manager.get_session(self.session_id)
        if session is None or session.page is None:
            raise RuntimeError("operator browser session is not open")
        return session.page

    # ------------------------------------------------------------ egress

    def _resolve_agent_tier(self) -> Optional[str]:
        """The operating agent's maturity tier (agent.status), or None.

        Used only to issue the egress policy — same tier source the
        capability resolver falls back to. Fault-isolated: a DB hiccup
        yields None (the issuer then applies the student floor).
        """
        if not self.agent_id:
            return None
        try:
            from core.database import get_db_session
            from core.models import AgentRegistry
            with get_db_session() as db:
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == str(self.agent_id)).first()
                return (getattr(agent, "status", None) or None)
        except Exception as exc:
            logger.debug(f"operator egress tier lookup failed: {exc}")
            return None

    def _egress_denial(self, url: str) -> Optional[str]:
        """Egress-allowlist denial detail for a URL, or None when allowed.

        Reuses the sandbox Phase D check so model-decided in-loop
        navigations get the SAME validation dispatched tool calls get.
        No-op unless the egress allowlist is enabled (opt-in, off by
        default). Fails CLOSED — a broken check must not become a bypass.
        """
        try:
            from core import sandbox_config
            if not sandbox_config.is_sandbox_egress_enabled():
                return None
            from core.sandbox_egress_proxy import check_egress
            from core.sandbox_policy import PolicyIssuer
            if self._egress_policy is None:
                self._egress_policy = PolicyIssuer().issue(
                    run_id=f"operator-{self.session_id or 'session'}",
                    agent_id=self.agent_id or "operator",
                    tier_at_issuance=self._resolve_agent_tier() or "student",
                )
            decision = check_egress(self._egress_policy, url=url,
                                    tool_name="operator_navigate")
            if decision.decision == "blocked":
                return decision.violation_detail
            return None
        except Exception as exc:
            logger.warning(f"operator egress check failed CLOSED: {exc}")
            return f"egress check error: {exc}"

    # ------------------------------------------------------------ observation

    async def observe(self) -> Observation:
        """Fresh screenshot + page facts. Called before EVERY decision."""
        obs = Observation()
        try:
            page = self._page()
            obs.url = page.url or ""
            try:
                obs.title = await page.title()
            except Exception:
                obs.title = ""
            try:
                text = await page.inner_text("body")
                obs.page_text = (text or "")[:_PAGE_TEXT_BUDGET]
            except Exception:
                obs.page_text = ""
            png = await page.screenshot(type="png")
            obs.screenshot_b64 = encode_screenshot_for_model(png)
            session = self._manager.get_session(self.session_id)
            if session is not None:
                session.last_used = datetime.now()
        except Exception as exc:
            obs.error = f"{type(exc).__name__}: {exc}"
        return obs

    # ------------------------------------------------------------ actuation

    async def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ONE action dict ({action_type, parameters}).

        Returns {success, action_type, detail?} — blocked_by_guardrail /
        blocked_by_governance mark hard stops the loop must not retry.
        """
        action_type = str(action.get("action_type") or "").lower()
        parameters = dict(action.get("parameters") or {})
        if action_type not in BROWSER_ACTIONS:
            return {"success": False, "action_type": action_type,
                    "error": f"unknown action type '{action_type}'"}

        # Guardrail first: money/checkout actions never reach the page.
        keyword = _guardrail_hit(action_type, parameters)
        if keyword:
            _audit(self.db, self.agent_id, self.user_id,
                   self.session_id or "none", action_type, "guardrail_blocked")
            return {"success": False, "action_type": action_type,
                    "blocked_by_guardrail": True,
                    "error": f"risky action keyword '{keyword}' — "
                             f"operator guardrail hard stop"}

        # Per-action governance callback (hard stop, LuxModel contract).
        if self.governance_callback is not None:
            try:
                allowed = await self.governance_callback(
                    action_type=action_type, details=parameters)
            except Exception as exc:
                logger.error(f"operator governance callback raised: {exc}")
                allowed = False
            if not allowed:
                _audit(self.db, self.agent_id, self.user_id,
                       self.session_id or "none", action_type, "governance_blocked")
                return {"success": False, "action_type": action_type,
                        "blocked_by_governance": True,
                        "error": "blocked by governance policy"}

        _audit(self.db, self.agent_id, self.user_id,
               self.session_id or "none", action_type, "started")

        try:
            result = await self._dispatch(action_type, parameters)
        except Exception as exc:
            logger.error(f"operator action '{action_type}' raised: {exc}")
            result = {"success": False, "action_type": action_type,
                      "error": str(exc)}

        _audit(self.db, self.agent_id, self.user_id,
               self.session_id or "none", action_type,
               "success" if result.get("success") else "failed",
               error=result.get("error"))
        return result

    async def _dispatch(self, action_type: str,
                        parameters: Dict[str, Any]) -> Dict[str, Any]:
        from tools.browser_tool import browser_navigate, browser_click

        if action_type == "navigate":
            url = str(parameters.get("url") or "").strip()
            if not url:
                return {"success": False, "action_type": action_type,
                        "error": "navigate requires parameters.url"}
            # Egress allowlist (when enabled): model-decided navigations
            # get the same Phase D validation dispatched tool calls get.
            # A denial is policy, not a retryable failure — same hard
            # stop contract as the governance callback below.
            denial = self._egress_denial(url)
            if denial:
                return {"success": False, "action_type": action_type,
                        "blocked_by_governance": True,
                        "error": f"navigation blocked by egress policy: "
                                 f"{denial}"}
            # browser_navigate carries the SSRF guard (private/link-local
            # addresses blocked) — never bypass it with page.goto directly.
            nav = await browser_navigate(
                self.session_id, url, user_id=self.user_id)
            nav["action_type"] = action_type
            return nav

        if action_type == "click":
            selector = parameters.get("selector")
            if selector:
                click = await browser_click(
                    self.session_id, str(selector),
                    user_id=self.user_id, agent_id=self.agent_id, db=self.db)
                click["action_type"] = action_type
                return click
            coords = parameters.get("coordinates") or []
            if not isinstance(coords, (list, tuple)) or len(coords) != 2:
                return {"success": False, "action_type": action_type,
                        "error": "click requires parameters.coordinates [x,y] "
                                 "or parameters.selector"}
            x, y = self._clamp_coords(coords)
            page = self._page()
            await page.mouse.click(x, y)
            return {"success": True, "action_type": action_type,
                    "coordinates": [x, y]}

        if action_type == "type":
            text = parameters.get("text")
            if text is None:
                return {"success": False, "action_type": action_type,
                        "error": "type requires parameters.text"}
            page = self._page()
            await page.keyboard.type(str(text))
            return {"success": True, "action_type": action_type}

        if action_type == "press_key":
            keys = parameters.get("keys") or []
            if isinstance(keys, str):
                keys = [keys]
            if not keys:
                return {"success": False, "action_type": action_type,
                        "error": "press_key requires parameters.keys"}
            combo = "+".join(_KEY_ALIASES.get(str(k).lower(), str(k)) for k in keys)
            page = self._page()
            await page.keyboard.press(combo)
            return {"success": True, "action_type": action_type, "keys": combo}

        if action_type == "scroll":
            direction = str(parameters.get("direction") or "down").lower()
            try:
                amount = max(1, min(10, int(parameters.get("amount", 3))))
            except (TypeError, ValueError):
                amount = 3
            dy = amount * 200 * (1 if direction == "down" else -1)
            page = self._page()
            await page.mouse.wheel(0, dy)
            return {"success": True, "action_type": action_type,
                    "direction": direction, "amount": amount}

        if action_type == "find_element":
            needle = str(parameters.get("text") or "")
            obs = await self.observe()
            found = bool(needle) and needle.lower() in (obs.page_text or "").lower()
            return {"success": True, "action_type": action_type,
                    "found": found, "url": obs.url}

        if action_type == "wait":
            try:
                duration = max(0.0, min(10.0, float(parameters.get("duration", 1))))
            except (TypeError, ValueError):
                duration = 1.0
            await asyncio.sleep(duration)
            return {"success": True, "action_type": action_type,
                    "duration": duration}

        if action_type == "screenshot":
            # Observations happen before every decision anyway; this is an
            # explicit no-op so the model can "look again" harmlessly.
            return {"success": True, "action_type": action_type}

        return {"success": False, "action_type": action_type,
                "error": f"unhandled action type '{action_type}'"}

    def _clamp_coords(self, coords) -> Tuple[int, int]:
        x = max(0, min(VIEWPORT_WIDTH - 1, int(coords[0])))
        y = max(0, min(VIEWPORT_HEIGHT - 1, int(coords[1])))
        return x, y
