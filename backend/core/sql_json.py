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
* PostgreSQL uses ``json_extract_path_text`` (JSONB-native; there is no
  ``json_extract`` function there — the old code emitted SQLite-only SQL
  that would fail at execution on PG), so the same call site stays
  portable.

The CASE wrapper is deliberate: SQLite may reorder the terms of an ``OR``/
``AND`` in a WHERE clause, so ``json_valid(col) = 1 AND json_extract(...) = v``
is NOT a reliable guard. CASE evaluates its THEN branch only when the WHEN
holds, which is guaranteed.

Path forms accepted: the SQLite ``$.a.b`` JSON-path (and a bare ``$.key``).
The PG branch rewrites that to the key sequence for
``json_extract_path_text``; array-index paths (``$.items[0]``) are
SQLite-only and raise ``NotImplementedError`` on the PG branch rather than
silently comparing the wrong thing. Any dialect other than sqlite/
postgresql (or an unresolvable bind, which historically emitted the
SQLite-only form as a "portable" fallback) now raises — an honest failure
at call time beats a dialect error at execution time.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import case, func

__all__ = ["is_sqlite", "is_postgres", "json_field_equals"]


def is_sqlite(db: Any) -> bool:
    """True when this session talks to SQLite (the unvalidated-JSON case).

    Defensive: an unresolvable bind reports False.
    """
    try:
        bind = db.get_bind()
    except Exception:  # noqa: BLE001 — dialect probing must never break a read
        return False
    return bind is not None and getattr(bind.dialect, "name", None) == "sqlite"


def is_postgres(db: Any) -> bool:
    """True when this session talks to PostgreSQL (JSONB — validated on
    write, addressed with ``json_extract_path_text``)."""
    try:
        bind = db.get_bind()
    except Exception:  # noqa: BLE001
        return False
    return bind is not None and getattr(bind.dialect, "name", None) == "postgresql"


def _json_path_keys(path: str) -> list:
    """``$.a.b`` → ``['a', 'b']`` for PostgreSQL path functions. Rejects
    array indexes / wildcards / non-``$.`` forms — those have no equivalent
    here and must not silently compare the wrong thing."""
    text = str(path or "").strip()
    if not text.startswith("$") or any(ch in text for ch in ("[", "*", "..")):
        raise NotImplementedError(
            f"json_field_equals: JSON path {path!r} uses array indexes or "
            f"wildcards, which the PostgreSQL branch does not support — "
            f"address the key with dot notation ('$.a.b')")
    keys = [k.strip('"') for k in text.lstrip("$").split(".") if k.strip('"')]
    if not keys:
        raise NotImplementedError(
            f"json_field_equals: unsupported JSON path {path!r}")
    return keys


def json_field_equals(db: Any, column: Any, path: str, value: Any):
    """``column -> path == value`` as a portable SQL expression.

    * SQLite: malformed rows are skipped instead of aborting the statement
      with ``malformed JSON`` (CASE-guarded ``json_extract``).
    * PostgreSQL: ``json_extract_path_text(column, 'a', 'b') = value``
      (JSONB-native; no ``json_extract`` function exists there).
    * Anything else (or a path the dialect cannot express): raises
      ``NotImplementedError`` — never emits SQL that only compiles.

    Use this anywhere a ``metadata_json``-style ``JSONColumn`` is compared
    in SQL — the same landmine exists for every such column on SQLite.
    """
    if is_sqlite(db):
        extracted = func.json_extract(column, path)
        return case(
            (func.json_valid(column) == 1, extracted), else_=None
        ) == value
    if is_postgres(db):
        return func.json_extract_path_text(
            column, *_json_path_keys(path)) == value
    dialect_name = None
    try:
        bind = db.get_bind()
        dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
    except Exception:  # noqa: BLE001
        pass
    raise NotImplementedError(
        f"json_field_equals: no JSON-comparison form for dialect "
        f"{dialect_name or 'unknown'!r} (supported: sqlite, postgresql)")
