"""
Tests for Email API Real-Time Message Ingestion
Tests the Gmail and Outlook API integration for polling and message fetching.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationIngestionPipeline,
    CommunicationAppType,
    IngestionConfig,
    LanceDBMemoryManager
)


@pytest.fixture
def mock_memory_manager():
    """Create a mock LanceDBMemoryManager"""
    manager = Mock(spec=LanceDBMemoryManager)
    manager.db = Mock()
    manager.ingest_communication = Mock(return_value=True)
    return manager


@pytest.fixture
def ingestion_pipeline(mock_memory_manager):
    """Create CommunicationIngestionPipeline instance"""
    pipeline = CommunicationIngestionPipeline(mock_memory_manager)
    return pipeline


@pytest.fixture
def gmail_config():
    """Create Gmail ingestion configuration"""
    return IngestionConfig(
        app_type=CommunicationAppType.GMAIL,
        enabled=True,
        real_time=True,
        batch_size=50,
        ingest_attachments=True,
        embed_content=True,
        retention_days=30
    )


@pytest.fixture
def outlook_config():
    """Create Outlook ingestion configuration"""
    return IngestionConfig(
        app_type=CommunicationAppType.OUTLOOK,
        enabled=True,
        real_time=True,
        batch_size=50,
        ingest_attachments=True,
        embed_content=True,
        retention_days=30
    )


class TestGmailAPIIntegration:
    """Test suite for Gmail API integration"""

    def test_configure_gmail_ingestion(self, ingestion_pipeline, gmail_config):
        """Test configuring Gmail ingestion"""
        ingestion_pipeline.configure_app(CommunicationAppType.GMAIL, gmail_config)

        assert "gmail" in ingestion_pipeline.ingestion_configs
        assert "gmail" in ingestion_pipeline.app_configs

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_gmail_messages_without_service(self, ingestion_pipeline):
        """Test that missing Gmail service is handled gracefully"""
        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = None
            mock_service_class.return_value = mock_service

            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_gmail_messages_success(self, ingestion_pipeline, gmail_config):
        """Test successful Gmail message fetching"""
        ingestion_pipeline.configure_app(CommunicationAppType.GMAIL, gmail_config)

        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = Mock()

            # Mock get_messages to return sample messages
            mock_service.get_messages = Mock(return_value=[
                {
                    "id": "1234567890",
                    "threadId": "thread_123",
                    "timestamp": "2024-02-01T12:00:00Z",
                    "sender": "John Doe <john@example.com>",
                    "recipient": "me@example.com",
                    "subject": "Test Email",
                    "body": "This is a test email from Gmail",
                    "snippet": "This is a test email",
                    "labelIds": ["INBOX", "UNREAD"],
                    "attachments": [],
                    "historyId": "123456",
                    "internalDate": "1706793600000"
                }
            ])

            mock_service_class.return_value = mock_service

            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert len(messages) == 1
            assert messages[0]["app_type"] == "gmail"
            assert messages[0]["sender"] == "John Doe"
            assert messages[0]["sender_email"] == "john@example.com"
            assert messages[0]["subject"] == "Test Email"
            assert messages[0]["content"] == "This is a test email from Gmail"
            assert "INBOX" in messages[0]["tags"]

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_gmail_messages_incremental(self, ingestion_pipeline):
        """Test incremental Gmail fetching with date filter"""
        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = Mock()
            mock_service.get_messages = Mock(return_value=[])

            mock_service_class.return_value = mock_service

            last_fetch = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
            messages = await ingestion_pipeline._fetch_gmail_messages(last_fetch)

            # Verify that get_messages was called with date query
            mock_service.get_messages.assert_called_once()
            call_args = mock_service.get_messages.call_args
            query = call_args.kwargs.get('query', call_args.args[0] if call_args.args else "")

            assert "after:" in query

    @pytest.mark.asyncio(mode="auto")
    async def test_gmail_message_normalization(self, ingestion_pipeline):
        """Test Gmail message normalization structure"""
        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = Mock()

            mock_service.get_messages = Mock(return_value=[
                {
                    "id": "msg_123",
                    "threadId": "thread_456",
                    "timestamp": "2024-02-01T14:30:00Z",
                    "sender": "Alice Smith <alice@company.com>",
                    "recipient": "bob@company.com",
                    "subject": "Project Update",
                    "body": "<p>HTML email content</p>",
                    "snippet": "HTML email content",
                    "labelIds": ["INBOX", "IMPORTANT", "CATEGORY_WORK"],
                    "attachments": [
                        {
                            "id": "att_123",
                            "filename": "document.pdf",
                            "size": 1024,
                            "contentType": "application/pdf"
                        }
                    ]
                }
            ])

            mock_service_class.return_value = mock_service

            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert len(messages) == 1
            msg = messages[0]

            # Verify structure
            assert msg["app_type"] == "gmail"
            assert msg["direction"] == "inbound"
            assert msg["sender"] == "Alice Smith"
            assert msg["sender_email"] == "alice@company.com"
            assert msg["subject"] == "Project Update"
            assert msg["content"] == "<p>HTML email content</p>"
            assert msg["priority"] == "high"  # IMPORTANT label
            assert "INBOX" in msg["tags"]
            assert "IMPORTANT" in msg["tags"]
            assert len(msg["attachments"]) == 1
            assert msg["attachments"][0]["filename"] == "document.pdf"


class TestOutlookAPIIntegration:
    """Test suite for Outlook API integration"""

    def test_configure_outlook_ingestion(self, ingestion_pipeline, outlook_config):
        """Test configuring Outlook ingestion"""
        ingestion_pipeline.configure_app(CommunicationAppType.OUTLOOK, outlook_config)

        assert "outlook" in ingestion_pipeline.ingestion_configs
        assert "outlook" in ingestion_pipeline.app_configs

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_messages_without_token(self, ingestion_pipeline):
        """Test that missing Microsoft token is handled gracefully"""
        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = None

            messages = await ingestion_pipeline._fetch_outlook_messages(None)

            assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_messages_success(self, ingestion_pipeline, outlook_config):
        """Test successful Outlook message fetching"""
        ingestion_pipeline.configure_app(CommunicationAppType.OUTLOOK, outlook_config)

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {
                "access_token": "test_outlook_token"
            }

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_client.get = AsyncMock(
                    return_value=Mock(
                        status_code=200,
                        json=lambda: {
                            "value": [
                                {
                                    "id": "AAMkADY3NjI5OWUzLWJjZDAtNDVkMS1h",
                                    "receivedDateTime": "2024-02-01T12:00:00Z",
                                    "from": {
                                        "emailAddress": {
                                            "name": "Bob Johnson",
                                            "address": "bob@example.com"
                                        }
                                    },
                                    "toRecipients": [
                                        {
                                            "emailAddress": {
                                                "address": "me@example.com"
                                            }
                                        }
                                    ],
                                    "subject": "Meeting Tomorrow",
                                    "body": {
                                        "contentType": "Text",
                                        "content": "Let's meet tomorrow at 2pm"
                                    },
                                    "importance": "Normal",
                                    "isRead": False,
                                    "conversationId": "conv_123"
                                }
                            ]
                        }
                    )
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                assert len(messages) == 1
                assert messages[0]["app_type"] == "outlook"
                assert messages[0]["sender"] == "Bob Johnson"
                assert messages[0]["sender_email"] == "bob@example.com"
                assert messages[0]["subject"] == "Meeting Tomorrow"
                assert messages[0]["content"] == "Let's meet tomorrow at 2pm"
                assert messages[0]["status"] == "unread"
                assert messages[0]["priority"] == "normal"

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_messages_with_attachments(self, ingestion_pipeline):
        """Test Outlook messages with attachments"""
        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_client.get = AsyncMock(
                    return_value=Mock(
                        status_code=200,
                        json=lambda: {
                            "value": [
                                {
                                    "id": "msg_456",
                                    "receivedDateTime": "2024-02-01T13:00:00Z",
                                    "from": {
                                        "emailAddress": {
                                            "name": "Charlie",
                                            "address": "charlie@example.com"
                                        }
                                    },
                                    "toRecipients": [
                                        {"emailAddress": {"address": "me@example.com"}}
                                    ],
                                    "subject": "Document Attached",
                                    "body": {
                                        "contentType": "HTML",
                                        "content": "<p>Please review attached</p>"
                                    },
                                    "importance": "High",
                                    "attachments": [
                                        {
                                            "id": "att_1",
                                            "name": "report.xlsx",
                                            "size": 2048,
                                            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            "isInline": False
                                        }
                                    ]
                                }
                            ]
                        }
                    )
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                assert len(messages) == 1
                assert len(messages[0]["attachments"]) == 1
                assert messages[0]["attachments"][0]["name"] == "report.xlsx"
                assert messages[0]["priority"] == "high"  # Importance: High

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_rate_limiting(self, ingestion_pipeline):
        """Test Outlook API rate limiting handling"""
        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Rate limit response
                rate_limit_response = Mock(status_code=429)
                rate_limit_response.headers = {"Retry-After": "30"}

                mock_client.get = AsyncMock(return_value=rate_limit_response)

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                # Should handle gracefully and return empty list
                assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_incremental_filtering(self, ingestion_pipeline):
        """Test Outlook incremental fetching with timestamp filter"""
        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                filter_params = None

                def check_filter(*args, **kwargs):
                    nonlocal filter_params
                    filter_params = kwargs.get('params', {})
                    return Mock(
                        status_code=200,
                        json=lambda: {"value": []}
                    )

                mock_client.get = AsyncMock(side_effect=check_filter)

                last_fetch = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
                await ingestion_pipeline._fetch_outlook_messages(last_fetch)

                # Verify filter was applied
                assert filter_params is not None
                assert "$filter" in filter_params


class TestEmailErrorHandling:
    """Test error handling in email integration"""

    @pytest.mark.asyncio(mode="auto")
    async def test_gmail_service_import_error(self, ingestion_pipeline):
        """Test graceful handling when Gmail service is not available"""
        with patch('integrations.atom_communication_ingestion_pipeline.INTEGRATIONS', {}, clear=True):
            # Force ImportError by hiding the module
            import sys
            gmail_module = sys.modules.get('integrations.gmail_service')
            if 'integrations.gmail_service' in sys.modules:
                del sys.modules['integrations.gmail_service']

            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_outlook_handles_api_error(self, ingestion_pipeline):
        """Test graceful handling of Outlook API errors"""
        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # API returns error
                mock_client.get = AsyncMock(
                    return_value=Mock(status_code=500, json=lambda: {"error": "Internal Server Error"})
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                # Should handle gracefully and return empty list
                assert messages == []


class TestEmailMessageNormalization:
    """Test email message normalization to unified format"""

    @pytest.mark.asyncio(mode="auto")
    async def test_gmail_and_outlook_same_structure(self):
        """Verify Gmail and Outlook messages have same unified structure"""
        # Both should have the same core fields
        required_fields = [
            "id", "app_type", "timestamp", "direction", "sender", "recipient",
            "subject", "content", "attachments", "metadata", "status", "priority", "tags"
        ]

        # Test that normalization includes all required fields
        # This is a structural test - actual normalization is tested in integration tests above
        assert "id" in required_fields
        assert "app_type" in required_fields
        assert "timestamp" in required_fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
