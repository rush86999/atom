"""Coverage wave 42 — core/feedback_analytics.py (15% → 90%+).

Real in-memory SQLite with AgentRegistry + AgentFeedback rows drives every
aggregation branch: agent summary (empty/full), overall statistics (empty/full),
top performers (qualification threshold, missing-agent skip), most-corrected,
daily trends, breakdown by type.
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.feedback_analytics import FeedbackAnalytics
from core.models import AgentFeedback, AgentRegistry, AgentStatus


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def _agent(db, agent_id=None):
    agent = AgentRegistry(
        id=agent_id or f"agent-{uuid.uuid4().hex[:8]}",
        name=f"Agent {agent_id or 'X'}",
        category="general", description="d",
        status=AgentStatus.SUPERVISED.value, confidence_score=0.75,
        module_path="core.agents.generic_agent", class_name="GenericAgent",
        workspace_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


def _feedback(db, agent_id, *, thumbs=None, rating=None, ftype=None, days_ago=0):
    fb = AgentFeedback(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        user_id="u1",
        original_output="out",
        user_correction="corr",
        thumbs_up_down=thumbs,
        rating=rating,
        feedback_type=ftype,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(fb)
    db.commit()
    return fb


class TestAgentFeedbackSummary:
    def test_agent_not_found_raises(self, db):
        with pytest.raises(ValueError):
            FeedbackAnalytics(db).get_agent_feedback_summary("missing-agent")

    def test_no_feedback_empty_summary(self, db):
        agent = _agent(db)
        summary = FeedbackAnalytics(db).get_agent_feedback_summary(agent.id)
        assert summary["total_feedback"] == 0
        assert summary["average_rating"] is None
        assert summary["rating_distribution"] == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def test_full_summary(self, db):
        agent = _agent(db)
        _feedback(db, agent.id, thumbs=True, rating=5, ftype="praise")
        _feedback(db, agent.id, thumbs=False, rating=1, ftype="correction")
        _feedback(db, agent.id, rating=4)
        summary = FeedbackAnalytics(db).get_agent_feedback_summary(agent.id)
        assert summary["total_feedback"] == 3
        assert summary["thumbs_up_count"] == 1
        assert summary["thumbs_down_count"] == 1
        assert summary["positive_count"] == 2  # thumbs-up + rating 4
        assert summary["negative_count"] == 1
        assert summary["average_rating"] == pytest.approx(10 / 3)
        assert summary["rating_distribution"] == {1: 1, 2: 0, 3: 0, 4: 1, 5: 1}
        assert summary["feedback_types"] == {"praise": 1, "correction": 1}

    def test_old_feedback_excluded_by_days(self, db):
        agent = _agent(db)
        _feedback(db, agent.id, thumbs=True, days_ago=40)
        summary = FeedbackAnalytics(db).get_agent_feedback_summary(agent.id, days=30)
        assert summary["total_feedback"] == 0


class TestFeedbackStatistics:
    def test_empty_statistics(self, db):
        stats = FeedbackAnalytics(db).get_feedback_statistics(days=30)
        assert stats["total_feedback"] == 0
        assert stats["overall_average_rating"] is None

    def test_full_statistics(self, db):
        agent = _agent(db)
        _feedback(db, agent.id, thumbs=True, rating=5, ftype="praise")
        _feedback(db, agent.id, thumbs=False, rating=1, ftype="correction")
        stats = FeedbackAnalytics(db).get_feedback_statistics(days=30)
        assert stats["total_feedback"] == 2
        assert stats["total_agents_with_feedback"] == 1
        assert stats["overall_positive_ratio"] == 0.5
        assert stats["overall_average_rating"] == 3.0
        assert stats["feedback_by_type"] == {"praise": 1, "correction": 1}


class TestTopPerformingAgents:
    def test_below_qualification_threshold_excluded(self, db):
        agent = _agent(db)
        _feedback(db, agent.id, thumbs=True)
        _feedback(db, agent.id, thumbs=True)
        top = FeedbackAnalytics(db).get_top_performing_agents(days=30)
        assert top == []

    def test_qualified_sorted_and_missing_agent_skipped(self, db):
        agent_a = _agent(db, agent_id="agent-a")
        agent_b = _agent(db, agent_id="agent-b")
        for _ in range(5):
            _feedback(db, agent_a.id, thumbs=True)
            _feedback(db, agent_b.id, thumbs=False)
        # feedback for a non-registered agent id — skipped in output
        for _ in range(5):
            _feedback(db, "ghost-agent", thumbs=True)
        top = FeedbackAnalytics(db).get_top_performing_agents(days=30, limit=10)
        assert top[0]["agent_id"] == "agent-a"
        assert top[0]["positive_ratio"] == 1.0
        assert top[0]["agent_name"] == "Agent agent-a"
        assert all(a["agent_id"] != "ghost-agent" for a in top)


class TestMostCorrectedAgents:
    def test_most_corrected(self, db):
        agent = _agent(db, agent_id="agent-c")
        _feedback(db, agent.id, ftype="correction")
        _feedback(db, agent.id, ftype="correction")
        _feedback(db, agent.id, ftype="praise")
        corrected = FeedbackAnalytics(db).get_most_corrected_agents(days=30)
        assert corrected[0]["agent_id"] == "agent-c"
        assert corrected[0]["correction_count"] == 2

    def test_empty_when_no_corrections(self, db):
        agent = _agent(db)
        _feedback(db, agent.id, ftype="praise")
        assert FeedbackAnalytics(db).get_most_corrected_agents() == []


class TestFeedbackTrends:
    def test_trends_grouped_by_day(self, db):
        agent = _agent(db)
        _feedback(db, agent.id, thumbs=True, rating=5)
        _feedback(db, agent.id, thumbs=False, rating=1)
        _feedback(db, agent.id, rating=3, days_ago=1)
        trends = FeedbackAnalytics(db).get_feedback_trends(days=30)
        assert len(trends) == 2
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert trends[0]["date"] == (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        assert trends[0]["average_rating"] == 3.0
        assert trends[1]["date"] == today
        assert trends[1]["total"] == 2
        assert trends[1]["positive"] == 1
        assert trends[1]["negative"] == 1
        assert trends[1]["average_rating"] == 3.0

    def test_trends_empty(self, db):
        assert FeedbackAnalytics(db).get_feedback_trends(days=30) == []


class TestBreakdownByType:
    def test_breakdown(self, db):
        agent = _agent(db)
        _feedback(db, agent.id, ftype="correction")
        _feedback(db, agent.id, ftype="correction")
        _feedback(db, agent.id, ftype=None)
        breakdown = FeedbackAnalytics(db).get_feedback_breakdown_by_type(days=30)
        assert breakdown == {"correction": 2}

    def test_breakdown_empty(self, db):
        assert FeedbackAnalytics(db).get_feedback_breakdown_by_type() == {}
