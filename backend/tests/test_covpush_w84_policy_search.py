# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/policy_search_service (standalone, EmbeddingService
mocked, real in-memory SQLite for GovernanceDocument).

- _generate_query_embedding: happy path + exception → empty-vector fallback.
- _cosine_similarity: normal, zero-norm either side, invalid input → 0.0.
- _get_verification_status: unverified / verified / outdated / NAIVE datetime
  from SQLite (bug-fix regression — aware-now minus naive raised TypeError
  on the Personal Edition SQLite backend).
- search(): embedding reuse, status/is_deleted/expiration filters, domain
  filter, verification filters (verified/unverified/outdated/None), string
  embedding parse (json) + malformed skip, similarity sort, limit truncation,
  formatting (last_verified iso / None).
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import EMBEDDING_DIM, PGVECTOR_AVAILABLE, GovernanceDocument, User
from core.policy_search_service import PGPolicySearchService

# GovernanceDocument.embedding is a pgvector Vector(EMBEDDING_DIM) column when
# pgvector is installed — inserts validate dimension count — so DB-bound test
# vectors must be full-dimension. Zero-padding keeps the 2-dim semantics
# (vector A vs orthogonal B) the suite was written with.
EMB_DIM = EMBEDDING_DIM if PGVECTOR_AVAILABLE else 2


def _vec(*components):
    return list(components) + [0.0] * (EMB_DIM - len(components))


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def svc(db):
    with patch("core.embedding_service.EmbeddingService") as emb_cls:
        emb = emb_cls.return_value
        emb.generate_embedding = AsyncMock(return_value=_vec(1.0, 0.0))
        service = PGPolicySearchService(db)
        yield service


def _make_user(db, user_id="u1"):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="F",
        last_name="L",
        role="admin",
        status="active",
    )
    db.add(user)
    db.commit()
    return user


def _make_doc(db, doc_id, *, title="Policy", content="Body", category="hr",
              status="approved", is_deleted=False, last_verified=None,
              expiration_date=None, embedding=None):
    _make_user(db)
    doc = GovernanceDocument(
        id=doc_id,
        title=title,
        content=content,
        category=category,
        status=status,
        entered_by="u1",
        is_deleted=is_deleted,
        last_verified=last_verified,
        expiration_date=expiration_date,
        embedding=embedding,
    )
    db.add(doc)
    db.commit()
    return doc


def _aware(days_ago=0, hours_ago=0):
    return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)


# ============================================================================
# _generate_query_embedding
# ============================================================================

class TestGenerateQueryEmbedding:
    def test_returns_embedding(self, svc):
        embedding = asyncio.run(svc._generate_query_embedding("hello"))
        assert embedding == _vec(1.0, 0.0)

    def test_exception_falls_back_to_empty_vector(self, svc):
        svc.embedding_service.generate_embedding = AsyncMock(side_effect=RuntimeError("embed down"))
        embedding = asyncio.run(svc._generate_query_embedding("hello"))
        assert embedding == []


# ============================================================================
# _cosine_similarity
# ============================================================================

class TestCosineSimilarity:
    def test_similar_vectors(self, svc):
        assert svc._cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self, svc):
        assert svc._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_norm_vec1(self, svc):
        assert svc._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_zero_norm_vec2(self, svc):
        assert svc._cosine_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0

    def test_invalid_input_returns_zero(self, svc):
        assert svc._cosine_similarity(["a", "b"], [1.0, 0.0]) == 0.0

    def test_scaled_vectors_same_direction(self, svc):
        assert svc._cosine_similarity([2.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


# ============================================================================
# _get_verification_status
# ============================================================================

class TestGetVerificationStatus:
    def test_none_is_unverified(self, svc):
        doc = SimpleNamespace(last_verified=None)
        assert svc._get_verification_status(doc) == "unverified"

    def test_fresh_is_verified(self, svc):
        doc = SimpleNamespace(last_verified=_aware(hours_ago=1))
        assert svc._get_verification_status(doc) == "verified"

    def test_old_is_outdated(self, svc):
        doc = SimpleNamespace(last_verified=_aware(days_ago=3))
        assert svc._get_verification_status(doc) == "outdated"

    def test_naive_datetime_does_not_crash(self, svc):
        """Regression: SQLite returns naive datetimes; subtracting them from
        an aware `now` raised TypeError on the Personal Edition backend."""
        doc = SimpleNamespace(
            last_verified=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1))
        assert svc._get_verification_status(doc) == "verified"

    def test_naive_old_datetime(self, svc):
        doc = SimpleNamespace(
            last_verified=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5))
        assert svc._get_verification_status(doc) == "outdated"


# ============================================================================
# search
# ============================================================================

