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
