# -*- coding: utf-8 -*-
"""Coverage wave 103 — core/memory/memory_consolidation_service.py to 100%.

Fully mocked: fake DB query chain, fake lancedb handler, fake
EpisodeLifecycleService (async methods), fake MemoryManager, real
MemoryEntry/ObservationSpace dataclasses from the POMDP framework. Zero LLM
spend, zero network.

Covers: init with/without POMDP (incl. get_memory_manager raising →
degraded init), sync_episodes_to_memory (POMDP-unavailable zeros, success
with reward/next_state derivation, per-episode exception → errors count),
observation/complexity/autonomy helpers (all branches), run_consolidation_cycle
(already-running guard, agent vs all-agent paths, expired counting,
episode-lifecycle add, finally-reset incl. exception), apply_forgetting_curve
(fallback vs POMDP decay + expiry), replay_critical_memories (filters, sort,
increment, limit), extract_patterns (grouping, below-threshold skip, UNKNOWN
task type), get_consolidation_status, and the factory.
"""
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.memory.memory_consolidation_service as mcs
from core.memory.pomdp_memory_framework import (
    MemoryEntry,
    MemoryStatus,
    MemoryType,
    ObservationSpace,
)


# ============================================================================
# Builders / helpers
# ============================================================================

def make_episode(**overrides):
    defaults = dict(
        id="ep_1",
        agent_id="agent_1",
        status="completed",
        started_at=datetime.now(),
        tenant_id="ws_1",
        task_description="analyze sales",
        human_intervention_count=0,
        total_steps=6,
        maturity_at_time="AUTONOMOUS",
        importance_score=0.8,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_observation(agent_id="agent_1", task_type="WORKFLOW"):
    return ObservationSpace(
        timestamp=datetime.now(),
        agent_id=agent_id,
        workspace_id="ws_1",
        task_type=task_type,
        user_intent="intent",
        available_tools=[],
        system_state={},
        resource_constraints={},
        recent_success_rate=1.0,
        recent_intervention_count=0,
    )


def make_memory(agent_id="agent_1", quality=0.9, access=12, status=MemoryStatus.CONSOLIDATED, task_type="WORKFLOW", created=None, learning=0.5, success=True, intervention=False):
    return MemoryEntry(
        id="mem_12345678",
        memory_type=MemoryType.EPISODIC,
        observation=make_observation(agent_id=agent_id, task_type=task_type),
        content={},
        status=status,
        quality_score=quality,
        access_count=access,
        learning_value=learning,
        success_outcome=success,
        intervention_required=intervention,
        created_at=created or datetime.now(),
    )


class FakeQuery:
    """Chains filter → order_by → limit → all on a fixed list."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **kw):
        return self

    def order_by(self, *a, **kw):
        return self

    def limit(self, n):
        return self

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, episodes):
        self._episodes = episodes

    def query(self, *a, **kw):
        return FakeQuery(self._episodes)


def make_lifecycle():
    lc = MagicMock()
    lc.consolidate_similar_episodes = AsyncMock(
        return_value={"consolidated": 3, "skipped": 0, "errors": 0}
    )
    lc.decay_old_episodes = AsyncMock(return_value={"affected": 2, "expired": 1})
    return lc


def make_manager(memories=None):
    mgr = MagicMock()
    mgr._episodic_memory = memories if memories is not None else {}
    mgr.trigger_manage_cycle = MagicMock(return_value=None)
    mgr.get_memory_statistics = MagicMock(return_value={"total": len(mgr._episodic_memory)})
    return mgr


def build_svc(db=None, lifecycle=None, manager=None, pomdp=True, raise_mgr=None):
    """Construct MemoryConsolidationService with all deps mocked.

    Returns (svc, lifecycle, manager). Patches stay active for the returned
    service: the `pomdp` and `raise_mgr` variants re-patch module globals
    around the constructor.
    """
    lc = lifecycle if lifecycle is not None else make_lifecycle()
    mgr = manager if manager is not None else make_manager()
    with patch.object(mcs, "POMDP_AVAILABLE", pomdp), \
         patch.object(mcs, "get_lancedb_handler", return_value=MagicMock()), \
         patch.object(mcs, "EpisodeLifecycleService", return_value=lc), \
         patch.object(mcs, "get_memory_manager", side_effect=raise_mgr if raise_mgr else lambda db, lh: mgr):
        svc = mcs.MemoryConsolidationService(db or FakeDB([]))
    return svc, lc, mgr


def _run(coro):
    return asyncio.run(coro)


# ============================================================================
# Construction
# ============================================================================

class TestInit:
    def test_pomdp_unavailable_degraded(self):
        svc, _, mgr = build_svc(pomdp=False)
        assert svc.memory_manager is None
        assert svc.pomdp_consolidation is None
        assert svc._consolidation_in_progress is False

    def test_pomdp_init_failure_logged(self, caplog):
        svc, _, _ = build_svc(raise_mgr=lambda db, lh: (_ for _ in ()).throw(RuntimeError("boom")))
        assert svc.memory_manager is None
        assert "Failed to initialize POMDP consolidation" in caplog.text

    def test_pomdp_available_full_init(self):
        svc, _, mgr = build_svc()
        assert svc.memory_manager is mgr
        assert svc.pomdp_consolidation is not None

    def test_factory(self):
        with patch.object(mcs, "POMDP_AVAILABLE", False), \
             patch.object(mcs, "get_lancedb_handler", return_value=MagicMock()), \
             patch.object(mcs, "EpisodeLifecycleService", return_value=MagicMock()):
            svc = mcs.get_consolidation_service(FakeDB([]))
        assert isinstance(svc, mcs.MemoryConsolidationService)

    def test_import_error_sets_pomdp_unavailable(self, caplog):
        """The try/except around the POMDP import: reload the module with
        the pomdp import forced to fail, assert the warning + flag, then
        reload back to the real state."""
        import builtins
        import importlib
        import sys

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if "pomdp_memory_framework" in name:
                raise ImportError("simulated missing pomdp")
            return real_import(name, *args, **kwargs)

        mod_name = "core.memory.memory_consolidation_service"
        with patch.object(builtins, "__import__", side_effect=fake_import), \
             caplog.at_level("WARNING", logger="core.memory.memory_consolidation_service"):
            mod = importlib.reload(sys.modules[mod_name])
        assert mod.POMDP_AVAILABLE is False
        assert "POMDP Memory Framework not available" in caplog.text

        # Restore the real module state for every other suite
        importlib.reload(sys.modules[mod_name])
        assert sys.modules[mod_name].POMDP_AVAILABLE is True


# ============================================================================
# sync_episodes_to_memory
# ============================================================================

class TestSyncEpisodes:
    def test_pomdp_unavailable_zeros(self):
        svc, _, _ = build_svc(pomdp=False)
        result = _run(svc.sync_episodes_to_memory("agent_1"))
        assert result == {"synced": 0, "skipped": 0, "errors": 0}

    def test_sync_success(self):
        svc, _, mgr = build_svc()
        episodes = [
            make_episode(id="ep_1", human_intervention_count=0, total_steps=6),
            make_episode(id="ep_2", human_intervention_count=2, total_steps=4),
        ]
        svc.db = FakeDB(episodes)
        result = _run(svc.sync_episodes_to_memory("agent_1"))
        assert result == {"synced": 2, "skipped": 0, "errors": 0}
        assert "ep_1" in mgr._episodic_memory
        assert "ep_2" in mgr._episodic_memory
        assert mgr._episodic_memory["ep_1"].reward == 1.0
        assert mgr._episodic_memory["ep_2"].reward == 0.5
        assert mgr._episodic_memory["ep_1"].next_state == "success"
        assert mgr._episodic_memory["ep_2"].next_state == "partial_success"
        assert mgr._episodic_memory["ep_1"].success_outcome is True
        assert mgr._episodic_memory["ep_2"].intervention_required is True
        # content payload + quality + complexity/autonomy inference
        entry = mgr._episodic_memory["ep_1"]
        assert entry.content["episode_id"] == "ep_1"
        assert entry.quality_score == 0.8
        assert entry.task_complexity == 4
        assert entry.autonomy_level == 4
        assert entry.status == MemoryStatus.INDEXED

    def test_sync_error_episode_counted(self):
        svc, _, mgr = build_svc()
        bad = make_episode(id="bad", human_intervention_count=None)  # reward calc raises
        good = make_episode(id="good")
        svc.db = FakeDB([bad, good])
        result = _run(svc.sync_episodes_to_memory("agent_1"))
        assert result == {"synced": 1, "skipped": 0, "errors": 1}
        assert "good" in mgr._episodic_memory


# ============================================================================
# Helpers
# ============================================================================

class TestHelpers:
    def test_observation_mapping(self):
        svc, _, _ = build_svc(pomdp=False)
        obs = svc._episode_to_observation(make_episode())
        assert obs.agent_id == "agent_1"
        assert obs.workspace_id == "ws_1"
        assert obs.user_intent == "analyze sales"
        assert obs.recent_success_rate == 1.0
        assert obs.recent_intervention_count == 0

    def test_observation_defaults_tenant_and_time(self):
        svc, _, _ = build_svc(pomdp=False)
        obs = svc._episode_to_observation(make_episode(tenant_id=None, started_at=None))
        assert obs.workspace_id == "default"
        assert obs.timestamp is not None

    def test_task_complexity_branches(self):
        svc, _, _ = build_svc(pomdp=False)
        assert svc._infer_task_complexity(make_episode(human_intervention_count=0, total_steps=6)) == 4
        assert svc._infer_task_complexity(make_episode(human_intervention_count=0, total_steps=2)) == 3
        assert svc._infer_task_complexity(make_episode(human_intervention_count=1, total_steps=5)) == 2
        assert svc._infer_task_complexity(make_episode(human_intervention_count=3, total_steps=5)) == 1
        assert svc._infer_task_complexity(make_episode(human_intervention_count=0, total_steps=None)) == 3

    def test_autonomy_level_branches(self):
        svc, _, _ = build_svc(pomdp=False)
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="STUDENT")) == 1
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="INTERN")) == 2
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="SUPERVISED")) == 3
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="AUTONOMOUS")) == 4
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="UNKNOWN")) == 1


# ============================================================================
# run_consolidation_cycle
# ============================================================================

class TestConsolidationCycle:
    def test_already_running_guard(self):
        svc, _, _ = build_svc(pomdp=False)
        svc._consolidation_in_progress = True
        result = _run(svc.run_consolidation_cycle("agent_1"))
        assert result == {"consolidated": 0, "status": "already_running"}

    def test_agent_path_uses_pomdp_and_lifecycle(self):
        svc, lc, mgr = build_svc()
        mem = make_memory(status=MemoryStatus.EXPIRED)
        mgr._episodic_memory = {"a": mem}
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(return_value=7)
        result = _run(svc.run_consolidation_cycle("agent_1"))
        svc.pomdp_consolidation.consolidate_memories.assert_awaited_once_with(
            agent_id="agent_1", batch_size=50
        )
        mgr.trigger_manage_cycle.assert_called_once_with()
        lc.consolidate_similar_episodes.assert_awaited_once_with(
            agent_id="agent_1", similarity_threshold=0.85
        )
        # 7 pomdp + 3 episode-lifecycle
        assert result["consolidated"] == 10
        assert result["expired"] == 1
        assert result["duration_seconds"] >= 0.0
        assert svc._consolidation_in_progress is False
        assert svc._last_consolidation is not None

    def test_all_agent_path_skips_pomdp_consolidation(self):
        svc, lc, mgr = build_svc()
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(return_value=7)
        result = _run(svc.run_consolidation_cycle())
        svc.pomdp_consolidation.consolidate_memories.assert_not_awaited()
        lc.consolidate_similar_episodes.assert_not_awaited()  # no agent_id → skip
        assert result["consolidated"] == 0

    def test_pomdp_unavailable_skips_pomdp_path(self):
        svc, lc, _ = build_svc(pomdp=False)
        result = _run(svc.run_consolidation_cycle("agent_1"))
        assert result["consolidated"] == 3  # episode lifecycle still ran
        assert svc._consolidation_in_progress is False

    def test_in_progress_reset_on_exception(self):
        svc, _, _ = build_svc()
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(
            side_effect=RuntimeError("x")
        )
        with pytest.raises(RuntimeError):
            _run(svc.run_consolidation_cycle("agent_1"))
        assert svc._consolidation_in_progress is False  # finally ran


# ============================================================================
# apply_forgetting_curve
# ============================================================================

class TestForgettingCurve:
    def test_pomdp_unavailable_falls_back_to_lifecycle(self):
        svc, lc, _ = build_svc(pomdp=False)
        result = _run(svc.apply_forgetting_curve("agent_1", days_threshold=7))
        assert result == {"affected": 2, "expired": 1}
        lc.decay_old_episodes.assert_awaited_once_with(days_threshold=7)

    def test_pomdp_unavailable_default_threshold(self):
        svc, lc, _ = build_svc(pomdp=False)
        _run(svc.apply_forgetting_curve("agent_1"))
        lc.decay_old_episodes.assert_awaited_once_with(days_threshold=90)

    def test_decay_and_expire(self):
        old = make_memory(quality=0.9, created=datetime.now() - timedelta(days=40))
        other_agent = make_memory(agent_id="other", created=datetime.now() - timedelta(days=40))
        svc, _, mgr = build_svc(manager=make_manager({"old": old, "other": other_agent}))
        result = _run(svc.apply_forgetting_curve("agent_1", days_threshold=30))
        assert result == {"affected": 1, "expired": 0}
        assert old.quality_score < 0.9  # decayed
        assert other_agent.quality_score == 0.9  # untouched (other agent)

    def test_low_quality_marked_expired(self):
        old = make_memory(quality=0.11, created=datetime.now() - timedelta(days=100))
        svc, _, mgr = build_svc(manager=make_manager({"old": old}))
        result = _run(svc.apply_forgetting_curve("agent_1", days_threshold=1))
        assert result["affected"] == 1
        assert result["expired"] == 1
        assert old.status == MemoryStatus.EXPIRED

    def test_recent_memory_untouched(self):
        fresh = make_memory(created=datetime.now())
        svc, _, mgr = build_svc(manager=make_manager({"fresh": fresh}))
        result = _run(svc.apply_forgetting_curve("agent_1", days_threshold=30))
        assert result == {"affected": 0, "expired": 0}


# ============================================================================
# replay_critical_memories
# ============================================================================

class TestReplay:
    def test_pomdp_unavailable_empty(self):
        svc, _, _ = build_svc(pomdp=False)
        assert _run(svc.replay_critical_memories("agent_1")) == []

    def test_filters_and_replays(self):
        eligible = make_memory(quality=0.9, access=15, learning=0.8)
        too_low_quality = make_memory(quality=0.6, access=15)
        too_few_access = make_memory(quality=0.9, access=3)
        expired = make_memory(quality=0.9, access=15, status=MemoryStatus.EXPIRED)
        wrong_agent = make_memory(agent_id="other", quality=0.9, access=15)
        memories = {
            "eligible": eligible,
            "lowq": too_low_quality,
            "few": too_few_access,
            "exp": expired,
            "other": wrong_agent,
        }
        svc, _, mgr = build_svc(manager=make_manager(memories))
        replayed = _run(svc.replay_critical_memories("agent_1", limit=5))
        assert len(replayed) == 1
        assert eligible.access_count == 16
        assert eligible.quality_score == pytest.approx(0.945)
        assert eligible.learning_value == pytest.approx(0.84)
        assert replayed[0]["memory_id"] == "mem_1234"

    def test_replay_limit_sorted_by_learning_value(self):
        memories = {
            f"m{i}": make_memory(quality=0.9, access=15, learning=(i + 1) / 10.0)
            for i in range(4)
        }
        svc, _, mgr = build_svc(manager=make_manager(memories))
        replayed = _run(svc.replay_critical_memories("agent_1", limit=2))
        assert len(replayed) == 2
        assert replayed[0]["learning_value"] > replayed[1]["learning_value"]
        assert replayed[0]["memory_id"] == replayed[0]["memory_id"]  # shape sanity


# ============================================================================
# extract_patterns
# ============================================================================

class TestExtractPatterns:
    def test_pomdp_unavailable_empty(self):
        svc, _, _ = build_svc(pomdp=False)
        assert _run(svc.extract_patterns("agent_1")) == []

    def test_pattern_found_and_metrics(self):
        memories = {
            f"m{i}": make_memory(quality=0.8, success=True, intervention=False)
            for i in range(3)
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "WORKFLOW"
        assert patterns[0]["sample_size"] == 3
        assert patterns[0]["avg_quality"] == 0.8
        assert patterns[0]["success_rate"] == 1.0
        assert patterns[0]["avg_intervention_rate"] == 0.0

    def test_below_min_size_skipped(self):
        memories = {f"m{i}": make_memory() for i in range(2)}  # MIN_PATTERN_SIZE = 3
        svc, _, _ = build_svc(manager=make_manager(memories))
        assert _run(svc.extract_patterns("agent_1")) == []

    def test_unknown_task_type_and_status_filter(self):
        memories = {
            "a": make_memory(task_type=None, status=MemoryStatus.CONSOLIDATED),
            "b": make_memory(status=MemoryStatus.INDEXED),  # not consolidated → excluded
            "c": make_memory(task_type=None, status=MemoryStatus.CONSOLIDATED),
            "d": make_memory(task_type=None, status=MemoryStatus.CONSOLIDATED),
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "UNKNOWN"
        assert patterns[0]["sample_size"] == 3

    def test_mixed_success_and_intervention_rates(self):
        memories = {
            "a": make_memory(success=True, intervention=False),
            "b": make_memory(success=False, intervention=True),
            "c": make_memory(success=True, intervention=True),
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert patterns[0]["success_rate"] == pytest.approx(0.667, abs=0.001)
        assert patterns[0]["avg_intervention_rate"] == pytest.approx(0.667, abs=0.001)

    def test_multiple_task_types_separate_groups(self):
        memories = {
            "a": make_memory(task_type="REPORT"),
            "b": make_memory(task_type="REPORT"),
            "c": make_memory(task_type="REPORT"),
            "d": make_memory(task_type="WORKFLOW"),
            "e": make_memory(task_type="WORKFLOW"),
            "f": make_memory(task_type="WORKFLOW"),
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert {p["pattern_type"] for p in patterns} == {"REPORT", "WORKFLOW"}


# ============================================================================
# Status
# ============================================================================

class TestStatus:
    def test_status_never_consolidated(self):
        svc, _, _ = build_svc(pomdp=False)
        status = svc.get_consolidation_status()
        assert status["last_consolidation"] is None
        assert status["in_progress"] is False
        assert status["pomdp_available"] is False
        assert status["memory_statistics"] == {}

    def test_status_after_cycle(self):
        svc, _, mgr = build_svc()
        mgr.get_memory_statistics = MagicMock(return_value={"total": 5})
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(return_value=1)
        _run(svc.run_consolidation_cycle("agent_1"))
        status = svc.get_consolidation_status()
        assert status["last_consolidation"] is not None
        assert status["in_progress"] is False
        assert status["pomdp_available"] is True
        assert status["memory_statistics"] == {"total": 5}
