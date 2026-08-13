"""Coverage wave 64 — core/continuous_learning_service.py (TDD, mocked db).

Covers the full online-learning pipeline: feedback recording (RLHF),
learning-record creation/update, parameter adjustment (online learning
with clamped temperature/top_p/penalties), progress/trend reporting,
per-user personalization, and adaptation recommendations, plus every
exception fallback (rollback + error dicts).
"""
from types import SimpleNamespace

import pytest

from core.continuous_learning_service import ContinuousLearningService
from core.models import AgentFeedback, AgentLearning


class FakeQuery:
    def __init__(self, first_result=None, all_result=None):
        self._first = first_result
        self._all = all_result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all


class FakeDB:
    def __init__(self, query_plan=None):
        self.query_plan = query_plan or {}
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.refreshed = []

    def query(self, model):
        return self.query_plan.get(model, FakeQuery())

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = f"id-{len(self.added)}"

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def flush(self):
        self.flushes += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def make_feedback(**kw):
    defaults = dict(
        tenant_id="tenant-1",
        agent_id="agent-1",
        user_id="user-1",
        feedback_type="positive",
        rating=5,
        agent_execution_id="exec-1",
        ai_reasoning=None,
        user_correction="",
        created_at=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_learning(**kw):
    defaults = dict(
        tenant_id="tenant-1",
        agent_id="agent-1",
        total_feedback=5,
        positive_feedback=4,
        negative_feedback=1,
        avg_rating=4.0,
        learning_rate=0.01,
        parameters_json={
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        },
        last_updated_at=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


@pytest.fixture
def service():
    db = FakeDB()
    return ContinuousLearningService(db)


class TestRecordFeedback:
    def test_record_feedback_success(self, service):
        db = service.db
        db.query_plan[AgentLearning] = FakeQuery(first_result=None)
        result = service.record_feedback(
            "tenant-1", "agent-1", "exec-1", "user-1",
            "positive", rating=5, comments="nice", corrected_output="fixed",
        )
        assert result is not None
        assert db.commits == 2
        assert db.refreshed
        fb = db.added[0]
        assert isinstance(fb, AgentFeedback)
        assert fb.tenant_id == "tenant-1"
        assert fb.agent_id == "agent-1"
        assert fb.agent_execution_id == "exec-1"
        assert fb.user_id == "user-1"
        assert fb.feedback_type == "positive"
        assert fb.rating == 5
        assert fb.ai_reasoning == "nice"
        assert fb.user_correction == "fixed"
        learning = db.added[1]
        assert isinstance(learning, AgentLearning)
        assert learning.total_feedback == 1
        assert learning.positive_feedback == 1

    def test_record_feedback_no_correction_uses_empty_string(self, service):
        db = service.db
        db.query_plan[AgentLearning] = FakeQuery(first_result=None)
        service.record_feedback(
            "tenant-1", "agent-1", "exec-1", "user-1", "negative",
        )
        fb = db.added[0]
        assert fb.user_correction == ""
        learning = db.added[1]
        assert learning.negative_feedback == 1

    def test_record_feedback_commit_failure_returns_none(self, service):
        service.db.commit = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        result = service.record_feedback(
            "tenant-1", "agent-1", "exec-1", "user-1", "positive",
        )
        assert result is None
        assert service.db.rollbacks == 1


class TestUpdateFromFeedback:
    def test_creates_new_learning_record_positive(self, service):
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=None)
        service.update_from_feedback(make_feedback(rating=5))
        assert service.db.flushes == 1
        assert service.db.commits == 1
        learning = service.db.added[0]
        assert learning.total_feedback == 1
        assert learning.positive_feedback == 1
        assert learning.negative_feedback == 0
        assert learning.avg_rating == 5.0
        assert learning.learning_rate == 0.01
        params = learning.parameters_json
        assert params["success_rate"] == 1.0
        assert params["temperature"] < 0.7

    def test_creates_new_learning_record_negative_without_rating(self, service):
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=None)
        service.update_from_feedback(make_feedback(feedback_type="rejection", rating=None))
        learning = service.db.added[0]
        assert learning.positive_feedback == 0
        assert learning.negative_feedback == 1
        assert learning.avg_rating is None
        assert learning.parameters_json["success_rate"] == 0.0
        assert learning.parameters_json["temperature"] > 0.7

    def test_creates_new_learning_record_neutral_type(self, service):
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=None)
        service.update_from_feedback(make_feedback(feedback_type="comment", rating=None))
        learning = service.db.added[0]
        assert learning.total_feedback == 1
        assert learning.positive_feedback == 0
        assert learning.negative_feedback == 0

    def test_updates_existing_positive_feedback(self, service):
        learning = make_learning(total_feedback=5, positive_feedback=3, negative_feedback=2, avg_rating=4.0)
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.update_from_feedback(make_feedback(rating=4))
        assert learning.total_feedback == 6
        assert learning.positive_feedback == 4
        assert learning.negative_feedback == 2
        assert learning.avg_rating == pytest.approx((4.0 * 5 + 4) / 6)

    def test_updates_existing_negative_correction(self, service):
        learning = make_learning(total_feedback=4, positive_feedback=3, negative_feedback=1)
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.update_from_feedback(make_feedback(feedback_type="correction", rating=1))
        assert learning.negative_feedback == 2

    def test_neutral_feedback_no_counter_change(self, service):
        learning = make_learning()
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.update_from_feedback(make_feedback(feedback_type="comment", rating=None))
        assert learning.total_feedback == 6
        assert learning.positive_feedback == 4
        assert learning.negative_feedback == 1

    def test_avg_rating_set_when_previously_none(self, service):
        learning = make_learning(avg_rating=None)
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.update_from_feedback(make_feedback(rating=3))
        assert learning.avg_rating == 3.0

    def test_parameters_json_none_gets_success_rate(self, service):
        learning = make_learning(parameters_json=None)
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.update_from_feedback(make_feedback(rating=5))
        assert learning.parameters_json["success_rate"] == pytest.approx((6 - 1) / 6, abs=1e-4)

    def test_existing_learning_parameters_preserved_and_adjusted(self, service):
        learning = make_learning(parameters_json={"temperature": 0.5})
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.update_from_feedback(make_feedback(feedback_type="negative", rating=2))
        params = learning.parameters_json
        assert params["temperature"] > 0.5
        assert params["presence_penalty"] > 0.0
        assert params["top_p"] == 0.9
        assert params["success_rate"] == pytest.approx((6 - 2) / 6, abs=1e-4)

    def test_exception_rolls_back(self, service):
        service.db.query = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        service.update_from_feedback(make_feedback())
        assert service.db.rollbacks == 1


