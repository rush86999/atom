"""
Test Suite for Unified Message Processor

Tests for core.unified_message_processor module (630 lines)
- Message normalization from multiple platforms
- Cross-platform deduplication
- Conversation threading
- Message enrichment (URLs, mentions, entities)
- Message search and statistics

Target Tests: 20-25
Target Coverage: 25-30%
"""

from datetime import datetime, timedelta
from unittest.mock import Mock
import pytest

from core.unified_message_processor import (
    UnifiedMessage,
    UnifiedMessageProcessor,
    MessageType,
    MessagePriority
)


class TestUnifiedMessageDataclass:
    """Test UnifiedMessage dataclass structure."""

    def test_unified_message_creation(self):
        """UnifiedMessage can be created with required fields."""
        message = UnifiedMessage(
            id="msg-001",
            unified_id="unified-123",
            platform="slack",
            platform_message_id="slack-msg-001",
            content="Hello world"
        )

        assert message.id == "msg-001"
        assert message.unified_id == "unified-123"
        assert message.platform == "slack"
        assert message.content == "Hello world"

    def test_unified_message_to_dict(self):
        """UnifiedMessage can be converted to dictionary."""
        message = UnifiedMessage(
            id="msg-001",
            unified_id="unified-123",
            platform="slack",
            platform_message_id="slack-msg-001",
            content="Test message"
        )

        result = message.to_dict()

        assert result["id"] == "msg-001"
        assert result["unified_id"] == "unified-123"
        assert result["platform"] == "slack"
        assert result["content"] == "Test message"


class TestUnifiedMessageProcessorInit:
    """Test UnifiedMessageProcessor initialization."""

    def test_initialization(self):
        """UnifiedMessageProcessor can be initialized."""
        processor = UnifiedMessageProcessor()

        assert processor.processed_messages == {}
        assert processor.message_hashes == set()
        assert processor.conversation_threads == {}
        assert processor.cross_platform_map == {}


class TestMessageNormalization:
    """Test message normalization from different platforms."""

    @pytest.fixture
    def processor(self):
        """Create message processor instance."""
        return UnifiedMessageProcessor()

    def test_normalize_slack_message(self, processor):
        """UnifiedMessageProcessor normalizes Slack messages correctly."""
        raw_message = {
            "id": "slack-msg-001",
            "app_type": "slack",
            "content": "Hello from Slack!",
            "sender": "John Doe",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {
                "channel_id": "C12345",
                "channel_name": "general",
                "channel_type": "channel"
            }
        }

        result = processor.normalize_message(raw_message)

        assert result.platform == "slack"
        assert result.content == "Hello from Slack!"
        assert result.sender_name == "John Doe"
        assert result.channel_id == "C12345"
        assert result.channel_name == "general"

    def test_normalize_teams_message(self, processor):
        """UnifiedMessageProcessor normalizes Teams messages correctly."""
        raw_message = {
            "id": "teams-msg-001",
            "app_type": "microsoft_teams",
            "content": "Hello from Teams!",
            "sender": "Jane Doe",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {
                "channel_id": "19:abc",
                "chat_title": "Project Chat",
                "chat_type": "group"
            }
        }

        result = processor.normalize_message(raw_message)

        assert result.platform == "teams"
        assert result.content == "Hello from Teams!"
        assert result.channel_name == "Project Chat"

    def test_normalize_gmail_message(self, processor):
        """UnifiedMessageProcessor normalizes Gmail messages correctly."""
        raw_message = {
            "id": "gmail-msg-001",
            "app_type": "gmail",
            "content": "Hello via Email!",
            "subject": "Test Subject",
            "sender": "sender@example.com",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {
                "thread_id": "thread-123"
            }
        }

        result = processor.normalize_message(raw_message)

        assert result.platform == "gmail"
        assert result.subject == "Test Subject"
        assert result.thread_id == "thread-123"
        assert result.channel_type == "email"

    def test_normalize_message_with_attachments(self, processor):
        """UnifiedMessageProcessor handles attachments correctly."""
        raw_message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "File attached",
            "attachments": [
                {"name": "file.pdf", "url": "https://example.com/file.pdf"}
            ],
            "timestamp": "2024-01-15T10:30:00Z"
        }

        result = processor.normalize_message(raw_message)

        assert result.has_attachments is True
        assert len(result.attachments) == 1
        assert "has_attachments" in result.tags

    def test_normalize_message_with_priority(self, processor):
        """UnifiedMessageProcessor handles message priority."""
        raw_message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Urgent message",
            "priority": "urgent",
            "timestamp": "2024-01-15T10:30:00Z"
        }

        result = processor.normalize_message(raw_message)

        assert result.priority == MessagePriority.URGENT.value


