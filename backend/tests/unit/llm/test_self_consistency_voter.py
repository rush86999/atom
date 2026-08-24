"""Workstream C — self-consistency voter tests.

The voter is the lowest-level piece of Phase 2 hallucination mitigation:
it draws N samples at varying temperatures and returns the modal plan.
It never executes anything — execution is the caller's job.

The hard import invariant (test C1) is what keeps this module honest: the
voter may only import ``BYOKHandler`` and stdlib, never the executor or
any adapter. If that breaks, the voter becomes a hidden execution path
and the "execute winning plan exactly once" guarantee is at risk.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean_mitigation_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("ATOM_") and (
            "VERIFIED" in k or "CASCADE" in k or "SELF_CONSISTENCY" in k
        ):
            monkeypatch.delenv(k, raising=False)


# ---------------------------------------------------------------------------
# C1: import invariant — voter must not import the executor
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C1_voter_module_does_not_import_executor():
    """Static check: voter module imports only BYOKHandler + stdlib.

    This is the architectural firebreak between *deciding* an action and
    *executing* it. If the voter ever imports UnifiedActionExecutor (or any
    adapter), the "caller executes the winning plan exactly once"
    guarantee is at risk.
    """
    # Resolve the voter source path: backend/tests/unit/llm/test_*.py
    # → backend/core/llm/self_consistency_voter.py
    voter_path = (
        Path(__file__).resolve().parents[3]
        / "core"
        / "llm"
        / "self_consistency_voter.py"
    )
    source = voter_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_substrings = (
        "UnifiedActionExecutor",
        "unified_action_executor",
        "atom_meta_agent",
        "generic_agent",
        "from core.api",
        "import core.api",
    )

    # Check import-module strings inside ImportFrom / Import nodes.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for f in forbidden_substrings:
                assert f not in module, (
                    f"voter imports forbidden module '{module}' (matches '{f}')"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for f in forbidden_substrings:
                    assert f not in alias.name, (
                        f"voter imports forbidden name '{alias.name}' (matches '{f}')"
                    )

    # Note: we deliberately do NOT scan the raw source for forbidden
    # substrings — the voter's docstring references them as part of the
    # invariant contract. The AST-level check above is the real
    # enforcement: it catches actual import statements, not prose.


# ---------------------------------------------------------------------------
# C2: three samples with majority → modal plan returned
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_C2_three_samples_with_majority():
    """3 samples, 2 identical → the majority plan wins."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    plan_a = SimpleNamespace(action="send_email", target="alice")
    plan_b = SimpleNamespace(action="send_email", target="alice")  # same hash
    plan_c = SimpleNamespace(action="draft_email", target="bob")

    handler = MagicMock()
    # The voter awaits each call — use AsyncMock with side_effect.
    handler.generate_structured_response = AsyncMock(
        side_effect=[plan_a, plan_b, plan_c]
    )

    voter = SelfConsistencyVoter(handler=handler)
    winner = await voter.vote(
        prompt="send to alice",
        response_model=dict,
        system_instruction="sys",
    )

    assert winner is plan_a  # First-seen of the majority hash.
    assert handler.generate_structured_response.call_count == 3


