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
    """Legacy ILIKE prefilter + title-3x/content-1x weighting (no FTS tables)."""
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
    tok_clause_ingested = and_(*[
        or_(
            IngestedDocument.file_name.ilike(f"%{t}%"),
            IngestedDocument.content_preview.ilike(f"%{t}%"),
        )
        for t in tokens
    ])
    needle = query.lower()
    results: List[Dict[str, Any]] = []

    if source in (None, "", "ingested"):
        qi = db.query(IngestedDocument).filter(tok_clause_ingested)
        if since:
            qi = qi.filter(
                or_(
                    IngestedDocument.created_at >= since,
                    IngestedDocument.external_modified_at >= since,
                )
            )
        if author:
            qi = qi.filter(IngestedDocument.integration_id.ilike(f"%{author}%"))
        for d in qi.limit(_MAX_PREFILTER).all():
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
        tok_clause_knowledge = and_(*[
            or_(
                KnowledgeDocument.title.ilike(f"%{t}%"),
                KnowledgeDocument.content.ilike(f"%{t}%"),
            )
            for t in tokens
        ])
        qk = db.query(KnowledgeDocument).filter(tok_clause_knowledge)
        if since:
            qk = qk.filter(
                or_(
                    KnowledgeDocument.created_at >= since,
                    KnowledgeDocument.updated_at >= since,
                )
            )
        for k in qk.limit(_MAX_PREFILTER).all():
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
    return results[:limit]


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
            if fts_ingested and fts_knowledge:
                results: List[Dict[str, Any]] = []
                if source in (None, "", "ingested"):
                    results.extend(_search_ingested_sqlite(db, fts_query, limit, since, author))
                if source in (None, "", "knowledge"):
                    results.extend(_search_knowledge_sqlite(db, fts_query, limit, since))
                results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
                return results[:limit]
            # Fall through to ILIKE when any FTS table is missing.
            return _search_iliike_fallback(db, query, limit, since, source, author)

        if dialect == "postgresql":
            has_vector = _fts_table_exists(db, "ingested_documents") and _column_exists_pg(
                db, "ingested_documents", "search_vector"
            )
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
