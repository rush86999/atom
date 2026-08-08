"""
P3 — Postcondition oracle + two-tier confidence (W2).

Two concerns:
1. Oracle: a mutating tool that lies ({verified:true} but the DB didn't change)
   is caught by the postcondition re-read (Postcept: never grade your own work).
2. Two-tier confidence: INTERNAL_HIGH is NOT credible; only EXTERNAL_VERIFIED is.
   coerce_match_level_for_storage defaults to AMBIGUOUS (RN3), and the new
   external tiers pass through unchanged.
"""
import pytest

from core.selector_confidence_service import (
    MatchConfidence, EXTERNAL_VERIFIED, EXTERNAL_REFUTED, NEEDS_EXTERNAL_VALIDATION,
    HIGH, PARTIAL, AMBIGUOUS, _VALID_LEVELS, coerce_match_level_for_storage,
)


# ---------------------------------------------------------------------------
# Two-tier confidence (P3c)
# ---------------------------------------------------------------------------
def test_internal_high_is_not_credible():
    """The Stanford credibility gate: internal self-assessment ≠ trustworthy."""
    mc = MatchConfidence(level=HIGH, score=0.9, rationale="x", provenance="internal")
    assert mc.is_high is True
    assert mc.is_credible is False, "INTERNAL_HIGH must NOT be auto-proceed-trusted"
    assert mc.needs_external_validation is True


def test_external_verified_is_credible():
    mc = MatchConfidence(
        level=EXTERNAL_VERIFIED, score=0.9, rationale="oracle re-derived",
        provenance="oracle", external_score=0.95, external_evidence="DB read-back",
    )
    assert mc.is_credible is True
    assert mc.needs_external_validation is False


def test_external_tiers_are_valid_levels():
    """RN3: the new tiers must be in _VALID_LEVELS (else coerce silently mangles them)."""
    assert NEEDS_EXTERNAL_VALIDATION in _VALID_LEVELS
    assert EXTERNAL_VERIFIED in _VALID_LEVELS
    assert EXTERNAL_REFUTED in _VALID_LEVELS


def test_coerce_defaults_to_ambiguous_not_partial():
    """RN3: AMBIGUOUS (route-to-human) is the safe default, not PARTIAL."""
    assert coerce_match_level_for_storage(None) == AMBIGUOUS
    assert coerce_match_level_for_storage("garbage") == AMBIGUOUS


def test_coerce_passes_new_tiers_through():
    assert coerce_match_level_for_storage(EXTERNAL_VERIFIED) == EXTERNAL_VERIFIED
    assert coerce_match_level_for_storage(NEEDS_EXTERNAL_VALIDATION) == NEEDS_EXTERNAL_VALIDATION


# ---------------------------------------------------------------------------
# Postcondition oracle (P3a)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_oracle_catches_lying_tool(monkeypatch):
    """A tool claims {verified:true} but the workflow row doesn't exist → oracle refutes."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    # Importing postcondition_verifiers registers the verifiers.
    import core.oracle.postcondition_verifiers  # noqa: F401
    from core.oracle import validate

    # Simulate a DB session where the workflow is absent (the tool lied).
    from unittest.mock import MagicMock
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    result = await validate("trigger_workflow", {"workflow_id": "wf-ghost", "db": db})
    assert result is not None
    assert result.verified is False, "oracle must refute a tool whose effect isn't in the DB"


@pytest.mark.asyncio
async def test_oracle_confirms_real_effect(monkeypatch):
    """A tool that actually created the workflow row → oracle confirms."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    import core.oracle.postcondition_verifiers  # noqa: F401
    from core.oracle import validate
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    wf = SimpleNamespace(id="wf-1", status="active")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = wf

    result = await validate("trigger_workflow", {"workflow_id": "wf-1", "db": db})
    assert result.verified is True
    assert "active" in result.evidence


@pytest.mark.asyncio
async def test_oracle_returns_none_for_unregistered_action():
    """Non-mutating actions have no postcondition → self-report stands."""
    from core.oracle import validate
    result = await validate("documents.search", {})
    assert result is None
