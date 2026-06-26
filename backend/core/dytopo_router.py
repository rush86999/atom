"""
Ported from atom-saas (single-tenant strip).
SaaS-only features removed: tenant_id threading, BYOK tenant routing,
tenant-scoped usage tracker. Algorithm is identical.

DyTopo — manager-guided dynamic topology for fleet coordination.

Per round, each specialist emits a natural-language ``(query_need, key_offer)``
descriptor pair. The router:

1. embeds every query_need and every key_offer (env-var API keys via the
   existing upstream LLMService),
2. builds an N x M cosine similarity matrix,
3. threshold-gates edges (default ``DYTOPO_SIM_THRESHOLD = 0.72``),
4. enforces a DAG via a per-execution ``visited`` set (refuse edges that would
   revisit a node already in the current walk),
5. caps out-degree at ``MAX_OUT_DEGREE = 3`` to keep per-round token cost
   bounded.

This module is **stateless**: it holds per-execution ``visited`` state in
memory only (no DB writes, no LanceDB tables, no Alembic churn).

It follows the same additive + flag-gated + default-OFF pattern as the
``turn_fact_extractor`` hooks in ``core/generic_agent.py``. With the flag off
the router short-circuits and returns an empty adjacency.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── flags ────────────────────────────────────────────────────────────────────
DYTOPO_ROUTING_ENABLED: bool = (
    os.getenv("DYTOPO_ROUTING_ENABLED", "false").lower() == "true"
)
DYTOPO_SIM_THRESHOLD: float = float(os.getenv("DYTOPO_SIM_THRESHOLD", "0.72"))


class DyTopoRouter:
    """Manager-guided dynamic topology for fleet coordination (single-tenant).

    Holds a per-execution ``visited`` dict in memory so successive rounds on the
    same ``execution_id`` keep producing a DAG. The dict is keyed by
    ``execution_id`` and reset whenever ``compute_round_topology`` is called for
    a new execution.
    """

    MAX_OUT_DEGREE: int = 3

    def __init__(self, db: Session, llm: Any):
        self.db = db
        self.llm = llm
        self.threshold: float = DYTOPO_SIM_THRESHOLD
        # execution_id -> set of agent ids already placed in the topology walk.
        self._visited: Dict[str, set] = {}

    # ── public surface ───────────────────────────────────────────────────────

    async def compute_round_topology(
        self,
        execution_id: str,
        specialists: List[Any],
        prior_state: Optional[dict],
    ) -> Dict[str, Any]:
        """Compute the directed adjacency for the next coordination round."""
        if not DYTOPO_ROUTING_ENABLED:
            return {
                "adjacency": {},
                "round": (prior_state.get("round", 0) + 1) if prior_state else 1,
                "embeddings_cached": False,
                "enabled": False,
            }

        if execution_id not in self._visited:
            self._visited[execution_id] = set()

        round_num: int = (prior_state.get("round", 0) + 1) if prior_state else 1

        if len(specialists) < 2:
            return {
                "adjacency": {},
                "round": round_num,
                "embeddings_cached": False,
                "enabled": True,
            }

        # 1) Extract (query_need, key_offer) from each specialist.
        queries: List[str] = []
        keys: List[str] = []
        for agent in specialists:
            try:
                q, k = await self.extract_descriptor(agent, prior_state or {})
            except Exception as exc:
                logger.debug(
                    "dytopo descriptor extraction failed for %s: %s",
                    getattr(agent, "id", "?"),
                    exc,
                )
                q, k = "", ""
            queries.append(q)
            keys.append(k)

        # 2) Batch-embed (single-tenant: no tenant_id passed).
        try:
            query_embeddings = await self.llm.generate_embeddings_batch(queries)
            key_embeddings = await self.llm.generate_embeddings_batch(keys)
        except Exception as exc:
            logger.debug("dytopo embedding batch failed: %s", exc)
            return {
                "adjacency": {},
                "round": round_num,
                "embeddings_cached": False,
                "enabled": True,
            }

        # 3) Similarity + gating + DAG + out-degree cap.
        sim = self._similarity_matrix(query_embeddings, key_embeddings)
        gated = self._gate_edges(
            sim,
            threshold=self.threshold,
            agent_ids=[getattr(a, "id", str(i)) for i, a in enumerate(specialists)],
            visited=self._visited[execution_id],
            max_out_degree=self.MAX_OUT_DEGREE,
        )

        for dst_list in gated.values():
            for d in dst_list:
                self._visited[execution_id].add(d)

        return {
            "adjacency": gated,
            "round": round_num,
            "embeddings_cached": True,
            "enabled": True,
        }

    async def extract_descriptor(self, agent: Any, observation: Any) -> Tuple[str, str]:
        """Ask the specialist LLM for a ``(query_need, key_offer)`` pair."""
        prompt = (
            "You are a specialist agent in a fleet. Emit two short, plain-text "
            "descriptors:\n"
            "  - query_need: what you need from another specialist to progress\n"
            "  - key_offer: what you can contribute to another specialist\n"
            'Return JSON: {"query_need": str, "key_offer": str}'
        )
        agent_id = getattr(agent, "id", "unknown")
        agent_name = getattr(agent, "name", agent_id)
        try:
            resp = await self.llm.generate_structured_response(
                prompt=prompt,
                context={"agent_id": agent_id, "agent_name": agent_name},
            )
        except Exception as exc:
            logger.debug("dytopo structured_response failed for %s: %s", agent_id, exc)
            return "", ""

        if isinstance(resp, dict):
            q = str(resp.get("query_need", "") or "").strip()
            k = str(resp.get("key_offer", "") or "").strip()
            return q, k
        return "", ""

    # ── internals ────────────────────────────────────────────────────────────

    def _similarity_matrix(
        self, queries: List[List[float]], keys: List[List[float]]
    ) -> List[List[float]]:
        try:
            q = np.asarray(queries, dtype=float)
            k = np.asarray(keys, dtype=float)
            if q.ndim != 2 or k.ndim != 2 or q.shape[1] != k.shape[1]:
                return [[0.0 for _ in keys] for _ in queries]
            q_norm = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-12)
            k_norm = k / (np.linalg.norm(k, axis=1, keepdims=True) + 1e-12)
            return (q_norm @ k_norm.T).tolist()
        except Exception as exc:
            logger.debug("dytopo similarity matrix failed: %s", exc)
            return [[0.0 for _ in keys] for _ in queries]

    def _gate_edges(
        self,
        sim: List[List[float]],
        threshold: float,
        agent_ids: List[str],
        visited: set,
        max_out_degree: int,
    ) -> Dict[str, List[str]]:
        adjacency: Dict[str, List[str]] = {aid: [] for aid in agent_ids}
        for i, src_id in enumerate(agent_ids):
            row = sim[i] if i < len(sim) else []
            ranked = sorted(
                (
                    (j, score)
                    for j, score in enumerate(row)
                    if j < len(agent_ids) and j != i and score >= threshold
                ),
                key=lambda x: x[1],
                reverse=True,
            )
            for j, _score in ranked:
                if len(adjacency[src_id]) >= max_out_degree:
                    break
                dst_id = agent_ids[j]
                if dst_id in visited:
                    continue
                if dst_id in adjacency[src_id]:
                    continue
                adjacency[src_id].append(dst_id)
        return adjacency