class TestSearch:
    def test_returns_formatted_results(self, db, svc):
        _make_doc(db, "d1", title="PTO Policy", content="Paid time off",
                  category="hr", last_verified=_aware(hours_ago=1),
                  embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="pto", verification_status=None))
        assert len(results) == 1
        result = results[0]
        assert result["id"] == "d1"
        assert result["title"] == "PTO Policy"
        assert result["content"] == "Paid time off"
        assert result["category"] == "hr"
        assert result["similarity"] == pytest.approx(1.0)
        assert result["verification_status"] == "verified"
        assert result["last_verified"] is not None

    def test_excludes_pending_status(self, db, svc):
        _make_doc(db, "d1", status="pending", embedding=_vec(1.0, 0.0))
        assert asyncio.run(svc.search(query="x", verification_status=None)) == []

    def test_excludes_deleted(self, db, svc):
        _make_doc(db, "d1", is_deleted=True, embedding=_vec(1.0, 0.0))
        assert asyncio.run(svc.search(query="x", verification_status=None)) == []

    def test_excludes_expired(self, db, svc):
        _make_doc(db, "d1", expiration_date=_aware(days_ago=1), embedding=_vec(1.0, 0.0))
        assert asyncio.run(svc.search(query="x", verification_status=None)) == []

    def test_includes_non_expiring(self, db, svc):
        _make_doc(db, "d1", expiration_date=None, embedding=_vec(1.0, 0.0))
        assert len(asyncio.run(svc.search(query="x", verification_status=None))) == 1

    def test_domain_filter(self, db, svc):
        _make_doc(db, "d1", category="hr", embedding=_vec(1.0, 0.0))
        _make_doc(db, "d2", category="finance", embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", domain="hr", verification_status=None))
        assert [r["id"] for r in results] == ["d1"]

    def test_verified_filter(self, db, svc):
        _make_doc(db, "d1", last_verified=_aware(hours_ago=1), embedding=_vec(1.0, 0.0))
        _make_doc(db, "d2", last_verified=None, embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", verification_status="verified"))
        assert [r["id"] for r in results] == ["d1"]

    def test_unverified_filter(self, db, svc):
        _make_doc(db, "d1", last_verified=_aware(hours_ago=1), embedding=_vec(1.0, 0.0))
        _make_doc(db, "d2", last_verified=None, embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", verification_status="unverified"))
        assert [r["id"] for r in results] == ["d2"]

    def test_outdated_filter(self, db, svc):
        _make_doc(db, "d1", last_verified=_aware(days_ago=3), embedding=_vec(1.0, 0.0))
        _make_doc(db, "d2", last_verified=_aware(hours_ago=1), embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", verification_status="outdated"))
        assert [r["id"] for r in results] == ["d1"]

    def test_no_verification_filter(self, db, svc):
        _make_doc(db, "d1", last_verified=None, embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", verification_status=None))
        assert len(results) == 1

    def test_sorts_by_similarity_desc(self, db, svc):
        _make_doc(db, "close", embedding=_vec(1.0, 0.0))
        _make_doc(db, "far", embedding=_vec(0.0, 1.0))
        results = asyncio.run(svc.search(query="x", verification_status=None))
        assert [r["id"] for r in results] == ["close", "far"]

    def test_limit_truncates(self, db, svc):
        for i in range(5):
            _make_doc(db, f"d{i}", embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", limit=2, verification_status=None))
        assert len(results) == 2

    def test_string_embedding_parsed(self, db, svc):
        if PGVECTOR_AVAILABLE:
            pytest.skip("pgvector columns reject string embeddings at insert; "
                        "string parse only exists for the legacy JSON column")
        _make_doc(db, "d1", embedding=json.dumps(_vec(1.0, 0.0)))
        results = asyncio.run(svc.search(query="x", verification_status=None))
        assert [r["id"] for r in results] == ["d1"]

    def test_malformed_string_embedding_skipped(self, db, svc):
        if PGVECTOR_AVAILABLE:
            pytest.skip("pgvector validates embeddings at insert; malformed "
                        "strings cannot be stored to be skipped at read time")
        _make_doc(db, "bad", embedding="{not-json")
        _make_doc(db, "good", embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", verification_status=None))
        assert [r["id"] for r in results] == ["good"]

    def test_missing_embedding_skipped(self, db, svc):
        _make_doc(db, "noemb", embedding=None)
        results = asyncio.run(svc.search(query="x", verification_status=None))
        assert results == []

    def test_last_verified_none_formats_null(self, db, svc):
        _make_doc(db, "d1", last_verified=None, embedding=_vec(1.0, 0.0))
        results = asyncio.run(svc.search(query="x", verification_status=None))
        assert results[0]["last_verified"] is None
        assert results[0]["verification_status"] == "unverified"

    def test_naive_last_verified_does_not_crash_search(self, db, svc):
        """Regression: naive last_verified (SQLite) crashed formatting."""
        _make_doc(db, "d1", last_verified=_aware(hours_ago=1), embedding=_vec(1.0, 0.0))
        with patch.object(PGPolicySearchService, "_get_verification_status",
                       side_effect=lambda doc: "verified"):
            results = asyncio.run(svc.search(query="x"))
        assert results[0]["last_verified"] is not None
