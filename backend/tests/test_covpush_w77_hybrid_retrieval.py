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
from core.hybrid_retrieval_service import (
    DEFAULT_RERANK_MODEL,
    HybridRetrievalService,
    RerankUnavailable,
)


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
        s._reranker_verdict = None
        s._reranker_probe_done = False
        return s

    @pytest.mark.asyncio
    async def test_loads_model_with_device(self):
        # CONTRACT CHANGE (2026-09-26, search work order Phase D). This test
        # used to assert the loader opened "BAAI/bge-large-en-v1.5" — an
        # EMBEDDING checkpoint used as a reranker. The expectation now pins the
        # trained cross-encoder default AND that the load is local-files-only,
        # because a request must never trigger a model download.
        fake_st = types.ModuleType("sentence_transformers")
        captured = {}

        class FakeCrossEncoder:
            def __init__(self, *a, **kw):
                captured["args"] = a
                captured["kwargs"] = kw

        fake_st.CrossEncoder = FakeCrossEncoder
        s = self._service()
        with patch.dict(sys.modules, {"sentence_transformers": fake_st}), \
             patch("core.hybrid_retrieval_service._classify_checkpoint",
                   lambda m: {"model_id": m, "trained_reranker": True, "reason": "ok"}):
            model = await s._get_reranker_model()
        assert model is not None
        assert captured["args"] == (DEFAULT_RERANK_MODEL,)
        assert "bge-large-en-v1.5" not in captured["args"][0], (
            "the embedding checkpoint must not be loaded as a reranker")
        assert captured["kwargs"]["device"] in ("cuda", "cpu")
        assert captured["kwargs"]["local_files_only"] is True, (
            "a request-time model download is forbidden")
        # cached on second call
        assert await s._get_reranker_model() is model

    @pytest.mark.asyncio
    async def test_embedding_checkpoint_is_refused(self):
        """The regression: an embedding checkpoint loaded through CrossEncoder
        yields cosine geometry, which was then min-max normalised into a
        confident-looking relevance score."""
        fake_st = types.ModuleType("sentence_transformers")

        class NeverLoaded:
            def __init__(self, *a, **kw):
                raise AssertionError("embedding checkpoint must not be loaded")

        fake_st.CrossEncoder = NeverLoaded
        s = self._service()
        with patch.dict(sys.modules, {"sentence_transformers": fake_st}), \
             patch("core.hybrid_retrieval_service._classify_checkpoint",
                   lambda m: {"model_id": m, "trained_reranker": False,
                              "reason": "single_logit_encoder_without_classification_head"}):
            assert await s._get_reranker_model() is False
        assert s.reranker_verdict()["trained_reranker"] is False

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
        s._reranker_verdict = None
        s._reranker_probe_done = True
        s.last_ranking_status = {}
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
        s._predict_bounded = AsyncMock(return_value=[("ep-1", 0.95)])
        result = await s.retrieve_semantic_hybrid("a1", "query")
        assert result == [("ep-1", 0.95, "reranked")]
        assert s.last_ranking_status["status"] == "ok"

    @pytest.mark.asyncio
    async def test_reranking_timeout_falls_back(self):
        s = self._service()
        s._reranker_model = MagicMock()
        s._predict_bounded = AsyncMock(side_effect=asyncio.TimeoutError)
        result = await s.retrieve_semantic_hybrid("a1", "query", rerank_top_k=2)
        assert result == [("ep-0", 0.75, "coarse_timeout_fallback"), ("ep-1", 0.5, "coarse_timeout_fallback")]

    @pytest.mark.asyncio
    async def test_reranking_error_falls_back(self):
        # Stage name sharpened: "coarse_fallback" could mean a timeout, a
        # saturated queue or a genuine failure, and the caller could not tell a
        # degraded ranking from a degraded source. Each cause is now named, and
        # none of them is reported as a retrieval failure.
        s = self._service()
        s._reranker_model = MagicMock()
        s._predict_bounded = AsyncMock(
            side_effect=RerankUnavailable("predict_failed:RuntimeError"))
        result = await s.retrieve_semantic_hybrid("a1", "query")
        assert result[0][2] == "coarse_failed_fallback"
        assert s.last_ranking_status["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_rerank_queue_saturation_is_named_and_bounded(self):
        s = self._service()
        s._reranker_model = MagicMock()
        s._predict_bounded = AsyncMock(
            side_effect=RerankUnavailable("queue_saturated"))
        result = await s.retrieve_semantic_hybrid("a1", "query")
        assert result[0][2] == "coarse_saturated_fallback"
        assert s.last_ranking_status["reason"] == "queue_saturated"


class TestRerankCrossEncoder:
    def _episode(self, ep_id, text, agent_id="a1"):
        ep = MagicMock()
        ep.id = ep_id
        ep.task_description = text
        ep.agent_id = agent_id
        return ep

    @pytest.mark.asyncio
    async def test_no_candidate_content_refuses_instead_of_faking_a_ranking(self):
        """CONTRACT CHANGE (2026-09-26, search work order Phase D). This used to
        return the candidate list unchanged when nothing had content to rank —
        indistinguishable from "the reranker ranked these and they came out in
        this order". Refusing lets the caller record a degraded ranking."""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        s = HybridRetrievalService.__new__(HybridRetrievalService)
        s.db = db
        s._reranker_model = MagicMock()
        s._reranker_probe_done = True
        candidates = [("ep-1", 0.5)]
        with pytest.raises(RerankUnavailable) as exc:
            await s._rerank_cross_encoder("q", candidates, "a1")
        assert "no_candidate_content" in str(exc.value)
        s._reranker_model.predict.assert_not_called()

    @pytest.mark.asyncio
    async def test_scores_align_to_own_episode(self):
        """CONTRACT CHANGE. The scores used to be min-max normalised per query,
        so B and C collapsed onto exactly 0.0 and 1.0 — an artefact of being
        the two lowest and highest in THIS batch, not a relevance judgement.
        Raw pairwise scores are kept so the caller's scale is the model's."""
        episodes = [self._episode("B", "episode B"), self._episode("C", "episode C")]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = episodes
        service = HybridRetrievalService.__new__(HybridRetrievalService)
        service.db = db
        service._reranker_model = MagicMock()
        service._reranker_probe_done = True
        service._reranker_model.predict.return_value = np.array([0.2, 0.9])

        result = await service._rerank_cross_encoder(
            "query", [("A", 0.1), ("B", 0.5), ("C", 0.5)], "a1")
        by_id = {ep_id: score for ep_id, score in result}
        assert by_id["B"] == pytest.approx(0.3 * 0.5 + 0.7 * 0.2)
        assert by_id["C"] == pytest.approx(0.3 * 0.5 + 0.7 * 0.9)
        assert "A" not in by_id, "a candidate with no content must not be scored"
        assert result[0][0] == "C", "the higher raw score must rank first"

    @pytest.mark.asyncio
    async def test_ranking_does_not_depend_on_numpy(self):
        """CONTRACT CHANGE. The NumPy branch existed only for the removed
        normalisation. Plain-Python float conversion is now the only path, so
        numpy's presence cannot change the ranking."""
        episodes = [self._episode("B", "text B"), self._episode("C", "text C")]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = episodes
        service = HybridRetrievalService.__new__(HybridRetrievalService)
        service.db = db
        service._reranker_model = MagicMock()
        service._reranker_probe_done = True
        service._reranker_model.predict.return_value = [0.2, 0.9]
        result = await service._rerank_cross_encoder(
            "q", [("B", 0.5), ("C", 0.5)], "a1")
        by_id = {ep_id: score for ep_id, score in result}
        assert by_id["B"] == pytest.approx(0.3 * 0.5 + 0.7 * 0.2)
        assert by_id["C"] == pytest.approx(0.3 * 0.5 + 0.7 * 0.9)


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

    def test_missing_torch_falls_back_to_cpu(self):
        # The NumPy guard this class used to assert is gone with the
        # normalisation it fed: float() is the only numeric path now, so numpy's
        # absence cannot change behaviour. The torch/CUDA guards remain live
        # because they select the rerank device.
        mod = self._reload(numpy=None, torch_mod=None)
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