class TestAdjustParameters:
    def test_positive_reinforces_behavior(self, service):
        learning = make_learning(learning_rate=0.02, total_feedback=10)
        params = service._adjust_parameters(learning, make_feedback(feedback_type="approval"))
        assert params["temperature"] == pytest.approx(0.7 - 0.02 * 0.1)
        assert params["presence_penalty"] == 0.0

    def test_negative_encourages_exploration(self, service):
        learning = make_learning(learning_rate=0.02, total_feedback=10)
        params = service._adjust_parameters(learning, make_feedback(feedback_type="rejection"))
        assert params["temperature"] == pytest.approx(0.7 + 0.02 * 0.2)
        assert params["presence_penalty"] == pytest.approx(0.02 * 0.1)

    def test_neutral_no_directional_adjustment(self, service):
        learning = make_learning()
        params = service._adjust_parameters(learning, make_feedback(feedback_type="comment"))
        assert params["temperature"] == 0.7

    def test_parameters_clamped_to_valid_ranges(self, service):
        learning = make_learning(parameters_json={
            "temperature": -1.0,
            "top_p": 5.0,
            "frequency_penalty": -5.0,
            "presence_penalty": 5.0,
        })
        params = service._adjust_parameters(learning, make_feedback(feedback_type="comment"))
        assert params["temperature"] == 0.0
        assert params["top_p"] == 1.0
        assert params["frequency_penalty"] == -2.0
        assert params["presence_penalty"] == 2.0

    def test_negative_adjustments_capped(self, service):
        learning = make_learning(learning_rate=2.0, total_feedback=1, parameters_json={
            "temperature": 0.99,
            "presence_penalty": 1.99,
        })
        params = service._adjust_parameters(learning, make_feedback(feedback_type="negative"))
        assert params["temperature"] == 1.0
        assert params["presence_penalty"] == 2.0

    def test_positive_temperature_floor(self, service):
        learning = make_learning(learning_rate=2.0, total_feedback=1, parameters_json={"temperature": 0.05})
        params = service._adjust_parameters(learning, make_feedback(feedback_type="positive"))
        assert params["temperature"] == 0.1

    def test_learning_rate_none_or_zero_falls_back(self, service):
        for rate in (None, 0):
            learning = make_learning(learning_rate=rate, total_feedback=0)
            params = service._adjust_parameters(learning, make_feedback(feedback_type="positive"))
            assert params["temperature"] == pytest.approx(0.7 - 0.01 * 0.1)

    def test_parameters_json_none_uses_defaults(self, service):
        learning = make_learning(parameters_json=None)
        params = service._adjust_parameters(learning, make_feedback(feedback_type="negative"))
        assert params["top_p"] == 0.9
        assert params["frequency_penalty"] == 0.0


