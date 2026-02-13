"""
Comprehensive unit tests for UnifiedMessageProcessor class

Tests cover:
- Initialization and configuration
- Message normalization from different platforms
- Unified ID generation for deduplication
- Message type detection
- Duplicate and cross-post detection
- Conversation threading
- Message search and filtering
- Statistics and analytics
- Content enrichment (URLs, mentions)
- Platform-specific handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime, timedelta
from typing import Dict, Any, List
import hashlib

# Import the UnifiedMessageProcessor and related classes
from core.unified_message_processor import (
    UnifiedMessageProcessor,
    UnifiedMessage,
    MessageType,
    MessagePriority,
    get_unified_processor
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def message_processor():
    """Create a UnifiedMessageProcessor instance for testing"""
    return UnifiedMessageProcessor()


@pytest.fixture
def sample_slack_message():
    """Sample Slack message for testing"""
    return {
        "id": "slack-msg-123",
        "app_type": "slack",
        "content": "Hello from Slack!",
        "content_type": "text",
        "sender": "John Doe",
        "sender_email": "john@example.com",
        "timestamp": "2024-01-15T10:30:00Z",
        "recipient": "#general",
        "metadata": {
            "channel_id": "C12345",
            "channel_name": "general",
            "channel_type": "channel",
            "thread_id": "T12345",
            "sender_id": "U12345"
        },
        "attachments": [],
        "tags": [],
        "status": "active"
    }


@pytest.fixture
def sample_teams_message():
    """Sample Teams message for testing"""
    return {
        "id": "teams-msg-456",
        "app_type": "microsoft_teams",
        "content": "Meeting at 3pm",
        "content_type": "text",
        "sender": "Jane Smith <jane@example.com>",
        "timestamp": "2024-01-15T10:35:00Z",
        "recipient": "19:chat-id",
        "metadata": {
            "chat_type": "group",
            "thread_id": "thread-789",
            "conversation_id": "conv-456"
        },
        "attachments": [],
        "priority": "normal"
    }


@pytest.fixture
def sample_email_message():
    """Sample email message for testing"""
    return {
        "id": "email-msg-789",
        "app_type": "gmail",
        "content": "Project update attached",
        "subject": "Weekly Report",
        "content_type": "text",
        "sender": "bob@example.com",
        "sender_email": "bob@example.com",
        "timestamp": "2024-01-15T10:40:00Z",
        "recipient": "team@company.com",
        "metadata": {
            "thread_id": "email-thread-123",
            "conversation_id": "email-thread-123"
        },
        "attachments": [{"name": "report.pdf", "size": 1024}],
        "priority": "high"
    }


@pytest.fixture
def sample_html_message():
    """Sample HTML message for testing"""
    return {
        "id": "html-msg-001",
        "app_type": "slack",
        "content": "<div><p>HTML content</p></div>",
        "content_type": "html",
        "sender": "System",
        "timestamp": "2024-01-15T10:45:00Z",
        "metadata": {}
    }


# =============================================================================
# TEST PROCESSOR INITIALIZATION
# =============================================================================

class TestMessageProcessorInit:
    """Tests for UnifiedMessageProcessor initialization"""

    def test_init_creates_empty_state(self, message_processor):
        """Test that initialization creates empty dictionaries"""
        assert hasattr(message_processor, 'processed_messages')
        assert hasattr(message_processor, 'message_hashes')
        assert hasattr(message_processor, 'conversation_threads')
        assert hasattr(message_processor, 'cross_platform_map')
        assert len(message_processor.processed_messages) == 0
        assert len(message_processor.message_hashes) == set()
        assert len(message_processor.conversation_threads) == 0

    def test_global_singleton(self):
        """Test that get_unified_processor returns singleton instance"""
        processor1 = get_unified_processor()
        processor2 = get_unified_processor()
        assert processor1 is processor2


# =============================================================================
# TEST UNIFIED ID GENERATION
# =============================================================================

class TestUnifiedIdGeneration:
    """Tests for unified message ID generation"""

    def test_generate_unified_id_basic(self, message_processor):
        """Test basic unified ID generation"""
        content = "Hello World"
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        platform = "slack"

        unified_id = message_processor.generate_unified_id(content, timestamp, platform)

        assert isinstance(unified_id, str)
        assert len(unified_id) == 16  # SHA256 truncated to 16 chars

    def test_generate_unified_id_case_insensitive(self, message_processor):
        """Test that content case doesn't affect unified ID"""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        platform = "slack"

        id1 = message_processor.generate_unified_id("Hello", timestamp, platform)
        id2 = message_processor.generate_unified_id("hello", timestamp, platform)

        assert id1 == id2

    def test_generate_unified_id_different_platforms(self, message_processor):
        """Test that different platforms produce different IDs"""
        content = "Hello World"
        timestamp = datetime(2024, 1, 15, 10, 30, 0)

        slack_id = message_processor.generate_unified_id(content, timestamp, "slack")
        teams_id = message_processor.generate_unified_id(content, timestamp, "teams")

        assert slack_id != teams_id


