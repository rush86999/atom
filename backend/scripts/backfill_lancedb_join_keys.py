#!/usr/bin/env python3
"""Backfill join keys into legacy LanceDB documents rows (hybrid search Step 5).

Rows written before the Step-1 bridge (LanceDB id == PG IngestedDocument.id) have
timestamp ids and no pg_document_id stamp. This script stamps metadata so the
hybrid search service can hydrate them (or leave them bridged:false).

Legs (see core/hybrid_search/backfill_matcher.py):
  1. external_id exact join (adapter-ingested docs)
  2. file_name + integration_id heuristic, earliest created_at wins (file-ingested docs)

Usage:
  PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m scripts.backfill_lancedb_join_keys
  # optional: --dry-run to only report

Does NOT rewrite the LanceDB id column (id rewriting would corrupt vector rows);
hydrate via metadata.pg_document_id instead.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_lancedb_join_keys")


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only, no writes")
    args = parser.parse_args()

    try:
        from core.database import get_db_session
        from core.lancedb_handler import get_lancedb_handler
        from core.hybrid_search.backfill_matcher import match_pg_row
    except Exception as e:
        logger.error("Failed to import backend modules (run from repo root): %s", e)
        return 1

    handler = get_lancedb_handler("default")
    if handler is None:
        logger.error("No LanceDB handler available")
        return 1

    table = handler.get_table("documents")
    if table is None:
        logger.warning("No 'documents' table — nothing to backfill")
        return 0

    rows = table.to_pandas().to_dict("records") if hasattr(table, "to_pandas") else table.to_arrow().to_pylist()

    stats = {"total": len(rows), "already_bridged": 0, "external_id_leg": 0, "file_leg": 0, "unbridged": 0, "updated": 0}
    updated: list[str] = []

    with get_db_session() as db:
        for row in rows:
            doc_id = str(row.get("id") or "")
            raw_meta = row.get("metadata") or {}
            try:
                metadata = json.loads(raw_meta) if isinstance(raw_meta, str) else dict(raw_meta or {})
            except Exception:
                metadata = {}

            if metadata.get("pg_document_id"):
                stats["already_bridged"] += 1
                continue

            pg_id = match_pg_row(db, metadata, doc_id)
            if pg_id is None:
                stats["unbridged"] += 1
                logger.info("[unbridged] %s (metadata: %s)", doc_id, list(metadata.keys()))
                continue

            leg = "external_id_leg" if metadata.get("external_id") else "file_leg"
            stats[leg] += 1
            metadata["pg_document_id"] = pg_id
            metadata.setdefault("source_type", "ingested")
            if args.dry_run:
                logger.info("[dry-run] %s -> %s (%s)", doc_id, pg_id, leg)
                continue
            try:
                table.update(
                    where=f"id = '{_escape_sql_literal(doc_id)}'",
                    values={"metadata": json.dumps(metadata)},
                )
                stats["updated"] += 1
                updated.append(doc_id)
            except Exception as e:
                logger.error("update failed for %s: %s", doc_id, e)

    logger.info("Backfill summary: %s", json.dumps(stats))
    if updated:
        logger.info("Updated %d rows", len(updated))
    return 0


if __name__ == "__main__":
    sys.exit(main())
