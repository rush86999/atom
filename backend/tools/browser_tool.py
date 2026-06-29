"""
Browser Automation Tool

Provides Chrome DevTools Protocol (CDP) control via Playwright for:
- Web scraping and data extraction
- Form filling and submission
- Multi-step web workflows
- Screenshot capture
- Browser-based testing
- PDF generation
- Network interception

Governance Integration:
- All browser actions require INTERN+ maturity level
- Full audit trail via browser_audit table
- Agent execution tracking for all browser sessions

Pre-Action Match-Confidence (Phase 2+):
- When BROWSER_LOCATOR_API_ENABLED=true, browser_click / browser_fill_form /
  browser_extract_text migrate from legacy query_selector* to Playwright's
  strict-mode page.locator() API and surface a MatchConfidence rationale on
  every return dict. See core/selector_confidence_service.py and
  docs/architecture/MATCH_CONFIDENCE.md.
- Audit rows are written via AuditService.create_browser_audit() at the
  start and end of each action with metadata.match_confidence populated.

Refactored to use standardized decorators and service factory.
"""

import asyncio
import base64
from datetime import datetime
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid
from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.feature_flags import FeatureFlags
from core.llm_service import get_llm_service
from core.models import AgentExecution
from core.proposal_service import ProposalService
from core.selector_confidence_service import (
    AMBIGUOUS,
    HIGH,
    PARTIAL,
    MatchConfidence,
    SelectorCandidate,
    MATCH_CONFIDENCE_FORCE_PROPOSAL,
    SELECTOR_CONFIDENCE_ENABLED,
    attach_tiebreak,
    score_candidates,
)
from core.service_factory import ServiceFactory
from core.structured_logger import get_logger
import os

logger = get_logger(__name__)

# Feature flags
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"

# Phase 2 — locator API + match-confidence annotation (shadow mode default).
# When false, all four migrated functions fall back to the legacy
# query_selector* path and return dicts without the match_confidence key.
BROWSER_LOCATOR_API_ENABLED = (
    os.getenv("BROWSER_LOCATOR_API_ENABLED", "true").lower() == "true"
)

# Cap candidate attribute enumeration — keeps latency bounded on huge lists.
_MAX_CANDIDATES_ENUMERATED = 5
# Late-appearance threshold mirrors selector_confidence_service.
_LATE_APPEARANCE_MS = 1000


# ============================================================================
# Phase 2 helpers — locator resolver + strict-mode catcher
# ============================================================================
async def _resolve_selector_with_confidence(
    page: Page,
    selector: str,
    wait_ms: int = 5000,
) -> Tuple[Optional[Locator], MatchConfidence]:
    """
    Resolve a CSS selector via page.locator() and produce a MatchConfidence.

    Returns ``(locator, confidence)``. ``locator`` is None when 0 matches
    were found within ``wait_ms`` (deterministic — no 5s timeout burn) or
    when the selector is malformed.

    The confidence drives downstream gating (Phase 4) and is always
    surfaced in the tool return dict for LLM/reviewer visibility.
    """
    if not SELECTOR_CONFIDENCE_ENABLED:
        # Should not be called when disabled, but degrade safely.
        return page.locator(selector), MatchConfidence(
            level=HIGH, score=1.0, rationale="confidence disabled", candidates=[], chosen_index=0
        )

    start = time.monotonic()
    try:
        locator = page.locator(selector)
        try:
            await locator.wait_for(state="visible", timeout=wait_ms)
        except PlaywrightTimeoutError:
            # 0 matches → ambiguous, not timeout-burn
            return None, MatchConfidence(
                level=AMBIGUOUS,
                score=0.0,
                rationale="0 matches within timeout",
                candidates=[],
                chosen_index=-1,
            )

        count = await locator.count()
        appeared_after_ms = int((time.monotonic() - start) * 1000)

        # Enumerate attributes for up to _MAX_CANDIDATES_ENUMERATED matches
        enumerated: List[SelectorCandidate] = []
        sample_attrs: Dict[str, str] = {}
        sample_tag = ""
        for i in range(min(count, _MAX_CANDIDATES_ENUMERATED)):
            try:
                info = await locator.nth(i).evaluate(
                    "el => ({tag: el.tagName, attrs: {...el.attributes}.length ? "
                    "Object.fromEntries(Array.from(el.attributes).map(a => [a.name, a.value])) : {}})"
                )
                tag = (info or {}).get("tag", "") if isinstance(info, dict) else ""
                attrs = (info or {}).get("attrs", {}) if isinstance(info, dict) else {}
                if i == 0:
                    sample_tag = tag
                    sample_attrs = attrs if isinstance(attrs, dict) else {}
            except Exception:
                # Attribute enumeration is best-effort; don't fail the resolution.
                tag, attrs = "", {}

        is_text_only = not any(
            k in selector for k in ("#", "[data-testid", "[aria-label", "[role")
        )

        candidate = SelectorCandidate(
            selector=selector,
            match_count=count,
            is_text_only=is_text_only,
            appeared_after_ms=appeared_after_ms,
            tag_hint=sample_tag,
            attributes=sample_attrs,
        )
        confidence = score_candidates([candidate])

        # For high-confidence single matches, callers can safely use locator.first
        return (locator.first if confidence.level == HIGH else locator), confidence

    except Exception as e:
        logger.warning(f"_resolve_selector_with_confidence failed for {selector!r}: {e}")
        return None, MatchConfidence(
            level=AMBIGUOUS,
            score=0.0,
            rationale=f"resolution error: {type(e).__name__}",
            candidates=[],
            chosen_index=-1,
        )


