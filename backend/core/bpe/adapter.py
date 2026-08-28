"""Domain adapter seam for the BPE workspace.

The paper's environment-adapter pattern: BPE is a *functional interface*,
not a fixed schema. Domain-specific internals (what "belief" means for chat
vs. workflow vs. research surfaces) live behind :class:`BPEAdapter`; the
coordination layer (:class:`~core.bpe.workspace.BPEWorkspace`) stays shared.

Belief maintenance is deliberately off the hot path: the adapter serves
``track`` queries from stores that background processes keep fresh
(GraphRAG entities, ``business_facts``, VFS document state), mirroring the
paper's rule-based background parser.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class BPEAdapter(Protocol):
    """Bridges domain-specific state to the shared ``track`` interface.

    ``belief_summary`` may be sync or async; the workspace awaits either.
    """

    def belief_summary(self, topic: str, context: Dict[str, Any]) -> str:
        """Return a compact belief summary for ``topic`` ('' when unknown)."""
        ...  # pragma: no cover - protocol


class NullAdapter:
    """Default adapter: no belief source wired — ``track`` returns empty."""

    def belief_summary(self, topic: str, context: Dict[str, Any]) -> str:
        return ""


class CompositeAdapter:
    """Fans ``track`` queries across adapters; first non-empty summary wins.

    Registration order is priority order (most specific adapter first).
    Adapter summaries may be sync or async; async results are awaited.
    """

    def __init__(self, adapters: Optional[list] = None) -> None:
        self._adapters = list(adapters or [])

    def add(self, adapter: Any) -> None:
        self._adapters.append(adapter)

    async def belief_summary(self, topic: str, context: Dict[str, Any]) -> str:
        import inspect

        for adapter in self._adapters:
            try:
                summary = adapter.belief_summary(topic, context)
                if inspect.isawaitable(summary):
                    summary = await summary
            except Exception as e:  # one bad source must not break tracking
                logger.debug("bpe adapter %s failed: %s", type(adapter).__name__, e)
                continue
            if summary:
                return summary
        return ""
