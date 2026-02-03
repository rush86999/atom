"""
Tests for Microsoft Teams API Real-Time Message Ingestion
Tests the Microsoft Graph API integration for polling and message fetching.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
import pytest_asyncio

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    CommunicationIngestionPipeline,
    IngestionConfig,
    LanceDBMemoryManager,
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
def teams_config():
    """Create Teams ingestion configuration"""
    return IngestionConfig(
        app_type=CommunicationAppType.MICROSOFT_TEAMS,
        enabled=True,
        real_time=True,
        batch_size=50,
        ingest_attachments=True,
        embed_content=True,
        retention_days=30
    )


class TestTeamsAPIIntegration:
    """Test suite for Teams API integration"""

    def test_configure_teams_ingestion(self, ingestion_pipeline, teams_config):
        """Test configuring Teams ingestion with monitored chats"""
        ingestion_pipeline.configure_app(CommunicationAppType.MICROSOFT_TEAMS, teams_config)

        # Add monitored chats to config
        ingestion_pipeline.app_configs[CommunicationAppType.MICROSOFT_TEAMS.value]["monitored_chats"] = [
            "19:meeting_MjdhNjM4YzUtYzExZi00OTY4LTkzYWUtOTQ2YTkwNmIwZjAy@thread.v2"
        ]

        assert "microsoft_teams" in ingestion_pipeline.ingestion_configs
        assert "microsoft_teams" in ingestion_pipeline.app_configs

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_teams_messages_without_token(self, ingestion_pipeline):
        """Test that missing Microsoft token is handled gracefully"""
        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = None

            messages = await ingestion_pipeline._fetch_teams_messages(None)

            assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_teams_chat_messages_success(self, ingestion_pipeline, teams_config):
        """Test successful chat message fetching from Teams"""
        ingestion_pipeline.configure_app(CommunicationAppType.MICROSOFT_TEAMS, teams_config)

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {
                "access_token": "test_token",
                "expires_in": 3600
            }

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock chats response
                mock_client.get = AsyncMock(
                    side_effect=[
                        # First call: get chats
                        Mock(
                            status_code=200,
                            json=lambda: {"value": [
                                {
                                    "id": "19:chat_123@thread.v2",
                                    "chatType": "oneOnOne",
                                    "topic": "Test Chat"
                                }
                            ]}
                        ),
                        # Second call: get messages from chat
                        Mock(
                            status_code=200,
                            json=lambda: {"value": [
                                {
                                    "id": "1234567890",
                                    "createdDateTime": "2024-02-01T12:00:00Z",
                                    "from": {
                                        "user": {
                                            "displayName": "John Doe",
                                            "email": "john@example.com"
                                        }
                                    },
                                    "body": {
                                        "content": "Hello from Teams!",
                                        "contentType": "text"
                                    },
                                    "messageType": "message",
                                    "webUrl": "https://teams.microsoft.com/l/message/1234567890"
                                }
                            ]}
                        )
                    ]
                )

                messages = await ingestion_pipeline._fetch_teams_chat_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    None
                )

                assert len(messages) == 1
                assert messages[0]["content"] == "Hello from Teams!"
                assert messages[0]["sender"] == "John Doe"
                assert messages[0]["sender_email"] == "john@example.com"
                assert messages[0]["metadata"]["chat_id"] == "19:chat_123@thread.v2"

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_teams_channel_messages_success(self, ingestion_pipeline, teams_config):
        """Test successful channel message fetching from Teams"""
        ingestion_pipeline.configure_app(CommunicationAppType.MICROSOFT_TEAMS, teams_config)

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {
                "access_token": "test_token"
            }

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock responses
                mock_client.get = AsyncMock(
                    side_effect=[
                        # First call: get teams
                        Mock(
                            status_code=200,
                            json=lambda: {"value": [
                                {
                                    "id": "team_id_123",
                                    "displayName": "Marketing Team"
                                }
                            ]}
                        ),
                        # Second call: get channels
                        Mock(
                            status_code=200,
                            json=lambda: {"value": [
                                {
                                    "id": "19:channel_id@thread.v2",
                                    "displayName": "General"
                                }
                            ]}
                        ),
                        # Third call: get messages from channel
                        Mock(
                            status_code=200,
                            json=lambda: {"value": [
                                {
                                    "id": "9876543210",
                                    "createdDateTime": "2024-02-01T12:00:00Z",
                                    "from": {
                                        "user": {
                                            "displayName": "Jane Smith",
                                            "email": "jane@example.com"
                                        }
                                    },
                                    "body": {
                                        "content": "Channel message!",
                                        "contentType": "text"
                                    },
                                    "messageType": "message",
                                    "webUrl": "https://teams.microsoft.com/l/message/9876543210"
                                }
                            ]}
                        )
                    ]
                )

                messages = await ingestion_pipeline._fetch_teams_channel_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    None
                )

                assert len(messages) == 1
                assert messages[0]["content"] == "Channel message!"
                assert messages[0]["sender"] == "Jane Smith"
                assert messages[0]["metadata"]["team_name"] == "Marketing Team"
                assert messages[0]["metadata"]["channel_name"] == "General"

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_teams_messages_incremental(self, ingestion_pipeline, teams_config):
        """Test incremental fetching with timestamp filtering"""
        ingestion_pipeline.configure_app(CommunicationAppType.MICROSOFT_TEAMS, teams_config)

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

                mock_client.get = AsyncMock(side_effect=[
                    # Get chats
                    Mock(status_code=200, json=lambda: {"value": [{"id": "chat_123", "chatType": "oneOnOne"}]}),
                    # Get messages (will check filter)
                    check_filter
                ])

                last_fetch = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
                await ingestion_pipeline._fetch_teams_chat_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    last_fetch
                )

                # Verify filter was applied
                assert filter_params is not None
                assert "$filter" in filter_params

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_teams_messages_rate_limiting(self, ingestion_pipeline, teams_config):
        """Test handling of Teams API rate limiting"""
        ingestion_pipeline.configure_app(CommunicationAppType.MICROSOFT_TEAMS, teams_config)

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock rate limit error
                rate_limit_response = Mock(status_code=429)
                rate_limit_response.headers = {"Retry-After": "30"}

                mock_client.get = AsyncMock(
                    side_effect=[
                        # Get chats
                        Mock(status_code=200, json=lambda: {"value": [{"id": "chat_123"}]}),
                        # Rate limited
                        rate_limit_response
                    ]
                )

                messages = await ingestion_pipeline._fetch_teams_chat_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    None
                )

                # Should handle gracefully and return empty list
                assert len(messages) == 0

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_teams_with_adaptive_cards(self, ingestion_pipeline, teams_config):
        """Test handling of Teams messages with Adaptive Cards"""
        ingestion_pipeline.configure_app(CommunicationAppType.MICROSOFT_TEAMS, teams_config)

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                adaptive_card = {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Adaptive Card Content"
                        }
                    ]
                }

                mock_client.get = AsyncMock(
                    side_effect=[
                        Mock(status_code=200, json=lambda: {"value": [{"id": "chat_123"}]}),
                        Mock(
                            status_code=200,
                            json=lambda: {"value": [
                                {
                                    "id": "msg_123",
                                    "createdDateTime": "2024-02-01T12:00:00Z",
                                    "from": {"user": {"displayName": "User"}},
                                    "body": {"content": "Card message", "contentType": "html"},
                                    "attachments": [
                                        {
                                            "contentType": "application/vnd.microsoft.card.adaptive",
                                            "content": adaptive_card
                                        }
                                    ]
                                }
                            ]}
                        )
                    ]
                )

                messages = await ingestion_pipeline._fetch_teams_chat_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    None
                )

                assert len(messages) == 1
                assert messages[0]["metadata"]["adaptive_card"] is not None
                assert messages[0]["metadata"]["adaptive_card"]["type"] == "AdaptiveCard"

    @pytest.mark.asyncio(mode="auto")
    async def test_teams_message_normalization_structure(self, ingestion_pipeline):
        """Test that Teams messages are properly normalized"""
        pipeline = CommunicationIngestionPipeline(Mock())

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_client.get = AsyncMock(
                    side_effect=[
                        # Chats
                        Mock(status_code=200, json=lambda: {"value": [{"id": "chat_123"}]}),
                        # Messages
                        Mock(status_code=200, json=lambda: {"value": [
                            {
                                "id": "msg_456",
                                "createdDateTime": "2024-02-01T12:00:00Z",
                                "from": {"user": {"displayName": "Alice", "email": "alice@company.com"}},
                                "body": {"content": "Test message", "contentType": "text"},
                                "messageType": "message",
                                "subject": "Test Subject"
                            }
                        ]})
                    ]
                )

                with patch.dict('os.environ', {}):
                    pipeline.app_configs["microsoft_teams"] = {"monitored_chats": ["chat_123"]}
                    messages = await pipeline._fetch_teams_chat_messages(
                        mock_client,
                        {"Authorization": "Bearer test_token"},
                        None
                    )

                assert len(messages) == 1
                msg = messages[0]

                # Verify structure
                assert msg["app_type"] == "microsoft_teams"
                assert msg["direction"] == "inbound"
                assert msg["sender"] == "Alice"
                assert msg["sender_email"] == "alice@company.com"
                assert msg["content"] == "Test message"
                assert msg["content_type"] == "text"
                assert msg["subject"] == "Test Subject"
                assert msg["status"] == "active"
                assert msg["priority"] == "normal"
                assert "teams" in msg["tags"]


class TestTeamsErrorHandling:
    """Test error handling in Teams integration"""

    @pytest.mark.asyncio(mode="auto")
    async def test_handles_api_error_gracefully(self):
        """Test graceful handling of Teams API errors"""
        pipeline = CommunicationIngestionPipeline(Mock())

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # API returns error
                mock_client.get = AsyncMock(
                    return_value=Mock(status_code=500, json=lambda: {"error": "Internal Server Error"})
                )

                messages = await pipeline._fetch_teams_chat_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    None
                )

                # Should handle gracefully and return empty list
                assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_handles_missing_chat_id(self):
        """Test handling of chats without IDs"""
        pipeline = CommunicationIngestionPipeline(Mock())

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Chat without ID
                mock_client.get = AsyncMock(
                    side_effect=[
                        Mock(status_code=200, json=lambda: {"value": [{"chatType": "oneOnOne"}]})
                    ]
                )

                messages = await pipeline._fetch_teams_chat_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    None
                )

                # Should skip invalid chat
                assert len(messages) == 0


class TestTeamsIngestionIntegration:
    """Integration tests for Teams message ingestion"""

    @pytest.mark.asyncio(mode="auto")
    async def test_full_teams_ingestion_flow(self):
        """Test complete flow: fetch -> ingest"""
        mock_manager = Mock()
        mock_manager.db = Mock()
        mock_manager.ingest_communication = Mock(return_value=True)

        pipeline = CommunicationIngestionPipeline(mock_manager)

        with patch('core.token_storage.token_storage') as mock_storage:
            mock_storage.get_token.return_value = {"access_token": "test_token"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_client.get = AsyncMock(
                    side_effect=[
                        # Chats
                        Mock(status_code=200, json=lambda: {"value": [{"id": "chat_123"}]}),
                        # Messages
                        Mock(status_code=200, json=lambda: {"value": [
                            {
                                "id": "msg_789",
                                "createdDateTime": "2024-02-01T12:00:00Z",
                                "from": {"user": {"displayName": "Bob"}},
                                "body": {"content": "Hello from Microsoft Teams!", "contentType": "text"},
                                "messageType": "message"
                            }
                        ]})
                    ]
                )

                # Fetch messages
                messages = await pipeline._fetch_teams_chat_messages(
                    mock_client,
                    {"Authorization": "Bearer test_token"},
                    None
                )

                assert len(messages) == 1

                # Ingest messages
                for msg in messages:
                    result = await pipeline.ingest_message("microsoft_teams", msg)
                    assert result is not None

                # Verify ingest was called
                assert mock_manager.ingest_communication.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