# =============================================================================
# TEST MESSAGE NORMALIZATION
# =============================================================================

class TestMessageNormalization:
    """Tests for message normalization from different platforms"""

    def test_normalize_slack_message(self, message_processor, sample_slack_message):
        """Test normalizing a Slack message"""
        unified = message_processor.normalize_message(sample_slack_message)

        assert unified.platform == "slack"
        assert unified.content == "Hello from Slack!"
        assert unified.sender_name == "John Doe"
        assert unified.sender_email == "john@example.com"
        assert unified.channel_name == "general"
        assert unified.channel_type == "channel"
        assert unified.thread_id == "T12345"

    def test_normalize_teams_message(self, message_processor, sample_teams_message):
        """Test normalizing a Teams message"""
        unified = message_processor.normalize_message(sample_teams_message)

        assert unified.platform == "teams"
        assert unified.content == "Meeting at 3pm"
        assert unified.sender_name == "Jane Smith"
        assert unified.sender_email == "jane@example.com"
        assert unified.channel_type == "group_chat"

    def test_normalize_email_message(self, message_processor, sample_email_message):
        """Test normalizing an email message"""
        unified = message_processor.normalize_message(sample_email_message)

        assert unified.platform == "gmail"
        assert unified.content == "Project update attached"
        assert unified.subject == "Weekly Report"
        assert unified.has_attachments is True
        assert unified.channel_type == "email"

    def test_normalize_sender_parsing(self, message_processor):
        """Test parsing sender from 'Name <email>' format"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Test",
            "sender": "John Doe <john@example.com>",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {}
        }

        unified = message_processor.normalize_message(message)

        assert unified.sender_name == "John Doe"
        assert unified.sender_email == "john@example.com"

    def test_normalize_sender_email_only(self, message_processor):
        """Test parsing sender when only email is provided"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Test",
            "sender": "john@example.com",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {}
        }

        unified = message_processor.normalize_message(message)

        assert unified.sender_name == "john"
        assert unified.sender_email == "john@example.com"

    def test_normalize_timestamp_parsing(self, message_processor):
        """Test timestamp parsing from string"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Test",
            "sender": "User",
            "timestamp": "2024-01-15T10:30:00",
            "metadata": {}
        }

        unified = message_processor.normalize_message(message)

        assert isinstance(unified.timestamp, datetime)
        assert unified.timestamp.year == 2024

    def test_normalize_invalid_timestamp(self, message_processor):
        """Test handling of invalid timestamp"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Test",
            "sender": "User",
            "timestamp": "invalid-date",
            "metadata": {}
        }

        unified = message_processor.normalize_message(message)

        assert isinstance(unified.timestamp, datetime)


# =============================================================================
# TEST MESSAGE TYPE DETECTION
# =============================================================================

