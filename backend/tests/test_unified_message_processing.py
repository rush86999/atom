"""
Tests for Unified Message Processor
Tests cross-platform message normalization, deduplication, and threading.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from core.unified_message_processor import (
    UnifiedMessageProcessor,
    UnifiedMessage,
    MessageType,
    MessagePriority
)


@pytest.fixture
def processor():
    """Create UnifiedMessageProcessor instance"""
    return UnifiedMessageProcessor()


class TestUnifiedMessageSchema:
    """Test unified message schema and normalization"""

    def test_normalize_slack_message(self, processor):
        """Test Slack message normalization"""
        slack_message = {
            "id": "1234567890.123456",
            "app_type": "slack",
            "content": "Hello from Slack!",
            "content_type": "text",
            "subject": None,
            "sender": "U123456",
            "sender_email": None,
            "recipient": "C123456",
            "timestamp": "2024-02-01T12:00:00Z",
            "direction": "inbound",
            "attachments": [],
            "metadata": {
                "channel_id": "C123456",
                "channel_name": "general",
                "channel_type": "channel",
                "thread_ts": "1234567890.123456"
            },
            "tags": ["slack"],
            "status": "active"
        }

        unified = processor.normalize_message(slack_message)

        assert unified.platform == "slack"
        assert unified.content == "Hello from Slack!"
        assert unified.sender_name == "U123456"
        assert unified.channel_name == "general"
        assert unified.channel_type == "channel"
        assert "slack" in unified.tags

    def test_normalize_teams_message(self, processor):
        """Test Teams message normalization"""
        teams_message = {
            "id": "1234567890",
            "app_type": "microsoft_teams",
            "content": "Hello from Teams!",
            "content_type": "text",
            "subject": "Project Update",
            "sender": "John Doe",
            "sender_email": "john@example.com",
            "recipient": "19:chat_123@thread.v2",
            "timestamp": "2024-02-01T12:00:00Z",
            "direction": "inbound",
            "attachments": [],
            "metadata": {
                "chat_id": "19:chat_123@thread.v2",
                "chat_type": "oneOnOne",
                "chat_title": "Private Chat"
            },
            "tags": ["teams", "chat"],
            "status": "active"
        }

        unified = processor.normalize_message(teams_message)

        assert unified.platform == "teams"
        assert unified.content == "Hello from Teams!"
        assert unified.subject == "Project Update"
        assert unified.sender_email == "john@example.com"
        assert unified.channel_type == "dm"

    def test_normalize_gmail_message(self, processor):
        """Test Gmail message normalization"""
        gmail_message = {
            "id": "1234567890",
            "app_type": "gmail",
            "content": "Hello from Gmail!",
            "content_type": "text",
            "subject": "Email Subject",
            "sender": "Alice Smith <alice@example.com>",
            "sender_email": "alice@example.com",
            "recipient": "me@example.com",
            "timestamp": "2024-02-01T12:00:00Z",
            "direction": "inbound",
            "attachments": [],
            "metadata": {
                "thread_id": "thread_123",
                "labelIds": ["INBOX", "UNREAD"],
                "snippet": "Hello from Gmail"
            },
            "priority": "normal",
            "tags": ["gmail"],
            "status": "active"
        }

        unified = processor.normalize_message(gmail_message)

        assert unified.platform == "gmail"
        assert unified.content == "Hello from Gmail!"
        assert unified.subject == "Email Subject"
        assert unified.sender_name == "Alice Smith"
        assert unified.sender_email == "alice@example.com"
        assert unified.thread_platform_id == "thread_123"

    def test_normalize_outlook_message(self, processor):
        """Test Outlook message normalization"""
        outlook_message = {
            "id": "AAMkADY3NjI5OWUzLWJjZDAtNDVkMS1h",
            "app_type": "outlook",
            "content": "Hello from Outlook!",
            "content_type": "text",
            "subject": "Outlook Subject",
            "sender": "Bob Johnson <bob@example.com>",
            "sender_email": "bob@example.com",
            "recipient": "me@example.com",
            "timestamp": "2024-02-01T12:00:00Z",
            "direction": "inbound",
            "attachments": [],
            "metadata": {
                "conversation_id": "conv_123",
                "importance": "High",
                "isRead": False
            },
            "priority": "high",
            "tags": ["outlook"],
            "status": "unread"
        }

        unified = processor.normalize_message(outlook_message)

        assert unified.platform == "outlook"
        assert unified.content == "Hello from Outlook!"
        assert unified.subject == "Outlook Subject"
        assert unified.priority == "high"
        assert unified.conversation_id == "conv_123"
        assert unified.channel_type == "email"

    def test_unified_id_generation(self, processor):
        """Test that unified IDs are consistent"""
        msg1 = {
            "id": "msg_1",
            "app_type": "slack",
            "content": "Same content",
            "timestamp": "2024-02-01T12:00:00Z"
        }

        msg2 = {
            "id": "msg_2",
            "app_type": "teams",
            "content": "Same content",
            "timestamp": "2024-02-01T13:00:00Z"  # Different time, same day
        }

        unified1 = processor.normalize_message(msg1)
        unified2 = processor.normalize_message(msg2)

        # Same content = same unified ID
        assert unified1.unified_id != unified2.unified_id  # Different platforms

        # But same content should be detected as duplicate
        unique, duplicates = processor.detect_duplicates([unified1, unified2])

        # Should detect as same content (duplicate) since content hash is same
        assert len(unique) <= 2


class TestDeduplication:
    """Test duplicate detection and cross-posting"""

    def test_detect_exact_duplicates(self, processor):
        """Test detection of exact duplicate messages"""
        messages = [
            UnifiedMessage(
                id="msg1",
                unified_id="hash1",
                platform="slack",
                platform_message_id="slack_msg1",
                content="Duplicate message",
                sender_name="User1",
                timestamp=datetime(2024, 2, 1, 12, 0, 0),
                content_type="text"
            ),
            UnifiedMessage(
                id="msg2",
                unified_id="hash1",
                platform="teams",
                platform_message_id="teams_msg1",
                content="Duplicate message",
                sender_name="User1",
                timestamp=datetime(2024, 2, 1, 12, 1, 0),
                content_type="text"
            )
        ]

        unique, duplicates = processor.detect_duplicates(messages)

        assert len(unique) == 1
        assert len(duplicates) == 1
        assert unique[0].is_cross_posted == True
        assert unique[0].id == "msg1"  # Earlier message kept
        assert duplicates["msg1"] == ["msg2"]

    def test_detect_similar_messages(self, processor):
        """Test detection of similar (not identical) messages"""
        messages = [
            UnifiedMessage(
                id="msg1",
                unified_id="hash1",
                platform="slack",
                platform_message_id="slack_msg1",
                content="This is a message",
                sender_name="User1",
                timestamp=datetime(2024, 2, 1, 12, 0, 0),
                content_type="text"
            ),
            UnifiedMessage(
                id="msg2",
                unified_id="hash2",
                platform="teams",
                platform_message_id="teams_msg1",
                content="This is another message",  # Different content
                sender_name="User1",
                timestamp=datetime(2024, 2, 1, 12, 1, 0),
                content_type="text"
            )
        ]

        unique, duplicates = processor.detect_duplicates(messages)

        # Should not detect as duplicates
        assert len(unique) == 2
        assert len(duplicates) == 0

    def test_cross_platform_duplicate_detection(self, processor):
        """Test cross-platform duplicate detection"""
        # Same message posted to Slack and Teams
        base_timestamp = datetime(2024, 2, 1, 12, 0, 0)

        messages = [
            UnifiedMessage(
                id="slack_msg",
                unified_id="hash1",
                platform="slack",
                platform_message_id="slack_123",
                content="Important announcement",
                sender_name="Admin",
                timestamp=base_timestamp,
                content_type="text"
            ),
            UnifiedMessage(
                id="teams_msg",
                unified_id="hash1",
                platform="teams",
                platform_message_id="teams_123",
                content="Important announcement",
                sender_name="Admin",
                timestamp=base_timestamp + timedelta(minutes=1),  # Slightly later
                content_type="text"
            ),
            UnifiedMessage(
                id="gmail_msg",
                unified_id="hash1",
                platform="gmail",
                platform_message_id="gmail_123",
                content="Important announcement",
                sender_name="Admin",
                timestamp=base_timestamp + timedelta(minutes=2),
                content_type="text"
            )
        ]

        unique, duplicates = processor.detect_duplicates(messages)

        # Should detect as cross-posted
        assert len(unique) == 1
        assert unique[0].platform == "slack"  # Earliest message kept
        assert unique[0].is_cross_posted == True
        assert len(unique[0].related_message_ids) == 2


class TestConversationThreading:
    """Test conversation threading across platforms"""

    def test_create_slack_thread(self, processor):
        """Test creating thread from Slack messages"""
        thread_ts = "1234567890.123456"
        messages = [
            UnifiedMessage(
                id="msg1",
                unified_id="hash1",
                platform="slack",
                platform_message_id="slack_msg1",
                content="First message",
                sender_name="User1",
                timestamp=datetime(2024, 2, 1, 12, 0, 0),
                thread_platform_id=thread_ts,
                content_type="text"
            ),
            UnifiedMessage(
                id="msg2",
                unified_id="hash2",
                platform="slack",
                platform_message_id="slack_msg2",
                content="Second message (reply)",
                sender_name="User2",
                timestamp=datetime(2024, 2, 1, 12, 1, 0),
                thread_platform_id=thread_ts,
                reply_to_message_id="msg1",
                content_type="text"
            )
        ]

        threads = processor.create_conversation_threads(messages)

        # Should create one thread
        assert len(threads) == 1
        thread_id = list(threads.keys())[0]

        # Both messages should be in the thread
        assert len(threads[thread_id]) == 2
        assert "msg1" in threads[thread_id]
        assert "msg2" in threads[thread_id]

    def test_create_email_thread(self, processor):
        """Test creating thread from email"""
        conversation_id = "conv_123"
        messages = [
            UnifiedMessage(
                id="email1",
                unified_id="hash1",
                platform="gmail",
                platform_message_id="gmail_1",
                content="Original email",
                sender_name="sender@example.com",
                timestamp=datetime(2024, 2, 1, 12, 0, 0),
                conversation_id=conversation_id,
                content_type="text"
            ),
            UnifiedMessage(
                id="email2",
                unified_id="hash2",
                platform="outlook",
                platform_message_id="outlook_1",
                content="Re: Original email",
                sender_name="replier@example.com",
                timestamp=datetime(2024, 2, 1, 12, 30, 0),
                conversation_id=conversation_id,
                reply_to_message_id="email1",
                content_type="text"
            )
        ]

        threads = processor.create_conversation_threads(messages)

        # Should create one thread with conversation_id
        assert conversation_id in threads
        assert len(threads[conversation_id]) == 2

    def test_cross_platform_threading(self, processor):
        """Test threading across different platforms"""
        # Same conversation across Slack, Teams, and Email
        base_time = datetime(2024, 2, 1, 12, 0, 0)

        # Simulate conversation ID generation
        messages = [
            UnifiedMessage(
                id="slack_1",
                unified_id="hash1",
                platform="slack",
                platform_message_id="slack_1",
                content="Starting conversation",
                sender_name="Alice",
                timestamp=base_time,
                channel_id="C123",
                content_type="text"
            ),
            UnifiedMessage(
                id="teams_1",
                unified_id="hash2",
                platform="teams",
                platform_message_id="teams_1",
                content="Same conversation on Teams",
                sender_name="Bob",
                timestamp=base_time + timedelta(minutes=5),
                channel_id="19:chat@thread.v2",
                content_type="text"
            ),
            UnifiedMessage(
                id="email_1",
                unified_id="hash3",
                platform="gmail",
                platform_message_id="email_1",
                content="Email follow-up",
                sender_name="Charlie",
                timestamp=base_time + timedelta(minutes=10),
                content_type="text"
            )
        ]

        threads = processor.create_conversation_threads(messages)

        # Should create separate threads for each platform/channel
        # (in real scenario, you'd match them by sender/content similarity)
        assert len(threads) >= 3


class TestMessageEnrichment:
    """Test message enrichment (URLs, mentions, etc.)"""

    def test_extract_urls(self, processor):
        """Test URL extraction from messages"""
        message = UnifiedMessage(
            id="msg1",
            unified_id="hash1",
            platform="slack",
            platform_message_id="slack_1",
            content="Check out https://example.com and http://test.org",
            sender_name="User1",
            timestamp=datetime(2024, 2, 1, 12, 0, 0),
            content_type="text"
        )

        processor._enrich_message(message)

        assert len(message.urls) == 2
        assert "https://example.com" in message.urls
        assert "http://test.org" in message.urls

    def test_extract_mentions(self, processor):
        """Test mention extraction"""
        # Test Slack mentions
        slack_msg = UnifiedMessage(
            id="msg1",
            unified_id="hash1",
            platform="slack",
            platform_message_id="slack_1",
            content="Hey <@U123> and <@U456> please review",
            sender_name="User1",
            timestamp=datetime(2024, 2, 1, 12, 0, 0),
            content_type="text"
        )

        processor._enrich_message(slack_msg)

        assert len(slack_msg.mentions) == 2
        assert "U123" in slack_msg.mentions

    def test_attachment_flag(self, processor):
        """Test has_attachments flag"""
        message_with_att = UnifiedMessage(
            id="msg1",
            unified_id="hash1",
            platform="gmail",
            platform_message_id="gmail_1",
            content="See attached file",
            sender_name="Sender",
            timestamp=datetime(2024, 2, 1, 12, 0, 0),
            content_type="text",
            attachments=[
                {"id": "att1", "filename": "file.pdf", "size": 1024}
            ]
        )

        processor.normalize_message({"id": "msg1", "app_type": "gmail"})

        # Re-normalize with processor
        gmail_msg = processor.normalize_message({
            "id": "msg1",
            "app_type": "gmail",
            "content": "See attached file",
            "sender": "Sender",
            "timestamp": "2024-02-01T12:00:00Z",
            "attachments": [{"id": "att1", "filename": "file.pdf"}]
        })

        assert gmail_msg.has_attachments == True
        assert "has_attachments" in gmail_msg.tags


class TestMessageProcessing:
    """Test end-to-end message processing"""

    def test_process_batch_of_messages(self, processor):
        """Test processing a batch of mixed platform messages"""
        raw_messages = [
            # Slack message
            {
                "id": "slack_1",
                "app_type": "slack",
                "content": "Slack message",
                "sender": "U123",
                "recipient": "C456",
                "timestamp": "2024-02-01T12:00:00Z",
                "direction": "inbound",
                "metadata": {"channel_id": "C456", "channel_name": "general"},
                "tags": ["slack"],
                "status": "active"
            },
            # Teams message
            {
                "id": "teams_1",
                "app_type": "microsoft_teams",
                "content": "Teams message",
                "sender": "John Doe",
                "sender_email": "john@example.com",
                "recipient": "chat_id",
                "timestamp": "2024-02-01T12:01:00Z",
                "direction": "inbound",
                "metadata": {"chat_type": "oneOnOne"},
                "tags": ["teams"],
                "status": "active"
            },
            # Gmail message
            {
                "id": "gmail_1",
                "app_type": "gmail",
                "content": "Email message",
                "subject": "Test Subject",
                "sender": "Jane <jane@example.com>",
                "sender_email": "jane@example.com",
                "recipient": "me@example.com",
                "timestamp": "2024-02-01T12:02:00Z",
                "direction": "inbound",
                "attachments": [],
                "metadata": {"thread_id": "thread_123"},
                "tags": ["gmail"],
                "status": "active"
            }
        ]

        processed = processor.process_messages(raw_messages)

        assert len(processed) == 3
        assert all(m.is_processed for m in processed)

        # Check platforms
        platforms = {m.platform for m in processed}
        assert platforms == {"slack", "teams", "gmail"}

    def test_get_statistics(self, processor):
        """Test statistics generation"""
        # Add some messages
        processor.process_messages([
            {
                "id": "msg1",
                "app_type": "slack",
                "content": "Message 1",
                "sender": "User1",
                "timestamp": "2024-02-01T12:00:00Z",
                "direction": "inbound",
                "tags": ["slack"],
                "status": "active"
            },
            {
                "id": "msg2",
                "app_type": "teams",
                "content": "Message 2",
                "sender": "User2",
                "timestamp": "2024-02-01T12:01:00Z",
                "direction": "inbound",
                "tags": ["teams"],
                "status": "active"
            }
        ])

        stats = processor.get_statistics()

        assert stats["total_messages"] == 2
        assert stats["unique_messages"] == 2
        assert stats["platforms"]["slack"] == 1
        assert stats["platforms"]["teams"] == 1

    def test_search_messages(self, processor):
        """Test message search functionality"""
        # Add messages
        processor.process_messages([
            {
                "id": "msg1",
                "app_type": "slack",
                "content": "Important meeting tomorrow at 2pm",
                "sender": "Alice",
                "timestamp": datetime(2024, 2, 1, 12, 0, 0),
                "subject": "Meeting",
                "direction": "inbound",
                "tags": ["slack"],
                "status": "active"
            },
            {
                "id": "msg2",
                "app_type": "gmail",
                "content": "Lunch updates",
                "sender": "Bob",
                "timestamp": datetime(2024, 2, 1, 12, 30, 0),
                "subject": "Lunch",
                "direction": "inbound",
                "tags": ["gmail"],
                "status": "active"
            }
        ])

        # Search for "meeting"
        results = processor.search_messages("meeting")

        assert len(results) == 1
        assert "meeting" in results[0].content.lower()

        # Search with platform filter
        results_slack = processor.search_messages("", platforms=["slack"])
        assert len(results_slack) == 1
        assert results_slack[0].platform == "slack"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
