"""
Advanced Workflow Debugging API Endpoints

Provides REST endpoints for:
- Variable modification during debugging
- Debug session persistence (export/import)
- Performance profiling
- Collaborative debugging
- Real-time trace streaming
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.workflow_debugger import WorkflowDebugger

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/workflows/debug", tags=["debugging-advanced"])


# ==================== Request/Response Models ====================

class ModifyVariableRequest(BaseModel):
    """Request to modify a variable during debugging."""
    session_id: str = Field(..., description="Debug session ID")
    variable_name: str = Field(..., description="Name of variable to modify")
    new_value: Any = Field(..., description="New value for the variable")
    scope: str = Field(default="local", description="Variable scope (local, global, workflow, context)")
    trace_id: Optional[str] = Field(None, description="Trace ID for audit trail")


class BulkModifyVariablesRequest(BaseModel):
    """Request to modify multiple variables at once."""
    session_id: str = Field(..., description="Debug session ID")
    modifications: List[Dict[str, Any]] = Field(..., description="List of {variable_name, new_value} dicts")
    scope: str = Field(default="local", description="Variable scope")


class ExportSessionResponse(BaseModel):
    """Response containing exported debug session data."""
    session: Dict[str, Any]
    breakpoints: List[Dict[str, Any]]
    traces: List[Dict[str, Any]]
    exported_at: str


class ImportSessionRequest(BaseModel):
    """Request to import a previously exported debug session."""
    export_data: Dict[str, Any]
    restore_breakpoints: bool = Field(default=True, description="Restore breakpoints")
    restore_variables: bool = Field(default=True, description="Restore variable state")


class PerformanceReportResponse(BaseModel):
    """Performance profiling report."""
    session_id: str
    total_duration_ms: int
    total_steps: int
    average_step_duration_ms: float
    slowest_steps: List[Dict[str, Any]]
    slowest_nodes: List[Dict[str, Any]]
    profiling_started_at: Optional[str]
    generated_at: str


class AddCollaboratorRequest(BaseModel):
    """Request to add a collaborator to a debug session."""
    session_id: str = Field(..., description="Debug session ID")
    user_id: str = Field(..., description="User ID of collaborator")
    permission: str = Field(default="viewer", description="Permission level: viewer, operator, owner")


class CreateTraceStreamRequest(BaseModel):
    """Request to create a trace stream for real-time updates."""
    session_id: str = Field(..., description="Debug session ID")
    execution_id: str = Field(..., description="Execution ID")


# ==================== Variable Modification Endpoints ====================

@router.post("/variables/modify")
async def modify_variable(
    request: ModifyVariableRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Modify a variable value during debugging.

    Allows changing variable values at runtime to test different scenarios.
    """
    debugger = WorkflowDebugger(db)
    result = debugger.modify_variable(
        session_id=request.session_id,
        variable_name=request.variable_name,
        new_value=request.new_value,
        scope=request.scope,
        trace_id=request.trace_id,
    )

    if not result:
        raise router.not_found_error("Debug session", request.session_id)

    return router.success_response(
        data={
            "variable": {
                "variable_id": result.id,
                "variable_name": result.variable_name,
                "variable_type": result.variable_type,
                "value": result.value,
                "value_preview": result.value_preview,
                "scope": result.scope,
                "is_changed": result.is_changed,
                "previous_value": result.previous_value,
            }
        },
        message="Variable modified successfully"
    )


