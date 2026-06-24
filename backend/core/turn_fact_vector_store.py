"""
Turn Fact Vector Store — LanceDB-backed Tier-2 recall for durable facts.

Design:
  - SQL row (TurnFact) is the source of truth; this module is best-effort.
  - Uses the existing embedded LanceDBHandler (file-based `./data/atom_memory`
    by default; no server container — Personal Edition).
  - Writes use `add_document(doc_id=TurnFact.id, ...)` so hydration is a single
    SQL lookup by primary key.
  - All public functions swallow exceptions — LanceDB corruption must never
    block SQL success or break /health/ready.

Table is created lazily via LanceDBHandler.add_document on first write
(inferring schema from data), consistent with how the rest of Atom uses it.
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from core.models import TurnFact

logger = logging.getLogger(__name__)

_TABLE_NAME = "turn_facts"


def _get_handler():
    """Lazy import to avoid circular deps; returns LanceDBHandler or None."""
    try:
        from core.lancedb_handler import LanceDBHandler

        return LanceDBHandler()
    except Exception as e:
        logger.debug("turn_fact vector store: LanceDB unavailable (%s)", e)
        return None


def write_turn_fact_vectors(*, rows: List[TurnFact], source_text: str = "") -> int:
    """
    Write fact vectors to LanceDB. Best-effort — returns count written.
    Never raises.
    """
    handler = _get_handler()
    if handler is None:
        return 0

    written = 0
    for row in rows:
        try:
            ok = handler.add_document(
                table_name=_TABLE_NAME,
                text=row.fact_text,
                source=f"turn_fact:{row.category}",
                metadata={
                    "category": row.category,
                    "domain": row.domain,
                    "confidence": row.confidence,
                    "content_hash": row.content_hash,
                    "extraction_source": row.extraction_source,
                },
                user_id=row.user_id or "turn_fact",
                workspace_id=row.workspace_id,
                doc_id=row.id,
                extract_knowledge=False,  # never trigger downstream AI from extraction
                skip_ai_triggers=True,
            )
            if ok:
                written += 1
        except Exception as e:
            logger.debug("turn_fact vector write skipped for %s: %s", row.id, e)

    return written


def search_relevant_fact_ids(
    *,
    workspace_id: str,
    query: str,
    limit: int = 5,
) -> List[str]:
    """
    Tier-2 recall. Embeds the query, searches LanceDB, returns TurnFact ids.
    Hydration is done by the caller via SQL. Returns [] on any failure.
    """
    handler = _get_handler()
    if handler is None or not query or len(query.strip()) < 3:
        return []

    try:
        results = handler.search(
            table_name=_TABLE_NAME,
            query=query,
            limit=limit,
        )
        if not results:
            return []

        ids: List[str] = []
        for r in results:
            rid = r.get("id") if isinstance(r, dict) else getattr(r, "id", None)
            if rid:
                ids.append(str(rid))
        return ids
    except Exception as e:
        logger.debug("turn_fact vector recall failed: %s", e)
        return []