class TestGetLearningProgress:
    def test_not_started(self, service):
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=None)
        result = service.get_learning_progress("tenant-1", "agent-1")
        assert result["status"] == "not_started"
        assert result["total_feedback"] == 0
        assert result["parameters"] == {}
        assert result["improvement_trend"] == "unknown"

    def test_learning_without_recent_feedback(self, service):
        learning = make_learning(total_feedback=10, positive_feedback=6, negative_feedback=4)
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=[])
        result = service.get_learning_progress("tenant-1", "agent-1")
        assert result["status"] == "learning"
        assert result["positive_rate"] == 0.6
        assert result["recent_positive_rate"] is None
        assert result["avg_rating"] == 4.0
        assert result["improvement_trend"] == "insufficient_data"

    def test_trend_improving(self, service):
        learning = make_learning(total_feedback=10, positive_feedback=4, avg_rating=None)
        recent = [
            make_feedback(feedback_type="positive"),
            make_feedback(feedback_type="approval"),
            make_feedback(feedback_type="positive"),
        ]
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=recent)
        result = service.get_learning_progress("tenant-1", "agent-1")
        assert result["positive_rate"] == 0.4
        assert result["recent_positive_rate"] == pytest.approx(1.0)
        assert result["improvement_trend"] == "improving"
        assert result["avg_rating"] is None

    def test_trend_declining(self, service):
        learning = make_learning(total_feedback=10, positive_feedback=8, negative_feedback=2)
        recent = [
            make_feedback(feedback_type="negative"),
            make_feedback(feedback_type="correction"),
            make_feedback(feedback_type="negative"),
        ]
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=recent)
        result = service.get_learning_progress("tenant-1", "agent-1")
        assert result["positive_rate"] == 0.8
        assert result["improvement_trend"] == "declining"

    def test_trend_stable(self, service):
        learning = make_learning(total_feedback=10, positive_feedback=5, negative_feedback=5)
        recent = [
            make_feedback(feedback_type="positive"),
            make_feedback(feedback_type="negative"),
            make_feedback(feedback_type="positive"),
            make_feedback(feedback_type="negative"),
        ]
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=recent)
        result = service.get_learning_progress("tenant-1", "agent-1")
        assert result["improvement_trend"] == "stable"

    def test_last_updated_isoformat(self, service):
        from datetime import datetime, timezone
        ts = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
        learning = make_learning(last_updated_at=ts, avg_rating=None)
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=[])
        result = service.get_learning_progress("tenant-1", "agent-1")
        assert result["last_updated"] == "2026-08-01T12:00:00+00:00"
        assert result["learning_rate"] == 0.01

    def test_exception_returns_error_dict(self, service):
        service.db.query = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        result = service.get_learning_progress("tenant-1", "agent-1")
        assert result["status"] == "error"
        assert "boom" in result["error"]