# ---------------------------------------------------------------------------
# C3: all three disagree → first sample returned
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_C3_all_three_disagree_returns_first():
    """All samples distinct → fall back to the lowest-temperature sample."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    plan_a = SimpleNamespace(action="send_email", target="alice")
    plan_b = SimpleNamespace(action="send_email", target="bob")  # diff target
    plan_c = SimpleNamespace(action="draft_email", target="carol")

    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(
        side_effect=[plan_a, plan_b, plan_c]
    )

    voter = SelfConsistencyVoter(handler=handler)
    winner = await voter.vote(
        prompt="decide",
        response_model=dict,
        system_instruction="sys",
    )

    # First sample = lowest temperature (spread starts below base).
    assert winner is plan_a


# ---------------------------------------------------------------------------
# C4: vote executes the action exactly once (caller's responsibility)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_C4_vote_executes_action_exactly_once():
    """The voter must not call any executor. The caller runs the winner once.

    We model the caller's execute() as a stub and assert it is called
    exactly once with the winning plan. The voter never sees execute().
    """
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    plan = SimpleNamespace(action="send_email", target="alice")

    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(
        side_effect=[plan, plan, plan]
    )

    voter = SelfConsistencyVoter(handler=handler)

    # Caller's stub execute() — NOT something the voter knows about.
    execute_calls: list = []

    async def execute(plan):
        execute_calls.append(plan)

    # The caller (not the voter) is responsible for this:
    winner = await voter.vote(
        prompt="p", response_model=dict, system_instruction="sys"
    )
    await execute(winner)  # caller's responsibility

    assert len(execute_calls) == 1
    assert execute_calls[0] is plan
    # Voter made 3 LLM calls, caller made 1 executor call.
    assert handler.generate_structured_response.call_count == 3


# ---------------------------------------------------------------------------
# C5: is_irreversible detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C5_is_irreversible_detection():
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    # Irreversible verbs/prefixes — flagged.
    assert SelfConsistencyVoter.is_irreversible({"action_type": "send_email"}) is True
    assert SelfConsistencyVoter.is_irreversible({"action_type": "create_user"}) is True
    assert SelfConsistencyVoter.is_irreversible({"action_type": "update_record"}) is True
    assert SelfConsistencyVoter.is_irreversible({"action_type": "delete_file"}) is True
    assert SelfConsistencyVoter.is_irreversible({"action_type": "bulk_delete"}) is True
    assert SelfConsistencyVoter.is_irreversible({"action_type": "transfer_funds"}) is True
    assert SelfConsistencyVoter.is_irreversible({"action_type": "refund_charge"}) is True
    assert SelfConsistencyVoter.is_irreversible({"action_type": "payment"}) is True

    # Read-only verbs — not flagged.
    assert SelfConsistencyVoter.is_irreversible({"action_type": "search"}) is False
    assert SelfConsistencyVoter.is_irreversible({"action_type": "browse"}) is False
    assert SelfConsistencyVoter.is_irreversible({"action_type": "get_user"}) is False
    assert SelfConsistencyVoter.is_irreversible({"action_type": "list_files"}) is False

    # Pydantic-v1-style .dict() object.
    class _V1:
        def __init__(self):
            self.action_type = "send_email"

        def dict(self):
            return {"action_type": "send_email"}

    assert SelfConsistencyVoter.is_irreversible(_V1()) is True

    # None input — safe default is False.
    assert SelfConsistencyVoter.is_irreversible(None) is False


# ---------------------------------------------------------------------------
# C6: inert when flag off
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_C6_self_consistency_inert_when_flag_off(monkeypatch):
    """Flag off → LLMService.generate_structured must NOT dispatch to voter.

    We verify by patching the voter class and ensuring it is not
    instantiated when the env flag is unset.
    """
    # Flag is off by default (autouse fixture).
    from core.llm_service import LLMService

    # Patch the voter import site inside llm_service.generate_structured.
    with patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as voter_cls:
        svc = LLMService.__new__(LLMService)
        svc._workspace_id = "ws-1"
        svc._db = None
        svc._handler = None
        svc._tenant_id = "t-1"
        svc.is_available = lambda: True
        svc._get_handler = MagicMock(return_value=MagicMock())
        # The wrapper unpacks `handler.get_optimal_provider(...)` into
        # (provider_id, resolved_model). Configure both so the wrapper
        # reaches the handler call without raising.
        handler_mock = svc._get_handler.return_value
        handler_mock.analyze_query_complexity = MagicMock(return_value="standard")
        handler_mock.get_optimal_provider = MagicMock(return_value=("openai", "gpt-4o-mini"))
        # Short-circuit: return None from the handler so we don't reach voter.
        handler_mock.generate_structured_response = AsyncMock(return_value=None)

        # Even if the caller passes enable_self_consistency=True, the flag
        # resolver returns False so the voter is never instantiated.
        import asyncio

        await svc.generate_structured(
            prompt="p",
            response_model=dict,
            enable_self_consistency=True,
        )

        voter_cls.assert_not_called()


# ---------------------------------------------------------------------------
# C7: temperature spread has N values, all distinct
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C7_temperature_spread_has_n_values():
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    temps = SelfConsistencyVoter._temperatures_for(3)
    assert len(temps) == 3
    # All distinct — majority voting on identical temperatures is pointless.
    assert len(set(temps)) == 3


# ---------------------------------------------------------------------------
# C8: sample count should be configurable but odd preferred
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C8_sample_count_env_driven_default_is_three(monkeypatch):
    """Default sample count is 3 (from hallucination_config)."""
    from core import hallucination_config as hc

    assert hc.get_self_consistency_samples() == 3


@pytest.mark.unit
def test_C8_sample_count_can_be_overridden(monkeypatch):
    """Env var can override the sample count."""
    from core import hallucination_config as hc

    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_SAMPLES", "5")
    assert hc.get_self_consistency_samples() == 5


@pytest.mark.unit
def test_C8_sample_count_odd_preferred_via_temperature_spread(monkeypatch):
    """Odd counts give clean majorities; even counts still work via tie-break."""
    from core import hallucination_config as hc

    # Odd — clean spread.
    assert len(hc.get_temperature_spread(3)) == 3
    assert len(hc.get_temperature_spread(5)) == 5
    # Even — still well-defined (tie-break picks lowest temp).
    assert len(hc.get_temperature_spread(4)) == 4


# ---------------------------------------------------------------------------
# Bonus: per-sample failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_per_sample_failure_does_not_crash_vote():
    """If one sample raises, the vote proceeds with the survivors."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    plan = SimpleNamespace(action="search")  # reversible; just for hashing

    handler = MagicMock()

    async def fake_call(**kwargs):
        # Second call raises; others return plan.
        n = fake_call.calls
        fake_call.calls += 1
        if n == 1:
            raise RuntimeError("transient")
        return plan

    fake_call.calls = 0
    handler.generate_structured_response = fake_call

    voter = SelfConsistencyVoter(handler=handler)
    winner = await voter.vote(
        prompt="p", response_model=dict, system_instruction="sys"
    )

    assert winner is plan  # The 2 surviving samples both returned plan.


