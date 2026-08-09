"""Mini-app DB store — host-mediated, per-instance record store.

Runtime-agnostic service behind ALL three data-layer surfaces:

* microVM logic (``record_ops`` envelope — host-validated, host-executed),
* agent actions (``mini_app_db_query`` / ``mini_app_db_write``),
* integration/workflow/UI API routes (``/api/mini-apps/instances/{id}/records``).

Locked decisions:

  * Rows are scoped by ``canvas_id`` (+ ``tenant_id``/``app_id``) — the
    caller passes them from host context (the canvas row), never from an op
    payload; cross-instance access is structurally impossible.
  * ``series`` is a logical, app-defined namespace; ``seq`` is a monotonic
    counter per (canvas, series) giving append order.
  * v1 filter semantics: host-side Python equality matching over ``data``
    (portable SQLite/PG), bounded by ``max_records_per_series``.
  * No ``str(e)`` leakage — app-visible errors are structured
    ``{"ok": False, "error": code}``; details go to logs.
  * ``ATOM_MINIAPP_DB_ENABLED`` kill switch (default on).
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SERIES_RE = re.compile(r"^[a-z0-9_]{1,64}$")

DEFAULT_MAX_RECORDS_PER_SERIES = 10_000
DEFAULT_MAX_RECORD_BYTES = 100 * 1024  # 100 KiB serialized JSON
DEFAULT_QUERY_LIMIT = 100
MAX_QUERY_LIMIT = 10_000

_ORDER_VALUES = {"asc", "desc"}


def db_store_enabled() -> bool:
    """Kill switch: ``ATOM_MINIAPP_DB_ENABLED`` (default on)."""
    return os.getenv("ATOM_MINIAPP_DB_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def validate_series(series: Any) -> Optional[str]:
    """Return the normalized series name or None when invalid."""
    if not isinstance(series, str):
        return None
    m = SERIES_RE.fullmatch(series)
    return m.group(0) if m else None


def validate_record_data(data: Any, max_bytes: int) -> bool:
    """A record payload must be a JSON-serializable dict within the size cap."""
    if not isinstance(data, dict):
        return False
    try:
        size = len(json.dumps(data).encode("utf-8"))
    except (TypeError, ValueError):
        return False
    return size <= max_bytes


def validate_filter(f: Any) -> bool:
    """A query filter must be a dict of scalar values (equality matching)."""
    if not isinstance(f, dict):
        return False
    for k, v in f.items():
        if not isinstance(k, str) or not k:
            return False
        if v is not None and not isinstance(v, (str, int, float, bool)):
            return False
    return True


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "series": row.series,
        "seq": int(row.seq or 0),
        "data": row.data or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _matches(data: Dict[str, Any], f: Dict[str, Any]) -> bool:
    return all(data.get(k) == v for k, v in f.items())


# ---------------------------------------------------------------------------
# CRUD primitives (all scoped by canvas_id; tenant_id for row creation)
# ---------------------------------------------------------------------------
def append_record(
    db: Session,
    canvas_id: str,
    tenant_id: str,
    app_id: str,
    series: str,
    data: Dict[str, Any],
    record_id: Optional[str] = None,
    created_by: Optional[str] = None,
    *,
    max_records: Optional[int] = None,
) -> Dict[str, Any]:
    """Append one record; ``seq`` = max(seq)+1 within (canvas, series).

    Enforces the per-series row cap (``max_records``, defaulting to
    ``DEFAULT_MAX_RECORDS_PER_SERIES``): once a (canvas, series) holds
    ``max_records`` rows, further appends raise ``ValueError`` and nothing is
    inserted — fail-closed, so runaway app logic / agents cannot grow the
    record store without bound.
    """
    from sqlalchemy import func

    from core.models import CanvasRecord

    cap = DEFAULT_MAX_RECORDS_PER_SERIES if max_records is None else max_records
    if cap > 0:
        existing = (
            db.query(CanvasRecord.id)
            .filter(CanvasRecord.canvas_id == canvas_id, CanvasRecord.series == series)
            .count()
        )
        if existing >= cap:
            raise ValueError(
                f"series record cap reached ({cap} rows for {series!r}); append rejected"
            )

    max_seq = (
        db.query(func.max(CanvasRecord.seq))
        .filter(CanvasRecord.canvas_id == canvas_id, CanvasRecord.series == series)
        .scalar()
    )
    row = CanvasRecord(
        id=record_id or str(uuid.uuid4()),
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        app_id=app_id,
        created_by=created_by,
        series=series,
        seq=int(max_seq or 0) + 1,
        data=data,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)


def get_record(db: Session, canvas_id: str, series: str, record_id: str) -> Optional[Dict[str, Any]]:
    from core.models import CanvasRecord

    row = (
        db.query(CanvasRecord)
        .filter(
            CanvasRecord.canvas_id == canvas_id,
            CanvasRecord.series == series,
            CanvasRecord.id == record_id,
        )
        .first()
    )
    return _row_to_dict(row) if row is not None else None


def query_records(
    db: Session,
    canvas_id: str,
    series: str,
    f: Optional[Dict[str, Any]] = None,
    limit: int = DEFAULT_QUERY_LIMIT,
    order: str = "desc",
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Rows for a series, ordered by ``seq``, latest-first by default."""
    from sqlalchemy import asc, desc

    from core.models import CanvasRecord

    q = db.query(CanvasRecord).filter(
        CanvasRecord.canvas_id == canvas_id, CanvasRecord.series == series
    )
    rows = q.all()
    filt = f or {}
    if filt:
        rows = [r for r in rows if _matches(r.data or {}, filt)]
    sort_key = lambda r: int(r.seq or 0)  # noqa: E731
    rows = sorted(rows, key=sort_key, reverse=(order == "desc"))
    limit = min(max(int(limit or 0), 0), MAX_QUERY_LIMIT)
    if offset:
        rows = rows[offset:]
    if limit:
        rows = rows[:limit]
    return [_row_to_dict(r) for r in rows]


