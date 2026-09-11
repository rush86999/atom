"""Self-provisioning FTS bootstrap for documents.search.

Regression context (2026-09-11): the lexical (BM25) leg of `documents.search`
returned 0 hits on EVERY query in the dev deployment. Root cause: the
`20260808_add_documents_fts` migration was never applied — the alembic CLI is
blocked on this DB (batch-mode FK crash + broken revision chain, round 71) — so
`ingested_documents_fts` / `knowledge_documents_fts` simply did not exist, and
`search_documents_lexical` silently fell through to ILIKE over a table that has
no full-content column (only `content_preview`). Hybrid search degraded to
`semantic_only` invisibly.

A second, latent bug surfaced while fixing the first: the migration's FTS sync
triggers referenced bare column names (`COALESCE(file_name,'')`), which SQLite
does not resolve inside a trigger body — so on any DB where that migration DID
run, every INSERT into the base table would raise `no such column: file_name`,
breaking document ingestion. Those tests below lock the qualified form.

These tests build the schema from the real ORM models so the ranker's filters
(`workspace_id`, freshness, etc.) exercise the production column set.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from core.hybrid_search.fts_bootstrap import (
    ensure_documents_fts,
    reset_bootstrap_cache,
)
from core.models import IngestedDocument, KnowledgeDocument


def _engine():
    """In-memory SQLite carrying only the two document tables the ranker reads."""
    eng = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    try:
        IngestedDocument.__table__.create(bind=eng, checkfirst=True)
        KnowledgeDocument.__table__.create(bind=eng, checkfirst=True)
    except Exception:
        # Fall back to metadata-wide creation if FK/DDL ordering complains.
        from core.models import Base

        Base.metadata.create_all(
            eng, tables=[IngestedDocument.__table__, KnowledgeDocument.__table__]
        )
    Session = sessionmaker(bind=eng)
    with Session() as db:
        db.add(
            IngestedDocument(
                id="1",
                workspace_id="ws-1",
                file_name="quote.pdf",
                file_path="/tmp/quote.pdf",
                file_type="pdf",
                integration_id="email",
                external_id="ext-1",
                content_preview="SPECIFICATIONS 1320mm 16GA foot shear 430kg",
            )
        )
        db.add(
            KnowledgeDocument(
                id="k1",
                tenant_id="t-1",
                title="Shear notes",
                content="manual back gauge 600mm",
            )
        )
        db.commit()
    return eng


def _table_names(eng) -> set:
    with eng.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {r[0] for r in rows}


def _trigger_names(eng) -> set:
    with eng.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    return {r[0] for r in rows}


def test_bootstrap_creates_fts_tables_and_backfills():
    """Red: without this, production had zero FTS tables -> lexical_hits=0."""
    eng = _engine()
    reset_bootstrap_cache()
    assert "ingested_documents_fts" not in _table_names(eng)

    assert ensure_documents_fts(eng) is True

    names = _table_names(eng)
    assert "ingested_documents_fts" in names
    assert "knowledge_documents_fts" in names
    # Pre-existing rows must be searchable immediately (backfill, not just DDL).
    with eng.connect() as conn:
        hit = conn.exec_driver_sql(
            "SELECT rowid FROM ingested_documents_fts "
            "WHERE ingested_documents_fts MATCH '1320mm'"
        ).fetchall()
    assert hit, "backfill did not index pre-existing rows"


def test_bootstrap_creates_sync_triggers():
    """Triggers must be new./old.-qualified or every base-table write raises."""
    eng = _engine()
    reset_bootstrap_cache()
    ensure_documents_fts(eng)

    names = _trigger_names(eng)
    for suffix in ("_ai", "_ad", "_au"):
        assert f"ingested_documents_fts{suffix}" in names

    Session = sessionmaker(bind=eng)
    with Session() as db:
        db.add(
            IngestedDocument(
                id="2",
                workspace_id="ws-1",
                file_name="new.pdf",
                file_path="/tmp/new.pdf",
                file_type="pdf",
                integration_id="email",
                external_id="ext-2",
                content_preview="guillotine blade 2600mm",
            )
        )
        db.commit()  # would raise "no such column: file_name" with bare triggers

    with eng.connect() as conn:
        hit = conn.exec_driver_sql(
            "SELECT rowid FROM ingested_documents_fts "
            "WHERE ingested_documents_fts MATCH 'guillotine'"
        ).fetchall()
    assert hit, "AFTER INSERT trigger did not index the new row"


def test_bootstrap_is_idempotent():
    """Called on every startup + every cold search: must never raise or duplicate."""
    eng = _engine()
    reset_bootstrap_cache()
    assert ensure_documents_fts(eng) is True
    assert ensure_documents_fts(eng) is True
    assert ensure_documents_fts(eng) is True
    with eng.connect() as conn:
        n = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM ingested_documents_fts"
        ).fetchone()[0]
    assert n == 1, f"backfill ran twice (duplicate rows: {n})"


def test_bootstrap_never_raises_on_broken_engine():
    """Never-raises contract: a bad bind must not break document search/startup."""
    reset_bootstrap_cache()
    assert ensure_documents_fts(None) is False

    class _Boom:
        class dialect:  # noqa: N801
            name = "sqlite"

        def connect(self):
            raise RuntimeError("boom")

    assert ensure_documents_fts(_Boom()) is False


def test_bootstrap_repairs_unpopulated_index():
    """A table that exists but was never backfilled must be healed, not trusted."""
    eng = _engine()
    reset_bootstrap_cache()
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE VIRTUAL TABLE ingested_documents_fts USING fts5("
            "file_name, content_preview, content='ingested_documents', "
            "content_rowid='rowid')"
        )
    assert ensure_documents_fts(eng) is True
    with eng.connect() as conn:
        hit = conn.exec_driver_sql(
            "SELECT rowid FROM ingested_documents_fts "
            "WHERE ingested_documents_fts MATCH '1320mm'"
        ).fetchall()
    assert hit, "empty FTS table was not backfilled"


def test_lexical_search_self_heals_missing_fts():
    """The search path itself provisions FTS, so a fresh DB gets a real BM25 leg."""
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    eng = _engine()
    reset_bootstrap_cache()
    Session = sessionmaker(bind=eng)
    with Session() as db:
        results = search_documents_lexical(db, "1320mm", limit=10)

    assert results, "lexical leg returned nothing even after self-provisioning"
    assert any(str(r.get("id")) == "1" for r in results)
    assert results[0].get("lexical_mode") != "iliike_fallback", (
        "self-heal did not engage; still on the degraded ILIKE path"
    )


def test_lexical_search_still_works_when_bootstrap_unavailable():
    """Degradation must stay graceful: FTS impossible -> ILIKE, never an exception."""
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    eng = _engine()
    reset_bootstrap_cache()
    Session = sessionmaker(bind=eng)
    with Session() as db:
        assert search_documents_lexical(db, "zzz", limit=10) == []
        assert search_documents_lexical(db, "a", limit=10) == []


def test_lexical_search_ors_when_and_matches_nothing():
    """A query with one absent term must still surface partial matches.

    FTS5 ANDs space-separated terms, so "1320mm nonexistentterm" would return
    nothing at all under strict AND. Live evidence: the natural-language query
    "1320mm 16GA foot shear 430kg packing size" returned lexical_hits=0 purely
    because "packing"/"size" are not in `content_preview`, even though the
    target document matched four other terms.
    """
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    eng = _engine()
    reset_bootstrap_cache()
    Session = sessionmaker(bind=eng)
    with Session() as db:
        # AND would fail (no doc contains 'nonexistentterm'); OR must recover.
        results = search_documents_lexical(db, "1320mm nonexistentterm", limit=10)

    assert results, "OR fallback did not engage; partial match was lost"
    assert any(str(r.get("id")) == "1" for r in results)
