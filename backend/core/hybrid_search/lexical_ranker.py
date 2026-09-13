"""BM25 lexical ranker over IngestedDocument + KnowledgeDocument.

SQLite: FTS5 external-content tables (ingested_documents_fts,
knowledge_documents_fts) ranked by ``bm25()`` — the twin of the reasoning-steps
implementation (turn_fact_extractor.search_reasoning_steps_lexical).
Postgres: generated tsvector ``search_vector`` + GIN ranked by ``ts_rank_cd``.

Degrades gracefully: if the FTS tables are missing (migration not applied on a
hybrid dev DB), falls back to the ILIKE substring prefilter with the same
title-3x/content-1x weighting as the legacy ``_documents_search``. Never raises.

Each result carries ``lexical_mode`` so the caller can label the leg honestly
(``fts5_bm25`` | ``tsvector_rank`` | ``iliike_fallback``).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from sqlalchemy.orm import Session
from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)

_FTS_TOKEN_CLEAN = re.compile(r"[A-Za-z0-9_]+")

_TITLE_WEIGHT = 3.0
_CONTENT_WEIGHT = 1.0
_MAX_PREFILTER = 200

# English stopwords (Postgres 'english' snowball list — the common denominator
# of both engines). FTS5/tsvector engines silently drop these from queries: PG
# returns zero rows for e.g. "and" (plainto_tsquery produces an empty tsquery)
# and FTS5 prefix "and*" only matches words STARTING with "and" — while the
# ILIKE fallback matches "and" inside "understand". A query made entirely of
# stopwords therefore returned [] (FTS present) vs matches (FTS absent) for the
# same function — DB-state-dependent results. Route stopword-only queries to
# the ILIKE path so behavior is consistent regardless of FTS availability.
_ENGLISH_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by",
    "for", "if", "in", "into", "is", "it", "no", "not", "of",
    "on", "or", "such", "that", "the", "their", "then", "there",
    "these", "they", "this", "to", "was", "will", "with",
})


def _query_safe_tokens(query: str) -> List[str]:
    """Split a user query into FTS-safe alphanumeric tokens (>= 2 chars)."""
    return [t for t in _FTS_TOKEN_CLEAN.findall(query.lower()) if len(t) >= 2]


def _fts_table_exists(db: Session, table_name: str) -> bool:
    bind = db.bind
    if bind is None:
        return False
    try:
        if bind.dialect.name == "sqlite":
            row = db.execute(
                sa_text(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name=:t"
                ),
                {"t": table_name},
            ).first()
            return row is not None
        if bind.dialect.name == "postgresql":
            row = db.execute(
                sa_text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = :t"
                ),
                {"t": table_name},
            ).first()
            return row is not None
    except Exception as e:
        logger.debug("_fts_table_exists(%s) failed: %s", table_name, e)
    return False


def _try_self_heal_fts(db: Session) -> bool:
    """Best-effort provisioning of the FTS index from the search path.

    Never raises: a failure here just leaves the caller on the degraded ILIKE
    leg, exactly as before. Cheap on the hot path — the bootstrap caches a
    successful provision per (dialect, database URL). That cache is RESET
    first: this function only runs when the index was observed MISSING, so a
    cached "ensured" for the same URL can only belong to a DIFFERENT database
    file (DB swap/restore without a restart — reset_bootstrap_cache had no
    production caller for exactly this case, 2026-09-13 review).
    """
    try:
        from core.hybrid_search.fts_bootstrap import (
            ensure_documents_fts_for_session,
            reset_bootstrap_cache,
        )

        reset_bootstrap_cache()
        return ensure_documents_fts_for_session(db)
    except Exception as e:
        logger.debug("documents FTS self-heal unavailable: %s", e)
        return False


def _search_ingested_sqlite(
    db: Session,
    fts_query: str,
    limit: int,
    since: Optional[datetime],
    author: Optional[str],
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT d.id, d.file_name, d.content_preview, d.external_modified_at, "
        "bm25(ingested_documents_fts) AS rank "
        "FROM ingested_documents_fts f "
        "JOIN ingested_documents d ON d.rowid = f.rowid "
        "WHERE ingested_documents_fts MATCH :q"
    )
    params: Dict[str, Any] = {"q": fts_query, "lim": limit}
    if since:
        sql += " AND (d.created_at >= :since OR d.external_modified_at >= :since)"
        params["since"] = since
    if author:
        sql += " AND d.integration_id LIKE :author"
        params["author"] = f"%{author}%"
    sql += " ORDER BY rank LIMIT :lim"
    rows = db.execute(sa_text(sql), params).fetchall()
    _RRF_K = 60
    return [
        {
            "source": "ingested",
            "id": r.id,
            "title": r.file_name,
            "preview": (r.content_preview or "")[:200],
            "score": round(1.0 / (_RRF_K + pos), 6),
            "rank": float(r.rank) if r.rank is not None else 0.0,
            "modified": r.external_modified_at.isoformat() if r.external_modified_at else None,
            "lexical_mode": "fts5_bm25",
        }
        for pos, r in enumerate(rows)
    ]


def _search_knowledge_sqlite(
    db: Session,
    fts_query: str,
    limit: int,
    since: Optional[datetime],
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT d.id, d.title, d.content, "
        "bm25(knowledge_documents_fts) AS rank "
        "FROM knowledge_documents_fts f "
        "JOIN knowledge_documents d ON d.rowid = f.rowid "
        "WHERE knowledge_documents_fts MATCH :q"
    )
    params: Dict[str, Any] = {"q": fts_query, "lim": limit}
    if since:
        sql += " AND (d.created_at >= :since OR d.updated_at >= :since)"
        params["since"] = since
    sql += " ORDER BY rank LIMIT :lim"
    rows = db.execute(sa_text(sql), params).fetchall()
    _RRF_K = 60
    return [
        {
            "source": "knowledge",
            "id": r.id,
            "title": r.title,
            "preview": (r.content or "")[:200],
            "score": round(1.0 / (_RRF_K + pos), 6),
            "rank": float(r.rank) if r.rank is not None else 0.0,
            "modified": None,
            "lexical_mode": "fts5_bm25",
        }
        for pos, r in enumerate(rows)
    ]


def _search_ingested_pg(
    db: Session,
    query: str,
    limit: int,
    since: Optional[datetime],
    author: Optional[str],
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT d.id, d.file_name, d.content_preview, d.external_modified_at, "
        "ts_rank_cd(d.search_vector, plainto_tsquery('english', :q)) AS rank "
        "FROM ingested_documents d "
        "WHERE d.search_vector @@ plainto_tsquery('english', :q)"
    )
    params: Dict[str, Any] = {"q": query, "lim": limit}
    if since:
        sql += " AND (d.created_at >= :since OR d.external_modified_at >= :since)"
        params["since"] = since
    if author:
        sql += " AND d.integration_id ILIKE :author"
        params["author"] = f"%{author}%"
    sql += " ORDER BY rank DESC LIMIT :lim"
    rows = db.execute(sa_text(sql), params).fetchall()
    _RRF_K = 60
    return [
        {
            "source": "ingested",
            "id": r.id,
            "title": r.file_name,
            "preview": (r.content_preview or "")[:200],
            "score": round(1.0 / (_RRF_K + pos), 6),
            "rank": float(r.rank) if r.rank is not None else 0.0,
            "modified": r.external_modified_at.isoformat() if r.external_modified_at else None,
            "lexical_mode": "tsvector_rank",
        }
        for pos, r in enumerate(rows)
    ]


def _search_knowledge_pg(
    db: Session,
    query: str,
    limit: int,
    since: Optional[datetime],
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT d.id, d.title, d.content, "
        "ts_rank_cd(d.search_vector, plainto_tsquery('english', :q)) AS rank "
        "FROM knowledge_documents d "
        "WHERE d.search_vector @@ plainto_tsquery('english', :q)"
    )
    params: Dict[str, Any] = {"q": query, "lim": limit}
    if since:
        sql += " AND (d.created_at >= :since OR d.updated_at >= :since)"
        params["since"] = since
    sql += " ORDER BY rank DESC LIMIT :lim"
    rows = db.execute(sa_text(sql), params).fetchall()
    _RRF_K = 60
    return [
        {
            "source": "knowledge",
            "id": r.id,
            "title": r.title,
            "preview": (r.content or "")[:200],
            "score": round(1.0 / (_RRF_K + pos), 6),
            "rank": float(r.rank) if r.rank is not None else 0.0,
            "modified": None,
            "lexical_mode": "tsvector_rank",
        }
        for pos, r in enumerate(rows)
    ]


def _search_iliike_fallback(
    db: Session,
    query: str,
    limit: int,
    since: Optional[datetime],
    source: Optional[str],
    author: Optional[str],
) -> List[Dict[str, Any]]:
    """Legacy ILIKE prefilter + title-3x/content-1x weighting (no FTS tables).

    Mirrors the FTS5 path's AND→OR retry (2026-09-13 review, P3-10): the
    AND-token prefilter is tried first (precision — a doc matching every
    token ranks by the full-needle hit); only when it returns NOTHING does
    an OR-token pass run, ranked by matched-token coverage, so one absent
    token no longer zeroes the whole fallback leg."""
    from core.models import IngestedDocument, KnowledgeDocument
    from sqlalchemy import or_, and_

    # Match on individual query tokens, not the full query string: a natural
    # question ("what's the price of the press brake?") is never a contiguous
    # substring of a title or preview, so the full-string ILIKE returned ~0
    # hits for every conversational query (same bug class as the GraphRAG
    # keyword leg). Tokens ORed across title+preview, then ranked by the
    # needle-substring weighting below.
    tokens = [t for t in _FTS_TOKEN_CLEAN.findall(query.lower()) if len(t) >= 2][:8]
    if not tokens:
        return []
    needle = query.lower()
    results: List[Dict[str, Any]] = []

    def _ingested_rows(clause) -> list:
        qi = db.query(IngestedDocument).filter(clause)
        if since:
            qi = qi.filter(
                or_(
                    IngestedDocument.created_at >= since,
                    IngestedDocument.external_modified_at >= since,
                )
            )
        if author:
            qi = qi.filter(IngestedDocument.integration_id.ilike(f"%{author}%"))
        return qi.limit(_MAX_PREFILTER).all()

    def _knowledge_rows(clause) -> list:
        qk = db.query(KnowledgeDocument).filter(clause)
        if since:
            qk = qk.filter(
                or_(
                    KnowledgeDocument.created_at >= since,
                    KnowledgeDocument.updated_at >= since,
                )
            )
        return qk.limit(_MAX_PREFILTER).all()

    def _token_clause(fields, mode: str):
        per_token = [or_(*(f.ilike(f"%{t}%") for f in fields)) for t in tokens]
        return (and_ if mode == "and" else or_)(*per_token)

    # Pass 1 — AND tokens + the exact-needle gate (legacy behavior).
    and_ing = _token_clause(
        (IngestedDocument.file_name, IngestedDocument.content_preview), "and"
    )
    and_know = _token_clause((KnowledgeDocument.title, KnowledgeDocument.content), "and")
    if source in (None, "", "ingested"):
        for d in _ingested_rows(and_ing):
            name_hit = needle in (d.file_name or "").lower()
            content_hit = needle in (d.content_preview or "").lower()
            if not (name_hit or content_hit):
                continue
            raw = (_TITLE_WEIGHT if name_hit else 0.0) + (_CONTENT_WEIGHT if content_hit else 0.0)
            results.append(
                {
                    "source": "ingested",
                    "id": d.id,
                    "title": d.file_name,
                    "preview": (d.content_preview or "")[:200],
                    "score": round(raw / (_TITLE_WEIGHT + _CONTENT_WEIGHT), 6),
                    "rank": 0.0,
                    "modified": d.external_modified_at.isoformat() if d.external_modified_at else None,
                    "lexical_mode": "iliike_fallback",
                }
            )
    if source in (None, "", "knowledge"):
        for k in _knowledge_rows(and_know):
            title_hit = needle in (k.title or "").lower()
            content_hit = needle in (k.content or "").lower()
            if not (title_hit or content_hit):
                continue
            raw = (_TITLE_WEIGHT if title_hit else 0.0) + (_CONTENT_WEIGHT if content_hit else 0.0)
            results.append(
                {
                    "source": "knowledge",
                    "id": k.id,
                    "title": k.title,
                    "preview": (k.content or "")[:200],
                    "score": round(raw / (_TITLE_WEIGHT + _CONTENT_WEIGHT), 6),
                    "rank": 0.0,
                    "modified": None,
                    "lexical_mode": "iliike_fallback",
                }
            )

    results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    if results:
        return results[:limit]

    # Pass 2 — OR-token recall pass (only when AND matched nothing): rank
    # by how many query tokens the row carries, mirroring the FTS5 leg's
    # OR retry so both engines answer partial matches the same way.
    or_results: List[Dict[str, Any]] = []

    def _coverage(name: str, content: str) -> int:
        return sum(
            1 for t in tokens if t in (name or "").lower() or t in (content or "").lower()
        )

    if source in (None, "", "ingested"):
        or_ing = _token_clause(
            (IngestedDocument.file_name, IngestedDocument.content_preview), "or"
        )
        for d in _ingested_rows(or_ing):
            hits = _coverage(d.file_name, d.content_preview)
            if not hits:
                continue
            or_results.append(
                {
                    "source": "ingested",
                    "id": d.id,
                    "title": d.file_name,
                    "preview": (d.content_preview or "")[:200],
                    "score": round(hits / len(tokens), 6),
                    "rank": 0.0,
                    "modified": d.external_modified_at.isoformat() if d.external_modified_at else None,
                    "lexical_mode": "iliike_fallback",
                }
            )
    if source in (None, "", "knowledge"):
        or_know = _token_clause((KnowledgeDocument.title, KnowledgeDocument.content), "or")
        for k in _knowledge_rows(or_know):
            hits = _coverage(k.title, k.content)
            if not hits:
                continue
            or_results.append(
                {
                    "source": "knowledge",
                    "id": k.id,
                    "title": k.title,
                    "preview": (k.content or "")[:200],
                    "score": round(hits / len(tokens), 6),
                    "rank": 0.0,
                    "modified": None,
                    "lexical_mode": "iliike_fallback",
                }
            )
    or_results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    return or_results[:limit]


def search_documents_lexical(
    db: Session,
    query: str,
    limit: int = 50,
    since: Optional[datetime] = None,
    source: Optional[str] = None,
    author: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """BM25 lexical search over ingested + knowledge documents.

    Returns a list of dicts: {source, id, title, preview, score, rank, modified,
    lexical_mode}. Skips trivial queries (<2 safe tokens). Never raises.
    """
    if not query or len(query.strip()) < 3:
        return []
    try:
        tokens = [t for t in _query_safe_tokens(query) if t]
        if not tokens:
            return []
        # Stopword-only queries: FTS5/tsvector engines drop these tokens
        # (PG's english config produces an empty tsquery; FTS5 prefix "and*"
        # misses "understand"-style substring occurrences), returning [] where
        # the ILIKE fallback matches. Route to ILIKE so the same query gives
        # the same answer whether or not the FTS tables exist.
        if all(t in _ENGLISH_STOPWORDS for t in tokens):
            return _search_iliike_fallback(db, query, limit, since, source, author)
        fts_query = " ".join(f"{t}*" for t in tokens)

        bind = db.bind
        if bind is None:
            return _search_iliike_fallback(db, query, limit, since, source, author)
        dialect = bind.dialect.name
        if dialect == "sqlite":
            fts_ingested = _fts_table_exists(db, "ingested_documents_fts")
            fts_knowledge = _fts_table_exists(db, "knowledge_documents_fts")
            if not (fts_ingested and fts_knowledge):
                # Self-heal: the index is provisioned at startup, but a DB that
                # appears after boot (restored backup, fresh file, blocked
                # migrations) has none — and without this the lexical leg
                # silently degraded to ILIKE for the life of the process
                # (observed 2026-09-11: lexical_hits=0 on every query, hybrid
                # reporting "semantic_only"). Provision once per process, then
                # re-check.
                if _try_self_heal_fts(db):
                    fts_ingested = _fts_table_exists(db, "ingested_documents_fts")
                    fts_knowledge = _fts_table_exists(db, "knowledge_documents_fts")
            if fts_ingested and fts_knowledge:
                def _run_sqlite(fts_q: str) -> List[Dict[str, Any]]:
                    out: List[Dict[str, Any]] = []
                    if source in (None, "", "ingested"):
                        out.extend(_search_ingested_sqlite(db, fts_q, limit, since, author))
                    if source in (None, "", "knowledge"):
                        out.extend(_search_knowledge_sqlite(db, fts_q, limit, since))
                    out.sort(key=lambda r: r.get("score", 0.0), reverse=True)
                    return out[:limit]

                results = _run_sqlite(fts_query)
                if not results:
                    # FTS5 space-separated terms are ANDed, so a natural-language
                    # query dies entirely if ANY single token is absent from the
                    # indexed columns — e.g. "1320mm 16GA... packing size" returned
                    # nothing because "packing"/"size" are not in content_preview.
                    # Retry once with OR so partial matches still surface; AND is
                    # tried first so a fully-matching query keeps its precision.
                    or_query = " OR ".join(f"{t}*" for t in tokens)
                    if or_query != fts_query:
                        results = _run_sqlite(or_query)
                return results
            # Fall through to ILIKE when any FTS table is missing.
            return _search_iliike_fallback(db, query, limit, since, source, author)

        if dialect == "postgresql":
            has_vector = _fts_table_exists(db, "ingested_documents") and _column_exists_pg(
                db, "ingested_documents", "search_vector"
            )
            if not has_vector:
                # Same self-heal as the sqlite branch (2026-09-13 review,
                # P3-11): it was wired only into sqlite, so a PG database
                # appearing after boot (restored backup, repointed DSN)
                # silently rode the ILIKE fallback for the process lifetime.
                # Idempotent, never raises.
                if _try_self_heal_fts(db):
                    has_vector = _fts_table_exists(
                        db, "ingested_documents"
                    ) and _column_exists_pg(db, "ingested_documents", "search_vector")
            if has_vector:
                results = []
                if source in (None, "", "ingested"):
                    results.extend(_search_ingested_pg(db, query, limit, since, author))
                if source in (None, "", "knowledge"):
                    results.extend(_search_knowledge_pg(db, query, limit, since))
                results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
                return results[:limit]
            return _search_iliike_fallback(db, query, limit, since, source, author)

        return _search_iliike_fallback(db, query, limit, since, source, author)
    except Exception as e:
        logger.error("search_documents_lexical failed: %s", e)
        return []


def _column_exists_pg(db: Session, table: str, column: str) -> bool:
    try:
        row = db.execute(
            sa_text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
        return row is not None
    except Exception:
        return False
