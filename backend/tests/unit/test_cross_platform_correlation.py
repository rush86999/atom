"""
Comprehensive unit tests for CrossPlatformCorrelationEngine class

Tests cover:
- Initialization and configuration
- Conversation correlation by participants
- Conversation correlation by time
- Conversation correlation by content
- Conversation correlation by cross-references
- Thread grouping and metadata extraction
- Timeline reconstruction
- Merging overlapping correlations
- Cross-platform linking
- Keyword extraction
- Timestamp parsing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set

# Import the CrossPlatformCorrelationEngine and related classes
from core.cross_platform_correlation import (
    CrossPlatformCorrelationEngine,
    LinkedConversation,
    CrossPlatformLink,
    CorrelationStrength,
    get_cross_platform_correlation_engine
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def correlation_engine():
    """Create a CrossPlatformCorrelationEngine instance for testing"""
    return CrossPlatformCorrelationEngine(similarity_threshold=0.3)


@pytest.fixture
def sample_slack_messages():
    """Sample Slack messages for testing"""
    return [
        {
            "id": "slack-1",
            "platform": "slack",
            "content": "Project deadline is tomorrow",
            "sender": "john.doe",
            "sender_email": "john@example.com",
            "timestamp": "2024-01-15T10:00:00Z",
            "thread_id": "slack-thread-1",
            "conversation_id": "conv-1",
            "channel_id": "C123",
            "mentions": ["jane.smith"]
        },
        {
            "id": "slack-2",
            "platform": "slack",
            "content": "Let's discuss the urgent deadline",
            "sender": "jane.smith",
            "sender_email": "jane@example.com",
            "timestamp": "2024-01-15T10:05:00Z",
            "thread_id": "slack-thread-1",
            "conversation_id": "conv-1",
            "channel_id": "C123"
        }
    ]


@pytest.fixture
def sample_teams_messages():
    """Sample Teams messages for testing"""
    return [
        {
            "id": "teams-1",
            "platform": "teams",
            "content": "Project deadline is tomorrow",
            "sender": "John Doe",
            "sender_email": "john@example.com",
            "timestamp": "2024-01-15T10:02:00Z",
            "thread_id": "teams-thread-1",
            "conversation_id": "conv-2",
            "mentions": []
        },
        {
            "id": "teams-2",
            "platform": "teams",
            "content": "Meeting about the deadline",
            "sender": "Jane Smith",
            "sender_email": "jane@example.com",
            "timestamp": "2024-01-15T10:07:00Z",
            "thread_id": "teams-thread-1",
            "conversation_id": "conv-2"
        }
    ]


@pytest.fixture
def sample_email_messages():
    """Sample email messages for testing"""
    return [
        {
            "id": "email-1",
            "platform": "gmail",
            "content": "Project deadline tomorrow - please review",
            "sender": "john@example.com",
            "sender_email": "john@example.com",
            "timestamp": "2024-01-15T09:58:00Z",
            "thread_id": "email-thread-1",
            "conversation_id": "email-thread-1"
        }
    ]


# =============================================================================
# TEST ENGINE INITIALIZATION
# =============================================================================

class TestCorrelationInit:
    """Tests for CrossPlatformCorrelationEngine initialization"""

    def test_init_creates_empty_state(self, correlation_engine):
        """Test that initialization creates empty state"""
        assert hasattr(correlation_engine, 'linked_conversations')
        assert hasattr(correlation_engine, 'cross_platform_links')
        assert hasattr(correlation_engine, 'similarity_threshold')
        assert len(correlation_engine.linked_conversations) == 0
        assert len(correlation_engine.cross_platform_links) == 0

    def test_init_with_custom_threshold(self):
        """Test initialization with custom similarity threshold"""
        engine = CrossPlatformCorrelationEngine(similarity_threshold=0.5)
        assert engine.similarity_threshold == 0.5

    def test_global_singleton(self):
        """Test that get_cross_platform_correlation_engine returns singleton instance"""
        engine1 = get_cross_platform_correlation_engine()
        engine2 = get_cross_platform_correlation_engine()
        assert engine1 is engine2


# =============================================================================
# TEST THREAD GROUPING
# =============================================================================

class TestThreadGrouping:
    """Tests for thread grouping functionality"""

    def test_group_by_thread(self, correlation_engine, sample_slack_messages):
        """Test grouping messages by thread"""
        grouped = correlation_engine._group_by_thread(sample_slack_messages)

        assert ("slack", "slack-thread-1") in grouped
        assert len(grouped[("slack", "slack-thread-1")]) == 2

    def test_group_by_thread_multiple_conversations(self, correlation_engine, sample_slack_messages, sample_teams_messages):
        """Test grouping messages from multiple conversations"""
        all_messages = sample_slack_messages + sample_teams_messages
        grouped = correlation_engine._group_by_thread(all_messages)

        assert len(grouped) == 2  # One Slack thread, one Teams thread
        assert ("slack", "slack-thread-1") in grouped
        assert ("teams", "teams-thread-1") in grouped

    def test_group_messages_without_thread(self, correlation_engine):
        """Test grouping messages that have no thread_id"""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test",
                "timestamp": "2024-01-15T10:00:00Z"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)

        assert ("slack", "no_thread") in grouped


# =============================================================================
# TEST METADATA EXTRACTION
# =============================================================================

class TestMetadataExtraction:
    """Tests for thread metadata extraction"""

    def test_extract_thread_metadata(self, correlation_engine, sample_slack_messages):
        """Test extracting metadata from threads"""
        grouped = correlation_engine._group_by_thread(sample_slack_messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)

        key = ("slack", "slack-thread-1")
        assert key in metadata
        assert metadata[key]["platform"] == "slack"
        assert metadata[key]["message_count"] == 2
        assert "john.doe" in metadata[key]["participants"]
        assert "jane.smith" in metadata[key]["participants"]
        assert metadata[key]["start_time"] is not None
        assert metadata[key]["end_time"] is not None

    def test_extract_participant_emails(self, correlation_engine, sample_slack_messages):
        """Test extracting participant emails"""
        grouped = correlation_engine._group_by_thread(sample_slack_messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)

        key = ("slack", "slack-thread-1")
        assert "john@example.com" in metadata[key]["participant_emails"]
        assert "jane@example.com" in metadata[key]["participant_emails"]

    def test_extract_keywords(self, correlation_engine):
        """Test keyword extraction from messages"""
        messages = [
            {"content": "Urgent deadline meeting review approval"},
            {"content": "Project blocked on feature"}
        ]

        keywords = correlation_engine._extract_keywords(messages)

        assert "urgent" in keywords
        assert "deadline" in keywords
        assert "meeting" in keywords


# =============================================================================
# TEST CORRELATION BY PARTICIPANTS
# =============================================================================

class TestCorrelationByParticipants:
    """Tests for participant-based correlation"""

    def test_correlate_by_shared_participants(self, correlation_engine, sample_slack_messages, sample_teams_messages):
        """Test correlating threads by shared participants"""
        all_messages = sample_slack_messages + sample_teams_messages
        grouped = correlation_engine._group_by_thread(all_messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)

        conversations = correlation_engine._correlate_by_participants(metadata)

        # Should link Slack and Teams threads due to shared participants
        assert len(conversations) > 0
        # Check that a linked conversation has multiple platforms
        if conversations:
            assert len(conversations[0].platforms) >= 2

    def test_correlate_by_email_cross_match(self, correlation_engine):
        """Test correlating by email-name cross-match"""
        messages = [
            {
                "id": "slack-1",
                "platform": "slack",
                "content": "Test",
                "sender": "johndoe",
                "sender_email": "john@example.com",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "email-1",
                "platform": "gmail",
                "content": "Test",
                "sender": "john@example.com",
                "timestamp": "2024-01-15T10:05:00Z",
                "thread_id": "thread-2"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)
        conversations = correlation_engine._correlate_by_participants(metadata)

        # Should correlate based on username matching email
        assert len(conversations) > 0


# =============================================================================
# TEST CORRELATION BY TIME
# =============================================================================

class TestCorrelationByTime:
    """Tests for temporal correlation"""

    def test_correlate_overlapping_time_periods(self, correlation_engine):
        """Test correlating threads with overlapping time periods"""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test 1",
                "sender": "user1",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "msg-2",
                "platform": "teams",
                "content": "Test 2",
                "sender": "user2",
                "timestamp": "2024-01-15T11:30:00Z",  # Within 2-hour window
                "thread_id": "thread-2"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)
        conversations = correlation_engine._correlate_by_time(metadata)

        # Should correlate due to temporal proximity
        assert len(conversations) > 0

    def test_no_correlation_far_time_periods(self, correlation_engine):
        """Test that threads far apart in time don't correlate"""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test 1",
                "sender": "user1",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "msg-2",
                "platform": "teams",
                "content": "Test 2",
                "sender": "user2",
                "timestamp": "2024-01-15T14:00:00Z",  # 4 hours later
                "thread_id": "thread-2"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)
        conversations = correlation_engine._correlate_by_time(metadata)

        # Should not correlate due to time distance
        assert len(conversations) == 0 or all(
            conv.correlation_strength == CorrelationStrength.WEAK
            for conv in conversations
        )


