"""
Canvas Tool Backend Helper

Provides helper functions for agents to present charts and visualizations
to users via the Canvas system.

Now includes governance integration with:
- Agent execution tracking for all presentations
- Governance checks before presenting
- Complete audit trail via canvas_audit table
- Performance-optimized caching
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.canvas_type_registry import CanvasType, canvas_type_registry
from core.models import AgentExecution, CanvasAudit
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


# Feature flags
import os

CANVAS_GOVERNANCE_ENABLED = os.getenv("CANVAS_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


async def _create_canvas_audit(
    db: Session,
    agent_id: Optional[str],
    agent_execution_id: Optional[str],
    user_id: str,
    canvas_id: Optional[str],
    session_id: Optional[str],  # Session isolation
    canvas_type: str = "generic",  # NEW: Canvas type (generic, docs, email, sheets, orchestration, terminal, coding)
    component_type: str = "component",  # NEW: Default component type
    component_name: Optional[str] = None,
    action: str = "present",
    governance_check_passed: Optional[bool] = None,
    metadata: Dict[str, Any] = None
) -> Optional[CanvasAudit]:
    """
    Create a canvas audit entry for tracking.

    Helper function to log all canvas actions for governance and audit trail.

    Args:
        db: Database session
        agent_id: Optional agent ID
        agent_execution_id: Optional agent execution ID
        user_id: User ID
        canvas_id: Canvas ID
        session_id: Optional session ID for isolation
        canvas_type: Canvas type (generic, docs, email, sheets, orchestration, terminal, coding)
        component_type: Component type (chart, markdown, form, rich_editor, thread_view, etc.)
        component_name: Optional component name
        action: Action (present, close, submit, update)
        governance_check_passed: Whether governance check passed
        metadata: Optional metadata dictionary

    Returns:
        CanvasAudit object or None on failure
    """
    try:
        audit = CanvasAudit(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=agent_id,
            agent_execution_id=agent_execution_id,
            user_id=user_id,
            canvas_id=canvas_id,
            session_id=session_id,
            canvas_type=canvas_type,  # NEW: Canvas type
            component_type=component_type,
            component_name=component_name,
            action=action,
            audit_metadata=metadata or {},
            governance_check_passed=governance_check_passed
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    except Exception as e:
        logger.error(f"Failed to create canvas audit: {e}")
        return None


async def present_chart(
    user_id: str,
    chart_type: str,
    data: List[Dict[str, Any]],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs
):
    """
    Send a chart to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the chart to
        chart_type: 'line_chart', 'bar_chart', or 'pie_chart'
        data: List of dicts with chart data
        title: Chart title
        agent_id: Agent ID presenting the chart (for governance)
        session_id: Optional session ID for session isolation
        **kwargs: Additional chart options (color, etc.)
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="present_chart"
                )

                # Check governance
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_chart"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked chart presentation: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to present chart: {governance_check['reason']}"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Present {chart_type}: {title or 'Untitled'}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for chart presentation")

        # Present the chart via WebSocket
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        canvas_id = str(uuid.uuid4())
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": f"{chart_type}",
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "data": {"data": data, "title": title, **kwargs}
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,
                    canvas_type="generic",  # Generic canvas for charts
                    component_type="chart",
                    component_name=chart_type,
                    action="present",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={
                        "title": title,
                        "data_points": len(data),
                        "chart_type": chart_type,
                        "session_id": session_id
                    }
                )

                # Mark execution as completed
                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Presented {chart_type} with {len(data)} data points"
                        execution.completed_at = datetime.now()
                        db.commit()

                        # Record outcome for confidence
                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(f"Presented {chart_type} to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "chart_type": chart_type,
            "canvas_id": canvas_id,
            "agent_id": agent.id if agent else None
        }

    except Exception as e:
        logger.error(f"Failed to present chart: {e}")

        # Mark execution as failed
        if agent_execution and CANVAS_GOVERNANCE_ENABLED:
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            governance_service = AgentGovernanceService(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}


