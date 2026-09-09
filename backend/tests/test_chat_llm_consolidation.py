"""Chat-path LLM consolidation tests (2026-09-09).

One chat message fired ~14 LLM completions; research (ESC arXiv 2401.10480,
difficulty-adaptive SC NAACL 2025, MoA cost arXiv 2409.07487) says most of
that spend buys nothing on ordinary turns. Covers the consolidation:

1. ESC-adaptive verify panel — 1 judge sample first; full N-sample vote
   only when the first verdict is NOT clearly grounded; USC judge only in
   enforce mode (its shadow pick was recorded but could change nothing).
2. ``allow_usc_judge`` on the voter — skipped flag-off, preserved default.
3. Tool-plan routing fields — planner classification replaces the NLU LLM
   parse when confident; falls back otherwise.
4. ``is_high_stakes_turn`` — the verify panel's documented scope rule.
5. MoA default-off — explicit opt-in, so a second provider can never
   silently multiply chat-path structured calls 1→N+1.
"""

import os
os.environ.setdefault("TESTING", "1")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.verify_panel as vp
from core.chat_tool_planner import ToolPlan
from core.hallucination_config import is_moa_enabled, is_verify_adaptive_enabled
from core.llm.self_consistency_voter import SelfConsistencyVoter
from core.verify_panel import VerifyVerdict, is_high_stakes_turn, verify_reply


@pytest.fixture(autouse=True)
def _no_run_record():
    """Keep panel verdicts out of the DB in unit tests."""
    with patch("core.verify_panel._schedule_run_record"):
        yield


@pytest.fixture(autouse=True)
def _runtime_defaults(monkeypatch):
    """Deterministic flag resolution: env unset + empty settings DB."""
    monkeypatch.delenv("ATOM_VERIFY_ADAPTIVE", raising=False)
    monkeypatch.delenv("ATOM_MOA_ENABLED", raising=False)
    monkeypatch.setenv("ATOM_SC_FANOUT", "false")
    with patch("core.runtime_settings._db_snapshot", return_value={}):
        yield


def _vote_result(winner_grounded=True, valid_count=1, agreement=1.0, level="high"):
    winner = VerifyVerdict(
        grounded=winner_grounded,
        unsupported_claims=[] if winner_grounded else ["claim X"],
        note="",
    )
    return SimpleNamespace(
        winner=winner,
        agreement_ratio=agreement,
        level=level,
        valid_count=valid_count,
        fanout_targets=[None],
    )


def _mock_voter(stage1, full):
    """verify_reply constructs its own voter — patch the class. Stage-1
    calls (sample_count=1) get ``stage1``; full-panel calls get ``full``."""
    voter = MagicMock()
    calls = {"n": 0}

    async def _vote(**kwargs):
        calls["n"] += 1
        if kwargs.get("sample_count") == 1:
            if isinstance(stage1, Exception):
                raise stage1
            return stage1
        return full

    voter.vote_with_consensus = AsyncMock(side_effect=_vote)
    return voter, calls


# ---------------------------------------------------------------------------
# 1. ESC-adaptive verify_reply
# ---------------------------------------------------------------------------

class TestAdaptiveVerifyReply:
    @pytest.mark.asyncio
    async def test_grounded_first_sample_stops_at_one_call(self, monkeypatch):
        monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "true")
        voter, calls = _mock_voter(_vote_result(True, 1), _vote_result(True, 3))
        with patch.object(vp, "SelfConsistencyVoter", return_value=voter):
            result = await verify_reply(
                "answer", "evidence", handler=MagicMock(), enforce=False)
        assert result["ran"] is True
        assert result["grounded"] is True
        assert result["samples"] == 1
        assert calls["n"] == 1
        kwargs = voter.vote_with_consensus.await_args_list[0].kwargs
        assert kwargs["sample_count"] == 1
        assert kwargs["allow_usc_judge"] is False

    @pytest.mark.asyncio
    async def test_ungrounded_first_sample_runs_full_panel(self, monkeypatch):
        monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "true")
        voter, calls = _mock_voter(_vote_result(False, 1), _vote_result(False, 3, 0.67, "high"))
        with patch.object(vp, "SelfConsistencyVoter", return_value=voter):
            result = await verify_reply(
                "answer", "evidence", handler=MagicMock(), enforce=False)
        assert result["ran"] is True
        assert result["grounded"] is False
        assert result["samples"] == 3
        assert calls["n"] == 2
        full_kwargs = voter.vote_with_consensus.await_args_list[1].kwargs
        assert full_kwargs["sample_count"] == 3
        # Shadow mode: no USC judge even on the full panel.
        assert full_kwargs["allow_usc_judge"] is False

    @pytest.mark.asyncio
    async def test_enforce_mode_allows_usc_judge_on_full_panel(self, monkeypatch):
        monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "true")
        voter, _ = _mock_voter(_vote_result(False, 1), _vote_result(True, 3))
        with patch.object(vp, "SelfConsistencyVoter", return_value=voter):
            await verify_reply(
                "answer", "evidence", handler=MagicMock(), enforce=True)
        full_kwargs = voter.vote_with_consensus.await_args_list[1].kwargs
        assert full_kwargs["allow_usc_judge"] is True

    @pytest.mark.asyncio
    async def test_stage1_failure_falls_back_to_full_panel(self, monkeypatch):
        monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "true")
        voter, calls = _mock_voter(RuntimeError("transient"), _vote_result(True, 3))
        with patch.object(vp, "SelfConsistencyVoter", return_value=voter):
            result = await verify_reply(
                "answer", "evidence", handler=MagicMock(), enforce=False)
        assert result["ran"] is True
        assert calls["n"] == 2

    @pytest.mark.asyncio
    async def test_adaptive_off_restores_fixed_panel(self, monkeypatch):
        monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "false")
        voter, calls = _mock_voter(None, _vote_result(True, 3))
        with patch.object(vp, "SelfConsistencyVoter", return_value=voter):
            result = await verify_reply(
                "answer", "evidence", handler=MagicMock(), enforce=False)
        assert result["ran"] is True
        assert result["samples"] == 3
        assert calls["n"] == 1
        kwargs = voter.vote_with_consensus.await_args_list[0].kwargs
        assert kwargs["sample_count"] == 3

    def test_adaptive_flag_defaults_on(self):
        assert is_verify_adaptive_enabled() is True


