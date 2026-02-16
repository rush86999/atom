"""
Agent Control Routes - REST API for agent-to-agent Atom OS control.

Allows any agent (OpenClaw, Claude, custom) to programmatically control Atom OS:
- Start Atom as background service
- Stop Atom service
- Check status
- Execute commands

Usage:
    import requests

    # Start Atom
    response = requests.post("http://localhost:8000/api/agent/start",
                            json={"port": 8000})

    # Check status
    response = requests.get("http://localhost:8000/api/agent/status")

    # Stop Atom
    response = requests.post("http://localhost:8000/api/agent/stop")
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

# Import daemon manager
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from cli.daemon import DaemonManager

router = APIRouter(prefix="/api/agent", tags=["agent-control"])


# Request/Response Models
class StartAgentRequest(BaseModel):
    """Request model for starting Atom OS service."""

    port: int = Field(default=8000, ge=1, le=65535, description="Port for web server")
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    workers: int = Field(default=1, ge=1, le=16, description="Number of worker processes")
    host_mount: bool = Field(default=False, description="Enable host filesystem mount")
    dev: bool = Field(default=False, description="Enable development mode")


class StartAgentResponse(BaseModel):
    """Response model for start endpoint."""

    success: bool
    pid: Optional[int] = None
    status: str
    dashboard_url: Optional[str] = None
    message: str
    error: Optional[str] = None


class StopAgentResponse(BaseModel):
    """Response model for stop endpoint."""

    success: bool
    status: str
    message: str
    error: Optional[str] = None


class RestartAgentResponse(BaseModel):
    """Response model for restart endpoint."""

    success: bool
    pid: Optional[int] = None
    status: str
    dashboard_url: Optional[str] = None
    was_running: bool
    message: str
    error: Optional[str] = None


class AgentStatusResponse(BaseModel):
    """Response model for status endpoint."""

    success: bool
    status: dict
    message: Optional[str] = None


class ExecuteCommandRequest(BaseModel):
    """Request model for execute endpoint."""

    command: str = Field(..., description="Atom command to execute")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")


class ExecuteCommandResponse(BaseModel):
    """Response model for execute endpoint."""

    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None


# API Endpoints
@router.post("/start", response_model=StartAgentResponse)
async def start_atom(request: StartAgentRequest):
    """Start Atom OS as background service.

    Called by external agents (Claude, OpenClaw, custom agents) to
    programmatically start Atom as a background service.

    **Example:**
        ```python
        import requests

        response = requests.post(
            "http://localhost:8000/api/agent/start",
            json={"port": 8000, "host": "0.0.0.0"}
        )
        print(response.json())
        ```

    **Returns:**
        - success: True if started successfully
        - pid: Process ID of daemon
        - status: "started"
        - dashboard_url: URL to web dashboard
        - message: Success message

    **Raises:**
        - 400: If Atom is already running
        - 500: If daemon fails to start
    """
    try:
        if DaemonManager.is_running():
            current_pid = DaemonManager.get_pid()
            raise HTTPException(
                status_code=400,
                detail=f"Atom OS is already running (PID: {current_pid})"
            )

        pid = DaemonManager.start_daemon(
            port=request.port,
            host=request.host,
            workers=request.workers,
            host_mount=request.host_mount,
            dev=request.dev
        )

        return StartAgentResponse(
            success=True,
            pid=pid,
            status="started",
            dashboard_url=f"http://{request.host}:{request.port}",
            message="Atom OS started successfully"
        )

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=StopAgentResponse)
async def stop_atom():
    """Stop Atom OS background service.

    Gracefully shuts down Atom daemon service.

    **Example:**
        ```python
        import requests

        response = requests.post("http://localhost:8000/api/agent/stop")
        print(response.json())
        ```

    **Returns:**
        - success: True if stopped
        - status: "stopped"
        - message: Success message

    **Raises:**
        - 400: If Atom is not running
        - 500: If stop fails
    """
    try:
        if not DaemonManager.is_running():
            raise HTTPException(
                status_code=400,
                detail="Atom OS is not running"
            )

        DaemonManager.stop_daemon()

        return StopAgentResponse(
            success=True,
            status="stopped",
            message="Atom OS stopped successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart", response_model=RestartAgentResponse)
async def restart_atom(request: StartAgentRequest):
    """Restart Atom OS background service.

    Stops Atom if running, then starts again with new configuration.

    **Example:**
        ```python
        import requests

        response = requests.post(
            "http://localhost:8000/api/agent/restart",
            json={"port": 8000}
        )
        print(response.json())
        ```

    **Returns:**
        - success: True if restarted
        - pid: New process ID
        - status: "restarted"
        - dashboard_url: URL to web dashboard
        - was_running: Whether Atom was running before restart
        - message: Success message

    **Raises:**
        - 500: If restart fails
    """
    try:
        was_running = DaemonManager.is_running()

        if was_running:
            DaemonManager.stop_daemon()

        # Wait for clean shutdown
        import time
        time.sleep(2)

        pid = DaemonManager.start_daemon(
            port=request.port,
            host=request.host,
            workers=request.workers,
            host_mount=request.host_mount,
            dev=request.dev
        )

        return RestartAgentResponse(
            success=True,
            pid=pid,
            status="restarted",
            dashboard_url=f"http://{request.host}:{request.port}",
            was_running=was_running,
            message="Atom OS restarted successfully"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=AgentStatusResponse)
async def get_status():
    """Get Atom OS status and running info.

    Returns current status, PID, uptime, memory usage, and CPU.

    **Example:**
        ```python
        import requests

        response = requests.get("http://localhost:8000/api/agent/status")
        print(response.json())
        ```

    **Returns:**
        - success: True
        - status: Dict with running status, pid, uptime_seconds, memory_mb, cpu_percent

    **Example Response:**
        ```json
        {
            "success": true,
            "status": {
                "running": true,
                "pid": 12345,
                "uptime_seconds": 3600,
                "memory_mb": 256.5,
                "cpu_percent": 5.2,
                "status": "running"
            }
        }
        ```
    """
    try:
        status_info = DaemonManager.get_status()

        return AgentStatusResponse(
            success=True,
            status=status_info
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ExecuteCommandResponse)
async def execute_atom_command(request: ExecuteCommandRequest):
    """Execute single Atom command and return result.

    Useful for one-off tasks from other agents. Starts Atom temporarily,
    executes command, and shuts down.

    **Note:** Command routing not yet fully implemented.
    Use POST /api/agent/start to run Atom as service instead.

    **Example:**
        ```python
        import requests

        response = requests.post(
            "http://localhost:8000/api/agent/execute",
            json={"command": "agent.chat('Hello, create a report')"}
        )
        print(response.json())
        ```

    **Returns:**
        - success: True
        - result: Command execution result (when implemented)
        - note: Implementation status message

    **Note:**
        This endpoint is currently a placeholder. Use daemon mode for
        full Atom functionality:

        ```bash
        # Start as service
        atom-os daemon

        # Or via API
        curl -X POST http://localhost:8000/api/agent/start
        ```
    """
    return ExecuteCommandResponse(
        success=True,
        result="Command execution not yet implemented",
        note="Use POST /api/agent/start to run Atom as service instead"
    )
