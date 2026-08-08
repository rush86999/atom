"""
P4 — Diversity-aware sampling + ReviewerVerifier (W3).

Two concerns:
1. Diversity-aware init (P4a): ``diversity_overlays`` rotates perspectives per
   sample; disabled by default (kill-switch parity).
2. ReviewerVerifier (P4b): the Virtual Biotech's "Scientific Reviewer" —
   evaluates the winner on addresses/evidence/thoroughness, accepts or signals
   re-delegation. NOT debate (never multi-round; fail-opens to the winner).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm.self_consistency_voter import SelfConsistencyVoter
from core.orchestration.verification import (
    ReviewerVerifier, VerificationOrchestrator, VerificationStrategy,
)


# ---------------------------------------------------------------------------
# P4a — diversity-aware sampling
# ---------------------------------------------------------------------------
def test_diversity_overlays_disabled_by_default():
    """Kill-switch parity: disabled → empty overlays (no behavior change)."""
    overlays = SelfConsistencyVoter.diversity_overlays(3, enabled=False)
    assert overlays == ["", "", ""], "disabled must produce empty overlays (parity)"


def test_diversity_overlays_enabled_rotates_perspectives():
    overlays = SelfConsistencyVoter.diversity_overlays(4, enabled=True)
    assert len(overlays) == 4
    assert len({o for o in overlays if o}) >= 2, "enabled must vary perspectives across samples"


# ---------------------------------------------------------------------------
# P4b — ReviewerVerifier
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reviewer_accepts_on_positive_verdict():
    llm = AsyncMock()
    llm.generate_response = AsyncMock(return_value='{"accept": true, "score": 0.9, "feedback": ""}')
    rv = ReviewerVerifier(llm_service=llm)
    result = await rv.verify(["the answer"], step=MagicMock(description="do X"), context=MagicMock())
    assert result.winner == "the answer", "accepted → winner returned"
    assert result.details["reviewed"] is True
    assert result.details["accepted"] is True


@pytest.mark.asyncio
async def test_reviewer_signals_redelegation_on_reject():
    """Rejected → winner is None so the orchestrator can re-delegate (NOT pick another)."""
    llm = AsyncMock()
    llm.generate_response = AsyncMock(
        return_value='{"accept": false, "score": 0.2, "feedback": "missing edge case"}'
    )
    rv = ReviewerVerifier(llm_service=llm)
    result = await rv.verify(["weak answer"], step=MagicMock(description="do X"), context=MagicMock())
    assert result.winner is None, "rejected → winner None (signal re-delegation, not a swap)"
    assert result.details["accepted"] is False
    assert "missing edge case" in result.reason


@pytest.mark.asyncio
async def test_reviewer_failopens_without_llm():
    """No LLM → can't review → accept the winner (never block the swarm)."""
    rv = ReviewerVerifier(llm_service=None)
    result = await rv.verify(["ans"], step=None, context=MagicMock())
    assert result.winner == "ans"
    assert result.details["reviewed"] is False


@pytest.mark.asyncio
async def test_reviewer_failopens_on_timeout():
    llm = AsyncMock()

    async def _slow(_):
        await asyncio.sleep(100)
    llm.generate_response = _slow
    rv = ReviewerVerifier(llm_service=llm, timeout_seconds=0.05)
    result = await rv.verify(["ans"], step=None, context=MagicMock())
    assert result.winner == "ans", "timeout → accept (fail-open), never block"


@pytest.mark.asyncio
async def test_reviewer_registered_in_orchestrator():
    """The REVIEW strategy must be wired into the dispatcher's verifier registry."""
    orch = VerificationOrchestrator()
    assert VerificationStrategy.REVIEW in orch._verifiers
    assert isinstance(orch._verifiers[VerificationStrategy.REVIEW], ReviewerVerifier)
