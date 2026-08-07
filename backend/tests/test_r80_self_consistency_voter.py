"""Round 80 — SelfConsistencyVoter coverage (feature #37, Workstream C).

TDD targets:
- B1: ``vote()`` popped per-sample kwargs (system_instruction, task_type,
  chain_id, image_payload) INSIDE the per-sample closure, so only the first
  sample received the caller's values and samples 2..N silently fell back to
  defaults. ``vote_with_consensus`` already hoists the pops; ``vote()`` was
  left behind. Fixed by hoisting to match.
- B2: ``is_irreversible`` only matched field NAMES (post Bug #13), so the
  most common action-plan shape — ``{"action": "send_email"}`` with the verb
  in the VALUE — was never flagged and the 3× sample gate never triggered.
  The module docstring promises value matching; the original C5 spec
  (tests/unit/llm/test_self_consistency_voter.py::test_C5) fails against the
  current code. Restored value PREFIX matching (startswith, not substring —
  Bug #13's false-positive protection is preserved).
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.self_consistency_voter import (
    LEVEL_AMBIGUOUS,
    LEVEL_HIGH,
    LEVEL_PARTIAL,
    SelfConsistencyVoter,
    VoteResult,
)


@pytest.fixture(autouse=True)
def _clean_mitigation_env(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("ATOM_") and (
            "VERIFIED" in k or "CASCADE" in k or "SELF_CONSISTENCY" in k
        ):
            monkeypatch.delenv(k, raising=False)


def _handler(*samples):
    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(side_effect=list(samples))
    return handler


def _plan(tag: str):
    """Distinct plans hash differently; identical tags hash identically."""
    return SimpleNamespace(action=tag)


# --------------------------------------------------------------------------- #
# Import invariant — the voter never executes anything.
# --------------------------------------------------------------------------- #
class TestImportInvariant:
    def test_module_does_not_import_executor(self):
        """AST check: voter imports only BYOKHandler + stdlib, never executors."""
        voter_path = (
            Path(__file__).resolve().parent.parent
            / "core" / "llm" / "self_consistency_voter.py"
        )
        tree = ast.parse(voter_path.read_text(encoding="utf-8"))
        forbidden = (
            "UnifiedActionExecutor",
            "unified_action_executor",
            "atom_meta_agent",
            "generic_agent",
            "from core.api",
            "import core.api",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for f in forbidden:
                    assert f not in module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        assert f not in alias.name


# --------------------------------------------------------------------------- #
# vote() — plain majority-vote variant
# --------------------------------------------------------------------------- #
class TestVote:
    async def test_majority_plan_wins(self):
        voter = SelfConsistencyVoter(handler=_handler(_plan("a"), _plan("a"), _plan("b")))
        winner = await voter.vote(prompt="p", response_model=dict)
        assert winner.action == "a"
        assert voter.handler.generate_structured_response.call_count == 3

    async def test_all_distinct_falls_back_to_lowest_temperature_sample(self):
        voter = SelfConsistencyVoter(handler=_handler(_plan("a"), _plan("b"), _plan("c")))
        winner = await voter.vote(prompt="p", response_model=dict)
        assert winner.action == "a"

    async def test_single_valid_sample_returned(self):
        voter = SelfConsistencyVoter(handler=_handler(None, _plan("a"), None))
        winner = await voter.vote(prompt="p", response_model=dict)
        assert winner.action == "a"

    async def test_all_samples_failed_returns_none(self):
        voter = SelfConsistencyVoter(handler=_handler(None, None, None))
        assert await voter.vote(prompt="p", response_model=dict) is None

    async def test_sample_failure_is_isolated(self):
        calls = {"n": 0}

        async def fake(**kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("transient")
            return _plan("a")

        handler = MagicMock()
        handler.generate_structured_response = fake
        voter = SelfConsistencyVoter(handler=handler)
        assert (await voter.vote(prompt="p", response_model=dict)).action == "a"

    async def test_sample_count_zero_clamps_to_one(self):
        voter = SelfConsistencyVoter(handler=_handler(_plan("a")))
        winner = await voter.vote(prompt="p", response_model=dict, sample_count=0)
        assert winner.action == "a"
        assert voter.handler.generate_structured_response.call_count == 1

    # ------------------------------------------------------------------ #
    # B1 regression: per-sample kwargs must reach ALL samples, not just
    # the first one.
    # ------------------------------------------------------------------ #
    async def test_b1_system_instruction_reaches_every_sample(self):
        handler = _handler(_plan("a"), _plan("a"), _plan("a"))
        voter = SelfConsistencyVoter(handler=handler)
        await voter.vote(
            prompt="p",
            response_model=dict,
            system_instruction="CUSTOM-SYS",
        )
        for call in handler.generate_structured_response.await_args_list:
            assert call.kwargs["system_instruction"] == "CUSTOM-SYS"

    async def test_b1_task_type_chain_id_image_payload_reach_every_sample(self):
        handler = _handler(_plan("a"), _plan("a"), _plan("a"))
        voter = SelfConsistencyVoter(handler=handler)
        await voter.vote(
            prompt="p",
            response_model=dict,
            task_type="agent_action",
            chain_id="chain-1",
            image_payload="data:img",
        )
        for call in handler.generate_structured_response.await_args_list:
            assert call.kwargs["task_type"] == "agent_action"
            assert call.kwargs["chain_id"] == "chain-1"
            assert call.kwargs["image_payload"] == "data:img"

    async def test_extra_kwargs_forwarded_to_all_samples(self):
        handler = _handler(_plan("a"), _plan("a"), _plan("a"))
        voter = SelfConsistencyVoter(handler=handler)
        await voter.vote(prompt="p", response_model=dict, foo="bar")
        for call in handler.generate_structured_response.await_args_list:
            assert call.kwargs["foo"] == "bar"

    async def test_samples_never_retrigger_moa(self):
        handler = _handler(_plan("a"), _plan("a"), _plan("a"))
        voter = SelfConsistencyVoter(handler=handler)
        await voter.vote(prompt="p", response_model=dict)
        for call in handler.generate_structured_response.await_args_list:
            assert call.kwargs["allow_moa"] is False

    async def test_per_sample_temperatures_match_spread(self):
        handler = _handler(_plan("a"), _plan("a"), _plan("a"))
        voter = SelfConsistencyVoter(handler=handler)
        await voter.vote(prompt="p", response_model=dict, temperature=0.7)
        temps = [c.kwargs["temperature"] for c in handler.generate_structured_response.await_args_list]
        assert temps == [0.6, 0.7, 0.8]


# --------------------------------------------------------------------------- #
# vote_with_consensus() — shadow + audit variant
# --------------------------------------------------------------------------- #
class TestVoteWithConsensus:
    async def test_returns_vote_result_metadata(self):
        voter = SelfConsistencyVoter(handler=_handler(_plan("a"), _plan("a"), _plan("b")))
        result = await voter.vote_with_consensus(prompt="p", response_model=dict)
        assert result.winner.action == "a"
        assert result.sample_count == 3
        assert result.valid_count == 3
        assert result.winner_count == 2
        assert result.distinct_hashes == 2
        assert abs(result.agreement_ratio - (2 / 3)) < 1e-9
        assert result.level == LEVEL_PARTIAL
        assert result.temperatures == [0.6, 0.7, 0.8]
        assert len(result.winner_hash) == 16
        assert len(result.prompt_hash) == 16

    async def test_unanimous_vote_is_high(self):
        voter = SelfConsistencyVoter(handler=_handler(_plan("a"), _plan("a"), _plan("a")))
        result = await voter.vote_with_consensus(prompt="p", response_model=dict)
        assert result.level == LEVEL_HIGH
        assert result.agreement_ratio == 1.0
        assert result.is_high is True
        assert result.requires_review is False

    async def test_all_failed_is_ambiguous_no_samples(self):
        voter = SelfConsistencyVoter(handler=_handler(None, None, None))
        result = await voter.vote_with_consensus(prompt="p", response_model=dict)
        assert result.winner is None
        assert result.is_no_samples is True
        assert result.level == LEVEL_AMBIGUOUS
        assert result.valid_count == 0
        assert result.agreement_ratio == 0.0

    async def test_single_valid_sample_reports_ratio_one(self):
        voter = SelfConsistencyVoter(handler=_handler(_plan("a"), None, None))
        result = await voter.vote_with_consensus(prompt="p", response_model=dict)
        assert result.winner is not None
        assert result.valid_count == 1
        assert result.agreement_ratio == 1.0

    async def test_even_count_tie_breaks_to_lowest_temperature(self):
        """4 samples, 2v2 tie → first-seen (lowest-temp) plan wins, partial."""
        voter = SelfConsistencyVoter(
            handler=_handler(_plan("a"), _plan("a"), _plan("b"), _plan("b"))
        )
        result = await voter.vote_with_consensus(prompt="p", response_model=dict, sample_count=4)
        assert result.winner.action == "a"
        assert result.winner_count == 2
        assert result.valid_count == 4
        assert abs(result.agreement_ratio - 0.5) < 1e-9
        assert result.level == LEVEL_PARTIAL  # 0.5 == partial threshold

    async def test_all_distinct_is_ambiguous(self):
        voter = SelfConsistencyVoter(handler=_handler(_plan("a"), _plan("b"), _plan("c")))
        result = await voter.vote_with_consensus(prompt="p", response_model=dict)
        assert result.winner.action == "a"  # lowest-temperature fallback
        assert result.winner_count == 1
        assert result.distinct_hashes == 3
        assert result.level == LEVEL_AMBIGUOUS
        assert result.requires_review is True

    async def test_prompt_hash_is_deterministic(self):
        h1 = await SelfConsistencyVoter(handler=_handler(_plan("a"), _plan("a"), _plan("a"))).vote_with_consensus(
            prompt="same prompt", response_model=dict
        )
        h2 = await SelfConsistencyVoter(handler=_handler(_plan("a"), _plan("a"), _plan("a"))).vote_with_consensus(
            prompt="same prompt", response_model=dict
        )
        assert h1.prompt_hash == h2.prompt_hash


# --------------------------------------------------------------------------- #
# Tri-state level mapping + VoteResult shape
# --------------------------------------------------------------------------- #
class TestTriStateLevel:
    def test_boundaries(self):
        level = SelfConsistencyVoter._level_from_agreement
        assert level(1.0) == LEVEL_HIGH
        assert level(0.85) == LEVEL_HIGH
        assert level(0.849) == LEVEL_PARTIAL
        assert level(0.5) == LEVEL_PARTIAL
        assert level(0.499) == LEVEL_AMBIGUOUS
        assert level(0.0) == LEVEL_AMBIGUOUS

    def test_env_thresholds_override(self, monkeypatch):
        monkeypatch.setenv("ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD", "0.95")
        level = SelfConsistencyVoter._level_from_agreement
        assert level(1.0) == LEVEL_HIGH
        assert level(0.667) == LEVEL_PARTIAL

    def test_temperatures_for_spread_and_recentering(self):
        assert SelfConsistencyVoter._temperatures_for(3) == [0.6, 0.7, 0.8]
        assert SelfConsistencyVoter._temperatures_for(5) == [0.5, 0.6, 0.7, 0.8, 0.9]
        assert SelfConsistencyVoter._temperatures_for(3, base=0.2) == [0.1, 0.2, 0.3]
        assert len(set(SelfConsistencyVoter._temperatures_for(4))) == 4

    def test_hash_sample_is_stable_across_field_order(self):
        h1 = SelfConsistencyVoter._hash_sample({"a": 1, "b": 2})
        h2 = SelfConsistencyVoter._hash_sample({"b": 2, "a": 1})
        assert h1 == h2
        assert SelfConsistencyVoter._hash_sample({"a": 1}) != h1


class TestVoteResult:
    def test_frozen(self):
        r = VoteResult(winner=None, agreement_ratio=0.0, level=LEVEL_AMBIGUOUS,
                       sample_count=3, valid_count=0, winner_count=0, distinct_hashes=0)
        with pytest.raises(Exception):
            r.level = LEVEL_HIGH  # type: ignore[misc]

    def test_requires_review_only_for_partial_ambiguous(self):
        high = VoteResult(winner=object(), agreement_ratio=1.0, level=LEVEL_HIGH,
                          sample_count=3, valid_count=3, winner_count=3, distinct_hashes=1)
        partial = VoteResult(winner=object(), agreement_ratio=0.66, level=LEVEL_PARTIAL,
                             sample_count=3, valid_count=3, winner_count=2, distinct_hashes=2)
        assert high.requires_review is False
        assert partial.requires_review is True

    def test_is_no_samples(self):
        r = VoteResult(winner=None, agreement_ratio=0.0, level=LEVEL_AMBIGUOUS,
                       sample_count=3, valid_count=0, winner_count=0, distinct_hashes=0)
        assert r.is_no_samples is True


# --------------------------------------------------------------------------- #
# is_irreversible — B2 regression + false-positive guards
# --------------------------------------------------------------------------- #
class TestIsIrreversible:
    # B2: the verb lives in the VALUE under a generic field name — the most
    # common plan shape. Must be flagged (matches the module docstring and the
    # original C5 spec).
    def test_b2_value_prefix_matching(self):
        assert SelfConsistencyVoter.is_irreversible({"action": "send_email"}) is True
        assert SelfConsistencyVoter.is_irreversible({"action_type": "create_user"}) is True
        assert SelfConsistencyVoter.is_irreversible({"operation": "delete_file"}) is True
        assert SelfConsistencyVoter.is_irreversible({"op": "transfer_funds"}) is True
        assert SelfConsistencyVoter.is_irreversible({"command": "publish"}) is True
        assert SelfConsistencyVoter.is_irreversible({"value": "bulk_delete"}) is True

    def test_key_prefix_matching(self):
        assert SelfConsistencyVoter.is_irreversible({"send_email": {"to": "a"}}) is True
        assert SelfConsistencyVoter.is_irreversible({"delete_file": "x"}) is True

    def test_read_only_verbs_not_flagged(self):
        assert SelfConsistencyVoter.is_irreversible({"action": "search"}) is False
        assert SelfConsistencyVoter.is_irreversible({"action": "browse"}) is False
        assert SelfConsistencyVoter.is_irreversible({"action": "get_user"}) is False
        assert SelfConsistencyVoter.is_irreversible({"action": "list_files"}) is False

    # Bug #13 false-positive guards: benign metadata fields must never trip
    # the gate, even when their values contain the verbs as substrings.
    def test_benign_metadata_fields_never_flagged(self):
        assert SelfConsistencyVoter.is_irreversible(
            {"created_at": "2026-01-01T00:00:00Z", "action": "search"}
        ) is False
        assert SelfConsistencyVoter.is_irreversible(
            {"updated_by": "create_user_role"}
        ) is False
        assert SelfConsistencyVoter.is_irreversible(
            {"last_payment_id": "pay_123", "note": "all good"}
        ) is False

    def test_substring_values_not_flagged(self):
        # Values containing a pattern mid-string must NOT match (prefix only).
        assert SelfConsistencyVoter.is_irreversible({"subject": "please delete_me later"}) is False
        assert SelfConsistencyVoter.is_irreversible({"title": "we deploy tomorrow"}) is False
        assert SelfConsistencyVoter.is_irreversible({"note": "see the create_user docs"}) is False

    def test_none_and_empty_plans_safe(self):
        assert SelfConsistencyVoter.is_irreversible(None) is False
        assert SelfConsistencyVoter.is_irreversible({}) is False

    def test_pydantic_style_objects(self):
        class _V2:
            def model_dump(self, *a, **k):
                return {"action": "send_email"}

        class _V1:
            def dict(self):
                return {"action_type": "update_record"}

        assert SelfConsistencyVoter.is_irreversible(_V2()) is True
        assert SelfConsistencyVoter.is_irreversible(_V1()) is True
        assert SelfConsistencyVoter.is_irreversible(_V2()) is True

    def test_scalar_plan_falls_back_to_value_field(self):
        assert SelfConsistencyVoter.is_irreversible("delete_file") is True
        assert SelfConsistencyVoter.is_irreversible("just a string") is False
