"""R83 #6 — soft self-consistency (ACL 2024), shadow-first.

Contract (docs/agents/R83_RELIABILITY_PLAN.md #6):
- weight = exp(mean token logprob); unstamped samples weigh 1.0 (hard vote);
- the weighted majority is computed ALONGSIDE the hard majority — on
  disagreement the vote follows the hard winner and logs
  ``llm_soft_sc.shadow`` (promotion to soft requires the eval gate);
- the handler stamps ``_atom_mean_logprob`` from the instructor raw
  response's logprobs and requests logprobs only when ATOM_SC_SOFT is on.
"""
import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm.self_consistency_voter import SelfConsistencyVoter


def _sample(plan, mean_logprob=None):
    s = SimpleNamespace(**plan)
    if mean_logprob is not None:
        s._atom_mean_logprob = mean_logprob
    return s


class TestSampleWeight:
    def test_weight_is_exp_of_mean_logprob(self):
        assert SelfConsistencyVoter._sample_weight(_sample({"a": 1}, -0.5)) == pytest.approx(math.exp(-0.5))

    def test_unstamped_sample_weighs_one(self):
        assert SelfConsistencyVoter._sample_weight(_sample({"a": 1})) == 1.0
        assert SelfConsistencyVoter._sample_weight({"a": 1}) == 1.0  # plain dict

    def test_extreme_logprob_does_not_overflow(self):
        assert SelfConsistencyVoter._sample_weight(_sample({"a": 1}, -1e6)) == pytest.approx(0.0)
        assert SelfConsistencyVoter._sample_weight(_sample({"a": 1}, "bad")) == 1.0


class TestShadowSoftVote:
    def _voter(self, samples):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(side_effect=list(samples))
        handler.get_ranked_providers = None
        return SelfConsistencyVoter(handler=handler)

    def test_disagreement_follows_hard_winner_and_logs_shadow(self, monkeypatch, caplog):
        monkeypatch.setenv("ATOM_SC_SOFT", "true")
        # Hard majority: A twice, B once. Weights: B's single sample is
        # near-certain (exp(-0.01)≈0.99), A's are weak (exp(-5)≈0.0067) —
        # the WEIGHTED winner flips to B. Shadow must follow A (hard).
        a1 = _sample({"plan": "A"}, -5.0)
        a2 = _sample({"plan": "A"}, -5.0)
        b1 = _sample({"plan": "B"}, -0.01)
        voter = self._voter([a1, a2, b1])
        with caplog.at_level("WARNING", logger="core.llm.self_consistency_voter"):
            result = asyncio.run(voter.vote_with_consensus(
                prompt="p", response_model=dict, sample_count=3,
            ))
        assert result.winner.plan == "A"  # hard winner
        assert result.winner_count == 2
        assert any("llm_soft_sc.shadow" in r.message for r in caplog.records)

    def test_agreement_logs_info_no_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("ATOM_SC_SOFT", "true")
        a1 = _sample({"plan": "A"}, -0.1)
        a2 = _sample({"plan": "A"}, -0.2)
        b1 = _sample({"plan": "B"}, -3.0)
        voter = self._voter([a1, a2, b1])
        with caplog.at_level("INFO", logger="core.llm.self_consistency_voter"):
            result = asyncio.run(voter.vote_with_consensus(
                prompt="p", response_model=dict, sample_count=3,
            ))
        assert result.winner.plan == "A"
        assert any("soft and hard winners agree" in r.message for r in caplog.records)
        assert not any("llm_soft_sc.shadow: soft winner" in r.message for r in caplog.records)

    def test_flag_off_no_soft_computation(self, monkeypatch, caplog):
        monkeypatch.setenv("ATOM_SC_SOFT", "false")
        a1 = _sample({"plan": "A"}, -5.0)
        a2 = _sample({"plan": "A"}, -5.0)
        b1 = _sample({"plan": "B"}, -0.01)
        voter = self._voter([a1, a2, b1])
        with caplog.at_level("INFO", logger="core.llm.self_consistency_voter"):
            asyncio.run(voter.vote_with_consensus(prompt="p", response_model=dict, sample_count=3))
        assert not any("llm_soft_sc.shadow" in r.message for r in caplog.records)

    def test_all_unstamped_is_noop(self, monkeypatch, caplog):
        monkeypatch.setenv("ATOM_SC_SOFT", "true")
        voter = self._voter([_sample({"plan": "A"}), _sample({"plan": "A"}), _sample({"plan": "B"})])
        with caplog.at_level("INFO", logger="core.llm.self_consistency_voter"):
            result = asyncio.run(voter.vote_with_consensus(
                prompt="p", response_model=dict, sample_count=3,
            ))
        assert result.winner.plan == "A"
        assert not any("llm_soft_sc.shadow" in r.message for r in caplog.records)


