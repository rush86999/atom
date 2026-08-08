"""
Coverage + bug-hunt tests for ``core/ab_testing_service.py``.

Tests cover test creation, lifecycle (start/complete), deterministic variant
assignment, metric recording, results aggregation, statistical analysis, and
all validation/error paths. The DB layer is mocked so no real DB is needed.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from core.ab_testing_service import ABTestingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svc(db=None):
    """Build a service backed by a MagicMock DB (or a provided one)."""
    return ABTestingService(db or MagicMock())


def _make_test(
    test_id="t1", name="T", status="running", traffic_percentage=0.5,
    primary_metric="success_rate", min_sample_size=2,
    variant_a_name="Control", variant_b_name="Treatment",
    variant_a_config=None, variant_b_config=None,
    secondary_metrics=None, confidence_level=0.95,
    statistical_significance_threshold=0.05,
    variant_a_metrics=None, variant_b_metrics=None,
    statistical_significance=None, winner=None,
    started_at=None, completed_at=None, test_type="prompt",
    agent_id="agent1",
):
    t = MagicMock()
    t.id = test_id
    t.name = name
    t.status = status
    t.test_type = test_type
    t.agent_id = agent_id
    t.traffic_percentage = traffic_percentage
    t.variant_a_name = variant_a_name
    t.variant_b_name = variant_b_name
    t.variant_a_config = variant_a_config or {"a": 1}
    t.variant_b_config = variant_b_config or {"b": 2}
    t.primary_metric = primary_metric
    t.secondary_metrics = secondary_metrics or []
    t.min_sample_size = min_sample_size
    t.confidence_level = confidence_level
    t.statistical_significance_threshold = statistical_significance_threshold
    t.variant_a_metrics = variant_a_metrics
    t.variant_b_metrics = variant_b_metrics
    t.statistical_significance = statistical_significance
    t.winner = winner
    t.started_at = started_at
    t.completed_at = completed_at
    return t


def _make_participant(variant="A", success=None, metric_value=None):
    p = MagicMock()
    p.assigned_variant = variant
    p.success = success
    p.metric_value = metric_value
    return p


# ---------------------------------------------------------------------------
# create_test
# ---------------------------------------------------------------------------

class TestCreateTest:
    def test_agent_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        s = _svc(db)
        result = s.create_test(
            name="n", test_type="prompt", agent_id="ghost",
            variant_a_config={}, variant_b_config={}, primary_metric="success_rate",
        )
        assert "error" in result
        assert "ghost" in result["error"]

    def test_invalid_test_type(self):
        db = MagicMock()
        agent = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        s = _svc(db)
        result = s.create_test(
            name="n", test_type="bogus", agent_id="a1",
            variant_a_config={}, variant_b_config={}, primary_metric="success_rate",
        )
        assert "error" in result
        assert "Invalid test_type" in result["error"]

    def test_traffic_percentage_out_of_range(self):
        db = MagicMock()
        agent = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        s = _svc(db)
        for bad in (-0.1, 1.5):
            result = s.create_test(
                name="n", test_type="prompt", agent_id="a1",
                variant_a_config={}, variant_b_config={},
                primary_metric="success_rate", traffic_percentage=bad,
            )
            assert "error" in result
            assert "traffic_percentage" in result["error"]

    def test_create_success_persists_and_returns_payload(self):
        db = MagicMock()
        agent = MagicMock()
        # First query (AgentRegistry lookup) returns agent; later queries unused.
        db.query.return_value.filter.return_value.first.return_value = agent
        s = _svc(db)

        with patch("core.ab_testing_service.uuid") as uuid_mod:
            uuid_mod.uuid4.return_value = "uuid-fixed"
            result = s.create_test(
                name="MyTest", test_type="strategy", agent_id="a1",
                variant_a_config={"x": 1}, variant_b_config={"y": 2},
                primary_metric="response_time", secondary_metrics=["rating"],
                description="desc", traffic_percentage=0.3, min_sample_size=50,
                confidence_level=0.99,
            )
        assert result["test_id"]  # uuid str
        assert result["name"] == "MyTest"
        assert result["status"] == "draft"
        assert result["test_type"] == "strategy"
        assert result["primary_metric"] == "response_time"
        assert result["traffic_percentage"] == 0.3
        assert result["variant_a"]["config"] == {"x": 1}
        assert result["variant_b"]["config"] == {"y": 2}
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_create_secondary_metrics_defaults_to_empty_list(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        s = _svc(db)
        result = s.create_test(
            name="n", test_type="prompt", agent_id="a1",
            variant_a_config={}, variant_b_config={}, primary_metric="success_rate",
        )
        assert result["test_id"]  # created

    def test_boundary_traffic_percentages_accepted(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        s = _svc(db)
        for ok in (0.0, 1.0):
            result = s.create_test(
                name="n", test_type="prompt", agent_id="a1",
                variant_a_config={}, variant_b_config={},
                primary_metric="success_rate", traffic_percentage=ok,
            )
            assert "error" not in result


# ---------------------------------------------------------------------------
# start_test / complete_test
# ---------------------------------------------------------------------------

class TestStartTest:
    def test_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        s = _svc(db)
        result = s.start_test("ghost")
        assert "error" in result

    def test_wrong_status(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _make_test(status="completed")
        s = _svc(db)
        result = s.start_test("t1")
        assert "error" in result
        assert "draft" in result["error"]

    def test_start_success(self):
        t = _make_test(status="draft")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = t
        s = _svc(db)
        result = s.start_test("t1")
        assert result["status"] == "running"
        assert t.status == "running"
        assert t.started_at is not None
        db.commit.assert_called_once()


class TestCompleteTest:
    def test_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        s = _svc(db)
        assert "error" in s.complete_test("ghost")

    def test_wrong_status(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _make_test(status="draft")
        s = _svc(db)
        result = s.complete_test("t1")
        assert "error" in result
        assert "running" in result["error"]

    def test_complete_success_stores_results(self):
        t = _make_test(status="running")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = t
        s = _svc(db)
        results = {
            "variant_a_metrics": {"count": 2, "success_rate": 0.5},
            "variant_b_metrics": {"count": 2, "success_rate": 0.9},
            "p_value": 0.01, "winner": "B",
            "min_sample_size_reached": True,
        }
        with patch.object(ABTestingService, "_calculate_test_results", return_value=results):
            out = s.complete_test("t1")
        assert out["status"] == "completed"
        assert out["winner"] == "B"
        assert t.status == "completed"
        assert t.variant_a_metrics == results["variant_a_metrics"]
        assert t.statistical_significance == 0.01
        assert t.winner == "B"
        assert t.completed_at is not None

    def test_complete_with_null_p_value_logs_without_crash(self):
        """complete_test must not crash when statistical_significance is None."""
        t = _make_test(status="running")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = t
        s = _svc(db)
        results = {
            "variant_a_metrics": {"count": 0},
            "variant_b_metrics": {"count": 0},
            "p_value": None, "winner": "inconclusive",
            "min_sample_size_reached": False,
        }
        with patch.object(ABTestingService, "_calculate_test_results", return_value=results):
            out = s.complete_test("t1")
        # Must not raise; p_value None is stored as-is.
        assert out["winner"] == "inconclusive"
        assert t.statistical_significance is None


# ---------------------------------------------------------------------------
# assign_variant
# ---------------------------------------------------------------------------

class TestAssignVariant:
    def test_test_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        s = _svc(db)
        assert "error" in s.assign_variant("ghost", "u1")

    def test_test_not_running(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _make_test(status="draft")
        s = _svc(db)
        result = s.assign_variant("t1", "u1")
        assert "error" in result
        assert "running" in result["error"]

    def test_existing_assignment_returned(self):
        t = _make_test(status="running")
        existing = MagicMock()
        existing.assigned_variant = "B"
        db = MagicMock()
        # First call: test lookup. Second call: existing participant lookup.
        db.query.return_value.filter.return_value.first.side_effect = [t, existing]
        s = _svc(db)
        result = s.assign_variant("t1", "u1")
        assert result["existing_assignment"] is True
        assert result["variant"] == "B"
        assert result["variant_name"] == "Treatment"
        assert result["config"] == t.variant_b_config
        # Must NOT add a new participant.
        db.add.assert_not_called()

    def test_new_assignment_is_deterministic(self):
        """Same (test_id, user_id) must always produce the same variant."""
        t = _make_test(status="running", traffic_percentage=0.5)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [t, None]  # no existing
        s = _svc(db)
        result = s.assign_variant("t1", "user-42")
        # Recompute expected variant from the same hash formula.
        h = int(hashlib.sha256(f"t1:user-42".encode()).hexdigest(), 16)
        fraction = (h % 10000) / 10000.0
        expected = "B" if fraction < t.traffic_percentage else "A"
        assert result["variant"] == expected
        assert result["existing_assignment"] is False
        db.add.assert_called_once()
        assert result["config"] == (t.variant_a_config if expected == "A" else t.variant_b_config)

    def test_traffic_percentage_all_b(self):
        """With traffic_percentage=1.0 every user lands in variant B."""
        t = _make_test(status="running", traffic_percentage=1.0)
        s = _svc()
        for uid in ["u1", "u2", "u3", "u4", "u5"]:
            db = MagicMock()
            db.query.return_value.filter.return_value.first.side_effect = [t, None]
            s.db = db
            result = s.assign_variant("t1", uid)
            assert result["variant"] == "B", f"uid={uid} got {result['variant']}"

    def test_traffic_percentage_zero_all_a(self):
        """With traffic_percentage=0.0 every user lands in variant A."""
        t = _make_test(status="running", traffic_percentage=0.0)
        s = _svc()
        for uid in ["u1", "u2", "u3"]:
            db = MagicMock()
            db.query.return_value.filter.return_value.first.side_effect = [t, None]
            s.db = db
            result = s.assign_variant("t1", uid)
            assert result["variant"] == "A", f"uid={uid} got {result['variant']}"

    def test_assignment_distribution_is_roughly_balanced(self):
        """Hash-based assignment over many users must hit both variants near 50/50."""
        t = _make_test(status="running", traffic_percentage=0.5)
        counts = {"A": 0, "B": 0}
        for i in range(2000):
            db = MagicMock()
            db.query.return_value.filter.return_value.first.side_effect = [t, None]
            s = _svc(db)
            r = s.assign_variant("t1", f"user-{i}")
            counts[r["variant"]] += 1
        # Both variants must get a meaningful share (no degenerate all-A or all-B).
        assert counts["A"] > 500, counts
        assert counts["B"] > 500, counts

    def test_session_id_persisted_on_new_assignment(self):
        t = _make_test(status="running")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [t, None]
        s = _svc(db)
        s.assign_variant("t1", "u1", session_id="sess-9")
        added = db.add.call_args[0][0]
        assert added.session_id == "sess-9"


# ---------------------------------------------------------------------------
# record_metric
# ---------------------------------------------------------------------------

class TestRecordMetric:
    def test_participant_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        s = _svc(db)
        result = s.record_metric("t1", "ghost")
        assert "error" in result

    def test_record_success_and_value(self):
        p = _make_participant(variant="A")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = p
        s = _svc(db)
        result = s.record_metric(
            "t1", "u1", success=True, metric_value=42.5, metadata={"k": "v"},
        )
        assert result["variant"] == "A"
        assert result["success"] is True
        assert result["metric_value"] == 42.5
        assert p.success is True
        assert p.metric_value == 42.5
        assert p.meta_data == {"k": "v"}
        assert p.recorded_at is not None
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_test_results / list_tests
# ---------------------------------------------------------------------------

class TestGetTestResults:
    def test_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        s = _svc(db)
        assert "error" in s.get_test_results("ghost")

    def test_returns_counts_per_variant(self):
        t = _make_test(started_at=datetime(2026, 1, 1), completed_at=datetime(2026, 1, 2))
        db = MagicMock()
        # The service calls db.query() three times:
        #   1. ABTest lookup   -> .filter().first() == t
        #   2. count variant A -> .filter().scalar() == 3
        #   3. count variant B -> .filter().scalar() == 7
        # Each db.query() must return a fresh chain. Configure via side_effect.
        test_q = MagicMock()
        test_q.filter.return_value.first.return_value = t
        count_a_q = MagicMock()
        count_a_q.filter.return_value.scalar.return_value = 3
        count_b_q = MagicMock()
        count_b_q.filter.return_value.scalar.return_value = 7
        db.query.side_effect = [test_q, count_a_q, count_b_q]
        s = _svc(db)
        result = s.get_test_results("t1")
        assert result["variant_a"]["participant_count"] == 3
        assert result["variant_b"]["participant_count"] == 7
        assert result["started_at"] == datetime(2026, 1, 1).isoformat()
        assert result["completed_at"] == datetime(2026, 1, 2).isoformat()

    def test_null_timestamps_serialized_as_none(self):
        t = _make_test(started_at=None, completed_at=None)
        db = MagicMock()
        test_q = MagicMock()
        test_q.filter.return_value.first.return_value = t
        count_a_q = MagicMock()
        count_a_q.filter.return_value.scalar.return_value = 0
        count_b_q = MagicMock()
        count_b_q.filter.return_value.scalar.return_value = 0
        db.query.side_effect = [test_q, count_a_q, count_b_q]
        s = _svc(db)
        result = s.get_test_results("t1")
        assert result["started_at"] is None
        assert result["completed_at"] is None


class TestListTests:
    def test_no_filters_returns_all(self):
        t1 = _make_test(test_id="t1")
        t2 = _make_test(test_id="t2")
        q = MagicMock()
        q.order_by.return_value.limit.return_value.all.return_value = [t1, t2]
        db = MagicMock()
        db.query.return_value = q
        s = _svc(db)
        result = s.list_tests()
        assert result["total"] == 2
        assert [x["test_id"] for x in result["tests"]] == ["t1", "t2"]

    def test_filters_applied(self):
        t1 = _make_test()
        q = MagicMock()
        q.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [t1]
        db = MagicMock()
        db.query.return_value = q
        s = _svc(db)
        s.list_tests(agent_id="a1", status="running", limit=5)
        q.filter.assert_called()  # agent filter
        q.filter.return_value.filter.assert_called()  # status filter


# ---------------------------------------------------------------------------
# _calculate_variant_metrics
# ---------------------------------------------------------------------------

class TestCalculateVariantMetrics:
    def test_empty_returns_none_metrics(self):
        s = _svc()
        out = s._calculate_variant_metrics([], "success_rate")
        assert out == {"count": 0, "success_rate": None, "average_metric_value": None}

    def test_success_rate_and_average(self):
        s = _svc()
        ps = [
            _make_participant(success=True, metric_value=10.0),
            _make_participant(success=False, metric_value=20.0),
            _make_participant(success=True, metric_value=None),  # metric ignored
            _make_participant(success=None, metric_value=30.0),  # not a success
        ]
        out = s._calculate_variant_metrics(ps, "success_rate")
        assert out["count"] == 4
        assert out["success_count"] == 2
        assert out["success_rate"] == 0.5
        # average over non-None metric_values only
        assert out["average_metric_value"] == 20.0  # (10+20+30)/3

    def test_all_none_metric_values(self):
        s = _svc()
        ps = [_make_participant(success=True, metric_value=None),
              _make_participant(success=False, metric_value=None)]
        out = s._calculate_variant_metrics(ps, "response_time")
        assert out["average_metric_value"] is None
        assert out["success_rate"] == 0.5


# ---------------------------------------------------------------------------
# _calculate_test_results
# ---------------------------------------------------------------------------

class TestCalculateTestResults:
    def test_below_min_sample_size_is_inconclusive(self):
        t = _make_test(min_sample_size=100, primary_metric="success_rate")
        db = MagicMock()
        a_q = MagicMock()
        a_q.all.return_value = [_make_participant("A", True)]
        b_q = MagicMock()
        b_q.all.return_value = [_make_participant("B", True)]
        db.query.return_value.filter.return_value = a_q  # both A and B reuse
        db.query.return_value.filter.side_effect = None
        db.query.return_value.filter.return_value.all.side_effect = [[_make_participant("A", True)],
                                                                     [_make_participant("B", True)]]
        s = _svc(db)
        out = s._calculate_test_results(t)
        assert out["winner"] == "inconclusive"
        assert out["p_value"] is None
        assert out["min_sample_size_reached"] is False

    def test_reaches_sample_size_and_calls_stat_test(self):
        t = _make_test(min_sample_size=2, primary_metric="success_rate")
        db = MagicMock()
        db.query.return_value.filter.return_value.all.side_effect = [
            [_make_participant("A", True), _make_participant("A", True)],
            [_make_participant("B", True), _make_participant("B", True)],
        ]
        s = _svc(db)
        with patch.object(ABTestingService, "_perform_statistical_test",
                          return_value=(0.01, "B")) as stat:
            out = s._calculate_test_results(t)
        assert out["winner"] == "B"
        assert out["p_value"] == 0.01
        assert out["min_sample_size_reached"] is True
        stat.assert_called_once()


# ---------------------------------------------------------------------------
# _perform_statistical_test (success_rate branch)
# ---------------------------------------------------------------------------

class TestStatisticalTestSuccessRate:
    def _svc(self):
        return _svc()

    def test_b_significantly_higher_wins(self):
        # rate_b=0.9, rate_a=0.5 -> diff=0.4 -> p=0.001 -> B wins
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": 0.5}, {"success_rate": 0.9}, "success_rate", 0.05
        )
        assert p == 0.001
        assert w == "B"

    def test_a_significantly_higher_wins(self):
        # rate_a=0.9, rate_b=0.5 -> diff=-0.4 -> p=0.001 -> A wins
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": 0.9}, {"success_rate": 0.5}, "success_rate", 0.05
        )
        assert p == 0.001
        assert w == "A"

    def test_small_difference_inconclusive(self):
        # diff=0.02 -> p=max(0.1, 1-0.1)=0.9 -> not significant -> inconclusive
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": 0.50}, {"success_rate": 0.52}, "success_rate", 0.05
        )
        assert p >= 0.05
        assert w == "inconclusive"

    def test_medium_diff_boundary_0_10(self):
        # abs_diff exactly 0.10 (0.20 - 0.10 is float-exact) -> p=0.05 ->
        # NOT strictly < alpha(0.05) -> inconclusive.
        # NOTE: values like 0.40/0.50 suffer float-precision in subtraction
        # (0.50-0.40 == 0.0999...), so the >= 0.10 branch is skipped — a known
        # fragility of the magnitude-bucket p-value heuristic. We use the
        # float-clean pair here to assert the intended boundary behavior.
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": 0.10}, {"success_rate": 0.20}, "success_rate", 0.05
        )
        assert p == 0.05
        assert w == "inconclusive"

    def test_strict_alpha_blocks_marginal_winner(self):
        # abs_diff=0.10 -> p=0.05; alpha=0.01 -> not significant -> inconclusive
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": 0.40}, {"success_rate": 0.50}, "success_rate", 0.01
        )
        assert w == "inconclusive"

    def test_large_diff_0_20_bucket_p_value_0_01(self):
        # 0.4 - 0.2 == 0.2 (float-exact) -> p=0.01; alpha=0.05 -> significant -> B.
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": 0.20}, {"success_rate": 0.40}, "success_rate", 0.05
        )
        assert p == 0.01
        assert w == "B"

    def test_large_diff_0_20_bucket_a_wins(self):
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": 0.40}, {"success_rate": 0.20}, "success_rate", 0.05
        )
        assert p == 0.01
        assert w == "A"


# ---------------------------------------------------------------------------
# _perform_statistical_test (numerical branch) + BUG
# ---------------------------------------------------------------------------

class TestStatisticalTestNumerical:
    def _svc(self):
        return _svc()

    def test_response_time_lower_is_better_b_wins(self):
        # B faster (lower); p_value=0.05, alpha=0.10 -> significant -> B wins.
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 120.0},
            {"success_rate": None, "average_metric_value": 100.0},
            "response_time", 0.10,
        )
        assert w == "B"

    def test_response_time_lower_is_better_a_wins(self):
        # A faster (lower); p_value=0.05, alpha=0.10 -> significant -> A wins.
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 100.0},
            {"success_rate": None, "average_metric_value": 120.0},
            "response_time", 0.10,
        )
        assert w == "A"

    def test_error_rate_lower_is_better(self):
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 0.02},
            {"success_rate": None, "average_metric_value": 0.01},
            "error_rate", 0.10,
        )
        assert w == "B"

    def test_rating_higher_is_better_b_wins(self):
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 3.0},
            {"success_rate": None, "average_metric_value": 4.5},
            "rating", 0.10,
        )
        assert w == "B"

    def test_rating_higher_is_better_a_wins(self):
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 4.5},
            {"success_rate": None, "average_metric_value": 3.0},
            "rating", 0.10,
        )
        assert w == "A"

    def test_significant_diff_at_alpha_0_05_is_inconclusive(self):
        """p_value=0.05 is not strictly < alpha=0.05, so even a real difference
        must be inconclusive at the strict threshold."""
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 100.0},
            {"success_rate": None, "average_metric_value": 80.0},
            "response_time", 0.05,
        )
        assert p == 0.05
        assert w == "inconclusive"

    def test_missing_average_metric_value_defaults_to_zero(self):
        # No average_metric_value key -> defaults to 0; both equal -> see tied test.
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None},
            {"success_rate": None},
            "rating", 0.05,
        )
        # tied (both 0) -> see tied test below; after fix this is inconclusive.
        assert w == "inconclusive"

    def test_numerical_significant_diff_declares_winner(self):
        # rating, B much higher -> avg_a != avg_b -> p=0.05, alpha=0.05 -> not < alpha.
        # With the fix, we need p < alpha, so use alpha=0.10 to confirm a winner path.
        p, w = self._svc()._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 2.0},
            {"success_rate": None, "average_metric_value": 5.0},
            "rating", 0.10,
        )
        assert p == 0.05
        assert w == "B"

    def test_bug_tied_response_time_should_be_inconclusive(self):
        """BUG: tied numerical metrics (no real difference) are declared a winner
        instead of 'inconclusive'. When avg_a == avg_b, p_value=0.5 (clearly not
        significant), yet the numerical branch returns winner='B' for
        response_time and 'A' for higher-is-better metrics. The success_rate
        branch correctly guards with `p_value < alpha`; the numerical branch
        must do the same."""
        s = self._svc()
        # Tied response_time: identical averages -> no difference -> inconclusive.
        p, w = s._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 100.0},
            {"success_rate": None, "average_metric_value": 100.0},
            "response_time", 0.05,
        )
        assert p == 0.5, "tied metrics should yield a non-significant p-value"
        assert w == "inconclusive", (
            "tied metrics (p_value=0.5 >= alpha) must be inconclusive, "
            f"got winner={w!r}"
        )

    def test_bug_tied_rating_should_be_inconclusive(self):
        """BUG: same root cause for higher-is-better numerical metrics — when
        avg_a == avg_b the code returns winner='A' instead of 'inconclusive'."""
        s = self._svc()
        p, w = s._perform_statistical_test(
            {"success_rate": None, "average_metric_value": 4.0},
            {"success_rate": None, "average_metric_value": 4.0},
            "rating", 0.05,
        )
        assert p == 0.5
        assert w == "inconclusive", f"expected inconclusive for tied metrics, got {w!r}"
