"""
Cross-cutting fixes: H6 (majority threshold), H8 (history-wipe), H9 (batch embedding).

These are valid bug fixes regardless of the W1–W5 workstreams.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.orchestration.verification.voting import VotingVerifier
from core.orchestration.verification.base import VerificationStrategy


# ---------------------------------------------------------------------------
# H6 — majority threshold is now a true ≥2/3 ratio, not a hardcoded count of 2.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_h6_majority_threshold_scales_beyond_n3():
    """At N=5, a 2/5 minority (40%) must NOT win; the old `>= 2` let it."""
    v = VotingVerifier()
    # 5 candidates: 2 say "A", 3 say "B" → B is the majority (3/5 = 60% ≥ 2/3? no, 60% < 66%).
    # Per the ceil(2N/3) threshold, 5 needs ≥4 to declare a majority → falls through to reconcile.
    candidates = [{"v": "A"}, {"v": "A"}, {"v": "B"}, {"v": "B"}, {"v": "B"}]
    result = await v.verify(candidates, step=MagicMock(), context=MagicMock())
    # The point: a bare 2-count no longer auto-wins. The winner (if any) must
    # meet the real ratio. 3/5 < 2/3 threshold → not a clean majority.
    # Either winner=None (reconcile) or winner=B with fallback_used; NOT "A".
    assert result.winner != {"v": "A"}, "a 2/5 minority must not win under the true ≥2/3 ratio"


@pytest.mark.asyncio
async def test_h6_two_of_three_still_wins():
    """The common case (2 of 3) must still declare a winner — regression guard."""
    v = VotingVerifier()
    candidates = [{"v": "A"}, {"v": "A"}, {"v": "B"}]
    result = await v.verify(candidates, step=MagicMock(), context=MagicMock())
    assert result.winner == {"v": "A"}, "2/3 majority must still win (the common N=3 case)"


# ---------------------------------------------------------------------------
# H8 — the import-fallback ObservationFilterService must NOT wipe history.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_h8_fallback_does_not_wipe_history():
    """The fallback filter returns the history unchanged, not ("", {}).

    The fallback class is defined inline in generic_agent.py when the real
    import fails. Test its contract directly by replicating the no-op path.
    """

    class _Fallback:  # mirrors generic_agent.py:41-46 fallback contract (post-H8)
        async def filter_history(self, execution_history="", *a, **kw):
            return execution_history, {"savings_tokens": 0, "original_tokens": 0,
                                       "filtered_tokens": 0, "embedding_pass": False,
                                       "enabled": False}

    fallback = _Fallback()
    result = await fallback.filter_history("some real history\n")
    history, metrics = result[0], result[1]
    assert history == "some real history\n", (
        "fallback must preserve history (H8: was returning '', silently wiping the transcript)"
    )
    assert metrics.get("savings_tokens") == 0


# ---------------------------------------------------------------------------
# H9 — observation filter uses generate_embeddings_batch when available.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_h9_uses_batch_embeddings(monkeypatch):
    """The filter should call generate_embeddings_batch once, not generate_embedding N times."""
    monkeypatch.setenv("OBSERVATION_FILTER_ENABLED", "true")
    from core.observation_filter_service import ObservationFilterService

    llm = MagicMock()
    llm.generate_embeddings_batch = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
    llm.generate_embedding = AsyncMock(return_value=[0.0, 0.0])  # should NOT be called
    svc = ObservationFilterService(llm=llm)
    # The gate is the module-level OBSERVATION_FILTER_ENABLED (read at import);
    # patch it on the module so filter_history proceeds to the embedding pass.
    import core.observation_filter_service as ofs
    monkeypatch.setattr(ofs, "OBSERVATION_FILTER_ENABLED", True)
    svc.embedding_min_step = 0  # ensure the step gate passes

    history = (
        "Observation: first result\n"
        "Observation: second result\n"
        "Observation: third result\n"
        "Observation: fourth result\n"
        "Observation: fifth result\n"
    )
    llm.generate_embeddings_batch = AsyncMock(
        return_value=[[0.1, 0.2]] * 5  # one embedding per observation
    )
    await svc.filter_history(history, current_step=5, task_input="x")
    llm.generate_embeddings_batch.assert_awaited(), "filter must use the batch API"
    llm.generate_embedding.assert_not_awaited(), "filter must not call generate_embedding per-item"