def count_records(
    db: Session,
    canvas_id: str,
    series: Optional[str] = None,
    f: Optional[Dict[str, Any]] = None,
) -> int:
    from core.models import CanvasRecord

    q = db.query(CanvasRecord).filter(CanvasRecord.canvas_id == canvas_id)
    if series is not None:
        q = q.filter(CanvasRecord.series == series)
    rows = q.all()
    filt = f or {}
    if filt:
        rows = [r for r in rows if _matches(r.data or {}, filt)]
    return len(rows)


def update_record(
    db: Session,
    canvas_id: str,
    series: str,
    record_id: str,
    data: Dict[str, Any],
    *,
    max_bytes: int = DEFAULT_MAX_RECORD_BYTES,
) -> Optional[Dict[str, Any]]:
    """Deep-merge ``data`` into the record's payload; returns the row or None.

    The merged payload is re-validated against the per-record size cap before
    being written — a delta that is individually within ``max_bytes`` can push
    the merged record past it, which the incoming-only validation would miss.
    Raises ``ValueError`` when the merged payload exceeds the cap (row left
    untouched).
    """
    from core.models import CanvasRecord

    row = (
        db.query(CanvasRecord)
        .filter(
            CanvasRecord.canvas_id == canvas_id,
            CanvasRecord.series == series,
            CanvasRecord.id == record_id,
        )
        .first()
    )
    if row is None:
        return None
    merged = dict(row.data or {})
    merged.update(data)
    if not validate_record_data(merged, max_bytes):
        raise ValueError(
            "merged record data exceeds the size cap; update rejected"
        )
    row.data = merged
    db.commit()
    return _row_to_dict(row)


def update_many_records(
    db: Session,
    canvas_id: str,
    series: str,
    f: Dict[str, Any],
    data: Dict[str, Any],
    *,
    max_bytes: int = DEFAULT_MAX_RECORD_BYTES,
) -> int:
    """Merge ``data`` into every matching row; returns the number updated.

    All matching rows are validated BEFORE any is mutated: if any merged
    payload would exceed the per-record size cap, ``ValueError`` is raised and
    no row is written (no partial application).
    """
    from core.models import CanvasRecord

    rows = (
        db.query(CanvasRecord)
        .filter(CanvasRecord.canvas_id == canvas_id, CanvasRecord.series == series)
        .all()
    )
    if f:
        rows = [r for r in rows if _matches(r.data or {}, f)]
    for r in rows:
        merged = dict(r.data or {})
        merged.update(data)
        if not validate_record_data(merged, max_bytes):
            raise ValueError(
                "merged record data exceeds the size cap; update_many rejected"
            )
    for r in rows:
        merged = dict(r.data or {})
        merged.update(data)
        r.data = merged
    if rows:
        db.commit()
    return len(rows)


def delete_record(db: Session, canvas_id: str, series: str, record_id: str) -> bool:
    from core.models import CanvasRecord

    row = (
        db.query(CanvasRecord)
        .filter(
            CanvasRecord.canvas_id == canvas_id,
            CanvasRecord.series == series,
            CanvasRecord.id == record_id,
        )
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def delete_series(db: Session, canvas_id: str, series: str) -> int:
    """Delete every row of one series; returns the deleted count."""
    from core.models import CanvasRecord

    rows = (
        db.query(CanvasRecord)
        .filter(CanvasRecord.canvas_id == canvas_id, CanvasRecord.series == series)
        .all()
    )
    for r in rows:
        db.delete(r)
    if rows:
        db.commit()
    return len(rows)


def clear_records(db: Session, canvas_id: str) -> int:
    """Delete every record of an instance canvas; returns the deleted count."""
    from core.models import CanvasRecord

    rows = db.query(CanvasRecord).filter(CanvasRecord.canvas_id == canvas_id).all()
    for r in rows:
        db.delete(r)
    if rows:
        db.commit()
    return len(rows)


def list_series(db: Session, canvas_id: str) -> List[Dict[str, Any]]:
    """Distinct series names + record counts for an instance."""
    from sqlalchemy import func

    from core.models import CanvasRecord

    out: Dict[str, int] = {}
    for (series,) in (
        db.query(CanvasRecord.series)
        .filter(CanvasRecord.canvas_id == canvas_id)
        .distinct()
        .all()
    ):
        out[series] = count_records(db, canvas_id, series=series)
    return [{"series": s, "count": c} for s, c in sorted(out.items())]
