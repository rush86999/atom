"""Wiring tests for the stage router inside the GenericAgent ReAct loop.

Verifies the shadow/enforce contract at the seam: model-type override,
handoff-note injection, explicit-model protection, and fail-open behavior.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.generic_agent import GenericAgent
from core.llm.stage_router import (
    CAPABLE,
    EFFICIENT,
    DecisionSource,
    StageDecision,
)
from core.react_models import ReActStep


def make_decision(group: str, handoff: str | None = None) -> StageDecision:
    return StageDecision(
        selected_group=group,
        applied_group=group,
        default_group=EFFICIENT,
        split_group=None,
        confidence=0.9,
        source=DecisionSource.DIMENSIONS.value,
        rationale=f"stage_router selected {group} (confidence 0.900, dimensions)",
        handoff_note=handoff,
    )


class FakeStageRouter:
    def __init__(self, enabled: bool = True, enforce: bool = False, decision=None):
        self.enabled = enabled
        self.enforce = enforce
        self._decision = decision

    async def decide_for_history(self, *args, **kwargs):
        return self._decision


def build_agent(llm: AsyncMock) -> GenericAgent:
    """GenericAgent with only the attrs _react_step touches, no DB, no LLM."""
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "test-agent"
    agent.name = "Test Agent"
    agent.workspace_id = "default"
    agent.config = {}
    agent.system_prompt = "You are a test agent."
    agent.allowed_tools = "*"
    agent.vision_enabled = False
    agent.last_screenshot = None
    agent.session_tools = []
    agent._custom_actions = {}
    agent._custom_action_specs = {}
    agent._run_maturity = None
    agent._stage_group = None
    agent.mcp = AsyncMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.llm = llm
    agent.reflection_service = AsyncMock()
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    agent.canvas_summary_service = AsyncMock()
    return agent


@pytest.fixture
def llm_mock() -> AsyncMock:
    llm = AsyncMock()
    llm.generate_structured = AsyncMock(
        return_value=ReActStep(thought="done", final_answer="ok")
    )
    return llm


@pytest.mark.asyncio
async def test_shadow_mode_keeps_model_and_skips_handoff(llm_mock, monkeypatch) -> None:
    decision = make_decision(CAPABLE, handoff="ROUTING HANDOFF: capable tier")
    monkeypatch.setattr(
        "core.llm.stage_router.get_stage_router",
        lambda: FakeStageRouter(enabled=True, enforce=False, decision=decision),
    )
    agent = build_agent(llm_mock)
    await agent._react_step("do a thing", {}, "")
    call_kwargs = llm_mock.generate_structured.call_args.kwargs
    assert call_kwargs["model"] == "auto"  # shadow: untouched
    assert "ROUTING HANDOFF" not in call_kwargs["system_instruction"]


@pytest.mark.asyncio
async def test_enforce_capable_maps_to_quality_with_handoff(llm_mock, monkeypatch) -> None:
    decision = make_decision(CAPABLE, handoff="ROUTING HANDOFF: capable tier")
    monkeypatch.setattr(
        "core.llm.stage_router.get_stage_router",
        lambda: FakeStageRouter(enabled=True, enforce=True, decision=decision),
    )
    agent = build_agent(llm_mock)
    agent._stage_group = EFFICIENT  # group switch → handoff fires
    await agent._react_step("do a thing", {}, "")
    call_kwargs = llm_mock.generate_structured.call_args.kwargs
    assert call_kwargs["model"] == "quality"
    assert "ROUTING HANDOFF" in call_kwargs["system_instruction"]


@pytest.mark.asyncio
async def test_enforce_efficient_maps_to_fast(llm_mock, monkeypatch) -> None:
    decision = make_decision(EFFICIENT)
    monkeypatch.setattr(
        "core.llm.stage_router.get_stage_router",
        lambda: FakeStageRouter(enabled=True, enforce=True, decision=decision),
    )
    agent = build_agent(llm_mock)
    await agent._react_step("do a thing", {}, "")
    assert llm_mock.generate_structured.call_args.kwargs["model"] == "fast"


@pytest.mark.asyncio
async def test_disabled_router_leaves_model_untouched(llm_mock, monkeypatch) -> None:
    monkeypatch.setattr(
        "core.llm.stage_router.get_stage_router",
        lambda: FakeStageRouter(enabled=False, enforce=False, decision=None),
    )
    agent = build_agent(llm_mock)
    await agent._react_step("do a thing", {}, "")
    assert llm_mock.generate_structured.call_args.kwargs["model"] == "auto"


@pytest.mark.asyncio
async def test_explicit_model_name_is_never_overridden(llm_mock, monkeypatch) -> None:
    decision = make_decision(CAPABLE, handoff="ROUTING HANDOFF: capable tier")
    monkeypatch.setattr(
        "core.llm.stage_router.get_stage_router",
        lambda: FakeStageRouter(enabled=True, enforce=True, decision=decision),
    )
    agent = build_agent(llm_mock)
    await agent._react_step("do a thing", {}, "", {"optimization": {"model": "gpt-4o"}})
    call_kwargs = llm_mock.generate_structured.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"  # explicit pin wins
    assert "ROUTING HANDOFF" not in call_kwargs["system_instruction"]


@pytest.mark.asyncio
async def test_router_failure_fails_open(llm_mock, monkeypatch) -> None:
    def boom():
        raise RuntimeError("router exploded")

    monkeypatch.setattr("core.llm.stage_router.get_stage_router", boom)
    agent = build_agent(llm_mock)
    await agent._react_step("do a thing", {}, "")  # must not raise
    assert llm_mock.generate_structured.call_args.kwargs["model"] == "auto"


@pytest.mark.asyncio
async def test_stage_group_tracks_applied_group(llm_mock, monkeypatch) -> None:
    decision = make_decision(CAPABLE)
    monkeypatch.setattr(
        "core.llm.stage_router.get_stage_router",
        lambda: FakeStageRouter(enabled=True, enforce=False, decision=decision),
    )
    agent = build_agent(llm_mock)
    await agent._react_step("do a thing", {}, "")
    assert agent._stage_group == CAPABLE  # shadow still tracks would-be group


# ── byok_handler outcome-join hook ─────────────────────────────────────────


class TestOutcomeJoinHook:
    @pytest.mark.asyncio
    async def test_record_outcome_feedback_writes_stage_outcome(self, monkeypatch) -> None:
        from core.llm import byok_handler as bh
        from core.llm.stage_router import set_stage_decision_carrier

        written: list = []

        def fake_record_stage_outcome(**kwargs):
            written.append(kwargs)

        monkeypatch.setattr(
            "core.llm.stage_router.record_stage_outcome", fake_record_stage_outcome
        )
        monkeypatch.setattr("core.llm.stage_router.get_stage_decision_carrier", lambda: "decision-xyz")
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")  # must NOT gate the join

        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.tenant_id = "tenant-1"
        await handler._record_outcome_feedback(
            model="deepseek-v4-flash",
            provider_id="opencode-go",
            task_type="agentic",
            content="ok",
            finish_reason="stop",
            success=True,
            cost=0.001,
            latency_ms=120.0,
        )
        assert len(written) == 1
        assert written[0]["decision_id"] == "decision-xyz"
        assert written[0]["success"] is True
        assert written[0]["actual_model"] == "deepseek-v4-flash"
        assert written[0]["actual_provider"] == "opencode-go"

    @pytest.mark.asyncio
    async def test_no_carrier_is_noop(self, monkeypatch) -> None:
        from core.llm import byok_handler as bh

        called: list = []
        monkeypatch.setattr("core.llm.stage_router.record_stage_outcome", lambda **k: called.append(k))
        monkeypatch.setattr("core.llm.stage_router.get_stage_decision_carrier", lambda: None)
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")

        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.tenant_id = "tenant-1"
        await handler._record_outcome_feedback(
            model="m", provider_id="p", task_type=None, content=None,
            finish_reason=None, success=False, cost=None, latency_ms=10.0,
        )
        assert called == []
