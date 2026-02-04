"""
Tests for Message Analytics Engine
Tests sentiment analysis, response times, activity detection, and cross-platform analytics.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest

from core.message_analytics_engine import (
    ActivityMetrics,
    MessageAnalyticsEngine,
    MessageStats,
    ResponseTimeMetrics,
    SentimentLevel,
    ThreadParticipation,
)


@pytest.fixture
def analytics_engine():
    """Create MessageAnalyticsEngine instance"""
    return MessageAnalyticsEngine()


@pytest.fixture
def sample_messages():
    """Create sample messages for testing"""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    return [
        {
            "id": "msg_001",
            "platform": "slack",
            "platform_message_id": "slack_001",
            "content": "This is great! Thank you for your help! 👍",
            "sender_name": "Alice",
            "timestamp": now.isoformat(),
            "thread_id": "thread_001",
            "channel_id": "C001",
            "has_attachments": False,
            "mentions": ["U123"],
            "urls": ["https://example.com"],
            "tags": ["slack"]
        },
        {
            "id": "msg_002",
            "platform": "teams",
            "platform_message_id": "teams_001",
            "content": "Having some issues with the system, can you help?",
            "sender_name": "Bob",
            "timestamp": (now - timedelta(seconds=30)).isoformat(),
            "thread_id": "thread_001",
            "channel_id": "19:chat@thread.v2",
            "has_attachments": True,
            "mentions": [],
            "urls": [],
            "tags": ["teams"]
        },
        {
            "id": "msg_003",
            "platform": "slack",
            "platform_message_id": "slack_002",
            "content": "I'm sorry about the mistake, let me fix it.",
            "sender_name": "Alice",
            "timestamp": (now - timedelta(seconds=60)).isoformat(),
            "thread_id": "thread_001",
            "channel_id": "C001",
            "has_attachments": False,
            "mentions": [],
            "urls": [],
            "tags": ["slack"]
        },
        {
            "id": "msg_004",
            "platform": "gmail",
            "platform_message_id": "gmail_001",
            "content": "The project is going well, excellent work everyone!",
            "sender_name": "Charlie",
            "timestamp": yesterday.isoformat(),
            "thread_id": "thread_002",
            "has_attachments": False,
            "mentions": [],
            "urls": [],
            "tags": ["gmail"]
        },
        {
            "id": "msg_005",
            "platform": "teams",
            "platform_message_id": "teams_002",
            "content": "This is terrible, nothing works!",
            "sender_name": "Diana",
            "timestamp": two_days_ago.isoformat(),
            "thread_id": "thread_003",
            "channel_id": "19:chat2@thread.v2",
            "has_attachments": False,
            "mentions": [],
            "urls": [],
            "tags": ["teams"]
        },
        {
            "id": "msg_006",
            "platform": "slack",
            "platform_message_id": "slack_003",
            "content": "Just a neutral update.",
            "sender_name": "Eve",
            "timestamp": yesterday.isoformat(),
            "thread_id": "thread_004",
            "channel_id": "C002",
            "has_attachments": False,
            "mentions": [],
            "urls": [],
            "tags": ["slack"]
        }
    ]


class TestSentimentAnalysis:
    """Test sentiment analysis"""

    def test_positive_sentiment(self, analytics_engine):
        """Test detecting positive sentiment"""
        assert analytics_engine.analyze_sentiment("This is great!") == SentimentLevel.POSITIVE
        assert analytics_engine.analyze_sentiment("Thank you so much! 🎉") == SentimentLevel.POSITIVE
        assert analytics_engine.analyze_sentiment("Awesome work!") == SentimentLevel.POSITIVE

    def test_negative_sentiment(self, analytics_engine):
        """Test detecting negative sentiment"""
        assert analytics_engine.analyze_sentiment("This is terrible") == SentimentLevel.NEGATIVE
        assert analytics_engine.analyze_sentiment("I'm frustrated with this bug") == SentimentLevel.NEGATIVE
        assert analytics_engine.analyze_sentiment("Nothing works!") == SentimentLevel.NEGATIVE

    def test_neutral_sentiment(self, analytics_engine):
        """Test detecting neutral sentiment"""
        assert analytics_engine.analyze_sentiment("Just an update") == SentimentLevel.NEUTRAL
        assert analytics_engine.analyze_sentiment("Meeting at 3pm") == SentimentLevel.NEUTRAL
        assert analytics_engine.analyze_sentiment("") == SentimentLevel.NEUTRAL

    def test_mixed_sentiment(self, analytics_engine):
        """Test text with both positive and negative keywords"""
        # More positive = positive (2 positive vs 1 negative)
        assert analytics_engine.analyze_sentiment("Great awesome but has a small issue") == SentimentLevel.POSITIVE
        # More negative = negative (2 negative vs 1 positive)
        assert analytics_engine.analyze_sentiment("Good but terrible awful experience") == SentimentLevel.NEGATIVE
        # Equal = neutral (1 positive vs 1 negative)
        assert analytics_engine.analyze_sentiment("Great and bad") == SentimentLevel.NEUTRAL


class TestMessageStats:
    """Test message statistics calculation"""

    def test_calculate_message_stats(self, analytics_engine, sample_messages):
        """Test basic message statistics"""
        stats = analytics_engine.calculate_message_stats(sample_messages)

        assert stats.total_messages == 6
        assert stats.total_words > 0
        assert stats.total_characters > 0
        assert stats.with_attachments == 1
        assert stats.with_mentions == 1
        assert stats.with_urls == 1

    def test_sentiment_distribution(self, analytics_engine, sample_messages):
        """Test sentiment distribution"""
        stats = analytics_engine.calculate_message_stats(sample_messages)

        # Should have all three sentiment types
        assert "positive" in stats.sentiment_distribution
        assert "negative" in stats.sentiment_distribution
        assert "neutral" in stats.sentiment_distribution

        # Should have at least one positive message
        assert stats.sentiment_distribution["positive"] >= 1

    def test_empty_messages(self, analytics_engine):
        """Test with empty message list"""
        stats = analytics_engine.calculate_message_stats([])

        assert stats.total_messages == 0
        assert stats.total_words == 0
        assert stats.total_characters == 0


class TestResponseTimeMetrics:
    """Test response time calculation"""

    def test_calculate_response_times_single_thread(self, analytics_engine):
        """Test response times in a single thread"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "First message",
                "sender": "Alice",
                "timestamp": (now - timedelta(minutes=10)).isoformat(),
                "thread_id": "thread_001"
            },
            {
                "id": "msg2",
                "platform": "slack",
                "content": "Response after 2 minutes",
                "sender": "Bob",
                "timestamp": (now - timedelta(minutes=8)).isoformat(),
                "thread_id": "thread_001"
            },
            {
                "id": "msg3",
                "platform": "slack",
                "content": "Another response after 1 minute",
                "sender": "Alice",
                "timestamp": (now - timedelta(minutes=7)).isoformat(),
                "thread_id": "thread_001"
            }
        ]

        metrics = analytics_engine.calculate_response_times(messages)

        assert metrics.total_responses == 2
        assert metrics.avg_response_time == 90.0  # (120 + 60) / 2
        assert metrics.median_response_time > 0
        # Response times are sorted for percentile calculation
        assert metrics.response_times == [60.0, 120.0]

    def test_response_time_filters(self, analytics_engine):
        """Test that response times filter correctly"""
        now = datetime.now(timezone.utc)

        # Create messages such that:
        # - One response is < 30s (too fast)
        # - One response is > 24h (too slow)
        messages = [
            {
                "id": "msg1",
                "content": "First",
                "timestamp": (now - timedelta(seconds=25)).isoformat(),
                "thread_id": "thread_001"
            },
            {
                "id": "msg2",
                "content": "Too fast",
                "timestamp": (now - timedelta(seconds=5)).isoformat(),
                "thread_id": "thread_001"
            },
            {
                "id": "msg3",
                "content": "Too slow",
                "timestamp": (now - timedelta(days=1, seconds=30)).isoformat(),
                "thread_id": "thread_001"
            }
        ]

        metrics = analytics_engine.calculate_response_times(messages)

        # Should filter out too fast (<30s) and too slow (>24h)
        # msg3->msg1: ~86400+30-25 = >86405s (too slow)
        # msg1->msg2: 20s (too fast)
        assert metrics.total_responses == 0

    def test_empty_response_times(self, analytics_engine):
        """Test with no threaded conversations"""
        messages = [
            {
                "id": "msg1",
                "content": "Single message",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        metrics = analytics_engine.calculate_response_times(messages)

        assert metrics.total_responses == 0


class TestThreadParticipation:
    """Test thread participation analysis"""

    def test_analyze_thread_participation(self, analytics_engine, sample_messages):
        """Test thread participation metrics"""
        participation = analytics_engine.analyze_thread_participation(sample_messages)

        assert len(participation) == 4  # 4 unique threads

        # Check thread_001 (3 messages from Alice, Bob)
        thread_001 = participation["thread_001"]
        assert thread_001.total_messages == 3
        assert "Alice" in thread_001.participants
        assert "Bob" in thread_001.participants
        assert thread_001.participants["Alice"] == 2
        assert thread_001.participants["Bob"] == 1

    def test_most_active_participant(self, analytics_engine, sample_messages):
        """Test finding most active participant"""
        participation = analytics_engine.analyze_thread_participation(sample_messages)

        thread_001 = participation["thread_001"]
        assert thread_001.most_active_participant == "Alice"

    def test_average_messages_per_user(self, analytics_engine, sample_messages):
        """Test average messages per user calculation"""
        participation = analytics_engine.analyze_thread_participation(sample_messages)

        thread_001 = participation["thread_001"]
        # Alice: 2, Bob: 1, average: 1.5
        assert thread_001.average_messages_per_user == 1.5


class TestActivityMetrics:
    """Test peak activity detection"""

    def test_detect_peak_activity_daily(self, analytics_engine):
        """Test daily peak activity detection"""
        messages = [
            {
                "id": "msg1",
                "content": "Message 1",
                "timestamp": datetime(2024, 2, 1, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
                "channel_id": "C001"
            },
            {
                "id": "msg2",
                "content": "Message 2",
                "timestamp": datetime(2024, 2, 1, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
                "channel_id": "C001"
            },
            {
                "id": "msg3",
                "content": "Message 3",
                "timestamp": datetime(2024, 2, 1, 15, 0, 0, tzinfo=timezone.utc).isoformat(),
                "channel_id": "C001"
            }
        ]

        activity = analytics_engine.detect_peak_activity(messages, period="daily")

        assert activity.messages_per_day.get("2024-02-01") == 3
        assert activity.messages_per_channel.get("C001") == 3

    def test_peak_days(self, analytics_engine):
        """Test peak days identification"""
        messages = [
            {
                "id": "msg1",
                "content": "Message",
                "timestamp": datetime(2024, 2, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat()
            },
            {
                "id": "msg2",
                "content": "Message",
                "timestamp": datetime(2024, 2, 1, 11, 0, 0, tzinfo=timezone.utc).isoformat()
            },
            {
                "id": "msg3",
                "content": "Message",
                "timestamp": datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc).isoformat()
            }
        ]

        activity = analytics_engine.detect_peak_activity(messages, period="daily")

        assert len(activity.peak_days) > 0
        # 2024-02-01 should be the peak day with 2 messages
        assert activity.peak_days[0][1] == 2

    def test_empty_activity(self, analytics_engine):
        """Test with no messages"""
        activity = analytics_engine.detect_peak_activity([], period="daily")

        assert activity.messages_per_day == {}
        assert activity.peak_days == []


class TestCrossPlatformAnalytics:
    """Test cross-platform analytics"""

    def test_cross_platform_stats(self, analytics_engine, sample_messages):
        """Test comparing activity across platforms"""
        analytics = analytics_engine.get_cross_platform_analytics(sample_messages)

        assert "platforms" in analytics
        assert "total_messages" in analytics
        assert analytics["total_messages"] == 6

        # Check platform counts
        assert "slack" in analytics["platforms"]
        assert "teams" in analytics["platforms"]
        assert "gmail" in analytics["platforms"]

        # Slack should have 3 messages
        assert analytics["platforms"]["slack"]["message_count"] == 3
        # Teams should have 2 messages
        assert analytics["platforms"]["teams"]["message_count"] == 2

    def test_sentiment_by_platform(self, analytics_engine, sample_messages):
        """Test sentiment distribution by platform"""
        analytics = analytics_engine.get_cross_platform_analytics(sample_messages)

        # Gmail message has positive sentiment ("excellent")
        gmail_stats = analytics["platforms"]["gmail"]
        assert gmail_stats["sentiment"]["positive"] >= 1

        # Teams message has negative sentiment ("terrible")
        teams_stats = analytics["platforms"]["teams"]
        assert teams_stats["sentiment"]["negative"] >= 1

    def test_most_active_platform(self, analytics_engine, sample_messages):
        """Test identifying most active platform"""
        analytics = analytics_engine.get_cross_platform_analytics(sample_messages)

        # Slack has most messages (3)
        assert analytics["most_active_platform"] == "slack"
        assert analytics["platforms"]["slack"]["message_count"] == 3


class TestAnalyticsSummary:
    """Test comprehensive analytics summary"""

    def test_get_analytics_summary_24h(self, analytics_engine, sample_messages):
        """Test 24-hour analytics summary"""
        summary = analytics_engine.get_analytics_summary(sample_messages, "24h")

        assert "time_window" in summary
        assert summary["time_window"] == "24h"
        assert "message_stats" in summary
        assert "response_times" in summary
        assert "thread_participation" in summary
        assert "activity_peaks" in summary
        assert "cross_platform" in summary

    def test_get_analytics_summary_all_time(self, analytics_engine, sample_messages):
        """Test all-time analytics summary"""
        summary = analytics_engine.get_analytics_summary(sample_messages, "all")

        assert summary["time_window"] == "all"
        assert summary["message_stats"]["total_messages"] == 6

    def test_time_window_filtering(self, analytics_engine):
        """Test that time window filters correctly"""
        now = datetime.now(timezone.utc)
        old_message = {
            "id": "old_msg",
            "content": "Old message",
            "timestamp": (now - timedelta(days=10)).isoformat()
        }
        new_message = {
            "id": "new_msg",
            "content": "New message",
            "timestamp": now.isoformat()
        }

        # 24h window should only include new message
        summary_24h = analytics_engine.get_analytics_summary([old_message, new_message], "24h")
        assert summary_24h["message_stats"]["total_messages"] == 1

        # All time should include both
        summary_all = analytics_engine.get_analytics_summary([old_message, new_message], "all")
        assert summary_all["message_stats"]["total_messages"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