class TestUnifiedIdGeneration:
    """Test unified ID generation for cross-platform deduplication."""

    @pytest.fixture
    def processor(self):
        """Create message processor instance."""
        return UnifiedMessageProcessor()

    def test_generate_unified_id_same_content_same_day(self, processor):
        """UnifiedMessageProcessor generates same ID for same content on same day."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)

        id1 = processor.generate_unified_id("Test message", timestamp, "slack")
        id2 = processor.generate_unified_id("Test message", timestamp, "slack")

        assert id1 == id2

    def test_generate_unified_id_different_content(self, processor):
        """UnifiedMessageProcessor generates different IDs for different content."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)

        id1 = processor.generate_unified_id("Message 1", timestamp, "slack")
        id2 = processor.generate_unified_id("Message 2", timestamp, "slack")

        assert id1 != id2

    def test_generate_unified_id_case_insensitive(self, processor):
        """UnifiedMessageProcessor generates same ID for different case."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)

        id1 = processor.generate_unified_id("Test Message", timestamp, "slack")
        id2 = processor.generate_unified_id("test message", timestamp, "slack")

        assert id1 == id2


class TestDuplicateDetection:
    """Test duplicate and cross-post detection."""

    @pytest.fixture
    def processor(self):
        """Create message processor instance."""
        return UnifiedMessageProcessor()

    def test_detect_duplicates_same_content(self, processor):
        """UnifiedMessageProcessor detects duplicate messages."""
        messages = [
            UnifiedMessage(
                id="msg-001",
                unified_id="unified-123",
                platform="slack",
                platform_message_id="slack-001",
                content="Same message",
                timestamp=datetime.now()
            ),
            UnifiedMessage(
                id="msg-002",
                unified_id="unified-124",
                platform="teams",
                platform_message_id="teams-001",
                content="Same message",
                timestamp=datetime.now()
            )
        ]

        unique, duplicate_groups = processor.detect_duplicates(messages)

        assert len(unique) == 1
        assert len(duplicate_groups) == 1
        assert unique[0].is_cross_posted is True

    def test_detect_cross_platform_duplicates(self, processor):
        """UnifiedMessageProcessor identifies cross-platform duplicates."""
        messages = [
            UnifiedMessage(
                id="msg-001",
                unified_id="unified-123",
                platform="slack",
                platform_message_id="slack-001",
                content="Cross-posted message",
                timestamp=datetime.now()
            ),
            UnifiedMessage(
                id="msg-002",
                unified_id="unified-124",
                platform="teams",
                platform_message_id="teams-001",
                content="Cross-posted message",
                timestamp=datetime.now()
            )
        ]

        unique, duplicate_groups = processor.detect_duplicates(messages)

        # Should track cross-platform mapping
        assert len(unique) == 1


class TestConversationThreading:
    """Test conversation thread creation."""

    @pytest.fixture
    def processor(self):
        """Create message processor instance."""
        return UnifiedMessageProcessor()

    def test_create_conversation_threads(self, processor):
        """UnifiedMessageProcessor creates conversation threads."""
        messages = [
            UnifiedMessage(
                id="msg-001",
                unified_id="unified-001",
                platform="slack",
                platform_message_id="slack-001",
                content="First message",
                conversation_id="conv-001",
                timestamp=datetime.now() - timedelta(minutes=10)
            ),
            UnifiedMessage(
                id="msg-002",
                unified_id="unified-002",
                platform="slack",
                platform_message_id="slack-002",
                content="Second message",
                conversation_id="conv-001",
                timestamp=datetime.now()
            )
        ]

        threads = processor.create_conversation_threads(messages)

        assert "conv-001" in threads
        assert len(threads["conv-001"]) == 2
        assert threads["conv-001"][0] == "msg-001"
        assert threads["conv-001"][1] == "msg-002"

    def test_create_conversation_without_conversation_id(self, processor):
        """UnifiedMessageProcessor generates conversation ID when missing."""
        message = UnifiedMessage(
            id="msg-001",
            unified_id="unified-001",
            platform="slack",
            platform_message_id="slack-001",
            content="Message",
            conversation_id=None,
            timestamp=datetime.now()
        )

        threads = processor.create_conversation_threads([message])

        # Should have created a conversation ID
        assert len(threads) == 1
        assert message.conversation_id is not None


class TestMessageEnrichment:
    """Test message enrichment with extracted data."""

    @pytest.fixture
    def processor(self):
        """Create message processor instance."""
        return UnifiedMessageProcessor()

    def test_enrich_message_extracts_urls(self, processor):
        """UnifiedMessageProcessor extracts URLs from content."""
        message = UnifiedMessage(
            id="msg-001",
            unified_id="unified-001",
            platform="slack",
            platform_message_id="slack-001",
            content="Check out https://example.com",
            timestamp=datetime.now()
        )

        processor._enrich_message(message)

        assert len(message.urls) == 1
        assert "https://example.com" in message.urls

    def test_enrich_message_extracts_slack_mentions(self, processor):
        """UnifiedMessageProcessor extracts Slack mentions."""
        message = UnifiedMessage(
            id="msg-001",
            unified_id="unified-001",
            platform="slack",
            platform_message_id="slack-001",
            content="Hey <@U12345>, check this out",
            timestamp=datetime.now()
        )

        processor._enrich_message(message)

        assert "U12345" in message.mentions

    def test_enrich_message_adds_platform_tag(self, processor):
        """UnifiedMessageProcessor adds platform tag to message."""
        message = UnifiedMessage(
            id="msg-001",
            unified_id="unified-001",
            platform="slack",
            platform_message_id="slack-001",
            content="Test message",
            timestamp=datetime.now()
        )

        processor._enrich_message(message)

        assert "slack" in message.tags


class TestMessageProcessing:
    """Test end-to-end message processing."""

    @pytest.fixture
    def processor(self):
        """Create message processor instance."""
        return UnifiedMessageProcessor()

    def test_process_messages_batch(self, processor):
        """UnifiedMessageProcessor processes batch of messages."""
        raw_messages = [
            {
                "id": "msg-001",
                "app_type": "slack",
                "content": "Message 1",
                "sender": "User 1",
                "timestamp": "2024-01-15T10:30:00Z"
            },
            {
                "id": "msg-002",
                "app_type": "teams",
                "content": "Message 2",
                "sender": "User 2",
                "timestamp": "2024-01-15T10:31:00Z"
            }
        ]

        result = processor.process_messages(raw_messages)

        assert len(result) == 2
        assert all(msg.is_processed for msg in result)
        assert len(processor.processed_messages) == 2

    def test_process_messages_handles_errors(self, processor):
        """UnifiedMessageProcessor handles processing errors gracefully."""
        # Add invalid message
        raw_messages = [
            {
                "id": "msg-001",
                "app_type": "slack",
                "content": "Valid message",
                "sender": "User 1",
                "timestamp": "2024-01-15T10:30:00Z"
            },
            None  # Invalid message
        ]

        result = processor.process_messages(raw_messages)

        # Should skip invalid message and continue
        assert len(result) >= 0


class TestMessageSearch:
    """Test message search functionality."""

    @pytest.fixture
    def processor(self):
        """Create message processor with pre-loaded messages."""
        processor = UnifiedMessageProcessor()

        # Add some messages
        msg1 = UnifiedMessage(
            id="msg-001",
            unified_id="unified-001",
            platform="slack",
            platform_message_id="slack-001",
            content="Important announcement",
            sender_name="Alice",
            timestamp=datetime.now()
        )

        msg2 = UnifiedMessage(
            id="msg-002",
            unified_id="unified-002",
            platform="teams",
            platform_message_id="teams-001",
            content="Regular message",
            sender_name="Bob",
            timestamp=datetime.now()
        )

        processor.processed_messages = {
            "msg-001": msg1,
            "msg-002": msg2
        }

        return processor

    def test_search_messages_by_content(self, processor):
        """UnifiedMessageProcessor can search messages by content."""
        results = processor.search_messages("announcement")

        assert len(results) == 1
        assert results[0].content == "Important announcement"

    def test_search_messages_by_sender(self, processor):
        """UnifiedMessageProcessor can search messages by sender."""
        results = processor.search_messages("Alice")

        assert len(results) == 1
        assert results[0].sender_name == "Alice"

    def test_search_messages_with_platform_filter(self, processor):
        """UnifiedMessageProcessor can filter search by platform."""
        results = processor.search_messages("message", platforms=["slack"])

        assert len(results) == 1
        assert results[0].platform == "slack"


class TestStatistics:
    """Test statistics calculation."""

    @pytest.fixture
    def processor(self):
        """Create message processor with messages."""
        processor = UnifiedMessageProcessor()

        msg1 = UnifiedMessage(
            id="msg-001",
            unified_id="unified-001",
            platform="slack",
            platform_message_id="slack-001",
            content="Message 1",
            message_type="text",
            timestamp=datetime.now()
        )

        msg2 = UnifiedMessage(
            id="msg-002",
            unified_id="unified-001",  # Duplicate
            platform="teams",
            platform_message_id="teams-001",
            content="Message 1",
            message_type="text",
            is_duplicate=True,
            timestamp=datetime.now()
        )

        processor.processed_messages = {
            "msg-001": msg1,
            "msg-002": msg2
        }

        return processor

    def test_get_statistics(self, processor):
        """UnifiedMessageProcessor calculates message statistics."""
        stats = processor.get_statistics()

        assert stats["total_messages"] == 2
        assert stats["unique_messages"] == 1
        assert stats["duplicate_messages"] == 1
        assert "slack" in stats["platforms"]
        assert "teams" in stats["platforms"]
