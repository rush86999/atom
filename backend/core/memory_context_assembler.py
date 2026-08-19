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


def assembly_enabled() -> bool:
    return os.getenv(ENV_FLAG, "true").lower() in ("1", "true", "yes", "on")


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


async def _integration_records_leg(message: str, workspace_id: str) -> List[str]:
    """Vector search over ALL ingested 3rd-party integration data
    (`integration_*` LanceDB tables written by the hybrid sync pipeline —
    Zoho, Shopify, Salesforce, OneDrive, Drive, …). Previously these tables
    were write-only; this leg makes every integration's ingested records
    retrievable at turn time. Runs in a thread (sync LanceDB I/O)."""

    def _search() -> List[str]:
        from core.lancedb_handler import get_lancedb_handler

        try:
            handler = get_lancedb_handler(workspace_id)
            if handler is None or handler.db is None or handler.db.db is None:
                return []
            tables = [
                t for t in handler.db.db.table_names() if str(t).startswith("integration_")
            ]
        except Exception as e:
            logger.debug(f"integration records leg: table list failed: {e}")
            return []
        lines: List[str] = []
        for table_name in tables[:6]:  # bounded: newest common integrations
            try:
                results = handler.search(table_name, message[:500], limit=2)
            except Exception:
                continue
            for rec in results or []:
                text = str(rec.get("text") or rec.get("content") or "").strip()
                if not text:
                    continue
                source = str(rec.get("source") or table_name.replace("integration_", ""))
                if len(text) > SNIPPET_CHAR_CAP:
                    text = text[:SNIPPET_CHAR_CAP] + "…"
                lines.append(f"[{source}] " + text.replace("\n", " "))
        return lines

    return await asyncio.to_thread(_search)


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


async def _safe(aw, label: str) -> Any:
    try:
        return await asyncio.wait_for(aw, timeout=PER_LEG_TIMEOUT_SECONDS)
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
        graph_ctx, knowledge_lines, integration_lines, episode_lines, fact_lines = await asyncio.gather(
            _safe(_graph_leg(message, workspace_id, tenant_id), "graph"),
            _safe(_knowledge_leg(message, workspace_id), "knowledge"),
            _safe(_integration_records_leg(message, workspace_id), "integration_records"),
            _safe(_episodes_leg(message, agent_id), "episodes"),
            _safe(_facts_leg(message, workspace_id), "facts"),
        )

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