class TestGetPersonalizedParameters:
    def test_no_learning_returns_defaults(self, service):
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=None)
        result = service.get_personalized_parameters("tenant-1", "agent-1")
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9

    def test_learning_parameters_returned(self, service):
        learning = make_learning(parameters_json={"temperature": 0.3, "top_p": 0.5})
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        result = service.get_personalized_parameters("tenant-1", "agent-1")
        assert result["temperature"] == 0.3
        assert result["top_p"] == 0.5

    def test_user_prefers_consistency_high_positive_rate(self, service):
        learning = make_learning(parameters_json={"temperature": 0.7})
        user_feedback = [
            make_feedback(feedback_type="positive"),
            make_feedback(feedback_type="approval"),
            make_feedback(feedback_type="positive"),
        ]
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=user_feedback)
        result = service.get_personalized_parameters("tenant-1", "agent-1", "user-1")
        assert result["temperature"] == 0.6

    def test_user_prefers_variety_low_positive_rate(self, service):
        learning = make_learning(parameters_json={"temperature": 0.7})
        user_feedback = [
            make_feedback(feedback_type="negative"),
            make_feedback(feedback_type="negative"),
            make_feedback(feedback_type="positive"),
        ]
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=user_feedback)
        result = service.get_personalized_parameters("tenant-1", "agent-1", "user-1")
        assert result["temperature"] == pytest.approx(0.8)

    def test_user_mid_rate_no_change(self, service):
        learning = make_learning(parameters_json={"temperature": 0.7})
        user_feedback = [
            make_feedback(feedback_type="positive"),
            make_feedback(feedback_type="negative"),
            make_feedback(feedback_type="positive"),
        ]
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=user_feedback)
        result = service.get_personalized_parameters("tenant-1", "agent-1", "user-1")
        assert result["temperature"] == 0.7

    def test_user_with_no_feedback(self, service):
        learning = make_learning(parameters_json={"temperature": 0.7})
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=[])
        result = service.get_personalized_parameters("tenant-1", "agent-1", "user-1")
        assert result["temperature"] == 0.7

    def test_user_temperature_clamps(self, service):
        learning = make_learning(parameters_json={"temperature": 0.05})
        user_feedback = [make_feedback(feedback_type="positive")] * 5
        service.db.query_plan[AgentLearning] = FakeQuery(first_result=learning)
        service.db.query_plan[AgentFeedback] = FakeQuery(all_result=user_feedback)
        result = service.get_personalized_parameters("tenant-1", "agent-1", "user-1")
        assert result["temperature"] == 0.2

    def test_exception_returns_defaults(self, service):
        service.db.query = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        result = service.get_personalized_parameters("tenant-1", "agent-1", "user-1")
        assert result == {
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }


class TestGenerateAdaptations:
    def test_low_positive_rate_and_declining(self, service):
        service.get_learning_progress = lambda t, a: {
            "positive_rate": 0.5,
            "total_feedback": 60,
            "improvement_trend": "declining",
        }
        adaptations = service.generate_adaptations("tenant-1", "agent-1")
        types = [a["type"] for a in adaptations]
        assert "parameter_adjustment" in types
        assert "performance_review" in types

    def test_high_success_maturity_advancement(self, service):
        service.get_learning_progress = lambda t, a: {
            "positive_rate": 0.95,
            "total_feedback": 100,
            "improvement_trend": "improving",
        }
        adaptations = service.generate_adaptations("tenant-1", "agent-1")
        assert adaptations[0]["type"] == "maturity_advancement"

    def test_limit_slicing(self, service):
        service.get_learning_progress = lambda t, a: {
            "positive_rate": 0.5,
            "total_feedback": 100,
            "improvement_trend": "declining",
        }
        adaptations = service.generate_adaptations("tenant-1", "agent-1", limit=1)
        assert len(adaptations) == 1

    def test_no_conditions_no_adaptations(self, service):
        service.get_learning_progress = lambda t, a: {
            "positive_rate": 0.7,
            "total_feedback": 10,
            "improvement_trend": "stable",
        }
        assert service.generate_adaptations("tenant-1", "agent-1") == []

    def test_low_rate_but_few_feedback_no_adjustment(self, service):
        service.get_learning_progress = lambda t, a: {
            "positive_rate": 0.2,
            "total_feedback": 3,
            "improvement_trend": "stable",
        }
        assert service.generate_adaptations("tenant-1", "agent-1") == []

    def test_exception_returns_empty(self, service):
        service.get_learning_progress = lambda t, a: (_ for _ in ()).throw(RuntimeError("boom"))
        assert service.generate_adaptations("tenant-1", "agent-1") == []