# ---------------------------------------------------------------------------
# Bonus: all samples return None → vote returns None
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_all_samples_none_returns_none():
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    handler = MagicMock()

    async def fake_call(**kwargs):
        return None

    handler.generate_structured_response = fake_call

    voter = SelfConsistencyVoter(handler=handler)
    winner = await voter.vote(
        prompt="p", response_model=dict, system_instruction="sys"
    )

    assert winner is None


# ===========================================================================
# Shadow + audit extensions — VoteResult, tri-state level, consensus method.
# These mirror the MatchConfidence pattern from selector_confidence_service
# and are additive on top of the C1-C8 + bonus tests above.
# ===========================================================================


# ---------------------------------------------------------------------------
# C9: vote_with_consensus returns VoteResult with correct fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_C9_vote_with_consensus_returns_metadata():
    """3 samples, 2 identical → VoteResult reports agreement 2/3 = 0.667."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    plan_a = SimpleNamespace(action="send_email", target="alice")
    plan_b = SimpleNamespace(action="send_email", target="alice")
    plan_c = SimpleNamespace(action="draft_email", target="bob")

    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(
        side_effect=[plan_a, plan_b, plan_c]
    )

    voter = SelfConsistencyVoter(handler=handler)
    result = await voter.vote_with_consensus(
        prompt="send to alice",
        response_model=dict,
        system_instruction="sys",
    )

    assert result.winner is plan_a
    assert result.sample_count == 3
    assert result.valid_count == 3
    assert result.winner_count == 2
    assert result.distinct_hashes == 2
    assert abs(result.agreement_ratio - (2 / 3)) < 1e-6
    assert result.temperatures == [0.6, 0.7, 0.8]
    assert result.winner_hash is not None
    assert result.prompt_hash is not None
    # 2/3 = 0.667 — partial band (between 0.50 and 0.85).
    assert result.level == "partial"
    assert result.is_high is False
    assert result.requires_review is True


# ---------------------------------------------------------------------------
# C10: tri-state level boundary mapping
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C10_level_from_agreement_boundaries():
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    level = SelfConsistencyVoter._level_from_agreement

    # Default thresholds: HIGH=0.85, PARTIAL=0.50.
    assert level(1.0) == "high"
    assert level(0.85) == "high"  # exact boundary inclusive
    assert level(0.849) == "partial"
    assert level(0.667) == "partial"  # 2/3 — the N=3 majority case
    assert level(0.50) == "partial"  # exact boundary inclusive
    assert level(0.499) == "ambiguous"
    assert level(0.333) == "ambiguous"  # 1/3 — all-distinct at N=3
    assert level(0.0) == "ambiguous"


@pytest.mark.unit
def test_C10_level_thresholds_env_overridable(monkeypatch):
    """Raising the HIGH threshold makes a unanimous N=3 vote still high,
    but a 2/3 vote falls through to partial."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD", "0.95")
    level = SelfConsistencyVoter._level_from_agreement
    # 3/3 = 1.0 still ≥ 0.95 → high.
    assert level(1.0) == "high"
    # 2/3 = 0.667 now falls below 0.95 → partial (still above 0.50).
    assert level(0.667) == "partial"


