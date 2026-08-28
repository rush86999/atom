"""Chat-surface belief adapter (plan Phase 1 scope: chat adapter first).

Serves ``workspace.track`` queries from stores that background ingestion
already keeps fresh — GraphRAG entities/relationships — so no LLM call sits
on the track path (paper: rule-based background parser). Returns '' when
nothing matches so the caller falls through cleanly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

_MAX_SUMMARY_CHARS = 800


class ChatBeliefAdapter:
    """Belief source for chat-scoped agents: GraphRAG entity context."""

    async def belief_summary(self, topic: str, context: Dict[str, Any]) -> str:
        topic = str(topic or "").strip()
        if not topic:
            return ""
        try:
            from core.graphrag_engine import GraphRAGEngine

            engine = GraphRAGEngine(workspace_id=str(context.get("workspace_id") or "default"))
            ctx = await engine.get_context_for_ai(query=topic)
            if not ctx:
                return ""
            return str(ctx)[:_MAX_SUMMARY_CHARS]
        except Exception as e:
            logger.debug("bpe chat belief summary failed: %s", e)
            return ""