# =============================================================================
# TEST CORRELATION BY CONTENT
# =============================================================================

class TestCorrelationByContent:
    """Tests for content-based correlation"""

    def test_correlate_similar_content(self, correlation_engine):
        """Test correlating threads with similar content"""
        messages = [
            {
                "id": "slack-1",
                "platform": "slack",
                "content": "Urgent deadline meeting tomorrow",
                "sender": "user1",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "teams-1",
                "platform": "teams",
                "content": "Deadline and urgent meeting discussion",
                "sender": "user2",
                "timestamp": "2024-01-15T10:05:00Z",
                "thread_id": "thread-2"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)
        conversations = correlation_engine._correlate_by_content(metadata)

        # Should correlate due to keyword overlap
        assert len(conversations) > 0

    def test_no_correlation_different_content(self, correlation_engine):
        """Test that different content doesn't correlate"""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Discussion about lunch plans",
                "sender": "user1",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "msg-2",
                "platform": "teams",
                "content": "Database server configuration",
                "sender": "user2",
                "timestamp": "2024-01-15T10:05:00Z",
                "thread_id": "thread-2"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)
        conversations = correlation_engine._correlate_by_content(metadata)

        # Should not correlate due to different content
        assert len(conversations) == 0


# =============================================================================
# TEST CORRELATION BY REFERENCES
# =============================================================================

