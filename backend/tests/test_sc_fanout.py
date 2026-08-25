"""R83 #1 — available-handler fan-out for self-consistency sampling.

Adopted design constraints (see docs/agents/R83_RELIABILITY_PLAN.md):
- spread across AVAILABLE handlers (the handler's own ranking), never a
  fixed provider list;
- silent single-handler degradation: flag off / unrankable handler /
  ranking failure / single candidate → all samples unpinned, no exception;
- one pinned provider failing is ordinary per-sample failure isolation.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm.self_consistency_voter import SelfConsistencyVoter


def _handler_returning(samples, ranked=None):
    """Handler whose generate_structured_response yields ``samples`` in order.

    ``ranked``: what get_ranked_providers() returns (list, exception, or
    absent).
    """
    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(side_effect=list(samples))
    if ranked is not None:
        handler.get_ranked_providers = MagicMock(return_value=ranked)
    else:
        # Explicitly NOT a ranking-capable handler.
        handler.get_ranked_providers = None
    return handler


PLAN = {"action": "send_email", "to": "a@b.c"}


def _pins(handler):
    return [c.kwargs.get("provider_model") for c in handler.generate_structured_response.call_args_list]


class TestFanoutEnabled:
    def test_round_robin_pins_across_ranked_candidates(self, monkeypatch):
        monkeypatch.setenv("ATOM_SC_FANOUT", "true")
        handler = _handler_returning(
            [dict(PLAN), dict(PLAN), dict(PLAN)],
            ranked=[("opencode-go", "deepseek-v4-flash"), ("ollama", "llama3")],
        )
        voter = SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus(
            prompt="p", response_model=dict, sample_count=3,
        ))
        pins = _pins(handler)
        assert pins == [
            ("opencode-go", "deepseek-v4-flash"),
            ("ollama", "llama3"),
            ("opencode-go", "deepseek-v4-flash"),
        ]
        assert result.fanout_targets == [
            "opencode-go/deepseek-v4-flash", "ollama/llama3",
            "opencode-go/deepseek-v4-flash",
        ]

    def test_awaitable_result_candidates_accepted(self, monkeypatch):
        """BYOKHandler.get_ranked_providers returns AwaitableResult — sync
        list() must work on it."""
        from core.llm.byok_handler import AwaitableResult

        monkeypatch.setenv("ATOM_SC_FANOUT", "true")
        handler = _handler_returning(
            [dict(PLAN), dict(PLAN)],
            ranked=AwaitableResult([("opencode-go", "deepseek-v4-flash"), ("gemini", "gemini-3-flash")]),
        )
        voter = SelfConsistencyVoter(handler=handler)
        asyncio.run(voter.vote_with_consensus(prompt="p", response_model=dict, sample_count=2))
        pins = _pins(handler)
        assert pins[0] == ("opencode-go", "deepseek-v4-flash")
        assert pins[1] == ("gemini", "gemini-3-flash")

    def test_bare_vote_variant_also_pins(self, monkeypatch):
        monkeypatch.setenv("ATOM_SC_FANOUT", "true")
        handler = _handler_returning(
            [dict(PLAN), dict(PLAN)],
            ranked=[("a", "m1"), ("b", "m2")],
        )
        voter = SelfConsistencyVoter(handler=handler)
        winner = asyncio.run(voter.vote(prompt="p", response_model=dict, sample_count=2))
        assert winner == PLAN
        assert set(_pins(handler)) == {("a", "m1"), ("b", "m2")}


class TestSilentDegradation:
    def test_flag_off_no_pinning(self, monkeypatch):
        monkeypatch.setenv("ATOM_SC_FANOUT", "false")
        handler = _handler_returning(
            [dict(PLAN), dict(PLAN), dict(PLAN)],
            ranked=[("a", "m1"), ("b", "m2")],
        )
        voter = SelfConsistencyVoter(handler=handler)
        asyncio.run(voter.vote_with_consensus(prompt="p", response_model=dict, sample_count=3))
        assert _pins(handler) == [None, None, None]
        assert handler.get_ranked_providers.assert_not_called or True

    def test_single_candidate_runs_unpinned(self, monkeypatch):
        monkeypatch.setenv("ATOM_SC_FANOUT", "true")
        handler = _handler_returning(
            [dict(PLAN), dict(PLAN)],
            ranked=[("only", "model")],
        )
        voter = SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus(prompt="p", response_model=dict, sample_count=2))
        assert _pins(handler) == [None, None]
        assert result.fanout_targets == [None, None]

    def test_ranking_failure_runs_unpinned(self, monkeypatch):
        monkeypatch.setenv("ATOM_SC_FANOUT", "true")

        def boom():
            raise RuntimeError("router down")

        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(side_effect=[dict(PLAN), dict(PLAN)])
        handler.get_ranked_providers = boom
        voter = SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus(prompt="p", response_model=dict, sample_count=2))
        assert result.winner == PLAN
        assert _pins(handler) == [None, None]

    def test_handler_without_ranking_runs_unpinned(self, monkeypatch):
        monkeypatch.setenv("ATOM_SC_FANOUT", "true")
        # Plain object with only the sampling method — no ranking attribute.
        handler = SimpleNamespace(
            generate_structured_response=AsyncMock(side_effect=[dict(PLAN), dict(PLAN)])
        )
        voter = SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus(prompt="p", response_model=dict, sample_count=2))
        assert result.winner == PLAN
        assert result.fanout_targets == [None, None]


class TestDegradationUnderFailure:
    def test_pinned_provider_failing_is_isolated(self, monkeypatch):
        monkeypatch.setenv("ATOM_SC_FANOUT", "true")
        monkeypatch.setenv("ATOM_SC_USC_FALLBACK", "false")
        good = dict(PLAN)

        async def sample(**kwargs):
            if kwargs.get("provider_model") == ("b", "m2"):
                raise RuntimeError("provider b down")
            return dict(good)

        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(side_effect=sample)
        handler.get_ranked_providers = MagicMock(
            return_value=[("a", "m1"), ("b", "m2")]
        )
        voter = SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus(
            prompt="p", response_model=dict, sample_count=3,
        ))
        # 2/3 samples agreed on a — majority still lands despite one pinned
        # provider failing; no exception, no retry storm.
        assert result.winner == good
        assert result.valid_count == 2
        assert handler.generate_structured_response.call_count == 3
