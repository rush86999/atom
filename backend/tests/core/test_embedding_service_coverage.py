"""
Coverage + bug-hunt tests for core/embedding_service.py

Targets: EmbeddingService — provider selection, preprocessing, FastEmbed
generation, LRU cache, coarse search, cross-encoder reranking, batch ops,
convenience functions. All providers/LanceDB/LLMService mocked. No network.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core import embedding_service as es_mod
from core.embedding_service import (
    EmbeddingProvider,
    EmbeddingService,
    generate_embedding,
    generate_embeddings_batch,
)


# ---------------------------------------------------------------------------
# Construction / provider selection
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_default_provider_is_fastembed(self):
        svc = EmbeddingService()
        assert svc.provider == EmbeddingProvider.FASTEMBED
        assert svc.model.startswith("BAAI/bge")

    def test_local_alias_normalized_to_fastembed(self):
        svc = EmbeddingService(provider="local")
        assert svc.provider == EmbeddingProvider.FASTEMBED

    def test_openai_provider_sets_model(self):
        svc = EmbeddingService(provider="openai")
        assert svc.provider == EmbeddingProvider.OPENAI
        assert svc.model == "text-embedding-3-small"

    def test_cohere_provider_sets_model(self):
        svc = EmbeddingService(provider="cohere")
        assert svc.provider == EmbeddingProvider.COHERE
        assert svc.model == "embed-english-v3.0"

    def test_explicit_model_override(self):
        svc = EmbeddingService(provider="openai", model="text-embedding-3-large")
        assert svc.model == "text-embedding-3-large"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            EmbeddingService(provider="bogus")

    def test_default_model_fallback_for_unknown(self):
        # _get_default_model falls back to bge-small for unknown provider
        svc = EmbeddingService.__new__(EmbeddingService)
        svc.provider = "unknown_xyz"
        assert svc._get_default_model() == "BAAI/bge-small-en-v1.5"

    def test_workspace_and_tenant_defaults(self):
        svc = EmbeddingService()
        assert svc.workspace_id == "default"
        assert svc.tenant_id == "default"
        assert svc._client is None

    def test_config_stored(self):
        cfg = {"api_key": "k"}
        svc = EmbeddingService(config=cfg)
        assert svc.config == cfg

    def test_cache_structures_initialized(self):
        svc = EmbeddingService()
        assert svc._fastembed_cache == {}
        assert svc._fastembed_cache_order == []
        assert svc._fastembed_cache_max == 1000


# ---------------------------------------------------------------------------
# _preprocess_text
# ---------------------------------------------------------------------------

class TestPreprocess:
    def test_empty_returns_empty(self, service):
        assert service._preprocess_text("") == ""

    def test_whitespace_collapsed_and_stripped(self, service):
        assert service._preprocess_text("  hello   world  ") == "hello world"

    def test_unicode_normalized(self, service):
        # NFKC folds fullwidth / ligatures
        out = service._preprocess_text("① ＨＥＬＬＯ")
        assert isinstance(out, str)

    def test_truncation_fastembed(self, service):
        long = "x" * 10000
        out = service._preprocess_text(long)
        assert len(out) == 8192

    def test_truncation_openai(self):
        svc = EmbeddingService(provider="openai")
        long = "y" * 40000
        out = svc._preprocess_text(long)
        assert len(out) == 32000

    def test_truncation_cohere(self):
        svc = EmbeddingService(provider="cohere")
        long = "z" * 25000
        out = svc._preprocess_text(long)
        assert len(out) == 20000

    def test_no_truncation_when_under_limit(self, service):
        out = service._preprocess_text("short text")
        assert out == "short text"


@pytest.fixture
def service():
    # The FastEmbed client is cached at CLASS level (shared across service
    # instances since the off-event-loop fix) — clear it so each test gets a
    # cold cache and its own stubbed TextEmbedding construction.
    EmbeddingService._FASTEMBED_CLIENTS.clear()
    yield EmbeddingService()
    EmbeddingService._FASTEMBED_CLIENTS.clear()


# ---------------------------------------------------------------------------
# generate_embedding (single)
# ---------------------------------------------------------------------------

class TestGenerateEmbedding:
    @pytest.mark.asyncio
    async def test_fastembed_path(self, service):
        fake_emb = [0.1, 0.2, 0.3]
        with patch.object(service, "_generate_fastembed_embedding",
                          AsyncMock(return_value=fake_emb)):
            result = await service.generate_embedding("hello")
        assert result == fake_emb

    @pytest.mark.asyncio
    async def test_openai_path_routes_to_llm_service(self):
        svc = EmbeddingService(provider="openai")
        svc.llm_service.generate_embedding = AsyncMock(return_value=[0.5, 0.6])
        result = await svc.generate_embedding("hello")
        assert result == [0.5, 0.6]
        svc.llm_service.generate_embedding.assert_awaited_once()
        # Ensure text kw + model kw passed
        _, kwargs = svc.llm_service.generate_embedding.call_args
        assert kwargs.get("model") == "text-embedding-3-small"
        assert "text" in kwargs

    @pytest.mark.asyncio
    async def test_cohere_path_routes_to_llm_service(self):
        svc = EmbeddingService(provider="cohere")
        svc.llm_service.generate_embedding = AsyncMock(return_value=[0.9])
        await svc.generate_embedding("hi")
        svc.llm_service.generate_embedding.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_preprocessing_applied_before_generation(self, service):
        captured = {}

        async def fake(text):
            captured["text"] = text
            return [1.0]

        with patch.object(service, "_generate_fastembed_embedding", side_effect=fake):
            await service.generate_embedding("  spaced  ")
        # preprocessing collapses whitespace
        assert captured["text"] == "spaced"

    @pytest.mark.asyncio
    async def test_exception_propagates(self, service):
        with patch.object(service, "_generate_fastembed_embedding",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            with pytest.raises(RuntimeError, match="boom"):
                await service.generate_embedding("x")


# ---------------------------------------------------------------------------
# generate_embeddings_batch
# ---------------------------------------------------------------------------

class TestGenerateBatch:
    @pytest.mark.asyncio
    async def test_fastembed_batch(self, service):
        with patch.object(service, "_generate_fastembed_embeddings_batch",
                          AsyncMock(return_value=[[0.1], [0.2]])):
            result = await service.generate_embeddings_batch(["a", "b"])
        assert result == [[0.1], [0.2]]

    @pytest.mark.asyncio
    async def test_openai_batch_routes_to_llm_service(self):
        svc = EmbeddingService(provider="openai")
        svc.llm_service.generate_embeddings_batch = AsyncMock(return_value=[[0.1], [0.2]])
        result = await svc.generate_embeddings_batch(["a", "b"])
        assert result == [[0.1], [0.2]]
        svc.llm_service.generate_embeddings_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_batch_preprocessed(self, service):
        with patch.object(service, "_generate_fastembed_embeddings_batch",
                          AsyncMock(return_value=[])) as m:
            await service.generate_embeddings_batch([])
        m.assert_awaited_once_with([])

    @pytest.mark.asyncio
    async def test_batch_exception_propagates(self, service):
        with patch.object(service, "_generate_fastembed_embeddings_batch",
                          AsyncMock(side_effect=ValueError("nope"))):
            with pytest.raises(ValueError):
                await service.generate_embeddings_batch(["a"])

    @pytest.mark.asyncio
    async def test_unknown_provider_in_generate_raises(self):
        """Defensive else-branch: provider set to invalid after construction."""
        svc = EmbeddingService(provider="fastembed")
        svc.provider = "totally_unknown"  # bypass __init__ validation
        with pytest.raises(ValueError, match="Unknown provider"):
            await svc.generate_embedding("x")

    @pytest.mark.asyncio
    async def test_unknown_provider_in_batch_raises(self):
        svc = EmbeddingService(provider="fastembed")
        svc.provider = "totally_unknown"
        with pytest.raises(ValueError, match="Unknown provider"):
            await svc.generate_embeddings_batch(["x"])


# ---------------------------------------------------------------------------
# FastEmbed internal generation
# ---------------------------------------------------------------------------

class TestFastEmbedGeneration:
    @pytest.mark.asyncio
    async def test_single_import_error(self, service):
        # Simulate fastembed not installed
        import sys
        with patch.dict(sys.modules, {"fastembed": None}):
            with pytest.raises(Exception, match="FastEmbed package not installed"):
                await service._generate_fastembed_embedding("x")

    @pytest.mark.asyncio
    async def test_single_empty_result_raises(self, service):
        fake_text_emb = MagicMock()
        # embed returns empty
        fake_text_emb.TextEmbedding = MagicMock(return_value=MagicMock(
            embed=MagicMock(return_value=iter([]))
        ))
        import sys
        with patch.dict(sys.modules, {"fastembed": fake_text_emb}):
            with pytest.raises(Exception, match="empty result"):
                await service._generate_fastembed_embedding("x")

    @pytest.mark.asyncio
    async def test_single_success(self, service):
        arr = MagicMock()
        arr.tolist.return_value = [0.1, 0.2]
        fake_text_emb = MagicMock()
        fake_text_emb.TextEmbedding = MagicMock(return_value=MagicMock(
            embed=MagicMock(return_value=iter([arr]))
        ))
        import sys
        with patch.dict(sys.modules, {"fastembed": fake_text_emb}):
            result = await service._generate_fastembed_embedding("hello")
        assert result == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_client_cached_after_first_call(self, service):
        arr = MagicMock()
        arr.tolist.return_value = [0.5]
        text_embedding_instance = MagicMock()
        # side_effect returns a FRESH iterator each call
        text_embedding_instance.embed = MagicMock(side_effect=lambda texts: iter([arr]))
        fake_text_emb = MagicMock()
        fake_text_emb.TextEmbedding = MagicMock(return_value=text_embedding_instance)
        import sys
        with patch.dict(sys.modules, {"fastembed": fake_text_emb}):
            await service._generate_fastembed_embedding("a")
            await service._generate_fastembed_embedding("b")
        # TextEmbedding constructor called only once (cached)
        assert fake_text_emb.TextEmbedding.call_count == 1

    @pytest.mark.asyncio
    async def test_batch_success(self, service):
        a1, a2 = MagicMock(), MagicMock()
        a1.tolist.return_value = [0.1]
        a2.tolist.return_value = [0.2]
        fake_text_emb = MagicMock()
        fake_text_emb.TextEmbedding = MagicMock(return_value=MagicMock(
            embed=MagicMock(return_value=iter([a1, a2]))
        ))
        import sys
        with patch.dict(sys.modules, {"fastembed": fake_text_emb}):
            result = await service._generate_fastembed_embeddings_batch(["x", "y"])
        assert result == [[0.1], [0.2]]

    @pytest.mark.asyncio
    async def test_batch_exception_propagates(self, service):
        fake_text_emb = MagicMock()
        fake_text_emb.TextEmbedding = MagicMock(side_effect=RuntimeError("load fail"))
        import sys
        with patch.dict(sys.modules, {"fastembed": fake_text_emb}):
            with pytest.raises(RuntimeError):
                await service._generate_fastembed_embeddings_batch(["x"])


# ---------------------------------------------------------------------------
# create_fastembed_embedding (numpy)
# ---------------------------------------------------------------------------

class TestCreateFastEmbedEmbedding:
    @pytest.mark.asyncio
    async def test_returns_numpy_array(self, service):
        with patch.object(service, "_generate_fastembed_embedding",
                          AsyncMock(return_value=[0.1] * 384)):
            result = await service.create_fastembed_embedding("x")
        import numpy as np
        assert isinstance(result, np.ndarray)
        assert result.shape[0] == 384

    @pytest.mark.asyncio
    async def test_warns_on_wrong_dimension(self, service, caplog):
        with patch.object(service, "_generate_fastembed_embedding",
                          AsyncMock(return_value=[0.1] * 100)):  # wrong dim
            with caplog.at_level("WARNING"):
                result = await service.create_fastembed_embedding("x")
        assert any("expected 384" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self, service):
        with patch.object(service, "_generate_fastembed_embedding",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.create_fastembed_embedding("x")
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_to_list_when_numpy_unavailable(self, service):
        """When numpy is unavailable, returns a plain list instead of ndarray."""
        with patch.object(service, "_generate_fastembed_embedding",
                          AsyncMock(return_value=[0.1, 0.2])), \
             patch.object(es_mod, "NUMPY_AVAILABLE", False):
            result = await service.create_fastembed_embedding("x")
        assert result == [0.1, 0.2]
        assert not hasattr(result, "shape")


# ---------------------------------------------------------------------------
# LRU cache (the formula_memory-style focus area)
# ---------------------------------------------------------------------------

class TestLRUCache:
    def test_put_then_get(self, service):
        service._lru_cache_put("a", [1.0, 2.0])
        assert service._lru_cache_get("a") == [1.0, 2.0]

    def test_get_missing_returns_none(self, service):
        assert service._lru_cache_get("missing") is None

    def test_get_updates_access_order(self, service):
        # Put a, b, c then get a (moves a to end). Evicting should drop b next.
        service._lru_cache_put("a", [1])
        service._lru_cache_put("b", [2])
        service._lru_cache_put("c", [3])
        service._lru_cache_get("a")  # a now most-recent
        # Force eviction by exceeding capacity
        service._fastembed_cache_max = 4
        service._lru_cache_put("d", [4])  # now at capacity (a,b,c,d)
        service._lru_cache_put("e", [5])  # evicts LRU = b
        assert "b" not in service._fastembed_cache
        assert "a" in service._fastembed_cache

    def test_eviction_removes_oldest(self, service):
        service._fastembed_cache_max = 2
        service._lru_cache_put("a", [1])
        service._lru_cache_put("b", [2])
        service._lru_cache_put("c", [3])  # evicts a
        assert "a" not in service._fastembed_cache
        assert "b" in service._fastembed_cache
        assert "c" in service._fastembed_cache

    def test_re_put_does_not_double_count_in_order(self, service):
        """Re-putting an existing key updates value + moves to MRU."""
        service._lru_cache_put("a", [1])
        service._lru_cache_put("a", [9])  # update existing
        assert service._lru_cache_get("a") == [9]
        # Order list should have a exactly once
        assert service._fastembed_cache_order.count("a") == 1


class TestLRUReputBug:
    """BUG: _lru_cache_put appends the key to _fastembed_cache_order without
    first removing any prior occurrence. Re-caching the same episode_id leaves
    stale duplicate entries, which (a) inflates the apparent cache size and
    (b) can later evict the live entry when an old duplicate is popped as
    'oldest', corrupting the cache."""

    def test_bug_re_put_creates_duplicate_order_entry(self, service):
        service._lru_cache_put("a", [1])
        service._lru_cache_put("b", [2])
        service._lru_cache_put("a", [10])  # update a
        # No duplicate allowed in the access-order list
        assert service._fastembed_cache_order.count("a") == 1, (
            "BUG: re-putting key 'a' left a duplicate entry in "
            "_fastembed_cache_order"
        )

    def test_bug_stale_duplicate_can_evict_live_entry(self, service):
        """Re-putting a key while under capacity leaves a stale duplicate in
        the order list, so cache_stats (keys_cached) diverges from the actual
        cache size (current_size) — cache bookkeeping corruption."""
        service._fastembed_cache_max = 5
        service._lru_cache_put("a", [1])
        service._lru_cache_put("b", [2])
        service._lru_cache_put("a", [10])  # update a (still under capacity)
        stats = service.get_cache_stats()
        # keys_cached counts order-list entries; current_size counts dict keys.
        # They MUST agree (every key in the dict should have exactly one order
        # entry). Divergence indicates cache corruption.
        assert stats["keys_cached"] == stats["current_size"], (
            f"BUG: order list ({stats['keys_cached']}) diverged from cache dict "
            f"({stats['current_size']}) — stale duplicate order entries"
        )

    def test_get_cache_stats(self, service):
        service._lru_cache_put("a", [1])
        service._lru_cache_put("b", [2])
        stats = service.get_cache_stats()
        assert stats["current_size"] == 2
        assert stats["max_size"] == 1000
        assert stats["utilization_percent"] == pytest.approx(0.2, rel=1e-6)
        assert stats["keys_cached"] == 2


# ---------------------------------------------------------------------------
# cache_fastembed_embedding / get_fastembed_embedding (LanceDB fallback)
# ---------------------------------------------------------------------------

class TestCacheEmbedding:
    @pytest.mark.asyncio
    async def test_cache_no_db_stores_in_lru(self, service):
        result = await service.cache_fastembed_embedding("ep1", [0.1, 0.2], db=None)
        assert result is True
        assert service._lru_cache_get("ep1") == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_cache_with_db_lancedb_success(self, service):
        fake_lancedb = MagicMock()
        fake_lancedb.add_embedding = AsyncMock(return_value=True)
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=fake_lancedb):
            result = await service.cache_fastembed_embedding("ep1", [0.1], db=object())
        assert result is True
        fake_lancedb.add_embedding.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_with_db_lancedb_failure_non_fatal(self, service):
        fake_lancedb = MagicMock()
        fake_lancedb.add_embedding = AsyncMock(side_effect=RuntimeError("db down"))
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=fake_lancedb):
            # Should still return True (LanceDB failure is non-critical)
            result = await service.cache_fastembed_embedding("ep1", [0.1], db=object())
        assert result is True

    @pytest.mark.asyncio
    async def test_get_from_lru_cache(self, service):
        service._lru_cache_put("ep1", [0.5, 0.6])
        result = await service.get_fastembed_embedding("ep1", db=None)
        assert result == [0.5, 0.6]

    @pytest.mark.asyncio
    async def test_get_falls_back_to_lancedb_and_caches(self, service):
        fake_lancedb = MagicMock()
        fake_lancedb.get_embedding = AsyncMock(return_value=[0.7, 0.8])
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=fake_lancedb):
            result = await service.get_fastembed_embedding("ep1", db=object())
        assert result == [0.7, 0.8]
        # Now cached in LRU
        assert service._lru_cache_get("ep1") == [0.7, 0.8]

    @pytest.mark.asyncio
    async def test_get_lancedb_returns_none(self, service):
        fake_lancedb = MagicMock()
        fake_lancedb.get_embedding = AsyncMock(return_value=None)
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=fake_lancedb):
            result = await service.get_fastembed_embedding("ep1", db=object())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_lancedb_failure_returns_none(self, service):
        fake_lancedb = MagicMock()
        fake_lancedb.get_embedding = AsyncMock(side_effect=RuntimeError("x"))
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=fake_lancedb):
            result = await service.get_fastembed_embedding("ep1", db=object())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_no_db_no_cache_returns_none(self, service):
        result = await service.get_fastembed_embedding("nope", db=None)
        assert result is None


# ---------------------------------------------------------------------------
# coarse_search_fastembed
# ---------------------------------------------------------------------------

class TestCoarseSearch:
    @pytest.mark.asyncio
    async def test_query_embedding_failure_returns_empty(self, service):
        with patch.object(service, "create_fastembed_embedding",
                          AsyncMock(return_value=None)):
            result = await service.coarse_search_fastembed("ag1", "q", db=object())
        assert result == []

    @pytest.mark.asyncio
    async def test_no_db_returns_empty(self, service):
        with patch.object(service, "create_fastembed_embedding",
                          AsyncMock(return_value=[0.1] * 384)):
            result = await service.coarse_search_fastembed("ag1", "q", db=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_scored_results(self, service):
        fake_lancedb = MagicMock()
        fake_lancedb.similarity_search = AsyncMock(return_value=[
            {"episode_id": "e1", "score": 0.9},
            {"episode_id": "e2", "score": 0.7},
        ])
        with patch.object(service, "create_fastembed_embedding",
                          AsyncMock(return_value=[0.1] * 384)), \
             patch("core.lancedb_handler.get_lancedb_handler", return_value=fake_lancedb):
            result = await service.coarse_search_fastembed("ag1", "q", db=object())
        assert result == [("e1", 0.9), ("e2", 0.7)]

    @pytest.mark.asyncio
    async def test_search_lancedb_failure_returns_empty(self, service):
        fake_lancedb = MagicMock()
        fake_lancedb.similarity_search = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(service, "create_fastembed_embedding",
                          AsyncMock(return_value=[0.1] * 384)), \
             patch("core.lancedb_handler.get_lancedb_handler", return_value=fake_lancedb):
            result = await service.coarse_search_fastembed("ag1", "q", db=object())
        assert result == []


# ---------------------------------------------------------------------------
# rerank_cross_encoder
# ---------------------------------------------------------------------------

class TestRerank:
    @pytest.mark.asyncio
    async def test_no_sentence_transformers_returns_empty(self, service, db_session):
        # Force the lazy-load ImportError path
        import sys
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            result = await service.rerank_cross_encoder(
                "q", ["e1"], "ag1", db_session
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_cross_encoder_constructor_failure_returns_empty(self, service):
        """sentence_transformers importable but CrossEncoder construction fails."""
        import sys
        fake_st = MagicMock()
        fake_st.CrossEncoder = MagicMock(side_effect=RuntimeError("model missing"))
        # Ensure the module-level `hasattr(self, '_cross_encoder')` is False
        assert not hasattr(service, "_cross_encoder")
        with patch.dict(sys.modules, {"sentence_transformers": fake_st}):
            result = await service.rerank_cross_encoder("q", ["e1"], "ag1", MagicMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_no_matching_episodes_returns_empty(self, service, db_session):
        # Provide a fake cross-encoder via attribute; but episodes query empty
        service._cross_encoder = MagicMock()
        service._cross_encoder.predict = MagicMock(return_value=[0.5])
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        result = await service.rerank_cross_encoder("q", ["e1"], "ag1", db)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_normalizes_and_sorts(self, service):
        """Cross-encoder scores normalized to [0,1] and sorted descending."""
        service._cross_encoder = MagicMock()
        # raw scores: min=0, max=1
        service._cross_encoder.predict = MagicMock(return_value=[0.0, 0.5, 1.0])
        ep1 = MagicMock(id="e1", agent_id="ag1", task_description="task 1")
        ep2 = MagicMock(id="e2", agent_id="ag1", task_description="task 2")
        ep3 = MagicMock(id="e3", agent_id="ag1", task_description="task 3")
        db = MagicMock()
        # rerank uses single .filter(...).all()
        db.query.return_value.filter.return_value.all.return_value = [ep1, ep2, ep3]
        result = await service.rerank_cross_encoder("q", ["e1", "e2", "e3"], "ag1", db)
        ids = [r[0] for r in result]
        scores = [r[1] for r in result]
        # highest score first -> e3 (raw 1.0 -> normalized 1.0)
        assert ids[0] == "e3"
        assert scores[0] == pytest.approx(1.0, abs=1e-4)
        assert scores[-1] == pytest.approx(0.0, abs=1e-4)

    @pytest.mark.asyncio
    async def test_rerank_predict_failure_returns_empty(self, service):
        service._cross_encoder = MagicMock()
        service._cross_encoder.predict = MagicMock(side_effect=RuntimeError("x"))
        ep1 = MagicMock(id="e1", agent_id="ag1", task_description="t")
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [ep1]
        result = await service.rerank_cross_encoder("q", ["e1"], "ag1", db)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_python_fallback_when_numpy_unavailable(self, service):
        """When NUMPY_AVAILABLE is False, scores normalize via pure-Python."""
        service._cross_encoder = MagicMock()
        service._cross_encoder.predict = MagicMock(return_value=[0.0, 1.0])
        ep1 = MagicMock(id="e1", agent_id="ag1", task_description="t1")
        ep2 = MagicMock(id="e2", agent_id="ag1", task_description="t2")
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [ep1, ep2]
        with patch.object(es_mod, "NUMPY_AVAILABLE", False):
            result = await service.rerank_cross_encoder("q", ["e1", "e2"], "ag1", db)
        assert len(result) == 2
        # normalized: (1.0 - 0.0)/(1.0 - 0.0 + 1e-8) ~= 1.0 for e2
        scores = {r[0]: r[1] for r in result}
        assert scores["e2"] == pytest.approx(1.0, abs=1e-4)
        assert scores["e1"] == pytest.approx(0.0, abs=1e-4)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    @pytest.mark.asyncio
    async def test_generate_embedding_convenience(self):
        with patch.object(EmbeddingService, "generate_embedding",
                          AsyncMock(return_value=[0.1, 0.2])):
            result = await generate_embedding("hello", provider="openai")
        assert result == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_convenience(self):
        with patch.object(EmbeddingService, "generate_embeddings_batch",
                          AsyncMock(return_value=[[0.1], [0.2]])):
            result = await generate_embeddings_batch(["a", "b"])
        assert result == [[0.1], [0.2]]


# ---------------------------------------------------------------------------
# numpy-availability branches
# ---------------------------------------------------------------------------

class TestNumpyAvailability:
    def test_numpy_available_flag(self):
        # numpy is a hard dep in conftest; should be available
        assert es_mod.NUMPY_AVAILABLE is True
