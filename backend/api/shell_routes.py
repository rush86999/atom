"""
Shell Routes - REST API for host shell command execution.

OpenClaw Integration: AUTONOMOUS agents can execute shell commands
on host filesystem through governed API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from core.host_shell_service import host_shell_service
from core.models import get_db, ShellSession
from core.agent_governance_service import agent_governance_service

router = APIRouter(prefix="/api/shell", tags=["Shell"])


class ShellCommandRequest(BaseModel):
    command: str
    working_directory: Optional[str] = None
    timeout: int = 300  # 5 minutes default


class ShellCommandResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    session_id: str
    duration_seconds: float


@router.post("/execute", response_model=ShellCommandResponse)
async def execute_shell_command(
    request: ShellCommandRequest,
    agent_id: str,
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Execute shell command on host filesystem.

    **Governance Requirements:**
    - Agent must be AUTONOMOUS maturity level
    - Command must be in whitelist (ls, cat, grep, git, npm, etc.)
    - Blocked commands are rejected (rm, mv, chmod, kill, sudo, etc.)
    - Working directory must be within allowed mount points
    - 5-minute timeout enforced

    **Audit Trail:**
    - All commands logged to ShellSession table
    - Includes command, exit code, stdout, stderr, duration
    - Traceable by agent_id and user_id

    **OpenClaw Integration:**
    This provides the "God Mode" local agent capability with
    Atom's governance-first approach (AUTONOMOUS gate + whitelist).
    """
    try:
        # Validate command first (fast check)
        validation = host_shell_service.validate_command(request.command)

        if not validation.get("valid"):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Command validation failed",
                    "reason": validation.get("reason"),
                    "allowed_commands": validation.get("allowed_commands")
                }
            )

        # Execute with governance checks
        result = await host_shell_service.execute_shell_command(
            agent_id=agent_id,
            user_id=user_id,
            command=request.command,
            working_directory=request.working_directory,
            timeout=request.timeout,
            db=db
        )

        return ShellCommandResponse(**result)

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shell execution failed: {str(e)}")


@router.get("/sessions")
async def list_shell_sessions(
    agent_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List shell command execution sessions.

    Returns audit trail of shell commands executed by agents.
    """
    query = db.query(ShellSession)

    if agent_id:
        query = query.filter(ShellSession.agent_id == agent_id)

    sessions = query.order_by(ShellSession.started_at.desc()).limit(limit).all()

    return {
        "sessions": [
            {
                "id": s.id,
                "agent_id": s.agent_id,
                "command": s.command,
                "exit_code": s.exit_code,
                "timed_out": s.timed_out,
                "started_at": s.started_at.isoformat(),
                "duration_seconds": s.duration_seconds
            }
            for s in sessions
        ]
    }


@router.get("/validate")
async def validate_command(command: str):
    """
    Validate shell command against whitelist.

    Fast validation without execution.
    """
    result = host_shell_service.validate_command(command)
    return result