async def _execute_with_locator(
    locator: Optional[Locator],
    action_fn,
) -> Tuple[bool, Optional[MatchConfidence], Optional[str]]:
    """
    Execute an action against a resolved locator, catching strict-mode violations.

    ``action_fn`` receives the locator and returns whatever the underlying
    Playwright call returns. Returns ``(success, upgraded_confidence_or_None, error_or_None)``.

    If Playwright raises a strict-mode-violation Error, we upgrade the
    confidence to ``ambiguous`` (rather than surfacing a raw error) so the
    caller can route the action through the proposal flow.
    """
    if locator is None:
        return False, None, "no locator resolved"
    try:
        await action_fn(locator)
        return True, None, None
    except PlaywrightError as e:
        msg = str(e)
        if "strict mode violation" in msg:
            upgraded = MatchConfidence(
                level=AMBIGUOUS,
                score=0.0,
                rationale=f"strict mode violation: {msg[:120]}",
                candidates=[],
                chosen_index=-1,
            )
            return False, upgraded, msg
        return False, None, msg
    except Exception as e:
        return False, None, str(e)


def _confidence_to_dict(confidence: Optional[MatchConfidence]) -> Optional[Dict[str, Any]]:
    """Serialize MatchConfidence for tool return dicts (None-safe)."""
    if confidence is None:
        return None
    return confidence.to_dict()