class TestMessageTypeDetection:
    """Tests for message type inference"""

    def test_infer_text_message(self, message_processor):
        """Test inferring text message type"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "This is a text message",
            "attachments": [],
            "metadata": {}
        }

        msg_type = message_processor._infer_message_type(message)

        assert msg_type == MessageType.TEXT.value

    def test_infer_html_message(self, message_processor):
        """Test inferring HTML message type"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "<div><p>HTML content</p></div>",
            "attachments": [],
            "metadata": {}
        }

        msg_type = message_processor._infer_message_type(message)

        assert msg_type == MessageType.HTML.value

    def test_infer_attachment_message(self, message_processor):
        """Test inferring attachment-only message type"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "",
            "attachments": [{"name": "file.pdf"}],
            "metadata": {}
        }

        msg_type = message_processor._infer_message_type(message)

        assert msg_type == MessageType.ATTACHMENT.value

    def test_infer_system_message(self, message_processor):
        """Test inferring system/bot message type"""
        message = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "",
            "attachments": [],
            "metadata": {"bot_id": "B12345"}
        }

        msg_type = message_processor._infer_message_type(message)

        assert msg_type == MessageType.SYSTEM.value


# =============================================================================
# TEST CONTENT ENRICHMENT
# =============================================================================

class TestContentEnrichment:
    """Tests for content enrichment"""

    def test_enrich_urls(self, message_processor):
        """Test URL extraction from content"""
        raw_msg = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Check out https://example.com and http://test.org",
            "sender": "User",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {}
        }

        unified = message_processor.normalize_message(raw_msg)

        assert len(unified.urls) == 2
        assert "https://example.com" in unified.urls
        assert "http://test.org" in unified.urls

    def test_enrich_slack_mentions(self, message_processor):
        """Test Slack mention extraction"""
        raw_msg = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Hey <@U12345> and <@U67890>",
            "sender": "User",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {}
        }

        unified = message_processor.normalize_message(raw_msg)

        assert len(unified.mentions) == 2
        assert "U12345" in unified.mentions

    def test_enrich_email_mentions(self, message_processor):
        """Test email address extraction"""
        raw_msg = {
            "id": "msg-001",
            "app_type": "gmail",
            "content": "Contact john@example.com or jane@test.org",
            "sender": "User",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {}
        }

        unified = message_processor.normalize_message(raw_msg)

        assert len(unified.mentions) >= 1

    def test_enrich_platform_tag(self, message_processor):
        """Test that platform tag is added"""
        raw_msg = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Test",
            "sender": "User",
            "timestamp": "2024-01-15T10:30:00Z",
            "metadata": {}
        }

        unified = message_processor.normalize_message(raw_msg)

        assert "slack" in unified.tags

    def test_enrich_attachment_tag(self, message_processor):
        """Test that attachment tag is added when present"""
        raw_msg = {
            "id": "msg-001",
            "app_type": "slack",
            "content": "Test",
            "sender": "User",
            "timestamp": "2024-01-15T10:30:00Z",
            "attachments": [{"name": "file.pdf"}],
            "metadata": {}
        }

        unified = message_processor.normalize_message(raw_msg)

        assert "has_attachments" in unified.tags


# =============================================================================
# TEST DUPLICATE DETECTION
# =============================================================================

class TestDuplicateDetection:
    """Tests for duplicate and cross-post detection"""

    def test_detect_duplicates_same_content(self, message_processor):
        """Test detecting duplicate messages with same content"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Same content",
            timestamp=datetime(2024, 1, 15, 10, 0, 0)
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="teams",
            platform_message_id="teams-1",
            content="Same content",
            timestamp=datetime(2024, 1, 15, 10, 5, 0)
        )

        unique, duplicates = message_processor.detect_duplicates([msg1, msg2])

        assert len(unique) == 1
        assert len(duplicates) == 1
        assert unique[0].is_cross_posted is True
        assert unique[0].related_message_ids == ["msg-2"]

    def test_detect_no_duplicates(self, message_processor):
        """Test when no duplicates exist"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Content one",
            timestamp=datetime(2024, 1, 15, 10, 0, 0)
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="teams",
            platform_message_id="teams-1",
            content="Content two",
            timestamp=datetime(2024, 1, 15, 10, 5, 0)
        )

        unique, duplicates = message_processor.detect_duplicates([msg1, msg2])

        assert len(unique) == 2
        assert len(duplicates) == 0

    def test_detect_duplicates_timestamp_ordering(self, message_processor):
        """Test that earliest message is marked as original"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Same content",
            timestamp=datetime(2024, 1, 15, 10, 5, 0)  # Later
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="teams",
            platform_message_id="teams-1",
            content="Same content",
            timestamp=datetime(2024, 1, 15, 10, 0, 0)  # Earlier
        )

        unique, duplicates = message_processor.detect_duplicates([msg1, msg2])

        assert unique[0].id == "msg-2"  # Earlier message is original
        assert msg1.is_duplicate is True