# ---------------------------------------------------------------------------
# C11: VoteResult properties — frozen, is_high, requires_review, is_no_samples
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C11_vote_result_is_frozen():
    """VoteResult must be immutable — mirrors MatchConfidence's frozen=True."""
    from core.llm.self_consistency_voter import VoteResult

    result = VoteResult(
        winner=None,
        agreement_ratio=0.0,
        level="ambiguous",
        sample_count=3,
        valid_count=0,
        winner_count=0,
        distinct_hashes=0,
    )
    with pytest.raises(Exception):
        result.level = "high"  # type: ignore[misc]


@pytest.mark.unit
def test_C11_vote_result_is_no_samples():
    from core.llm.self_consistency_voter import VoteResult

    no_samples = VoteResult(
        winner=None,
        agreement_ratio=0.0,
        level="ambiguous",
        sample_count=3,
        valid_count=0,
        winner_count=0,
        distinct_hashes=0,
    )
    assert no_samples.is_no_samples is True
    assert no_samples.is_high is False
    assert no_samples.requires_review is True  # ambiguous → review


@pytest.mark.unit
def test_C11_vote_result_high_does_not_require_review():
    from core.llm.self_consistency_voter import VoteResult

    high = VoteResult(
        winner=object(),
        agreement_ratio=1.0,
        level="high",
        sample_count=3,
        valid_count=3,
        winner_count=3,
        distinct_hashes=1,
    )
    assert high.is_high is True
    assert high.requires_review is False
    assert high.is_no_samples is False


# ---------------------------------------------------------------------------
# C12: vote_with_consensus with all-None samples returns ambiguous result
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_C12_vote_with_consensus_all_failed():
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    handler = MagicMock()

    async def fake_call(**kwargs):
        return None

    handler.generate_structured_response = fake_call

    voter = SelfConsistencyVoter(handler=handler)
    result = await voter.vote_with_consensus(
        prompt="p", response_model=dict, system_instruction="sys"
    )

    assert result.winner is None
    assert result.is_no_samples is True
    assert result.level == "ambiguous"
    assert result.valid_count == 0
    assert result.sample_count == 3


# ---------------------------------------------------------------------------
# C13: prompt hash is deterministic and short
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C13_prompt_hash_is_deterministic_and_short():
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    h1 = SelfConsistencyVoter._hash_prompt("send email to alice")
    h2 = SelfConsistencyVoter._hash_prompt("send email to alice")
    h3 = SelfConsistencyVoter._hash_prompt("send email to bob")

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16  # truncated SHA-256 for log readability


