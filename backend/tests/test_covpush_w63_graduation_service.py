"""Coverage wave 63 — core/agent_graduation_service.py (91% → 95%+).

Closes the remaining holes: POMDP ImportError fallback (module reload),
POMDP init failure in __init__, EpisodeService db-mismatch rebuild, readiness
numeric guard fallback + remaining gap branches (insufficient episodes,
intervention-rate, no episodes), trajectory stable/zero-improvement paths,
learning-consistency recommendation bands (good/moderate/poor), promotion
notification no-loop fallback + POMDP memory consolidation (success/failure),
performance-trend no-ratings + stable paths, supervision score empty-sessions.
"""
import importlib
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.agent_graduation_service import AgentGraduationService
from core.episode_service import EpisodeService
from core.models import AgentStatus


def _agent(**kw):
    base = dict(id="a1", name="Agent 1", category="general",
                status=AgentStatus.SUPERVISED.value, confidence_score=0.8,
                module_path="core.agents.generic_agent",
                class_name="GenericAgent", workspace_id="default",
                tenant_id="default", configuration={},
                user_id="u1")
    base.update(kw)
    return MagicMock(**base)


def _episode(**kw):
    base = dict(id="e1", agent_id="a1", task_description="Task",
                human_intervention_count=1, constitutional_score=0.9,
                maturity_at_time="supervised", started_at=datetime.now(),
                metadata_json={})
    base.update(kw)
    return MagicMock(**base)


def _session(**kw):
    base = dict(id="s1", agent_id="a1", status="completed",
                duration_seconds=3600, intervention_count=1,
                supervisor_rating=4.5, started_at=datetime.now())
    base.update(kw)
    return MagicMock(**base)


@pytest.fixture
def svc():
    return AgentGraduationService(Mock())


class TestModuleReload:
    def test_pomdp_import_error_fallback(self):
        mod = importlib.import_module("core.agent_graduation_service")
        framework = sys.modules.get("core.memory.pomdp_memory_framework")
        try:
            sys.modules["core.memory.pomdp_memory_framework"] = None
            reloaded = importlib.reload(mod)
            assert reloaded.POMDP_AVAILABLE is False
        finally:
            sys.modules["core.memory.pomdp_memory_framework"] = framework
            importlib.reload(mod)
        assert mod.POMDP_AVAILABLE is True

    def test_pomdp_init_failure_tolerated(self, paths_none):
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True), \
             patch("core.agent_graduation_service.get_memory_manager",
                   side_effect=RuntimeError("boom")):
            svc = AgentGraduationService(Mock())
        assert svc.memory_manager is None
        assert svc.experience_calculator is None


@pytest.fixture
def paths_none():
    return None


