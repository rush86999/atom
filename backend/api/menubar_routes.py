"""
Menu Bar Companion API Routes

Provides endpoints for the macOS menu bar companion app:
- Authentication
- Recent agents and canvases
- Quick chat
- Connection status
- Command execution
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.database import get_db
from core.models import (
    MenuBarAudit,
    User,
    DeviceNode,
    AgentRegistry,
    AgentExecution,
    CanvasAudit,
)
from core.auth import verify_password, create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/menubar",
    tags=["menubar"],
)

# ============================================================================
# Pydantic Models
# ============================================================================


class MenuBarLoginRequest(BaseModel):
    """Menu bar login request"""
    email: str
    password: str
    device_name: str = Field(default="MenuBar")
    platform: str = Field(default="darwin")
    app_version: Optional[str] = None


class MenuBarLoginResponse(BaseModel):
    """Menu bar login response"""
    success: bool
    access_token: Optional[str] = None
    device_id: Optional[str] = None
    user: Optional[dict] = None
    error: Optional[str] = None


class MenuBarAgentSummary(BaseModel):
    """Agent summary for menu bar"""
    id: str
    name: str
    maturity_level: str
    status: str
    last_execution: Optional[datetime] = None
    execution_count: int = 0


class MenuBarCanvasSummary(BaseModel):
    """Canvas summary for menu bar"""
    id: str
    canvas_type: str
    created_at: datetime
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None


class QuickChatRequest(BaseModel):
    """Quick chat request from menu bar"""
    message: str
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[dict] = None


class QuickChatResponse(BaseModel):
    """Quick chat response"""
    success: bool
    response: Optional[str] = None
    execution_id: Optional[str] = None
    agent_id: Optional[str] = None
    error: Optional[str] = None


class ConnectionStatusResponse(BaseModel):
    """Connection status response"""
    status: str  # connected, disconnected, error
    device_id: Optional[str] = None
    last_seen: Optional[datetime] = None
    server_time: datetime


class RecentItemsResponse(BaseModel):
    """Recent items response"""
    agents: List[MenuBarAgentSummary]
    canvases: List[MenuBarCanvasSummary]


# ============================================================================
# Dependencies
# ============================================================================


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/menubar/auth/login", auto_error=False)


async def get_current_menubar_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from menu bar token"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        from jose import jwt, JWTError
        from core.auth import SECRET_KEY, ALGORITHM

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_device_by_token(device_id: str, db: Session) -> Optional[DeviceNode]:
    """Get device by ID"""
    return db.query(DeviceNode).filter(
        DeviceNode.device_id == device_id,
        DeviceNode.app_type == "menubar"
    ).first()


# ============================================================================
# Authentication Endpoints
# ============================================================================


@router.post("/auth/login", response_model=MenuBarLoginResponse)
async def menubar_login(
    request: MenuBarLoginRequest,
    x_platform: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Authenticate menu bar companion app.

    Creates or updates DeviceNode entry for the menu bar app.
    Returns access token for subsequent requests.

    All login attempts are logged to MenuBarAudit.
    """
    try:
        # Create audit entry for login attempt
        audit = MenuBarAudit(
            user_id=None,  # Will set if successful
            device_id=None,  # Will set if successful
            action="login",
            endpoint="/api/menubar/auth/login",
            request_params={"email": request.email},
            platform=request.platform or x_platform,
        )

        # Verify user credentials
        user = db.query(User).filter(User.email == request.email).first()
        if not user or not verify_password(request.password, user.password_hash):
            audit.success = False
            audit.error_message = "Invalid email or password"
            db.add(audit)
            db.commit()

            return MenuBarLoginResponse(
                success=False,
                error="Invalid email or password"
            )

        # Create device node for menu bar app
        device_id = f"menubar_{user.id}_{request.platform}"

        device = db.query(DeviceNode).filter(
            DeviceNode.device_id == device_id
        ).first()

        if device:
            # Update existing device
            device.name = request.device_name
            device.platform = request.platform
            device.app_version = request.app_version
            device.app_type = "menubar"
            device.status = "online"
            device.last_seen = datetime.utcnow()
        else:
            # Create new device
            device = DeviceNode(
                device_id=device_id,
                name=request.device_name,
                platform=request.platform,
                app_version=request.app_version,
                node_type="desktop_mac" if request.platform == "darwin" else "desktop_windows",
                app_type="menubar",
                status="online",
                last_seen=datetime.utcnow(),
                capabilities=["quick_chat", "notification", "hotkey"],
                workspace_id="default",  # Single-tenant
                user_id=str(user.id),  # Set user_id for the device
            )
            db.add(device)

        db.commit()
        db.refresh(device)

        # Create access token
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "device_id": device_id}
        )

        logger.info(f"Menu bar login successful: {user.email}, device: {device_id}")

        # Update audit with success
        audit.user_id = str(user.id)
        audit.device_id = device_id
        audit.success = True
        audit.response_summary = {"device_created": device is not None}
        db.add(audit)
        db.commit()

        return MenuBarLoginResponse(
            success=True,
            access_token=access_token,
            device_id=device_id,
            user={
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        )

    except Exception as e:
        logger.error(f"Menu bar login error: {e}", exc_info=True)

        # Create audit entry for error
        try:
            error_audit = MenuBarAudit(
                user_id=None,
                device_id=None,
                action="login",
                endpoint="/api/menubar/auth/login",
                request_params={"email": request.email},
                success=False,
                error_message=str(e),
                platform=request.platform or x_platform,
            )
            db.add(error_audit)
            db.commit()
        except Exception:
            pass  # Don't fail audit if we're already in error state

        return MenuBarLoginResponse(
            success=False,
            error=str(e)
        )


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    x_device_id: Optional[str] = Header(None),
    current_user: User = Depends(get_current_menubar_user),
    db: Session = Depends(get_db)
):
    """
    Get connection status for menu bar app.

    Updates last_seen timestamp for the device.
    """
    try:
        device_id = x_device_id

        if device_id:
            device = get_device_by_token(device_id, db)
            if device:
                # Update last_seen
                device.last_seen = datetime.utcnow()
                db.commit()

                return ConnectionStatusResponse(
                    status="connected",
                    device_id=device_id,
                    last_seen=device.last_seen,
                    server_time=datetime.utcnow(),
                )

        return ConnectionStatusResponse(
            status="disconnected",
            server_time=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Connection status error: {e}")
        return ConnectionStatusResponse(
            status="error",
            server_time=datetime.utcnow(),
        )


# ============================================================================
# Recent Items Endpoints
# ============================================================================


@router.get("/recent/agents", response_model=List[MenuBarAgentSummary])
async def get_recent_agents(
    limit: int = 5,
    current_user: User = Depends(get_current_menubar_user),
    db: Session = Depends(get_db)
):
    """
    Get recently used agents for menu bar quick access.

    Returns top 5 agents by recent execution count.
    """
    try:
        # Get agents with recent executions
        recent_executions = db.query(
            AgentRegistry.id,
            AgentRegistry.name,
            AgentRegistry.status,
            func.max(AgentExecution.started_at).label('last_execution'),
            func.count(AgentExecution.id).label('execution_count')
        ).join(
            AgentExecution, AgentRegistry.id == AgentExecution.agent_id
        ).filter(
            AgentRegistry.status.in_(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
        ).group_by(
            AgentRegistry.id
        ).order_by(
            desc('last_execution')
        ).limit(limit).all()

        agents = []
        for agent_id, name, agent_status, last_exec, count in recent_executions:
            agents.append(MenuBarAgentSummary(
                id=str(agent_id),
                name=name,
                maturity_level=agent_status,
                status=agent_status,
                last_execution=last_exec,
                execution_count=count,
            ))

        return agents

    except Exception as e:
        logger.error(f"Recent agents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/recent/canvases", response_model=List[MenuBarCanvasSummary])
async def get_recent_canvases(
    limit: int = 5,
    current_user: User = Depends(get_current_menubar_user),
    db: Session = Depends(get_db)
):
    """
    Get recently presented canvases for menu bar quick access.

    Returns top 5 canvases by creation time.
    """
    try:
        recent_canvases = db.query(CanvasAudit).order_by(
            desc(CanvasAudit.created_at)
        ).limit(limit).all()

        canvases = []
        for canvas in recent_canvases:
            # Get agent name if available
            agent_name = None
            if canvas.agent_id:
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == canvas.agent_id
                ).first()
                if agent:
                    agent_name = agent.name

            canvases.append(MenuBarCanvasSummary(
                id=str(canvas.id),
                canvas_type=canvas.canvas_type or "generic",
                created_at=canvas.created_at,
                agent_id=str(canvas.agent_id) if canvas.agent_id else None,
                agent_name=agent_name,
            ))

        return canvases

    except Exception as e:
        logger.error(f"Recent canvases error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/recent", response_model=RecentItemsResponse)
async def get_recent_items(
    agent_limit: int = 5,
    canvas_limit: int = 5,
    current_user: User = Depends(get_current_menubar_user),
    db: Session = Depends(get_db)
):
    """
    Get both recent agents and canvases in a single request.
    """
    agents = await get_recent_agents(agent_limit, current_user, db)
    canvases = await get_recent_canvases(canvas_limit, current_user, db)

    return RecentItemsResponse(
        agents=agents,
        canvases=canvases,
    )


# ============================================================================
# Quick Chat Endpoint
# ============================================================================


@router.post("/quick/chat", response_model=QuickChatResponse)
async def quick_chat(
    request: QuickChatRequest,
    x_device_id: Optional[str] = Header(None),
    x_platform: Optional[str] = Header(None),
    current_user: User = Depends(get_current_menubar_user),
    db: Session = Depends(get_db)
):
    """
    Send quick chat message from menu bar.

    Forwards the message to the agent execution service.
    Returns the agent's response.

    Governance:
    - All agent-triggered actions logged to MenuBarAudit
    - Agent maturity validated before execution
    """
    agent_id = None
    agent_execution_id = None
    agent_maturity = None
    governance_check_passed = None

    try:
        # Create audit entry for the request
        audit = MenuBarAudit(
            user_id=str(current_user.id),
            device_id=x_device_id,
            action="quick_chat",
            endpoint="/api/menubar/quick/chat",
            request_params={"message": request.message[:200]},  # Truncate for audit
            platform=x_platform,
        )

        # Select agent
        agent_id = request.agent_id
        if not agent_id:
            # Use default AUTONOMOUS agent
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.status == "AUTONOMOUS"
            ).first()
            if agent:
                agent_id = str(agent.id)
            else:
                # Fallback to SUPERVISED
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.status == "SUPERVISED"
                ).first()
                if agent:
                    agent_id = str(agent.id)
                else:
                    audit.success = False
                    audit.error_message = "No agents available"
                    db.add(audit)
                    db.commit()

                    return QuickChatResponse(
                        success=False,
                        error="No agents available"
                    )

        # Resolve agent and check governance
        resolver = AgentContextResolver(db)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(current_user.id),
            requested_agent_id=agent_id,
            action_type="quick_chat"
        )

        if agent:
            agent_id = str(agent.id)
            agent_maturity = agent.status
            audit.agent_id = agent_id

            # Check governance
            governance = AgentGovernanceService(db)
            governance_check = governance.can_perform_action(
                agent_id=agent_id,
                action_type="quick_chat"
            )

            governance_check_passed = governance_check.get("allowed", True)
            audit.governance_check_passed = governance_check_passed

            if not governance_check_passed:
                audit.success = False
                audit.error_message = "Governance check failed"
                db.add(audit)
                db.commit()

                return QuickChatResponse(
                    success=False,
                    error="Agent not authorized for quick chat",
                    agent_id=agent_id,
                )

        # Update device last_command_at
        if x_device_id:
            device = get_device_by_token(x_device_id, db)
            if device:
                device.last_command_at = datetime.utcnow()
                device.last_seen = datetime.utcnow()
                db.commit()

        # Execute agent chat using the agent execution service
        from core.agent_execution_service import execute_agent_chat

        result = await execute_agent_chat(
            agent_id=agent_id,
            message=request.message,
            user_id=str(current_user.id),
            session_id=request.session_id,
            workspace_id="default",  # Single-tenant: always use default
            stream=False  # Menubar uses simple request/response, no WebSocket
        )

        if not result.get("success"):
            audit.success = False
            audit.error_message = result.get("error", "Unknown error")
            audit.agent_execution_id = result.get("execution_id")
            db.add(audit)
            db.commit()

            return QuickChatResponse(
                success=False,
                error=result.get("error", "Unknown error"),
                agent_id=agent_id,
            )

        audit.success = True
        audit.agent_execution_id = result.get("execution_id")
        audit.response_summary = {"response_length": len(result.get("response", ""))}
        db.add(audit)
        db.commit()

        return QuickChatResponse(
            success=True,
            response=result.get("response", ""),
            execution_id=result.get("execution_id", ""),
            agent_id=agent_id,
            session_id=result.get("session_id"),
        )

    except Exception as e:
        logger.error(f"Quick chat error: {e}", exc_info=True)

        # Create audit entry for error
        try:
            error_audit = MenuBarAudit(
                user_id=str(current_user.id),
                device_id=x_device_id,
                agent_id=agent_id,
                agent_execution_id=agent_execution_id,
                action="quick_chat",
                endpoint="/api/menubar/quick/chat",
                request_params={"message": request.message[:200] if request else ""},
                success=False,
                error_message=str(e),
                platform=x_platform,
                agent_maturity=agent_maturity,
                governance_check_passed=governance_check_passed
            )
            db.add(error_audit)
            db.commit()
        except Exception:
            pass  # Don't fail audit if we're already in error state

        return QuickChatResponse(
            success=False,
            error=str(e)
        )


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def menubar_health():
    """Health check endpoint for menu bar app"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
