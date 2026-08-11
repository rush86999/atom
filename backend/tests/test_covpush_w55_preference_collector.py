"""Coverage wave 55 — core/llm/routing/preference_collector.py (66% → 90%+).

record_feedback (missing decision, success), A/B assignment + learning-router
gate, training dataset generation (workspace filter, age filter, feedback
match, quality filter, weight), prompt feature extraction (code/numbers/word
length), token buckets, example weights (explicit/rejected/extreme), stats,
factory.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from core.llm.routing.preference_collector import (
    FeedbackConfig,
    FeedbackSource,
    FeedbackType,
    PreferenceDataCollector,
    RoutingOutcome,
    get_preference_collector,
)


@pytest.fixture
def collector():
    return PreferenceDataCollector(FeedbackConfig())


def _decide(collector, ws="ws1", tokens=100, task="chat", prompt="hello world", **kw):
    return collector.record_routing_decision(
        workspace_id=ws, tenant_id="t1", estimated_tokens=tokens,
        task_type=task, prompt=prompt, chosen_model="m1",
        chosen_provider="p1", chosen_tier="standard", **kw)


class TestRecordFeedback:
    def test_unknown_decision_returns_empty(self, collector):
        assert collector.record_feedback("nope", RoutingOutcome.SUCCESS) == ""

    def test_record_success(self, collector):
        did = _decide(collector)
        fid = collector.record_feedback(
            did, RoutingOutcome.SUCCESS, quality_score=0.9,
            preferred_model="m2", preferred_provider="p2",
            feedback_type=FeedbackType.EXPLICIT)
        assert fid
        assert collector.feedback_records[fid].decision_id == did


class TestAbTesting:
    def test_assign_group_consistency(self, collector):
        g1 = collector.assign_ab_test_group("ws1")
        assert g1 in ("learning", "control")
        assert collector.assign_ab_test_group("ws1") == g1

    def test_gate_disabled(self, collector):
        c = PreferenceDataCollector(FeedbackConfig(enable_ab_testing=False))
        assert c.should_use_learning_router("ws1") is False

    def test_gate_enabled_learning_group(self, collector):
        c = PreferenceDataCollector(FeedbackConfig(enable_ab_testing=True))
        with patch.object(c, "assign_ab_test_group", return_value="learning"):
            assert c.should_use_learning_router("ws1") is True
        with patch.object(c, "assign_ab_test_group", return_value="control"):
            assert c.should_use_learning_router("ws1") is False


class TestTrainingDataset:
    def test_generates_examples_with_filters(self, collector):
        did = _decide(collector, tokens=300, task="code", prompt="```python\ndef f():\n    return 42\n```")
        collector.record_feedback(did, RoutingOutcome.SUCCESS, quality_score=0.9)
        examples = collector.generate_training_dataset("ws1")
        assert len(examples) == 1
        ex = examples[0]
        assert ex.user_satisfaction == 0.9
        assert ex.was_successful is True
        assert ex.chosen_model == "m1"
        assert ex.prompt_features["token_bucket"] == 1
        assert ex.prompt_features["has_code"] == 1.0
        assert ex.prompt_features["has_numbers"] == 1.0

    def test_workspace_and_age_filters(self, collector):
        did = _decide(collector, ws="ws1")
        collector.record_feedback(did, RoutingOutcome.SUCCESS, quality_score=0.8)
        # other workspace excluded
        assert collector.generate_training_dataset("ws2") == []
        # stale decision excluded
        decision = collector.decisions[did]
        decision.timestamp = datetime.now() - timedelta(days=200)
        assert collector.generate_training_dataset("ws1") == []

    def test_no_feedback_and_quality_filter(self, collector):
        _decide(collector)
        assert collector.generate_training_dataset("ws1") == []
        did = _decide(collector)
        collector.record_feedback(did, RoutingOutcome.REJECTED, quality_score=0.1)
        assert collector.generate_training_dataset("ws1", min_quality=0.3) == []

    def test_weight_calculation(self, collector):
        did = _decide(collector)
        fid = collector.record_feedback(
            did, RoutingOutcome.REJECTED, quality_score=0.1,
            feedback_type=FeedbackType.EXPLICIT)
        fb = collector.feedback_records[fid]
        assert collector._calculate_example_weight(fb) == pytest.approx(2.0 * 1.5 * 1.3)


class TestFeatureExtraction:
    def test_features(self, collector):
        from core.llm.routing.preference_collector import RoutingDecision
        decision = RoutingDecision(
            decision_id="d1", workspace_id="ws1", tenant_id="t1",
            estimated_tokens=6000, task_type="analysis", prompt_prefix="text 123",
            chosen_model="m", chosen_provider="p", chosen_tier="t",
            confidence=0.9, timestamp=datetime.now(timezone.utc))
        features = collector._extract_prompt_features(decision)
        assert features["log_tokens"] > 0
        assert features["token_bucket"] == 4  # >= 5000
        assert features["task_analysis"] == 1.0
        assert features["has_numbers"] == 1.0

    def test_token_buckets(self, collector):
        assert collector._get_token_bucket(50) == 0
        assert collector._get_token_bucket(300) == 1
        assert collector._get_token_bucket(1000) == 2
        assert collector._get_token_bucket(3000) == 3
        assert collector._get_token_bucket(9000) == 4


class TestStatsAndFactory:
    def test_stats_with_and_without_feedback(self, collector):
        stats = collector.get_collection_stats("ws1")
        assert stats["total_decisions"] == 0
        assert stats["feedback_coverage"] == 0
        did = _decide(collector)
        collector.record_feedback(did, RoutingOutcome.SUCCESS, quality_score=0.9)
        stats = collector.get_collection_stats("ws1")
        assert stats["total_feedback"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["avg_quality_score"] == 0.9
        assert stats["ready_for_training"] is False  # below min_samples

    def test_stats_preferred_models(self, collector):
        did = _decide(collector)
        collector.record_feedback(did, RoutingOutcome.SUCCESS,
                                  preferred_model="m2")
        stats = collector.get_collection_stats("ws1")
        assert stats["preferred_models"] == ["m2"]

    def test_factory(self):
        c = get_preference_collector()
        assert isinstance(c, PreferenceDataCollector)