class TestReadinessEdgeBranches:
    async def test_episode_service_db_mismatch_rebuilt(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        other_db = Mock()
        readiness = SimpleNamespace(
            to_dict=lambda: {"threshold_met": True},
            readiness_score=0.9, episodes_analyzed=20,
            breakdown={"total_interventions": 1},
            zero_intervention_ratio=0.95, avg_constitutional_score=0.9,
        )
        built_with = []

        class _FakeEpisodeService(EpisodeService):
            def __init__(self, db, tenant_api_key=None, **kw):
                built_with.append(db)
                self.db = db
                self.get_graduation_readiness = Mock(return_value=readiness)

        es = _FakeEpisodeService(other_db)
        with patch("core.agent_graduation_service.get_episode_service",
                   return_value=es), \
             patch("core.agent_graduation_service.EpisodeService",
                   _FakeEpisodeService):
            result = await svc.calculate_readiness_score("a1", "SUPERVISED")
        assert result["ready"] is True
        assert result["episode_count"] == 20
        # db mismatch triggered a rebuild with the service's own session
        assert built_with == [other_db, svc.db]

    async def test_numeric_guard_fallback(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        readiness = SimpleNamespace(
            to_dict=lambda: {"threshold_met": False},
            readiness_score="not-a-number", episodes_analyzed="x",
            breakdown={}, zero_intervention_ratio="y",
            avg_constitutional_score="z",
        )
        with patch("core.agent_graduation_service.get_episode_service",
                   return_value=SimpleNamespace(
                       get_graduation_readiness=Mock(return_value=readiness))):
            result = await svc.calculate_readiness_score("a1", "INTERN")
        assert result["score"] == 0.0
        assert result["episode_count"] == 0
        assert "Insufficient episodes" in result["gaps"][0]
        assert "No episodes recorded yet" in result["gaps"]

    async def test_episode_gap_and_intervention_gap(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        readiness = SimpleNamespace(
            to_dict=lambda: {"threshold_met": False},
            readiness_score=0.5, episodes_analyzed=5,
            breakdown={"total_interventions": 9},
            zero_intervention_ratio=0.1, avg_constitutional_score=0.6,
        )
        with patch("core.agent_graduation_service.get_episode_service",
                   return_value=SimpleNamespace(
                       get_graduation_readiness=Mock(return_value=readiness))):
            result = await svc.calculate_readiness_score("a1", "INTERN")
        # episodes 5 < 10 AND intervention rate 0.9 > 0.5
        assert any("Insufficient episodes" in g for g in result["gaps"])
        assert any("Intervention rate 0.90" in g for g in result["gaps"])
        assert result["intervention_rate"] == 0.9

    async def test_min_episodes_override_honored(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        readiness = SimpleNamespace(
            to_dict=lambda: {"threshold_met": True},
            readiness_score=0.9, episodes_analyzed=12,
            breakdown={"total_interventions": 0},
            zero_intervention_ratio=1.0, avg_constitutional_score=0.9,
        )
        with patch("core.agent_graduation_service.get_episode_service",
                   return_value=SimpleNamespace(
                       get_graduation_readiness=Mock(return_value=readiness))):
            result = await svc.calculate_readiness_score(
                "a1", "SUPERVISED", min_episodes=15)
        assert any("Insufficient episodes (12/15" in g for g in result["gaps"])


class TestTrajectoryBranches:
    async def test_trajectory_zero_historical(self, svc):
        svc.memory_manager = Mock()
        memories = [SimpleNamespace(intervention_required=False) for _ in range(12)]
        svc.memory_manager.recall_by_quality.return_value = memories
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc._analyze_intervention_trajectory("a1")
        assert result["historical_rate"] == 0.0
        assert result["improvement_rate"] == 0.0

    async def test_trajectory_stable(self, svc):
        svc.memory_manager = Mock()
        memories = (
            [SimpleNamespace(intervention_required=True)] * 4 +
            [SimpleNamespace(intervention_required=False)] * 6 +   # recent 0.4
            [SimpleNamespace(intervention_required=True)] * 4 +
            [SimpleNamespace(intervention_required=False)] * 6    # historical 0.4
        )
        svc.memory_manager.recall_by_quality.return_value = memories
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc._analyze_intervention_trajectory("a1")
        assert result["trend"] == "stable"
        assert result["is_improving"] is True


class TestConsistencyBands:
    def _memories(self, qualities):
        return [SimpleNamespace(quality_score=q, intervention_required=False)
                for q in qualities]

    async def test_consistency_good_band(self, svc):
        svc.memory_manager = Mock()
        svc.memory_manager.recall_by_quality.return_value = self._memories(
            [1.0] * 6 + [0.0] * 2)
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc.analyze_learning_consistency("a1")
        assert "Good" in result["recommendation"]
        assert 0.6 <= result["consistency_score"] < 0.8

    async def test_consistency_moderate_band(self, svc):
        svc.memory_manager = Mock()
        svc.memory_manager.recall_by_quality.return_value = self._memories(
            [1.0, 0, 0.3, 0, 0.4, 0, 0.2, 0])
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc.analyze_learning_consistency("a1")
        assert "Moderate" in result["recommendation"]
        assert 0.4 <= result["consistency_score"] < 0.6

    async def test_consistency_poor_band(self, svc):
        svc.memory_manager = Mock()
        svc.memory_manager.recall_by_quality.return_value = self._memories(
            [4.0, 0, 0, 0, 0, 0, 0, 0])
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc.analyze_learning_consistency("a1")
        assert "Poor" in result["recommendation"]


class TestPromoteBranches:
    async def test_promote_notification_no_loop_fallback(self, svc):
        agent = _agent(configuration=None)
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_workspace_id",
                   return_value="w1"), \
             patch("core.personal_scope.resolve_tenant_id",
                   return_value="t1"), \
             patch("core.agent_graduation_service.POMDP_AVAILABLE", False), \
             patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")), \
             patch("asyncio.new_event_loop") as new_loop, \
             patch("asyncio.set_event_loop") as set_loop:
            ns.return_value.send_notification = AsyncMock()
            result = await svc.promote_agent("a1", "INTERN", "u1")
        assert result is True
        assert agent.configuration["promoted_at"]
        new_loop.return_value.run_until_complete.assert_called_once()
        set_loop.assert_called_once_with(new_loop.return_value)

    async def test_promote_notification_failure_tolerated(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_workspace_id",
                   side_effect=RuntimeError("boom")), \
             patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
            result = await svc.promote_agent("a1", "INTERN", "u1")
        assert result is True  # promotion already committed

    async def test_promote_pomdp_consolidation_success(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_workspace_id",
                   return_value="w1"), \
             patch("core.personal_scope.resolve_tenant_id",
                   return_value="t1"), \
             patch("core.agent_graduation_service.POMDP_AVAILABLE", True), \
             patch("core.agent_graduation_service.get_memory_manager") as gmm, \
             patch("core.memory.pomdp_memory_framework.MemoryConsolidation") as mc:
            ns.return_value.send_notification = AsyncMock()
            mc.return_value.consolidate_memories = AsyncMock(return_value=7)
            result = await svc.promote_agent("a1", "INTERN", "u1")
        assert result is True
        mc.assert_called_once_with(gmm.return_value)
        mc.return_value.consolidate_memories.assert_awaited_once_with("a1")

    async def test_promote_pomdp_consolidation_failure_tolerated(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_workspace_id",
                   return_value="w1"), \
             patch("core.personal_scope.resolve_tenant_id",
                   return_value="t1"), \
             patch("core.agent_graduation_service.POMDP_AVAILABLE", True), \
             patch("core.memory.pomdp_memory_framework.MemoryConsolidation") as mc:
            ns.return_value.send_notification = AsyncMock()
            mc.return_value.consolidate_memories = AsyncMock(
                side_effect=RuntimeError("boom"))
            result = await svc.promote_agent("a1", "INTERN", "u1")
        assert result is True  # consolidation failure never rolls back promotion


class TestTrendBranches:
    def test_trend_missing_ratings_stable(self, svc):
        base = [datetime.now() - timedelta(days=i) for i in range(10)]
        sessions = [_session(started_at=base[i], supervisor_rating=None)
                    for i in range(10)]
        assert svc._calculate_performance_trend(sessions) == "stable"

    def test_trend_neutral_stable(self, svc):
        base = [datetime.now() - timedelta(days=i) for i in range(10)]
        sessions = [_session(started_at=base[i], supervisor_rating=4.0,
                             intervention_count=1)
                    for i in range(10)]
        assert svc._calculate_performance_trend(sessions) == "stable"


class TestSupervisionScoreEmpty:
    def test_supervision_score_no_sessions(self, svc):
        metrics = {"average_supervisor_rating": 0.0, "intervention_rate": 1.0,
                   "total_sessions": 0, "high_rating_sessions": 0,
                   "recent_performance_trend": "unknown"}
        score = svc._supervision_score(metrics, {"max_intervention_rate": 0.5})
        # rating 0 + intervention (1 - 1.0/5)*30 + high-quality 0 + trend 0
        assert score == 24.0