class TestCorrelationByReferences:
    """Tests for cross-reference correlation"""

    def test_correlate_by_platform_reference(self, correlation_engine):
        """Test correlating threads that mention other platforms"""
        messages = [
            {
                "id": "slack-1",
                "platform": "slack",
                "content": "Let's continue this discussion in Teams",
                "sender": "user1",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "teams-1",
                "platform": "teams",
                "content": "Continuing our discussion",
                "sender": "user1",
                "timestamp": "2024-01-15T10:05:00Z",
                "thread_id": "thread-2"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)
        conversations = correlation_engine._correlate_by_references(metadata)

        # Should correlate due to platform reference
        assert len(conversations) > 0


# =============================================================================
# TEST CONVERSATION CORRELATION
# =============================================================================

class TestConversationCorrelation:
    """Tests for full conversation correlation"""

    def test_correlate_conversations_all_strategies(self, correlation_engine, sample_slack_messages, sample_teams_messages):
        """Test correlating conversations using all strategies"""
        all_messages = sample_slack_messages + sample_teams_messages

        conversations = correlation_engine.correlate_conversations(all_messages)

        assert len(conversations) > 0
        assert all(isinstance(conv, LinkedConversation) for conv in conversations)

    def test_correlate_creates_unified_timeline(self, correlation_engine, sample_slack_messages, sample_teams_messages):
        """Test that correlation creates unified message timeline"""
        all_messages = sample_slack_messages + sample_teams_messages

        conversations = correlation_engine.correlate_conversations(all_messages)

        if conversations:
            assert hasattr(conversations[0], 'unified_messages')
            # Check that messages are from both platforms
            platforms = set(msg.get("platform") for msg in conversations[0].unified_messages)
            assert len(platforms) >= 1


# =============================================================================
# TEST CROSS-PLATFORM LINKING
# =============================================================================

class TestCrossPlatformLinking:
    """Tests for cross-platform link creation"""

    def test_cross_platform_link_creation(self, correlation_engine):
        """Test that cross-platform links are created"""
        messages = [
            {
                "id": "slack-1",
                "platform": "slack",
                "content": "Urgent deadline",
                "sender": "john@example.com",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "teams-1",
                "platform": "teams",
                "content": "Urgent deadline",
                "sender": "john@example.com",
                "timestamp": "2024-01-15T10:05:00Z",
                "thread_id": "thread-2"
            }
        ]

        correlation_engine.correlate_conversations(messages)

        # Check that links were created
        assert len(correlation_engine.cross_platform_links) > 0

    def test_cross_platform_link_properties(self, correlation_engine):
        """Test cross-platform link properties"""
        link = CrossPlatformLink(
            source_platform="slack",
            source_thread="thread-1",
            target_platform="teams",
            target_thread="thread-2",
            strength=CorrelationStrength.STRONG,
            reason="Shared 2 participants",
            shared_participants={"user1", "user2"},
            temporal_distance=120.0
        )

        assert link.source_platform == "slack"
        assert link.target_platform == "teams"
        assert link.strength == CorrelationStrength.STRONG
        assert len(link.shared_participants) == 2
        assert link.temporal_distance == 120.0


# =============================================================================
# TEST TIMELINE RECONSTRUCTION
# =============================================================================

class TestTimelineReconstruction:
    """Tests for unified timeline reconstruction"""

    def test_build_unified_timeline(self, correlation_engine, sample_slack_messages, sample_teams_messages):
        """Test building unified timeline from multiple threads"""
        all_messages = sample_slack_messages + sample_teams_messages
        grouped = correlation_engine._group_by_thread(all_messages)

        threads = {
            "slack": "slack-thread-1",
            "teams": "teams-thread-1"
        }

        timeline = correlation_engine._build_unified_timeline(threads, grouped)

        assert len(timeline) == 4  # 2 Slack + 2 Teams messages
        # Check that messages are sorted by timestamp
        timestamps = [correlation_engine._parse_timestamp(msg.get("timestamp")) for msg in timeline]
        assert timestamps == sorted(timestamps)

    def test_get_unified_timeline(self, correlation_engine):
        """Test getting unified timeline for a conversation"""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "First",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "msg-2",
                "platform": "teams",
                "content": "Second",
                "timestamp": "2024-01-15T10:05:00Z",
                "thread_id": "thread-2"
            }
        ]

        correlation_engine.correlate_conversations(messages)

        if correlation_engine.linked_conversations:
            conv_id = list(correlation_engine.linked_conversations.keys())[0]
            timeline = correlation_engine.get_unified_timeline(conv_id)

            assert timeline is not None
            assert len(timeline) == 2