# ---------------------------------------------------------------------------
# C14: force-proposal flag is independently flag-gated
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C14_force_proposal_flag_resolvers(monkeypatch):
    """Force-proposal flag resolves via env var → False, like the others."""
    from core import hallucination_config as hc

    # Default off (autouse fixture).
    assert hc.is_self_consistency_force_proposal_enabled() is False

    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL", "true")
    assert hc.is_self_consistency_force_proposal_enabled() is True

    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL", "1")
    assert hc.is_self_consistency_force_proposal_enabled() is True

    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL", "false")
    assert hc.is_self_consistency_force_proposal_enabled() is False


# ---------------------------------------------------------------------------
# C15: hallucination_config — shadow + audit surface is additive
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C15_shadow_audit_resolvers_exist_and_default_safe():
    """Smoke check: shadow + audit additions are present and default-safe."""
    from core import hallucination_config as hc

    # Force-proposal toggle (shadow mode default).
    assert callable(hc.is_self_consistency_force_proposal_enabled)
    assert hc.is_self_consistency_force_proposal_enabled() is False

    # Tri-state thresholds mirror MATCH_CONFIDENCE_*_THRESHOLD defaults.
    assert callable(hc.get_self_consistency_high_threshold)
    assert hc.get_self_consistency_high_threshold() == 0.85
    assert callable(hc.get_self_consistency_partial_threshold)
    assert hc.get_self_consistency_partial_threshold() == 0.50

    # Thresholds are env-overridable.
    import os

    os.environ["ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD"] = "0.90"
    try:
        assert hc.get_self_consistency_high_threshold() == 0.90
    finally:
        del os.environ["ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD"]


# ---------------------------------------------------------------------------
# C16: SelfConsistencyVote model exists (regression check for the audit table)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_C16_self_consistency_vote_model_exists():
    """SelfConsistencyVote model must be importable and have the expected columns."""
    from core.models import SelfConsistencyVote

    cols = {c.name for c in SelfConsistencyVote.__table__.columns}
    expected = {
        "id", "tenant_id", "workspace_id", "timestamp", "created_at",
        "agent_id", "user_id", "session_id",
        "prompt_hash", "response_model_name",
        "sample_count", "valid_count", "winner_count", "distinct_hashes",
        "agreement_ratio", "level", "winner_hash", "temperatures",
        "gated", "proposal_id", "error_message", "metadata_json",
    }
    missing = expected - cols
    assert not missing, f"SelfConsistencyVote missing columns: {missing}"


# ---------------------------------------------------------------------------
# R83 #8: JCS (RFC 8785) canonicalization + hash-algo tagging
#
# Problem: json.dumps(sort_keys=True) does NOT give numeric equivalence
# ({"n": 1} != {"n": 1.0}) and sorts keys by code point, not UTF-16 units.
# RFC 8785 JCS fixes both. Historical rows hashed with the legacy algo are
# preserved: every new audit row records which algo produced its hashes so
# old/new rows stay interpretable without a data migration.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_R8_jcs_numeric_equivalence(monkeypatch):
    """1 vs 1.0 must collide under jcs hashing (the core RFC 8785 win)."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_HASH_ALGO", "jcs-sha256")
    h1 = SelfConsistencyVoter._hash_sample({"amount": 1})
    h2 = SelfConsistencyVoter._hash_sample({"amount": 1.0})
    assert h1 == h2


@pytest.mark.unit
def test_R8_legacy_algo_preserves_old_behavior(monkeypatch):
    """Kill switch ATOM_SC_HASH_ALGO=legacy restores byte-identical old hashes."""
    import hashlib
    import json as _json

    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_HASH_ALGO", "sha256-sortkeys")
    plan = {"b": 2, "a": 1.0}
    expected = hashlib.sha256(
        _json.dumps(plan, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    assert SelfConsistencyVoter._hash_sample(plan) == expected


@pytest.mark.unit
def test_R8_invalid_algo_falls_back_to_legacy(monkeypatch):
    """Invalid ATOM_SC_HASH_ALGO value degrades to legacy (safe default)."""
    import hashlib
    import json as _json

    from core.hallucination_config import get_sc_hash_algo
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_HASH_ALGO", "bogus")
    assert get_sc_hash_algo() == "sha256-sortkeys"
    plan = {"a": 1}
    expected = hashlib.sha256(
        _json.dumps(plan, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    assert SelfConsistencyVoter._hash_sample(plan) == expected


@pytest.mark.unit
def test_R8_hash_sample_never_raises_on_unserializable(monkeypatch):
    """Canonicalization failure falls back to legacy path instead of raising."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_HASH_ALGO", "jcs-sha256")
    weird = {"x": float("nan")}  # rfc8785 raises FloatDomainError on NaN
    h = SelfConsistencyVoter._hash_sample(weird)
    assert isinstance(h, str) and len(h) == 64


