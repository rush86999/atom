# -*- coding: utf-8 -*-
"""
Coverage + bug-hunt tests for core/supervisor_learning_service.py.

The SupervisorLearningService orchestrates supervisor learning from feedback
(ratings, votes, intervention outcomes). The real ``SupervisorPerformance``
model in core/models.py does NOT carry the attributes this service reads/writes
(``confidence_score``, ``competence_level``, ``performance_trend``,
``learning_rate``, ``total_ratings``, ``total_interventions``, etc.), so the
service can only be exercised through mocks of the ORM objects. We mock the DB
session and the performance/rating/outcome objects to drive every branch.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.supervisor_learning_service import SupervisorLearningService
import core.supervisor_learning_service as sls_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_performance(
    supervisor_id: str = "sup-1",
    confidence_score: float = 0.5,
    competence_level: str = "novice",
    performance_trend: str = "stable",
    learning_rate: float = 0.0,
    total_ratings: int = 0,
    average_rating: float | None = None,
    total_sessions_supervised: int = 0,
    total_interventions: int = 0,
    successful_interventions: int | None = None,
    failed_interventions: int | None = None,
    last_updated=None,
):
    """Build a mock SupervisorPerformance-like object with all attrs the
    service touches. Uses a real MagicMock so attribute writes persist."""
    p = MagicMock()
    p.supervisor_id = supervisor_id
    p.confidence_score = confidence_score
    p.competence_level = competence_level
    p.performance_trend = performance_trend
    p.learning_rate = learning_rate
    p.total_ratings = total_ratings
    p.average_rating = average_rating
    p.total_sessions_supervised = total_sessions_supervised
    p.total_interventions = total_interventions
    p.successful_interventions = successful_interventions
    p.failed_interventions = failed_interventions
    p.last_updated = last_updated
    return p


def _make_rating(rating: int, created_at: datetime | None = None):
    r = MagicMock()
    r.rating = rating
    r.created_at = created_at or datetime.now()
    return r


def _make_outcome(outcome: str, assessed_at: datetime | None = None):
    o = MagicMock()
    o.outcome = outcome
    o.assessed_at = assessed_at or datetime.now()
    return o


def _service_with_existing(performance):
    """Build a service whose db returns ``performance`` for lookups."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = performance
    return SupervisorLearningService(db), db


# ---------------------------------------------------------------------------
# _get_or_create_performance
# ---------------------------------------------------------------------------

class TestGetOrCreatePerformance:
    async def test_returns_existing_performance(self):
        perf = _make_performance()
        svc, db = _service_with_existing(perf)
        result = await svc._get_or_create_performance("sup-1")
        assert result is perf
        db.add.assert_not_called()
        db.commit.assert_not_called()

    async def test_creates_performance_when_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = SupervisorLearningService(db)
        created = []
        def _ctor(**kwargs):
            perf = _make_performance(**kwargs)
            created.append(perf)
            return perf
        with patch.object(sls_module, "SupervisorPerformance", side_effect=_ctor):
            result = await svc._get_or_create_performance("sup-2")
        assert result.supervisor_id == "sup-2"
        assert result.confidence_score == 0.5
        assert result.competence_level == "novice"
        db.add.assert_called_once()
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# process_feedback_for_learning — rating path
# ---------------------------------------------------------------------------