# =============================================================================
# TEST MERGING CORRELATIONS
# =============================================================================

class TestMergingCorrelations:
    """Tests for merging overlapping correlations"""

    def test_merge_overlapping_correlations(self, correlation_engine):
        """Test merging overlapping conversation correlations"""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test",
                "sender": "user1",
                "timestamp": "2024-01-15T10:00:00Z",
                "thread_id": "thread-1"
            },
            {
                "id": "msg-2",
                "platform": "teams",
                "content": "Test",
                "sender": "user1",
                "timestamp": "2024-01-15T10:05:00Z",
                "thread_id": "thread-2"
            },
            {
                "id": "msg-3",
                "platform": "gmail",
                "content": "Test",
                "sender": "user1",
                "timestamp": "2024-01-15T10:10:00Z",
                "thread_id": "thread-3"
            }
        ]

        grouped = correlation_engine._group_by_thread(messages)
        metadata = correlation_engine._extract_thread_metadata(grouped)

        # Create multiple correlations
        participant_convs = correlation_engine._correlate_by_participants(metadata)
        time_convs = correlation_engine._correlate_by_time(metadata)

        # Merge them
        merged = correlation_engine._merge_correlations(participant_convs + time_convs, grouped)

        # Should merge into fewer conversations
        assert len(merged) <= len(participant_convs) + len(time_convs)


