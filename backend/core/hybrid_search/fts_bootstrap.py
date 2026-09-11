"""Self-provisioning BM25/FTS index for ``documents.search``.

Why this module exists
----------------------
`documents.search` is a *hybrid* search: an FTS5/tsvector lexical leg fused with
a LanceDB vector leg by RRF (see ``docs/architecture/AGENT_HYBRID_SEARCH.md``).
The lexical leg depends on virtual tables (``ingested_documents_fts``,
``knowledge_documents_fts``) created by the ``20260808_add_documents_fts``
migration.

Migrations are not a reliable provisioning mechanism for this app's local
(SQLite, single-tenant, file-first) deployments. Observed 2026-09-11: the dev DB
had **zero** FTS tables and **zero** triggers, because the alembic CLI is
blocked on it (batch-mode FK crash + broken revision chain, round 71). The
lexical leg then fell through to an ILIKE scan over ``content_preview`` — and
``ingested_documents`` has no full-content column at all — so every query
reported ``lexical_hits: 0`` and hybrid search silently degraded to
``semantic_only``. Retrieval still *appeared* to work (the vector leg carried
it), which is exactly why this rotted invisibly.

The house convention for deployment-independent schema is self-provisioning at
first use: see the trust-calibration gateway's per-engine ``_ensure_table``
(CLAUDE.md #81p) and ``RuntimeSetting``/``OntologyDraftAction``. This module
applies that convention to the search index: idempotent, dialect-aware,
callable from both startup and the search path, and **never raising** — a
missing index must degrade search quality, never break search or boot.

Both entry points matter: startup provisioning keeps the index warm, while the
search-path call heals an index that appears later (new DB file, restored
backup, a row inserted before boot finished).
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# fts_table -> (base_table, columns)
_FTS_SPECS: Dict[str, Tuple[str, Sequence[str]]] = {
    "ingested_documents_fts": ("ingested_documents", ("file_name", "content_preview")),
    "knowledge_documents_fts": ("knowledge_documents", ("title", "content")),
}

# PG twin: base_table -> columns folded into the generated tsvector.
_PG_VECTOR_COLUMNS: Dict[str, Sequence[str]] = {
    "ingested_documents": ("file_name", "content_preview"),
    "knowledge_documents": ("title", "content"),
}

_ENSURED: set = set()
_LOCK = threading.Lock()


def reset_bootstrap_cache() -> None:
    """Clear the fast-path cache (tests, and after a DB swap)."""
    with _LOCK:
        _ENSURED.clear()


def _cache_key(bind: Any) -> str:
    try:
        url = getattr(bind, "url", None)
        return f"{getattr(bind.dialect, 'name', '?')}::{url}"
    except Exception:  # pragma: no cover - defensive
        return f"unknown::{id(bind)}"


def _dialect_name(bind: Any) -> Optional[str]:
    try:
        return bind.dialect.name
    except Exception:
        return None


def _table_exists(conn: Any, table: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).first()
    return row is not None


def _trigger_exists(conn: Any, name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
    ).first()
    return row is not None


def _column_names(conn: Any, table: str) -> List[str]:
    try:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return [r[1] for r in rows]
    except Exception:
        return []


def _create_triggers(conn: Any, fts: str, base: str, columns: Sequence[str]) -> None:
    """Create the INSERT/UPDATE/DELETE sync triggers for an external-content FTS5 table.

    Column references MUST be ``new.``/``old.`` qualified. SQLite does not
    resolve bare column names inside a trigger body, so the ``COALESCE(col,'')``
    form used by the original ``20260808_add_documents_fts`` migration raised
    ``no such column: file_name`` on every write to the base table. Because the
    trigger fires on INSERT, that bug would have broken document ingestion
    outright on any deployment where the migration ran; it stayed latent here
    only because the FTS tables were never provisioned at all. Verified against
    sqlite3: qualified SQL indexes inserts, refreshes updates, and drops deletes.
    """
    cols = ", ".join(columns)
    new_sql = ", ".join(f"COALESCE(new.{c},'')" for c in columns)
    old_sql = ", ".join(f"COALESCE(old.{c},'')" for c in columns)
    ddl = (
        (
            f"{fts}_ai",
            f"CREATE TRIGGER IF NOT EXISTS {fts}_ai AFTER INSERT ON {base} BEGIN "
            f"INSERT INTO {fts}(rowid, {cols}) VALUES (new.rowid, {new_sql}); END",
        ),
        (
            f"{fts}_ad",
            f"CREATE TRIGGER IF NOT EXISTS {fts}_ad AFTER DELETE ON {base} BEGIN "
            f"INSERT INTO {fts}({fts}, rowid, {cols}) VALUES('delete', old.rowid, {old_sql}); END",
        ),
        (
            f"{fts}_au",
            f"CREATE TRIGGER IF NOT EXISTS {fts}_au AFTER UPDATE ON {base} BEGIN "
            f"INSERT INTO {fts}({fts}, rowid, {cols}) VALUES('delete', old.rowid, {old_sql}); "
            f"INSERT INTO {fts}(rowid, {cols}) VALUES (new.rowid, {new_sql}); END",
        ),
    )
    for _name, stmt in ddl:
        conn.exec_driver_sql(stmt)


def _backfill(conn: Any, fts: str, base: str, columns: Sequence[str]) -> int:
    cols = ", ".join(columns)
    col_sql = ", ".join(f"COALESCE({c},'')" for c in columns)
    result = conn.exec_driver_sql(
        f"INSERT INTO {fts}(rowid, {cols}) SELECT rowid, {col_sql} FROM {base}"
    )
    try:
        return int(result.rowcount or 0)
    except Exception:  # pragma: no cover - defensive
        return 0


def _sqlite_fts_row_count(conn: Any, fts: str) -> int:
    """Number of rows actually *indexed* in an FTS5 table.

    Do NOT use ``SELECT COUNT(*) FROM <fts>``: for an external-content table
    (``content='base'``) the FTS5 table stores nothing itself and such a query
    is proxied to the content table, so it reports the base table's row count
    even when the index is completely empty — verified against sqlite3, where
    COUNT(*) returned 1 both before and after backfill. The ``_docsize`` shadow
    table reflects the true index contents (0 when empty, n after backfill).
    """
    try:
        row = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {fts}_docsize").first()
        return int(row[0]) if row else 0
    except Exception:
        # Shadow table absent (unexpected schema): fall back to COUNT(*), which
        # at worst suppresses the repair path rather than corrupting the index.
        try:
            row = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {fts}").first()
            return int(row[0]) if row else 0
        except Exception:
            return 0


def _ensure_sqlite(conn: Any) -> bool:
    ok = True
    for fts, (base, columns) in _FTS_SPECS.items():
        if not _table_exists(conn, base):
            continue
        available = _column_names(conn, base)
        if not available:
            continue
        # Guard against schema drift: only index columns that actually exist.
        usable = [c for c in columns if c in available]
        if not usable:
            continue
        cols = ", ".join(usable)
        try:
            if not _table_exists(conn, fts):
                conn.exec_driver_sql(
                    f"CREATE VIRTUAL TABLE {fts} USING fts5("
                    f"{cols}, content='{base}', content_rowid='rowid')"
                )
                _backfill(conn, fts, base, usable)
            elif _sqlite_fts_row_count(conn, fts) == 0:
                # Table exists but was never populated (partial/aborted provision).
                _backfill(conn, fts, base, usable)
            _create_triggers(conn, fts, base, usable)
        except Exception as e:
            logger.warning("FTS provisioning failed for %s: %s", fts, e)
            ok = False
    return ok


def _ensure_postgres(conn: Any) -> bool:
    ok = True
    for base, columns in _PG_VECTOR_COLUMNS.items():
        try:
            exists = conn.exec_driver_sql(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (base,),
            ).first()
            if not exists:
                continue
            expr = " || ' ' || ".join(f"coalesce({c},'')" for c in columns)
            conn.exec_driver_sql(
                f"ALTER TABLE {base} ADD COLUMN IF NOT EXISTS search_vector tsvector "
                f"GENERATED ALWAYS AS (to_tsvector('english', {expr})) STORED"
            )
            conn.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS ix_{base}_search "
                f"ON {base} USING gin(search_vector)"
            )
        except Exception as e:
            logger.warning("tsvector provisioning failed for %s: %s", base, e)
            ok = False
    return ok


def ensure_documents_fts(bind: Any) -> bool:
    """Idempotently provision the lexical index for ``documents.search``.

    Accepts an ``Engine`` or ``Connection`` (either is passed to the search
    path). Safe to call on every startup and from the search path: existence is
    re-checked, so repeat calls neither raise nor duplicate rows.

    Returns ``True`` when the index is provisioned (or already was), ``False``
    when provisioning was impossible. NEVER raises — callers treat ``False`` as
    "fall back to the degraded lexical path".
    """
    if bind is None:
        return False
    dialect = _dialect_name(bind)
    if dialect not in ("sqlite", "postgresql"):
        return False

    key = _cache_key(bind)
    with _LOCK:
        if key in _ENSURED:
            return True

    try:
        if hasattr(bind, "begin"):
            with bind.begin() as conn:
                ok = _ensure_sqlite(conn) if dialect == "sqlite" else _ensure_postgres(conn)
        else:
            ok = _ensure_sqlite(bind) if dialect == "sqlite" else _ensure_postgres(bind)
    except Exception as e:
        logger.warning("documents FTS bootstrap failed: %s", e)
        return False

    if ok:
        with _LOCK:
            _ENSURED.add(key)
    return ok


def ensure_documents_fts_for_session(db: Any) -> bool:
    """Convenience wrapper for ORM sessions; never raises."""
    try:
        return ensure_documents_fts(getattr(db, "bind", None))
    except Exception:
        return False
