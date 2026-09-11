"""Dialect-portable JSON-column comparisons that tolerate corrupt rows.

Why this exists (live 2026-09-11): `GET /api/chat/trace/{session_id}` returned
500 for EVERY session, which broke the canvas Agent Workspace history restore.
Root cause was a single unrelated row: three `agent_executions` rows held
non-JSON in ``metadata_json`` — workflow_template rows that a one-off Aug-30
recovery INSERT had shifted one column into the executions table (``started_at``
= 1 was the template's ``is_public``; ``metadata_json`` held ``created_at``).

The column is a ``JSONColumn``: ``JSONB`` on PostgreSQL, which VALIDATES on
write (a malformed value cannot exist there), but plain JSON/TEXT on SQLite,
which does NOT. On SQLite, ``json_extract()`` raises ``malformed JSON`` for the
ENTIRE statement the moment it evaluates one bad row — so one corrupt row takes
down a read that has nothing to do with it. SQLite is the Personal-Edition
default, so this is the common case, not an exotic one.

``json_field_equals`` renders the comparison so that:

* SQLite evaluates ``json_extract`` ONLY for rows whose JSON is valid, and
* PostgreSQL keeps the plain comparison (no ``json_valid`` there, and it is
  unnecessary), so the same call site stays portable.

The CASE wrapper is deliberate: SQLite may reorder the terms of an ``AND`` in a
WHERE clause, so ``json_valid(col) = 1 AND json_extract(...) = v`` is NOT a
reliable guard. CASE evaluates its THEN branch only when the WHEN holds, which
is guaranteed.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import case, func

__all__ = ["is_sqlite", "json_field_equals"]


def is_sqlite(db: Any) -> bool:
    """True when this session talks to SQLite (the unvalidated-JSON case).

    Defensive: an unresolvable bind reports False, which keeps the plain
    (portable) comparison rather than emitting a SQLite-only function.
    """
    try:
        bind = db.get_bind()
    except Exception:  # noqa: BLE001 — dialect probing must never break a read
        return False
    return bind is not None and getattr(bind.dialect, "name", None) == "sqlite"


def json_field_equals(db: Any, column: Any, path: str, value: Any):
    """``column -> path == value`` as a portable SQL expression.

    On SQLite, malformed rows are skipped instead of aborting the statement
    with ``malformed JSON``. Use this anywhere a ``metadata_json``-style
    ``JSONColumn`` is compared in SQL — the same landmine exists for every
    such column on SQLite.
    """
    extracted = func.json_extract(column, path)
    if is_sqlite(db):
        extracted = case(
            (func.json_valid(column) == 1, extracted), else_=None
        )
    return extracted == value
