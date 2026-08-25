"""
Memory Context Assembler — unified turn-time retrieval for chat/IM surfaces.

Combines the platform's memory systems into one bounded prompt block at the
moment an employee talks to an agent:

  - Communication memory (emails/Slack/WhatsApp/Teams…) — LanceDB hybrid
    (vector + FTS) via CommunicationIngestionPipeline
  - Documents + conversations — DocumentsHybridSearch (BM25 + vector RRF
    fused, conversations leg bridged to the comms store; bridge, don't copy)
  - GraphRAG context (ontology identities + relationships) — graphrag_engine
  - Learning episodes — EpisodeRetrievalService.retrieve_contextual
  - Durable turn facts — prefetch_relevant_facts (Tier-2 recall)

Design (docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md, P0):
  - Every leg is independently fault-isolated: a failing store yields an
    empty block, never an error.
  - Per-leg timeout enforced via asyncio.wait_for; sync legs run in threads
    so they cannot block the event loop.
  - Hard output budget: per-block and total character caps keep the injected
    context small and high-precision (Claude-style bounded block, not a
    growing fact list).
  - Off by default is NOT the goal — default ON via MEMORY_CONTEXT_ASSEMBLY
    (default true); set false to restore the legacy memory-less behavior.

Reads happen at turn time; writes (fact extraction, consolidation) stay on
their own paths (Letta sleep-time principle).
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ENV_FLAG = "MEMORY_CONTEXT_ASSEMBLY"

PER_LEG_TIMEOUT_SECONDS = 1.5  # steady-state is 10–50ms/leg; first call pays
                                # embedding-model loads, so allow a cold start.
TOTAL_CHAR_BUDGET = 10_000          # ≈ 2.5k tokens across all blocks
GRAPH_CHAR_CAP = 3_200
KNOWLEDGE_CHAR_CAP = 2_000
EPISODES_CHAR_CAP = 1_200
FACTS_CHAR_CAP = 1_600
SNIPPET_CHAR_CAP = 220

# P1.4 rerank: budget-gated second pass over each leg's candidates before
# the per-block caps truncate them — keeps the most relevant lines, not the
# first N a store happened to return. Cross-encoder (HybridRetrievalService
# reuse) when torch is healthy; fastembed cosine-similarity fallback (works
# without torch); no-op otherwise. Plan budget: rerank only when total
# assembly stays < 800 ms (docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md §6).
RERANK_FLAG = "MEMORY_CONTEXT_RERANK"
RERANK_BUDGET_MS = 700               # enter the rerank phase only if gather ≤ 700ms
RERANK_LEG_TIMEOUT_SECONDS = 0.250   # per-leg rerank cap (CPU cross-encoder is slow)
RERANK_MIN_LINES = 3                 # nothing to decide below this


def assembly_enabled() -> bool:
    from core.experiments import is_enabled

    return is_enabled("memory_context_assembly")


def rerank_enabled() -> bool:
    return os.getenv(RERANK_FLAG, "true").lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------- #
# Legs
# --------------------------------------------------------------------------- #

async def _graph_leg(message: str, workspace_id: str, tenant_id: str) -> str:
    from core.graphrag_engine import GraphRAGEngine

    engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)
    context = await engine.get_context_for_ai(query=message[:500])
    if not context:
        return ""
    context = str(context).strip()
    if len(context) > GRAPH_CHAR_CAP:
        context = context[:GRAPH_CHAR_CAP] + "…"
    return context


async def _knowledge_leg(message: str, workspace_id: str) -> List[str]:
    """Unified hybrid knowledge leg (P1.3) — documents + conversations fused
    by RRF via DocumentsHybridSearch (BM25 FTS5/tsvector + LanceDB vector,
    plus the conversations leg bridged to the comms store — bridge, don't
    copy: no comms record is duplicated into documents). Replaces the
    standalone comms-only leg: the hybrid path covers the comms store itself.
    Runs async I/O directly; per-leg timeout applies at the call site."""
    try:
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        result = await DocumentsHybridSearch().search(
            query=message[:500], limit=6
        )
    except Exception as e:
        logger.debug(f"memory assembler: knowledge leg failed: {e}")
        return []
    lines: List[str] = []
    for hit in (result or {}).get("results", []) or []:
        source = str(hit.get("source") or "doc")
        title = str(hit.get("title") or "").strip()
        preview = str(hit.get("preview") or "").strip().replace("\n", " ")
        if not preview:
            continue
        if len(preview) > SNIPPET_CHAR_CAP:
            preview = preview[:SNIPPET_CHAR_CAP] + "…"
        label = title if title else source
        lines.append(f"[{source}: {label}] {preview}")
    return lines


async def _episodes_leg(message: str, agent_id: str) -> List[str]:
    from core.database import SessionLocal
    from core.episode_retrieval_service import EpisodeRetrievalService

    db = SessionLocal()
    try:
        service = EpisodeRetrievalService(db)
        result = await service.retrieve_contextual(agent_id, message[:500], limit=3)
    finally:
        db.close()
    lines: List[str] = []
    for ep in (result or {}).get("episodes", []) or []:
        summary = str(
            ep.get("summary") or ep.get("title") or ep.get("description") or ""
        ).strip()
        if not summary:
            continue
        outcome = ep.get("outcome") or ""
        if len(summary) > SNIPPET_CHAR_CAP:
            summary = summary[:SNIPPET_CHAR_CAP] + "…"
        suffix = f" (outcome: {outcome})" if outcome else ""
        lines.append(summary.replace("\n", " ") + suffix)
    return lines


async def _facts_leg(message: str, workspace_id: str) -> List[str]:
    from core.turn_fact_extractor import prefetch_relevant_facts

    facts = await asyncio.to_thread(
        prefetch_relevant_facts, workspace_id, message[:500], 5
    )
    return [str(getattr(f, "fact_text", "")).strip() for f in facts or [] if getattr(f, "fact_text", "")]


async def _integration_records_leg(
    message: str, workspace_id: str, agent_role: Optional[str] = None
) -> List[str]:
    """Vector search over ALL ingested 3rd-party integration data
    (`integration_*` LanceDB tables written by the hybrid sync pipeline —
    Zoho, Shopify, Salesforce, OneDrive, Drive, …). Previously these tables
    were write-only; this leg makes every integration's ingested records
    retrievable at turn time. Runs in a thread (sync LanceDB I/O).

    Role-aware recall (Round 80, integration-data half): when the operating
    AI employee's role (AgentRegistry.category, lowercased) is known, records
    tagged ``metadata.role == <role>`` at sync time are surfaced FIRST and
    untagged general records top up the remaining slots — mirroring
    WorldModelService._recall_general_knowledge. Additive, never exclusive:
    a role with no tagged records still gets the general pool."""

    safe_role = str(agent_role).lower().replace("'", "''") if agent_role else None

    def _search() -> List[str]:
        from core.lancedb_handler import get_lancedb_handler

        try:
            handler = get_lancedb_handler(workspace_id)
            if handler is None:
                logger.info(f"integration records leg: no handler for ws {workspace_id}")
                return []
            handler._ensure_db()  # connection is lazy; the guard below must not
                                  # fire before search() had a chance to init it
            if handler.db is None:
                logger.info(f"integration records leg: lancedb not connected for ws {workspace_id}")
                return []
            tables = [
                t for t in handler.db.table_names() if str(t).startswith("integration_")
            ]
            logger.info(
                f"integration records leg: ws={workspace_id} role={safe_role} "
                f"tables={tables[:6] if len(tables) > 6 else tables} "
                f"({len(tables)} total)"
            )
        except Exception as e:
            logger.info(f"integration records leg: table list failed for ws {workspace_id}: {e}")
            return []
        lines: List[str] = []
        seen_ids: set = set()

        def _hit_role(rec: dict) -> str:
            """Role tag for a hit. `metadata` is a JSON *string* column in
            LanceDB, so a server-side `metadata.role == …` filter can never
            match (R83) — parse client-side instead."""
            import json as _json

            raw = rec.get("metadata")
            if isinstance(raw, str):
                try:
                    raw = _json.loads(raw)
                except Exception:  # noqa: BLE001
                    return ""
            if not isinstance(raw, dict):
                return ""
            return str(raw.get("role") or "").lower()

        for table_name in tables[:6]:  # bounded: newest common integrations
            # Pass 1 (role-scoped): records synced FOR this employee's role.
            #   R83: role matching is done post-search (see _hit_role) — the
            #   old `metadata.role == '…'` DataFusion filter always returned []
            #   against the string-typed column, silently disabling the pass.
            # Pass 2 (general): untagged top-up so a role with few tagged
            # records never starves — additive, never exclusive.
            passes = [None]
            per_pass_limit = 2 if not safe_role else 3  # extra headroom for post-filter
            for filter_str in passes:
                try:
                    results = handler.search(
                        table_name,
                        message[:500],
                        limit=per_pass_limit,
                        filter_str=filter_str,
                    )
                    logger.info(
                        f"integration records leg: {table_name} "
                        f"filter={filter_str or 'none'} search returned "
                        f"{len(results or [])} hits"
                    )
                except Exception as e:
                    logger.info(
                        f"integration records leg: {table_name} search failed "
                        f"(filter={filter_str or 'none'}): {e}"
                    )
                    continue
                if safe_role and results:
                    role_first = [r for r in results if _hit_role(r) == safe_role]
                    results = role_first + [
                        r for r in results if _hit_role(r) != safe_role
                    ]
                for rec in results or []:
                    if rec.get("id") in seen_ids:
                        continue
                    text = str(rec.get("text") or rec.get("content") or "").strip()
                    if not text:
                        continue
                    seen_ids.add(rec.get("id"))
                    source = str(rec.get("source") or table_name.replace("integration_", ""))
                    if len(text) > SNIPPET_CHAR_CAP:
                        text = text[:SNIPPET_CHAR_CAP] + "…"
                    lines.append(f"[{source}] " + text.replace("\n", " "))
        return lines

    return await asyncio.to_thread(_search)


def _resolve_agent_role(agent_id: Optional[str]) -> Optional[str]:
    """Map an agent id to its role (AgentRegistry.category, lowercased) —
    the SAME tag sync_integration_data(role=...) stamps at ingest, so the
    two halves of the Round-80 role loop always agree. Best-effort and
    fault-isolated: None (general knowledge) on any failure."""
    if not agent_id:
        return None
    try:
        from core.database import SessionLocal
        from core.models import AgentRegistry

        db = SessionLocal()
        try:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if agent and getattr(agent, "category", None):
                return str(agent.category).lower()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"agent role resolution failed for {agent_id}: {e}")
    return None


# --------------------------------------------------------------------------- #
# P1.4 rerank (budget-gated; cross-encoder → fastembed cosine → no-op)
# --------------------------------------------------------------------------- #

_RERANK_MODEL = None       # None = not probed; False = unavailable; else CrossEncoder
_RERANK_MODEL_PROBED = False
_RERANK_EMBEDDER = None    # lazy EmbeddingService(fastembed)


async def _probe_cross_encoder() -> Any:
    """One-time availability probe for the cross-encoder tier (plan intent:
    HybridRetrievalService reuse, in-process). Heavy — imports torch and can
    load/download the model — so it must run from `warm()`, never the hot
    path. Caches the result; never raises."""
    global _RERANK_MODEL, _RERANK_MODEL_PROBED
    if _RERANK_MODEL_PROBED:
        return _RERANK_MODEL
    _RERANK_MODEL_PROBED = True
    try:
        from core.database import SessionLocal
        from core.hybrid_retrieval_service import HybridRetrievalService

        db = SessionLocal()
        try:
            svc = HybridRetrievalService(db)
            model = await svc._get_reranker_model()
            _RERANK_MODEL = model if model is not False else False
        finally:
            db.close()
    except Exception as e:
        logger.info(f"memory assembler: cross-encoder unavailable: {e}")
        _RERANK_MODEL = False
    return _RERANK_MODEL


async def _rerank_lines(query: str, lines: List[str]) -> List[str]:
    """Re-order candidate lines by relevance to `query`.

    Tier 1: the cached cross-encoder probed during `warm()` (torch healthy
    machines only). Tier 2 (this env: broken torch): fastembed cosine
    similarity — the same embedder the comm store and vector legs use, so it
    is warm and cheap. Tier 3: no-op. Never raises; the hot path imports
    nothing heavy (the cross-encoder is probed once in warm(), never here).
    The caller enforces the per-leg time budget via `_safe`.
    """
    global _RERANK_EMBEDDER
    if not rerank_enabled() or len(lines) < RERANK_MIN_LINES:
        return lines

    # -- Tier 1: cached cross-encoder (probed in warm()) ---------------------
    model = _RERANK_MODEL
    if model:
        try:
            scores = await asyncio.to_thread(
                model.predict, [(query, ln) for ln in lines]
            )
            order = sorted(
                range(len(lines)),
                key=lambda i: scores[i],
                reverse=True,
            )
            return [lines[i] for i in order]
        except Exception as e:
            logger.debug(f"memory assembler: cross-encoder predict failed ({e}); "
                         f"trying fastembed cosine")

    # -- Tier 2: fastembed cosine similarity --------------------------------
    try:
        if _RERANK_EMBEDDER is None:
            from core.embedding_service import EmbeddingService

            _RERANK_EMBEDDER = EmbeddingService(provider="fastembed")
        import numpy as np

        vectors = await _RERANK_EMBEDDER.generate_embeddings_batch(
            [query[:500]] + lines
        )
        q = np.asarray(vectors[0], dtype=float)
        docs = np.asarray(vectors[1:], dtype=float)
        q_norm = float(np.linalg.norm(q))
        doc_norms = np.linalg.norm(docs, axis=1)
        sims = (docs @ q) / (doc_norms * q_norm + 1e-8)
        order = sorted(range(len(lines)), key=lambda i: sims[i], reverse=True)
        return [lines[i] for i in order]
    except Exception as e:
        logger.debug(f"memory assembler: fastembed rerank unavailable ({e}); no-op")
        return lines


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _bounded_lines(lines: List[str], cap: int) -> str:
    out: List[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > cap or not line:
            continue
        out.append(f"- {line}")
        used += cost
    return "\n".join(out)


async def _safe(aw, label: str, timeout: float = PER_LEG_TIMEOUT_SECONDS) -> Any:
    try:
        return await asyncio.wait_for(aw, timeout=timeout)
    except asyncio.TimeoutError:
        logger.info(f"memory assembler: {label} leg timed out")
        return None
    except Exception as e:
        logger.info(f"memory assembler: {label} leg failed: {e}")
        return None


async def warm(workspace_id: str = "default", tenant_id: str = "default") -> None:
    """Preload everything the legs need (embedding models, LanceDB tables,
    comms pipeline) so the first user-facing turn doesn't pay cold-start
    costs. Call once at app startup; generous timeout because model loads
    can take seconds. Never raises."""
    legs = (
        _knowledge_leg("warmup", workspace_id),
        _integration_records_leg("warmup", workspace_id),
        _facts_leg("warmup", workspace_id),
    )
    for coro in legs:
        try:
            await asyncio.wait_for(coro, timeout=45)
        except Exception as e:
            logger.debug(f"assembler warmup leg skipped: {e}")

    # Warm the rerank tiers: probe the cross-encoder once (heavy import only
    # here), then warm the fastembed embedder so the first rerank pass
    # doesn't pay a cold model load that would blow the per-leg budget.
    try:
        await asyncio.wait_for(_probe_cross_encoder(), timeout=45)
    except Exception as e:
        logger.debug(f"assembler cross-encoder probe skipped: {e}")
    try:
        await asyncio.wait_for(
            _rerank_lines("warmup", ["warmup a", "warmup b", "warmup c"]),
            timeout=45,
        )
    except Exception as e:
        logger.debug(f"assembler rerank warmup skipped: {e}")


async def assemble_memory_context(
    message: str,
    workspace_id: str = "default",
    tenant_id: str = "default",
    agent_id: str = "atom_main",
) -> Optional[str]:
    """Return a bounded `RELEVANT MEMORY` prompt block, or None if nothing
    relevant (or the flag is off). Never raises."""
    if not message or not message.strip():
        return None
    try:
        started = time.monotonic()
        # Round 80 role loop (recall half): the operating AI employee's role
        # scopes integration-record recall to the work/responsibilities the
        # data was synced for. Same tag the sync route stamps at ingest.
        agent_role = await asyncio.to_thread(_resolve_agent_role, agent_id)
        graph_ctx, knowledge_lines, integration_lines, episode_lines, fact_lines = await asyncio.gather(
            _safe(_graph_leg(message, workspace_id, tenant_id), "graph"),
            _safe(_knowledge_leg(message, workspace_id), "knowledge"),
            _safe(_integration_records_leg(message, workspace_id, agent_role), "integration_records"),
            _safe(_episodes_leg(message, agent_id), "episodes"),
            _safe(_facts_leg(message, workspace_id), "facts"),
        )

        # P1.4 rerank phase — budget-gated: only when the gather stayed fast
        # enough to leave room under the 800ms plan budget. Each leg is
        # re-ordered by relevance so the per-block caps keep the best lines,
        # not the first N the store returned. Stop the phase once budget is
        # exhausted (a slow or absent reranker degrades to current order).
        gather_elapsed_ms = (time.monotonic() - started) * 1000
        if rerank_enabled() and gather_elapsed_ms < RERANK_BUDGET_MS:
            legs_to_rerank = (
                ("knowledge", knowledge_lines),
                ("integration_records", integration_lines),
                ("episodes", episode_lines),
                ("facts", fact_lines),
            )
            for label, lines in legs_to_rerank:
                if not lines:
                    continue
                reranked = await _safe(
                    _rerank_lines(message, lines),
                    f"rerank:{label}",
                    timeout=RERANK_LEG_TIMEOUT_SECONDS,
                )
                if isinstance(reranked, list):
                    if label == "knowledge":
                        knowledge_lines = reranked
                    elif label == "integration_records":
                        integration_lines = reranked
                    elif label == "episodes":
                        episode_lines = reranked
                    else:
                        fact_lines = reranked
                if (time.monotonic() - started) * 1000 >= (
                    RERANK_BUDGET_MS + RERANK_LEG_TIMEOUT_SECONDS * 1000
                ):
                    break

        blocks: List[str] = []
        if graph_ctx:
            blocks.append("KNOWLEDGE GRAPH CONTEXT:\n" + graph_ctx)
        knowledge_block = _bounded_lines(knowledge_lines or [], KNOWLEDGE_CHAR_CAP)
        if knowledge_block:
            blocks.append("RELATED KNOWLEDGE & CONVERSATIONS (docs + email/chat):\n" + knowledge_block)
        integration_block = _bounded_lines(integration_lines or [], KNOWLEDGE_CHAR_CAP)
        if integration_block:
            blocks.append("RELATED INTEGRATION RECORDS (CRM/shop/files ingested):\n" + integration_block)
        episodes_block = _bounded_lines(episode_lines or [], EPISODES_CHAR_CAP)
        if episodes_block:
            blocks.append("RELEVANT PAST EPISODES (prior agent work):\n" + episodes_block)
        facts_block = _bounded_lines(fact_lines or [], FACTS_CHAR_CAP)
        if facts_block:
            blocks.append("DURABLE FACTS (previously learned):\n" + facts_block)

        if not blocks:
            return None

        body = "\n\n".join(blocks)
        if len(body) > TOTAL_CHAR_BUDGET:
            body = body[:TOTAL_CHAR_BUDGET] + "…"
        return (
            "RELEVANT MEMORY (auto-retrieved; may be incomplete — verify before "
            "acting on specifics):\n\n" + body
        )
    except Exception as e:
        logger.info(f"memory assembler: assembly failed cleanly: {e}")
        return None