class TestHandlerStamping:
    def test_stamp_sets_mean_logprob_from_raw_response(self):
        from core.llm.byok_handler import BYOKHandler

        raw = SimpleNamespace(choices=[SimpleNamespace(
            logprobs=SimpleNamespace(content=[
                SimpleNamespace(logprob=-0.5), SimpleNamespace(logprob=-1.5),
            ])
        )])
        result = SimpleNamespace(_raw_response=raw, plan="A")
        BYOKHandler._stamp_sample_logprob(result)
        assert result._atom_mean_logprob == pytest.approx(-1.0)

    def test_no_logprobs_no_stamp(self):
        from core.llm.byok_handler import BYOKHandler

        result = SimpleNamespace(_raw_response=SimpleNamespace(choices=[SimpleNamespace(logprobs=None)]))
        BYOKHandler._stamp_sample_logprob(result)
        assert not hasattr(result, "_atom_mean_logprob")

        result2 = SimpleNamespace()  # no raw response at all
        BYOKHandler._stamp_sample_logprob(result2)
        assert not hasattr(result2, "_atom_mean_logprob")

    def test_structured_call_requests_logprobs_only_when_enabled(self, monkeypatch):
        """The instructor create call gains logprobs=True only under ATOM_SC_SOFT."""
        from types import SimpleNamespace as NS
        from tests.test_covpush_byok_gen import make_handler, patch_session, pro_tenant_db

        captured = {}

        class _FakeInstructorClient:
            def __init__(self, client):
                pass

            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        captured.update(kwargs)
                        parsed = NS(plan="x")
                        parsed._raw_response = NS(
                            choices=[NS(logprobs=NS(content=[NS(logprob=-0.25)]))],
                        )
                        return parsed

        import core.llm.byok_handler as mod

        monkeypatch.setattr(mod.instructor, "from_openai", lambda client: _FakeInstructorClient(client))

        handler = make_handler()
        handler.clients = {"p1": object()}
        handler.get_ranked_providers = AsyncMock(return_value=[("p1", "m1")])

        # pro_tenant_db's workspace mock lacks .id for the plan lookup —
        # extend it with one (the lookup only needs it to exist).
        monkeypatch.setenv("ATOM_SC_SOFT", "true")
        with patch_session(pro_tenant_db()):
            result = asyncio.run(handler.generate_structured_response(
                prompt="p", system_instruction="s", response_model=dict,
            ))
        assert captured.get("logprobs") is True
        assert getattr(result, "_atom_mean_logprob", None) == pytest.approx(-0.25)

        # Flag off → no logprobs kwarg, no stamp.
        captured.clear()
        monkeypatch.setenv("ATOM_SC_SOFT", "false")
        with patch_session(pro_tenant_db()):
            result2 = asyncio.run(handler.generate_structured_response(
                prompt="p", system_instruction="s", response_model=dict,
            ))
        assert "logprobs" not in captured
        assert not hasattr(result2, "_atom_mean_logprob")
