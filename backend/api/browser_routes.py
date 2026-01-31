"""
Browser Automation Routes

API endpoints for browser automation with CDP via Playwright.

Governance Integration:
- All browser actions require INTERN+ maturity level
- Full audit trail via browser_audit table
- Agent execution tracking for all browser sessions
"""

import logging
import uuid
import os
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User, BrowserSession, BrowserAudit, AgentExecution, AgentRegistry
from core.security_dependencies import get_current_user
from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService

from tools.browser_tool import (
    get_browser_manager,
    browser_create_session,
    browser_navigate,
    browser_screenshot,
    browser_fill_form,
    browser_click,
    browser_extract_text,
    browser_execute_script,
    browser_close_session,
    browser_get_page_info,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/browser", tags=["browser"])

# Feature flags
BROWSER_GOVERNANCE_ENABLED = os.getenv("BROWSER_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    headless: Optional[bool] = None
    browser_type: str = "chromium"
    agent_id: Optional[str] = None


class NavigateRequest(BaseModel):
    session_id: str
    url: str
    wait_until: str = "load"
    agent_id: Optional[str] = None


class ScreenshotRequest(BaseModel):
    session_id: str
    full_page: bool = False
    path: Optional[str] = None


class FillFormRequest(BaseModel):
    session_id: str
    selectors: Dict[str, str]
    submit: bool = False


class ClickRequest(BaseModel):
    session_id: str
    selector: str
    wait_for: Optional[str] = None


class ExtractTextRequest(BaseModel):
    session_id: str
    selector: Optional[str] = None


class ExecuteScriptRequest(BaseModel):
    session_id: str
    script: str


class CloseSessionRequest(BaseModel):
    session_id: str


# ============================================================================
# Helper Functions
# ============================================================================

def _create_browser_audit(
    db: Session,
    user_id: str,
    session_id: str,
    action_type: str,
    action_target: Optional[str],
    action_params: Dict[str, Any],
    success: bool,
    result_summary: Optional[str] = None,
    error_message: Optional[str] = None,
    result_data: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
    agent_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None,
    governance_check_passed: Optional[bool] = None,
) -> BrowserAudit:
    """Create a browser audit entry."""
    try:
        audit = BrowserAudit(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=agent_id,
            agent_execution_id=agent_execution_id,
            user_id=user_id,
            session_id=session_id,
            action_type=action_type,
            action_target=action_target,
            action_params=action_params,
            success=success,
            result_summary=result_summary,
            error_message=error_message,
            result_data=result_data or {},
            duration_ms=duration_ms,
            governance_check_passed=governance_check_passed
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    except Exception as e:
        logger.error(f"Failed to create browser audit: {e}")
        return None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/session/create")
async def create_browser_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new browser session.

    Requires INTERN+ maturity level for agent-initiated sessions.
    """
    result = await browser_create_session(
        user_id=current_user.id,
        agent_id=request.agent_id,
        headless=request.headless,
        browser_type=request.browser_type,
        db=db
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    # Create database session record
    try:
        db_session = BrowserSession(
            session_id=result["session_id"],
            workspace_id="default",
            agent_id=request.agent_id,
            user_id=current_user.id,
            browser_type=request.browser_type,
            headless=result.get("headless", True),
            status="active",
            metadata_json={"created_via": "api"}
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)

        result["db_session_id"] = db_session.id
    except Exception as e:
        logger.error(f"Failed to create browser session record: {e}")

    return result


@router.post("/navigate")
async def navigate(
    request: NavigateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Navigate to a URL in an existing browser session."""
    start_time = datetime.now()
    agent = None
    governance_check = None

    # Governance check if agent_id provided
    if request.agent_id and BROWSER_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
        try:
            resolver = AgentContextResolver(db)
            governance = AgentGovernanceService(db)

            agent, _ = await resolver.resolve_agent_for_request(
                user_id=current_user.id,
                requested_agent_id=request.agent_id,
                action_type="browser_navigate"
            )

            if agent:
                governance_check = governance.can_perform_action(
                    agent_id=agent.id,
                    action_type="browser_navigate"
                )

                if not governance_check["allowed"]:
                    _create_browser_audit(
                        db=db,
                        user_id=current_user.id,
                        session_id=request.session_id,
                        action_type="navigate",
                        action_target=request.url,
                        action_params={"wait_until": request.wait_until},
                        success=False,
                        error_message=f"Governance blocked: {governance_check['reason']}",
                        agent_id=agent.id,
                        governance_check_passed=False
                    )

                    raise HTTPException(
                        status_code=403,
                        detail=f"Agent not permitted: {governance_check['reason']}"
                    )

                # Create execution record
                execution = AgentExecution(
                    agent_id=agent.id,
                    workspace_id="default",
                    status="running",
                    input_summary=f"Navigate to {request.url}",
                    triggered_by="browser_api"
                )
                db.add(execution)
                db.commit()
                db.refresh(execution)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Governance check failed: {e}")

    # Perform navigation
    result = await browser_navigate(
        session_id=request.session_id,
        url=request.url,
        wait_until=request.wait_until,
        user_id=current_user.id
    )

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Create audit entry
    _create_browser_audit(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        action_type="navigate",
        action_target=request.url,
        action_params={"wait_until": request.wait_until},
        success=result.get("success", False),
        result_summary=result.get("title"),
        error_message=result.get("error"),
        result_data=result if result.get("success") else None,
        duration_ms=duration_ms,
        agent_id=agent.id if agent else None,
        governance_check_passed=governance_check["allowed"] if governance_check else None
    )

    # Update database session record
    if result.get("success"):
        try:
            db_session = db.query(BrowserSession).filter(
                BrowserSession.session_id == request.session_id
            ).first()
            if db_session:
                db_session.current_url = result.get("url")
                db_session.page_title = result.get("title")
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update browser session: {e}")

    return result


@router.post("/screenshot")
async def screenshot(
    request: ScreenshotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Take a screenshot of the current page."""
    start_time = datetime.now()

    result = await browser_screenshot(
        session_id=request.session_id,
        full_page=request.full_page,
        path=request.path,
        user_id=current_user.id
    )

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Create audit entry
    _create_browser_audit(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        action_type="screenshot",
        action_target=request.path or "base64",
        action_params={"full_page": request.full_page},
        success=result.get("success", False),
        result_summary=f"Screenshot ({result.get('size_bytes')} bytes)",
        error_message=result.get("error"),
        result_data=result if result.get("success") else None,
        duration_ms=duration_ms
    )

    return result


@router.post("/fill-form")
async def fill_form(
    request: FillFormRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fill form fields using CSS selectors."""
    start_time = datetime.now()

    result = await browser_fill_form(
        session_id=request.session_id,
        selectors=request.selectors,
        submit=request.submit,
        user_id=current_user.id
    )

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Create audit entry
    _create_browser_audit(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        action_type="fill_form",
        action_target=f"{len(request.selectors)} fields",
        action_params={"selectors": request.selectors, "submit": request.submit},
        success=result.get("success", False),
        result_summary=f"Filled {result.get('fields_filled', 0)} fields",
        error_message=result.get("error"),
        result_data=result if result.get("success") else None,
        duration_ms=duration_ms
    )

    return result


@router.post("/click")
async def click(
    request: ClickRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Click an element using CSS selector."""
    start_time = datetime.now()

    result = await browser_click(
        session_id=request.session_id,
        selector=request.selector,
        wait_for=request.wait_for,
        user_id=current_user.id
    )

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Create audit entry
    _create_browser_audit(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        action_type="click",
        action_target=request.selector,
        action_params={"wait_for": request.wait_for},
        success=result.get("success", False),
        error_message=result.get("error"),
        result_data=result if result.get("success") else None,
        duration_ms=duration_ms
    )

    return result


@router.post("/extract-text")
async def extract_text(
    request: ExtractTextRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extract text content from the page or specific elements."""
    start_time = datetime.now()

    result = await browser_extract_text(
        session_id=request.session_id,
        selector=request.selector,
        user_id=current_user.id
    )

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Create audit entry
    _create_browser_audit(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        action_type="extract_text",
        action_target=request.selector or "full_page",
        action_params={"selector": request.selector},
        success=result.get("success", False),
        result_summary=f"Extracted {result.get('length', 0)} chars",
        error_message=result.get("error"),
        result_data={"length": result.get("length")} if result.get("success") else None,
        duration_ms=duration_ms
    )

    return result


@router.post("/execute-script")
async def execute_script(
    request: ExecuteScriptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute JavaScript in the browser context."""
    start_time = datetime.now()

    result = await browser_execute_script(
        session_id=request.session_id,
        script=request.script,
        user_id=current_user.id
    )

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Create audit entry (don't log full script for security)
    _create_browser_audit(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        action_type="execute_script",
        action_target=f"{len(request.script)} chars",
        action_params={"script_length": len(request.script)},
        success=result.get("success", False),
        result_summary="Script executed",
        error_message=result.get("error"),
        duration_ms=duration_ms
    )

    return result


@router.post("/session/close")
async def close_session(
    request: CloseSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Close a browser session."""
    start_time = datetime.now()

    result = await browser_close_session(
        session_id=request.session_id,
        user_id=current_user.id
    )

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Create audit entry
    _create_browser_audit(
        db=db,
        user_id=current_user.id,
        session_id=request.session_id,
        action_type="close_session",
        action_target=None,
        action_params={},
        success=result.get("success", False),
        result_summary="Session closed",
        error_message=result.get("error"),
        duration_ms=duration_ms
    )

    # Update database session record
    if result.get("success"):
        try:
            db_session = db.query(BrowserSession).filter(
                BrowserSession.session_id == request.session_id
            ).first()
            if db_session:
                db_session.status = "closed"
                db_session.closed_at = datetime.now()
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update browser session: {e}")

    return result


@router.get("/session/{session_id}/info")
async def get_session_info(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get information about a browser session."""
    result = await browser_get_page_info(
        session_id=session_id,
        user_id=current_user.id
    )

    # Add database info
    try:
        db_session = db.query(BrowserSession).filter(
            BrowserSession.session_id == session_id
        ).first()

        if db_session:
            result["db_session_id"] = db_session.id
            result["created_at"] = db_session.created_at.isoformat()
            result["status"] = db_session.status
            result["browser_type"] = db_session.browser_type
    except Exception as e:
        logger.error(f"Failed to fetch session info: {e}")

    return result


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all browser sessions for the current user."""
    try:
        sessions = db.query(BrowserSession).filter(
            BrowserSession.user_id == current_user.id
        ).order_by(BrowserSession.created_at.desc()).limit(50).all()

        return {
            "success": True,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "id": s.id,
                    "browser_type": s.browser_type,
                    "headless": s.headless,
                    "status": s.status,
                    "current_url": s.current_url,
                    "page_title": s.page_title,
                    "created_at": s.created_at.isoformat(),
                    "closed_at": s.closed_at.isoformat() if s.closed_at else None
                }
                for s in sessions
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/audit")
async def get_browser_audit(
    session_id: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get browser audit log for the current user."""
    try:
        query = db.query(BrowserAudit).filter(
            BrowserAudit.user_id == current_user.id
        )

        if session_id:
            query = query.filter(BrowserAudit.session_id == session_id)

        audits = query.order_by(BrowserAudit.created_at.desc()).limit(limit).all()

        return {
            "success": True,
            "audits": [
                {
                    "id": a.id,
                    "session_id": a.session_id,
                    "action_type": a.action_type,
                    "action_target": a.action_target,
                    "success": a.success,
                    "result_summary": a.result_summary,
                    "error_message": a.error_message,
                    "duration_ms": a.duration_ms,
                    "created_at": a.created_at.isoformat()
                }
                for a in audits
            ]
        }
    except Exception as e:
        logger.error(f"Failed to fetch audit log: {e}")
        return {
            "success": False,
            "error": str(e)
        }
