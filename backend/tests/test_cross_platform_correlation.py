"""
Comprehensive test suite for Cross-Platform Correlation Engine

Tests conversation correlation across platforms, participant matching,
temporal correlation, content similarity, cross-references, and
unified timeline building.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.append(os.getcwd())

from core.cross_platform_correlation import (
    CorrelationStrength,
    LinkedConversation,
    CrossPlatformLink,
    CrossPlatformCorrelationEngine,
    correlation_engine,
    get_cross_platform_correlation_engine
)


class TestDataClasses(unittest.TestCase):
    """Test suite for dataclasses"""

    def test_linked_conversation_creation(self):
        """Test LinkedConversation dataclass creation"""
        conv = LinkedConversation(
            conversation_id="conv-1",
            threads={"slack": "thread-1", "teams": "thread-2"},
            platforms={"slack", "teams"},
            participants={"user1", "user2"},
            participant_emails={"user1@example.com"},
            message_count=10,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            correlation_strength=CorrelationStrength.STRONG,
            topic_keywords={"deploy", "release"}
        )

        self.assertEqual(conv.conversation_id, "conv-1")
        self.assertEqual(len(conv.threads), 2)
        self.assertEqual(conv.correlation_strength, CorrelationStrength.STRONG)

    def test_cross_platform_link_creation(self):
        """Test CrossPlatformLink dataclass creation"""
        link = CrossPlatformLink(
            source_platform="slack",
            source_thread="thread-1",
            target_platform="teams",
            target_thread="thread-2",
            strength=CorrelationStrength.MODERATE,
            reason="Shared participants",
            shared_participants={"user1", "user2"},
            temporal_distance=300.0
        )

        self.assertEqual(link.source_platform, "slack")
        self.assertEqual(link.target_platform, "teams")
        self.assertEqual(link.temporal_distance, 300.0)


class TestCorrelationEngineBasic(unittest.TestCase):
    """Test suite for basic correlation engine functionality"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine(similarity_threshold=0.3)

    def test_initialization(self):
        """Test engine initialization"""
        self.assertEqual(self.engine.similarity_threshold, 0.3)
        self.assertEqual(len(self.engine.linked_conversations), 0)
        self.assertEqual(len(self.engine.cross_platform_links), 0)

    def test_singleton_instance(self):
        """Test singleton instance getter"""
        instance = get_cross_platform_correlation_engine()

        self.assertIsInstance(instance, CrossPlatformCorrelationEngine)


class TestGroupByThread(unittest.TestCase):
    """Test suite for message grouping"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_group_by_thread_basic(self):
        """Test grouping messages by thread"""
        messages = [
            {"platform": "slack", "thread_id": "thread-1", "content": "Message 1"},
            {"platform": "slack", "thread_id": "thread-1", "content": "Message 2"},
            {"platform": "teams", "thread_id": "thread-2", "content": "Message 3"}
        ]

        grouped = self.engine._group_by_thread(messages)

        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped[("slack", "thread-1")]), 2)
        self.assertEqual(len(grouped[("teams", "thread-2")]), 1)

    def test_group_by_thread_no_thread_id(self):
        """Test grouping messages without thread_id"""
        messages = [
            {"platform": "slack", "content": "Message 1", "id": "msg-1"}
        ]

        grouped = self.engine._group_by_thread(messages)

        # Should group under "no_thread"
        self.assertIn(("slack", "no_thread"), grouped)


class TestExtractThreadMetadata(unittest.TestCase):
    """Test suite for thread metadata extraction"""

    def setUp(self):
        """Setup correlation engine and test data"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_extract_metadata_basic(self):
        """Test basic metadata extraction"""
        messages = [
            {
                "platform": "slack",
                "thread_id": "thread-1",
                "timestamp": "2024-01-01T10:00:00Z",
                "sender_name": "User 1",
                "sender_email": "user1@example.com",
                "content": "Deploy the release",
                "mentions": ["User 2"]
            },
            {
                "platform": "slack",
                "thread_id": "thread-1",
                "timestamp": "2024-01-01T10:05:00Z",
                "sender_name": "User 2",
                "sender_email": "user2@example.com",
                "content": "Review the code"
            }
        ]

        grouped = self.engine._group_by_thread(messages)
        metadata = self.engine._extract_thread_metadata(grouped)

        key = ("slack", "thread-1")
        self.assertIn(key, metadata)
        self.assertEqual(metadata[key]["message_count"], 2)
        self.assertIn("User 1", metadata[key]["participants"])
        self.assertIn("User 2", metadata[key]["participants"])
        self.assertIn("user1@example.com", metadata[key]["participant_emails"])

    def test_extract_metadata_timestamps(self):
        """Test timestamp parsing in metadata"""
        messages = [
            {
                "platform": "slack",
                "thread_id": "thread-1",
                "timestamp": "2024-01-01T10:00:00Z",
                "content": "Message 1"
            },
            {
                "platform": "slack",
                "thread_id": "thread-1",
                "timestamp": "2024-01-01T11:00:00Z",
                "content": "Message 2"
            }
        ]

        grouped = self.engine._group_by_thread(messages)
        metadata = self.engine._extract_thread_metadata(grouped)

        key = ("slack", "thread-1")
        self.assertIsNotNone(metadata[key]["start_time"])
        self.assertIsNotNone(metadata[key]["end_time"])
        self.assertLess(metadata[key]["start_time"], metadata[key]["end_time"])

    def test_extract_keywords(self):
        """Test keyword extraction from messages"""
        messages = [
            {"content": "Urgent: deploy the release before deadline"},
            {"content": "Review the feature and fix bug"}
        ]

        keywords = self.engine._extract_keywords(messages)

        # Should extract important words
        self.assertIn("urgent", keywords)
        self.assertIn("deploy", keywords)
        self.assertIn("release", keywords)
        self.assertIn("deadline", keywords)
        self.assertIn("review", keywords)
        self.assertIn("feature", keywords)
        self.assertIn("bug", keywords)


