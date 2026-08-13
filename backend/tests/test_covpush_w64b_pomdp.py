"""
Coverage-push tests for core.memory.pomdp_memory_framework.

Target: >=95% statement coverage STANDALONE (this file alone).

Covers: enums (MemoryType/MemoryAccessPattern/MemoryStatus), ObservationSpace
(vector encoding + dict serialization), ActionSpace gating, MemoryEntry
serialization, the full write-manage-read loop (hypothesis trajectories,
write_memory incl. working-memory FIFO eviction, trigger_manage_cycle with
index/consolidate/expire paths, read_memory across all three stores, recall
helpers), embedding/summary/quality-score helpers, memory statistics,
ExperienceCalculator readiness scoring + experience metrics (incl. the
intervention-rate / improvement-rate correction), offline consolidation, the
factory functions, and the testing utilities (create_test_memory,
simulate_agent_experience).

Regression tests for two real bugs fixed in this module:
  - trigger_manage_cycle crashed with TypeError when evicting memories whose
    created_at was naive (write_memory writes naive datetimes) because the
    cutoff was tz-aware — any real entry crashed the expiry sweep.
  - _calculate_experience_metrics computed recent_intervention_rate and
    intervention_improvement_rate over the intervention-ONLY filtered list,
    making both metrics degenerate (rate always 1.0 when any intervention
    existed; improvement always 0.0) — see BUG FIX note in the module.

Documented unreachable: ObservationSpace.to_vector's `else` branch — the
feature list is fixed and only contains str/float/int fields.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from core.memory.pomdp_memory_framework import (
    ActionSpace,
    ExperienceCalculator,
    ExperienceMetrics,
    MemoryAccessPattern,
    MemoryConsolidation,
    MemoryEntry,
    MemoryManager,
    MemoryStatus,
    MemoryType,
    ObservationSpace,
    create_test_memory,
    get_experience_calculator,
    get_memory_manager,
    simulate_agent_experience,
)


def _obs(agent_id="a1", task_type="CHAT", **kw) -> ObservationSpace:
    base = dict(agent_id=agent_id, task_type=task_type,
                available_tools=["llm", "canvas"])
    base.update(kw)
    return ObservationSpace(**base)


def _entry(**kw) -> MemoryEntry:
    base = dict(observation=_obs(), action_taken="act", reward=0.8,
                next_state="ok", content={"text": "some memory content"})
    base.update(kw)
    return MemoryEntry(**base)


def _mgr(**kw) -> MemoryManager:
    mgr = MemoryManager(Mock())
    for k, v in kw.items():
        setattr(mgr, k, v)
    return mgr


# ─── Enums & Constants ───────────────────────────────────────────────────────

class TestEnums:
    def test_memory_type_values(self):
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.WORKING.value == "working"

    def test_memory_access_pattern_values(self):
        assert MemoryAccessPattern.RECALL.value == "recall"
        assert MemoryAccessPattern.RECOGNITION.value == "recognition"
        assert MemoryAccessPattern.INTEGRATION.value == "integration"

    def test_memory_status_values(self):
        assert MemoryStatus.PENDING.value == "pending"
        assert MemoryStatus.INDEXED.value == "indexed"
        assert MemoryStatus.CONSOLIDATING.value == "consolidating"
        assert MemoryStatus.CONSOLIDATED.value == "consolidated"
        assert MemoryStatus.EXPIRED.value == "expired"


# ─── Observation / Action spaces ─────────────────────────────────────────────

class TestObservationSpace:
    def test_defaults(self):
        obs = ObservationSpace()
        assert obs.agent_id == ""
        assert obs.recent_success_rate == 0.0
        assert obs.user_capabilities == []

    def test_to_dict(self):
        obs = _obs(user_intent="help", user_capabilities=["read"],
                   user_emotion="neutral", system_state={"cpu": 0.1},
                   resource_constraints={"mem": 100}, recent_success_rate=0.9,
                   recent_intervention_count=2)
        data = obs.to_dict()
        assert data["agent_id"] == "a1"
        assert data["task_type"] == "CHAT"
        assert data["user_intent"] == "help"
        assert data["user_capabilities"] == ["read"]
        assert data["user_emotion"] == "neutral"
        assert data["available_tools"] == ["llm", "canvas"]
        assert data["system_state"] == {"cpu": 0.1}
        assert data["resource_constraints"] == {"mem": 100}
        assert data["recent_success_rate"] == 0.9
        assert data["recent_intervention_count"] == 2
        assert "timestamp" in data
        assert data["timestamp"] == obs.timestamp.isoformat()

    def test_to_vector_string_float_int_features(self):
        obs = _obs(user_intent="hello", available_tools=["a", "b", "c"],
                   recent_success_rate=0.5, recent_intervention_count=3)
        vec = obs.to_vector()
        assert len(vec) == 5
        # Feature 0: task_type str hash-encoded in [0, 1)
        assert 0.0 <= vec[0] < 1.0
        # Feature 1: user_intent str hash-encoded in [0, 1)
        assert 0.0 <= vec[1] < 1.0
        # Feature 2: len(available_tools) as float/100
        assert vec[2] == pytest.approx(3 / 100.0)
        # Feature 3: recent_success_rate passes through
        assert vec[3] == pytest.approx(0.5)
        # Feature 4: intervention count as float/100
        assert vec[4] == pytest.approx(3 / 100.0)

    def test_to_vector_empty_strings_and_zeroes(self):
        obs = ObservationSpace()
        vec = obs.to_vector()
        assert vec[2] == 0.0
        assert vec[3] == 0.0
        assert vec[4] == 0.0
        assert 0.0 <= vec[0] < 1.0
        assert 0.0 <= vec[1] < 1.0


class TestActionSpace:
    def test_can_perform_action_by_maturity_rank(self):
        assert ActionSpace(maturity_level="AUTONOMOUS").can_perform_action(4)
        assert ActionSpace(maturity_level="SUPERVISED").can_perform_action(3)
        assert not ActionSpace(maturity_level="STUDENT").can_perform_action(2)
        assert ActionSpace(maturity_level="STUDENT").can_perform_action(1)

    def test_can_perform_action_unknown_maturity_defaults_to_rank_1(self):
        space = ActionSpace(maturity_level="MYSTERY")
        assert space.can_perform_action(1)
        assert not space.can_perform_action(2)

    def test_can_perform_action_boundaries(self):
        space = ActionSpace(maturity_level="INTERN")
        assert space.can_perform_action(2)
        assert not space.can_perform_action(3)


# ─── MemoryEntry ─────────────────────────────────────────────────────────────

class TestMemoryEntry:
    def test_defaults(self):
        entry = MemoryEntry()
        assert entry.id
        assert entry.memory_type == MemoryType.EPISODIC
        assert entry.status == MemoryStatus.PENDING
        assert entry.access_count == 0
        assert entry.quality_score == 0.0
        assert entry.success_outcome is True
        assert entry.task_complexity == 1

    def test_to_dict_with_observation(self):
        entry = _entry(learning_value=0.7)
        data = entry.to_dict()
        assert data["id"] == entry.id
        assert data["memory_type"] == "episodic"
        assert data["status"] == "pending"
        assert data["observation"]["agent_id"] == "a1"
        assert data["action_taken"] == "act"
        assert data["reward"] == 0.8
        assert data["next_state"] == "ok"
        assert data["learning_value"] == 0.7
        assert "created_at" in data and "last_accessed" in data
        assert data["content"] == {"text": "some memory content"}

    def test_to_dict_without_observation(self):
        entry = MemoryEntry()
        data = entry.to_dict()
        assert data["observation"] is None


# ─── MemoryManager: init + hypothesis trajectories ───────────────────────────

class TestMemoryManagerInit:
    def test_init_sets_state(self):
        db = Mock()
        mgr = MemoryManager(db, lancedb_handler="ldb")
        assert mgr.db is db
        assert mgr.lancedb == "ldb"
        assert mgr._episodic_memory == {}
        assert mgr._semantic_memory == {}
        assert mgr._working_memory == {}
        assert mgr._write_queue == []
        assert mgr._consolidation_queue == []
        assert mgr.working_memory_capacity == 100
        assert mgr.episodic_retention_days == 90
        assert mgr.consolidation_threshold == 5


class TestHypothesisTrajectory:
    def test_save_stores_semantic_entry_with_hashed_key(self):
        mgr = _mgr()
        mgr.save_hypothesis_trajectory(
            "  Fix the Parser Bug  ", [{"step": 1}], ["branch_a"])
        assert len(mgr._semantic_memory) == 1
        entry = next(iter(mgr._semantic_memory.values()))
        assert entry.memory_type == MemoryType.SEMANTIC
        assert entry.access_count == 1
        assert entry.reward == 1.0
        assert entry.content == ('{"task_query": "  Fix the Parser Bug  ", '
                                 '"winning_trajectory": [{"step": 1}], '
                                 '"pruned_failure_branches": ["branch_a"]}')
        # Key is a sha256 of the lowercased trimmed query (deterministic)
        import hashlib
        expected_key = hashlib.sha256(
            "fix the parser bug".encode("utf-8")).hexdigest()
        assert expected_key in mgr._semantic_memory

    def test_recall_found_trajectory_increments_access(self):
        mgr = _mgr()
        mgr.save_hypothesis_trajectory("same query", [1], [])
        result = mgr.recall_hypothesis_trajectory("same query")
        assert result == {"task_query": "same query",
                          "winning_trajectory": [1],
                          "pruned_failure_branches": []}
        entry = next(iter(mgr._semantic_memory.values()))
        assert entry.access_count == 2

    def test_recall_corrupt_json_returns_none(self):
        mgr = _mgr()
        import hashlib
        key = hashlib.sha256("anything".encode("utf-8")).hexdigest()
        mgr._semantic_memory[key] = MemoryEntry(content="{not json!!")
        assert mgr.recall_hypothesis_trajectory("anything") is None

    def test_recall_missing_returns_none(self):
        assert _mgr().recall_hypothesis_trajectory("missing") is None


# ─── WRITE phase ─────────────────────────────────────────────────────────────

class TestWriteMemory:
    def test_write_episodic(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        assert entry.status == MemoryStatus.PENDING
        assert entry.reward == 0.5
        assert mgr._episodic_memory[entry.id] is entry
        assert entry not in mgr._semantic_memory.values()
        assert entry.id not in mgr._working_memory

    def test_write_semantic(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 1.0, "ok",
                                 {"text": "x"}, memory_type=MemoryType.SEMANTIC)
        assert mgr._semantic_memory[entry.id] is entry
        assert entry.id not in mgr._episodic_memory

    def test_write_working(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 0.0, "ctx",
                                 {"text": "x"}, memory_type=MemoryType.WORKING)
        assert mgr._working_memory[entry.id] is entry

    def test_write_working_fifo_evicts_oldest_at_capacity(self):
        mgr = _mgr(working_memory_capacity=2)
        e1 = mgr.write_memory(_obs(), "act", 0.0, "ctx", {"text": "x"},
                              memory_type=MemoryType.WORKING)
        e2 = mgr.write_memory(_obs(), "act", 0.0, "ctx", {"text": "x"},
                              memory_type=MemoryType.WORKING)
        assert set(mgr._working_memory) == {e1.id, e2.id}
        e3 = mgr.write_memory(_obs(), "act", 0.0, "ctx", {"text": "x"},
                              memory_type=MemoryType.WORKING)
        assert set(mgr._working_memory) == {e2.id, e3.id}
        assert e1.id not in mgr._working_memory


# ─── MANAGE phase ────────────────────────────────────────────────────────────

class TestTriggerManageCycle:
    def test_indexes_pending_memories(self):
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "hello world"})
        e2 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "more text"})
        processed = mgr.trigger_manage_cycle()
        assert processed == 2
        assert e1.status == MemoryStatus.INDEXED
        assert e2.status == MemoryStatus.INDEXED
        assert e1.summary == "hello world"
        assert e1.embedding is not None

    def test_consolidates_frequently_accessed(self):
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        e1.access_count = 5
        e1.status = MemoryStatus.INDEXED
        processed = mgr.trigger_manage_cycle()
        assert processed == 1  # 0 indexed (already), 1 consolidated
        assert e1.status == MemoryStatus.CONSOLIDATED
        assert e1.consolidation_level == 2

    def test_consolidation_respects_threshold(self):
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        e1.access_count = 4  # below threshold of 5
        e1.status = MemoryStatus.INDEXED
        processed = mgr.trigger_manage_cycle()
        assert processed == 0
        assert e1.status == MemoryStatus.INDEXED

    def test_evicts_expired_by_age_naive_created_at(self):
        """Regression: naive created_at (as written by write_memory) used to
        crash the expiry sweep with a naive-vs-aware TypeError."""
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        e1.created_at = datetime.now() - timedelta(days=200)  # naive
        e2 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "y"})
        mgr.trigger_manage_cycle()  # must not raise
        assert e1.id not in mgr._episodic_memory
        assert e2.id in mgr._episodic_memory

    def test_evicts_expired_by_age_aware_created_at(self):
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        e1.created_at = datetime.now(timezone.utc) - timedelta(days=91)
        mgr.trigger_manage_cycle()
        assert e1.id not in mgr._episodic_memory

    def test_evicts_marked_expired_regardless_of_age(self):
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        e1.status = MemoryStatus.EXPIRED
        e1.created_at = datetime.now(timezone.utc)
        mgr.trigger_manage_cycle()
        assert e1.id not in mgr._episodic_memory

    def test_retains_recent_memories(self):
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        e1.created_at = datetime.now() - timedelta(days=30)
        mgr.trigger_manage_cycle()
        assert e1.id in mgr._episodic_memory


class TestIndexMemory:
    def test_generates_embedding_and_summary(self):
        mgr = _mgr()
        entry = _entry(content={"text": "short text"})
        mgr._index_memory(entry)
        assert entry.status == MemoryStatus.INDEXED
        assert entry.embedding is not None
        assert entry.embedding.dtype == np_dtype()
        assert entry.summary == "short text"

    def test_skips_existing_embedding_and_summary(self):
        mgr = _mgr()
        import numpy as np
        entry = _entry(content={"text": "x"}, embedding=np.array([1.0]),
                       summary="already")
        mgr._index_memory(entry)
        assert entry.summary == "already"
        assert entry.embedding.tolist() == [1.0]

    def test_no_embedding_without_text_key(self):
        mgr = _mgr()
        entry = _entry(content={"action": "ran"})
        mgr._index_memory(entry)
        assert entry.embedding is None
        assert entry.summary == "Action: ran"


class TestConsolidateMemory:
    def test_marks_consolidated(self):
        mgr = _mgr()
        entry = _entry()
        mgr._consolidate_memory(entry)
        assert entry.status == MemoryStatus.CONSOLIDATED
        assert entry.consolidation_level == 2


# ─── READ phase ──────────────────────────────────────────────────────────────

class TestReadMemory:
    def test_read_episodic_updates_tracking_and_quality(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        got = mgr.read_memory(entry.id)
        assert got is entry
        assert entry.access_count == 1
        assert entry.last_accessed is not None
        assert entry.quality_score > 0.5  # base 0.5 + factors

    def test_read_episodic_expired_returns_none(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        entry.status = MemoryStatus.EXPIRED
        assert mgr.read_memory(entry.id) is None

    def test_read_semantic(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"},
                                 memory_type=MemoryType.SEMANTIC)
        got = mgr.read_memory(entry.id)
        assert got is entry
        assert entry.access_count == 1

    def test_read_working(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 0.5, "ctx", {"text": "x"},
                                 memory_type=MemoryType.WORKING)
        got = mgr.read_memory(entry.id)
        assert got is entry
        assert entry.access_count == 1

    def test_read_missing_returns_none(self):
        assert _mgr().read_memory("nope") is None

    def test_read_with_integration_pattern(self):
        mgr = _mgr()
        entry = mgr.write_memory(_obs(), "act", 0.5, "ok", {"text": "x"})
        got = mgr.read_memory(entry.id,
                              access_pattern=MemoryAccessPattern.INTEGRATION)
        assert got is entry


class TestRecallRecent:
    def test_filters_by_agent_and_task_type(self):
        mgr = _mgr()
        a1 = mgr.write_memory(_obs(agent_id="a1", task_type="CHAT"),
                              "act", 0.5, "ok", {"text": "1"})
        a2 = mgr.write_memory(_obs(agent_id="a2", task_type="CHAT"),
                              "act", 0.5, "ok", {"text": "2"})
        a3 = mgr.write_memory(_obs(agent_id="a1", task_type="WORKFLOW"),
                              "act", 0.5, "ok", {"text": "3"})
        # newest first (a3 written last)
        assert [m.id for m in mgr.recall_recent("a1")] == [a3.id, a1.id]
        assert [m.id for m in mgr.recall_recent("a1", task_type="CHAT")] == [a1.id]
        assert [m.id for m in mgr.recall_recent("a1", task_type="WORKFLOW")] == [a3.id]
        assert [m.id for m in mgr.recall_recent("nobody")] == []

    def test_sorts_by_created_at_desc_and_respects_limit(self):
        mgr = _mgr()
        entries = []
        for i in range(5):
            e = mgr.write_memory(_obs(agent_id="a1"), "act", 0.5, "ok",
                                 {"text": str(i)})
            e.created_at = datetime.now(timezone.utc) - timedelta(hours=i)
            entries.append(e)
        got = mgr.recall_recent("a1", limit=3)
        assert [m.id for m in got] == [e.id for e in [entries[0], entries[1], entries[2]]]

    def test_excludes_expired(self):
        mgr = _mgr()
        e1 = mgr.write_memory(_obs(agent_id="a1"), "act", 0.5, "ok", {"text": "x"})
        e2 = mgr.write_memory(_obs(agent_id="a1"), "act", 0.5, "ok", {"text": "y"})
        e2.status = MemoryStatus.EXPIRED
        assert [m.id for m in mgr.recall_recent("a1")] == [e1.id]

    def test_handles_entries_without_observation(self):
        mgr = _mgr()
        orphan = MemoryEntry(content={"text": "no obs"})
        mgr._episodic_memory[orphan.id] = orphan
        assert mgr.recall_recent("a1") == []


class TestRecallByQuality:
    def test_filters_sorts_limits(self):
        mgr = _mgr()
        low = mgr.write_memory(_obs(agent_id="a1"), "act", 0.5, "ok", {"text": "1"})
        low.quality_score = 0.4
        high1 = mgr.write_memory(_obs(agent_id="a1"), "act", 0.5, "ok", {"text": "2"})
        high1.quality_score = 0.9
        high2 = mgr.write_memory(_obs(agent_id="a1"), "act", 0.5, "ok", {"text": "3"})
        high2.quality_score = 0.8
        other = mgr.write_memory(_obs(agent_id="a2"), "act", 0.5, "ok", {"text": "4"})
        other.quality_score = 0.9
        got = mgr.recall_by_quality("a1", min_quality=0.5, limit=1)
        assert [m.id for m in got] == [high1.id]
        got2 = mgr.recall_by_quality("a1", min_quality=0.5)
        assert [m.id for m in got2] == [high1.id, high2.id]

    def test_excludes_expired(self):
        mgr = _mgr()
        e = mgr.write_memory(_obs(agent_id="a1"), "act", 0.5, "ok", {"text": "x"})
        e.quality_score = 0.9
        e.status = MemoryStatus.EXPIRED
        assert mgr.recall_by_quality("a1") == []


# ─── Helper methods ──────────────────────────────────────────────────────────

def np_dtype():
    import numpy as np
    return np.dtype("float32")


class TestEmbedding:
    def test_generates_deterministic_hash_vector(self):
        mgr = _mgr()
        v1 = mgr._generate_embedding("hello world")
        v2 = mgr._generate_embedding("hello world")
        v3 = mgr._generate_embedding("different")
        assert v1.shape == (32,)  # md5 hexdigest is 32 chars
        assert v1.dtype == np_dtype()
        assert (v1 == v2).all()
        assert not (v1 == v3).all()


class TestGenerateSummary:
    def test_long_text_truncated(self):
        mgr = _mgr()
        assert mgr._generate_summary({"text": "x" * 150}) == "x" * 100 + "..."

    def test_short_text_kept(self):
        mgr = _mgr()
        assert mgr._generate_summary({"text": "hello"}) == "hello"

    def test_action_fallback(self):
        mgr = _mgr()
        assert mgr._generate_summary({"action": "responded"}) == "Action: responded"

    def test_other_content_fallback(self):
        mgr = _mgr()
        summary = mgr._generate_summary({"nested": {"a": 1}})
        assert summary == str({"nested": {"a": 1}})[:100]


class TestQualityScore:
    def test_base_score_only(self):
        mgr = _mgr()
        entry = _entry()
        entry.created_at = datetime.now(timezone.utc) - timedelta(days=40)
        entry.success_outcome = False
        entry.learning_value = 0.0
        entry.intervention_required = True
        assert mgr._calculate_quality_score(MemoryAccessPattern.RECALL,
                                            entry) == pytest.approx(0.5)

    def test_access_frequency_factor_capped(self):
        mgr = _mgr()
        entry = _entry()
        entry.created_at = datetime.now(timezone.utc) - timedelta(days=40)
        entry.success_outcome = False
        entry.learning_value = 0.0
        entry.intervention_required = True
        entry.access_count = 250
        assert mgr._calculate_quality_score(MemoryAccessPattern.RECALL,
                                            entry) == pytest.approx(0.8)

    def test_recency_and_success_factors(self):
        mgr = _mgr()
        entry = _entry()
        entry.created_at = datetime.now(timezone.utc)
        entry.success_outcome = True
        entry.intervention_required = True
        entry.access_count = 0
        score = mgr._calculate_quality_score(MemoryAccessPattern.RECALL, entry)
        assert score == pytest.approx(0.5 + 0.2 + 0.2)  # recency + success

    def test_learning_value_factor(self):
        mgr = _mgr()
        entry = _entry()
        entry.created_at = datetime.now(timezone.utc) - timedelta(days=40)
        entry.success_outcome = False
        entry.learning_value = 0.5
        entry.intervention_required = True
        score = mgr._calculate_quality_score(MemoryAccessPattern.RECALL, entry)
        assert score == pytest.approx(0.5 + 0.15)

    def test_learning_value_factor_capped(self):
        mgr = _mgr()
        entry = _entry()
        entry.created_at = datetime.now(timezone.utc) - timedelta(days=40)
        entry.success_outcome = False
        entry.learning_value = 5.0
        entry.intervention_required = True
        score = mgr._calculate_quality_score(MemoryAccessPattern.RECALL, entry)
        assert score == pytest.approx(0.5 + 0.3)

    def test_no_intervention_bonus_and_total_cap(self):
        mgr = _mgr()
        entry = _entry()
        entry.created_at = datetime.now(timezone.utc)
        entry.success_outcome = True
        entry.learning_value = 5.0
        entry.intervention_required = False
        entry.access_count = 500
        score = mgr._calculate_quality_score(MemoryAccessPattern.RECALL, entry)
        assert score == pytest.approx(1.0)  # capped


class TestMemoryStatistics:
    def test_statistics_breakdown(self):
        mgr = _mgr()
        p = mgr.write_memory(_obs(), "a", 0.5, "ok", {"text": "x"})
        i = mgr.write_memory(_obs(), "a", 0.5, "ok", {"text": "y"})
        i.status = MemoryStatus.INDEXED
        c = mgr.write_memory(_obs(), "a", 0.5, "ok", {"text": "z"})
        c.status = MemoryStatus.CONSOLIDATED
        e = mgr.write_memory(_obs(), "a", 0.5, "ok", {"text": "w"})
        e.status = MemoryStatus.EXPIRED
        s = mgr.write_memory(_obs(), "a", 0.5, "ok", {"text": "v"},
                             memory_type=MemoryType.SEMANTIC)
        s.status = MemoryStatus.INDEXED
        w = mgr.write_memory(_obs(), "a", 0.5, "ctx", {"text": "u"},
                             memory_type=MemoryType.WORKING)
        stats = mgr.get_memory_statistics()
        assert stats["total_memories"] == 5
        assert stats["episodic"] == {"total": 4, "pending": 1, "indexed": 1,
                                     "consolidated": 1, "expired": 1}
        assert stats["working"]["total"] == 1
        assert stats["working"]["utilization"] == pytest.approx(1 / 100.0)
        assert stats["semantic"]["total"] == 1
        assert stats["semantic"]["indexed"] == 1


# ─── ExperienceCalculator ────────────────────────────────────────────────────

CRITERIA = {
    "INTERN": {"min_episodes": 10, "max_intervention_rate": 0.5,
               "min_constitutional_score": 0.70, "min_learning_consistency": 0.6},
    "SUPERVISED": {"min_episodes": 20, "max_intervention_rate": 0.3,
                   "min_constitutional_score": 0.80,
                   "min_learning_consistency": 0.7},
}


def _quality_memories(agent_id="a1", count=20, quality=0.9, success=True,
                      intervention=False, learning_value=0.8, autonomy=4):
    memories = []
    for i in range(count):
        m = _entry(observation=_obs(agent_id=agent_id, task_type="WORKFLOW"),
                   content={"text": f"episode {i}"})
        m.quality_score = quality
        m.success_outcome = success
        m.intervention_required = intervention
        m.learning_value = learning_value
        m.autonomy_level = autonomy
        memories.append(m)
    return memories


class TestReadinessScore:
    def test_no_memories_returns_not_ready(self):
        mgr = _mgr()
        calc = ExperienceCalculator(Mock(), mgr)
        result = calc.calculate_readiness_score("a1", "INTERN", CRITERIA)
        assert result["ready"] is False
        assert result["score"] == 0.0
        assert result["episode_count"] == 0
        assert "No episodic memories" in result["gaps"][0]

    def test_fully_ready_agent(self):
        mgr = _mgr()
        for m in _quality_memories():
            mgr._episodic_memory[m.id] = m
        calc = ExperienceCalculator(Mock(), mgr)
        result = calc.calculate_readiness_score("a1", "INTERN", CRITERIA)
        assert result["ready"] is True
        assert result["score"] == pytest.approx(100.0)
        assert result["gaps"] == []
        assert result["episode_count"] == pytest.approx(18.0)  # 20 * 0.9

    def test_unknown_target_maturity_uses_default_criteria(self):
        mgr = _mgr()
        for m in _quality_memories(count=3, quality=0.5, success=True,
                                   intervention=True):
            mgr._episodic_memory[m.id] = m
        calc = ExperienceCalculator(Mock(), mgr)
        # Empty criteria dict -> default min_episodes=10, max_intervention=0.5
        result = calc.calculate_readiness_score("a1", "BOGUS", {})
        assert result["ready"] is False
        assert any("quality episodes" in g for g in result["gaps"])

    def test_intervention_rate_gap(self):
        mgr = _mgr()
        # 12 memories, 8 of the first 10 require intervention -> rate 0.8
        for i in range(12):
            m = _quality_memories(count=1, quality=0.9)[0]
            m.intervention_required = i < 8
            mgr._episodic_memory[m.id] = m
        calc = ExperienceCalculator(Mock(), mgr)
        result = calc.calculate_readiness_score("a1", "INTERN", CRITERIA)
        assert any("Intervention rate" in g for g in result["gaps"])

    def test_constitutional_score_gap(self):
        mgr = _mgr()
        for m in _quality_memories(count=20, quality=0.5):
            mgr._episodic_memory[m.id] = m
        calc = ExperienceCalculator(Mock(), mgr)
        result = calc.calculate_readiness_score("a1", "INTERN", CRITERIA)
        assert any("Memory quality" in g for g in result["gaps"])

    def test_learning_consistency_gap(self):
        mgr = _mgr()
        for m in _quality_memories(count=8, quality=0.9):  # <= 10 successes
            mgr._episodic_memory[m.id] = m
        calc = ExperienceCalculator(Mock(), mgr)
        result = calc.calculate_readiness_score("a1", "INTERN", CRITERIA)
        assert any("Learning consistency" in g for g in result["gaps"])

    def test_worsening_intervention_trend_gap(self):
        """Regression: intervention_improvement_rate was always 0.0 (computed
        over an all-intervention list), so the 'not improving' gap and the
        +0.15 readiness credit could never both behave correctly. Now a
        worsening trend yields a negative improvement rate."""
        mgr = _mgr()
        memories = _quality_memories(count=12, quality=0.9, success=False)
        # First half: 2 interventions; second half: 6 -> improvement negative
        for i, m in enumerate(memories):
            m.intervention_required = (i < 2) or (i >= 6)
            m.success_outcome = not m.intervention_required
        for m in memories:
            mgr._episodic_memory[m.id] = m
        calc = ExperienceCalculator(Mock(), mgr)
        result = calc.calculate_readiness_score("a1", "INTERN", CRITERIA)
        assert result["intervention_improvement_rate"] < 0
        assert any("not improving" in g for g in result["gaps"])


class TestExperienceMetrics:
    def test_empty_list_returns_defaults(self):
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics([])
        assert metrics.quality_weighted_episode_count == 0.0
        assert metrics.recent_intervention_rate == 0.0
        assert metrics.cross_episode_learning_score == 0.0

    def test_no_interventions_rate_zero(self):
        memories = _quality_memories(count=12)
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.recent_intervention_rate == 0.0
        assert metrics.intervention_improvement_rate == 0.0
        assert metrics.avg_memory_quality_score == pytest.approx(0.9)
        assert metrics.high_quality_memories_count == 12
        assert metrics.quality_weighted_episode_count == pytest.approx(10.8)
        assert metrics.cross_episode_learning_score == 1.0
        assert metrics.complex_task_success_rate == 1.0

    def test_recent_intervention_rate_is_fraction_of_recent_episodes(self):
        """Regression: the rate used to be computed over the intervention-only
        sublist (always 1.0). Now it is the fraction of the most recent 10
        episodes that required intervention."""
        memories = _quality_memories(count=12, quality=0.9, success=False)
        for i, m in enumerate(memories):
            m.intervention_required = i < 3  # 3 of the first 10 recent
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.recent_intervention_rate == pytest.approx(0.3)

    def test_improving_trend_positive_improvement(self):
        memories = _quality_memories(count=12, quality=0.9, success=False)
        for i, m in enumerate(memories):
            m.intervention_required = (0 <= i < 6) and (i % 2 == 0)  # 3 in first half
            m.intervention_required = m.intervention_required or (i == 11)  # 1 late
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        # first_half rate = 3/6 = 0.5; second_half = 1/6 ~ 0.167
        assert metrics.intervention_improvement_rate == pytest.approx(
            (0.5 - 1 / 6) / 0.5)

    def test_improvement_clamped_to_one(self):
        memories = _quality_memories(count=12, quality=0.9, success=False)
        for i, m in enumerate(memories):
            m.intervention_required = i < 6
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.intervention_improvement_rate == pytest.approx(1.0)

    def test_improvement_clamped_to_negative_one(self):
        memories = _quality_memories(count=12, quality=0.9, success=False)
        for i, m in enumerate(memories):
            m.intervention_required = (i < 2) or (i >= 6)  # 2 first-half, 6 second
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.intervention_improvement_rate == pytest.approx(-1.0)

    def test_improvement_skipped_when_first_half_clean(self):
        memories = _quality_memories(count=12, quality=0.9, success=False)
        for i, m in enumerate(memories):
            m.intervention_required = i >= 6  # no interventions in first half
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.intervention_improvement_rate == 0.0

    def test_consistency_default_with_few_successes(self):
        memories = _quality_memories(count=8, quality=0.9, success=True)
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.cross_episode_learning_score == 0.5

    def test_consistency_is_success_rate_with_enough_data(self):
        memories = _quality_memories(count=12, quality=0.9, success=True)
        memories[0].success_outcome = False
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.cross_episode_learning_score == pytest.approx(11 / 12)

    def test_no_high_autonomy_memories(self):
        memories = _quality_memories(count=12, quality=0.9, autonomy=1)
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.complex_task_success_rate == 0.0

    def test_complex_task_success_rate_only_high_autonomy(self):
        memories = _quality_memories(count=6, quality=0.9, autonomy=4)
        memories[0].autonomy_level = 2  # excluded from denominator
        metrics = ExperienceCalculator(Mock(), _mgr())._calculate_experience_metrics(
            memories)
        assert metrics.complex_task_success_rate == 1.0


# ─── Offline MemoryConsolidation ─────────────────────────────────────────────

class TestMemoryConsolidation:
    def test_init(self):
        mgr = _mgr()
        cons = MemoryConsolidation(mgr)
        assert cons.memory_manager is mgr

    async def test_consolidates_candidate_batch(self):
        mgr = _mgr()
        for i in range(3):
            m = _entry(observation=_obs(agent_id="a1"))
            m.status = MemoryStatus.INDEXED
            m.consolidation_level = 1
            m.access_count = 5
            mgr._episodic_memory[m.id] = m
        cons = MemoryConsolidation(mgr)
        count = await cons.consolidate_memories("a1", batch_size=2)
        assert count == 2
        consolidated = [m for m in mgr._episodic_memory.values()
                        if m.status == MemoryStatus.CONSOLIDATED]
        assert len(consolidated) == 2
        assert all(m.consolidation_level == 2 for m in consolidated)

    async def test_filters_by_agent_status_level_access(self):
        mgr = _mgr()
        wrong_agent = _entry(observation=_obs(agent_id="other"))
        wrong_agent.status = MemoryStatus.INDEXED
        wrong_agent.consolidation_level = 1
        wrong_agent.access_count = 5
        mgr._episodic_memory[wrong_agent.id] = wrong_agent
        pending = _entry(observation=_obs(agent_id="a1"))
        pending.status = MemoryStatus.PENDING
        pending.consolidation_level = 1
        pending.access_count = 5
        mgr._episodic_memory[pending.id] = pending
        cons = MemoryConsolidation(mgr)
        count = await cons.consolidate_memories("a1")
        assert count == 0

    async def test_consolidation_exception_swallowed(self):
        mgr = _mgr()
        m = _entry(observation=_obs(agent_id="a1"))
        m.status = MemoryStatus.INDEXED
        m.consolidation_level = 1
        m.access_count = 5
        mgr._episodic_memory[m.id] = m
        cons = MemoryConsolidation(mgr)
        with patch.object(cons, "_strengthen_associations",
                          side_effect=ValueError("boom")):
            count = await cons.consolidate_memories("a1")
        assert count == 0
        assert m.status == MemoryStatus.INDEXED  # unchanged

    def test_strengthen_associations_is_noop(self):
        cons = MemoryConsolidation(_mgr())
        assert cons._strengthen_associations(_entry()) is None

    def test_extract_patterns_is_noop(self):
        cons = MemoryConsolidation(_mgr())
        assert cons._extract_patterns(_entry()) is None


# ─── Factories ───────────────────────────────────────────────────────────────

class TestFactories:
    def test_get_memory_manager(self):
        db = Mock()
        mgr = get_memory_manager(db, lancedb_handler="x")
        assert isinstance(mgr, MemoryManager)
        assert mgr.db is db
        assert mgr.lancedb == "x"

    def test_get_experience_calculator(self):
        mgr = _mgr()
        calc = get_experience_calculator(Mock(), mgr)
        assert isinstance(calc, ExperienceCalculator)
        assert calc.memory_manager is mgr


# ─── Testing utilities ───────────────────────────────────────────────────────

class TestCreateTestMemory:
    def test_defaults(self):
        entry = create_test_memory()
        assert entry.observation.agent_id == "test_agent"
        assert entry.observation.task_type == "CHAT"
        assert entry.observation.available_tools == ["llm", "canvas"]
        assert entry.action_taken == "response_sent"
        assert entry.reward == 0.8
        assert entry.next_state == "success"
        assert entry.content == {"text": "Test memory content"}

    def test_custom_arguments(self):
        entry = create_test_memory(agent_id="a9", task_type="WORKFLOW",
                                   action="task_completed", reward=0.3,
                                   outcome="needs_intervention",
                                   content={"text": "custom"},
                                   memory_type=MemoryType.SEMANTIC)
        assert entry.memory_type == MemoryType.SEMANTIC
        assert entry.observation.agent_id == "a9"
        assert entry.content == {"text": "custom"}


class TestSimulateAgentExperience:
    def test_simulates_with_interventions(self):
        memories = simulate_agent_experience("a1", num_episodes=20,
                                             intervention_rate=0.3)
        assert len(memories) == 20
        interventions = [m for m in memories if m.intervention_required]
        # every Nth episode (N = int(1/0.3) = 3) requires intervention
        assert len(interventions) == 7  # i % 3 == 0
        assert all(m.intervention_required == (i % 3 == 0)
                   for i, m in enumerate(memories))
        assert all(m.observation.agent_id == "a1" for m in memories)
        assert all(m.observation.task_type == "WORKFLOW" for m in memories)
        assert all(m.learning_value in (0.8, 0.2) for m in memories)
        # intervention episodes fail (2/3 overall success)
        assert memories[0].success_outcome is False
        assert memories[1].success_outcome is True
        assert memories[0].reward == 0.3
        assert memories[0].learning_value == 0.2

    def test_simulates_without_interventions(self):
        memories = simulate_agent_experience("a2", num_episodes=5,
                                             intervention_rate=0.0)
        assert len(memories) == 5
        assert all(not m.intervention_required for m in memories)
        assert all(m.success_outcome for m in memories)
        assert all(m.reward == 0.8 for m in memories)

    def test_simulate_full_intervention_rate(self):
        memories = simulate_agent_experience("a3", num_episodes=6,
                                             intervention_rate=1.0)
        assert len(memories) == 6
        assert all(m.intervention_required for m in memories)
        # success follows the fixed 2/3 pattern independent of intervention
        assert all(m.success_outcome == (i % 3 != 0)
                   for i, m in enumerate(memories))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
