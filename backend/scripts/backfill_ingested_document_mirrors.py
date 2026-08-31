#!/usr/bin/env python3
"""Create PG IngestedDocument mirror rows for vector-only LanceDB documents.

The Aug 2026 journey trace found the Knowledge VFS listing only PG rows while
the LanceDB ``documents`` table held dozens of connector ingests
(process_file_bytes wrote vector rows but no PG mirror). Writer-side parity
now exists (auto_document_ingestion._mirror_pg_row); this script heals stores
written before that fix.

For every LanceDB documents row whose id has no PG IngestedDocument row, a
mirror row is created with id == the vector id (join-key bridge): hybrid
search flips to bridged:true, and the Knowledge VFS ls/grep/cat serve it as a
first-class document.

Usage:
  PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m scripts.backfill_ingested_document_mirrors
  # optional: --dry-run to only report, --workspace to override workspace_id
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_ingested_document_mirrors")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only, no writes")
    parser.add_argument(
        "--workspace",
        default="default",
        help="workspace_id stamped on created rows (default: 'default')",
    )
    args = parser.parse_args()

    try:
        from core.database import SessionLocal
        from core.lancedb_handler import get_lancedb_handler
        from core.models import IngestedDocument
    except Exception as e:
        logger.error("Failed to import backend modules (run from repo root): %s", e)
        return 1

    handler = get_lancedb_handler(args.workspace)
    if handler is None:
        logger.error("No LanceDB handler available")
        return 1

    heads = handler.list_document_heads("documents", limit=10000)
    if not heads:
        logger.warning("No rows in the 'documents' table — nothing to backfill")
        return 0

    stats = {"total": len(heads), "already_bridged": 0, "created": 0, "failed": 0}
    session = SessionLocal()
    try:
        for head in heads:
            doc_id = str(head.get("id") or "")
            if not doc_id:
                stats["failed"] += 1
                continue
            metadata = head.get("metadata") or {}

            if session.query(IngestedDocument).filter(IngestedDocument.id == doc_id).first():
                stats["already_bridged"] += 1
                continue

            # Full doc: content_preview feeds the FTS lexical leg, so the
            # mirror must carry real text, not a null preview.
            full = handler.get_document_by_id("documents", doc_id) or {}
            text = str(full.get("text") or "")

            file_name = str(
                metadata.get("file_name") or metadata.get("title") or doc_id
            )
            file_ext = str(metadata.get("file_type") or "").strip()
            if not file_ext and "." in file_name:
                file_ext = file_name.rsplit(".", 1)[-1].lower()
            source = str(metadata.get("integration_id") or "").strip()
            if not source:
                # e.g. "zoho_workdrive:<file>" / "upload:<file>" source column
                source = str(head.get("source") or "unknown").split(":", 1)[0]

            row = IngestedDocument(
                id=doc_id,
                workspace_id=args.workspace,
                file_name=file_name,
                file_path=str(head.get("source") or f"{source}:{file_name}"),
                file_type=file_ext or "bin",
                integration_id=source or "unknown",
                file_size_bytes=int(metadata.get("file_size") or 0),
                content_preview=text[:500],
                external_id=str(metadata.get("external_id") or f"vector:{doc_id}"),
                ingested_at=datetime.now(timezone.utc),
                last_verified_at=datetime.now(timezone.utc),
                source_content_hash=metadata.get("source_content_hash"),
                freshness_status=str(metadata.get("freshness_status") or "fresh"),
                sensitivity=str(metadata.get("sensitivity") or "internal"),
                role=str(metadata["role"]) if metadata.get("role") else None,
            )
            if args.dry_run:
                stats["created"] += 1
                logger.info("[dry-run] would create mirror for %s (%s)", doc_id, file_name)
                continue
            try:
                session.add(row)
                session.commit()
                stats["created"] += 1
            except Exception as e:
                session.rollback()
                stats["failed"] += 1
                logger.error("mirror row failed for %s: %s", doc_id, e)
    finally:
        session.close()

    logger.info("Backfill summary: %s", json.dumps(stats))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