class TestCorrelationByParticipants(unittest.TestCase):
    """Test suite for participant-based correlation"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_correlate_by_shared_participants(self):
        """Test correlation based on shared participants"""
        messages = [
            # Slack thread
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": "2024-01-01T10:00:00Z",
                "sender_name": "Alice",
                "sender_email": "alice@example.com",
                "content": "Discussion"
            },
            # Teams thread with same participant
            {
                "platform": "teams",
                "thread_id": "teams-1",
                "timestamp": "2024-01-01T11:00:00Z",
                "sender_name": "Alice",
                "sender_email": "alice@example.com",
                "content": "Discussion"
            }
        ]

        correlations = self.engine.correlate_conversations(messages)

        self.assertGreater(len(correlations), 0)

        # Check that cross-platform link was created
        self.assertGreater(len(self.engine.cross_platform_links), 0)
        link = self.engine.cross_platform_links[0]
        self.assertEqual(link.source_platform, "slack")
        self.assertEqual(link.target_platform, "teams")

    def test_correlate_by_email_name_match(self):
        """Test correlation based on email-name cross-match"""
        messages = [
            # Slack thread with email
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": "2024-01-01T10:00:00Z",
                "sender_name": "Bob Smith",
                "sender_email": "bob.smith@example.com",
                "content": "Discussion"
            },
            # Teams thread with matching name (from email username)
            {
                "platform": "teams",
                "thread_id": "teams-1",
                "timestamp": "2024-01-01T11:00:00Z",
                "sender_name": "bob.smith",
                "sender_email": "bob.smith@example.com",
                "content": "Discussion"
            }
        ]

        correlations = self.engine.correlate_conversations(messages)

        # Should correlate based on email/name match
        self.assertGreater(len(correlations), 0)


class TestCorrelationByTime(unittest.TestCase):
    """Test suite for temporal correlation"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_correlate_by_time_overlap(self):
        """Test correlation based on overlapping time periods"""
        base_time = datetime.now(timezone.utc)

        messages = [
            # Slack thread
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": base_time.isoformat(),
                "content": "Message 1"
            },
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": (base_time + timedelta(minutes=30)).isoformat(),
                "content": "Message 2"
            },
            # Teams thread within 2-hour window
            {
                "platform": "teams",
                "thread_id": "teams-1",
                "timestamp": (base_time + timedelta(hours=1)).isoformat(),
                "content": "Message 3"
            }
        ]

        correlations = self.engine.correlate_conversations(messages)

        # Should find temporal correlation
        self.assertGreater(len(correlations), 0)


class TestCorrelationByContent(unittest.TestCase):
    """Test suite for content-based correlation"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine(similarity_threshold=0.2)

    def test_correlate_by_content_similarity(self):
        """Test correlation based on content similarity"""
        messages = [
            # Slack thread about deployment
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": "2024-01-01T10:00:00Z",
                "content": "We need to deploy the release urgently"
            },
            # Teams thread with similar keywords
            {
                "platform": "teams",
                "thread_id": "teams-1",
                "timestamp": "2024-01-01T11:00:00Z",
                "content": "The release deployment is urgent"
            }
        ]

        correlations = self.engine.correlate_conversations(messages)

        # Should correlate based on keyword overlap
        self.assertGreater(len(correlations), 0)


class TestCorrelationByReferences(unittest.TestCase):
    """Test suite for cross-reference correlation"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_correlate_by_platform_mentions(self):
        """Test correlation based on platform mentions"""
        base_time = datetime.now(timezone.utc)

        messages = [
            # Slack thread mentioning teams
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": base_time.isoformat(),
                "content": "Let's discuss this in Teams meeting"
            },
            # Teams thread around the same time
            {
                "platform": "teams",
                "thread_id": "teams-1",
                "timestamp": (base_time + timedelta(minutes=30)).isoformat(),
                "content": "Meeting discussion"
            }
        ]

        correlations = self.engine.correlate_conversations(messages)

        # Should find reference-based correlation
        self.assertGreater(len(correlations), 0)