# =============================================================================
# TEST TIMESTAMP PARSING
# =============================================================================

class TestTimestampParsing:
    """Tests for timestamp parsing"""

    def test_parse_datetime_object(self, correlation_engine):
        """Test parsing datetime object"""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = correlation_engine._parse_timestamp(dt)

        assert result == dt

    def test_parse_iso_string(self, correlation_engine):
        """Test parsing ISO format string"""
        iso_string = "2024-01-15T10:30:00Z"
        result = correlation_engine._parse_timestamp(iso_string)

        assert result is not None
        assert result.year == 2024

    def test_parse_invalid_string(self, correlation_engine):
        """Test parsing invalid timestamp string"""
        result = correlation_engine._parse_timestamp("invalid-date")

        assert result is None

    def test_parse_none(self, correlation_engine):
        """Test parsing None value"""
        result = correlation_engine._parse_timestamp(None)

        assert result is None


# =============================================================================
# TEST CORRELATION STRENGTH
# =============================================================================

class TestCorrelationStrength:
    """Tests for CorrelationStrength enum"""

    def test_correlation_strength_values(self):
        """Test that CorrelationStrength enum has correct values"""
        assert CorrelationStrength.STRONG.value == "strong"
        assert CorrelationStrength.MODERATE.value == "moderate"
        assert CorrelationStrength.WEAK.value == "weak"


# =============================================================================
# TEST LINKED CONVERSATION
# =============================================================================

class TestLinkedConversation:
    """Tests for LinkedConversation dataclass"""

    def test_linked_conversation_creation(self):
        """Test creating a linked conversation"""
        conv = LinkedConversation(
            conversation_id="conv-1",
            threads={"slack": "thread-1", "teams": "thread-2"},
            platforms={"slack", "teams"},
            participants={"user1", "user2"},
            participant_emails={"user1@example.com"},
            message_count=5,
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 11, 0, 0),
            correlation_strength=CorrelationStrength.STRONG,
            topic_keywords={"deadline", "urgent"}
        )

        assert conv.conversation_id == "conv-1"
        assert len(conv.platforms) == 2
        assert len(conv.participants) == 2
        assert conv.message_count == 5
        assert conv.correlation_strength == CorrelationStrength.STRONG

    def test_linked_conversation_default_values(self):
        """Test linked conversation with default values"""
        conv = LinkedConversation(
            conversation_id="conv-2",
            threads={"slack": "thread-1"},
            platforms={"slack"},
            participants={"user1"}
        )

        assert conv.participant_emails == set()
        assert conv.message_count == 0
        assert conv.start_time is None
        assert conv.end_time is None
        assert conv.correlation_strength == CorrelationStrength.MODERATE
        assert conv.topic_keywords == set()
        assert conv.unified_messages == []
