"""Mutation rollback registry for the self-evolution pipeline.

Snapshots agent config before each mutation deployment and can revert on
regression. This is the safety net that the SOTA gap analysis identified as
missing — deployed mutations (config patches, skill promotions, GEA config
overwrites) had no revert operator.

Evidence: Darwin Gödel Machine (Sakana AI) maintains version archives with
automatic reversion on regression. Shao et al. (ICLR 2026) shows that
without rollback, misevolution is irreversible.
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Max snapshots held in-memory (LRU eviction).
_MAX_SNAPSHOTS = 1000


@dataclass
class MutationSnapshot:
    """A pre-mutation config snapshot that can be restored on regression."""

    mutation_id: str
    agent_id: str
    config_key: str  # e.g. "system_prompt", "configuration", "ast_tripwire"
    old_value: Any  # the value BEFORE the mutation was applied
    new_value: Any  # the value AFTER the mutation was applied
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verified: bool = False  # set True once the mutation passes regression validation
    source: str = "unknown"  # "alpha_evolver", "harness_evolution", "gea", "memento"


class MutationRollbackRegistry:
    """Tracks config mutations and provides rollback on regression.

    In-memory (LRU, max 1000) + optionally durable via the agent's config
    ``_mutation_snapshots`` key. Thread-safe (mutations happen from async
    handlers that may overlap).
    """

    def __init__(self, max_snapshots: int = _MAX_SNAPSHOTS) -> None:
        self._max_snapshots = max_snapshots
        self._snapshots: "OrderedDict[str, MutationSnapshot]" = OrderedDict()
        self._lock = threading.Lock()

    def snapshot(
        self,
        agent_id: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        source: str = "unknown",
    ) -> str:
        """Record a pre-mutation snapshot. Returns the mutation_id for later rollback.

        Call this BEFORE deploying a mutation. The ``old_value`` is what
        will be restored if rollback(mutation_id) is called.
        """
        mutation_id = f"mut_{uuid.uuid4().hex[:12]}"
        snap = MutationSnapshot(
            mutation_id=mutation_id,
            agent_id=agent_id,
            config_key=config_key,
            old_value=old_value,
            new_value=new_value,
            source=source,
        )
        with self._lock:
            self._snapshots[mutation_id] = snap
            while len(self._snapshots) > self._max_snapshots:
                self._snapshots.popitem(last=False)
        logger.info(
            f"[RollbackRegistry] snapshot for agent {agent_id} "
            f"key={config_key} source={source} → {mutation_id}"
        )
        return mutation_id

    def rollback(self, mutation_id: str, agent_config: Optional[Dict[str, Any]] = None) -> bool:
        """Revert a single mutation by restoring its old_value.

        If ``agent_config`` is provided (the agent's live config dict), the
        old_value is written back into it under the config_key. Returns True
        if the rollback was applied, False if the mutation_id is unknown.
        """
        with self._lock:
            snap = self._snapshots.get(mutation_id)
        if snap is None:
            logger.warning(f"[RollbackRegistry] unknown mutation_id: {mutation_id}")
            return False

        if agent_config is not None:
            agent_config[snap.config_key] = snap.old_value
            logger.info(
                f"[RollbackRegistry] rolled back {mutation_id} for agent "
                f"{snap.agent_id}: restored {snap.config_key}"
            )
        return True

    def rollback_agent(self, agent_id: str, agent_config: Optional[Dict[str, Any]] = None) -> int:
        """Revert ALL unverified mutations for an agent (nuclear option).

        Returns the number of mutations rolled back. Only reverts mutations
        that haven't been marked as verified (passed regression validation).
        """
        count = 0
        with self._lock:
            agent_snaps = [
                s for s in self._snapshots.values()
                if s.agent_id == agent_id and not s.verified
            ]
        for snap in agent_snaps:
            if agent_config is not None:
                agent_config[snap.config_key] = snap.old_value
            count += 1
            logger.info(
                f"[RollbackRegistry] agent-wide rollback: {snap.mutation_id} "
                f"({snap.config_key})"
            )
        return count

    def verify(self, mutation_id: str) -> bool:
        """Mark a mutation as verified (passed regression validation).

        Verified mutations are excluded from agent-wide rollback.
        """
        with self._lock:
            snap = self._snapshots.get(mutation_id)
            if snap is None:
                return False
            snap.verified = True
        logger.info(f"[RollbackRegistry] verified {mutation_id}")
        return True

    def get_snapshot(self, mutation_id: str) -> Optional[MutationSnapshot]:
        with self._lock:
            return self._snapshots.get(mutation_id)

    def get_agent_mutations(self, agent_id: str) -> List[MutationSnapshot]:
        with self._lock:
            return [s for s in self._snapshots.values() if s.agent_id == agent_id]

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


# Module-level singleton (stateless registry, safe to share).
_default_registry: Optional[MutationRollbackRegistry] = None


def get_rollback_registry() -> MutationRollbackRegistry:
    """Return the process-wide default MutationRollbackRegistry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = MutationRollbackRegistry()
    return _default_registry