@router.post("/variables/modify-bulk")
async def bulk_modify_variables(
    request: BulkModifyVariablesRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Modify multiple variables at once.

    Efficiently updates multiple variables in a single request.
    """
    debugger = WorkflowDebugger(db)
    results = debugger.bulk_modify_variables(
        session_id=request.session_id,
        modifications=request.modifications,
        scope=request.scope,
    )

    return router.success_response(
        data={
            "modified_count": len(results),
            "variables": [
                {
                    "variable_id": v.id,
                    "variable_name": v.variable_name,
                    "value": v.value,
                    "is_changed": v.is_changed,
                }
                for v in results
            ]
        },
        message=f"Modified {len(results)} variables"
    )


# ==================== Session Persistence Endpoints ====================

@router.get("/sessions/{session_id}/export")
async def export_debug_session(
    session_id: str,
    db: Session = Depends(get_db)
) -> ExportSessionResponse:
    """
    Export a debug session to JSON for persistence.

    Returns complete session data including breakpoints and traces.
    """
    debugger = WorkflowDebugger(db)
    export_data = debugger.export_session(session_id)

    if not export_data:
        raise router.not_found_error("Debug session", session_id)

    return ExportSessionResponse(**export_data)


@router.post("/sessions/import")
async def import_debug_session(
    request: ImportSessionRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Import a previously exported debug session.

    Creates a new debug session from exported data.
    """
    debugger = WorkflowDebugger(db)
    new_session = debugger.import_session(
        export_data=request.export_data,
        restore_breakpoints=request.restore_breakpoints,
        restore_variables=request.restore_variables,
    )

    if not new_session:
        raise router.internal_error("Failed to import session")

    return router.success_response(
        data={
            "session_id": new_session.id,
            "workflow_id": new_session.workflow_id,
            "session_name": new_session.session_name,
            "status": new_session.status,
        },
        message="Debug session imported successfully"
    )


# ==================== Performance Profiling Endpoints ====================

@router.post("/sessions/{session_id}/profiling/start")
async def start_performance_profiling(
    session_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start performance profiling for a debug session.

    Records execution time for each step to identify bottlenecks.
    """
    debugger = WorkflowDebugger(db)
    success = debugger.start_performance_profiling(session_id)

    if not success:
        raise router.not_found_error("Debug session", session_id)

    return router.success_response(message="Performance profiling started")


@router.post("/profiling/record-timing")
async def record_step_timing(
    session_id: str,
    node_id: str,
    node_type: str,
    duration_ms: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Record timing data for a workflow step.

    Called by the workflow engine during execution when profiling is enabled.
    """
    debugger = WorkflowDebugger(db)
    success = debugger.record_step_timing(
        session_id=session_id,
        node_id=node_id,
        node_type=node_type,
        duration_ms=duration_ms,
    )

    if not success:
        raise router.validation_error("timing", "Failed to record timing")

    return router.success_response(message="Timing recorded successfully")


@router.get("/sessions/{session_id}/profiling/report")
async def get_performance_report(
    session_id: str,
    db: Session = Depends(get_db)
) -> PerformanceReportResponse:
    """
    Generate a performance report for a debug session.

    Returns aggregated timing data and bottleneck identification.
    """
    debugger = WorkflowDebugger(db)
    report = debugger.get_performance_report(session_id)

    if not report:
        raise router.not_found_error("Performance report", session_id)

    return PerformanceReportResponse(**report)


# ==================== Collaborative Debugging Endpoints ====================

@router.post("/sessions/{session_id}/collaborators")
async def add_collaborator(
    session_id: str,
    user_id: str,
    permission: str = Query("viewer", description="Permission level: viewer, operator, owner"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add a collaborator to a debug session.

    Permissions:
    - viewer: Can view session state and traces
    - operator: Can control execution (step, pause, continue)
    - owner: Full control including modifying breakpoints and variables
    """
    debugger = WorkflowDebugger(db)
    success = debugger.add_collaborator(session_id, user_id, permission)

    if not success:
        raise router.not_found_error("Debug session", session_id)

    return router.success_response(message=f"Added collaborator {user_id}")


@router.delete("/sessions/{session_id}/collaborators/{user_id}")
async def remove_collaborator(
    session_id: str,
    user_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Remove a collaborator from a debug session."""
    debugger = WorkflowDebugger(db)
    success = debugger.remove_collaborator(session_id, user_id)

    if not success:
        raise router.not_found_error("Collaborator", user_id)

    return router.success_response(message=f"Removed collaborator {user_id}")


@router.get("/sessions/{session_id}/collaborators")
async def get_session_collaborators(
    session_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get all collaborators for a debug session."""
    debugger = WorkflowDebugger(db)
    collaborators = debugger.get_session_collaborators(session_id)

    return router.success_response(
        data={
            "session_id": session_id,
            "collaborators": collaborators,
            "count": len(collaborators),
        },
        message=f"Retrieved {len(collaborators)} collaborators"
    )


@router.get("/sessions/{session_id}/collaborators/{user_id}/permissions")
async def check_collaborator_permission(
    session_id: str,
    user_id: str,
    required_permission: str = Query(..., description="Required permission level"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check if a collaborator has the required permission.

    Permission hierarchy: viewer < operator < owner
    """
    debugger = WorkflowDebugger(db)
    has_permission = debugger.check_collaborator_permission(
        session_id, user_id, required_permission
    )

    return router.success_response(
        data={
            "session_id": session_id,
            "user_id": user_id,
            "required_permission": required_permission,
            "has_permission": has_permission,
        }
    )


# ==================== Real-time Trace Streaming Endpoints ====================

@router.post("/streams/create")
async def create_trace_stream(
    request: CreateTraceStreamRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a unique stream ID for real-time trace updates.

    Returns a stream ID that can be used with WebSocket connections.
    """
    debugger = WorkflowDebugger(db)
    stream_id = debugger.create_trace_stream(
        session_id=request.session_id,
        execution_id=request.execution_id,
    )

    return router.success_response(
        data={
            "stream_id": stream_id,
            "websocket_url": f"ws://localhost:8000/api/debug/streams/{stream_id}",
        },
        message="Trace stream created successfully"
    )


@router.post("/streams/{stream_id}/close")
async def close_trace_stream(
    stream_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Close a trace stream and clean up resources."""
    debugger = WorkflowDebugger(db)
    success = debugger.close_trace_stream(stream_id)

    if success:
        return router.success_response(
            data={"stream_id": stream_id},
            message="Stream closed successfully"
        )
    else:
        return router.success_response(
            data={"stream_id": stream_id},
            message="Failed to close stream"
        )
