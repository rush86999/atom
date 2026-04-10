"""
Auto-Dev Capability Gate

Gates Auto-Dev features based on agent maturity level (graduation framework)
and workspace settings. This ensures:

1. Only agents that have proven competence can use self-evolution features
2. Users must explicitly enable Auto-Dev in workspace settings
3. Users are notified when agents graduate into new capabilities

Maturity requirements:
    - auto_dev.memento_skills    → INTERN    (skill suggestions, user approval required)
    - auto_dev.alpha_evolver     → SUPERVISED (mutation loops, results queued for review)
    - auto_dev.background_evolution → AUTONOMOUS (background loops, sandbox-gated)
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Maturity level constants (mirrors CapabilityMaturityLevel from graduation service)
STUDENT = "student"
INTERN = "intern"
SUPERVISED = "supervised"
AUTONOMOUS = "autonomous"

MATURITY_ORDER = [STUDENT, INTERN, SUPERVISED, AUTONOMOUS]


def is_at_least(current: str, required: str) -> bool:
    """Check if current maturity level meets or exceeds the required level."""
    if current not in MATURITY_ORDER or required not in MATURITY_ORDER:
        return False
    return MATURITY_ORDER.index(current) >= MATURITY_ORDER.index(required)


class AutoDevCapabilityService:
    """Gates Auto-Dev features based on agent maturity and workspace settings."""

    # Maturity requirements for each Auto-Dev capability
    CAPABILITY_GATES: dict[str, str] = {
        "auto_dev.memento_skills": INTERN,
        "auto_dev.alpha_evolver": SUPERVISED,
        "auto_dev.background_evolution": AUTONOMOUS,
    }

    def __init__(self, db: Session):
        self.db = db
        self._graduation_service = None

    @property
    def graduation(self):
        """Lazy-load graduation service to avoid circular imports."""
        if self._graduation_service is None:
            try:
                from core.capability_graduation_service import (
                    CapabilityGraduationService,
                )

                self._graduation_service = CapabilityGraduationService(self.db)
            except ImportError:
                logger.warning(
                    "CapabilityGraduationService not available — "
                    "Auto-Dev capabilities will default to STUDENT (disabled)"
                )
        return self._graduation_service

    def can_use(
        self,
        agent_id: str,
        capability: str,
        workspace_settings: dict[str, Any] | None = None,
    ) -> bool:
        """
        Check if an agent can use a specific Auto-Dev capability.

        Requires BOTH:
        1. Workspace settings allow it (auto_dev.enabled + per-capability toggle)
        2. Agent has graduated to the required maturity level

        Args:
            agent_id: The agent to check
            capability: e.g., "auto_dev.memento_skills"
            workspace_settings: Workspace.configuration dict (or Tenant.configuration)

        Returns:
            True if the agent is allowed to use this capability
        """
        settings = workspace_settings or {}

        # 1. Check workspace-level toggle
        auto_dev_settings = settings.get("auto_dev", {})
        if not auto_dev_settings.get("enabled", False):
            return False

        # 2. Check capability-specific toggle
        cap_key = capability.split(".")[-1]  # e.g., "memento_skills"
        if not auto_dev_settings.get(cap_key, True):
            return False

        # 3. Check graduation maturity gate
        required = self.CAPABILITY_GATES.get(capability)
        if not required:
            logger.warning(f"Unknown Auto-Dev capability: {capability}")
            return False

        current = self._get_agent_maturity(agent_id, capability)
        return is_at_least(current, required)

    def record_usage(self, agent_id: str, capability: str, success: bool) -> None:
        """
        Record Auto-Dev usage to progress agent maturity via graduation framework.

        Each successful use contributes to the agent's graduation score for
        this capability, eventually unlocking higher tiers.
        """
        if self.graduation:
            try:
                self.graduation.record_usage(agent_id, capability, success)
            except Exception as e:
                logger.error(f"Failed to record Auto-Dev usage: {e}")

    def check_daily_limits(
        self,
        agent_id: str,
        capability: str,
        workspace_settings: dict[str, Any] | None = None,
    ) -> bool:
        """
        Check if the agent has exceeded daily Auto-Dev limits.

        Limits are defined in workspace settings:
        - max_mutations_per_day (default: 10)
        - max_skill_candidates_per_day (default: 5)
        """
        settings = (workspace_settings or {}).get("auto_dev", {})

        if capability == "auto_dev.alpha_evolver":
            max_daily = settings.get("max_mutations_per_day", 10)
        elif capability == "auto_dev.memento_skills":
            max_daily = settings.get("max_skill_candidates_per_day", 5)
        else:
            return True

        # Count today's usage from models
        from datetime import datetime, timezone

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        try:
            if capability == "auto_dev.alpha_evolver":
                from core.auto_dev.models import ToolMutation

                count = (
                    self.db.query(ToolMutation)
                    .filter(
                        ToolMutation.tenant_id == self._get_agent_tenant(agent_id),
                        ToolMutation.created_at >= today_start,
                    )
                    .count()
                )
            elif capability == "auto_dev.memento_skills":
                from core.auto_dev.models import SkillCandidate

                count = (
                    self.db.query(SkillCandidate)
                    .filter(
                        SkillCandidate.agent_id == agent_id,
                        SkillCandidate.created_at >= today_start,
                    )
                    .count()
                )
            else:
                return True

            return count < max_daily
        except Exception as e:
            logger.error(f"Failed to check daily limits: {e}")
            return True  # Fail open to avoid blocking the system

    def notify_capability_unlocked(
        self, agent_id: str, capability: str
    ) -> dict[str, Any]:
        """
        Generate notification payload when an agent graduates into a new capability.

        The caller (e.g., GraduationService) should deliver this notification
        to the user via the appropriate channel.
        """
        cap_display = capability.replace("auto_dev.", "").replace("_", " ").title()
        return {
            "type": "auto_dev_capability_unlocked",
            "agent_id": agent_id,
            "capability": capability,
            "message": (
                f"Agent has graduated to use {cap_display}. "
                f"Enable it in Settings > Auto-Dev to activate."
            ),
            "action_required": True,
        }

    def _get_agent_maturity(self, agent_id: str, capability: str) -> str:
        """Get agent's current maturity for a capability."""
        if self.graduation:
            try:
                return self.graduation.get_maturity(agent_id, capability)
            except Exception as e:
                logger.error(f"Failed to get maturity for {agent_id}: {e}")
        return STUDENT

    def _get_agent_tenant(self, agent_id: str) -> str | None:
        """Get tenant_id for an agent."""
        try:
            from core.models import AgentRegistry

            agent = (
                self.db.query(AgentRegistry)
                .filter(AgentRegistry.id == agent_id)
                .first()
            )
            return agent.tenant_id if agent else None
        except Exception:
            return None
