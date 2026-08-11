"""Coverage wave 32 — core/atom_meta_agent remaining branches (87% → 93%+).

- _meta_agent_sandbox_check: fs review, tripwire blocked, tripwire killrun
  trigger, caps review, non-killrun exception fail-open, killrun guard block
- execute: killed run → status killed_sandbox (KillRunAborted top-level)
- execute: turn-fact extraction dispatch on session end (flag on)
- execute: vector-recall prefetch populates context (flag on)
- execute: execution-creation DB error tolerated (run continues)
- execute: field-guide failure tolerated (empty context)
"""
import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.atom_meta_agent as ama
from core.atom_meta_agent import AtomMetaAgent
from core.react_models import ReActStep


@pytest.fixture
def meta_agent(monkeypatch):
    monkeypatch.setattr(ama, "WorldModelService", MagicMock())
    monkeypatch.setattr(ama, "CapabilityGraduationService", MagicMock())
    monkeypatch.setattr(ama, "get_canvas_provider", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(ama, "mcp_service", MagicMock())
    monkeypatch.setattr(ama, "AgentGovernanceService", MagicMock())
    monkeypatch.setattr(ama, "AgentFleetService", MagicMock())
    monkeypatch.setattr(ama, "FleetOptimizationService", MagicMock())
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)

    sl = MagicMock()
    sl.return_value.__enter__.return_value = MagicMock()
    monkeypatch.setattr(ama, "SessionLocal", sl)

    sf = MagicMock()
    sf.get_llm_service.return_value = MagicMock()
    monkeypatch.setattr("core.service_factory.ServiceFactory", sf)

    agent = AtomMetaAgent()
    agent.llm = MagicMock()
    agent.world_model = MagicMock()
    return agent, sl


def _prepare_execute(agent, sl, monkeypatch, *, route_category=None, tools=None):
    from ai.nlp_engine import NaturalLanguageEngine, RouteCategory, RouteClassification

    workspace = SimpleNamespace(tenant_id="default")
    db = sl.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.first.return_value = workspace

    nlu = MagicMock()
    nlu.classify_route = AsyncMock(return_value=RouteClassification(
        category=route_category or RouteCategory.ONE_OFF,
        reasoning="r", confidence=0.9,
    ))
    monkeypatch.setattr(ama, "NaturalLanguageEngine", MagicMock(return_value=nlu))

    agent.world_model.recall_experiences = AsyncMock(return_value={"experiences": []})
    agent.mcp.get_all_tools = AsyncMock(return_value=tools or [
        {"name": "trigger_workflow", "description": "d", "parameters": {}},
    ])
    monkeypatch.setattr("core.field_guide_service.get_field_guide_service",
                        lambda: MagicMock(get_field_guide_context=lambda w: "guide"))
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
    agent._persist_reasoning_step = MagicMock(return_value="step-id")
    agent._record_execution = AsyncMock()
    return nlu


