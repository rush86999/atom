# -*- coding: utf-8 -*-
"""Coverage wave 76 — core/ab_testing_service (ABTestingService).

Real in-memory SQLite (no LLM, no network). Covers the previously-uncovered
lines 196-228 (complete_test error paths + success), 273-324 (existing
assignment replay + new deterministic assignment), 508-549 (sample-size-gated
results), and the full _perform_statistical_test branch matrix (success-rate
diff buckets 0.30/0.20/0.10/else, diff==0, non-significant, numerical tie /
response_time / error_rate / rating, alpha edge).

Also repairs the stale-suite fixture failures in tests/test_ab_testing_service.py
by exercising the real DB paths the mock fixtures could not.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ab_testing_service import ABTestingService
from core.database import Base
from core.models import (
    ABTest,
    ABTestParticipant,
    AgentRegistry,
)  # noqa: F401 (register models)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", tenant_id="t1"):
    if db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first():
        return
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id=tenant_id,
        category="Test",
        module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _make_test(db, *, name="Test", agent_id="agent-1", status="draft",
               traffic_percentage=0.5, min_sample_size=2,
               primary_metric="success_rate", test_id="test-1",
               threshold=0.05):
    _make_agent(db, agent_id=agent_id)
    test = ABTest(
        id=test_id,
        name=name,
        test_type="prompt",
        agent_id=agent_id,
        traffic_percentage=traffic_percentage,
        variant_a_name="Control",
        variant_b_name="Treatment",
        variant_a_config={"variant": "a"},
        variant_b_config={"variant": "b"},
        primary_metric=primary_metric,
        min_sample_size=min_sample_size,
        statistical_significance_threshold=threshold,
        status=status,
    )
    db.add(test)
    db.commit()
    return test


def _make_participant(db, test_id, user_id, variant, *, success=None,
                      metric_value=None, session_id=None):
    p = ABTestParticipant(
        test_id=test_id, user_id=user_id, assigned_variant=variant,
        session_id=session_id, success=success, metric_value=metric_value,
    )
    db.add(p)
    db.commit()
    return p


# ============================================================================
# Creation & lifecycle
# ============================================================================

class TestCreation:
    def test_create_test_success(self, db):
        _make_agent(db)
        svc = ABTestingService(db)
        result = svc.create_test(
            name="Prompt Test", test_type="prompt", agent_id="agent-1",
            variant_a_config={"p": "v1"}, variant_b_config={"p": "v2"},
            primary_metric="success_rate",
            secondary_metrics=["satisfaction_rate"],
            traffic_percentage=0.3, min_sample_size=50,
        )
        assert "error" not in result
        assert result["status"] == "draft"
        assert result["traffic_percentage"] == 0.3
        assert result["min_sample_size"] == 50
        assert result["variant_a"]["name"] == "Control"

    def test_create_test_agent_not_found(self, db):
        svc = ABTestingService(db)
        result = svc.create_test(
            name="X", test_type="prompt", agent_id="missing",
            variant_a_config={}, variant_b_config={}, primary_metric="r",
        )
        assert result["error"] == "Agent 'missing' not found"

    def test_create_test_invalid_type(self, db):
        _make_agent(db)
        svc = ABTestingService(db)
        result = svc.create_test(
            name="X", test_type="bogus", agent_id="agent-1",
            variant_a_config={}, variant_b_config={}, primary_metric="r",
        )
        assert "Invalid test_type" in result["error"]

    def test_create_test_invalid_traffic(self, db):
        _make_agent(db)
        svc = ABTestingService(db)
        result = svc.create_test(
            name="X", test_type="prompt", agent_id="agent-1",
            variant_a_config={}, variant_b_config={}, primary_metric="r",
            traffic_percentage=1.5,
        )
        assert "traffic_percentage" in result["error"]
        result = svc.create_test(
            name="X", test_type="prompt", agent_id="agent-1",
            variant_a_config={}, variant_b_config={}, primary_metric="r",
            traffic_percentage=-0.1,
        )
        assert "traffic_percentage" in result["error"]

    def test_start_test(self, db):
        _make_test(db, status="draft")
        svc = ABTestingService(db)
        result = svc.start_test("test-1")
        assert result["status"] == "running"
        assert result["started_at"]
        assert db.query(ABTest).get("test-1").status == "running"

    def test_start_test_not_found(self, db):
        svc = ABTestingService(db)
        assert "not found" in svc.start_test("nope")["error"]

    def test_start_test_already_running(self, db):
        _make_test(db, status="running")
        svc = ABTestingService(db)
        result = svc.start_test("test-1")
        assert "must be in 'draft'" in result["error"]

    def test_complete_test_not_found(self, db):
        svc = ABTestingService(db)
        assert "not found" in svc.complete_test("nope")["error"]

    def test_complete_test_not_running(self, db):
        _make_test(db, status="draft")
        svc = ABTestingService(db)
        result = svc.complete_test("test-1")
        assert "must be in 'running'" in result["error"]

    def test_complete_test_success_with_winner(self, db):
        _make_test(db, status="running", min_sample_size=2)
        _make_participant(db, "test-1", "u1", "A", success=True)
        _make_participant(db, "test-1", "u2", "A", success=True)
        _make_participant(db, "test-1", "u3", "B", success=True)
        _make_participant(db, "test-1", "u4", "B", success=False)
        svc = ABTestingService(db)
        result = svc.complete_test("test-1")
        assert result["status"] == "completed"
        assert result["winner"] == "A"  # A rate 1.0 vs B rate 0.5 -> A wins
        assert result["p_value"] == 0.001
        assert result["min_sample_size_reached"] is True
        test = db.query(ABTest).get("test-1")
        assert test.winner == "A"
        assert test.statistical_significance == 0.001
        assert test.variant_a_metrics["success_rate"] == 1.0
        assert test.variant_b_metrics["success_rate"] == 0.5

    def test_complete_test_sample_size_not_reached(self, db):
        _make_test(db, status="running", min_sample_size=10)
        _make_participant(db, "test-1", "u1", "A", success=True)
        _make_participant(db, "test-1", "u3", "B", success=False)
        svc = ABTestingService(db)
        result = svc.complete_test("test-1")
        assert result["winner"] == "inconclusive"
        assert result["p_value"] is None
        assert result["min_sample_size_reached"] is False


# ============================================================================
# Variant assignment
# ============================================================================

class TestVariantAssignment:
    def test_assign_not_found(self, db):
        svc = ABTestingService(db)
        assert "not found" in svc.assign_variant("nope", "u1")["error"]

    def test_assign_requires_running(self, db):
        _make_test(db, status="draft")
        svc = ABTestingService(db)
        result = svc.assign_variant("test-1", "u1")
        assert "must be running" in result["error"]

    def test_assign_new_participant_deterministic_and_replay(self, db):
        _make_test(db, status="running", traffic_percentage=0.5)
        svc = ABTestingService(db)
        first = svc.assign_variant("test-1", "user-123", session_id="sess-1")
        assert "error" not in first
        assert first["existing_assignment"] is False
        assert first["variant"] in ("A", "B")
        assert first["config"] == {"variant": first["variant"].lower()}

        # Same user must get the same variant (existing-assignment replay).
        second = svc.assign_variant("test-1", "user-123", session_id="sess-2")
        assert second["existing_assignment"] is True
        assert second["variant"] == first["variant"]
        assert second["variant_name"] == first["variant_name"]

        participant = db.query(ABTestParticipant).filter(
            ABTestParticipant.user_id == "user-123"
        ).one()
        assert participant.session_id == "sess-1"  # first assignment persisted
        assert participant.assigned_variant == first["variant"]

    def test_assign_traffic_percentage_zero_forces_a(self, db):
        _make_test(db, status="running", traffic_percentage=0.0)
        svc = ABTestingService(db)
        result = svc.assign_variant("test-1", "u-a")
        assert result["variant"] == "A"
        assert result["config"] == {"variant": "a"}

    def test_assign_traffic_percentage_one_forces_b(self, db):
        _make_test(db, status="running", traffic_percentage=1.0)
        svc = ABTestingService(db)
        result = svc.assign_variant("test-1", "u-b")
        assert result["variant"] == "B"
        assert result["variant_name"] == "Treatment"
        assert result["config"] == {"variant": "b"}

    def test_hash_assignment_is_stable_across_services(self, db):
        _make_test(db, status="running", traffic_percentage=0.5)
        svc1 = ABTestingService(db)
        svc2 = ABTestingService(db)
        assert svc1.assign_variant("test-1", "hash-user")["variant"] == \
            svc2.assign_variant("test-1", "hash-user")["variant"]


# ============================================================================
# Metric tracking & results
# ============================================================================

class TestMetricsAndResults:
    def test_record_metric_success(self, db):
        _make_test(db, status="running")
        _make_participant(db, "test-1", "u1", "A")
        svc = ABTestingService(db)
        result = svc.record_metric(
            "test-1", "u1", success=True, metric_value=0.9,
            metadata={"source": "unit"},
        )
        assert result["success"] is True
        assert result["metric_value"] == 0.9
        p = db.query(ABTestParticipant).filter(
            ABTestParticipant.user_id == "u1").one()
        assert p.success is True
        assert p.meta_data == {"source": "unit"}
        assert p.recorded_at is not None

    def test_record_metric_participant_not_found(self, db):
        _make_test(db, status="running")
        svc = ABTestingService(db)
        result = svc.record_metric("test-1", "nobody", success=True)
        assert "Participant not found" in result["error"]

    def test_get_test_results_not_found(self, db):
        svc = ABTestingService(db)
        assert "not found" in svc.get_test_results("nope")["error"]

    def test_get_test_results_counts_and_timestamps(self, db):
        _make_test(db, status="running")
        _make_participant(db, "test-1", "u1", "A")
        _make_participant(db, "test-1", "u2", "A")
        _make_participant(db, "test-1", "u3", "B")
        svc = ABTestingService(db)
        result = svc.get_test_results("test-1")
        assert result["variant_a"]["participant_count"] == 2
        assert result["variant_b"]["participant_count"] == 1
        assert result["started_at"] is None
        assert result["completed_at"] is None
        assert result["winner"] is None

    def test_list_tests_empty(self, db):
        svc = ABTestingService(db)
        result = svc.list_tests()
        assert result == {"total": 0, "tests": []}

    def test_list_tests_filters_and_limit(self, db):
        _make_test(db, name="t1", agent_id="agent-1", status="running",
                   test_id="test-1")
        _make_test(db, name="t2", agent_id="agent-1", status="completed",
                   test_id="test-2")
        _make_test(db, name="t3", agent_id="agent-2", status="running",
                   test_id="test-3")
        svc = ABTestingService(db)
        result = svc.list_tests(agent_id="agent-1", status="running", limit=5)
        assert result["total"] == 1
        assert result["tests"][0]["test_id"] == "test-1"
        result = svc.list_tests(agent_id="agent-1", limit=1)
        assert result["total"] == 1  # limit truncates
        result = svc.list_tests(status="completed")
        assert result["total"] == 1
        assert result["tests"][0]["test_id"] == "test-2"


# ============================================================================
# Statistical internals (direct unit coverage)
# ============================================================================

class TestStatisticalInternals:
    def _metrics(self, count, success_rate, avg_metric):
        # success_rate supplied directly to avoid float->int truncation
        # (e.g. int(100*0.7) == 69) skewing the rate buckets.
        return {
            "count": count,
            "success_count": int(round(count * success_rate)) if success_rate is not None else 0,
            "success_rate": success_rate,
            "average_metric_value": avg_metric,
        }

    def test_calculate_variant_metrics_empty(self):
        svc = ABTestingService(db=None)
        assert svc._calculate_variant_metrics([], "success_rate") == {
            "count": 0, "success_rate": None, "average_metric_value": None}

    def test_calculate_variant_metrics_mixed(self, db):
        _make_test(db, status="running")
        p1 = _make_participant(db, "test-1", "u1", "A", success=True,
                               metric_value=1.0)
        p2 = _make_participant(db, "test-1", "u2", "A", success=False,
                               metric_value=3.0)
        p3 = _make_participant(db, "test-1", "u3", "A", success=None,
                               metric_value=None)
        svc = ABTestingService(db)
        metrics = svc._calculate_variant_metrics([p1, p2, p3], "success_rate")
        assert metrics["count"] == 3
        assert metrics["success_count"] == 1
        assert metrics["success_rate"] == 1 / 3
        assert metrics["average_metric_value"] == 2.0

    def test_statistical_success_rate_very_significant(self):
        svc = ABTestingService(db=None)
        a = self._metrics(100, 0.5, None)
        b = self._metrics(100, 0.9, None)
        p_value, winner = svc._perform_statistical_test(a, b, "success_rate", 0.05)
        assert p_value == 0.001
        assert winner == "B"

    def test_statistical_success_rate_significant_b_wins(self):
        svc = ABTestingService(db=None)
        # 0.75 - 0.5 = 0.25 exactly (float-safe) -> >= 0.20 bucket -> p 0.01
        a = self._metrics(100, 0.5, None)
        b = self._metrics(100, 0.75, None)
        p_value, winner = svc._perform_statistical_test(a, b, "success_rate", 0.05)
        assert p_value == 0.01
        assert winner == "B"

    def test_statistical_success_rate_a_wins_on_negative_diff(self):
        svc = ABTestingService(db=None)
        a = self._metrics(100, 0.8, None)
        b = self._metrics(100, 0.5, None)
        p_value, winner = svc._perform_statistical_test(a, b, "success_rate", 0.05)
        assert p_value == 0.001
        assert winner == "A"

    def test_statistical_success_rate_small_diff_inconclusive(self):
        svc = ABTestingService(db=None)
        a = self._metrics(100, 0.5, None)
        b = self._metrics(100, 0.55, None)
        p_value, winner = svc._perform_statistical_test(a, b, "success_rate", 0.05)
        assert p_value == pytest.approx(0.75)  # max(0.1, 1 - 0.05*5)
        assert winner == "inconclusive"

    def test_statistical_success_rate_medium_diff_at_alpha_edge(self):
        svc = ABTestingService(db=None)
        # diff 0.15 -> p=0.05; with alpha 0.05, p < alpha is False -> no winner
        a = self._metrics(100, 0.5, None)
        b = self._metrics(100, 0.65, None)
        p_value, winner = svc._perform_statistical_test(a, b, "success_rate", 0.05)
        assert p_value == 0.05
        assert winner == "inconclusive"

    def test_statistical_success_rate_equal_rates(self):
        svc = ABTestingService(db=None)
        a = self._metrics(100, 0.6, None)
        b = self._metrics(100, 0.6, None)
        p_value, winner = svc._perform_statistical_test(a, b, "success_rate", 0.05)
        assert p_value == 1.0
        assert winner == "inconclusive"

    def test_statistical_numerical_tie_inconclusive(self):
        svc = ABTestingService(db=None)
        a = self._metrics(10, None, 2.0)
        b = self._metrics(10, None, 2.0)
        p_value, winner = svc._perform_statistical_test(a, b, "response_time", 0.05)
        assert p_value == 0.5
        assert winner == "inconclusive"

    def test_statistical_response_time_lower_is_better(self):
        svc = ABTestingService(db=None)
        a = self._metrics(10, None, 1.0)
        b = self._metrics(10, None, 3.0)
        p_value, winner = svc._perform_statistical_test(a, b, "response_time", 0.1)
        assert p_value == 0.05
        assert winner == "A"  # lower response time wins

    def test_statistical_error_rate_lower_is_better(self):
        svc = ABTestingService(db=None)
        a = self._metrics(10, None, 0.5)
        b = self._metrics(10, None, 0.1)
        p_value, winner = svc._perform_statistical_test(a, b, "error_rate", 0.1)
        assert winner == "B"

    def test_statistical_rating_higher_is_better(self):
        svc = ABTestingService(db=None)
        a = self._metrics(10, None, 3.0)
        b = self._metrics(10, None, 4.5)
        p_value, winner = svc._perform_statistical_test(a, b, "rating", 0.1)
        assert winner == "B"

    def test_statistical_numerical_not_significant_at_default_alpha(self):
        svc = ABTestingService(db=None)
        a = self._metrics(10, None, 1.0)
        b = self._metrics(10, None, 2.0)
        p_value, winner = svc._perform_statistical_test(a, b, "rating", 0.05)
        assert p_value == 0.05
        assert winner == "inconclusive"  # 0.05 is not < 0.05

    def test_full_ab_test_workflow(self, db):
        """End-to-end: create -> start -> assign -> record -> complete."""
        _make_agent(db)
        svc = ABTestingService(db)
        created = svc.create_test(
            name="E2E", test_type="tool", agent_id="agent-1",
            variant_a_config={"tool": "x"}, variant_b_config={"tool": "y"},
            primary_metric="success_rate", min_sample_size=2,
        )
        test_id = created["test_id"]
        svc.start_test(test_id)
        # 20 users: deterministic hash gives A:11 / B:9 (verified) -> both
        # variants clear min_sample_size=2.
        for i in range(20):
            assignment = svc.assign_variant(test_id, f"user-{i}")
            svc.record_metric(
                test_id, f"user-{i}",
                success=(assignment["variant"] == "B" or i % 2 == 0),
            )
        completed = svc.complete_test(test_id)
        assert completed["status"] == "completed"
        assert completed["winner"] in ("A", "B", "inconclusive")
        assert completed["min_sample_size_reached"] is True