class TestUnifiedTimeline(unittest.TestCase):
    """Test suite for unified timeline building"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_build_unified_timeline(self):
        """Test building unified timeline from correlated conversations"""
        base_time = datetime.now(timezone.utc)

        messages = [
            {
                "platform": "slack",
                "thread_id": "thread-1",
                "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "content": "Slack message",
                "sender": "Alice"
            },
            {
                "platform": "teams",
                "thread_id": "thread-2",
                "timestamp": base_time.isoformat(),
                "content": "Teams message",
                "sender": "Bob"
            }
        ]

        correlations = self.engine.correlate_conversations(messages)

        if correlations:
            conv = correlations[0]

            # Check unified messages were built
            self.assertGreater(len(conv.unified_messages), 0)

            # Verify messages are sorted by timestamp
            timestamps = [
                self.engine._parse_timestamp(msg.get("timestamp"))
                for msg in conv.unified_messages
            ]

            # Should be in ascending order
            for i in range(len(timestamps) - 1):
                if timestamps[i] and timestamps[i+1]:
                    self.assertLessEqual(timestamps[i], timestamps[i+1])

    def test_get_unified_timeline_by_conversation_id(self):
        """Test retrieving unified timeline by conversation ID"""
        base_time = datetime.now(timezone.utc)

        messages = [
            {
                "platform": "slack",
                "thread_id": "thread-1",
                "timestamp": base_time.isoformat(),
                "content": "Message 1",
                "sender": "Alice"
            }
        ]

        self.engine.correlate_conversations(messages)

        # Get first conversation ID
        if self.engine.linked_conversations:
            conv_id = list(self.engine.linked_conversations.keys())[0]
            timeline = self.engine.get_unified_timeline(conv_id)

            self.assertIsNotNone(timeline)
            self.assertGreater(len(timeline), 0)

    def test_get_unified_timeline_nonexistent(self):
        """Test retrieving timeline for non-existent conversation"""
        timeline = self.engine.get_unified_timeline("nonexistent")

        self.assertIsNone(timeline)


class TestTimestampParsing(unittest.TestCase):
    """Test suite for timestamp parsing"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_parse_datetime_string(self):
        """Test parsing datetime from ISO string"""
        timestamp_str = "2024-01-01T10:00:00Z"
        result = self.engine._parse_timestamp(timestamp_str)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, datetime)

    def test_parse_datetime_object(self):
        """Test parsing datetime object"""
        dt = datetime.now(timezone.utc)
        result = self.engine._parse_timestamp(dt)

        self.assertEqual(result, dt)

    def test_parse_none_timestamp(self):
        """Test parsing None timestamp"""
        result = self.engine._parse_timestamp(None)

        self.assertIsNone(result)

    def test_parse_invalid_string(self):
        """Test parsing invalid string"""
        result = self.engine._parse_timestamp("invalid-timestamp")

        self.assertIsNone(result)


class TestFullCorrelationPipeline(unittest.TestCase):
    """Test suite for full correlation pipeline"""

    def setUp(self):
        """Setup correlation engine"""
        self.engine = CrossPlatformCorrelationEngine()

    def test_full_pipeline_multiple_strategies(self):
        """Test full correlation pipeline with all strategies"""
        base_time = datetime.now(timezone.utc)

        messages = [
            # Slack thread about deployment
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": base_time.isoformat(),
                "sender": "Alice",
                "sender_email": "alice@example.com",
                "content": "We need to deploy the release urgently",
                "mentions": ["Bob"]
            },
            {
                "platform": "slack",
                "thread_id": "slack-1",
                "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
                "sender": "Bob",
                "sender_email": "bob@example.com",
                "content": "I'll review the release"
            },
            # Teams thread with same participants, similar topic
            {
                "platform": "teams",
                "thread_id": "teams-1",
                "timestamp": (base_time + timedelta(minutes=30)).isoformat(),
                "sender": "Alice",
                "sender_email": "alice@example.com",
                "content": "Let's discuss the release deployment",
                "mentions": ["Bob"]
            },
            {
                "platform": "teams",
                "thread_id": "teams-1",
                "timestamp": (base_time + timedelta(minutes=35)).isoformat(),
                "sender": "Bob",
                "sender_email": "bob@example.com",
                "content": "The deployment is urgent"
            }
        ]

        correlations = self.engine.correlate_conversations(messages)

        # Should find correlations through multiple strategies
        self.assertGreater(len(correlations), 0)

        # Verify cross-platform links were created
        self.assertGreater(len(self.engine.cross_platform_links), 0)

        # Verify linked conversations were created
        self.assertGreater(len(self.engine.linked_conversations), 0)


if __name__ == "__main__":
    unittest.main()