class TestSandboxCheck:
    def test_fs_review_replaces_decision(self):
        base = MagicMock()
        base.is_allowed = True
        base.requires_review = False
        base.args_hash = "h"
        base.decision = "allowed"
        fs = MagicMock()
        fs.requires_review = True
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_fs_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_tripwires_enabled", return_value=False), \
             patch("core.sandbox_config.is_sandbox_caps_enabled", return_value=False), \
             patch("core.sandbox_policy.PolicyIssuer") as issuer_cls, \
             patch("core.sandbox_fs.validate", return_value=fs), \
             patch("core.sandbox_audit.write_violation"):
            issuer_cls.return_value.issue.return_value = MagicMock()
            issuer_cls.return_value.check.return_value = base
            decision = ama._meta_agent_sandbox_check(
                "file_read", {}, {"run_id": "r1", "tier": "autonomous"}
            )
        assert decision is fs

    def test_tripwire_blocked_replaces_decision(self):
        base = MagicMock()
        base.is_allowed = True
        base.requires_review = False
        base.args_hash = "h"
        base.decision = "allowed"
        tw = MagicMock()
        tw.decision = "blocked"
        tw.killrun_triggered = False
        tw.violation_detail = "hit"
        tw.metadata_json = {}
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_fs_enabled", return_value=False), \
             patch("core.sandbox_config.is_sandbox_tripwires_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_caps_enabled", return_value=False), \
             patch("core.sandbox_policy.PolicyIssuer") as issuer_cls, \
             patch("core.sandbox_tripwire.check", return_value=tw), \
             patch("core.sandbox_audit.write_violation"):
            issuer_cls.return_value.issue.return_value = MagicMock()
            issuer_cls.return_value.check.return_value = base
            decision = ama._meta_agent_sandbox_check(
                "shell_exec", {}, {"run_id": "r1", "tier": "autonomous"}
            )
        assert decision is tw

    def test_tripwire_killrun_triggered(self):
        base = MagicMock()
        base.is_allowed = True
        base.requires_review = False
        base.args_hash = "h"
        base.decision = "allowed"
        tw = MagicMock()
        tw.decision = "blocked"
        tw.killrun_triggered = True
        tw.violation_detail = "kill"
        tw.metadata_json = {"tripwire_id": "tw-7"}
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_fs_enabled", return_value=False), \
             patch("core.sandbox_config.is_sandbox_tripwires_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_force_enforce_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_caps_enabled", return_value=False), \
             patch("core.sandbox_policy.PolicyIssuer") as issuer_cls, \
             patch("core.sandbox_tripwire.check", return_value=tw), \
             patch("core.sandbox_killrun.trigger_killrun") as trigger, \
             patch("core.sandbox_audit.write_violation"):
            issuer_cls.return_value.issue.return_value = MagicMock()
            issuer_cls.return_value.check.return_value = base
            ama._meta_agent_sandbox_check(
                "shell_exec", {}, {"run_id": "r1", "tier": "autonomous"}
            )
        trigger.assert_called_once()

    def test_caps_review_replaces_decision(self):
        base = MagicMock()
        base.is_allowed = True
        base.requires_review = False
        base.args_hash = "h"
        base.decision = "allowed"
        cap = MagicMock()
        cap.requires_review = True
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_fs_enabled", return_value=False), \
             patch("core.sandbox_config.is_sandbox_tripwires_enabled", return_value=False), \
             patch("core.sandbox_config.is_sandbox_caps_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer") as issuer_cls, \
             patch("core.sandbox_caps.check_caps", return_value=cap), \
             patch("core.sandbox_audit.write_violation"):
            issuer_cls.return_value.issue.return_value = MagicMock()
            issuer_cls.return_value.check.return_value = base
            decision = ama._meta_agent_sandbox_check(
                "file_write", {}, {"run_id": "r1", "tier": "autonomous"}
            )
        assert decision is cap

    def test_non_killrun_exception_fails_open(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer", side_effect=RuntimeError("boom")):
            decision = ama._meta_agent_sandbox_check(
                "browser_click", {}, {"run_id": "r1", "tier": "autonomous"}
            )
        assert decision.decision == "allowed"
        assert "error" in decision.metadata_json

    def test_killrun_guard_blocks(self):
        from core.sandbox_killrun import KillRunAborted
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_killrun.guard", side_effect=KillRunAborted("pre-killed")):
            # The meta-agent check PROPAGATES KillRunAborted (documented: it is
            # how tripwire kills abort the AgentExecution at the top level)
            with pytest.raises(KillRunAborted):
                ama._meta_agent_sandbox_check(
                    "browser_click", {}, {"run_id": "run-gated", "tier": "autonomous"}
                )


class TestExecuteExtras:
    @pytest.mark.asyncio
    async def test_killed_run_returns_killed_sandbox(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        from core.sandbox_killrun import KillRunAborted
        agent._react_step = AsyncMock(side_effect=KillRunAborted("killed by tripwire"))
        result = await agent.execute("do it", context={})
        assert result["status"] == "killed_sandbox"

    @pytest.mark.asyncio
    async def test_vector_recall_prefetch_populates_context(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="ok"))
        monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", True)
        # NOTE: prefetch_relevant_facts is SYNC (called without await); an
        # AsyncMock would return an unawaited coroutine and the block's
        # try/except silently swallows the TypeError — use a sync stub.
        with patch.object(ama, "_prefetch_relevant_facts", new=lambda **kw: [
            {"fact_text": "revenue 50k", "confidence": 0.9}
        ]):
            await agent.execute("hi there", context={})
        ctx = agent._react_step.call_args.kwargs["context"]
        assert ctx["prefetched_facts"][0]["fact_text"] == "revenue 50k"

    @pytest.mark.asyncio
    async def test_execution_creation_error_tolerated(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="ok"))
        db = sl.return_value.__enter__.return_value
        def _boom(*a, **k):
            raise RuntimeError("db write failed")
        db.add.side_effect = _boom
        result = await agent.execute("hi there", context={})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_field_guide_failure_tolerated(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="ok"))
        def _boom(*a, **k):
            raise RuntimeError("guide down")
        monkeypatch.setattr("core.field_guide_service.get_field_guide_service", _boom)
        await agent.execute("do it", context={})
        ctx = agent._react_step.call_args.kwargs["context"]
        assert ctx["_field_guide_context"] == ""

    @pytest.mark.asyncio
    async def test_turn_fact_extraction_dispatched(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock(return_value=[])
        monkeypatch.setattr(ama, "get_turn_fact_extractor", lambda **k: extractor)
        await agent.execute("note revenue is 50k", context={})
        await asyncio.sleep(0.2)  # fire-and-forget task
        assert extractor.extract_from_turn.await_count >= 1