# =============================================================================
# TEST CONVERSATION THREADING
# =============================================================================

class TestConversationThreading:
    """Tests for conversation threading"""

    def test_create_conversation_threads(self, message_processor):
        """Test creating conversation threads"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="First message",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            conversation_id="conv-1"
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="slack",
            platform_message_id="slack-2",
            content="Second message",
            timestamp=datetime(2024, 1, 15, 10, 5, 0),
            conversation_id="conv-1"
        )

        # Add to processed messages
        message_processor.processed_messages["msg-1"] = msg1
        message_processor.processed_messages["msg-2"] = msg2

        threads = message_processor.create_conversation_threads([msg1, msg2])

        assert "conv-1" in threads
        assert len(threads["conv-1"]) == 2

    def test_create_thread_from_thread_id(self, message_processor):
        """Test creating thread when conversation_id is missing"""
        msg = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Message",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            thread_id="thread-1",
            channel_id="channel-1"
        )

        message_processor.processed_messages["msg-1"] = msg

        threads = message_processor.create_conversation_threads([msg])

        assert "slack_channel-1_conversation" in threads

    def test_thread_sorting_by_timestamp(self, message_processor):
        """Test that messages in threads are sorted by timestamp"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="First",
            timestamp=datetime(2024, 1, 15, 10, 5, 0),
            conversation_id="conv-1"
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="slack",
            platform_message_id="slack-2",
            content="Second",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            conversation_id="conv-1"
        )

        message_processor.processed_messages["msg-1"] = msg1
        message_processor.processed_messages["msg-2"] = msg2

        threads = message_processor.create_conversation_threads([msg1, msg2])

        assert threads["conv-1"][0] == "msg-2"  # Earlier message first


# =============================================================================
# TEST MESSAGE PROCESSING
# =============================================================================

class TestMessageProcessing:
    """Tests for batch message processing"""

    @pytest.mark.asyncio
    async def test_process_messages(self, message_processor, sample_slack_message, sample_teams_message):
        """Test processing a batch of messages"""
        raw_messages = [sample_slack_message, sample_teams_message]

        processed = message_processor.process_messages(raw_messages)

        assert len(processed) == 2
        assert all(msg.is_processed for msg in processed)
        assert len(message_processor.processed_messages) == 2

    @pytest.mark.asyncio
    async def test_process_messages_with_error(self, message_processor, sample_slack_message):
        """Test handling errors during message processing"""
        # Add an invalid message
        invalid_msg = {"id": "invalid"}  # Missing required fields

        raw_messages = [sample_slack_message, invalid_msg]

        processed = message_processor.process_messages(raw_messages)

        # Should process valid message and skip invalid one
        assert len(processed) == 1


# =============================================================================
# TEST MESSAGE SEARCH
# =============================================================================

