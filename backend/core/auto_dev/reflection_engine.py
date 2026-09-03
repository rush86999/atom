"""
Reflection Engine

Monitors the event bus for task failures and identifies recurring failure
patterns that warrant automatic fixes:

  - TOOL-flavored failures (structured tool_errors recorded at the
    integration chokepoint — core/auto_dev/tool_error_signals.py) route to
    AlphaEvolverEngine → tool-code mutation candidates.
  - Everything else routes to MementoEngine → NEW skill candidates.

Operates as a "pattern detector":
- Filters for agents at Student/Intern maturity level (capability gate)
- Batches failure events by task similarity
- Triggers an engine when a pattern occurs ≥ threshold times
- Both engines emit PENDING candidates — sandbox validation and supervisor
  approval stay mandatory; nothing auto-deploys.

Until 2026-09-02 this listener existed but was never constructed, so
emit_task_fail fired into the void — register_global() (called from app
startup) is what makes the harness actually run.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session

from core.auto_dev.event_hooks import TaskEvent, event_bus
from core.auto_dev.tool_error_signals import tool_error_signature

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
        db: Session | None = None,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    ):
        # db=None → long-lived bus-listener mode: a fresh session per event
        # (a process-lifetime SQLAlchemy session would go stale).
        self.db = db
        self.failure_threshold = failure_threshold
        # In-memory failure pattern tracker: agent_id → [failure descriptions]
        self._failure_buffer: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def register(self) -> None:
        """Register this engine on the global event bus."""
        event_bus.on_task_fail(self.process_failure)
        logger.info("ReflectionEngine registered on event bus")

    @contextmanager
    def _working_session(self):
        """The engine's working session — the caller's when provided, else a
        fresh per-event session that is closed on exit (listener mode)."""
        if self.db is not None:
            yield self.db
        else:
            from core.database import SessionLocal

            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

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

        # Add to buffer. Structured tool_errors (recorded at the
        # integration chokepoint) ride along — they are what routes the
        # pattern to AlphaEvolver instead of Memento.
        _tool_errors = (event.metadata or {}).get("tool_errors") or []
        _first_tool_error = (
            _tool_errors[0]
            if isinstance(_tool_errors, list) and _tool_errors
            else None
        )
        self._failure_buffer[agent_id].append(
            {
                "episode_id": event.episode_id,
                "task_description": event.task_description,
                "error_trace": event.error_trace,
                "tenant_id": event.tenant_id,
                "tool_error": _first_tool_error
                if isinstance(_first_tool_error, dict)
                else None,
            }
        )

        # Check for recurring pattern
        similar_failures = self._find_similar_failures(agent_id, event.task_description)

        if len(similar_failures) >= self.failure_threshold:
            logger.info(
                f"ReflectionEngine: {len(similar_failures)} similar failures detected "
                f"for agent {agent_id}. Triggering Auto-Dev fix."
            )
            await self._trigger_fix(
                agent_id=agent_id,
                tenant_id=event.tenant_id,
                episode_id=event.episode_id,
                similar_failures=similar_failures,
            )

            # Clear the buffer for this pattern to avoid re-triggering
            self._clear_pattern(agent_id, similar_failures)

    async def _trigger_fix(
        self,
        agent_id: str,
        tenant_id: str,
        episode_id: str,
        similar_failures: list[dict[str, Any]],
    ) -> None:
        """Trigger a FIX for a recurring failure pattern.

        Tool-flavored failures go to AlphaEvolver (tools are fixed by
        mutating tool code); everything else goes to Memento (a NEW skill
        that works around the gap). Falls back to Memento when no tool
        source can be resolved for the failing tool."""
        try:
            tool_error = next(
                (f.get("tool_error") for f in similar_failures if f.get("tool_error")),
                None,
            )
            if tool_error and await self._trigger_alpha_evolver(
                agent_id, tenant_id, episode_id, tool_error
            ):
                return

            from core.auto_dev.memento_engine import MementoEngine

            with self._working_session() as db:
                engine = MementoEngine(db=db)
                candidate = await engine.generate_skill_candidate(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    episode_id=episode_id,
                )
                skill_name = candidate.skill_name
            from core.auto_dev.guidance import notify_proposal

            notify_proposal(
                agent_id=agent_id,
                tenant_id=tenant_id,
                kind="skill",
                name=skill_name,
                candidate_id=str(candidate.id),
                failure_summary=str(getattr(candidate, "skill_description", "") or ""),
            )
            logger.info(f"ReflectionEngine triggered skill candidate: {skill_name}")
        except Exception as e:
            logger.error(f"ReflectionEngine failed to trigger Memento: {e}")

    async def _trigger_alpha_evolver(
        self,
        agent_id: str,
        tenant_id: str,
        episode_id: str,
        tool_error: dict[str, Any],
    ) -> bool:
        """Attempt a tool-code mutation for a recurring TOOL error.
        Returns False when the failing tool's source can't be resolved
        (integration services aren't registered as mutable tools) — the
        caller then falls back to a Memento skill."""
        try:
            from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine

            tool_name = str(tool_error.get("signature") or "")
            base_code = resolve_tool_source(tool_name)
            if not base_code:
                return False

            with self._working_session() as db:
                engine = AlphaEvolverEngine(db=db)
                mutation = await engine.generate_tool_mutation(
                    tenant_id=tenant_id,
                    tool_name=tool_name,
                    parent_tool_id=None,
                    base_code=base_code,
                    mutation_prompt=(
                        "This tool repeatedly fails in production with: "
                        f"{tool_error.get('error')}. Mutate the tool code to "
                        "handle the failing condition (sanitize inputs, "
                        "retry idempotently, or degrade gracefully) without "
                        "changing its outward contract."
                    ),
                )
            from core.auto_dev.guidance import notify_proposal

            notify_proposal(
                agent_id=agent_id,
                tenant_id=tenant_id,
                kind="mutation",
                name=tool_name,
                candidate_id=str(getattr(mutation, "id", "") or ""),
                failure_summary=str(tool_error.get("error") or ""),
            )
            logger.info(
                f"ReflectionEngine triggered tool mutation candidate for {tool_name}"
            )
            return True
        except Exception as e:
            logger.warning(f"ReflectionEngine tool mutation skipped: {e}")
            return False

    def _should_process_agent(self, agent_id: str, tenant_id: str) -> bool:
        """Check if the agent should be processed for Auto-Dev."""
        try:
            from core.auto_dev.capability_gate import AutoDevCapabilityService

            with self._working_session() as db:
                gate = AutoDevCapabilityService(db)
                workspace_settings = self._get_workspace_settings(db, tenant_id)
                return gate.can_use(
                    agent_id=agent_id,
                    capability="auto_dev.memento_skills",
                    workspace_settings=workspace_settings,
                )
        except Exception:
            # If graduation framework isn't available, skip
            return False

    def _get_workspace_settings(self, db: Session, tenant_id: str) -> dict[str, Any]:
        """Retrieve workspace settings for a tenant."""
        try:
            from core.models import Workspace

            workspace = (
                db.query(Workspace)
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


# Module-level singleton — registered once at app startup so emitted
# task-fail events actually reach Memento/AlphaEvolver.
_engine_singleton: ReflectionEngine | None = None


def register_global(
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
) -> ReflectionEngine:
    """Idempotently create + register the process-wide ReflectionEngine."""
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = ReflectionEngine(
            db=None, failure_threshold=failure_threshold
        )
        _engine_singleton.register()
    return _engine_singleton


def resolve_tool_source(tool_name: str) -> str | None:
    """Source code of a registered tool, when it exists in action_registry.
    Integration services (outlook/gmail/…) are NOT registered there — they
    aren't mutable tools, and their failures fall back to Memento skills."""
    try:
        import inspect

        from core.action_registry import action_registry

        action = action_registry.get_action(tool_name)
        handler = getattr(action, "handler", None)
        if handler is not None:
            return inspect.getsource(handler)
    except Exception:
        pass
    return None


async def trigger_live_tool_fix(
    agent_id: str,
    tenant_id: str,
    service: str,
    action: str,
    error_detail: str,
    execution_id: str | None = None,
) -> bool:
    """REAL-TIME evolution trigger for an ACTIVE task.

    Called by the integration chokepoint the moment a tool error pattern
    crosses the repeat threshold — no waiting for episode finalization.
    AlphaEvolver's generate_tool_mutation needs only the tool source + the
    error, so a fix candidate can exist while the task is still running.
    Returns True when a mutation candidate was proposed."""
    tool_name = tool_error_signature(service, action)
    base_code = resolve_tool_source(tool_name)
    if not base_code:
        logger.debug(
            f"live evolution trigger: {tool_name} is not a registered tool — "
            "episode-time Memento path remains")
        return False
    try:
        from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
        from core.auto_dev.guidance import notify_proposal
        from core.database import SessionLocal

        with SessionLocal() as db:
            engine = AlphaEvolverEngine(db=db)
            mutation = await engine.generate_tool_mutation(
                tenant_id=tenant_id,
                tool_name=tool_name,
                parent_tool_id=None,
                base_code=base_code,
                mutation_prompt=(
                    "This tool repeatedly fails in production with: "
                    f"{error_detail}. Mutate the tool code to handle the "
                    "failing condition (sanitize inputs, retry "
                    "idempotently, or degrade gracefully) without changing "
                    "its outward contract."
                ),
            )
        notify_proposal(
            agent_id=agent_id,
            tenant_id=tenant_id,
            kind="mutation",
            name=tool_name,
            candidate_id=str(getattr(mutation, "id", "") or ""),
            failure_summary=str(error_detail or ""),
        )
        if execution_id:
            _mark_execution_triggered(execution_id, tool_name, str(getattr(mutation, "id", "") or ""))
        logger.info(
            f"Live evolution trigger: tool mutation candidate for {tool_name} "
            f"(agent {agent_id}, active task)")
        return True
    except Exception as e:
        logger.warning(f"live evolution trigger failed for {tool_name}: {e}")
        return False


def _mark_execution_triggered(
    execution_id: str, tool_name: str, mutation_id: str
) -> None:
    """Mark the ACTIVE execution so its task record shows the evolution
    harness engaged mid-flight."""
    try:
        from core.database import SessionLocal
        from core.models import AgentExecution

        with SessionLocal() as db:
            execution = db.query(AgentExecution).filter(
                AgentExecution.id == execution_id
            ).first()
            if execution is None:
                return
            meta = dict(execution.metadata_json or {})
            meta["evolution_triggered"] = {
                "tool": tool_name,
                "mutation_id": mutation_id,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            execution.metadata_json = meta
            db.commit()
    except Exception as e:
        logger.debug(f"evolution marker skipped: {e}")
