# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/self_evolution_service.py.

Unit coverage of the self-evolution service (legacy single-agent API +
GEA delegation + Auto-Dev cycles):
- analyze_agent_performance: agent-missing, no history, low approval rate
  (>5 hitls, <0.5), frequent correction (>3 feedbacks), maintain-current
  paths; confidence_score echo; ISO last_analysis.
- apply_auto_tune: agent missing, configuration None / existing history
  append + commit.
- run_group_evolution / analyze_group_readiness: AgentEvolutionLoop
  delegation, empty group, avg-perf rounding, recommended threshold.
- run_memento_cycle / run_alpha_evolve_cycle: gate deny, gate allow +
  usage record, ImportError (module absent) -> skipped, generic exception
  -> error dict.
- _get_workspace_settings: metadata_json, no metadata, no workspace,
  exception -> {}.

No LLM spend, no network; SessionLocal and the evolution-loop/auto-dev
classes are fully mocked.
"""
import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.self_evolution_service import (
    SelfEvolutionService,
    self_evolution_service,
)


@pytest.fixture()
def svc():
    return SelfEvolutionService()


@pytest.fixture()
def session():
    return MagicMock()


@pytest.fixture()
def session_local(session, monkeypatch):
    session.__enter__.return_value = session
    monkeypatch.setattr("core.self_evolution_service.SessionLocal", lambda: session)
    return session


def _agent(**kw):
    defaults = dict(
        id="agent-1",
        name="Agent",
        confidence_score=0.8,
        category="general",
        status="active",
        configuration=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _feedback_q(count):
    q = MagicMock()
    q.filter.return_value.all.return_value = [object()] * count
    return q


def _hitl_q(statuses):
    q = MagicMock()
    q.filter.return_value.all.return_value = [
        SimpleNamespace(status=s) for s in statuses
    ]
    return q


def _agent_q(agent):
    q = MagicMock()
    q.filter.return_value.first.return_value = agent
    return q


class TestAnalyzeAgentPerformance:
    def test_agent_not_found(self, session_local, session, svc):
        session.query.return_value.filter.return_value.first.return_value = None
        result = _run(svc.analyze_agent_performance("ghost"))
        assert result == {"error": "Agent not found"}
        session.close.assert_called_once()

    def test_no_history_maintain_autonomy(self, session_local, session, svc):
        agent = _agent()
        session.query.side_effect = [_agent_q(agent), _feedback_q(0), _hitl_q([])]
        result = _run(svc.analyze_agent_performance("agent-1"))
        assert result["agent_id"] == "agent-1"
        assert result["confidence_score"] == 0.8
        assert result["approval_rate"] == 0.0
        assert result["recent_feedback_count"] == 0
        assert result["detected_bottleneck"] == "none"
        assert result["recommendation"] == "Maintain current autonomy."
        assert result["last_analysis"].endswith("+00:00")
        session.close.assert_called_once()

    def test_low_approval_rate_bottleneck(self, session_local, session, svc):
        agent = _agent()
        statuses = ["approved"] * 2 + ["rejected"] * 4  # 6 hitls, 33% approval
        session.query.side_effect = [_agent_q(agent), _feedback_q(0), _hitl_q(statuses)]
        result = _run(svc.analyze_agent_performance("agent-1"))
        assert result["approval_rate"] == pytest.approx(2 / 6)
        assert result["detected_bottleneck"] == "low_approval_rate"
        assert "system prompt" in result["recommendation"]

    def test_low_approval_but_few_hitls_ignored(self, session_local, session, svc):
        agent = _agent()
        statuses = ["rejected"] * 3  # 3 hitls, 0% approval but <= 5
        session.query.side_effect = [_agent_q(agent), _feedback_q(4), _hitl_q(statuses)]
        result = _run(svc.analyze_agent_performance("agent-1"))
        assert result["detected_bottleneck"] == "frequent_correction"
        assert "RAG" in result["recommendation"]

    def test_frequent_correction_bottleneck(self, session_local, session, svc):
        agent = _agent()
        statuses = ["approved"] * 6
        session.query.side_effect = [_agent_q(agent), _feedback_q(4), _hitl_q(statuses)]
        result = _run(svc.analyze_agent_performance("agent-1"))
        assert result["approval_rate"] == 1.0
        assert result["detected_bottleneck"] == "frequent_correction"
        assert "RAG context" in result["recommendation"]


class TestApplyAutoTune:
    def test_agent_missing_noop(self, session_local, session, svc):
        session.query.return_value.filter.return_value.first.return_value = None
        _run(svc.apply_auto_tune("ghost", "insight"))
        session.commit.assert_not_called()
        session.close.assert_called_once()

    def test_agent_without_configuration(self, session_local, session, svc):
        agent = _agent()
        session.query.side_effect = [_agent_q(agent)]
        _run(svc.apply_auto_tune("agent-1", "tune insight"))
        assert agent.configuration["evolution_history"][0]["insight"] == "tune insight"
        session.commit.assert_called_once()

    def test_agent_with_existing_history(self, session_local, session, svc):
        agent = _agent(
            configuration={"evolution_history": [{"timestamp": "2026-01-01", "insight": "old"}]}
        )
        session.query.side_effect = [_agent_q(agent)]
        _run(svc.apply_auto_tune("agent-1", "new insight"))
        assert len(agent.configuration["evolution_history"]) == 2
        assert agent.configuration["evolution_history"][1]["insight"] == "new insight"
        assert agent.configuration["evolution_history"][1]["timestamp"].endswith("+00:00")

    def test_logs_insight(self, session_local, session, svc):
        agent = _agent()
        session.query.side_effect = [_agent_q(agent)]
        with patch("core.self_evolution_service.logger") as log:
            _run(svc.apply_auto_tune("agent-1", "x"))
        log.info.assert_called_once()


class TestRunGroupEvolution:
    def test_delegates_to_evolution_loop(self, session_local, session, svc):
        result_obj = SimpleNamespace(
            benchmark_passed=True,
            benchmark_score=0.92,
            to_dict=lambda: {"cycle_id": "c1", "passed": True},
        )
        loop_cls = MagicMock()
        loop_cls.return_value.run_evolution_cycle = AsyncMock(return_value=result_obj)
        with patch("core.agent_evolution_loop.AgentEvolutionLoop", loop_cls):
            result = _run(
                svc.run_group_evolution("t-1", group_size=7, target_agent_id="a1", category="research")
            )
        loop_cls.assert_called_once_with(session)
        loop_cls.return_value.run_evolution_cycle.assert_awaited_once_with(
            tenant_id="t-1", group_size=7, target_agent_id="a1", category="research"
        )
        assert result == {"cycle_id": "c1", "passed": True}


class TestAnalyzeGroupReadiness:
    def test_empty_group(self, session_local, session, svc):
        loop_cls = MagicMock()
        loop_cls.return_value.select_parent_group.return_value = []
        with patch("core.agent_evolution_loop.AgentEvolutionLoop", loop_cls):
            result = _run(svc.analyze_group_readiness("t-1"))
        assert result == {
            "candidate_count": 0,
            "parent_group": [],
            "avg_performance": 0.0,
            "evolution_recommended": False,
        }

    def test_group_with_agents(self, session_local, session, svc):
        members = [
            SimpleNamespace(id="a1", name="A", confidence_score=0.6, category="c", status="active"),
            SimpleNamespace(id="a2", name="B", confidence_score=0.8, category="c", status="student"),
        ]
        loop_cls = MagicMock()
        loop_cls.return_value.select_parent_group.return_value = members
        with patch("core.agent_evolution_loop.AgentEvolutionLoop", loop_cls):
            result = _run(svc.analyze_group_readiness("t-1", group_size=5))
        assert loop_cls.return_value.select_parent_group.assert_called_once_with(
            tenant_id="t-1", n=5
        ) or True
        assert result["candidate_count"] == 2
        assert result["avg_performance"] == 0.7
        assert result["evolution_recommended"] is True
        assert result["parent_group"][0]["agent_id"] == "a1"
        assert result["parent_group"][1]["status"] == "student"

    def test_group_high_perf_not_recommended(self, session_local, session, svc):
        members = [
            SimpleNamespace(id="a1", name="A", confidence_score=0.9, category="c", status="active"),
            SimpleNamespace(id="a2", name="B", confidence_score=0.95, category="c", status="active"),
        ]
        loop_cls = MagicMock()
        loop_cls.return_value.select_parent_group.return_value = members
        with patch("core.agent_evolution_loop.AgentEvolutionLoop", loop_cls):
            result = _run(svc.analyze_group_readiness("t-1"))
        assert result["avg_performance"] == 0.925
        assert result["evolution_recommended"] is False


class TestRunMementoCycle:
    def test_gate_denies(self, session_local, session, svc):
        gate = MagicMock()
        gate.can_use.return_value = False
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            result = _run(svc.run_memento_cycle("a1", "ep-1", "t-1"))
        assert result["skipped"] is True
        assert "INTERN" in result["reason"]

    def test_gate_allows(self, session_local, session, svc):
        gate = MagicMock()
        gate.can_use.return_value = True
        engine = MagicMock()
        engine.generate_skill_candidate = AsyncMock(
            return_value=SimpleNamespace(id="cand-1", skill_name="web-scraper")
        )
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate), \
             patch("core.auto_dev.memento_engine.MementoEngine", return_value=engine):
            result = _run(svc.run_memento_cycle("a1", "ep-1", "t-1"))
        assert result == {"success": True, "candidate_id": "cand-1", "skill_name": "web-scraper"}
        gate.record_usage.assert_called_once_with("a1", "auto_dev.memento_skills", success=True)

    def test_module_not_installed(self, session_local, session, svc):
        with patch.dict(sys.modules, {"core.auto_dev.capability_gate": None}):
            result = _run(svc.run_memento_cycle("a1", "ep-1", "t-1"))
        assert result["skipped"] is True
        assert result["reason"] == "Auto-Dev module not installed"

    def test_generic_exception(self, session_local, session, svc):
        gate = MagicMock()
        gate.can_use.side_effect = RuntimeError("boom")
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            result = _run(svc.run_memento_cycle("a1", "ep-1", "t-1"))
        assert result == {"error": "boom"}

    def test_workspace_settings_flow(self, session_local, session, svc):
        session.query.return_value.filter.return_value.first.return_value = (
            SimpleNamespace(metadata_json={"auto_dev_enabled": True})
        )
        assert svc._get_workspace_settings(session, "t-1") == {"auto_dev_enabled": True}


class TestRunAlphaEvolveCycle:
    def test_gate_denies(self, session_local, session, svc):
        gate = MagicMock()
        gate.can_use.return_value = False
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            result = _run(svc.run_alpha_evolve_cycle("a1", "t-1", "code", "goal"))
        assert result["skipped"] is True
        assert "SUPERVISED" in result["reason"]

    def test_gate_allows(self, session_local, session, svc):
        gate = MagicMock()
        gate.can_use.return_value = True
        engine = MagicMock()
        engine.run_research_experiment = AsyncMock(return_value=[{"experiment": 1}])
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate), \
             patch("core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", return_value=engine):
            result = _run(
                svc.run_alpha_evolve_cycle("a1", "t-1", "code", "goal", iterations=5)
            )
        assert result == {"success": True, "results": [{"experiment": 1}]}
        engine.run_research_experiment.assert_awaited_once_with(
            tenant_id="t-1", base_code="code", research_goal="goal", iterations=5
        )
        gate.record_usage.assert_called_once_with("a1", "auto_dev.alpha_evolver", success=True)

    def test_module_not_installed(self, session_local, session, svc):
        with patch.dict(sys.modules, {"core.auto_dev.capability_gate": None}):
            result = _run(svc.run_alpha_evolve_cycle("a1", "t-1", "code", "goal"))
        assert result["skipped"] is True

    def test_generic_exception(self, session_local, session, svc):
        gate = MagicMock()
        gate.can_use.side_effect = ValueError("nope")
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            result = _run(svc.run_alpha_evolve_cycle("a1", "t-1", "code", "goal"))
        assert result == {"error": "nope"}


class TestGetWorkspaceSettings:
    def test_workspace_with_metadata(self, session_local, session, svc):
        session.query.return_value.filter.return_value.first.return_value = (
            SimpleNamespace(metadata_json={"k": "v"})
        )
        assert svc._get_workspace_settings(session, "t-1") == {"k": "v"}

    def test_workspace_without_metadata(self, session_local, session, svc):
        session.query.return_value.filter.return_value.first.return_value = (
            SimpleNamespace(metadata_json=None)
        )
        assert svc._get_workspace_settings(session, "t-1") == {}

    def test_no_workspace(self, session_local, session, svc):
        session.query.return_value.filter.return_value.first.return_value = None
        assert svc._get_workspace_settings(session, "t-1") == {}

    def test_query_exception(self, session_local, session, svc):
        session.query.side_effect = RuntimeError("db down")
        assert svc._get_workspace_settings(session, "t-1") == {}


class TestSingleton:
    def test_module_singleton(self):
        assert isinstance(self_evolution_service, SelfEvolutionService)


def _run(coro):
    return asyncio.run(coro)
