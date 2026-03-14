"""
Agent coordination service for multi-agent canvas collaboration.

Provides:
- Agent handoff protocols
- Multi-agent coordination (sequential, parallel, consensus)
- Agent presence management on canvases
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from core.models import AgentRegistry, Canvas, Tenant, User, AgentHandoff, AgentCanvasPresence, ExecutionStatus
from core.coordinated_strategy_service import CoordinatedStrategyService
import logging

logger = logging.getLogger(__name__)


class AgentHandoffProtocol:
    """
    Protocol for coordinating handoffs between agents on a canvas.

    Enables agents to:
    - Initiate handoffs to other agents
    - Accept/reject handoffs
    - Pass context between agents
    - Track handoff completion
    """

    def __init__(self, db: Session):
        self.db = db

    async def initiate_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        canvas_id: str,
        tenant_id: str,
        context: Dict,
        reason: str,
        initiated_by: Optional[str] = None
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

        # Create handoff record
        handoff = AgentHandoff(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            canvas_id=canvas_id,
            tenant_id=tenant_id,
            context=context,
            reason=reason,
            status=ExecutionStatus.PENDING.value,
            initiated_at=datetime.now(timezone.utc)
        )

        self.db.add(handoff)
        self.db.commit()
        self.db.refresh(handoff)

        # Broadcast handoff to canvas room
        try:
            from core.websockets import get_connection_manager
            manager = get_connection_manager()

            await manager.broadcast_event(
                f"tenant:{tenant_id}:canvas:{canvas_id}",
                "AGENT_HANDOFF",
                {
                    "handoff_id": str(handoff.id),
                    "from_agent": {
                        "id": str(from_agent.id),
                        "name": from_agent.name
                    },
                    "to_agent": {
                        "id": str(to_agent.id),
                        "name": to_agent.name
                    },
                    "canvas_id": canvas_id,
                    "reason": reason,
                    "context": context,
                    "status": "pending",
                    "initiated_by": initiated_by,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast handoff: {e}")

        logger.info(
            f"Agent handoff initiated: {from_agent.name} -> {to_agent.name} "
            f"on canvas {canvas_id} (reason: {reason})"
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
        try:
            from core.websockets import get_connection_manager
            manager = get_connection_manager()

            await manager.broadcast_event(
                f"tenant:{tenant_id}:canvas:{handoff.canvas_id}",
                "AGENT_COORDINATION_RESPONSE",
                {
                    "handoff_id": handoff_id,
                    "status": "accepted",
                    "agent_id": agent_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast acceptance: {e}")

        logger.info(f"Agent handoff {handoff_id} accepted by agent {agent_id}")

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
        try:
            from core.websockets import get_connection_manager
            manager = get_connection_manager()

            await manager.broadcast_event(
                f"tenant:{tenant_id}:canvas:{handoff.canvas_id}",
                "AGENT_COORDINATION_RESPONSE",
                {
                    "handoff_id": handoff_id,
                    "status": "rejected",
                    "agent_id": agent_id,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast rejection: {e}")

        logger.info(f"Agent handoff {handoff_id} rejected by agent {agent_id}: {reason}")

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
        try:
            from core.websockets import get_connection_manager
            manager = get_connection_manager()

            await manager.broadcast_event(
                f"tenant:{tenant_id}:canvas:{handoff.canvas_id}",
                "AGENT_ACTION_COMPLETE",
                {
                    "handoff_id": handoff_id,
                    "status": "completed",
                    "result": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast completion: {e}")

        logger.info(f"Agent handoff {handoff_id} completed")

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
        # Verify agent and canvas exist
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        canvas = self.db.query(Canvas).filter(
            Canvas.id == canvas_id,
            Canvas.tenant_id == tenant_id
        ).first()

        if not agent or not canvas:
            raise ValueError("Invalid agent or canvas ID")

        # Check if agent is already on canvas
        existing = self.db.query(AgentCanvasPresence).filter(
            AgentCanvasPresence.agent_id == agent_id,
            AgentCanvasPresence.canvas_id == canvas_id,
            AgentCanvasPresence.status == "active"
        ).first()

        if existing:
            return {"status": "already_present", "message": "Agent already on canvas"}

        # Add agent presence
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

        # Broadcast agent join
        try:
            from core.websockets import get_connection_manager
            manager = get_connection_manager()

            await manager.broadcast_event(
                f"tenant:{tenant_id}:canvas:{canvas_id}",
                "AGENT_JOIN_CANVAS",
                {
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "canvas_role": role,
                    "status": "active",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast agent join: {e}")

        logger.info(f"Agent {agent.name} joined canvas {canvas_id}")

        return {
            "status": "joined",
            "agent_id": agent_id,
            "canvas_id": canvas_id,
            "role": role
        }

    def get_canvas_agents(
        self,
        canvas_id: str,
        tenant_id: str
    ) -> List[Dict]:
        """Get all agents currently on a canvas."""
        presences = self.db.query(AgentCanvasPresence).filter(
            AgentCanvasPresence.canvas_id == canvas_id,
            AgentCanvasPresence.tenant_id == tenant_id,
            AgentCanvasPresence.status == "active"
        ).all()

        result = []
        for presence in presences:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == presence.agent_id
            ).first()

            if agent:
                result.append({
                    "agent_id": str(agent.id),
                    "agent_name": agent.name,
                    "canvas_role": presence.role,
                    "status": presence.status,
                    "joined_at": presence.joined_at.isoformat()
                })

        return result

    async def coordinate_agents(
        self,
        canvas_id: str,
        tenant_id: str,
        task: str,
        required_agents: List[str],
        coordination_strategy: str = "sequential"
    ) -> Dict:
        """
        Coordinate multiple agents.
        """
        if coordination_strategy == "coordinated_strategy":
            return await self._coordinate_diverse_strategy(
                canvas_id, tenant_id, task, required_agents
            )
        # Other strategies can be added here
        return {"error": f"Strategy {coordination_strategy} not supported in current port"}

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
        
        # Identify initiator
        agents = self.get_canvas_agents(canvas_id, tenant_id)
        if not agents:
            raise ValueError("No agents active on canvas to initiate strategy")
            
        initiator_id = agents[0]["agent_id"]
        
        # Initiate strategy
        strategy = strategy_service.initiate_strategy(
            tenant_id=tenant_id,
            title=f"Strategic Plan: {task[:50]}...",
            objective=task,
            initiator_agent_id=initiator_id
        )
        
        # Recruit partners
        recruited = []
        for specialty in required_specialties:
            partner = strategy_service.recruit_diverse_partner(
                strategy.id, specialty, complementary_trait="risk_profile"
            )
            if partner:
                await self.add_agent_to_canvas(str(partner.id), canvas_id, tenant_id, role="strategic_partner")
                strategy_service.add_contribution(
                    strategy.id, str(partner.id), {"action": "Recruited as diverse partner"}
                )
                recruited.append({"agent_id": str(partner.id), "specialty": specialty})
                
        return {
            "strategy_id": strategy.id,
            "status": "strategic_negotiation_active",
            "recruited_partners": recruited
        }