def _write_browser_audit(
    db: Optional[Session],
    agent_id: Optional[str],
    user_id: Optional[str],
    session_id: str,
    action: str,
    status: str,
    confidence: Optional[MatchConfidence] = None,
    error: Optional[str] = None,
) -> None:
    """
    Write a BrowserAudit row via AuditService (never raises).

    Closes the long-standing gap noted in MATCH_CONFIDENCE.md: the
    BrowserAudit model existed but had no writers. Each browser action
    now records a ``started`` row at entry and a ``success``/``failed``
    row at completion, with ``metadata.match_confidence`` populated when
    the locator API is on.
    """
    if db is None:
        return
    try:
        from core.audit_service import AuditService

        metadata: Dict[str, Any] = {"status": status}
        if confidence is not None:
            metadata["match_confidence"] = confidence.to_dict()
        if error is not None:
            metadata["error"] = error[:500]

        AuditService().create_browser_audit(
            db=db,
            agent_id=agent_id,
            agent_execution_id=None,
            user_id=user_id or "system",
            session_id=session_id,
            action=action,
            metadata=metadata,
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
    except Exception as e:
        # Audit is best-effort; never break the action over an audit failure.
        logger.debug(f"BrowserAudit write skipped ({action}/{status}): {e}")


async def _maybe_gate_with_proposal(
    action: str,
    selector: str,
    confidence: MatchConfidence,
    agent_id: Optional[str],
    db: Optional[Session],
    session_id: str,
    user_id: Optional[str],
    *,
    extra_selectors: Optional[Dict[str, str]] = None,
    override: bool = False,
    per_field_confidence: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Route partial/ambiguous matches through ProposalService.

    Returns None when the action should proceed (high confidence, shadow
    mode, post-approval override, or no agent_id/db). Returns a
    ``{requires_approval, proposal_id, match_confidence}`` dict when the
    action should be gated.

    Included for AUTONOMOUS agents — whose tier is routed by history, not
    current-call certainty. See MATCH_CONFIDENCE.md § Phase 4.
    """
    if override:
        return None
    if confidence.level == HIGH:
        return None
    if not MATCH_CONFIDENCE_FORCE_PROPOSAL:
        return None
    if not agent_id or db is None:
        return None

    try:
        # Build proposed_action with full candidate visibility for reviewer
        proposed_action: Dict[str, Any] = {
            "action_type": "browser_automate",
            "action": action,
            "selector": selector,
            "selectors": extra_selectors or {},
            "session_id": session_id,
            "selector_candidates": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__
                                     for c in confidence.candidates],
            "match_rationale": confidence.rationale,
            "match_score": confidence.score,
            "chosen_index": confidence.chosen_index,
            "originating_tier": "match_confidence_gate",
            "match_confidence_override": True,  # post-approval re-exec bypasses gate
        }
        if per_field_confidence is not None:
            proposed_action["per_field_confidence"] = per_field_confidence

        proposal = await ProposalService(db).create_action_proposal(
            intern_agent_id=agent_id,
            trigger_context={
                "source": "match_confidence_gate",
                "level": confidence.level,
                "session_id": session_id,
            },
            proposed_action=proposed_action,
            reasoning=(
                f"Selector {selector!r} resolved with level={confidence.level} "
                f"(score={confidence.score:.2f}): {confidence.rationale}. "
                f"Routing through human review because current-call certainty is "
                f"low, even though agent tier may permit direct execution."
            ),
            session_id=session_id,
            title=f"Match-confidence gate: {action} {selector!r}",
        )

        return {
            "requires_approval": True,
            "proposal_id": proposal.id,
            "match_confidence": confidence.to_dict(),
        }
    except Exception as e:
        logger.warning(f"_maybe_gate_with_proposal failed (proceeding without gate): {e}", exc_info=True)
        return None


class BrowserSession:
    """
    Managed browser session with context and page tracking.

    Each session represents a unique browser instance that can be
    reused across multiple operations for maintaining state (cookies,
    localStorage, etc.).
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        agent_id: Optional[str] = None,
        headless: bool = True,
        browser_type: str = "chromium"
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.agent_id = agent_id
        self.headless = headless
        self.browser_type = browser_type
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.created_at = datetime.now()
        self.last_used = datetime.now()

    async def start(self):
        """Start the browser session."""
        try:
            self.playwright = await async_playwright().start()

            # Select browser type
            if self.browser_type == "firefox":
                self.browser = await self.playwright.firefox.launch(headless=self.headless)
            elif self.browser_type == "webkit":
                self.browser = await self.playwright.webkit.launch(headless=self.headless)
            else:  # chromium (default)
                self.browser = await self.playwright.chromium.launch(headless=self.headless)

            # Create context with realistic viewport
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )

            # Create default page
            self.page = await self.context.new_page()

            logger.info(f"Browser session {self.session_id} started ({self.browser_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to start browser session {self.session_id}: {e}")
            raise

    async def close(self):
        """Close the browser session and cleanup resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

            logger.info(f"Browser session {self.session_id} closed")
            return True

        except Exception as e:
            logger.error(f"Error closing browser session {self.session_id}: {e}")
            return False


class BrowserSessionManager:
    """
    Manages active browser sessions with automatic cleanup.

    Sessions are stored in memory and automatically cleaned up after
    a timeout period of inactivity.
    """

    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, BrowserSession] = {}
        self.session_timeout_minutes = session_timeout_minutes

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get an existing session by ID."""
        return self.sessions.get(session_id)

    async def create_session(
        self,
        user_id: str,
        agent_id: Optional[str] = None,
        headless: bool = True,
        browser_type: str = "chromium"
    ) -> BrowserSession:
        """Create and start a new browser session."""
        session_id = str(uuid.uuid4())
        session = BrowserSession(
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            headless=headless,
            browser_type=browser_type
        )

        await session.start()
        self.sessions[session_id] = session
        return session

    async def close_session(self, session_id: str) -> bool:
        """Close and remove a session."""
        session = self.sessions.get(session_id)
        if session:
            await session.close()
            del self.sessions[session_id]
            return True
        return False

    async def cleanup_expired_sessions(self):
        """Remove expired sessions based on last used time."""
        now = datetime.now()
        expired_ids = []

        for session_id, session in self.sessions.items():
            elapsed = (now - session.last_used).total_seconds() / 60
            if elapsed > self.session_timeout_minutes:
                expired_ids.append(session_id)

        for session_id in expired_ids:
            logger.info(f"Cleaning up expired browser session: {session_id}")
            await self.close_session(session_id)

        return len(expired_ids)


# Global session manager
_session_manager = BrowserSessionManager()


def get_browser_manager() -> BrowserSessionManager:
    """Get the global browser session manager."""
    return _session_manager


# ============================================================================
# Browser Tool Functions
# ============================================================================

async def browser_create_session(
    user_id: str,
    agent_id: Optional[str] = None,
    headless: bool = None,
    browser_type: str = "chromium",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Create a new browser session with governance integration.

    Args:
        user_id: User ID creating the session
        agent_id: Agent ID creating the session (for governance)
        headless: Whether to run headless (default from env)
        browser_type: Browser type (chromium, firefox, webkit)
        db: Database session for governance

    Returns:
        Dict with session_id and metadata
    """
    agent = None
    governance_check = None
    agent_execution = None

    try:
        # Governance: Check agent permissions (browser_navigate = INTERN+)
        if FeatureFlags.should_enforce_governance('browser') and agent_id and db:
            resolver = AgentContextResolver(db)
            governance = ServiceFactory.get_governance_service(db)

            agent, _ = await resolver.resolve_agent_for_request(
                user_id=user_id,
                requested_agent_id=agent_id,
                action_type="browser_navigate"
            )

            if agent:
                governance_check = governance.can_perform_action(
                    agent_id=agent.id,
                    action_type="browser_navigate"
                )

                if not governance_check["allowed"]:
                    logger.warning(f"Governance blocked browser session: {governance_check['reason']}")
                    return {
                        "success": False,
                        "error": f"Agent not permitted to use browser: {governance_check['reason']}"
                    }

                # Create execution record
                agent_execution = AgentExecution(
                    agent_id=agent.id,
                    workspace_id="default",
                    status="running",
                    input_summary="Create browser session",
                    triggered_by="browser_tool"
                )
                db.add(agent_execution)
                db.commit()
                db.refresh(agent_execution)

        # Create session
        if headless is None:
            headless = BROWSER_HEADLESS

        session = await get_browser_manager().create_session(
            user_id=user_id,
            agent_id=agent_id if agent else None,
            headless=headless,
            browser_type=browser_type
        )

        # Record outcome
        if agent and db and FeatureFlags.should_enforce_governance('browser'):
            governance = ServiceFactory.get_governance_service(db)
            await governance.record_outcome(agent.id, success=True)

            if agent_execution:
                agent_execution.status = "completed"
                agent_execution.output_summary = f"Created browser session {session.session_id}"
                agent_execution.completed_at = datetime.now()
                db.commit()

        logger.info(f"Created browser session {session.session_id} for user {user_id}")

        return {
            "success": True,
            "session_id": session.session_id,
            "browser_type": browser_type,
            "headless": headless,
            "agent_id": agent.id if agent else None,
            "created_at": session.created_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to create browser session: {e}")

        if agent_execution and db and FeatureFlags.should_enforce_governance('browser'):
            try:
                governance = ServiceFactory.get_governance_service(db)
                await governance.record_outcome(agent.id, success=False)

                agent_execution.status = "failed"
                agent_execution.error_message = str(e)
                agent_execution.completed_at = datetime.now()
                db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {
            "success": False,
            "error": str(e)
        }


async def browser_navigate(
    session_id: str,
    url: str,
    wait_until: str = "load",
    user_id: str = None,
    agent_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Navigate to a URL in an existing browser session.

    Args:
        session_id: Browser session ID
        url: URL to navigate to
        wait_until: When to consider navigation succeeded (load, domcontentloaded, networkidle)
        user_id: User ID for validation
        agent_id: Agent ID for governance
        db: Database session for governance

    Returns:
        Dict with navigation result and page info
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    try:
        # Navigate to URL
        response = await session.page.goto(url, wait_until=wait_until, timeout=30000)

        session.last_used = datetime.now()

        # Get page info
        title = await session.page.title()
        url_final = session.page.url

        logger.info(f"Navigated session {session_id} to {url}")

        return {
            "success": True,
            "session_id": session_id,
            "url": url_final,
            "title": title,
            "status": response.status if response else None,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Navigation failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def browser_screenshot(
    session_id: str,
    path: Optional[str] = None,
    full_page: bool = False,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Take a screenshot of the current page.

    Args:
        session_id: Browser session ID
        path: Optional file path to save screenshot
        full_page: Whether to capture full scrolling page
        user_id: User ID for validation

    Returns:
        Dict with screenshot data (base64) or file path
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    try:
        # Take screenshot
        screenshot_bytes = await session.page.screenshot(
            full_page=full_page,
            type="png"
        )

        session.last_used = datetime.now()

        # Encode to base64
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Save to file if path provided
        if path:
            import os
            # SECURITY: sanitize path to prevent directory traversal.
            # Reject absolute paths, parent-dir traversal, and confine
            # writes to a configured screenshot directory (or cwd if unset).
            if ".." in path or os.path.isabs(path):
                logger.warning(f"Rejected suspicious screenshot path: {path!r}")
                return {
                    "success": False,
                    "error": "Invalid screenshot path: relative paths only, no '..'",
                }
            screenshot_dir = os.getenv("SCREENSHOT_DIR", os.getcwd())
            safe_path = os.path.normpath(os.path.join(screenshot_dir, path))
            # Verify the resolved path hasn't escaped the screenshot dir
            if not os.path.abspath(safe_path).startswith(os.path.abspath(screenshot_dir)):
                logger.warning(f"Screenshot path escaped base directory: {path!r}")
                return {
                    "success": False,
                    "error": "Invalid screenshot path: must stay within screenshot directory",
                }
            os.makedirs(os.path.dirname(safe_path) or screenshot_dir, exist_ok=True)
            with open(safe_path, "wb") as f:
                f.write(screenshot_bytes)

            logger.info(f"Screenshot saved to {safe_path}")
            return {
                "success": True,
                "path": safe_path,
                "size_bytes": len(screenshot_bytes)
            }

        logger.info(f"Screenshot taken for session {session_id}")

        return {
            "success": True,
            "data": screenshot_base64,
            "size_bytes": len(screenshot_bytes),
            "format": "png"
        }

    except Exception as e:
        logger.error(f"Screenshot failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def browser_fill_form(
    session_id: str,
    selectors: Dict[str, str],
    submit: bool = False,
    user_id: str = None,
    agent_id: Optional[str] = None,
    db: Optional[Session] = None,
    match_confidence_override: bool = False,
) -> Dict[str, Any]:
    """
    Fill form fields using CSS selectors.

    When BROWSER_LOCATOR_API_ENABLED=true, each field is resolved via
    page.locator() and a per-field MatchConfidence is reported under
    ``result.match_confidence.fields``. Gating (if any) applies to the
    WHOLE form — partial fills leave the page in an inconsistent state.

    Args:
        session_id: Browser session ID
        selectors: Dict mapping CSS selectors to values
        submit: Whether to submit the form after filling
        user_id: User ID for validation
        agent_id: Optional agent ID for Phase 4 proposal gating
        db: Optional DB session for Phase 4 proposal gating
        match_confidence_override: Skip gating (post-approval re-execution)

    Returns:
        Dict with fill result, or {requires_approval, proposal_id} when gated
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    use_locator = BROWSER_LOCATOR_API_ENABLED and SELECTOR_CONFIDENCE_ENABLED
    per_field_confidence: Dict[str, Any] = {}

    try:
        filled_count = 0

        # Phase 4: when locator + gating on, do TWO passes — resolve all
        # fields first (so we can gate on worst-case before any fill
        # executes), then fill only if not gated. Whole-form transactional
        # integrity: partial fills leave the page in an inconsistent state.
        if use_locator and MATCH_CONFIDENCE_FORCE_PROPOSAL and not match_confidence_override:
            # Pass 1: resolve all
            resolved: Dict[str, Dict[str, Any]] = {}
            for selector, value in selectors.items():
                try:
                    locator, confidence = await _resolve_selector_with_confidence(
                        session.page, selector
                    )
                    per_field_confidence[selector] = confidence.to_dict()
                    info = await locator.evaluate(
                        "el => ({tag: el.tagName, type: el.type || ''})"
                    ) if locator is not None else {}
                    tag = (info or {}).get("tag", "") if isinstance(info, dict) else ""
                    resolved[selector] = {"value": value, "locator": locator, "tag": tag}
                except Exception as e:
                    logger.warning(f"Failed to resolve {selector}: {e}")
                    per_field_confidence[selector] = {
                        "level": AMBIGUOUS, "score": 0.0,
                        "rationale": f"resolve error: {type(e).__name__}",
                        "candidates": [], "chosen_index": -1,
                    }
                    resolved[selector] = {"value": selectors[selector], "locator": None, "tag": ""}

            # Compute worst-case confidence for gating
            worst_level = HIGH
            level_rank = {HIGH: 0, PARTIAL: 1, AMBIGUOUS: 2}
            worst_field = None
            for sel, fc in per_field_confidence.items():
                fc_level = fc.get("level", PARTIAL)
                if level_rank.get(fc_level, 1) > level_rank[worst_level]:
                    worst_level = fc_level
                    worst_field = sel

            if worst_level != HIGH and worst_field is not None:
                # Build gating confidence from worst field
                worst_fc = per_field_confidence[worst_field]
                gate_conf = MatchConfidence(
                    level=worst_level,
                    score=worst_fc.get("score", 0.0),
                    rationale=f"worst field {worst_field!r}: {worst_fc.get('rationale', '')}",
                    candidates=[SelectorCandidate(
                        selector=worst_field,
                        match_count=worst_fc.get("candidates", [{}])[0].get("match_count", 0)
                            if worst_fc.get("candidates") else 0,
                        is_text_only=worst_fc.get("candidates", [{}])[0].get("is_text_only", False)
                            if worst_fc.get("candidates") else False,
                        appeared_after_ms=0,
                        tag_hint="",
                        attributes={},
                    )],
                    chosen_index=0,
                )
                gate_result = await _maybe_gate_with_proposal(
                    "fill_form", worst_field, gate_conf, agent_id, db,
                    session_id, user_id,
                    extra_selectors=dict(selectors),
                    override=match_confidence_override,
                    per_field_confidence=per_field_confidence,
                )
                if gate_result is not None:
                    _write_browser_audit(
                        db, agent_id, user_id, session_id, "fill_form", "gated",
                        confidence=gate_conf,
                    )
                    return gate_result

            # Pass 2: not gated — fill each resolved field
            for selector, info in resolved.items():
                try:
                    if info["locator"] is None:
                        continue
                    tag = info["tag"]
                    value = info["value"]
                    if tag in ["INPUT", "TEXTAREA"]:
                        await session.page.fill(selector, value)
                        filled_count += 1
                    elif tag == "SELECT":
                        await session.page.select_option(selector, value)
                        filled_count += 1
                    else:
                        logger.warning(f"Unsupported element type: {tag} for selector {selector}")
                except Exception as e:
                    logger.warning(f"Failed to fill {selector}: {e}")
        else:
            # Original single-pass loop (legacy or no-gate path)
            for selector, value in selectors.items():
                try:
                    if use_locator:
                        locator, confidence = await _resolve_selector_with_confidence(
                            session.page, selector
                        )
                        per_field_confidence[selector] = confidence.to_dict()
                        if locator is None:
                            logger.warning(f"Skipping unfilled field {selector}: 0 matches")
                            continue

                        # Determine tag via evaluate on the locator
                        info = await locator.evaluate(
                            "el => ({tag: el.tagName, type: el.type || ''})"
                        )
                        tag_name = (info or {}).get("tag", "") if isinstance(info, dict) else ""
                    else:
                        # Legacy path
                        await session.page.wait_for_selector(selector, timeout=5000)
                        element = await session.page.query_selector(selector)
                        tag_name = await element.evaluate("el => el.tagName")

                    if tag_name in ["INPUT", "TEXTAREA"]:
                        await session.page.fill(selector, value)
                        filled_count += 1
                    elif tag_name == "SELECT":
                        await session.page.select_option(selector, value)
                        filled_count += 1
                    else:
                        logger.warning(f"Unsupported element type: {tag_name} for selector {selector}")

                except Exception as e:
                    logger.warning(f"Failed to fill {selector}: {e}")

        session.last_used = datetime.now()

        result: Dict[str, Any] = {
            "success": True,
            "session_id": session_id,
            "fields_filled": filled_count
        }
        if use_locator:
            # Roll up: form-level confidence = worst field confidence
            worst_level = HIGH
            level_rank = {HIGH: 0, PARTIAL: 1, AMBIGUOUS: 2}
            for fc in per_field_confidence.values():
                if level_rank.get(fc.get("level", PARTIAL), 1) > level_rank[worst_level]:
                    worst_level = fc.get("level", PARTIAL)
            result["match_confidence"] = {
                "level": worst_level,
                "fields": per_field_confidence,
            }

        # Submit form if requested
        if submit:
            # Try to find submit button or form
            try:
                # Look for button with type="submit"
                submit_button = await session.page.query_selector("button[type='submit']")
                if submit_button:
                    await submit_button.click()
                    result["submitted"] = True
                    result["submission_method"] = "submit_button"
                else:
                    # Try form submission
                    await session.page.evaluate("() => document.querySelector('form')?.submit()")
                    result["submitted"] = True
                    result["submission_method"] = "form_submit"
            except Exception as submit_error:
                logger.warning(f"Form submission failed: {submit_error}")
                result["submitted"] = False
                result["submit_error"] = str(submit_error)

        logger.info(f"Filled {filled_count} fields in session {session_id}")

        return result

    except Exception as e:
        logger.error(f"Form fill failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def browser_click(
    session_id: str,
    selector: str,
    wait_for: Optional[str] = None,
    user_id: str = None,
    agent_id: Optional[str] = None,
    db: Optional[Session] = None,
    match_confidence_override: bool = False,
) -> Dict[str, Any]:
    """
    Click an element using CSS selector.

    When BROWSER_LOCATOR_API_ENABLED=true, resolves via page.locator() and
    surfaces match_confidence. When MATCH_CONFIDENCE_FORCE_PROPOSAL=true
    AND confidence.level in {partial, ambiguous}, routes through
    ProposalService instead of clicking — for ALL agent tiers including
    AUTONOMOUS.

    Args:
        session_id: Browser session ID
        selector: CSS selector for element to click
        wait_for: Optional selector to wait for after click
        user_id: User ID for validation
        agent_id: Optional agent ID for Phase 4 proposal gating
        db: Optional DB session for Phase 4 proposal gating
        match_confidence_override: Skip gating (post-approval re-execution)

    Returns:
        Dict with click result, or {requires_approval, proposal_id} when gated
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    use_locator = BROWSER_LOCATOR_API_ENABLED and SELECTOR_CONFIDENCE_ENABLED

    _write_browser_audit(
        db, agent_id, user_id, session_id, "click", "started"
    )

    try:
        if use_locator:
            locator, confidence = await _resolve_selector_with_confidence(
                session.page, selector
            )

            # Phase 3 — LLM tiebreaker (only fires on PARTIAL)
            if confidence.level == PARTIAL and locator is not None:
                try:
                    llm_service = get_llm_service()
                    confidence = await attach_tiebreak(
                        confidence,
                        page_context={"url": session.page.url},
                        llm_service=llm_service,
                    )
                except Exception as e:
                    logger.debug(f"attach_tiebreak skipped: {e}")

            # Phase 4 — proposal gating (AUTONOMOUS included)
            gate_result = await _maybe_gate_with_proposal(
                "click", selector, confidence, agent_id, db,
                session_id, user_id, override=match_confidence_override,
            )
            if gate_result is not None:
                _write_browser_audit(
                    db, agent_id, user_id, session_id, "click", "gated",
                    confidence=confidence,
                )
                return gate_result

            if locator is None:
                return {
                    "success": False,
                    "error": f"Selector {selector} resolved to 0 matches",
                    "selector": selector,
                    "match_confidence": _confidence_to_dict(confidence),
                }
            ok, upgraded, err = await _execute_with_locator(
                locator, lambda loc: loc.click()
            )
            if upgraded is not None:
                confidence = upgraded
            if not ok:
                _write_browser_audit(
                    db, agent_id, user_id, session_id, "click", "failed",
                    confidence=confidence, error=err or "click failed",
                )
                return {
                    "success": False,
                    "error": err or "click failed",
                    "selector": selector,
                    "match_confidence": _confidence_to_dict(confidence),
                }
        else:
            # Legacy path
            await session.page.wait_for_selector(selector, state="visible", timeout=5000)
            await session.page.click(selector)
            confidence = None

        session.last_used = datetime.now()

        # Wait for navigation or element if specified
        if wait_for:
            try:
                await session.page.wait_for_selector(wait_for, timeout=5000)
            except Exception as e:
                logger.debug(f"Wait for selector '{wait_for}' not found or timeout: {e}")
                # Continue anyway - don't fail the entire operation

        logger.info(f"Clicked {selector} in session {session_id}")

        result: Dict[str, Any] = {
            "success": True,
            "session_id": session_id,
            "selector": selector
        }
        if use_locator:
            result["match_confidence"] = _confidence_to_dict(confidence)
        _write_browser_audit(
            db, agent_id, user_id, session_id, "click", "success", confidence
        )
        return result

    except Exception as e:
        logger.error(f"Click failed for session {session_id}: {e}")
        result: Dict[str, Any] = {
            "success": False,
            "error": str(e)
        }
        if use_locator:
            result["match_confidence"] = _confidence_to_dict(
                MatchConfidence(
                    level=AMBIGUOUS, score=0.0,
                    rationale=f"click exception: {type(e).__name__}",
                    candidates=[], chosen_index=-1,
                )
            )
        _write_browser_audit(
            db, agent_id, user_id, session_id, "click", "failed",
            error=str(e),
        )
        return result


async def browser_extract_text(
    session_id: str,
    selector: Optional[str] = None,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Extract text content from the page or specific elements.

    When BROWSER_LOCATOR_API_ENABLED=true and a selector is provided, the
    match count is surfaced via match_confidence. extract_text NEVER gates
    (it is read-only) — gating AUTONOMOUS reads of multi-match selectors
    would block legitimate scraping.

    Args:
        session_id: Browser session ID
        selector: Optional CSS selector (if None, extracts full page text)
        user_id: User ID for validation

    Returns:
        Dict with extracted text (and match_confidence when selector + locator API on)
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    use_locator = (
        BROWSER_LOCATOR_API_ENABLED
        and SELECTOR_CONFIDENCE_ENABLED
        and selector is not None
    )
    confidence: Optional[MatchConfidence] = None

    try:
        if selector:
            if use_locator:
                # Resolve to compute confidence; use .all_inner_texts() for the actual text
                locator, confidence = await _resolve_selector_with_confidence(
                    session.page, selector
                )
                if locator is None:
                    return {
                        "success": True,
                        "session_id": session_id,
                        "text": "",
                        "length": 0,
                        "match_confidence": _confidence_to_dict(confidence),
                    }
                try:
                    texts = await session.page.locator(selector).all_inner_texts()
                except Exception:
                    texts = []
                result_text = "\n".join(texts)
            else:
                # Legacy path
                elements = await session.page.query_selector_all(selector)
                texts = [await el.inner_text() for el in elements]
                result_text = "\n".join(texts)
        else:
            # Extract full page text
            result_text = await session.page.inner_text("body")

        session.last_used = datetime.now()

        logger.info(f"Extracted {len(result_text)} chars from session {session_id}")

        result: Dict[str, Any] = {
            "success": True,
            "session_id": session_id,
            "text": result_text,
            "length": len(result_text)
        }
        if use_locator and confidence is not None:
            result["match_confidence"] = _confidence_to_dict(confidence)
        return result

    except Exception as e:
        logger.error(f"Text extraction failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def browser_execute_script(
    session_id: str,
    script: str,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Execute JavaScript in the browser context.

    Args:
        session_id: Browser session ID
        script: JavaScript code to execute
        user_id: User ID for validation

    Returns:
        Dict with execution result
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    try:
        # Execute script
        result = await session.page.evaluate(script)

        session.last_used = datetime.now()

        logger.info(f"Executed script in session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "result": result
        }

    except Exception as e:
        logger.error(f"Script execution failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def browser_close_session(
    session_id: str,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Close a browser session.

    Args:
        session_id: Browser session ID
        user_id: User ID for validation

    Returns:
        Dict with close result
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    try:
        success = await get_browser_manager().close_session(session_id)

        if success:
            logger.info(f"Closed browser session {session_id}")
            return {
                "success": True,
                "session_id": session_id
            }
        else:
            return {
                "success": False,
                "error": "Failed to close session"
            }

    except Exception as e:
        logger.error(f"Failed to close session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def browser_get_page_info(
    session_id: str,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Get information about the current page.

    Args:
        session_id: Browser session ID
        user_id: User ID for validation

    Returns:
        Dict with page information
    """
    session = get_browser_manager().get_session(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Browser session {session_id} not found"
        }

    if user_id and session.user_id != user_id:
        return {
            "success": False,
            "error": "Session belongs to different user"
        }

    try:
        # Get page info
        title = await session.page.title()
        url = session.page.url

        # Get cookies
        cookies = await session.context.cookies()

        logger.info(f"Retrieved page info for session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "title": title,
            "url": url,
            "cookies_count": len(cookies)
        }

    except Exception as e:
        logger.error(f"Failed to get page info for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }
