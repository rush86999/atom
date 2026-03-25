"""
Agent coordination service for multi-agent canvas collaboration.

Provides:
- Agent handoff protocols
- Multi-agent coordination (sequential, parallel, consensus)
- Agent presence management on canvases
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
from core.models import AgentRegistry, Canvas, Tenant, User, AgentHandoff, AgentCanvasPresence
from core.coordinated_strategy_service import CoordinatedStrategyService

logger = logging.getLogger(__name__)


class AgentHandoffProtocol:
    """
    Protocol for coordinating handoffs between agents on a canvas.

    Enables agents to:
    - Initiate handoffs to other agents
    - Accept/reject handoffs
    - Pass context between agents
    - Track handoff completion
    - Validate I/O schemas
    """

    def __init__(self, db: Session):
        self.db = db

    def validate_handoff_payload(self, payload: Dict, schema: Dict) -> bool:
        """
        Validate a handoff payload against a provided JSON schema.
        Reduces 'Coordination Tax' by catching errors early.
        """
        if not schema:
            return True
            
        try:
            from jsonschema import validate
            validate(instance=payload, schema=schema)
            return True
        except ImportError:
            # Fallback if jsonschema not installed: check keys at top level
            for key in schema.get("required", []):
                if key not in payload:
                    logger.error(f"Schema validation failed: missing required key '{key}'")
                    return False
            return True
        except Exception as e:
            logger.error(f"Handoff schema validation error: {e}")
            return False


    async def initiate_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        canvas_id: str,
        tenant_id: str,
        context: Dict,
        reason: str,
        initiated_by: Optional[str] = None,
        input_schema: Optional[Dict] = None,
        output_schema: Optional[Dict] = None
    ) -> Dict:
        """
        Initiate handoff from one agent to another.
        """
        # Verify agents exist
        from_agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == from_agent_id
        ).first()

        to_agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == to_agent_id
        ).first()

        if not from_agent or not to_agent:
            raise ValueError("Invalid agent IDs")

        # Verify canvas exists
        canvas = self.db.query(Canvas).filter(
            Canvas.id == canvas_id,
            Canvas.tenant_id == tenant_id
        ).first()

        if not canvas:
            raise ValueError("Invalid canvas ID")

        # Validate context against input_schema if provided
        if input_schema and not self.validate_handoff_payload(context, input_schema):
            raise ValueError("Handoff context does not match required input schema")

        # Create handoff record
        handoff = AgentHandoff(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            canvas_id=canvas_id,
            tenant_id=tenant_id,
            context=context,
            input_schema=input_schema,
            output_schema=output_schema,
            reason=reason,
            status="pending",
            initiated_at=datetime.now(timezone.utc)
        )

        self.db.add(handoff)
        self.db.commit()
        self.db.refresh(handoff)

        # Broadcast handoff to canvas room
        from core.websockets import get_connection_manager
        manager = get_connection_manager()

        await manager.broadcast_event(
            f"tenant:{tenant_id}:canvas:{canvas_id}",
            manager.AGENT_HANDOFF,
            {
                "handoff_id": str(handoff.id),
                "from_agent": {
                    "id": str(from_agent.id),
                    "name": from_agent.name,
                    "role": from_agent.category
                },
                "to_agent": {
                    "id": str(to_agent.id),
                    "name": to_agent.name,
                    "role": to_agent.category
                },
                "canvas_id": canvas_id,
                "reason": reason,
                "context": context,
                "status": "pending",
                "initiated_by": initiated_by,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        logger.info(
            f"Agent handoff initiated: {from_agent.name} -> {to_agent.name}",
            extra={
                "from_agent_id": from_agent_id,
                "to_agent_id": to_agent_id,
                "canvas_id": canvas_id,
                "tenant_id": tenant_id
            }
        )

        return {
            "handoff_id": str(handoff.id),
            "status": "pending",
            "message": f"Handoff initiated from {from_agent.name} to {to_agent.name}"
        }

    async def accept_handoff(
        self,
        handoff_id: str,
        agent_id: str,
        tenant_id: str
    ) -> Dict:
        """Accept handoff request."""
        handoff = self.db.query(AgentHandoff).filter(
            AgentHandoff.id == handoff_id
        ).first()

        if not handoff:
            raise ValueError("Handoff not found")

        if handoff.to_agent_id != agent_id:
            raise ValueError("Agent not authorized for this handoff")

        handoff.status = "accepted"
        handoff.responded_at = datetime.now(timezone.utc)

        self.db.commit()

        # Broadcast acceptance
        from core.websockets import get_connection_manager
        manager = get_connection_manager()

        await manager.broadcast_event(
            f"tenant:{tenant_id}:canvas:{handoff.canvas_id}",
            manager.AGENT_COORDINATION_RESPONSE,
            {
                "handoff_id": handoff_id,
                "status": "accepted",
                "agent_id": agent_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        return {"status": "accepted", "message": "Handoff accepted"}

    async def reject_handoff(
        self,
        handoff_id: str,
        agent_id: str,
        tenant_id: str,
        reason: str = None
    ) -> Dict:
        """Reject handoff request."""
        handoff = self.db.query(AgentHandoff).filter(
            AgentHandoff.id == handoff_id
        ).first()

        if not handoff:
            raise ValueError("Handoff not found")

        if handoff.to_agent_id != agent_id:
            raise ValueError("Agent not authorized for this handoff")

        handoff.status = "rejected"
        handoff.responded_at = datetime.now(timezone.utc)
        handoff.rejection_reason = reason

        self.db.commit()

        # Broadcast rejection
        from core.websockets import get_connection_manager
        manager = get_connection_manager()

        await manager.broadcast_event(
            f"tenant:{tenant_id}:canvas:{handoff.canvas_id}",
            manager.AGENT_COORDINATION_RESPONSE,
            {
                "handoff_id": handoff_id,
                "status": "rejected",
                "agent_id": agent_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        return {"status": "rejected", "message": "Handoff rejected"}

    async def complete_handoff(
        self,
        handoff_id: str,
        result: Dict,
        tenant_id: str
    ) -> Dict:
        """Mark handoff as completed with result."""
        handoff = self.db.query(AgentHandoff).filter(
            AgentHandoff.id == handoff_id
        ).first()

        if not handoff:
            raise ValueError("Handoff not found")

        handoff.status = "completed"
        handoff.completed_at = datetime.now(timezone.utc)
        handoff.result = result

        self.db.commit()

        # Broadcast completion
        from core.websockets import get_connection_manager
        manager = get_connection_manager()

        await manager.broadcast_event(
            f"tenant:{tenant_id}:canvas:{handoff.canvas_id}",
            manager.AGENT_ACTION_COMPLETE,
            {
                "handoff_id": handoff_id,
                "status": "completed",
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        return {"status": "completed", "result": result}


class MultiAgentCanvasService:
    """
    Coordinate multiple agents working on the same canvas.
    """

    def __init__(self, db: Session):
        self.db = db
        self.handoff_protocol = AgentHandoffProtocol(db)

    async def add_agent_to_canvas(
        self,
        agent_id: str,
        canvas_id: str,
        tenant_id: str,
        role: str = "collaborator"
    ) -> Dict:
        """
        Add an agent to a canvas collaboration session.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        canvas = self.db.query(Canvas).filter(
            Canvas.id == canvas_id,
            Canvas.tenant_id == tenant_id
        ).first()

        if not agent or not canvas:
            raise ValueError("Invalid agent or canvas ID")

        # Check existing presence
        existing = self.db.query(AgentCanvasPresence).filter(
            AgentCanvasPresence.agent_id == agent_id,
            AgentCanvasPresence.canvas_id == canvas_id,
            AgentCanvasPresence.status == "active"
        ).first()

        if existing:
            return {"status": "already_present", "message": "Agent already on canvas"}

        # Add presence
        presence = AgentCanvasPresence(
            agent_id=agent_id,
            canvas_id=canvas_id,
            tenant_id=tenant_id,
            role=role,
            status="active",
            joined_at=datetime.now(timezone.utc)
        )

        self.db.add(presence)
        self.db.commit()

        # Broadcast join
        from core.websockets import get_connection_manager
        manager = get_connection_manager()

        await manager.broadcast_event(
            f"tenant:{tenant_id}:canvas:{canvas_id}",
            manager.AGENT_JOIN_CANVAS,
            {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "agent_role": agent.category,
                "canvas_role": role,
                "status": "active",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        return {
            "status": "joined",
            "agent_id": agent_id,
            "canvas_id": canvas_id,
            "role": role
        }

    async def remove_agent_from_canvas(
        self,
        agent_id: str,
        canvas_id: str,
        tenant_id: str
    ) -> Dict:
        """Remove an agent from a canvas collaboration session."""
        presence = self.db.query(AgentCanvasPresence).filter(
            AgentCanvasPresence.agent_id == agent_id,
            AgentCanvasPresence.canvas_id == canvas_id,
            AgentCanvasPresence.tenant_id == tenant_id,
            AgentCanvasPresence.status == "active"
        ).first()

        if not presence:
            return {"status": "not_present", "message": "Agent not on canvas"}

        presence.status = "left"
        presence.left_at = datetime.now(timezone.utc)

        self.db.commit()

        # Broadcast leave
        from core.websockets import get_connection_manager
        manager = get_connection_manager()

        await manager.broadcast_event(
            f"tenant:{tenant_id}:canvas:{canvas_id}",
            manager.AGENT_LEAVE_CANVAS,
            {
                "agent_id": agent_id,
                "canvas_id": canvas_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        return {"status": "removed", "agent_id": agent_id}

    async def coordinate_agents(
        self,
        canvas_id: str,
        tenant_id: str,
        task: str,
        required_agents: List[str],
        coordination_strategy: str = "sequential"
    ) -> Dict:
        """
        Coordinate multiple agents to complete a task together.
        """
        if coordination_strategy == "sequential":
            return await self._coordinate_sequential(canvas_id, tenant_id, task, required_agents)
        elif coordination_strategy == "coordinated_strategy":
            return await self._coordinate_diverse_strategy(canvas_id, tenant_id, task, required_agents)
        else:
            raise ValueError(f"Coordination strategy {coordination_strategy} not supported yet in upstream.")

    async def _coordinate_sequential(
        self,
        canvas_id: str,
        tenant_id: str,
        task: str,
        required_agents: List[str]
    ) -> Dict:
        """Sequential coordination: Agent 1 -> Agent 2 -> Agent 3."""
        # This is a simplified version for the first wave
        context = {"task": task}
        return {
            "coordination_type": "sequential",
            "task": task,
            "status": "initiated",
            "required_agents": required_agents
        }

    async def _coordinate_diverse_strategy(
        self,
        canvas_id: str,
        tenant_id: str,
        task: str,
        required_specialties: List[str]
    ) -> Dict:
        """
        Initiates a coordinated strategy and recruits diverse specialty partners.
        """
        strategy_service = CoordinatedStrategyService(self.db)
        
        # 1. Identify initiator (system or first active agent)
        initiator_id = "system" # Default
        
        # 2. Initiate strategy
        strategy = strategy_service.initiate_strategy(
            tenant_id=tenant_id,
            title=f"Strategic Plan: {task[:50]}...",
            objective=task,
            initiator_agent_id=initiator_id
        )
        
        # 3. Recruit partners
        recruited = []
        for specialty in required_specialties:
            partner = strategy_service.recruit_diverse_partner(
                strategy.id, specialty
            )
            if partner:
                await self.add_agent_to_canvas(str(partner.id), canvas_id, tenant_id, role="strategic_partner")
                recruited.append({"agent_id": str(partner.id), "specialty": specialty})
                
        return {
            "strategy_id": strategy.id,
            "status": "negotiation_active",
            "recruited_partners": recruited
        }


# WebSocket handler function for agent handoffs
async def handle_agent_handoff(
    room_id: str,
    data: Dict,
    user: User,
    tenant_id: str,
    db: Session
):
    """
    Handle agent handoff message from WebSocket.
    """
    from_agent = data.get("from_agent")
    to_agent = data.get("to_agent")
    canvas_id = data.get("canvas_id")
    context = data.get("context", {})
    reason = data.get("reason", "User initiated")

    if not all([from_agent, to_agent, canvas_id]):
        logger.error("Invalid agent_handoff message: missing required fields")
        return

    protocol = AgentHandoffProtocol(db)

    try:
        result = await protocol.initiate_handoff(
            from_agent_id=from_agent,
            to_agent_id=to_agent,
            canvas_id=canvas_id,
            tenant_id=tenant_id,
            context=context,
            reason=reason,
            initiated_by=user.id
        )

        logger.info(f"Agent handoff successful: {result}")

    except Exception as e:
        logger.error(f"Agent handoff failed: {e}", 
                     extra={
                         "room_id": room_id, 
                         "tenant_id": tenant_id,
                         "canvas_id": canvas_id,
                         "from_agent": from_agent,
                         "to_agent": to_agent
                     },
                     exc_info=True)
