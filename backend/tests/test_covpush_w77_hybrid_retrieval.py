"""Coverage wave 77 — core/hybrid_retrieval_service.py (0% -> 100%).

Two-stage hybrid retrieval: FastEmbed coarse + cross-encoder rerank with
graceful degradation. Fully mocked (no models loaded, no network).
"""
import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

import core.hybrid_retrieval_service as hybrid_mod
from core.hybrid_retrieval_service import HybridRetrievalService


def _coarse_results(n=3):
    # 0.25 steps keep float values exactly representable
    return [(f"ep-{i}", 0.75 - i * 0.25) for i in range(n)]


class TestInit:
    def test_init_wires_embedding_service(self):
        with patch("core.embedding_service.EmbeddingService") as MockES:
            service = HybridRetrievalService(MagicMock())
        MockES.assert_called_once_with(provider="fastembed")
        assert service._reranker_model is None


class TestGetRerankerModel:
    def _service(self):
        s = HybridRetrievalService.__new__(HybridRetrievalService)
        s.db = MagicMock()
        s._reranker_model = None
        return s

    @pytest.mark.asyncio
    async def test_loads_model_with_device(self):
        fake_st = types.ModuleType("sentence_transformers")
        captured = {}

        class FakeCrossEncoder:
            def __init__(self, *a, **kw):
                captured["args"] = a
                captured["kwargs"] = kw

        fake_st.CrossEncoder = FakeCrossEncoder
        s = self._service()
        with patch.dict(sys.modules, {"sentence_transformers": fake_st}):
            model = await s._get_reranker_model()
        assert model is not None
        assert captured["args"] == ("BAAI/bge-large-en-v1.5",)
        assert captured["kwargs"]["device"] in ("cuda", "cpu")
        # cached on second call
        assert await s._get_reranker_model() is model

    @pytest.mark.asyncio
    async def test_import_error_disables_reranker(self):
        s = self._service()
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            assert await s._get_reranker_model() is False

    @pytest.mark.asyncio
    async def test_load_error_disables_reranker(self):
        fake_st = types.ModuleType("sentence_transformers")

        class BoomCrossEncoder:
            def __init__(self, *a, **kw):
                raise RuntimeError("download failed")

        fake_st.CrossEncoder = BoomCrossEncoder
        s = self._service()
        with patch.dict(sys.modules, {"sentence_transformers": fake_st}):
            assert await s._get_reranker_model() is False


class TestRetrieveSemanticHybrid:
    def _service(self, coarse=None):
        db = MagicMock()
        s = HybridRetrievalService.__new__(HybridRetrievalService)
        s.db = db
        s.embedding_service = MagicMock()
        s.embedding_service.coarse_search_fastembed = AsyncMock(
            return_value=coarse if coarse is not None else _coarse_results())
        s._reranker_model = None
        return s

    @pytest.mark.asyncio
    async def test_no_coarse_results(self):
        s = self._service(coarse=[])
        assert await s.retrieve_semantic_hybrid("a1", "query") == []

    @pytest.mark.asyncio
    async def test_reranking_disabled_model(self):
        s = self._service()
        s._reranker_model = False
        result = await s.retrieve_semantic_hybrid("a1", "query", rerank_top_k=2)
        assert result == [("ep-0", 0.75, "coarse_only"), ("ep-1", 0.5, "coarse_only")]

    @pytest.mark.asyncio
    async def test_use_reranking_false(self):
        s = self._service()
        result = await s.retrieve_semantic_hybrid("a1", "query", use_reranking=False)
        assert result[0][2] == "coarse_only"
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_reranking_success(self):
        s = self._service()
        s._reranker_model = MagicMock()
        s._rerank_cross_encoder = AsyncMock(return_value=[("ep-1", 0.95)])
        result = await s.retrieve_semantic_hybrid("a1", "query")
        assert result == [("ep-1", 0.95, "reranked")]

    @pytest.mark.asyncio
    async def test_reranking_timeout_falls_back(self):
        s = self._service()
        s._reranker_model = MagicMock()
        s._rerank_cross_encoder = AsyncMock(side_effect=asyncio.TimeoutError)
        result = await s.retrieve_semantic_hybrid("a1", "query", rerank_top_k=2)
        assert result == [("ep-0", 0.75, "coarse_timeout_fallback"), ("ep-1", 0.5, "coarse_timeout_fallback")]

    @pytest.mark.asyncio
    async def test_reranking_error_falls_back(self):
        s = self._service()
        s._reranker_model = MagicMock()
        s._rerank_cross_encoder = AsyncMock(side_effect=RuntimeError("boom"))
        result = await s.retrieve_semantic_hybrid("a1", "query")
        assert result[0][2] == "coarse_fallback"


