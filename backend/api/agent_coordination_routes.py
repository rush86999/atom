"""
Agent coordination API routes for atom-upstream.

Provides endpoints for:
- Adding/removing agents from canvases
- Agent handoffs
- Multi-agent coordination
- Agent presence tracking
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query, HTTPException
from sqlalchemy.orm import Session

from core.auth_routes import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User, AgentRegistry, Canvas
from core.agent_coordination import AgentHandoffProtocol, MultiAgentCanvasService
from core.rbac_service import Permission
from core.security_dependencies import require_permission

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/agent-coordination", tags=["Agent Coordination"])


@router.post("/canvas/{canvas_id}/agents/{agent_id}/join")
async def add_agent_to_canvas(
    canvas_id: str,
    agent_id: str,
    role: str = Query("collaborator", description="Agent role on canvas"),
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """
    Add an agent to a canvas collaboration session.
    """
    # Verify agent exists
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id
    ).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Add agent to canvas
    service = MultiAgentCanvasService(db)
    result = await service.add_agent_to_canvas(
        agent_id=agent_id,
        canvas_id=canvas_id,
        tenant_id=user.tenant_id,
        role=role
    )

    return router.success_response(
        data=result,
        message=f"Agent {agent.name} added to canvas"
    )


@router.delete("/canvas/{canvas_id}/agents/{agent_id}")
async def remove_agent_from_canvas(
    canvas_id: str,
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """Remove an agent from a canvas collaboration session."""
    service = MultiAgentCanvasService(db)
    result = await service.remove_agent_from_canvas(
        agent_id=agent_id,
        canvas_id=canvas_id,
        tenant_id=user.tenant_id
    )

    return router.success_response(
        data=result,
        message="Agent removed from canvas"
    )


@router.get("/canvas/{canvas_id}/agents")
async def get_canvas_agents(
    canvas_id: str,
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    db: Session = Depends(get_db)
):
    """Get all agents currently active on a canvas."""
    service = MultiAgentCanvasService(db)
    # Note: get_canvas_agents might not be implemented in MultiAgentCanvasService yet, 
    # but we'll follow the SaaS pattern.
    # Looking at core/agent_coordination.py, it seems it's not there.
    # Let's check AgentCanvasPresence directly.
    from core.models import AgentCanvasPresence
    
    agents = db.query(AgentCanvasPresence).filter(
        AgentCanvasPresence.canvas_id == canvas_id,
        AgentCanvasPresence.tenant_id == user.tenant_id,
        AgentCanvasPresence.status == "active"
    ).all()

    agent_list = []
    for p in agents:
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == p.agent_id).first()
        if agent:
            agent_list.append({
                "agent_id": agent.id,
                "name": agent.name,
                "role": p.role,
                "joined_at": p.joined_at.isoformat() if p.joined_at else None
            })

    return router.success_list_response(
        items=agent_list,
        total=len(agent_list),
        message=f"Retrieved {len(agent_list)} agents on canvas"
    )


@router.post("/canvas/{canvas_id}/handoffs")
async def initiate_agent_handoff(
    canvas_id: str,
    from_agent_id: str,
    to_agent_id: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """
    Initiate a handoff from one agent to another on a canvas.
    """
    protocol = AgentHandoffProtocol(db)
    result = await protocol.initiate_handoff(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        canvas_id=canvas_id,
        tenant_id=user.tenant_id,
        context=context or {},
        reason=reason,
        initiated_by=user.id
    )

    return router.success_response(
        data=result,
        message="Agent handoff initiated"
    )


@router.post("/handoffs/{handoff_id}/accept")
async def accept_agent_handoff(
    handoff_id: str,
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """Accept an agent handoff request."""
    # In upstream, we might need to verify the agent belongs to the tenant.
    protocol = AgentHandoffProtocol(db)
    result = await protocol.accept_handoff(
        handoff_id=handoff_id,
        agent_id=agent_id,
        tenant_id=user.tenant_id
    )

    return router.success_response(
        data=result,
        message="Handoff accepted"
    )


@router.post("/handoffs/{handoff_id}/reject")
async def reject_agent_handoff(
    handoff_id: str,
    agent_id: str,
    reason: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """Reject an agent handoff request."""
    protocol = AgentHandoffProtocol(db)
    result = await protocol.reject_handoff(
        handoff_id=handoff_id,
        agent_id=agent_id,
        tenant_id=user.tenant_id,
        reason=reason
    )

    return router.success_response(
        data=result,
        message="Handoff rejected"
    )


@router.post("/handoffs/{handoff_id}/complete")
async def complete_agent_handoff(
    handoff_id: str,
    result_data: Dict[str, Any],
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """ Mark an agent handoff as completed with result. """
    protocol = AgentHandoffProtocol(db)
    result = await protocol.complete_handoff(
        handoff_id=handoff_id,
        result=result_data,
        tenant_id=user.tenant_id
    )

    return router.success_response(
        data=result,
        message="Handoff completed"
    )


@router.get("/canvas/{canvas_id}/handoffs")
async def get_canvas_handoffs(
    canvas_id: str,
    status: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    db: Session = Depends(get_db)
):
    """Get all handoffs for a canvas."""
    from core.models import AgentHandoff
    
    query = db.query(AgentHandoff).filter(
        AgentHandoff.canvas_id == canvas_id,
        AgentHandoff.tenant_id == user.tenant_id
    )
    
    if status:
        query = query.filter(AgentHandoff.status == status)
        
    handoffs = query.all()

    handoff_list = [
        {
            "handoff_id": str(h.id),
            "from_agent_id": h.from_agent_id,
            "to_agent_id": h.to_agent_id,
            "status": h.status,
            "reason": h.reason,
            "initiated_at": h.initiated_at.isoformat() if h.initiated_at else None
        }
        for h in handoffs
    ]

    return router.success_list_response(
        items=handoff_list,
        total=len(handoff_list),
        message=f"Retrieved {len(handoff_list)} handoffs"
    )


@router.post("/canvas/{canvas_id}/coordinate")
async def coordinate_agents(
    canvas_id: str,
    task: str,
    required_agents: List[str],
    coordination_strategy: str = Query("sequential", description="Strategy: sequential, coordinated_strategy"),
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db)
):
    """
    Coordinate multiple agents to complete a task together.
    """
    service = MultiAgentCanvasService(db)
    result = await service.coordinate_agents(
        canvas_id=canvas_id,
        tenant_id=user.tenant_id,
        task=task,
        required_agents=required_agents,
        coordination_strategy=coordination_strategy
    )

    return router.success_response(
        data=result,
        message="Coordination initiated"
    )