class TestProcessFeedbackRating:
    async def test_rating_5_boosts_confidence(self):
        perf = _make_performance(confidence_score=0.5, total_ratings=0)
        svc, db = _service_with_existing(perf)
        # _update_learning_metrics reads recent ratings
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await svc.process_feedback_for_learning("sup-1", "rating", {"rating": 5})

        # adjustment 0.05, alpha 0.2 -> +0.01 -> 0.51
        assert perf.confidence_score == pytest.approx(0.51)
        assert perf.total_ratings == 1
        assert result["feedback_type"] == "rating"
        assert result["confidence_change"] == pytest.approx(0.01)
        db.commit.assert_called()

    async def test_rating_1_lowers_confidence(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning("sup-1", "rating", {"rating": 1})
        # adjustment -0.05, alpha 0.2 -> -0.01 -> 0.49
        assert perf.confidence_score == pytest.approx(0.49)

    async def test_rating_3_neutral(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning("sup-1", "rating", {"rating": 3})
        assert perf.confidence_score == pytest.approx(0.5)

    async def test_rating_unknown_value_defaults_neutral(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        # rating not in RATING_BOOST -> adjustment 0.0
        await svc.process_feedback_for_learning("sup-1", "rating", {"rating": 99})
        assert perf.confidence_score == pytest.approx(0.5)
        assert perf.total_ratings == 1

    async def test_rating_clamped_to_max(self):
        perf = _make_performance(confidence_score=0.94)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning("sup-1", "rating", {"rating": 5})
        # 0.94 + 0.01 = 0.95 -> clamped to 0.95
        assert perf.confidence_score == pytest.approx(0.95)

    async def test_rating_clamped_to_min(self):
        perf = _make_performance(confidence_score=0.11)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning("sup-1", "rating", {"rating": 1})
        # 0.11 - 0.01 = 0.10 -> clamped to 0.10
        assert perf.confidence_score == pytest.approx(0.10)

    async def test_rating_missing_defaults_to_3(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        # No "rating" key -> defaults to 3 -> neutral
        await svc.process_feedback_for_learning("sup-1", "rating", {})
        assert perf.confidence_score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# process_feedback_for_learning — vote path
# ---------------------------------------------------------------------------

class TestProcessFeedbackVote:
    async def test_vote_up_small_boost(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning("sup-1", "vote", {"vote_type": "up"})
        # 0.01 * 0.1 = +0.001 -> 0.501
        assert perf.confidence_score == pytest.approx(0.501)

    async def test_vote_down_small_drop(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning("sup-1", "vote", {"vote_type": "down"})
        # -0.02 * 0.1 = -0.002 -> 0.498
        assert perf.confidence_score == pytest.approx(0.498)

    async def test_vote_unknown_type_treated_as_down(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        # anything not "up" -> else branch (down)
        await svc.process_feedback_for_learning("sup-1", "vote", {"vote_type": "sideways"})
        assert perf.confidence_score == pytest.approx(0.498)


# ---------------------------------------------------------------------------
# process_feedback_for_learning — intervention outcome path
# ---------------------------------------------------------------------------

class TestProcessFeedbackIntervention:
    async def test_success_and_effective(self):
        perf = _make_performance(confidence_score=0.5, total_interventions=0,
                                  successful_interventions=0, failed_interventions=0)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning(
            "sup-1", "intervention_outcome",
            {"outcome": "success", "was_effective": True},
        )
        # 0.03 * 0.15 = +0.0045 -> 0.5045
        assert perf.confidence_score == pytest.approx(0.5045)
        assert perf.total_interventions == 1
        assert perf.successful_interventions == 1
        assert perf.failed_interventions == 0

    async def test_failure_penalizes(self):
        perf = _make_performance(confidence_score=0.5, total_interventions=0,
                                  successful_interventions=0, failed_interventions=0)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning(
            "sup-1", "intervention_outcome",
            {"outcome": "failure", "was_effective": False},
        )
        # -0.05 * 0.15 = -0.0075 -> 0.4925
        assert perf.confidence_score == pytest.approx(0.4925)
        assert perf.failed_interventions == 1

    async def test_not_effective_counts_as_failure(self):
        perf = _make_performance(confidence_score=0.5, total_interventions=0,
                                  successful_interventions=0, failed_interventions=0)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        # outcome success but NOT effective -> elif branch (not was_effective) -> -0.05, failed count
        await svc.process_feedback_for_learning(
            "sup-1", "intervention_outcome",
            {"outcome": "success", "was_effective": False},
        )
        assert perf.confidence_score == pytest.approx(0.4925)
        assert perf.failed_interventions == 1
        assert perf.successful_interventions == 0

    async def test_partial_and_effective_no_change(self):
        perf = _make_performance(confidence_score=0.5, total_interventions=0,
                                  successful_interventions=0, failed_interventions=0)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning(
            "sup-1", "intervention_outcome",
            {"outcome": "partial", "was_effective": True},
        )
        assert perf.confidence_score == pytest.approx(0.5)
        assert perf.successful_interventions == 1

    async def test_outcome_defaults_partial_effective(self):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        await svc.process_feedback_for_learning("sup-1", "intervention_outcome", {})
        # default outcome "partial", default was_effective True -> no change, successful +1
        assert perf.confidence_score == pytest.approx(0.5)
        assert perf.successful_interventions == 1


# ---------------------------------------------------------------------------
# process_feedback_for_learning — unknown type
# ---------------------------------------------------------------------------

class TestProcessFeedbackUnknown:
    async def test_unknown_feedback_type_logs_warning(self, caplog):
        perf = _make_performance(confidence_score=0.5)
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        import logging
        with caplog.at_level(logging.WARNING):
            result = await svc.process_feedback_for_learning("sup-1", "mystery", {})
        assert "Unknown feedback type" in caplog.text
        assert result["feedback_type"] == "mystery"


# ---------------------------------------------------------------------------
# _update_learning_metrics
# ---------------------------------------------------------------------------

class TestUpdateLearningMetrics:
    async def test_fewer_than_10_ratings_stable(self):
        perf = _make_performance()
        svc, db = _service_with_existing(perf)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            _make_rating(4) for _ in range(5)
        ]
        await svc._update_learning_metrics(perf)
        assert perf.performance_trend == "stable"
        assert perf.learning_rate == 0.0

    async def test_improving_trend(self):
        perf = _make_performance()
        svc, db = _service_with_existing(perf)
        now = datetime.now()
        # ordered desc: newest first. first_half (older) = low ratings,
        # second_half (newer) = high ratings -> improving
        ratings = (
            [_make_rating(5, now - timedelta(days=i)) for i in range(10)]  # newer, high
            + [_make_rating(2, now - timedelta(days=20 + i)) for i in range(10)]  # older, low
        )
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = ratings
        await svc._update_learning_metrics(perf)
        assert perf.performance_trend == "improving"
        assert perf.learning_rate > 0

    async def test_declining_trend(self):
        perf = _make_performance()
        svc, db = _service_with_existing(perf)
        now = datetime.now()
        # newer low, older high -> declining
        ratings = (
            [_make_rating(1, now - timedelta(days=i)) for i in range(10)]  # newer, low
            + [_make_rating(5, now - timedelta(days=20 + i)) for i in range(10)]  # older, high
        )
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = ratings
        await svc._update_learning_metrics(perf)
        assert perf.performance_trend == "declining"
        assert perf.learning_rate < 0

    async def test_stable_trend_small_difference(self):
        perf = _make_performance()
        svc, db = _service_with_existing(perf)
        now = datetime.now()
        ratings = [_make_rating(4, now - timedelta(days=i)) for i in range(20)]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = ratings
        await svc._update_learning_metrics(perf)
        assert perf.performance_trend == "stable"
        assert perf.learning_rate == 0.0

    async def test_improving_learning_rate_capped(self):
        perf = _make_performance()
        svc, db = _service_with_existing(perf)
        now = datetime.now()
        # huge difference (5 vs 1) -> difference 4 -> min(4/2, 0.1) = 0.1
        ratings = (
            [_make_rating(5, now - timedelta(days=i)) for i in range(10)]
            + [_make_rating(1, now - timedelta(days=20 + i)) for i in range(10)]
        )
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = ratings
        await svc._update_learning_metrics(perf)
        assert perf.learning_rate == pytest.approx(0.1)

    async def test_declining_learning_rate_floored(self):
        perf = _make_performance()
        svc, db = _service_with_existing(perf)
        now = datetime.now()
        ratings = (
            [_make_rating(1, now - timedelta(days=i)) for i in range(10)]
            + [_make_rating(5, now - timedelta(days=20 + i)) for i in range(10)]
        )
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = ratings
        await svc._update_learning_metrics(perf)
        assert perf.learning_rate == pytest.approx(-0.1)


# ---------------------------------------------------------------------------
# update_competence_level
# ---------------------------------------------------------------------------

class TestUpdateCompetenceLevel:
    async def test_promotion_to_expert(self):
        perf = _make_performance(
            confidence_score=0.9, total_sessions_supervised=150,
            successful_interventions=90, failed_interventions=5,
            competence_level="advanced",
        )
        svc, db = _service_with_existing(perf)
        result = await svc.update_competence_level("sup-1")
        assert result["new_level"] == "expert"
        assert result["level_changed"] is True

    async def test_promotion_to_advanced(self):
        perf = _make_performance(
            confidence_score=0.75, total_sessions_supervised=60,
            successful_interventions=40, failed_interventions=10,
            competence_level="intermediate",
        )
        svc, db = _service_with_existing(perf)
        result = await svc.update_competence_level("sup-1")
        assert result["new_level"] == "advanced"
        assert result["level_changed"] is True

    async def test_promotion_to_intermediate(self):
        perf = _make_performance(
            confidence_score=0.55, total_sessions_supervised=25,
            successful_interventions=14, failed_interventions=6,
            competence_level="novice",
        )
        svc, db = _service_with_existing(perf)
        result = await svc.update_competence_level("sup-1")
        assert result["new_level"] == "intermediate"

    async def test_demotion_to_novice_low_confidence(self):
        perf = _make_performance(
            confidence_score=0.35, total_sessions_supervised=5,
            successful_interventions=5, failed_interventions=5,
            competence_level="intermediate",
        )
        svc, db = _service_with_existing(perf)
        result = await svc.update_competence_level("sup-1")
        assert result["new_level"] == "novice"

    async def test_demotion_to_novice_low_sessions(self):
        perf = _make_performance(
            confidence_score=0.6, total_sessions_supervised=5,
            successful_interventions=5, failed_interventions=0,
            competence_level="intermediate",
        )
        svc, db = _service_with_existing(perf)
        result = await svc.update_competence_level("sup-1")
        # sessions < 10 -> novice
        assert result["new_level"] == "novice"

    async def test_no_change_when_in_middle_band(self):
        perf = _make_performance(
            confidence_score=0.6, total_sessions_supervised=30,
            successful_interventions=15, failed_interventions=15,
            competence_level="intermediate",
        )
        svc, db = _service_with_existing(perf)
        result = await svc.update_competence_level("sup-1")
        # 0.6 conf, 30 sessions, 0.5 success -> not intermediate tier (needs 0.7 sr),
        # not novice tier (conf >= 0.4 and sessions >= 10) -> stays "intermediate"
        assert result["new_level"] == "intermediate"
        assert result["level_changed"] is False

    async def test_zero_interventions_defaults_0_5_success_rate(self):
        perf = _make_performance(
            confidence_score=0.55, total_sessions_supervised=25,
            successful_interventions=0, failed_interventions=0,
            competence_level="novice",
        )
        svc, db = _service_with_existing(perf)
        result = await svc.update_competence_level("sup-1")
        # success_rate defaults to 0.5 -> not enough for intermediate (needs 0.7)
        assert result["criteria"]["intervention_success_rate"] == 0.5


# ---------------------------------------------------------------------------
# get_top_performers
# ---------------------------------------------------------------------------

class TestGetTopPerformers:
    def _setups(self):
        p1 = _make_performance(supervisor_id="low", confidence_score=0.4,
                               average_rating=2.0, total_sessions_supervised=5)
        p2 = _make_performance(supervisor_id="high", confidence_score=0.9,
                               average_rating=5.0, total_sessions_supervised=200)
        return p1, p2

    async def test_sort_by_confidence_score(self):
        p1, p2 = self._setups()
        db = MagicMock()
        db.query.return_value.all.return_value = [p1, p2]
        svc = SupervisorLearningService(db)
        result = await svc.get_top_performers(metric="confidence_score")
        assert [r["supervisor_id"] for r in result] == ["high", "low"]

    async def test_sort_by_average_rating(self):
        p1, p2 = self._setups()
        db = MagicMock()
        db.query.return_value.all.return_value = [p1, p2]
        svc = SupervisorLearningService(db)
        result = await svc.get_top_performers(metric="average_rating")
        assert [r["supervisor_id"] for r in result] == ["high", "low"]

    async def test_sort_by_total_sessions(self):
        p1, p2 = self._setups()
        db = MagicMock()
        db.query.return_value.all.return_value = [p1, p2]
        svc = SupervisorLearningService(db)
        result = await svc.get_top_performers(metric="total_sessions")
        assert [r["supervisor_id"] for r in result] == ["high", "low"]

    async def test_limit_applied(self):
        p1, p2 = self._setups()
        db = MagicMock()
        db.query.return_value.all.return_value = [p1, p2]
        svc = SupervisorLearningService(db)
        result = await svc.get_top_performers(metric="confidence_score", limit=1)
        assert len(result) == 1
        assert result[0]["supervisor_id"] == "high"

    async def test_filter_by_competence_level(self):
        p1, p2 = self._setups()
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [p2]
        svc = SupervisorLearningService(db)
        with patch.object(sls_module, "SupervisorPerformance") as model_cls:
            model_cls.competence_level = "expert"
            result = await svc.get_top_performers(metric="confidence_score", competence_level="expert")
        db.query.return_value.filter.assert_called()
        assert all(r["supervisor_id"] == "high" for r in result)

    async def test_average_rating_none_handled(self):
        p1 = _make_performance(supervisor_id="none", confidence_score=0.5,
                               average_rating=None)
        db = MagicMock()
        db.query.return_value.all.return_value = [p1]
        svc = SupervisorLearningService(db)
        result = await svc.get_top_performers(metric="average_rating")
        assert result[0]["average_rating"] is None

    async def test_unknown_metric_returns_unsorted(self):
        """Documents current behavior: unknown metric -> no sorting."""
        p1, p2 = self._setups()
        db = MagicMock()
        db.query.return_value.all.return_value = [p1, p2]
        svc = SupervisorLearningService(db)
        result = await svc.get_top_performers(metric="bogus")
        assert [r["supervisor_id"] for r in result] == ["low", "high"]


# ---------------------------------------------------------------------------
# BUG: success_rate metric documented but not implemented -> unsorted
# ---------------------------------------------------------------------------

class TestGetTopPerformersSuccessRateBug:
    async def test_success_rate_metric_sorts_by_success_rate(self):
        """BUG: get_top_performers documents ``success_rate`` as a valid metric
        (docstring line 177) but provides no sort branch for it, so it falls
        into the ``else`` clause and returns performers in arbitrary DB order
        instead of ranked by intervention success rate.

        Setup: low performer (10% success) + high performer (90% success).
        Expected after fix: high ranked first. Before fix: unsorted (DB order).
        """
        low = _make_performance(supervisor_id="low", confidence_score=0.5,
                                successful_interventions=1, failed_interventions=9,
                                total_interventions=10)
        high = _make_performance(supervisor_id="high", confidence_score=0.5,
                                 successful_interventions=9, failed_interventions=1,
                                 total_interventions=10)
        db = MagicMock()
        # DB returns them in non-sorted order
        db.query.return_value.all.return_value = [low, high]
        svc = SupervisorLearningService(db)
        result = await svc.get_top_performers(metric="success_rate", limit=10)
        ranked = [r["supervisor_id"] for r in result]
        assert ranked == ["high", "low"], (
            f"success_rate metric must rank by success rate; got {ranked}"
        )


# ---------------------------------------------------------------------------
# calculate_learning_insights
# ---------------------------------------------------------------------------

class TestCalculateLearningInsights:
    async def test_no_performance_returns_empty(self):
        from core.models import SupervisorPerformance
        perf_chain = MagicMock()
        perf_chain.filter.return_value.first.return_value = None
        db = MagicMock()
        db.query.side_effect = lambda model: perf_chain
        svc = SupervisorLearningService(db)
        result = await svc.calculate_learning_insights("ghost")
        assert result["current_state"]["competence_level"] == "novice"
        assert result["strengths"] == []
        assert result["recent_feedback_summary"]["total_ratings"] == 0
        assert result["recent_feedback_summary"]["average_rating"] is None

    async def test_full_insights_with_data(self):
        perf = _make_performance(
            confidence_score=0.9, competence_level="expert",
            performance_trend="improving", learning_rate=0.05,
            total_sessions_supervised=200, average_rating=4.8,
        )
        ratings = [_make_rating(5), _make_rating(4), _make_rating(5)]
        outcomes = [_make_outcome("success"), _make_outcome("success"), _make_outcome("failure")]

        # db.query(model) is called 3 times with different models. Route each
        # call to a distinct chain so first()/all() return the right data.
        perf_chain = MagicMock()
        perf_chain.filter.return_value.first.return_value = perf
        rating_chain = MagicMock()
        rating_chain.filter.return_value.all.return_value = ratings
        outcome_chain = MagicMock()
        outcome_chain.filter.return_value.all.return_value = outcomes

        from core.models import SupervisorPerformance, SupervisorRating, InterventionOutcome
        routing = {
            SupervisorPerformance: perf_chain,
            SupervisorRating: rating_chain,
            InterventionOutcome: outcome_chain,
        }
        db = MagicMock()
        db.query.side_effect = lambda model: routing[model]
        svc = SupervisorLearningService(db)
        result = await svc.calculate_learning_insights("sup-1", time_range_days=30)

        assert result["current_state"]["competence_level"] == "expert"
        assert result["recent_feedback_summary"]["total_ratings"] == 3
        assert result["recent_feedback_summary"]["average_rating"] == pytest.approx(4.67, abs=0.01)
        assert result["recent_feedback_summary"]["intervention_success_rate"] == pytest.approx(0.667, abs=0.01)
        assert "High overall confidence" in result["strengths"]
        assert "Extensive supervision experience" in result["strengths"]

    async def test_insights_empty_ratings_and_outcomes(self):
        perf = _make_performance(confidence_score=0.3, competence_level="novice",
                                 performance_trend="declining",
                                 total_sessions_supervised=5)
        from core.models import SupervisorPerformance, SupervisorRating, InterventionOutcome
        perf_chain = MagicMock()
        perf_chain.filter.return_value.first.return_value = perf
        empty_chain = MagicMock()
        empty_chain.filter.return_value.all.return_value = []
        routing = {
            SupervisorPerformance: perf_chain,
            SupervisorRating: empty_chain,
            InterventionOutcome: empty_chain,
        }
        db = MagicMock()
        db.query.side_effect = lambda model: routing[model]
        svc = SupervisorLearningService(db)
        result = await svc.calculate_learning_insights("sup-1")
        assert "Low confidence score needs improvement" in result["weaknesses"]
        assert "Limited supervision experience" in result["weaknesses"]
        assert "Declining performance trend" in result["weaknesses"]


# ---------------------------------------------------------------------------
# _identify_strengths / _identify_weaknesses / _generate_recommendations
# ---------------------------------------------------------------------------

class TestStrengths:
    async def test_high_confidence_strength(self):
        perf = _make_performance(confidence_score=0.85, total_sessions_supervised=10,
                                  performance_trend="stable")
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_strengths(perf, [], [])
        assert "High overall confidence" in result

    async def test_exceptional_ratings(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        ratings = [_make_rating(5), _make_rating(5), _make_rating(5)]
        result = await svc._identify_strengths(perf, ratings, [])
        assert "Exceptional supervisor ratings" in result

    async def test_strong_ratings(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        ratings = [_make_rating(4), _make_rating(4)]
        result = await svc._identify_strengths(perf, ratings, [])
        assert "Strong supervisor ratings" in result

    async def test_excellent_intervention_success(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        outcomes = [_make_outcome("success") for _ in range(9)] + [_make_outcome("failure")]
        result = await svc._identify_strengths(perf, [], outcomes)
        assert "Excellent intervention success rate" in result

    async def test_good_intervention_success(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        outcomes = [_make_outcome("success") for _ in range(8)] + [_make_outcome("failure")] * 2
        result = await svc._identify_strengths(perf, [], outcomes)
        assert "Good intervention success rate" in result

    async def test_extensive_experience(self):
        perf = _make_performance(total_sessions_supervised=150)
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_strengths(perf, [], [])
        assert "Extensive supervision experience" in result

    async def test_improving_trend_strength(self):
        perf = _make_performance(performance_trend="improving")
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_strengths(perf, [], [])
        assert "Consistently improving performance" in result

    async def test_default_strength_when_none(self):
        perf = _make_performance(confidence_score=0.5, total_sessions_supervised=10,
                                  performance_trend="stable")
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_strengths(perf, [], [])
        assert result == ["Developing core skills"]


class TestWeaknesses:
    async def test_low_confidence(self):
        perf = _make_performance(confidence_score=0.4)
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_weaknesses(perf, [], [])
        assert "Low confidence score needs improvement" in result

    async def test_below_average_ratings(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        ratings = [_make_rating(2), _make_rating(2)]
        result = await svc._identify_weaknesses(perf, ratings, [])
        assert "Below-average supervisor ratings" in result

    async def test_poor_intervention_success(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        outcomes = [_make_outcome("failure"), _make_outcome("failure")]
        result = await svc._identify_weaknesses(perf, [], outcomes)
        assert "Intervention success rate needs improvement" in result

    async def test_declining_trend(self):
        perf = _make_performance(performance_trend="declining")
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_weaknesses(perf, [], [])
        assert "Declining performance trend" in result

    async def test_limited_experience(self):
        perf = _make_performance(total_sessions_supervised=5)
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_weaknesses(perf, [], [])
        assert "Limited supervision experience" in result

    async def test_default_weakness_when_none(self):
        perf = _make_performance(confidence_score=0.6, total_sessions_supervised=50,
                                  performance_trend="stable")
        svc, _ = _service_with_existing(perf)
        result = await svc._identify_weaknesses(perf, [], [])
        assert result == ["No significant weaknesses identified"]


class TestRecommendations:
    async def test_novice_recommendation(self):
        perf = _make_performance(competence_level="novice")
        svc, _ = _service_with_existing(perf)
        result = await svc._generate_recommendations(perf, [], [])
        assert any("training modules" in r for r in result)

    async def test_intermediate_recommendation(self):
        perf = _make_performance(competence_level="intermediate")
        svc, _ = _service_with_existing(perf)
        result = await svc._generate_recommendations(perf, [], [])
        assert any("Continue practicing" in r for r in result)

    async def test_advanced_recommendation(self):
        perf = _make_performance(competence_level="advanced")
        svc, _ = _service_with_existing(perf)
        result = await svc._generate_recommendations(perf, [], [])
        assert any("mentoring" in r for r in result)

    async def test_low_success_rate_recommendation(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        outcomes = [_make_outcome("failure"), _make_outcome("failure")]
        result = await svc._generate_recommendations(perf, [], outcomes)
        assert any("Review intervention techniques" in r for r in result)

    async def test_high_success_rate_recommendation(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        outcomes = [_make_outcome("success") for _ in range(10)]
        result = await svc._generate_recommendations(perf, [], outcomes)
        assert any("knowledge sharing" in r for r in result)

    async def test_many_low_ratings_recommendation(self):
        perf = _make_performance()
        svc, _ = _service_with_existing(perf)
        # > 20% low ratings (3 of 10 are <= 2)
        ratings = [_make_rating(1), _make_rating(2), _make_rating(1)] + [_make_rating(5) for _ in range(7)]
        result = await svc._generate_recommendations(perf, ratings, [])
        assert any("Analyze low-rated sessions" in r for r in result)

    async def test_declining_trend_recommendation(self):
        perf = _make_performance(competence_level="intermediate", performance_trend="declining")
        svc, _ = _service_with_existing(perf)
        result = await svc._generate_recommendations(perf, [], [])
        assert any("Performance declining" in r for r in result)

    async def test_default_recommendation(self):
        perf = _make_performance(competence_level="expert", performance_trend="stable")
        svc, _ = _service_with_existing(perf)
        result = await svc._generate_recommendations(perf, [], [])
        assert result == ["Continue current approach"]


# ---------------------------------------------------------------------------
# _calculate_learning_velocity + _estimate_time_to_next_level
# ---------------------------------------------------------------------------

class TestLearningVelocity:
    async def test_velocity_with_learning_rate(self):
        perf = _make_performance(learning_rate=0.05, performance_trend="improving",
                                 confidence_score=0.4, competence_level="novice")
        svc, _ = _service_with_existing(perf)
        result = await svc._calculate_learning_velocity(perf, time_range_days=30)
        assert result["learning_rate"] == 0.05
        assert result["confidence_velocity"] == pytest.approx(0.05 / 30 * 30, abs=0.001)
        assert result["estimated_time_to_next_level"] is not None

    async def test_velocity_zero_learning_rate(self):
        perf = _make_performance(learning_rate=0.0)
        svc, _ = _service_with_existing(perf)
        result = await svc._calculate_learning_velocity(perf, time_range_days=30)
        assert result["confidence_velocity"] == 0.0


class TestEstimateTimeToNextLevel:
    def _svc(self):
        return SupervisorLearningService(MagicMock())

    def test_expert_returns_none(self):
        perf = _make_performance(competence_level="expert", learning_rate=0.05)
        assert self._svc()._estimate_time_to_next_level(perf) is None

    def test_zero_learning_rate_returns_none(self):
        perf = _make_performance(competence_level="novice", learning_rate=0.0,
                                 confidence_score=0.4)
        assert self._svc()._estimate_time_to_next_level(perf) is None

    def test_negative_learning_rate_returns_none(self):
        perf = _make_performance(competence_level="novice", learning_rate=-0.01,
                                 confidence_score=0.4)
        assert self._svc()._estimate_time_to_next_level(perf) is None

    def test_ready_for_promotion_when_above_threshold(self):
        perf = _make_performance(competence_level="novice", learning_rate=0.05,
                                 confidence_score=0.55)  # above 0.50 threshold
        assert self._svc()._estimate_time_to_next_level(perf) == "Ready for promotion"

    def test_at_threshold_ready_for_promotion(self):
        perf = _make_performance(competence_level="novice", learning_rate=0.05,
                                 confidence_score=0.50)  # gap = 0 -> ready
        assert self._svc()._estimate_time_to_next_level(perf) == "Ready for promotion"

    def test_estimated_days_format(self):
        # gap 0.10, learning_rate 0.05 -> days = 0.10 / (0.05*30) = 0.0667 days
        perf = _make_performance(competence_level="novice", learning_rate=0.05,
                                 confidence_score=0.40)
        result = self._svc()._estimate_time_to_next_level(perf)
        assert "days" in result

    def test_estimated_months_format(self):
        # gap 0.10, learning_rate 0.001 -> days = 0.10/(0.001*30) = 3.33 days -> still days
        # need bigger gap to push past 30 days: gap 1.0 impossible. Use small lr.
        # gap 0.10, lr 0.001 -> 3.33 days. Use lr 0.0001 -> 333 days -> months+
        perf = _make_performance(competence_level="novice", learning_rate=0.0001,
                                 confidence_score=0.40)
        result = self._svc()._estimate_time_to_next_level(perf)
        assert "months" in result

    def test_advanced_level_threshold(self):
        # advanced threshold is 0.85; confidence 0.80 -> gap 0.05
        perf = _make_performance(competence_level="advanced", learning_rate=0.01,
                                 confidence_score=0.80)
        result = self._svc()._estimate_time_to_next_level(perf)
        assert result is not None

    def test_unknown_level_uses_default_threshold(self):
        perf = _make_performance(competence_level="guru", learning_rate=0.05,
                                 confidence_score=0.40)
        # unknown level -> threshold 0.85
        result = self._svc()._estimate_time_to_next_level(perf)
        assert result is not None


# ---------------------------------------------------------------------------
# _empty_insights
# ---------------------------------------------------------------------------

class TestEmptyInsights:
    def test_empty_insights_structure(self):
        svc = SupervisorLearningService(MagicMock())
        result = svc._empty_insights()
        assert result["current_state"]["confidence_score"] == 0.5
        assert result["current_state"]["competence_level"] == "novice"
        assert result["strengths"] == []
        assert result["recommendations"] == ["Start supervising sessions to establish baseline"]
        assert result["learning_velocity"]["estimated_time_to_next_level"] is None
        assert result["recent_feedback_summary"]["intervention_success_rate"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
