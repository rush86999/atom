"""
Evolution Engine

Background optimizer that listens for skill execution events on
Autonomous-tier agents and triggers AlphaEvolverEngine when performance
signals indicate optimization opportunities.

Monitors:
- High execution latency (>5s)
- High token usage
- Partial failures / retries
- Low fitness scores on existing variants

Requires AUTONOMOUS maturity level and explicit workspace opt-in.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from core.auto_dev.event_hooks import SkillExecutionEvent, event_bus

logger = logging.getLogger(__name__)

# Thresholds for triggering optimization
LATENCY_THRESHOLD_SECONDS = 5.0
TOKEN_THRESHOLD = 5000


class EvolutionEngine:
    """
    Background optimizer that triggers AlphaEvolver on underperforming skills.

    Usage:
        engine = EvolutionEngine(db)
        engine.register()  # Registers on event bus
    """

    def __init__(self, db: Session):
        self.db = db

    def register(self) -> None:
        """Register this engine on the global event bus."""
        event_bus.on_skill_execution(self.process_execution)
        logger.info("EvolutionEngine registered on event bus")

    async def process_execution(self, event: SkillExecutionEvent) -> None:
        """
        Evaluate a skill execution and trigger optimization if warranted.

        Only processes agents with AUTONOMOUS maturity and workspace opt-in.
        """
        # Gate check: background evolution requires AUTONOMOUS
        if not self._should_optimize(event.agent_id, event.tenant_id):
            return

        # Check if optimization is warranted
        optimization_reason = self._check_optimization_triggers(event)
        if not optimization_reason:
            return

        logger.info(
            f"EvolutionEngine: Triggering optimization for skill '{event.skill_name}' "
            f"(agent {event.agent_id}). Reason: {optimization_reason}"
        )

        await self._trigger_alpha_evolver(event, optimization_reason)

    async def _trigger_alpha_evolver(
        self, event: SkillExecutionEvent, reason: str
    ) -> None:
        """Trigger AlphaEvolverEngine for the underperforming skill."""
        try:
            from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine

            engine = AlphaEvolverEngine(db=self.db)

            # We need the skill's source code to mutate it.
            # Attempt to retrieve it from the skill registry.
            skill_code = self._get_skill_code(event.skill_id, event.tenant_id)
            if not skill_code:
                logger.warning(
                    f"Cannot optimize skill {event.skill_id}: source code not found"
                )
                return

            mutation = await engine.generate_tool_mutation(
                tenant_id=event.tenant_id,
                tool_name=event.skill_name or event.skill_id,
                parent_tool_id=None,
                base_code=skill_code,
                mutation_prompt=(
                    f"Optimize this skill for: {reason}. "
                    f"Current latency: {event.execution_seconds:.2f}s. "
                    f"Current token usage: {event.token_usage}."
                ),
            )

            # Auto-validate the mutation
            exec_result = await engine.sandbox_execute_mutation(
                mutation_id=mutation.id,
                tenant_id=event.tenant_id,
                inputs={},
            )

            if exec_result.get("success"):
                logger.info(
                    f"EvolutionEngine: Mutation {mutation.id} passed sandbox. "
                    f"Queued for review."
                )
            else:
                logger.info(
                    f"EvolutionEngine: Mutation {mutation.id} failed sandbox. "
                    f"Discarding."
                )

        except Exception as e:
            logger.error(f"EvolutionEngine optimization failed: {e}")

    def _should_optimize(self, agent_id: str, tenant_id: str) -> bool:
        """Check if the agent has AUTONOMOUS maturity for background evolution."""
        try:
            from core.auto_dev.capability_gate import AutoDevCapabilityService

            gate = AutoDevCapabilityService(self.db)
            workspace_settings = self._get_workspace_settings(tenant_id)

            return gate.can_use(
                agent_id=agent_id,
                capability="auto_dev.background_evolution",
                workspace_settings=workspace_settings,
            )
        except Exception:
            return False

    def _check_optimization_triggers(
        self, event: SkillExecutionEvent
    ) -> str | None:
        """Check if the skill execution warrants optimization."""
        reasons = []

        if event.execution_seconds > LATENCY_THRESHOLD_SECONDS:
            reasons.append(f"high_latency ({event.execution_seconds:.1f}s)")

        if event.token_usage > TOKEN_THRESHOLD:
            reasons.append(f"high_token_usage ({event.token_usage})")

        if not event.success:
            reasons.append("execution_failure")

        return ", ".join(reasons) if reasons else None

    def _get_skill_code(self, skill_id: str, tenant_id: str) -> str | None:
        """Retrieve the source code for a skill."""
        try:
            from core.skill_builder_service import SkillBuilderService
            from pathlib import Path

            builder = SkillBuilderService()
            skills_dir = builder._get_tenant_skills_dir(tenant_id)

            # Search for the skill by ID in the skills directory
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    for script in skill_dir.glob("*.py"):
                        if skill_id in str(script):
                            return script.read_text()

            return None
        except Exception:
            return None

    def _get_workspace_settings(self, tenant_id: str) -> dict[str, Any]:
        """Retrieve workspace settings for a tenant."""
        try:
            from core.models import Workspace

            workspace = (
                self.db.query(Workspace)
                .filter(Workspace.tenant_id == tenant_id)
                .first()
            )
            if workspace and workspace.metadata_json:
                return workspace.metadata_json
        except Exception:
            pass
        return {}
