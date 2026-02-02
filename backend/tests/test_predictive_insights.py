"""
Tests for Predictive Insights Engine
Tests response time prediction, channel recommendations, and bottleneck detection.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from core.predictive_insights import (
    PredictiveInsightsEngine,
    UrgencyLevel,
    RecommendationConfidence,
    ResponseTimePrediction,
    ChannelRecommendation,
    BottleneckAlert,
    CommunicationPattern,
    get_predictive_insights_engine
)


@pytest.fixture
def insights_engine():
    """Create PredictiveInsightsEngine instance"""
    return PredictiveInsightsEngine()


@pytest.fixture
def historical_messages():
    """Create historical messages for analysis"""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    return [
        # Alice's messages (active on Slack, responds quickly)
        {
            "id": "msg1",
            "platform": "slack",
            "content": "Project update",
            "sender_name": "Alice",
            "timestamp": yesterday.isoformat(),
            "thread_id": "thread1"
        },
        {
            "id": "msg2",
            "platform": "slack",
            "content": "Thanks for update",
            "sender_name": "Alice",
            "timestamp": (yesterday + timedelta(minutes=10)).isoformat(),
            "thread_id": "thread1"
        },
        {
            "id": "msg3",
            "platform": "teams",
            "content": "Meeting question",
            "sender_name": "Alice",
            "timestamp": (yesterday + timedelta(hours=2)).isoformat(),
            "thread_id": "thread2"
        },
        {
            "id": "msg4",
            "platform": "slack",
            "content": "Urgent issue - need help ASAP",
            "sender_name": "Alice",
            "timestamp": now.isoformat(),
            "thread_id": "thread3"
        },
        {
            "id": "msg4b",
            "platform": "slack",
            "content": "Task completed",
            "sender_name": "Alice",
            "timestamp": (now + timedelta(hours=1)).isoformat(),
            "thread_id": "thread4"
        },
        # Bob's messages (slow responder, uses Gmail)
        {
            "id": "msg5",
            "platform": "gmail",
            "content": "Report attached",
            "sender_name": "Bob",
            "timestamp": two_days_ago.isoformat(),
            "thread_id": "thread4"
        },
        {
            "id": "msg6",
            "platform": "gmail",
            "content": "Thanks",
            "sender_name": "Bob",
            "timestamp": (two_days_ago + timedelta(hours=24)).isoformat(),
            "thread_id": "thread4"
        },
        {
            "id": "msg7",
            "platform": "slack",
            "content": "Quick chat",
            "sender_name": "Bob",
            "timestamp": (yesterday + timedelta(hours=4)).isoformat(),
            "thread_id": "thread5"
        },
        {
            "id": "msg7b",
            "platform": "gmail",
            "content": "Question about deadline",
            "sender_name": "Bob",
            "timestamp": (yesterday + timedelta(hours=6)).isoformat(),
            "thread_id": "thread6"
        },
        {
            "id": "msg7c",
            "platform": "gmail",
            "content": "Meeting tomorrow?",
            "sender_name": "Bob",
            "timestamp": (yesterday + timedelta(hours=8)).isoformat(),
            "thread_id": "thread7"
        },
        # Old messages for bottleneck testing
        {
            "id": "msg8",
            "platform": "slack",
            "content": "Waiting for response",
            "sender_name": "Charlie",
            "timestamp": (now - timedelta(hours=30)).isoformat(),
            "thread_id": "thread8"
        },
        {
            "id": "msg9",
            "platform": "teams",
            "content": "Urgent deadline",
            "sender_name": "Charlie",
            "timestamp": (now - timedelta(hours=50)).isoformat(),
            "thread_id": "thread9"
        }
    ]


class TestResponseTimePrediction:
    """Test response time prediction"""

    def test_predict_with_no_data(self, insights_engine):
        """Test prediction with no historical data"""
        prediction = insights_engine.predict_response_time(
            recipient="UnknownUser",
            platform="slack"
        )

        assert prediction.user_id == "UnknownUser"
        assert prediction.predicted_seconds > 0
        assert prediction.confidence == RecommendationConfidence.LOW
        assert prediction.factors["data_available"] is False

    def test_predict_with_historical_data(self, insights_engine, historical_messages):
        """Test prediction with historical data"""
        insights_engine.analyze_historical_data(historical_messages)

        prediction = insights_engine.predict_response_time(
            recipient="Alice",
            platform="slack"
        )

        assert prediction.user_id == "Alice"
        assert prediction.predicted_seconds > 0
        assert prediction.confidence in [RecommendationConfidence.MEDIUM, RecommendationConfidence.HIGH]
        assert prediction.factors["data_available"] is True

    def test_predict_by_urgency(self, insights_engine, historical_messages):
        """Test prediction with different urgency levels"""
        insights_engine.analyze_historical_data(historical_messages)

        urgent_pred = insights_engine.predict_response_time(
            recipient="Alice",
            platform="slack",
            urgency=UrgencyLevel.URGENT
        )

        low_pred = insights_engine.predict_response_time(
            recipient="Alice",
            platform="slack",
            urgency=UrgencyLevel.LOW
        )

        # Urgent messages should have shorter predicted times
        assert urgent_pred.predicted_seconds < low_pred.predicted_seconds

    def test_predict_by_time_of_day(self, insights_engine, historical_messages):
        """Test prediction at different times of day"""
        insights_engine.analyze_historical_data(historical_messages)

        morning = datetime.now(timezone.utc).replace(hour=10)
        evening = datetime.now(timezone.utc).replace(hour=22)

        morning_pred = insights_engine.predict_response_time(
            recipient="Alice",
            platform="slack",
            time_of_day=morning
        )

        evening_pred = insights_engine.predict_response_time(
            recipient="Alice",
            platform="slack",
            time_of_day=evening
        )

        # Predictions should include time factors
        assert "hour_of_day" in morning_pred.factors
        assert "hour_of_day" in evening_pred.factors


class TestChannelRecommendation:
    """Test optimal channel recommendations"""

    def test_recommend_with_no_data(self, insights_engine):
        """Test recommendation with no historical data"""
        recommendation = insights_engine.recommend_channel(
            recipient="UnknownUser"
        )

        assert recommendation.user_id == "UnknownUser"
        assert recommendation.recommended_platform == "slack"  # Default
        assert recommendation.confidence == RecommendationConfidence.LOW
        assert len(recommendation.alternatives) > 0

    def test_recommend_with_historical_data(self, insights_engine, historical_messages):
        """Test recommendation with historical data"""
        insights_engine.analyze_historical_data(historical_messages)

        recommendation = insights_engine.recommend_channel(
            recipient="Alice"
        )

        assert recommendation.user_id == "Alice"
        assert recommendation.recommended_platform in ["slack", "teams", "gmail", "outlook"]
        assert recommendation.confidence in [RecommendationConfidence.MEDIUM, RecommendationConfidence.HIGH]
        assert recommendation.expected_response_time is not None

    def test_recommend_for_urgent_message(self, insights_engine, historical_messages):
        """Test recommendation for urgent messages"""
        insights_engine.analyze_historical_data(historical_messages)

        recommendation = insights_engine.recommend_channel(
            recipient="Bob",
            urgency=UrgencyLevel.URGENT
        )

        # Should prefer real-time platforms for urgent
        assert recommendation.recommended_platform in ["slack", "teams"]
        assert "urgent" in recommendation.reason.lower() or "real-time" in recommendation.reason.lower()

    def test_recommend_includes_alternatives(self, insights_engine, historical_messages):
        """Test that recommendations include alternatives"""
        insights_engine.analyze_historical_data(historical_messages)

        recommendation = insights_engine.recommend_channel(
            recipient="Alice"
        )

        assert len(recommendation.alternatives) > 0
        assert recommendation.recommended_platform not in recommendation.alternatives


class TestBottleneckDetection:
    """Test bottleneck detection"""

    def test_detect_no_bottlenecks(self, insights_engine):
        """Test with no recent threads"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Recent message",
                "sender_name": "User",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            }
        ]

        insights_engine.analyze_historical_data(messages)
        bottlenecks = insights_engine.detect_bottlenecks(threshold_hours=24)

        assert len(bottlenecks) == 0

    def test_detect_bottlenecks(self, insights_engine, historical_messages):
        """Test bottleneck detection"""
        insights_engine.analyze_historical_data(historical_messages)
        bottlenecks = insights_engine.detect_bottlenecks(threshold_hours=24)

        # Should detect threads without recent responses
        assert len(bottlenecks) > 0

        bottleneck = bottlenecks[0]
        assert bottleneck.thread_id in ["thread8", "thread9"]
        assert bottleneck.severity in [UrgencyLevel.MEDIUM, UrgencyLevel.HIGH, UrgencyLevel.URGENT]
        assert bottleneck.wait_time_seconds >= 24 * 3600
        assert bottleneck.suggested_action != ""

    def test_bottleneck_severity_levels(self, insights_engine):
        """Test different severity levels"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Old message",
                "sender_name": "User",
                "timestamp": (now - timedelta(hours=26)).isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Very old message",
                "sender_name": "User",
                "timestamp": (now - timedelta(hours=80)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        insights_engine.analyze_historical_data(messages)
        bottlenecks = insights_engine.detect_bottlenecks(threshold_hours=24)

        assert len(bottlenecks) == 2

        # Check severity based on wait time
        severities = [b.severity for b in bottlenecks]
        assert UrgencyLevel.HIGH in severities or UrgencyLevel.URGENT in severities

    def test_bottleneck_includes_affected_users(self, insights_engine, historical_messages):
        """Test that bottlenecks track affected users"""
        insights_engine.analyze_historical_data(historical_messages)
        bottlenecks = insights_engine.detect_bottlenecks(threshold_hours=24)

        if bottlenecks:
            bottleneck = bottlenecks[0]
            assert len(bottleneck.affected_users) > 0
            assert "Charlie" in bottleneck.affected_users


class TestUserPatterns:
    """Test user pattern analysis"""

    def test_analyze_user_patterns(self, insights_engine, historical_messages):
        """Test pattern extraction from messages"""
        insights_engine.analyze_historical_data(historical_messages)

        assert len(insights_engine.user_patterns) > 0

        # Alice should have a pattern
        alice_pattern = insights_engine.get_user_pattern("Alice")
        assert alice_pattern is not None
        assert alice_pattern.user_id == "Alice"
        assert alice_pattern.most_active_platform in ["slack", "teams"]
        assert len(alice_pattern.most_active_hours) > 0

    def test_pattern_response_probabilities(self, insights_engine, historical_messages):
        """Test hourly response probabilities"""
        insights_engine.analyze_historical_data(historical_messages)

        pattern = insights_engine.get_user_pattern("Alice")
        assert pattern is not None

        # Check probabilities exist
        assert len(pattern.response_probability_by_hour) > 0

        # Probabilities should be between 0 and 1
        for prob in pattern.response_probability_by_hour.values():
            assert 0 <= prob <= 1

    def test_pattern_preferred_types(self, insights_engine, historical_messages):
        """Test preferred message types"""
        insights_engine.analyze_historical_data(historical_messages)

        pattern = insights_engine.get_user_pattern("Alice")
        assert pattern is not None

        # Should have some preferred types
        assert len(pattern.preferred_message_types) > 0

        # Types should be from our predefined list
        valid_types = ["urgent", "file_share", "meeting", "question", "task", "general"]
        for msg_type in pattern.preferred_message_types:
            assert msg_type in valid_types


class TestInsightsSummary:
    """Test insights summary"""

    def test_get_insights_summary(self, insights_engine, historical_messages):
        """Test getting summary of insights"""
        insights_engine.analyze_historical_data(historical_messages)
        summary = insights_engine.get_insights_summary()

        assert "users_analyzed" in summary
        assert "threads_tracked" in summary
        assert "bottlenecks_detected" in summary
        assert "active_patterns" in summary
        assert "avg_response_time_all_users" in summary

        assert summary["users_analyzed"] > 0
        assert summary["threads_tracked"] > 0

    def test_empty_summary(self, insights_engine):
        """Test summary with no data"""
        summary = insights_engine.get_insights_summary()

        assert summary["users_analyzed"] == 0
        assert summary["threads_tracked"] == 0


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_messages(self, insights_engine):
        """Test with empty message list"""
        insights_engine.analyze_historical_data([])

        summary = insights_engine.get_insights_summary()
        assert summary["users_analyzed"] == 0

    def test_messages_without_sender(self, insights_engine):
        """Test messages without sender information"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Orphan message",
                "timestamp": now.isoformat(),
                # No sender
            }
        ]

        insights_engine.analyze_historical_data(messages)

        # Should handle gracefully
        summary = insights_engine.get_insights_summary()
        assert summary["users_analyzed"] >= 0

    def test_invalid_timestamps(self, insights_engine):
        """Test handling of invalid timestamps"""
        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Message",
                "sender_name": "User",
                "timestamp": "invalid-timestamp",
                "thread_id": "thread1"
            }
        ]

        # Should not crash
        insights_engine.analyze_historical_data(messages)

        summary = insights_engine.get_insights_summary()
        assert isinstance(summary, dict)

    def test_insufficient_data_points(self, insights_engine):
        """Test with insufficient data for patterns"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Only message",
                "sender_name": "User",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            }
        ]

        insights_engine.analyze_historical_data(messages)

        # Should not create patterns with insufficient data
        pattern = insights_engine.get_user_pattern("User")
        assert pattern is None  # Need at least min_data_points messages


class TestConfidenceLevels:
    """Test confidence level assignment"""

    def test_low_confidence_no_data(self, insights_engine):
        """Test low confidence with no data"""
        prediction = insights_engine.predict_response_time(
            recipient="Unknown",
            platform="slack"
        )

        assert prediction.confidence == RecommendationConfidence.LOW

    def test_confidence_increases_with_data(self, insights_engine):
        """Test that confidence increases with more data"""
        now = datetime.now(timezone.utc)

        # Create many messages
        messages = []
        for i in range(50):
            messages.append({
                "id": f"msg{i}",
                "platform": "slack",
                "content": "Message",
                "sender_name": "ActiveUser",
                "timestamp": (now - timedelta(hours=i)).isoformat(),
                "thread_id": f"thread{i%10}"
            })

        insights_engine.analyze_historical_data(messages)

        prediction = insights_engine.predict_response_time(
            recipient="ActiveUser",
            platform="slack"
        )

        # Should have higher confidence with more data
        assert prediction.confidence in [RecommendationConfidence.MEDIUM, RecommendationConfidence.HIGH]


class TestSingleton:
    """Test singleton instance"""

    def test_get_singleton_engine(self):
        """Test getting singleton insights engine"""
        engine1 = get_predictive_insights_engine()
        engine2 = get_predictive_insights_engine()

        assert engine1 is engine2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
