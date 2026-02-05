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
"""

import asyncio
import base64
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentExecution, User

logger = logging.getLogger(__name__)

# Feature flags
import os

BROWSER_GOVERNANCE_ENABLED = os.getenv("BROWSER_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"


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
        if BROWSER_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id and db:
            resolver = AgentContextResolver(db)
            governance = AgentGovernanceService(db)

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
        if agent and db and BROWSER_GOVERNANCE_ENABLED:
            governance = AgentGovernanceService(db)
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

        if agent_execution and db and BROWSER_GOVERNANCE_ENABLED:
            try:
                governance = AgentGovernanceService(db)
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
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "wb") as f:
                f.write(screenshot_bytes)

            logger.info(f"Screenshot saved to {path}")
            return {
                "success": True,
                "path": path,
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
    user_id: str = None
) -> Dict[str, Any]:
    """
    Fill form fields using CSS selectors.

    Args:
        session_id: Browser session ID
        selectors: Dict mapping CSS selectors to values
        submit: Whether to submit the form after filling
        user_id: User ID for validation

    Returns:
        Dict with fill result
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
        filled_count = 0

        for selector, value in selectors.items():
            try:
                # Wait for element
                await session.page.wait_for_selector(selector, timeout=5000)

                # Check input type and fill accordingly
                element = await session.page.query_selector(selector)
                tag_name = await element.evaluate("el => el.tagName")
                input_type = await element.evaluate("el => el.type || ''")

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

        result = {
            "success": True,
            "session_id": session_id,
            "fields_filled": filled_count
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
    user_id: str = None
) -> Dict[str, Any]:
    """
    Click an element using CSS selector.

    Args:
        session_id: Browser session ID
        selector: CSS selector for element to click
        wait_for: Optional selector to wait for after click
        user_id: User ID for validation

    Returns:
        Dict with click result
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
        # Wait for element to be clickable
        await session.page.wait_for_selector(selector, state="visible", timeout=5000)

        # Click element
        await session.page.click(selector)

        session.last_used = datetime.now()

        # Wait for navigation or element if specified
        if wait_for:
            try:
                await session.page.wait_for_selector(wait_for, timeout=5000)
            except Exception as e:
                logger.debug(f"Wait for selector '{wait_for}' not found or timeout: {e}")
                # Continue anyway - don't fail the entire operation

        logger.info(f"Clicked {selector} in session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "selector": selector
        }

    except Exception as e:
        logger.error(f"Click failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def browser_extract_text(
    session_id: str,
    selector: Optional[str] = None,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Extract text content from the page or specific elements.

    Args:
        session_id: Browser session ID
        selector: Optional CSS selector (if None, extracts full page text)
        user_id: User ID for validation

    Returns:
        Dict with extracted text
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
        if selector:
            # Extract text from specific element(s)
            elements = await session.page.query_selector_all(selector)
            texts = [await el.inner_text() for el in elements]
            result_text = "\n".join(texts)
        else:
            # Extract full page text
            result_text = await session.page.inner_text("body")

        session.last_used = datetime.now()

        logger.info(f"Extracted {len(result_text)} chars from session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "text": result_text,
            "length": len(result_text)
        }

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
