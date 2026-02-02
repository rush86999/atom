"""
Tests for Cross-Platform Correlation Engine
Tests conversation linking across Slack, Teams, Gmail, and Outlook.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from core.cross_platform_correlation import (
    CrossPlatformCorrelationEngine,
    CorrelationStrength,
    LinkedConversation,
    CrossPlatformLink,
    get_cross_platform_correlation_engine
)


@pytest.fixture
def correlation_engine():
    """Create CrossPlatformCorrelationEngine instance"""
    return CrossPlatformCorrelationEngine()


@pytest.fixture
def sample_cross_platform_messages():
    """Create sample messages from multiple platforms"""
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    two_hours_ago = now - timedelta(hours=2)

    return [
        # Slack thread about "project deadline"
        {
            "id": "slack_001",
            "platform": "slack",
            "content": "Project deadline is approaching, need review",
            "sender_name": "Alice",
            "sender_email": "alice@company.com",
            "timestamp": two_hours_ago.isoformat(),
            "thread_id": "thread_slack_001",
            "channel_id": "C001",
            "mentions": ["bob"]
        },
        {
            "id": "slack_002",
            "platform": "slack",
            "content": "I'll handle the review",
            "sender_name": "Bob",
            "sender_email": "bob@company.com",
            "timestamp": (two_hours_ago + timedelta(minutes=30)).isoformat(),
            "thread_id": "thread_slack_001"
        },
        # Teams thread with same participants, same topic
        {
            "id": "teams_001",
            "platform": "teams",
            "content": "Let's discuss the project deadline",
            "sender_name": "Alice",
            "sender_email": "alice@company.com",
            "timestamp": one_hour_ago.isoformat(),
            "thread_id": "thread_teams_001",
            "channel_id": "19:chat@thread.v2"
        },
        {
            "id": "teams_002",
            "platform": "teams",
            "content": "I'll do the review",
            "sender_name": "Bob",
            "sender_email": "bob@company.com",
            "timestamp": (one_hour_ago + timedelta(minutes=20)).isoformat(),
            "thread_id": "thread_teams_001"
        },
        # Gmail thread about different topic
        {
            "id": "gmail_001",
            "platform": "gmail",
            "content": "Meeting agenda for tomorrow",
            "sender_name": "Charlie",
            "sender_email": "charlie@company.com",
            "timestamp": now.isoformat(),
            "thread_id": "thread_gmail_001"
        },
        # Unrelated Slack message
        {
            "id": "slack_003",
            "platform": "slack",
            "content": "Lunch at noon?",
            "sender_name": "Diana",
            "sender_email": "diana@company.com",
            "timestamp": now.isoformat(),
            "thread_id": "thread_slack_002"
        }
    ]


class TestParticipantCorrelation:
    """Test participant-based correlation"""

    def test_correlate_by_shared_participants(self, correlation_engine, sample_cross_platform_messages):
        """Test linking threads with same participants"""
        conversations = correlation_engine.correlate_conversations(sample_cross_platform_messages)

        # Should link Slack and Teams threads (Alice and Bob in both)
        assert len(conversations) > 0

        # Find conversation with both platforms
        multi_platform = [c for c in conversations if len(c.platforms) > 1]
        assert len(multi_platform) > 0

        conv = multi_platform[0]
        assert "slack" in conv.platforms
        assert "teams" in conv.platforms
        assert "Alice" in conv.participants
        assert "Bob" in conv.participants

    def test_correlate_by_email_matching(self, correlation_engine):
        """Test linking threads via email addresses"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Hello",
                "sender_name": "Alice Smith",
                "sender_email": "alice@company.com",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Hi there",
                "sender_name": "alice@company.com",  # Email as name
                "sender_email": "alice@company.com",
                "timestamp": (now + timedelta(minutes=5)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        assert len(conversations) > 0
        conv = conversations[0]
        assert "slack" in conv.platforms
        assert "teams" in conv.platforms


class TestTemporalCorrelation:
    """Test temporal correlation"""

    def test_correlate_by_time_proximity(self, correlation_engine):
        """Test linking threads based on overlapping time periods"""
        now = datetime.now(timezone.utc)
        same_time = now - timedelta(hours=1)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Discussion",
                "sender_name": "User1",
                "timestamp": same_time.isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Chat",
                "sender_name": "User2",
                "timestamp": (same_time + timedelta(minutes=30)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        # Should find temporal correlation
        assert len(conversations) > 0


class TestContentCorrelation:
    """Test content-based correlation"""

    def test_correlate_by_keywords(self, correlation_engine):
        """Test linking threads with similar content"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Project deadline is urgent",
                "sender_name": "User1",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Deadline approaching for project",
                "sender_name": "User2",
                "timestamp": (now + timedelta(hours=1)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        # Should find content correlation with "deadline" and "project"
        assert len(conversations) > 0


class TestCrossReferences:
    """Test cross-reference correlation"""

    def test_detect_platform_references(self, correlation_engine):
        """Test detecting references to other platforms"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Let's continue this discussion in Teams",
                "sender_name": "User1",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Continuing from Slack",
                "sender_name": "User1",
                "timestamp": (now + timedelta(minutes=10)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        # Should detect cross-reference
        assert len(conversations) > 0


class TestUnifiedTimeline:
    """Test unified conversation timeline"""

    def test_build_unified_timeline(self, correlation_engine, sample_cross_platform_messages):
        """Test merging messages from multiple platforms"""
        conversations = correlation_engine.correlate_conversations(sample_cross_platform_messages)

        # Find multi-platform conversation
        multi_platform = [c for c in conversations if len(c.platforms) > 1]
        if multi_platform:
            conv = multi_platform[0]

            # Get unified timeline
            timeline = correlation_engine.get_unified_timeline(conv.conversation_id)

            assert timeline is not None
            assert len(timeline) > 0

            # Check messages are sorted by timestamp
            timestamps = [
                correlation_engine._parse_timestamp(m.get("timestamp"))
                for m in timeline
            ]
            assert timestamps == sorted(timestamps)

            # Check platform attribution
            has_source = any("_correlation_source" in m for m in timeline)
            assert has_source

    def test_get_unified_timeline_by_id(self, correlation_engine):
        """Test retrieving timeline by conversation ID"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Message 1",
                "sender_name": "Alice",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Message 2",
                "sender_name": "Alice",
                "timestamp": (now + timedelta(minutes=5)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        if conversations:
            conv_id = conversations[0].conversation_id
            timeline = correlation_engine.get_unified_timeline(conv_id)

            assert timeline is not None
            assert len(timeline) == 2


class TestCrossPlatformLinks:
    """Test cross-platform link metadata"""

    def test_link_metadata(self, correlation_engine, sample_cross_platform_messages):
        """Test cross-platform link creation"""
        correlation_engine.correlate_conversations(sample_cross_platform_messages)

        # Check that links were created
        assert len(correlation_engine.cross_platform_links) > 0

        link = correlation_engine.cross_platform_links[0]
        assert link.source_platform != link.target_platform
        assert link.strength in CorrelationStrength
        assert link.reason != ""
        assert isinstance(link.shared_participants, set)

    def test_temporal_distance_in_links(self, correlation_engine):
        """Test temporal distance calculation in links"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "First",
                "sender_name": "User1",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Second",
                "sender_name": "User2",
                "timestamp": (now + timedelta(minutes=30)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        correlation_engine.correlate_conversations(messages)

        # Find temporal link
        temporal_links = [
            link for link in correlation_engine.cross_platform_links
            if link.temporal_distance is not None
        ]

        if temporal_links:
            link = temporal_links[0]
            assert link.temporal_distance >= 0
            assert link.temporal_distance < 3600  # Less than 1 hour


class TestCorrelationStrength:
    """Test correlation strength classification"""

    def test_strong_correlation_multiple_participants(self, correlation_engine):
        """Test strong correlation with multiple shared participants"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Discussion",
                "sender_name": "Alice",
                "timestamp": now.isoformat(),
                "thread_id": "thread1",
                "mentions": ["Bob", "Charlie"]
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Chat",
                "sender_name": "Bob",
                "timestamp": (now + timedelta(minutes=5)).isoformat(),
                "thread_id": "thread2",
                "mentions": ["Alice", "Charlie"]
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        if conversations:
            # Should have at least moderate correlation
            conv = conversations[0]
            assert conv.correlation_strength in [CorrelationStrength.MODERATE, CorrelationStrength.STRONG]

    def test_weak_correlation_time_only(self, correlation_engine):
        """Test weak correlation based only on time"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Random chat",
                "sender_name": "User1",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Different topic",
                "sender_name": "User2",
                "timestamp": (now + timedelta(minutes=15)).isoformat(),
                "thread_id": "thread2"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        if conversations:
            conv = conversations[0]
            # Time-only correlation with no other factors should be weak or moderate
            assert conv.correlation_strength in [CorrelationStrength.WEAK, CorrelationStrength.MODERATE]


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_messages(self, correlation_engine):
        """Test with empty message list"""
        conversations = correlation_engine.correlate_conversations([])

        assert conversations == []

    def test_single_platform(self, correlation_engine):
        """Test with messages from only one platform"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Message",
                "sender_name": "User1",
                "timestamp": now.isoformat(),
                "thread_id": "thread1"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        # No cross-platform correlation with single platform
        # (might still create conversations but with single platform)
        assert all(len(c.platforms) <= 1 for c in conversations)

    def test_messages_without_thread_id(self, correlation_engine):
        """Test handling messages without thread IDs"""
        now = datetime.now(timezone.utc)

        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Orphan message",
                "sender_name": "User1",
                "timestamp": now.isoformat()
                # No thread_id
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        # Should handle gracefully
        assert isinstance(conversations, list)

    def test_invalid_timestamps(self, correlation_engine):
        """Test handling of invalid timestamps"""
        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Message",
                "sender_name": "User1",
                "timestamp": "invalid-timestamp",
                "thread_id": "thread1"
            }
        ]

        conversations = correlation_engine.correlate_conversations(messages)

        # Should handle gracefully
        assert isinstance(conversations, list)


class TestSingleton:
    """Test singleton instance"""

    def test_get_singleton_engine(self):
        """Test getting singleton correlation engine"""
        engine1 = get_cross_platform_correlation_engine()
        engine2 = get_cross_platform_correlation_engine()

        assert engine1 is engine2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
