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
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from core.websockets import manager as ws_manager
from core.models import AgentExecution, CanvasAudit
from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService

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
    component_type: str,
    component_name: Optional[str],
    action: str,
    governance_check_passed: Optional[bool],
    metadata: Dict[str, Any] = None
) -> Optional[CanvasAudit]:
    """
    Create a canvas audit entry for tracking.

    Helper function to log all canvas actions for governance and audit trail.
    """
    try:
        audit = CanvasAudit(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=agent_id,
            agent_execution_id=agent_execution_id,
            user_id=user_id,
            canvas_id=canvas_id,
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
        workspace_id: Workspace ID for governance context
        **kwargs: Additional chart options (color, etc.)
    """
    from core.database import SessionLocal

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with SessionLocal() as db:
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

        canvas_id = str(uuid.uuid4())
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": f"{chart_type}",
                    "canvas_id": canvas_id,
                    "data": {"data": data, "title": title, **kwargs}
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with SessionLocal() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    component_type="chart",
                    component_name=chart_type,
                    action="present",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={
                        "title": title,
                        "data_points": len(data),
                        "chart_type": chart_type
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
                with SessionLocal() as db:
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
    agent_id: Optional[str] = None
):
    """
    Send a status panel to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the panel to
        items: List of status items with 'label', 'value', and optional 'trend'
        title: Panel title
        agent_id: Agent ID presenting the panel (for governance)
        workspace_id: Workspace ID for governance context
    """
    from core.database import SessionLocal

    agent = None
    governance_check = None

    try:
        # Governance: Check agent permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with SessionLocal() as db:
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

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "status_panel",
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
    agent_id: Optional[str] = None
):
    """
    Send markdown content to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the content to
        content: Markdown formatted content
        title: Content title
        agent_id: Agent ID presenting the content (for governance)
        workspace_id: Workspace ID for governance context
    """
    from core.database import SessionLocal

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with SessionLocal() as db:
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

        canvas_id = str(uuid.uuid4())
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "markdown",
                    "canvas_id": canvas_id,
                    "data": {"content": content, "title": title}
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with SessionLocal() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    component_type="markdown",
                    component_name=None,
                    action="present",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={"title": title, "content_length": len(content)}
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
    agent_id: Optional[str] = None
):
    """
    Present a form to the user with governance integration.

    Args:
        user_id: User ID to present the form to
        form_schema: Form schema with fields, validation rules
        title: Form title
        agent_id: Agent ID presenting the form (for governance)
        workspace_id: Workspace ID for governance context

    Returns:
        Dict with success status and canvas_id for tracking submissions
    """
    from core.database import SessionLocal

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions (INTERN+ required)
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with SessionLocal() as db:
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

        canvas_id = str(uuid.uuid4())
        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "form",
                    "canvas_id": canvas_id,
                    "data": {"schema": form_schema, "title": title}
                }
            }
        )

        # Create audit entry
        if CANVAS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            with SessionLocal() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    component_type="form",
                    component_name=None,
                    action="present",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={"title": title, "field_count": len(form_schema.get("fields", []))}
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


async def close_canvas(user_id: str):
    """
    Close the canvas for a user.

    Args:
        user_id: User ID to close the canvas for
    """
    try:
        user_channel = f"user:{user_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "close"
                }
            }
        )

        logger.info(f"Closed canvas for user {user_id}")
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to close canvas: {e}")
        return {"success": False, "error": str(e)}