@pytest.mark.unit
def test_R8_vote_result_carries_hash_algo(monkeypatch):
    """VoteResult must record which hash algorithm grouped the samples."""
    from core.llm.self_consistency_voter import (
        LEVEL_HIGH,
        SelfConsistencyVoter,
        VoteResult,
    )

    class _Handler:
        async def generate_structured_response(self, **kw):
            return {"action": "noop", "amount": kw.get("_marker", 1)}

    monkeypatch.setenv("ATOM_SC_HASH_ALGO", "jcs-sha256")

    async def _run():
        voter = SelfConsistencyVoter(handler=_Handler())
        return await voter.vote_with_consensus(
            prompt="p",
            response_model=dict,
            sample_count=3,
            system_instruction="s",
        )

    import asyncio

    result = asyncio.run(_run())
    assert result.hash_algo == "jcs-sha256"
    assert result.level in {LEVEL_HIGH, "partial", "ambiguous"}


@pytest.mark.unit
def test_R8_jcs_groups_plans_legacy_fragments(monkeypatch):
    """Same plans differing only by int/float literal group as ONE under jcs."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_HASH_ALGO", "jcs-sha256")
    plans = [{"amount": 100}, {"amount": 100.0}, {"amount": 100.00}]
    hashes = {SelfConsistencyVoter._hash_sample(p) for p in plans}
    assert len(hashes) == 1


@pytest.mark.unit
def test_R17_scv_model_has_hash_algo_column():
    """SelfConsistencyVote audit model carries hash_algo (R83 #8)."""
    from core.models import SelfConsistencyVote

    cols = {c.name for c in SelfConsistencyVote.__table__.columns}
    assert "hash_algo" in cols


# ---------------------------------------------------------------------------
# R83 #2: Universal Self-Consistency judge fallback (Chen et al., ICML 2024)
#
# When every sample is distinct, the current path returns the lowest-temp
# sample. USC feeds all plans to a cheap judge and asks which is most
# consistent — recovering signal from otherwise-wasted votes. Opt-in via
# ATOM_SC_USC_FALLBACK (adds an LLM call; default off like
# ATOM_SANDBOX_JUDGE_ENABLED). Any judge failure degrades to the exact
# pre-existing lowest-temp behavior.
# ---------------------------------------------------------------------------


import asyncio


def _distinct_handler(plans):
    """Handler instance returning plan[i] on sample-call i (then repeating)."""

    class _H:
        def __init__(self):
            self.calls = 0

        async def generate_structured_response(self, **kw):
            self.calls += 1
            if kw.get("task_type") == "usc_judge":
                return {"best_index": kw.get("_usc_pick", 0)}
            idx = min(self.calls - 1, len(plans) - 1)
            return plans[idx]

    return _H()


@pytest.mark.unit
def test_R2_flag_off_returns_lowest_temp(monkeypatch):
    """Kill-switch parity: flag unset → all-distinct still returns samples[0]."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.delenv("ATOM_SC_USC_FALLBACK", raising=False)
    plans = [{"a": 1}, {"a": 2}, {"a": 3}]

    async def run():
        return await SelfConsistencyVoter(handler=_distinct_handler(plans)).vote_with_consensus(
            prompt="p", response_model=dict, sample_count=3, system_instruction="s"
        )

    result = asyncio.run(run())
    assert result.winner == plans[0]
    assert result.selection == "lowest-temp"


@pytest.mark.unit
def test_R2_flag_on_judge_picks_winner(monkeypatch):
    """Flag on → judge's best_index selects among the distinct plans."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_USC_FALLBACK", "true")
    plans = [{"a": 1}, {"a": 2}, {"a": 3}]

    async def run():
        h = _distinct_handler(plans)
        orig = h.generate_structured_response

        async def patched(**kw):
            if kw.get("task_type") == "usc_judge":
                return {"best_index": 1}
            return await orig(**kw)

        h.generate_structured_response = patched
        return await SelfConsistencyVoter(handler=h).vote_with_consensus(
            prompt="p", response_model=dict, sample_count=3, system_instruction="s"
        )

    result = asyncio.run(run())
    assert result.winner == plans[1]
    assert result.selection == "usc-judge"


@pytest.mark.unit
def test_R2_judge_failure_falls_back_lowest_temp(monkeypatch):
    """Judge raising / timing out must degrade to lowest-temp, never raise."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_USC_FALLBACK", "true")
    plans = [{"a": 1}, {"a": 2}, {"a": 3}]

    async def run():
        h = _distinct_handler(plans)
        orig = h.generate_structured_response

        async def boom(**kw):
            if kw.get("task_type") == "usc_judge":
                raise RuntimeError("provider down")
            return await orig(**kw)

        h.generate_structured_response = boom
        return await SelfConsistencyVoter(handler=h).vote_with_consensus(
            prompt="p", response_model=dict, sample_count=3, system_instruction="s"
        )

    result = asyncio.run(run())
    assert result.winner == plans[0]
    assert result.selection == "lowest-temp"


@pytest.mark.unit
def test_R2_judge_out_of_range_index_ignored(monkeypatch):
    """best_index outside [0, n) is invalid → lowest-temp fallback."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_USC_FALLBACK", "true")
    plans = [{"a": 1}, {"a": 2}, {"a": 3}]

    async def run():
        h = _distinct_handler(plans)
        orig = h.generate_structured_response

        async def bad(**kw):
            if kw.get("task_type") == "usc_judge":
                return {"best_index": 99}
            return await orig(**kw)

        h.generate_structured_response = bad
        return await SelfConsistencyVoter(handler=h).vote_with_consensus(
            prompt="p", response_model=dict, sample_count=3, system_instruction="s"
        )

    result = asyncio.run(run())
    assert result.winner == plans[0]
    assert result.selection == "lowest-temp"


@pytest.mark.unit
def test_R2_no_judge_call_on_majority(monkeypatch):
    """Flag on but majority exists → zero judge invocations."""
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    monkeypatch.setenv("ATOM_SC_USC_FALLBACK", "true")
    plans = [{"a": 1}, {"a": 1}, {"a": 2}]
    judge_calls = {"n": 0}

    class _Maj:
        async def generate_structured_response(self, **kw):
            if kw.get("task_type") == "usc_judge":
                judge_calls["n"] += 1
                return {"best_index": 0}
            return plans[min(getattr(_Maj, "calls", 0), 2)]

    # simple rotating handler
    state = {"i": 0}

    class _Rot:
        async def generate_structured_response(self, **kw):
            if kw.get("task_type") == "usc_judge":
                judge_calls["n"] += 1
                return {"best_index": 0}
            i = state["i"]
            state["i"] += 1
            return plans[min(i % 3, 2)]

    async def run():
        return await SelfConsistencyVoter(handler=_Rot()).vote_with_consensus(
            prompt="p", response_model=dict, sample_count=3, system_instruction="s"
        )

    result = asyncio.run(run())
    assert judge_calls["n"] == 0
    assert result.selection == "majority"
