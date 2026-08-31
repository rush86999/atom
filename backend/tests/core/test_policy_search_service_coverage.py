"""
Coverage tests for core.policy_search_service.PGPolicySearchService.

Hybrid (vector + exact-filter) governance-policy search. These tests exercise
the service in isolation with a mocked DB session and a mocked LLMService so
the embedding/similarity/filter/format branches all run without a live
database or network.
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_doc(**overrides):
    """Build a fake GovernanceDocument-like object for search results."""
    defaults = dict(
        id="doc-1",
        title="Travel Policy",
        content="Employees must book economy class.",
        category="hr",
        embedding=[1.0, 0.0, 0.0],
        last_verified=datetime.now(timezone.utc),
        status="approved",
        is_deleted=False,
        expiration_date=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def llm_mock():
    """Fake LLMService whose generate_embedding is an async callable."""
    m = MagicMock()
    m.generate_embedding = AsyncMock(return_value=[1.0, 0.0, 0.0])
    return m


@pytest.fixture
def service(llm_mock):
    """PGPolicySearchService with a mocked DB session and embedding seams.

    LLMService and EmbeddingService are both imported *inside* __init__, so
    we patch them at their sources. Embeddings moved off LLMService to a
    dedicated EmbeddingService (EMBEDDING_PROVIDER-aware); the tests stub
    the embedding seam with the same [1.0, 0.0, 0.0] vector as before.
    """
    with patch("core.llm_service.LLMService", return_value=llm_mock), \
         patch("core.embedding_service.EmbeddingService") as emb_cls:
        emb_cls.return_value.generate_embedding = AsyncMock(return_value=[1.0, 0.0, 0.0])
        from core.policy_search_service import PGPolicySearchService
        svc = PGPolicySearchService(MagicMock())
    return svc


def _seed_db(service, docs):
    """Make the mocked DB session return ``docs`` from the search query."""
    service.db.execute.return_value.scalars.return_value.all.return_value = docs


# ---------------------------------------------------------------------------
# _cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors_is_one(self, service):
        assert service._cosine_similarity([1.0, 1.0], [1.0, 1.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_is_zero(self, service):
        assert service._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_norm_returns_zero(self, service):
        # Either vector having zero magnitude short-circuits to 0.0.
        assert service._cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
        assert service._cosine_similarity([1.0, 1.0], [0.0, 0.0]) == 0.0

    def test_mismatched_dims_returns_zero(self, service):
        # np.dot raises on mismatched lengths; the handler returns 0.0.
        assert service._cosine_similarity([1.0, 2.0, 3.0], [1.0]) == 0.0


# ---------------------------------------------------------------------------
# _get_verification_status
# ---------------------------------------------------------------------------

class TestGetVerificationStatus:
    def test_unverified_when_no_last_verified(self, service):
        assert service._get_verification_status(_make_doc(last_verified=None)) == "unverified"

    def test_verified_when_recent(self, service):
        doc = _make_doc(last_verified=datetime.now(timezone.utc))
        assert service._get_verification_status(doc) == "verified"

    def test_outdated_when_older_than_24h(self, service):
        doc = _make_doc(last_verified=datetime.now(timezone.utc) - timedelta(hours=48))
        assert service._get_verification_status(doc) == "outdated"


# ---------------------------------------------------------------------------
# _generate_query_embedding
# ---------------------------------------------------------------------------

class TestGenerateQueryEmbedding:
    @pytest.mark.asyncio
    async def test_success_returns_embedding(self, service):
        assert await service._generate_query_embedding("travel") == [1.0, 0.0, 0.0]
        service.embedding_service.generate_embedding.assert_awaited_once_with("travel")

    @pytest.mark.asyncio
    async def test_failure_returns_zero_vector_fallback(self, service):
        # Failure contract: [] (no vector -> every cosine scores 0.0, docs
        # still surface unranked) rather than a fake zero-vector.
        service.embedding_service.generate_embedding = AsyncMock(
            side_effect=RuntimeError("boom"))
        emb = await service._generate_query_embedding("travel")
        assert emb == []


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    @pytest.mark.asyncio
    async def test_results_sorted_by_similarity_desc(self, service):
        # Query embedding is [1,0,0]; "close" aligns with it, "far" is orthogonal.
        close = _make_doc(id="close", embedding=[1.0, 0.0, 0.0])
        far = _make_doc(id="far", embedding=[0.0, 1.0, 0.0])
        _seed_db(service, [far, close])  # intentionally unsorted input

        results = await service.search(query="travel")

        assert [r["id"] for r in results] == ["close", "far"]
        assert results[0]["similarity"] == pytest.approx(1.0)
        assert results[0]["category"] == "hr"

    @pytest.mark.asyncio
    async def test_limit_truncates_results(self, service):
        docs = [_make_doc(id=f"d{i}", embedding=[1.0, 0.0, 0.0]) for i in range(3)]
        _seed_db(service, docs)

        results = await service.search(query="travel", limit=1)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_domain_filter_does_not_error(self, service):
        _seed_db(service, [_make_doc(id="d1", category="hr")])
        results = await service.search(query="travel", domain="hr")
        assert results and results[0]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_string_embedding_is_json_parsed(self, service):
        # embedding stored as a JSON string must be parsed before similarity.
        doc = _make_doc(id="str-emb", embedding=json.dumps([1.0, 0.0, 0.0]))
        _seed_db(service, [doc])

        results = await service.search(query="travel")
        assert results and results[0]["id"] == "str-emb"
        assert results[0]["similarity"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_malformed_string_embedding_is_skipped(self, service):
        # A corrupt JSON embedding string must be skipped (continue), not crash.
        bad = _make_doc(id="bad", embedding="not-json")
        good = _make_doc(id="good", embedding=[1.0, 0.0, 0.0])
        _seed_db(service, [bad, good])

        results = await service.search(query="travel")
        assert [r["id"] for r in results] == ["good"]

    @pytest.mark.asyncio
    async def test_falsy_embedding_is_skipped(self, service):
        # Empty/None embeddings are skipped.
        empty = _make_doc(id="empty", embedding=None)
        zero_list = _make_doc(id="zero", embedding=[])
        good = _make_doc(id="good", embedding=[1.0, 0.0, 0.0])
        _seed_db(service, [empty, zero_list, good])

        results = await service.search(query="travel")
        assert [r["id"] for r in results] == ["good"]

    @pytest.mark.asyncio
    async def test_verification_status_filter_branches(self, service):
        # Exercise each verification_status branch (verified/unverified/outdated/
        # None) so every stmt.where path runs.
        for status in ("verified", "unverified", "outdated", None):
            _seed_db(service, [_make_doc(id="d1", embedding=[1.0, 0.0, 0.0])])
            results = await service.search(query="travel", verification_status=status)
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_result_includes_iso_last_verified_or_none(self, service):
        recent = _make_doc(id="recent", embedding=[1.0, 0.0, 0.0],
                           last_verified=datetime.now(timezone.utc))
        never = _make_doc(id="never", embedding=[0.0, 1.0, 0.0], last_verified=None)
        _seed_db(service, [recent, never])

        results = {r["id"]: r for r in await service.search(query="travel")}
        assert results["recent"]["last_verified"] is not None
        assert "T" in results["recent"]["last_verified"]  # ISO 8601
        assert results["never"]["last_verified"] is None
