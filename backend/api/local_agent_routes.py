"""
Local Agent API Routes - REST endpoints for local agent communication.

Provides execute/approve/status/start/stop endpoints for local agent management.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AgentRegistry, ShellSession
from core.host_shell_service import host_shell_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/local-agent", tags=["local-agent"])


# ============================================================================
# Pydantic Models
# ============================================================================

class ExecuteCommandRequest(BaseModel):
    """Request to execute command via local agent."""
    agent_id: str = Field(..., description="Agent ID requesting execution")
    command: str = Field(..., description="Shell command to execute")
    working_directory: Optional[str] = Field(None, description="Working directory for command")


class ExecuteCommandResponse(BaseModel):
    """Response from command execution."""
    allowed: bool = Field(..., description="Whether execution was allowed")
    exit_code: Optional[int] = Field(None, description="Process exit code")
    stdout: Optional[str] = Field(None, description="Standard output")
    stderr: Optional[str] = Field(None, description="Standard error")
    session_id: Optional[str] = Field(None, description="Shell session ID")
    duration_seconds: Optional[float] = Field(None, description="Execution duration")
    timed_out: Optional[bool] = Field(None, description="Whether command timed out")
    requires_approval: Optional[bool] = Field(None, description="Whether approval is required")
    reason: Optional[str] = Field(None, description="Reason for denial")


class ApproveCommandRequest(BaseModel):
    """Request to approve pending command."""
    agent_id: str = Field(..., description="Agent ID requesting approval")
    command: str = Field(..., description="Command to approve")
    session_id: Optional[str] = Field(None, description="Session ID for approval")


class AgentStatusResponse(BaseModel):
    """Response for local agent status check."""
    running: bool = Field(..., description="Whether local agent is running")
    backend_reachable: bool = Field(..., description="Whether backend is reachable")
    status: str = Field(..., description="Status message")


# ============================================================================
# Error Helpers
# ============================================================================

def _agent_not_found_error(agent_id: str) -> HTTPException:
    """Create 404 error for agent not found."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent '{agent_id}' not found"
    )


def _permission_denied_error(reason: str) -> HTTPException:
    """Create 403 error for permission denied."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=reason
    )


def _command_not_allowed_error(command: str, reason: str) -> HTTPException:
    """Create 400 error for command not allowed."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Command '{command}' not allowed: {reason}"
    )


# ============================================================================
# Routes
# ============================================================================

@router.post("/execute", response_model=ExecuteCommandResponse)
async def execute_command(
    request: ExecuteCommandRequest,
    db: Session = Depends(get_db)
) -> ExecuteCommandResponse:
    """
    Execute command via local agent.

    Flow:
    1. Check agent maturity from database
    2. Validate command against whitelist
    3. Return approval_required if maturity < needed
    4. Execute command if AUTONOMOUS maturity

    Args:
        request: Execute command request
        db: Database session

    Returns:
        ExecuteCommandResponse with execution result or approval status

    Raises:
        HTTPException 404: Agent not found
        HTTPException 403: Permission denied
        HTTPException 400: Command not in whitelist
        HTTPException 503: Backend unreachable
    """
    # Step 1: Get agent from database
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == request.agent_id
    ).first()

    if not agent:
        raise _agent_not_found_error(request.agent_id)

    maturity_level = agent.status

    # Step 2: Check maturity requirements
    # AUTONOMOUS agents can execute without approval
    # STUDENT/INTERN/SUPERVISED require approval
    if maturity_level != "AUTONOMOUS":
        # Return approval required response
        return ExecuteCommandResponse(
            allowed=False,
            requires_approval=True,
            reason=f"Agent maturity {maturity_level} requires approval for shell execution"
        )

    # Step 3: Validate command against whitelist
    validation = host_shell_service.validate_command(request.command)
    if not validation.get("valid", False):
        reason = validation.get("reason", "Unknown")
        raise _command_not_allowed_error(request.command, reason)

    # Step 4: Execute command
    try:
        result = await host_shell_service.execute_shell_command(
            agent_id=request.agent_id,
            user_id="local-agent",
            command=request.command,
            working_directory=request.working_directory,
            timeout=300,
            db=db
        )

        return ExecuteCommandResponse(
            allowed=True,
            exit_code=result.get("exit_code"),
            stdout=result.get("stdout"),
            stderr=result.get("stderr"),
            session_id=result.get("session_id"),
            duration_seconds=result.get("duration_seconds"),
            timed_out=result.get("timed_out", False)
        )

    except PermissionError as e:
        raise _permission_denied_error(str(e))
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Command execution failed: {str(e)}"
        )


@router.post("/approve")
async def approve_command(
    request: ApproveCommandRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Approve pending command for lower maturity agents.

    Allows user to manually approve commands for STUDENT/INTERN/SUPERVISED agents.

    Args:
        request: Approve command request
        db: Database session

    Returns:
        Dict with approval status and session_id

    Raises:
        HTTPException 404: Agent not found
        HTTPException 400: Command not valid
    """
    # Get agent
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == request.agent_id
    ).first()

    if not agent:
        raise _agent_not_found_error(request.agent_id)

    # Validate command
    validation = host_shell_service.validate_command(request.command)
    if not validation.get("valid", False):
        reason = validation.get("reason", "Unknown")
        raise _command_not_allowed_error(request.command, reason)

    # Execute command with manual approval
    try:
        result = await host_shell_service.execute_shell_command(
            agent_id=request.agent_id,
            user_id="local-agent-approver",
            command=request.command,
            working_directory=None,
            timeout=300,
            db=db
        )

        return {
            "success": True,
            "approved": True,
            "session_id": result.get("session_id"),
            "exit_code": result.get("exit_code"),
            "stdout": result.get("stdout"),
            "stderr": result.get("stderr")
        }

    except Exception as e:
        logger.error(f"Approved command execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Command execution failed: {str(e)}"
        )


@router.get("/status", response_model=AgentStatusResponse)
async def get_status(db: Session = Depends(get_db)) -> AgentStatusResponse:
    """
    Check local agent status.

    Returns status of local agent and backend connectivity.

    Args:
        db: Database session

    Returns:
        AgentStatusResponse with running status and backend reachability
    """
    # Check if we can reach the database
    try:
        db.execute("SELECT 1")
        backend_reachable = True
    except:
        backend_reachable = False

    # Check if there are recent shell sessions (local agent active)
    recent_sessions = db.query(ShellSession).filter(
        ShellSession.started_at >= datetime.utcnow().replace(second=0, microsecond=0)
    ).count()

    running = recent_sessions > 0 or backend_reachable

    return AgentStatusResponse(
        running=running,
        backend_reachable=backend_reachable,
        status="running" if running else "not_running"
    )


@router.post("/start")
async def start_local_agent(
    backend_url: str = "http://localhost:8000",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start local agent process.

    Note: This endpoint provides configuration for starting local agent.
    Actual startup should be done via CLI: atom-os local-agent start

    Args:
        backend_url: Backend API URL
        db: Database session

    Returns:
        Dict with start instructions and status
    """
    return {
        "message": "Use CLI to start local agent",
        "command": "atom-os local-agent start",
        "backend_url": backend_url,
        "status": "configured"
    }


@router.post("/stop")
async def stop_local_agent(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Stop local agent process.

    Note: This endpoint signals stop request.
    Actual shutdown should be done via CLI: atom-os local-agent stop

    Args:
        db: Database session

    Returns:
        Dict with stop instructions
    """
    return {
        "message": "Use CLI to stop local agent",
        "command": "atom-os local-agent stop",
        "status": "stop_requested"
    }
