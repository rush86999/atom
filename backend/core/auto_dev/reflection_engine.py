"""
Reflection Engine

Monitors the event bus for task failures and identifies recurring failure
patterns that warrant automatic skill generation via MementoEngine.

Operates as a "pattern detector":
- Filters for agents at Student/Intern maturity level
- Batches failure events by task similarity
- Triggers MementoEngine when a pattern occurs ≥ threshold times
- Queries ReflectionService for past critiques to enrich context
"""

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from core.auto_dev.event_hooks import TaskEvent, event_bus

logger = logging.getLogger(__name__)

# Minimum number of similar failures before triggering skill generation
DEFAULT_FAILURE_THRESHOLD = 2


class ReflectionEngine:
    """
    Monitors task failures and triggers Memento-Skills when patterns emerge.

    Usage:
        engine = ReflectionEngine(db)
        engine.register()  # Registers on event bus

        # Or manually:
        await engine.process_failure(event)
    """

    def __init__(
        self,
        db: Session,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    ):
        self.db = db
        self.failure_threshold = failure_threshold
        # In-memory failure pattern tracker: agent_id → [failure descriptions]
        self._failure_buffer: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def register(self) -> None:
        """Register this engine on the global event bus."""
        event_bus.on_task_fail(self.process_failure)
        logger.info("ReflectionEngine registered on event bus")

    async def process_failure(self, event: TaskEvent) -> None:
        """
        Process a task failure event.

        Adds the failure to the pattern buffer for the agent. If the
        number of similar failures exceeds the threshold, triggers
        MementoEngine to generate a skill candidate.
        """
        agent_id = event.agent_id

        # Check if this agent's maturity allows Auto-Dev
        if not self._should_process_agent(agent_id, event.tenant_id):
            return

        # Add to buffer
        self._failure_buffer[agent_id].append(
            {
                "episode_id": event.episode_id,
                "task_description": event.task_description,
                "error_trace": event.error_trace,
                "tenant_id": event.tenant_id,
            }
        )

        # Check for recurring pattern
        similar_failures = self._find_similar_failures(agent_id, event.task_description)

        if len(similar_failures) >= self.failure_threshold:
            logger.info(
                f"ReflectionEngine: {len(similar_failures)} similar failures detected "
                f"for agent {agent_id}. Triggering Memento-Skills."
            )
            await self._trigger_memento(
                agent_id=agent_id,
                tenant_id=event.tenant_id,
                episode_id=event.episode_id,
                similar_failures=similar_failures,
            )

            # Clear the buffer for this pattern to avoid re-triggering
            self._clear_pattern(agent_id, similar_failures)

    async def _trigger_memento(
        self,
        agent_id: str,
        tenant_id: str,
        episode_id: str,
        similar_failures: list[dict[str, Any]],
    ) -> None:
        """Trigger MementoEngine to generate a skill candidate."""
        try:
            from core.auto_dev.memento_engine import MementoEngine

            engine = MementoEngine(db=self.db)
            candidate = await engine.generate_skill_candidate(
                tenant_id=tenant_id,
                agent_id=agent_id,
                episode_id=episode_id,
            )
            logger.info(
                f"ReflectionEngine triggered skill candidate: {candidate.skill_name}"
            )
        except Exception as e:
            logger.error(f"ReflectionEngine failed to trigger Memento: {e}")

    def _should_process_agent(self, agent_id: str, tenant_id: str) -> bool:
        """Check if the agent should be processed for Auto-Dev."""
        try:
            from core.auto_dev.capability_gate import AutoDevCapabilityService

            gate = AutoDevCapabilityService(self.db)

            # Get workspace settings for this tenant
            workspace_settings = self._get_workspace_settings(tenant_id)

            return gate.can_use(
                agent_id=agent_id,
                capability="auto_dev.memento_skills",
                workspace_settings=workspace_settings,
            )
        except Exception:
            # If graduation framework isn't available, skip
            return False

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

    def _find_similar_failures(
        self, agent_id: str, task_description: str
    ) -> list[dict[str, Any]]:
        """Find failures with similar task descriptions for an agent."""
        buffer = self._failure_buffer.get(agent_id, [])
        # Simple word-overlap similarity
        task_words = set(task_description.lower().split())

        similar = []
        for failure in buffer:
            other_words = set(failure["task_description"].lower().split())
            if task_words and other_words:
                overlap = len(task_words & other_words) / max(
                    len(task_words), len(other_words)
                )
                if overlap >= 0.5:  # 50% word overlap threshold
                    similar.append(failure)

        return similar

    def _clear_pattern(
        self, agent_id: str, similar_failures: list[dict[str, Any]]
    ) -> None:
        """Remove processed failures from the buffer."""
        episode_ids = {f["episode_id"] for f in similar_failures}
        self._failure_buffer[agent_id] = [
            f
            for f in self._failure_buffer[agent_id]
            if f["episode_id"] not in episode_ids
        ]
