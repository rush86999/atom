"""Backfill matcher: stamp join keys into legacy LanceDB documents rows.

The matcher logic is pure (testable); the script itself (backfill_lancedb_join_keys.py)
iterates the LanceDB table and applies it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def match_pg_row(
    db: Session,
    metadata: Dict[str, Any],
    lancedb_id: str,
) -> Optional[str]:
    """Resolve a LanceDB documents row to a PG IngestedDocument id.

    Leg 1 (adapter-ingested): ``metadata.external_id`` matches
    ``IngestedDocument.external_id`` — exact join.
    Leg 2 (file-ingested): ``metadata.file_name`` + ``integration_id`` heuristic —
    best-effort, lowest-id wins on ties.
    Returns the PG id or None (row stays unbridged).
    """
    from core.models import IngestedDocument

    external_id = metadata.get("external_id")
    if external_id:
        row = (
            db.query(IngestedDocument)
            .filter(IngestedDocument.external_id == external_id)
            .order_by(IngestedDocument.created_at.asc())
            .first()
        )
        if row is not None:
            return row.id

    file_name = metadata.get("file_name")
    if file_name:
        integration_id = metadata.get("integration_id")
        q = db.query(IngestedDocument).filter(IngestedDocument.file_name == file_name)
        if integration_id:
            q = q.filter(IngestedDocument.integration_id == integration_id)
        q = q.order_by(IngestedDocument.created_at.asc())
        row = q.first()
        if row is not None:
            return row.id

    return None
