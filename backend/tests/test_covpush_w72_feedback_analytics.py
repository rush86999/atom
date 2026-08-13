# -*- coding: utf-8 -*-
"""Coverage wave 72 — core/feedback_advanced_analytics (in-memory SQLite,
no network, no LLM spend).

Covers the whole service (baseline 11%): feedback/performance correlation
(empty, thumbs-only, rating-only, mixed, executions absent), all five
correlation interpretations, cohort analysis (missing agents skipped,
categories, corrections, ratings), performance prediction (insufficient data,
all five trend bands + every recommendation branch), and feedback velocity
(empty, uniform, bursty, variable).
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentExecution, AgentFeedback, AgentRegistry, User
from core.feedback_advanced_analytics import AdvancedFeedbackAnalytics


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def svc(db):
    return AdvancedFeedbackAnalytics(db)


def _make_agent(db, agent_id, category="Test"):
    agent = AgentRegistry(id=agent_id, name=f"Agent {agent_id}",
                          workspace_id="ws-1", tenant_id="default",
                          category=category, module_path="test",
                          class_name="Test")
    db.add(agent)
    return agent


def _make_execution(db, exec_id, agent_id, status="completed"):
    execution = AgentExecution(id=exec_id, agent_id=agent_id, status=status)
    db.add(execution)
    return execution


def _make_feedback(db, fb_id, agent_id, *, execution_id=None, thumbs=None,
                   rating=None, feedback_type=None, days_ago=1,
                   user_id="user-1"):
    feedback = AgentFeedback(
        id=fb_id,
        tenant_id="default",
        agent_id=agent_id,
        agent_execution_id=execution_id,
        user_id=user_id,
        original_output="out",
        user_correction="corr",
        thumbs_up_down=thumbs,
        rating=rating,
        feedback_type=feedback_type,
        created_at=datetime.now() - timedelta(days=days_ago),
    )
    db.add(feedback)
    return feedback


# ============================================================================
# analyze_feedback_performance_correlation
# ============================================================================

def test_correlation_no_feedback(svc):
    result = svc.analyze_feedback_performance_correlation("agent-1")
    assert result == {"agent_id": "agent-1", "message": "Insufficient data for correlation analysis"}


def test_correlation_with_feedback_no_executions(svc):
    _make_agent(db=svc.db, agent_id="agent-1")
    _make_feedback(svc.db, "fb1", "agent-1", thumbs=True, execution_id="ex-none")
    result = svc.analyze_feedback_performance_correlation("agent-1")
    assert result["feedback_with_executions"] == 1
    assert result["positive_feedback_executions"] == 1
    assert result["positive_success_rate"] == 0.0
    assert result["negative_success_rate"] == 0.0
    assert result["correlation_strength"] == 0.0


def test_correlation_full_math(svc):
    _make_agent(db=svc.db, agent_id="agent-1")
    # positive feedback: 2 executions completed, 1 failed
    _make_execution(svc.db, "ex-ok-1", "agent-1", "completed")
    _make_execution(svc.db, "ex-ok-2", "agent-1", "completed")
    _make_execution(svc.db, "ex-bad", "agent-1", "failed")
    # negative feedback: 1 completed, 1 error
    _make_execution(svc.db, "ex-neg-ok", "agent-1", "completed")
    _make_execution(svc.db, "ex-neg-err", "agent-1", "error")
    svc.db.commit()

    _make_feedback(svc.db, "fb1", "agent-1", execution_id="ex-ok-1", thumbs=True)
    _make_feedback(svc.db, "fb2", "agent-1", execution_id="ex-ok-2", rating=5)
    _make_feedback(svc.db, "fb3", "agent-1", execution_id="ex-bad", rating=4)  # rating >= 4 -> positive
    _make_feedback(svc.db, "fb4", "agent-1", execution_id="ex-neg-ok", thumbs=False)
    _make_feedback(svc.db, "fb5", "agent-1", execution_id="ex-neg-err", rating=1)
    svc.db.commit()

    result = svc.analyze_feedback_performance_correlation("agent-1")
    assert result["feedback_with_executions"] == 5
    assert result["positive_feedback_executions"] == 3
    assert result["negative_feedback_executions"] == 2
    assert result["positive_success_rate"] == pytest.approx(2 / 3)
    assert result["negative_success_rate"] == pytest.approx(0.5)
    assert result["correlation_strength"] == pytest.approx(2 / 3 - 0.5)
    assert result["interpretation"] == svc._interpret_correlation(2 / 3 - 0.5)


def test_correlation_neutral_feedback_excluded(svc):
    _make_agent(db=svc.db, agent_id="agent-1")
    _make_execution(svc.db, "ex-1", "agent-1", "completed")
    svc.db.commit()
    _make_feedback(svc.db, "fb1", "agent-1", execution_id="ex-1", rating=3)  # neutral
    svc.db.commit()
    result = svc.analyze_feedback_performance_correlation("agent-1")
    assert result["positive_feedback_executions"] == 0
    assert result["negative_feedback_executions"] == 0


def test_interpret_correlation_all_bands(svc):
    assert svc._interpret_correlation(0.5) == "Strong positive correlation - positive feedback predicts success"
    assert svc._interpret_correlation(0.2) == "Moderate positive correlation - positive feedback associated with success"
    assert svc._interpret_correlation(0.0) == "Weak correlation - feedback and performance not strongly linked"
    assert svc._interpret_correlation(-0.2) == "Moderate negative correlation - surprising pattern, needs investigation"
    assert svc._interpret_correlation(-0.5) == "Strong negative correlation - investigate feedback quality"


# ============================================================================
# analyze_feedback_by_agent_cohort
# ============================================================================

def test_cohort_empty(svc):
    result = svc.analyze_feedback_by_agent_cohort(days=30)
    assert result["cohorts"] == {}


def test_cohort_missing_agent_skipped(svc):
    _make_feedback(svc.db, "fb1", "ghost-agent", thumbs=True)
    svc.db.commit()
    result = svc.analyze_feedback_by_agent_cohort(days=30)
    assert result["cohorts"] == {}


def test_cohort_grouping_and_aggregation(svc):
    _make_agent(svc.db, "a1", category="Finance")
    _make_agent(svc.db, "a2", category="Finance")
    _make_agent(svc.db, "b1", category="Ops")
    svc.db.commit()

    _make_feedback(svc.db, "fb1", "a1", thumbs=True, feedback_type="approval")
    _make_feedback(svc.db, "fb2", "a1", rating=5, feedback_type="rating")
    _make_feedback(svc.db, "fb3", "a2", thumbs=False, feedback_type="correction")
    _make_feedback(svc.db, "fb4", "a2", rating=2, feedback_type="rating")
    _make_feedback(svc.db, "fb5", "b1", rating=4, feedback_type="comment")
    _make_feedback(svc.db, "fb6", "b1", thumbs=True, days_ago=100)  # outside window
    svc.db.commit()

    result = svc.analyze_feedback_by_agent_cohort(days=30)
    finance = result["cohorts"]["Finance"]
    assert finance["agent_count"] == 2
    assert finance["total_feedback"] == 4
    assert finance["positive_count"] == 2
    assert finance["negative_count"] == 2
    assert finance["positive_ratio"] == pytest.approx(0.5)
    assert finance["average_rating"] == pytest.approx((5 + 2) / 2)
    assert finance["corrections"] == 1

    ops = result["cohorts"]["Ops"]
    assert ops["agent_count"] == 1
    assert ops["total_feedback"] == 1
    assert ops["positive_count"] == 1
    assert ops["positive_ratio"] == 1.0
    assert ops["average_rating"] == 4.0


# ============================================================================
# predict_agent_performance
# ============================================================================

def _seed_feedback_run(svc, agent_id, ratings):
    _make_agent(svc.db, agent_id)
    svc.db.commit()
    for i, rating in enumerate(ratings):
        _make_feedback(svc.db, f"{agent_id}-fb{i}", agent_id, rating=rating,
                       days_ago=len(ratings) - i)
    svc.db.commit()


def test_predict_insufficient_data(svc):
    _make_agent(svc.db, "agent-1")
    _make_feedback(svc.db, "fb1", "agent-1", rating=5)
    _make_feedback(svc.db, "fb2", "agent-1", rating=4)
    svc.db.commit()
    result = svc.predict_agent_performance("agent-1")
    assert result == {"agent_id": "agent-1", "message": "Insufficient data for prediction"}


def test_predict_strong_improving(svc):
    _seed_feedback_run(svc, "agent-1", [1, 1, 2, 2, 5, 5, 5, 5])  # 4 old low, 4 new high
    result = svc.predict_agent_performance("agent-1")
    assert result["prediction"] == "improving"
    assert result["confidence"] == "high"
    assert result["first_half_positive_ratio"] == 0.0
    assert result["second_half_positive_ratio"] == 1.0
    assert result["trend"] == 1.0
    assert result["recommendation"] == "Consider agent for promotion"


def test_predict_modest_improving(svc):
    # halves of 6: 4/6 -> 5/6 = +0.167 (0.05 < trend <= 0.2)
    _seed_feedback_run(svc, "agent-1", [5, 5, 4, 4, 1, 1, 5, 5, 5, 4, 4, 1])
    result = svc.predict_agent_performance("agent-1")
    assert result["prediction"] == "improving"
    assert result["confidence"] == "moderate"
    assert result["trend"] == pytest.approx(1 / 6)
    assert result["message"] == "Agent shows modest improvement trend"
    assert result["recommendation"] == "Continue current approach"


def test_predict_stable(svc):
    _seed_feedback_run(svc, "agent-1", [4, 5, 4, 5, 4, 5, 4, 5])  # 1.0 both halves
    result = svc.predict_agent_performance("agent-1")
    assert result["prediction"] == "stable"
    assert result["confidence"] == "moderate"
    assert result["recommendation"] == "Continue monitoring"


def test_predict_modest_declining(svc):
    # halves of 6: 5/6 -> 4/6 = -0.167 (-0.2 < trend <= -0.05)
    _seed_feedback_run(svc, "agent-1", [5, 5, 5, 4, 4, 1, 5, 5, 4, 4, 1, 1])
    result = svc.predict_agent_performance("agent-1")
    assert result["prediction"] == "declining"
    assert result["confidence"] == "moderate"
    assert result["trend"] == pytest.approx(-1 / 6)
    assert result["message"] == "Agent shows modest decline trend"
    assert result["recommendation"] == "Monitor closely and investigate issues"


def test_predict_strong_declining(svc):
    _seed_feedback_run(svc, "agent-1", [5, 5, 5, 5, 1, 1, 1, 1])  # half1 1.0, half2 0.0
    result = svc.predict_agent_performance("agent-1")
    assert result["prediction"] == "declining"
    assert result["confidence"] == "high"
    assert result["recommendation"] == "Review agent configuration and consider additional training"


def test_prediction_recommendation_fallback(svc):
    assert svc._get_prediction_recommendation("improving", "moderate") == "Continue current approach"


# ============================================================================
# analyze_feedback_velocity
# ============================================================================

def test_velocity_no_feedback(svc):
    _make_agent(svc.db, "agent-1")
    svc.db.commit()
    result = svc.analyze_feedback_velocity("agent-1")
    assert result == {"agent_id": "agent-1", "message": "No feedback data available"}


def test_velocity_uniform(svc):
    _make_agent(svc.db, "agent-1")
    svc.db.commit()
    for day in (1, 2, 3):
        _make_feedback(svc.db, f"fb-{day}-1", "agent-1", thumbs=True, days_ago=day)
        _make_feedback(svc.db, f"fb-{day}-2", "agent-1", thumbs=True, days_ago=day)
    svc.db.commit()
    result = svc.analyze_feedback_velocity("agent-1")
    assert result["total_feedback"] == 6
    assert result["days_with_feedback"] == 3
    assert result["average_per_day"] == 2.0
    assert result["max_per_day"] == 2
    assert result["min_per_day"] == 2
    assert result["pattern"] == "uniform"
    assert len(result["feedback_by_day"]) == 3


def test_velocity_bursty(svc):
    _make_agent(svc.db, "agent-1")
    svc.db.commit()
    for i in range(5):
        _make_feedback(svc.db, f"fb-a{i}", "agent-1", thumbs=True, days_ago=1)
    _make_feedback(svc.db, "fb-b1", "agent-1", thumbs=True, days_ago=2)
    _make_feedback(svc.db, "fb-b2", "agent-1", thumbs=True, days_ago=3)
    svc.db.commit()
    result = svc.analyze_feedback_velocity("agent-1")
    assert result["pattern"] == "bursty"  # max 5 > avg 7/3 * 2 = 4.67


def test_velocity_variable(svc):
    _make_agent(svc.db, "agent-1")
    svc.db.commit()
    for i in range(3):
        _make_feedback(svc.db, f"fb-a{i}", "agent-1", thumbs=True, days_ago=1)
    _make_feedback(svc.db, "fb-b1", "agent-1", thumbs=True, days_ago=2)
    _make_feedback(svc.db, "fb-c1", "agent-1", thumbs=True, days_ago=3)
    svc.db.commit()
    result = svc.analyze_feedback_velocity("agent-1")
    assert result["pattern"] == "variable"  # max 3 <= avg 5/3 * 2 = 3.33