async def present_status_panel(
    user_id: str,
    items: List[Dict[str, Any]],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Send a status panel to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the panel to
        items: List of status items with 'label', 'value', and optional 'trend'
        title: Panel title
        agent_id: Agent ID presenting the panel (for governance)
        session_id: Optional session ID for session isolation
    """
    from core.database import get_db_session

    agent = None
    governance_check = None

    try:
        # Governance: Check agent permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                agent, _ = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="present_chart"
                )

                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_chart"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked status panel: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted: {governance_check['reason']}"
                        }

        # Present the panel
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "status_panel",
                    "session_id": session_id,
                    "data": {"items": items, "title": title}
                }
            }
        )

        logger.info(f"Presented status panel to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to present status panel: {e}")
        return {"success": False, "error": str(e)}


async def present_markdown(
    user_id: str,
    content: str,
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Send markdown content to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the content to
        content: Markdown formatted content
        title: Content title
        agent_id: Agent ID presenting the content (for governance)
        session_id: Optional session ID for session isolation
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                agent, _ = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="present_markdown"
                )

                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_markdown"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked markdown: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted: {governance_check['reason']}"
                        }

                    # Create execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Present markdown: {title or 'Untitled'}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

        # Present the markdown
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        canvas_id = str(uuid.uuid4())
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "markdown",
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "data": {"content": content, "title": title}
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,  # NEW: Session isolation
                    component_type="markdown",
                    component_name=None,
                    action="present",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={"title": title, "content_length": len(content), "session_id": session_id}
                )

                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Presented markdown ({len(content)} chars)"
                        execution.completed_at = datetime.now()
                        db.commit()

                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(f"Presented markdown content to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "canvas_id": canvas_id,
            "agent_id": agent.id if agent else None
        }

    except Exception as e:
        logger.error(f"Failed to present markdown: {e}")
        return {"success": False, "error": str(e)}


async def present_form(
    user_id: str,
    form_schema: Dict[str, Any],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Present a form to the user with governance integration.

    Args:
        user_id: User ID to present the form to
        form_schema: Form schema with fields, validation rules
        title: Form title
        agent_id: Agent ID presenting the form (for governance)
        session_id: Optional session ID for session isolation

    Returns:
        Dict with success status and canvas_id for tracking submissions
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions (INTERN+ required)
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                agent, _ = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="present_form"
                )

                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_form"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked form presentation: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to present form: {governance_check['reason']}"
                        }

                    # Create execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Present form: {title or 'Untitled'}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

        # Present the form
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        canvas_id = str(uuid.uuid4())
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "form",
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "data": {"schema": form_schema, "title": title}
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,  # NEW: Session isolation
                    component_type="form",
                    component_name=None,
                    action="present",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={"title": title, "field_count": len(form_schema.get("fields", [])), "session_id": session_id}
                )

                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Presented form with {len(form_schema.get('fields', []))} fields"
                        execution.completed_at = datetime.now()
                        db.commit()

                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(f"Presented form to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "canvas_id": canvas_id,
            "agent_execution_id": agent_execution.id if agent_execution else None,
            "agent_id": agent.id if agent else None
        }

    except Exception as e:
        logger.error(f"Failed to present form: {e}")
        return {"success": False, "error": str(e)}


async def update_canvas(
    user_id: str,
    canvas_id: str,
    updates: Dict[str, Any],
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Update existing canvas with new data without re-presenting entire component.

    Enables bidirectional canvas updates for dynamic dashboards and real-time data updates.
    Similar to OpenClaw's surfaceUpdate and dataModelUpdate commands.

    Args:
        user_id: User ID to send the update to
        canvas_id: Canvas ID to update (must exist from prior present_chart/form/markdown call)
        updates: Dictionary containing update data (e.g., {"data": [...], "title": "Updated"})
        agent_id: Agent ID performing the update (for governance)
        session_id: Optional session ID for session isolation

    Returns:
        Dict with success status and update details

    Example:
        # Update chart data
        await update_canvas(
            user_id="user-1",
            canvas_id="canvas-123",
            updates={"data": [{"x": 1, "y": 5}, {"x": 2, "y": 10}]},
            agent_id="agent-1"
        )

        # Update title
        await update_canvas(
            user_id="user-1",
            canvas_id="canvas-123",
            updates={"title": "Updated Sales Data"}
        )
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="update_canvas"
                )

                # Check governance (INTERN+ required for updates)
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="update_canvas"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked canvas update: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to update canvas: {governance_check['reason']}"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Update canvas {canvas_id}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for canvas update")

        # Send update via WebSocket
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "update",
                    "canvas_id": canvas_id,
                    "updates": updates
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,  # NEW: Session isolation
                    component_type="canvas_update",
                    component_name=None,
                    action="update",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={
                        "update_keys": list(updates.keys()),
                        "session_id": session_id
                    }
                )

                # Mark execution as completed
                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Updated canvas {canvas_id} with {len(updates)} fields"
                        execution.completed_at = datetime.now()
                        db.commit()

                        # Record outcome for confidence
                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(f"Updated canvas {canvas_id} for user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "canvas_id": canvas_id,
            "updated_fields": list(updates.keys()),
            "agent_id": agent.id if agent else None,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Failed to update canvas: {e}")

        # Mark execution as failed
        if agent_execution and CANVAS_GOVERNANCE_ENABLED:
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            governance_service = AgentGovernanceService(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}


async def close_canvas(user_id: str, session_id: Optional[str] = None):
    """
    Close the canvas for a user.

    Args:
        user_id: User ID to close the canvas for
        session_id: Optional session ID for session isolation
    """
    try:
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "close"
                }
            }
        )

        logger.info(f"Closed canvas for user {user_id}" + (f" (session: {session_id})" if session_id else ""))
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to close canvas: {e}")
        return {"success": False, "error": str(e)}


async def canvas_execute_javascript(
    user_id: str,
    canvas_id: str,
    javascript: str,
    agent_id: str,  # Required - must be AUTONOMOUS
    session_id: Optional[str] = None,
    timeout_ms: int = 5000
):
    """
    Execute JavaScript in a canvas context (AUTONOMOUS agents only).

    WARNING: This function requires AUTONOMOUS maturity level due to security risks.
    JavaScript execution can manipulate the DOM, access browser APIs, and perform
    arbitrary client-side actions.

    Args:
        user_id: User ID to execute JavaScript for
        canvas_id: Canvas ID to execute JavaScript in
        javascript: JavaScript code to execute
        agent_id: Agent ID performing the execution (must be AUTONOMOUS)
        session_id: Optional session ID for session isolation
        timeout_ms: Execution timeout in milliseconds (default: 5000)

    Returns:
        Dict with success status and execution details

    Example:
        # Update document title
        await canvas_execute_javascript(
            user_id="user-1",
            canvas_id="canvas-123",
            javascript="document.title = 'Updated Title';",
            agent_id="agent-autonomous-1"
        )

        # Manipulate DOM
        await canvas_execute_javascript(
            user_id="user-1",
            canvas_id="canvas-123",
            javascript="document.getElementById('chart').style.height = '500px';",
            agent_id="agent-autonomous-1"
        )
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Security: Require agent_id (no anonymous execution)
        if not agent_id:
            logger.warning("JavaScript execution blocked: No agent_id provided")
            return {
                "success": False,
                "error": "JavaScript execution requires an explicit agent_id (AUTONOMOUS only)"
            }

        # Governance: Resolve agent and check permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="canvas_execute_javascript"
                )

                # Check governance (AUTONOMOUS required)
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="canvas_execute_javascript"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked JavaScript execution: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to execute JavaScript: {governance_check['reason']}"
                        }

                    # Verify agent is AUTONOMOUS (double-check for security)
                    if agent.status != "AUTONOMOUS":
                        logger.warning(f"JavaScript execution blocked: Agent {agent.name} is {agent.status}, not AUTONOMOUS")
                        return {
                            "success": False,
                            "error": f"JavaScript execution requires AUTONOMOUS maturity level. Agent {agent.name} is {agent.status}"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Execute JavaScript in canvas {canvas_id}: {javascript[:100]}...",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for canvas JavaScript execution")

        # Basic JavaScript validation (security)
        if not javascript or not javascript.strip():
            return {
                "success": False,
                "error": "JavaScript code cannot be empty"
            }

        # Check for obviously dangerous patterns (basic security)
        dangerous_patterns = [
            "eval(", "Function(", "setTimeout(", "setInterval(",
            "document.cookie", "localStorage.", "sessionStorage.",
            "window.location", "window.top", "window.parent"
        ]

        javascript_lower = javascript.lower()
        for pattern in dangerous_patterns:
            if pattern in javascript:
                logger.warning(f"JavaScript execution blocked: Dangerous pattern '{pattern}' detected")
                return {
                    "success": False,
                    "error": f"JavaScript contains potentially dangerous pattern: {pattern}. Use of {pattern} is not allowed."
                }

        # Send JavaScript execution request via WebSocket
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:execute",
                "data": {
                    "action": "execute_javascript",
                    "canvas_id": canvas_id,
                    "javascript": javascript,
                    "timeout_ms": timeout_ms
                }
            }
        )

        # Create audit entry with JavaScript content
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,
                    component_type="javascript_execution",
                    component_name=None,
                    action="execute",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={
                        "javascript": javascript,
                        "javascript_length": len(javascript),
                        "timeout_ms": timeout_ms,
                        "session_id": session_id
                    }
                )

                # Mark execution as completed
                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Executed JavaScript in canvas {canvas_id} ({len(javascript)} chars)"
                        execution.completed_at = datetime.now()
                        db.commit()

                        # Record outcome for confidence
                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(
            f"Executed JavaScript in canvas {canvas_id} for user {user_id} "
            f"({len(javascript)} chars)" + (f" (agent: {agent.name})" if agent else "")
        )
        return {
            "success": True,
            "canvas_id": canvas_id,
            "javascript_length": len(javascript),
            "agent_id": agent.id if agent else None,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Failed to execute JavaScript: {e}")

        # Mark execution as failed
        if agent_execution and CANVAS_GOVERNANCE_ENABLED:
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            governance_service = AgentGovernanceService(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}


async def present_specialized_canvas(
    user_id: str,
    canvas_type: str,
    component_type: str,
    data: Dict[str, Any],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    layout: str = None
):
    """
    Present a specialized canvas with type-specific components.

    Generic function for presenting specialized canvas types:
    - docs: Documentation with rich editor, version history, comments
    - email: Email with threads, compose, attachments
    - sheets: Spreadsheet with grid, formulas, charts
    - orchestration: Multi-app workflows with kanban, gantt, diagrams
    - terminal: Command output, file trees, process monitoring
    - coding: Code editor, diff views, PR reviews

    Args:
        user_id: User ID to present canvas to
        canvas_type: Type of canvas (docs, email, sheets, orchestration, terminal, coding)
        component_type: Component type (rich_editor, thread_view, data_grid, etc.)
        data: Component-specific data
        title: Canvas title
        agent_id: Optional agent ID for governance
        session_id: Optional session ID for isolation
        layout: Optional layout (document, inbox, sheet, board, etc.)

    Returns:
        Dict with success status, canvas_id, and details

    Example:
        # Present documentation canvas
        await present_specialized_canvas(
            user_id="user-1",
            canvas_type="docs",
            component_type="rich_editor",
            data={"content": "# API Reference\\n\\nEndpoints..."},
            title="API Documentation",
            agent_id="agent-1"
        )

        # Present spreadsheet canvas
        await present_specialized_canvas(
            user_id="user-1",
            canvas_type="sheets",
            component_type="data_grid",
            data={"cells": {"A1": "Revenue", "B1": 100000}},
            title="Financial Model",
            layout="sheet"
        )
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Validate canvas type
        if not canvas_type_registry.validate_canvas_type(canvas_type):
            logger.warning(f"Invalid canvas type: {canvas_type}")
            return {
                "success": False,
                "error": f"Invalid canvas type: {canvas_type}. Must be one of: {list(canvas_type_registry.get_all_types().keys())}"
            }

        # Validate component for canvas type
        if not canvas_type_registry.validate_component(canvas_type, component_type):
            logger.warning(f"Component {component_type} not supported for canvas type {canvas_type}")
            return {
                "success": False,
                "error": f"Component {component_type} not supported for {canvas_type} canvas"
            }

        # Validate layout if provided
        if layout and not canvas_type_registry.validate_layout(canvas_type, layout):
            logger.warning(f"Layout {layout} not supported for canvas type {canvas_type}")
            return {
                "success": False,
                "error": f"Layout {layout} not supported for {canvas_type} canvas"
            }

        # Governance: Resolve agent and check permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type=f"present_{canvas_type}"
                )

                # Check governance for this canvas type
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type=f"present_{canvas_type}"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked {canvas_type} canvas: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to present {canvas_type} canvas: {governance_check['reason']}"
                        }

                    # Check maturity requirements
                    min_maturity = canvas_type_registry.get_min_maturity(canvas_type)
                    if agent.maturity_level < min_maturity.value:
                        logger.warning(
                            f"Agent maturity {agent.maturity_level} below required {min_maturity.value} for {canvas_type}"
                        )
                        return {
                            "success": False,
                            "error": f"Agent maturity {agent.maturity_level} insufficient for {canvas_type} canvas (requires {min_maturity.value})"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Present {canvas_type} canvas: {title or component_type}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for {canvas_type} canvas")

        # Present the specialized canvas via WebSocket
        user_channel = f"user:{user_id}"
        if session_id:
            user_channel = f"user:{user_id}:session:{session_id}"

        canvas_id = str(uuid.uuid4())
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "canvas_type": canvas_type,
                    "component": component_type,
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "title": title,
                    "layout": layout,
                    "data": data
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,
                    canvas_type=canvas_type,
                    component_type=component_type,
                    component_name=None,
                    action="present",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={
                        "title": title,
                        "layout": layout,
                        **data
                    }
                )

                # Mark execution as completed
                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Presented {canvas_type} canvas: {title or component_type}"
                        execution.completed_at = datetime.now()
                        db.commit()

                        # Record outcome for confidence
                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(
            f"Presented {canvas_type} canvas ({component_type}) to user {user_id}"
            + (f" (agent: {agent.name})" if agent else "")
        )
        return {
            "success": True,
            "canvas_type": canvas_type,
            "component_type": component_type,
            "canvas_id": canvas_id,
            "agent_id": agent.id if agent else None,
            "title": title,
            "layout": layout
        }

    except Exception as e:
        logger.error(f"Failed to present specialized canvas: {e}")

        # Mark execution as failed
        if agent_execution and CANVAS_GOVERNANCE_ENABLED:
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            governance_service = AgentGovernanceService(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}