# ---------------------------------------------------------------------------
# 2. Voter allow_usc_judge
# ---------------------------------------------------------------------------

class TestVoterUscJudgeGate:
    def _voter_with_distinct_samples(self, n=3):
        samples = [SimpleNamespace(action=f"distinct-{i}") for i in range(n)]
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(side_effect=samples)
        return SelfConsistencyVoter(handler=handler, tenant_id="t"), handler

    @pytest.mark.asyncio
    async def test_usc_judge_skipped_when_disallowed(self):
        voter, handler = self._voter_with_distinct_samples()
        with patch.object(voter, "_usc_judge_pick", new_callable=AsyncMock) as judge:
            result = await voter.vote_with_consensus(
                prompt="p", response_model=SimpleNamespace,
                sample_count=3, allow_usc_judge=False)
        judge.assert_not_awaited()
        assert result.selection == "lowest-temp"

    @pytest.mark.asyncio
    async def test_usc_judge_runs_by_default(self):
        voter, handler = self._voter_with_distinct_samples()
        with patch.object(voter, "_usc_judge_pick",
                          new_callable=AsyncMock, return_value=1) as judge:
            result = await voter.vote_with_consensus(
                prompt="p", response_model=SimpleNamespace, sample_count=3)
        judge.assert_awaited_once()
        assert result.selection == "usc-judge"


# ---------------------------------------------------------------------------
# 3. Tool-plan routing fields
# ---------------------------------------------------------------------------

class TestToolPlanRoutingFields:
    def test_toolplan_parses_new_fields(self):
        plan = ToolPlan.model_validate({
            "use_tool": True, "service": "outlook", "intent": "search",
            "query": "quote", "suggested_intent": "search_request",
            "routing_confidence": 0.9,
        })
        assert plan.suggested_intent == "search_request"
        assert plan.routing_confidence == pytest.approx(0.9)

    def test_toolplan_new_fields_optional(self):
        plan = ToolPlan.model_validate({"use_tool": False})
        assert plan.suggested_intent is None
        assert plan.routing_confidence is None

    def test_toolplan_coerces_quoted_confidence(self):
        """Models emit quoted numbers through tool-call arguments; a strict
        float rejection sends instructor into a regeneration loop that
        burns the planner's entire time budget (live 2026-09-09)."""
        plan = ToolPlan.model_validate({"routing_confidence": "0.9"})
        assert plan.routing_confidence == pytest.approx(0.9)
        assert ToolPlan.model_validate(
            {"routing_confidence": "not-a-number"}).routing_confidence is None

    def _classify(self, plan):
        """Call the orchestrator helper unbound — it touches nothing on self."""
        from integrations.chat_orchestrator import ChatOrchestrator
        return ChatOrchestrator._intent_from_tool_plan(SimpleNamespace(), plan)

    def test_confident_label_replaces_nlu(self):
        plan = ToolPlan(suggested_intent="search_request", routing_confidence=0.9)
        intent = self._classify(plan)
        assert intent is not None
        assert intent["primary_intent"].value == "search_request"
        assert intent["confidence"] == pytest.approx(0.9)
        assert intent["source"] == "tool_plan"

    def test_agent_request_label_preserved(self):
        """AGENT routing must survive the consolidation — it triggers the
        meta-agent loop."""
        from integrations.chat_orchestrator import ChatIntent
        plan = ToolPlan(suggested_intent="agent_request", routing_confidence=0.8)
        intent = self._classify(plan)
        assert intent["primary_intent"] is ChatIntent.AGENT_REQUEST

    def test_low_confidence_falls_back_to_nlu(self):
        plan = ToolPlan(suggested_intent="search_request", routing_confidence=0.4)
        assert self._classify(plan) is None

    def test_missing_label_falls_back_to_nlu(self):
        assert self._classify(ToolPlan()) is None

    def test_unknown_label_falls_back_to_nlu(self):
        plan = ToolPlan(suggested_intent="book_a_venue", routing_confidence=0.99)
        assert self._classify(plan) is None

    def test_none_plan_falls_back_to_nlu(self):
        assert self._classify(None) is None


# ---------------------------------------------------------------------------
# 4. Panel scope rule
# ---------------------------------------------------------------------------

class TestHighStakesScope:
    def test_mission_critical_always_high_stakes(self):
        assert is_high_stakes_turn("simple", True) is True
        assert is_high_stakes_turn(None, True) is True

    def test_top_two_complexity_tiers(self):
        assert is_high_stakes_turn("complex", False) is True
        assert is_high_stakes_turn("advanced", False) is True

    def test_ordinary_turns_are_not(self):
        assert is_high_stakes_turn("simple", False) is False
        assert is_high_stakes_turn("moderate", False) is False
        assert is_high_stakes_turn(None, False) is False


# ---------------------------------------------------------------------------
# 5. MoA default-off
# ---------------------------------------------------------------------------

class TestMoaDefaultOff:
    def test_moa_defaults_off(self):
        assert is_moa_enabled() is False

    def test_moa_explicit_opt_in(self, monkeypatch):
        monkeypatch.setenv("ATOM_MOA_ENABLED", "true")
        assert is_moa_enabled() is True