class TestRerankCrossEncoder:
    def _episode(self, ep_id, text, agent_id="a1"):
        ep = MagicMock()
        ep.id = ep_id
        ep.task_description = text
        ep.agent_id = agent_id
        return ep

    @pytest.mark.asyncio
    async def test_empty_pairs_returns_candidates(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        s = HybridRetrievalService.__new__(HybridRetrievalService)
        s.db = db
        s._reranker_model = MagicMock()
        candidates = [("ep-1", 0.5)]
        result = await s._rerank_cross_encoder("q", candidates, "a1")
        assert result == candidates  # unchanged
        s._reranker_model.predict.assert_not_called()

    @pytest.mark.asyncio
    async def test_scores_align_to_own_episode(self):
        episodes = [self._episode("B", "episode B"), self._episode("C", "episode C")]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = episodes
        service = HybridRetrievalService.__new__(HybridRetrievalService)
        service.db = db
        service._reranker_model = MagicMock()
        service._reranker_model.predict.return_value = np.array([0.2, 0.9])

        result = await service._rerank_cross_encoder("query", [("A", 0.1), ("B", 0.5), ("C", 0.5)], "a1")
        by_id = {ep_id: score for ep_id, score in result}
        # B is pair #0 -> normalized 0.0; C is pair #1 -> 1.0
        assert by_id["B"] == pytest.approx(0.3 * 0.5 + 0.7 * 0.0)
        assert by_id["C"] == pytest.approx(0.3 * 0.5 + 0.7 * 1.0)
        assert "A" not in by_id
        # sorted by combined score descending
        assert result[0][0] == "C"

    @pytest.mark.asyncio
    async def test_non_numpy_normalization(self):
        episodes = [self._episode("B", "text B"), self._episode("C", "text C")]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = episodes
        service = HybridRetrievalService.__new__(HybridRetrievalService)
        service.db = db
        service._reranker_model = MagicMock()
        service._reranker_model.predict.return_value = [0.2, 0.9]
        with patch.object(hybrid_mod, "NUMPY_AVAILABLE", False):
            result = await service._rerank_cross_encoder("q", [("B", 0.5), ("C", 0.5)], "a1")
        by_id = {ep_id: score for ep_id, score in result}
        assert by_id["B"] == pytest.approx(0.3 * 0.5)
        assert by_id["C"] == pytest.approx(0.3 * 0.5 + 0.7 * 1.0)


class TestBaseline:
    @pytest.mark.asyncio
    async def test_baseline_returns_coarse(self):
        s = HybridRetrievalService.__new__(HybridRetrievalService)
        s.db = MagicMock()
        s.embedding_service = MagicMock()
        s.embedding_service.coarse_search_fastembed = AsyncMock(return_value=_coarse_results())
        result = await s.retrieve_semantic_baseline("a1", "query", top_k=5)
        assert result == [("ep-0", 0.75), ("ep-1", 0.5), ("ep-2", 0.25)]
        s.embedding_service.coarse_search_fastembed.assert_awaited_once_with(
            agent_id="a1", query="query", top_k=5, db=s.db)


class TestModuleImportGuards:
    """Import-time environment branches (numpy/torch/CUDA availability)."""

    _MISSING = object()

    def _reload(self, numpy=_MISSING, torch_mod=_MISSING):
        patches = {}
        if numpy is not self._MISSING:
            patches["numpy"] = numpy
        if torch_mod is not self._MISSING:
            patches["torch"] = torch_mod
        with patch.dict(sys.modules, patches):
            return importlib.reload(hybrid_mod)

    def test_numpy_missing_fallback(self):
        mod = self._reload(numpy=None, torch_mod=None)
        assert mod.NUMPY_AVAILABLE is False
        assert mod.CUDA_AVAILABLE is False
        importlib.reload(hybrid_mod)  # restore real env

    def test_cuda_available_branch(self):
        fake_torch = types.ModuleType("torch")
        cuda = types.ModuleType("torch.cuda")
        cuda.is_available = lambda: True
        cuda.get_device_name = lambda *a: "RTX 4090"
        fake_torch.cuda = cuda
        mod = self._reload(numpy=None, torch_mod=fake_torch)
        assert mod.CUDA_AVAILABLE is True
        importlib.reload(hybrid_mod)

    def test_cuda_missing_cpu_branch(self):
        fake_torch = types.ModuleType("torch")
        cuda = types.ModuleType("torch.cuda")
        cuda.is_available = lambda: False
        fake_torch.cuda = cuda
        mod = self._reload(numpy=None, torch_mod=fake_torch)
        assert mod.CUDA_AVAILABLE is False
        importlib.reload(hybrid_mod)
