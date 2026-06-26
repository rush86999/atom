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
        # Stored under the agent's `configuration` JSON column (the model has
        # no `properties` field; earlier code referenced a nonexistent attr).
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return CapabilityMaturityLevel.STUDENT

        config = self._config(agent)
        maturities = config.get("capability_maturities", {})
        return maturities.get(capability_name, CapabilityMaturityLevel.STUDENT)

    def record_usage(
        self,
        agent_id: str,
        capability_name: str,
        success: bool,
        verified: str = "unverified",
    ):
        """
        Record usage of a capability to progress maturity.

        Args:
            success: Tool's self-reported success (kept for audit, NOT trusted
                for graduation alone).
            verified: Tri-state from tool_outcome_verifier —
                'verified' | 'unverified' | 'failed_verification'.
                Only 'verified' successes increment the graduation counter.
                Unverified successes still count in the denominator (they
                *lower* the success ratio), so silent no-ops cannot inflate
                capability stats (general critique, fixed).
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return

        config = self._config(agent)
        if "capability_stats" not in config:
            config["capability_stats"] = {}

        stats = config["capability_stats"].get(
            capability_name,
            {"success": 0, "total": 0, "verified_success": 0},
        )
        stats["total"] += 1
        # Self-reported success — tracked but not sufficient for graduation.
        if success:
            stats["success"] += 1
        # Graduation-gating signal: only verified successes count.
        if success and verified == "verified":
            stats["verified_success"] = stats.get("verified_success", 0) + 1

        config["capability_stats"][capability_name] = stats
        # Persist back through the model's JSON column (mutation isn't auto-detected).
        agent.configuration = dict(config)
        self.flag_modified(agent, "configuration")

        # Graduation now gates on verified_success — a silent no-op returning
        # {success: true} without evidence lands as unverified and cannot
        # promote the capability.
        verified_successes = stats.get("verified_success", 0)
        current = self.get_maturity(agent_id, capability_name)
        if verified_successes >= 5 and current == CapabilityMaturityLevel.STUDENT:
            self._update_maturity(agent, capability_name, CapabilityMaturityLevel.INTERN)
        elif verified_successes >= 20 and current == CapabilityMaturityLevel.INTERN:
            self._update_maturity(agent, capability_name, CapabilityMaturityLevel.SUPERVISED)
        elif verified_successes >= 50 and current == CapabilityMaturityLevel.SUPERVISED:
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
        config = self._config(agent)
        if "capability_maturities" not in config:
            config["capability_maturities"] = {}
        config["capability_maturities"][capability_name] = level
        agent.configuration = dict(config)
        self.flag_modified(agent, "configuration")
        logger.info(f"Capability '{capability_name}' for agent {agent.id} graduated to {level}")

    def _config(self, agent: AgentRegistry) -> dict:
        """Read the agent's configuration JSON column as a plain dict.

        Earlier code referenced a nonexistent ``agent.properties`` attribute;
        the model stores flexible metadata under ``configuration``. Returns a
        mutable copy so callers can edit and reassign.
        """
        cfg = getattr(agent, "configuration", None) or {}
        if not isinstance(cfg, dict):
            # JSON columns may return other shapes; coerce defensively.
            try:
                cfg = dict(cfg)
            except Exception:
                cfg = {}
        return dict(cfg)

    @staticmethod
    def flag_modified(agent: AgentRegistry, column: str) -> None:
        """Mark a JSON column as mutated so SQLAlchemy flushes the change."""
        try:
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(agent, column)
        except Exception:
            pass
