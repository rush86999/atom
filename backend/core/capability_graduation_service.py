"""
Capability Graduation Service - Upstream Edition

Manages the maturity progression of agent capabilities through 
Student, Intern, Supervised, and Autonomous levels.
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models import AgentRegistry, HITLAction, HITLActionStatus

logger = logging.getLogger(__name__)

class CapabilityMaturityLevel:
    STUDENT = "student"
    INTERN = "intern"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"

    ORDER = [STUDENT, INTERN, SUPERVISED, AUTONOMOUS]

    @classmethod
    def is_at_least(cls, current: str, required: str) -> bool:
        if current not in cls.ORDER or required not in cls.ORDER:
            return False
        return cls.ORDER.index(current) >= cls.ORDER.index(required)

class CapabilityGraduationService:
    """Service to track and manage capability maturity for agents."""

    def __init__(self, db: Session):
        self.db = db

    def get_maturity(self, agent_id: str, capability_name: str) -> str:
        """Get current maturity level for a capability."""
        # In Upstream, we store this in agent properties for now
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return CapabilityMaturityLevel.STUDENT

        maturities = agent.properties.get("capability_maturities", {})
        return maturities.get(capability_name, CapabilityMaturityLevel.STUDENT)

    def record_usage(self, agent_id: str, capability_name: str, success: bool):
        """Record usage of a capability to progress maturity."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return

        if "capability_stats" not in agent.properties:
            agent.properties["capability_stats"] = {}

        stats = agent.properties["capability_stats"].get(capability_name, {"success": 0, "total": 0})
        stats["total"] += 1
        if success:
            stats["success"] += 1

        agent.properties["capability_stats"][capability_name] = stats

        # Simple progression logic for Upstream
        current = self.get_maturity(agent_id, capability_name)
        if success and stats["success"] >= 5 and current == CapabilityMaturityLevel.STUDENT:
            self._update_maturity(agent, capability_name, CapabilityMaturityLevel.INTERN)
        elif success and stats["success"] >= 20 and current == CapabilityMaturityLevel.INTERN:
            self._update_maturity(agent, capability_name, CapabilityMaturityLevel.SUPERVISED)
        elif success and stats["success"] >= 50 and current == CapabilityMaturityLevel.SUPERVISED:
            # Autonomous requires high confidence
            self._update_maturity(agent, capability_name, CapabilityMaturityLevel.AUTONOMOUS)

        self.db.commit()

    def reset_maturity(self, agent_id: str, capability_name: str, reason: str):
        """Reset capability maturity to STUDENT level."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if agent:
            self._update_maturity(agent, capability_name, CapabilityMaturityLevel.STUDENT)
            logger.info(f"Reset maturity for {agent_id}:{capability_name} to STUDENT. Reason: {reason}")
            self.db.commit()

    def _update_maturity(self, agent: AgentRegistry, capability_name: str, level: str):
        if "capability_maturities" not in agent.properties:
            agent.properties["capability_maturities"] = {}
        agent.properties["capability_maturities"][capability_name] = level
        logger.info(f"Capability '{capability_name}' for agent {agent.id} graduated to {level}")
