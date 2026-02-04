"""
Workflow Debugging API Endpoints

RESTful API endpoints for workflow debugging functionality including:
- Debug session management
- Breakpoint operations
- Step execution control
- Variable inspection
- Execution trace viewing
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.workflow_debugger import WorkflowDebugger

logger = logging.getLogger(__name__)

# Initialize router
router = BaseAPIRouter(prefix="/api/workflows", tags=["workflow-debugging"])

# Request/Response Models

class CreateDebugSessionRequest(BaseModel):
    """Request model for creating a debug session"""
    workflow_id: str = Field(..., description="ID of the workflow to debug")
    execution_id: Optional[str] = Field(None, description="Associated execution ID")
    session_name: Optional[str] = Field(None, description="Name for the debug session")
    stop_on_entry: bool = Field(False, description="Pause on first step")
    stop_on_exceptions: bool = Field(True, description="Pause on exceptions")
    stop_on_error: bool = Field(True, description="Pause on errors")

class AddBreakpointRequest(BaseModel):
    """Request model for adding a breakpoint"""
    workflow_id: str = Field(..., description="ID of the workflow")
    node_id: str = Field(..., description="ID of the node to break at")
    debug_session_id: Optional[str] = Field(None, description="Debug session ID")
    edge_id: Optional[str] = Field(None, description="ID of the edge (for edge breakpoints)")
    breakpoint_type: str = Field("node", description="Type of breakpoint")
    condition: Optional[str] = Field(None, description="Conditional expression")
    hit_limit: Optional[int] = Field(None, description="Stop after N hits")
    log_message: Optional[str] = Field(None, description="Log message instead of stopping")

class StepExecutionRequest(BaseModel):
    """Request model for step execution control"""
    session_id: str = Field(..., description="Debug session ID")
    action: str = Field(..., description="Action: step_over, step_into, step_out, continue, pause")

class CreateTraceRequest(BaseModel):
    """Request model for creating an execution trace"""
    workflow_id: str = Field(..., description="ID of the workflow")
    execution_id: str = Field(..., description="Execution ID")
    step_number: int = Field(..., description="Step number")
    node_id: str = Field(..., description="ID of the node")
    node_type: str = Field(..., description="Type of the node")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Input data for this step")
    variables_before: Optional[Dict[str, Any]] = Field(None, description="Variables before execution")
    debug_session_id: Optional[str] = Field(None, description="Debug session ID")

class CompleteTraceRequest(BaseModel):
    """Request model for completing a trace"""
    output_data: Optional[Dict[str, Any]] = Field(None, description="Output data from this step")
    variables_after: Optional[Dict[str, Any]] = Field(None, description="Variables after execution")
    error_message: Optional[str] = Field(None, description="Error message if failed")


# ==================== Debug Session Endpoints ====================

@router.post("/{workflow_id}/debug/sessions")
async def create_debug_session(
    workflow_id: str,
    request: CreateDebugSessionRequest,
    user_id: str = Query(..., description="User ID creating the session"),
    db: Session = Depends(get_db)
):
    """Create a new debug session for a workflow"""
    try:
        debugger = WorkflowDebugger(db)

        session = debugger.create_debug_session(
            workflow_id=workflow_id,
            user_id=user_id,
            execution_id=request.execution_id,
            session_name=request.session_name,
            stop_on_entry=request.stop_on_entry,
            stop_on_exceptions=request.stop_on_exceptions,
            stop_on_error=request.stop_on_error,
        )

        return {
            "session_id": session.id,
            "workflow_id": session.workflow_id,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error creating debug session: {e}")
        raise router.internal_error(
            message="Failed to create debug session",
            details={"error": str(e)}
        )


@router.get("/{workflow_id}/debug/sessions")
async def get_debug_sessions(
    workflow_id: str,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    db: Session = Depends(get_db)
):
    """Get all debug sessions for a workflow"""
    try:
        debugger = WorkflowDebugger(db)
        sessions = debugger.get_active_debug_sessions(workflow_id, user_id)

        return [
            {
                "session_id": s.id,
                "workflow_id": s.workflow_id,
                "execution_id": s.execution_id,
                "user_id": s.user_id,
                "session_name": s.session_name,
                "status": s.status,
                "current_step": s.current_step,
                "current_node_id": s.current_node_id,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]

    except Exception as e:
        logger.error(f"Error getting debug sessions: {e}")
        raise router.internal_error(
            message="Failed to retrieve debug sessions",
            details={"error": str(e)}
        )


@router.post("/debug/sessions/{session_id}/pause")
async def pause_debug_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Pause a debug session"""
    try:
        debugger = WorkflowDebugger(db)
        success = debugger.pause_debug_session(session_id)

        if not success:
            raise router.not_found_error("DebugSession", session_id)

        return {"message": "Debug session paused", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error pausing debug session: {e}")
        raise router.internal_error(
            message="Failed to pause debug session",
            details={"error": str(e)}
        )


@router.post("/debug/sessions/{session_id}/resume")
async def resume_debug_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Resume a paused debug session"""
    try:
        debugger = WorkflowDebugger(db)
        success = debugger.resume_debug_session(session_id)

        if not success:
            raise router.not_found_error("DebugSession", session_id)

        return {"message": "Debug session resumed", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error resuming debug session: {e}")
        raise router.internal_error(
            message="Failed to resume debug session",
            details={"error": str(e)}
        )


@router.post("/debug/sessions/{session_id}/complete")
async def complete_debug_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Complete a debug session"""
    try:
        debugger = WorkflowDebugger(db)
        success = debugger.complete_debug_session(session_id)

        if not success:
            raise router.not_found_error("DebugSession", session_id)

        return {"message": "Debug session completed", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error completing debug session: {e}")
        raise router.internal_error(
            message="Failed to complete debug session",
            details={"error": str(e)}
        )


# ==================== Breakpoint Endpoints ====================

@router.post("/{workflow_id}/debug/breakpoints")
async def add_breakpoint(
    workflow_id: str,
    request: AddBreakpointRequest,
    user_id: str = Query(..., description="User ID adding the breakpoint"),
    db: Session = Depends(get_db)
):
    """Add a breakpoint to a workflow"""
    try:
        debugger = WorkflowDebugger(db)

        breakpoint = debugger.add_breakpoint(
            workflow_id=workflow_id,
            node_id=request.node_id,
            user_id=user_id,
            debug_session_id=request.debug_session_id,
            edge_id=request.edge_id,
            breakpoint_type=request.breakpoint_type,
            condition=request.condition,
            hit_limit=request.hit_limit,
            log_message=request.log_message,
        )

        return {
            "breakpoint_id": breakpoint.id,
            "node_id": breakpoint.node_id,
            "edge_id": breakpoint.edge_id,
            "breakpoint_type": breakpoint.breakpoint_type,
            "is_active": breakpoint.is_active,
            "is_disabled": breakpoint.is_disabled,
            "condition": breakpoint.condition,
            "hit_limit": breakpoint.hit_limit,
            "hit_count": breakpoint.hit_count,
            "log_message": breakpoint.log_message,
            "created_at": breakpoint.created_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error adding breakpoint: {e}")
        raise router.internal_error(
            message="Failed to add breakpoint",
            details={"error": str(e)}
        )


@router.get("/{workflow_id}/debug/breakpoints")
async def get_breakpoints(
    workflow_id: str,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    active_only: bool = Query(True, description="Only return active breakpoints"),
    db: Session = Depends(get_db)
):
    """Get all breakpoints for a workflow"""
    try:
        debugger = WorkflowDebugger(db)
        breakpoints = debugger.get_breakpoints(workflow_id, user_id, active_only)

        return [
            {
                "breakpoint_id": bp.id,
                "workflow_id": bp.workflow_id,
                "debug_session_id": bp.debug_session_id,
                "node_id": bp.node_id,
                "edge_id": bp.edge_id,
                "breakpoint_type": bp.breakpoint_type,
                "condition": bp.condition,
                "hit_count": bp.hit_count,
                "hit_limit": bp.hit_limit,
                "is_active": bp.is_active,
                "is_disabled": bp.is_disabled,
                "log_message": bp.log_message,
                "created_at": bp.created_at.isoformat(),
                "created_by": bp.created_by,
            }
            for bp in breakpoints
        ]

    except Exception as e:
        logger.error(f"Error getting breakpoints: {e}")
        raise router.internal_error(
            message="Failed to retrieve breakpoints",
            details={"error": str(e)}
        )


@router.delete("/debug/breakpoints/{breakpoint_id}")
async def remove_breakpoint(
    breakpoint_id: str,
    user_id: str = Query(..., description="User ID removing the breakpoint"),
    db: Session = Depends(get_db)
):
    """Remove a breakpoint"""
    try:
        debugger = WorkflowDebugger(db)
        success = debugger.remove_breakpoint(breakpoint_id, user_id)

        if not success:
            raise router.not_found_error("Breakpoint", breakpoint_id)

        return {"message": "Breakpoint removed", "breakpoint_id": breakpoint_id}

    except Exception as e:
        logger.error(f"Error removing breakpoint: {e}")
        raise router.internal_error(
            message="Failed to remove breakpoint",
            details={"error": str(e)}
        )


@router.put("/debug/breakpoints/{breakpoint_id}/toggle")
async def toggle_breakpoint(
    breakpoint_id: str,
    user_id: str = Query(..., description="User ID toggling the breakpoint"),
    db: Session = Depends(get_db)
):
    """Toggle breakpoint enabled/disabled"""
    try:
        debugger = WorkflowDebugger(db)
        new_state = debugger.toggle_breakpoint(breakpoint_id, user_id)

        if new_state is None:
            raise router.not_found_error("Breakpoint", breakpoint_id)

        return {
            "message": "Breakpoint toggled",
            "breakpoint_id": breakpoint_id,
            "is_disabled": not new_state,
        }

    except Exception as e:
        logger.error(f"Error toggling breakpoint: {e}")
        raise router.internal_error(
            message="Failed to toggle breakpoint",
            details={"error": str(e)}
        )


# ==================== Step Execution Endpoints ====================

@router.post("/debug/step")
async def step_execution(
    request: StepExecutionRequest,
    db: Session = Depends(get_db)
):
    """Control step execution (step over, into, out, continue, pause)"""
    try:
        debugger = WorkflowDebugger(db)

        if request.action == "step_over":
            result = debugger.step_over(request.session_id)
        elif request.action == "step_into":
            result = debugger.step_into(request.session_id)
        elif request.action == "step_out":
            result = debugger.step_out(request.session_id)
        elif request.action == "continue":
            result = debugger.continue_execution(request.session_id)
        elif request.action == "pause":
            result = debugger.pause_execution(request.session_id)
        else:
            raise router.validation_error(
                field="action",
                message=f"Invalid action: {request.action}",
                details={"provided_action": request.action}
            )

        if not result:
            raise router.not_found_error("DebugSession", request.session_id)

        return result

    except Exception as e:
        logger.error(f"Error controlling step execution: {e}")
        raise router.internal_error(
            message="Failed to control step execution",
            details={"error": str(e)}
        )


# ==================== Execution Trace Endpoints ====================

@router.post("/debug/traces")
async def create_trace(
    request: CreateTraceRequest,
    db: Session = Depends(get_db)
):
    """Create a new execution trace entry"""
    try:
        debugger = WorkflowDebugger(db)

        trace = debugger.create_trace(
            workflow_id=request.workflow_id,
            execution_id=request.execution_id,
            step_number=request.step_number,
            node_id=request.node_id,
            node_type=request.node_type,
            input_data=request.input_data,
            variables_before=request.variables_before,
            debug_session_id=request.debug_session_id,
        )

        return {
            "trace_id": trace.id,
            "workflow_id": trace.workflow_id,
            "execution_id": trace.execution_id,
            "step_number": trace.step_number,
            "node_id": trace.node_id,
            "node_type": trace.node_type,
            "status": trace.status,
            "created_at": trace.started_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error creating trace: {e}")
        raise router.internal_error(
            message="Failed to create execution trace",
            details={"error": str(e)}
        )


@router.put("/debug/traces/{trace_id}/complete")
async def complete_trace(
    trace_id: str,
    request: CompleteTraceRequest,
    db: Session = Depends(get_db)
):
    """Mark an execution trace as completed"""
    try:
        debugger = WorkflowDebugger(db)
        success = debugger.complete_trace(
            trace_id=trace_id,
            output_data=request.output_data,
            variables_after=request.variables_after,
            error_message=request.error_message,
        )

        if not success:
            raise router.not_found_error("ExecutionTrace", trace_id)

        return {"message": "Trace completed", "trace_id": trace_id}

    except Exception as e:
        logger.error(f"Error completing trace: {e}")
        raise router.internal_error(
            message="Failed to complete execution trace",
            details={"error": str(e)}
        )


@router.get("/executions/{execution_id}/traces")
async def get_execution_traces(
    execution_id: str,
    debug_session_id: Optional[str] = Query(None, description="Filter by debug session"),
    limit: int = Query(100, ge=1, le=500, description="Maximum traces to return"),
    db: Session = Depends(get_db)
):
    """Get execution traces for an execution"""
    try:
        debugger = WorkflowDebugger(db)
        traces = debugger.get_execution_traces(execution_id, debug_session_id, limit)

        return [
            {
                "trace_id": t.id,
                "workflow_id": t.workflow_id,
                "execution_id": t.execution_id,
                "debug_session_id": t.debug_session_id,
                "step_number": t.step_number,
                "node_id": t.node_id,
                "node_type": t.node_type,
                "status": t.status,
                "input_data": t.input_data,
                "output_data": t.output_data,
                "error_message": t.error_message,
                "variable_changes": t.variable_changes,
                "started_at": t.started_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "duration_ms": t.duration_ms,
            }
            for t in traces
        ]

    except Exception as e:
        logger.error(f"Error getting execution traces: {e}")
        raise router.internal_error(
            message="Failed to retrieve execution traces",
            details={"error": str(e)}
        )


# ==================== Variable Inspection Endpoints ====================

@router.get("/debug/sessions/{session_id}/variables")
async def get_session_variables(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get all watch variables for a debug session"""
    try:
        debugger = WorkflowDebugger(db)
        variables = debugger.get_watch_variables(session_id)

        return [
            {
                "variable_id": v.id,
                "trace_id": v.trace_id,
                "variable_name": v.variable_name,
                "variable_path": v.variable_path,
                "variable_type": v.variable_type,
                "value": v.value,
                "value_preview": v.value_preview,
                "is_mutable": v.is_mutable,
                "scope": v.scope,
                "is_changed": v.is_changed,
                "previous_value": v.previous_value,
                "is_watch": v.is_watch,
                "watch_expression": v.watch_expression,
            }
            for v in variables
        ]

    except Exception as e:
        logger.error(f"Error getting session variables: {e}")
        raise router.internal_error(
            message="Failed to retrieve session variables",
            details={"error": str(e)}
        )


@router.get("/debug/traces/{trace_id}/variables")
async def get_trace_variables(
    trace_id: str,
    db: Session = Depends(get_db)
):
    """Get all variable snapshots for a trace"""
    try:
        debugger = WorkflowDebugger(db)
        variables = debugger.get_variables_for_trace(trace_id)

        return [
            {
                "variable_id": v.id,
                "variable_name": v.variable_name,
                "variable_path": v.variable_path,
                "variable_type": v.variable_type,
                "value": v.value,
                "value_preview": v.value_preview,
                "is_mutable": v.is_mutable,
                "scope": v.scope,
                "is_changed": v.is_changed,
                "previous_value": v.previous_value,
            }
            for v in variables
        ]

    except Exception as e:
        logger.error(f"Error getting trace variables: {e}")
        raise router.internal_error(
            message="Failed to retrieve trace variables",
            details={"error": str(e)}
        )


# Export router
__all__ = ["router"]