class TestMessageSearch:
    """Tests for message search functionality"""

    def test_search_messages_by_content(self, message_processor):
        """Test searching messages by content"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Project deadline tomorrow",
            timestamp=datetime(2024, 1, 15, 10, 0, 0)
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="teams",
            platform_message_id="teams-1",
            content="Meeting at 3pm",
            timestamp=datetime(2024, 1, 15, 10, 5, 0)
        )

        message_processor.processed_messages["msg-1"] = msg1
        message_processor.processed_messages["msg-2"] = msg2

        results = message_processor.search_messages("deadline")

        assert len(results) == 1
        assert results[0].id == "msg-1"

    def test_search_messages_by_platform(self, message_processor):
        """Test filtering messages by platform"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Test",
            timestamp=datetime(2024, 1, 15, 10, 0, 0)
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="teams",
            platform_message_id="teams-1",
            content="Test",
            timestamp=datetime(2024, 1, 15, 10, 5, 0)
        )

        message_processor.processed_messages["msg-1"] = msg1
        message_processor.processed_messages["msg-2"] = msg2

        results = message_processor.search_messages("Test", platforms=["slack"])

        assert len(results) == 1
        assert results[0].platform == "slack"

    def test_search_messages_skip_duplicates(self, message_processor):
        """Test that duplicate messages are excluded from search"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Test",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            is_duplicate=False
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="teams",
            platform_message_id="teams-1",
            content="Test",
            timestamp=datetime(2024, 1, 15, 10, 5, 0),
            is_duplicate=True
        )

        message_processor.processed_messages["msg-1"] = msg1
        message_processor.processed_messages["msg-2"] = msg2

        results = message_processor.search_messages("Test")

        assert len(results) == 1
        assert results[0].id == "msg-1"


# =============================================================================
# TEST STATISTICS
# =============================================================================

class TestStatistics:
    """Tests for message statistics"""

    def test_get_statistics_empty(self, message_processor):
        """Test statistics with no messages"""
        stats = message_processor.get_statistics()

        assert stats["total_messages"] == 0
        assert stats["unique_messages"] == 0
        assert stats["duplicate_messages"] == 0

    def test_get_statistics_with_messages(self, message_processor):
        """Test statistics with processed messages"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Test",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            is_duplicate=False
        )

        msg2 = UnifiedMessage(
            id="msg-2",
            unified_id="def456",
            platform="teams",
            platform_message_id="teams-1",
            content="Test",
            timestamp=datetime(2024, 1, 15, 10, 5, 0),
            is_duplicate=True
        )

        message_processor.processed_messages["msg-1"] = msg1
        message_processor.processed_messages["msg-2"] = msg2

        stats = message_processor.get_statistics()

        assert stats["total_messages"] == 2
        assert stats["unique_messages"] == 1
        assert stats["duplicate_messages"] == 1
        assert "slack" in stats["platforms"]
        assert "teams" in stats["platforms"]

    def test_get_statistics_cross_posts(self, message_processor):
        """Test statistics with cross-posted messages"""
        msg1 = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Test",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            is_cross_posted=True
        )

        message_processor.processed_messages["msg-1"] = msg1

        stats = message_processor.get_statistics()

        assert stats["cross_platform_posts"] == 1


# =============================================================================
# TEST TO_DICT
# =============================================================================

class TestToDict:
    """Tests for UnifiedMessage.to_dict method"""

    def test_to_dict_basic(self):
        """Test converting message to dictionary"""
        msg = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Test content",
            timestamp=datetime(2024, 1, 15, 10, 0, 0)
        )

        msg_dict = msg.to_dict()

        assert msg_dict["id"] == "msg-1"
        assert msg_dict["unified_id"] == "abc123"
        assert msg_dict["platform"] == "slack"
        assert msg_dict["content"] == "Test content"
        assert msg_dict["timestamp"] == "2024-01-15T10:00:00"

    def test_to_dict_with_optional_fields(self):
        """Test converting message with all fields to dictionary"""
        msg = UnifiedMessage(
            id="msg-1",
            unified_id="abc123",
            platform="slack",
            platform_message_id="slack-1",
            content="Test",
            subject="Test Subject",
            sender_name="John Doe",
            sender_email="john@example.com",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            tags=["tag1", "tag2"],
            mentions=["user1"],
            urls=["https://example.com"]
        )

        msg_dict = msg.to_dict()

        assert msg_dict["subject"] == "Test Subject"
        assert msg_dict["sender_email"] == "john@example.com"
        assert len(msg_dict["tags"]) == 2
        assert len(msg_dict["mentions"]) == 1
        assert len(msg_dict["urls"]) == 1
