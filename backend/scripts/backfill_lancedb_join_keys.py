#!/usr/bin/env python3
"""Backfill join keys for pre-Step-1 LanceDB document rows.

Hybrid search Step 1 stamps metadata.pg_document_id + source_type at ingest
time, so vector hits resolve to documents.cat paths. This one-shot script
closes the gap for rows written BEFORE that bridge existed.

Two heuristic legs (per the hybrid-search plan critique):
  1. external_id leg — adapter-ingested docs carry metadata.external_id
     (→ IngestedDocument.external_id). Highest confidence.
  2. file heuristic leg — file-ingested docs lack external_id; match by
     source + file_name + ingested_at window.

This script stamps metadata.pg_document_id (NOT an id-column rewrite —
LanceDB tables are append-only; rewriting the id would require a full table
rebuild). The hybrid service hydrates via metadata.pg_document_id when the
LanceDB id is a legacy timestamp.

Usage:
    cd backend && venv/bin/python scripts/backfill_lancedb_join_keys.py [--dry-run]

Never raises on individual rows; logs a summary at the end.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_join_keys")

_MATCH_WINDOW_MINUTES = 5  # file-heuristic: ingested_at within this window of a PG row


def _get_lancedb():
    from core.lancedb_handler import get_lancedb_handler
    return get_lancedb_handler()


def _get_db():
    from core.database import SessionLocal
    return SessionLocal()


def _parse_metadata(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _match_by_external_id(db, external_id: str) -> Optional[str]:
    """Leg 1: find the IngestedDocument.id by external_id."""
    if not external_id:
        return None
    try:
        from core.models import IngestedDocument
        row = db.query(IngestedDocument).filter(
            IngestedDocument.external_id == external_id
        ).first()
        return row.id if row else None
    except Exception:
        return None


def _match_by_file_heuristic(db, source: str, file_name: str, ingested_at: str) -> Optional[str]:
    """Leg 2: match file-ingested docs by source + file_name + time window."""
    if not file_name:
        return None
    try:
        from core.models import IngestedDocument
        q = db.query(IngestedDocument).filter(IngestedDocument.file_name == file_name)
        if ingested_at:
            try:
                ts = datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
                window = timedelta(minutes=_MATCH_WINDOW_MINUTES)
                q = q.filter(IngestedDocument.ingested_at.between(ts - window, ts + window))
            except Exception:
                pass
        row = q.first()
        return row.id if row else None
    except Exception:
        return None


def backfill(dry_run: bool = False) -> Dict[str, int]:
    stats = {"total": 0, "stamped": 0, "already_stamped": 0, "unmatched": 0, "errors": 0}
    handler = _get_lancedb()
    if handler is None:
        logger.error("LanceDB handler unavailable; nothing to backfill.")
        return stats

    table = handler.get_table("documents")
    if table is None:
        logger.info("documents table does not exist; nothing to backfill.")
        return stats

    try:
        rows = table.to_list()
    except Exception as e:
        logger.error("failed to read documents table: %s", e)
        return stats

    db = _get_db()
    try:
        for row in rows:
            stats["total"] += 1
            meta = _parse_metadata(row.get("metadata"))
            if meta.get("pg_document_id") or meta.get("source_type"):
                stats["already_stamped"] += 1
                continue

            external_id = meta.get("external_id")
            file_name = meta.get("file_name")
            source = row.get("source", "")
            ingested_at = meta.get("ingested_at")

            pg_id = _match_by_external_id(db, external_id) or _match_by_file_heuristic(
                db, source, file_name, ingested_at
            )
            if pg_id:
                meta["pg_document_id"] = pg_id
                meta["source_type"] = "ingested" if external_id else "file"
                if not dry_run:
                    # LanceDB metadata is a JSON column; update via a new add
                    # with the same id (upsert). This is the stamp-only path —
                    # the id column is NOT rewritten.
                    row["metadata"] = json.dumps(meta)
                    try:
                        table.add([row])
                    except Exception as e:
                        logger.warning("stamp failed for row %s: %s", row.get("id"), e)
                        stats["errors"] += 1
                        continue
                stats["stamped"] += 1
                logger.info("stamped %s → pg_document_id=%s", row.get("id"), pg_id)
            else:
                stats["unmatched"] += 1
                logger.debug("unmatched row %s (source=%s, file=%s)", row.get("id"), source, file_name)
    finally:
        try:
            db.close()
        except Exception:
            pass

    logger.info(
        "backfill complete: %d total, %d stamped, %d already-stamped, %d unmatched, %d errors",
        stats["total"], stats["stamped"], stats["already_stamped"], stats["unmatched"], stats["errors"],
    )
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill LanceDB join keys for hybrid search")
    ap.add_argument("--dry-run", action="store_true", help="report what would be stamped without writing")
    args = ap.parse_args()
    result = backfill(dry_run=args.dry_run)
    sys.exit(0 if result["errors"] == 0 else 1)
