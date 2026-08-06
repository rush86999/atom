"""
Coverage-push tests for core.agent_learning_enhanced (AgentLearningEnhanced).

Mocks DB session, world model, and continuous learning service.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

import pytest

from core.agent_learning_enhanced import AgentLearningEnhanced


def make_learning(db=None, world_model=None, continuous=None):
    with patch("core.agent_learning_enhanced.WorldModelService", return_value=world_model or Mock()) as wm, \
         patch("core.agent_learning_enhanced.ContinuousLearningService", return_value=continuous or Mock()) as cl:
        learning = AgentLearningEnhanced(db or Mock())
    return learning, wm, cl


def make_feedback(**overrides):
    fb = Mock()
    fb.thumbs_up_down = None
    fb.rating = None
    fb.feedback_type = None
    fb.agent_id = "a1"
    fb.agent_execution_id = None
    fb.input_context = "ctx"
    fb.user_correction = "corr"
    fb.ai_reasoning = "reason"
    fb.created_at = datetime.now()
    for k, v in overrides.items():
        setattr(fb, k, v)
    return fb


class TestAdjustConfidence:
    def test_thumbs_up_and_rating5(self):
        learning, _, _ = make_learning()
        fb = make_feedback(thumbs_up_down=True, rating=5)
        assert learning.adjust_confidence_with_feedback("a1", fb, 0.5) == pytest.approx(0.65)

    def test_thumbs_down_rating1_correction(self):
        learning, _, _ = make_learning()
        fb = make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction")
        assert learning.adjust_confidence_with_feedback("a1", fb, 0.5) == pytest.approx(0.32)

    def test_rating3_noop(self):
        learning, _, _ = make_learning()
        fb = make_feedback(rating=3)
        assert learning.adjust_confidence_with_feedback("a1", fb, 0.5) == 0.5

    def test_rating2_rating4(self):
        learning, _, _ = make_learning()
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(rating=2), 0.5) == pytest.approx(0.45)
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(rating=4), 0.5) == pytest.approx(0.55)

    def test_clamping(self):
        learning, _, _ = make_learning()
        fb = make_feedback(thumbs_up_down=True, rating=5)
        assert learning.adjust_confidence_with_feedback("a1", fb, 0.99) == 1.0
        fb2 = make_feedback(thumbs_up_down=False, rating=1)
        assert learning.adjust_confidence_with_feedback("a1", fb2, 0.01) == 0.0


class TestGetLearningSignals:
    def _db_with_feedback(self, feedback_list, learning_record=None):
        db = Mock()
        fb_query = Mock()
        fb_query.filter.return_value = fb_query
        fb_query.all.return_value = feedback_list
        lr_query = Mock()
        lr_query.filter.return_value = lr_query
        lr_query.first.return_value = learning_record
        db.query.side_effect = [fb_query, lr_query]
        return db

    def test_no_feedback_no_record(self):
        db = self._db_with_feedback([], None)
        learning, _, _ = make_learning(db)
        result = learning.get_learning_signals("a1")
        assert result["total_feedback"] == 0
        assert result["learning_signals"] == []

    def test_no_feedback_with_record(self):
        record = Mock()
        record.total_feedback = 10
        record.positive_feedback = 7
        record.parameters_json = {"lr": 0.01}
        db = self._db_with_feedback([], record)
        learning, _, _ = make_learning(db)
        result = learning.get_learning_signals("a1")
        assert result["total_feedback"] == 10
        assert result["positive_ratio"] == 0.7
        assert result["parameters"] == {"lr": 0.01}

    def test_high_positive_signals(self):
        fbs = [make_feedback(thumbs_up_down=True, rating=5) for _ in range(5)]
        db = self._db_with_feedback(fbs, None)
        learning, _, _ = make_learning(db)
        result = learning.get_learning_signals("a1")
        assert result["total_feedback_in_period"] == 5
        assert result["positive_ratio_in_period"] == 1.0
        assert any(s["type"] == "strength" for s in result["learning_signals"])
        assert result["improvement_suggestions"] == []

    def test_low_positive_and_corrections(self):
        fbs = [make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction") for _ in range(5)]
        db = self._db_with_feedback(fbs, None)
        learning, _, _ = make_learning(db)
        result = learning.get_learning_signals("a1")
        assert result["positive_ratio_in_period"] == 0.0
        types = {s["type"] for s in result["learning_signals"]}
        assert "weakness" in types
        assert "pattern" in types
        assert any(s["priority"] == "high" for s in result["improvement_suggestions"])
        assert any(s["priority"] == "medium" for s in result["improvement_suggestions"])

    def test_mixed_ratings_avg(self):
        fbs = [make_feedback(rating=5), make_feedback(rating=4)]
        db = self._db_with_feedback(fbs, None)
        learning, _, _ = make_learning(db)
        result = learning.get_learning_signals("a1")
        assert any("Excellent average rating" in s["message"] for s in result["learning_signals"])

    def test_poor_ratings_avg(self):
        fbs = [make_feedback(rating=1), make_feedback(rating=2)]
        db = self._db_with_feedback(fbs, None)
        learning, _, _ = make_learning(db)
        result = learning.get_learning_signals("a1")
        assert any("Poor average rating" in s["message"] for s in result["learning_signals"])

    def test_aggregate_warning(self):
        fbs = [make_feedback(thumbs_up_down=True) for _ in range(2)]
        record = Mock()
        record.total_feedback = 20
        record.positive_feedback = 5
        record.parameters_json = {}
        db = self._db_with_feedback(fbs, record)
        learning, _, _ = make_learning(db)
        result = learning.get_learning_signals("a1")
        assert result["aggregate_data"]["aggregate_total"] == 20
        assert any(s["type"] == "warning" for s in result["learning_signals"])


class TestRecordFeedbackInWorldModel:
    @pytest.mark.asyncio
    async def test_success_outcome_with_execution(self):
        learning, _, _ = make_learning()
        fb = make_feedback(thumbs_up_down=True, rating=5, agent_execution_id="ex1")
        learning.db.query.return_value.filter.return_value.first.return_value = Mock()
        learning.world_model.record_experience = AsyncMock(return_value=True)
        assert await learning.record_feedback_in_world_model(fb) is True
        experience = learning.world_model.record_experience.call_args.args[0]
        assert experience.outcome == "Success"
        assert experience.artifacts == ["ex1"]
        assert experience.feedback_score == 1.0

    @pytest.mark.asyncio
    async def test_failure_outcome(self):
        learning, _, _ = make_learning()
        fb = make_feedback(thumbs_up_down=False, rating=1)
        learning.world_model.record_experience = AsyncMock(return_value=True)
        assert await learning.record_feedback_in_world_model(fb) is True
        experience = learning.world_model.record_experience.call_args.args[0]
        assert experience.outcome == "Failure"

    @pytest.mark.asyncio
    async def test_mixed_outcome(self):
        learning, _, _ = make_learning()
        fb = make_feedback(rating=3)
        learning.world_model.record_experience = AsyncMock(return_value=True)
        assert await learning.record_feedback_in_world_model(fb) is True
        assert learning.world_model.record_experience.call_args.args[0].outcome == "Mixed"

    @pytest.mark.asyncio
    async def test_record_failure_returns_false(self):
        learning, _, _ = make_learning()
        fb = make_feedback(thumbs_up_down=True)
        learning.world_model.record_experience = AsyncMock(return_value=False)
        assert await learning.record_feedback_in_world_model(fb) is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        learning, _, _ = make_learning()
        fb = make_feedback()
        learning.world_model.record_experience = AsyncMock(side_effect=RuntimeError("boom"))
        assert await learning.record_feedback_in_world_model(fb) is False


class TestBatchUpdateConfidence:
    def test_agent_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        learning, _, _ = make_learning(db)
        assert learning.batch_update_confidence_from_feedback("a1") is None

    def test_no_feedback_returns_confidence(self):
        db = Mock()
        agent = Mock(confidence_score=0.6)
        fb_query = Mock()
        fb_query.filter.return_value = fb_query
        fb_query.all.return_value = []
        db.query.side_effect = [Mock(filter=Mock(return_value=Mock(first=Mock(return_value=agent)))), fb_query]
        learning, _, _ = make_learning(db)
        assert learning.batch_update_confidence_from_feedback("a1") == 0.6

    def test_with_feedback(self):
        db = Mock()
        agent = Mock(confidence_score=0.5)
        fb_query = Mock()
        fb_query.filter.return_value = fb_query
        fb_query.all.return_value = [
            make_feedback(thumbs_up_down=True, rating=5, created_at=datetime.now()),
            make_feedback(thumbs_up_down=False, rating=1, created_at=datetime.now()),
        ]
        db.query.side_effect = [Mock(filter=Mock(return_value=Mock(first=Mock(return_value=agent)))), fb_query]
        learning, _, _ = make_learning(db)
        assert learning.batch_update_confidence_from_feedback("a1") == pytest.approx(0.5)

    def test_with_correction_feedback(self):
        db = Mock()
        agent = Mock(confidence_score=0.5)
        fb_query = Mock()
        fb_query.filter.return_value = fb_query
        fb_query.all.return_value = [
            make_feedback(feedback_type="correction", created_at=datetime.now()),
        ]
        db.query.side_effect = [Mock(filter=Mock(return_value=Mock(first=Mock(return_value=agent)))), fb_query]
        learning, _, _ = make_learning(db)
        assert learning.batch_update_confidence_from_feedback("a1") == pytest.approx(0.47)


class TestRecordUserCorrection:
    @pytest.mark.asyncio
    async def test_success_with_agent(self):
        db = Mock()
        agent = Mock(confidence_score=0.5)
        db.query.return_value.filter.return_value.first.return_value = agent
        learning, _, _ = make_learning(db)
        exp_id = await learning.record_user_correction(
            "a1", "t1", {"action_type": "send", "parameters": {"x": 1}},
            {"action_type": "send", "parameters": {"x": 2}}, "ctx"
        )
        assert exp_id
        db.add.assert_called()
        db.commit.assert_called()
        assert agent.confidence_score == 0.45

    @pytest.mark.asyncio
    async def test_success_no_agent(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        learning, _, _ = make_learning(db)
        exp_id = await learning.record_user_correction("a1", "t1", {}, {}, None)
        assert exp_id

    @pytest.mark.asyncio
    async def test_continuous_learning_failure_tolerated(self):
        db = Mock()
        agent = Mock(confidence_score=0.5)
        db.query.return_value.filter.return_value.first.return_value = agent
        learning, _, _ = make_learning(db)
        learning.continuous_learning.update_from_feedback = Mock(side_effect=RuntimeError("cl down"))
        exp_id = await learning.record_user_correction("a1", "t1", {"action_type": "a"}, {"action_type": "b"})
        assert exp_id

    @pytest.mark.asyncio
    async def test_exception_rolls_back(self):
        db = Mock()
        db.add.side_effect = RuntimeError("boom")
        learning, _, _ = make_learning(db)
        with pytest.raises(RuntimeError):
            await learning.record_user_correction("a1", "t1", {}, {})
        db.rollback.assert_called()

    def test_classify_correction(self):
        learning, _, _ = make_learning()
        assert learning._classify_correction("not-dict", {}) == "other_correction"
        assert learning._classify_correction({"action_type": "a"}, {"action_type": "b"}) == "action_type_change"
        assert learning._classify_correction({"action_type": "a", "parameters": [1]}, {"action_type": "a", "parameters": [2]}) == "parameter_adjustment"
        assert learning._classify_correction({"action_type": "a"}, {"action_type": "a"}) == "other_correction"


class TestRecordRejection:
    @pytest.mark.asyncio
    async def test_success(self):
        db = Mock()
        agent = Mock(confidence_score=0.5)
        db.query.return_value.filter.return_value.first.return_value = agent
        learning, _, _ = make_learning(db)
        exp_id = await learning.record_rejection("a1", "t1", "send_email", {"to": "x"}, "bad idea")
        assert exp_id
        assert agent.confidence_score == 0.4

    @pytest.mark.asyncio
    async def test_continuous_learning_failure_tolerated(self):
        db = Mock()
        agent = Mock(confidence_score=0.5)
        db.query.return_value.filter.return_value.first.return_value = agent
        learning, _, _ = make_learning(db)
        learning.continuous_learning.update_from_feedback = Mock(side_effect=RuntimeError("cl down"))
        exp_id = await learning.record_rejection("a1", "t1", "act", {"x": 1}, "no")
        assert exp_id

    @pytest.mark.asyncio
    async def test_exception_rolls_back(self):
        db = Mock()
        db.add.side_effect = RuntimeError("boom")
        learning, _, _ = make_learning(db)
        with pytest.raises(RuntimeError):
            await learning.record_rejection("a1", "t1", "act", {})
        db.rollback.assert_called()


class TestAnalyzeFailurePatterns:
    @pytest.mark.asyncio
    async def test_patterns_found(self):
        db = Mock()
        exp = Mock(task_type="send", learnings={"correction_type": "parameter_adjustment"})
        exp2 = Mock(task_type="send", learnings={"correction_type": "parameter_adjustment"})
        exp3 = Mock(task_type="send", learnings={"rejection_type": "explicit_rejection"})
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = [exp, exp2, exp3]
        db.query.return_value = q
        learning, _, _ = make_learning(db)
        patterns = await learning.analyze_failure_patterns("a1", "t1", min_occurrences=2)
        assert len(patterns) == 1
        assert patterns[0]["type"] == "parameter_adjustment"
        assert patterns[0]["count"] == 2

    @pytest.mark.asyncio
    async def test_no_patterns(self):
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = [Mock(task_type="t", learnings=None)]
        db.query.return_value = q
        learning, _, _ = make_learning(db)
        assert await learning.analyze_failure_patterns("a1", "t1", min_occurrences=3) == []

    @pytest.mark.asyncio
    async def test_exception(self):
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        learning, _, _ = make_learning(db)
        assert await learning.analyze_failure_patterns("a1", "t1") == []
