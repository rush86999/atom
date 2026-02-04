"""
Tests for Slack API Real-Time Message Ingestion
Tests the Slack WebClient integration for polling and message fetching.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest

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
def slack_config():
    """Create Slack ingestion configuration"""
    return IngestionConfig(
        app_type=CommunicationAppType.SLACK,
        enabled=True,
        real_time=True,
        batch_size=50,
        ingest_attachments=True,
        embed_content=True,
        retention_days=30
    )


class TestSlackAPIIntegration:
    """Test suite for Slack API integration"""

    def test_configure_slack_ingestion(self, ingestion_pipeline, slack_config):
        """Test configuring Slack ingestion with monitored channels"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)

        # Add monitored channels to config
        ingestion_pipeline.app_configs[CommunicationAppType.SLACK.value]["monitored_channels"] = [
            "C123456",
            "C789012"
        ]

        assert "slack" in ingestion_pipeline.ingestion_configs
        assert "slack" in ingestion_pipeline.app_configs
        assert ingestion_pipeline.app_configs["slack"]["monitored_channels"] == ["C123456", "C789012"]

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_without_token(self, ingestion_pipeline):
        """Test that missing SLACK_BOT_TOKEN is handled gracefully"""
        with patch.dict('os.environ', {}, clear=True):
            messages = await ingestion_pipeline._fetch_slack_messages(None)

            assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_no_channels_configured(self, ingestion_pipeline, slack_config):
        """Test behavior when no channels are configured"""
        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'xoxb-test-token'}):
            ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
            # Don't add monitored_channels

            messages = await ingestion_pipeline._fetch_slack_messages(None)

            assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_success(self, ingestion_pipeline, slack_config):
        """Test successful message fetching from Slack"""
        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'xoxb-test-token'}):
            ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
            ingestion_pipeline.app_configs["slack"]["monitored_channels"] = ["C123456"]

            # Mock AsyncWebClient at the point where it's used
            with patch('integrations.atom_communication_ingestion_pipeline.slack_sdk') as mock_slack_sdk:
                mock_client_class = Mock()
                mock_slack_sdk.web.async_client = Mock(return_value=AsyncMock())
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                # Mock conversations_info response (channel name)
                mock_client.conversations_info = AsyncMock(return_value={
                    "ok": True,
                    "channel": {"name": "general"}
                })

                # Mock conversations_history response
                mock_client.conversations_history = AsyncMock(return_value={
                    "ok": True,
                    "messages": [
                        {
                            "type": "message",
                            "ts": "1638360000.000100",
                            "user": "U123456",
                            "text": "Hello world!",
                            "reactions": [{"name": "thumbsup"}]
                        },
                        {
                            "type": "message",
                            "ts": "1638360001.000200",
                            "user": "U789012",
                            "text": "Another message"
                        }
                    ],
                    "response_metadata": {}
                })

                messages = await ingestion_pipeline._fetch_slack_messages(
                    datetime.now(timezone.utc) - timedelta(hours=1)
                )

                assert len(messages) == 2
                assert messages[0]["content"] == "Hello world!"
                assert messages[0]["sender"] == "U123456"
                assert messages[0]["metadata"]["channel_name"] == "general"
                assert messages[1]["content"] == "Another message"

                # Verify client was closed
                mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_with_pagination(self, ingestion_pipeline, slack_config):
        """Test cursor-based pagination for message fetching"""
        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'xoxb-test-token'}):
            ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
            ingestion_pipeline.app_configs["slack"]["monitored_channels"] = ["C123456"]

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.conversations_info = AsyncMock(return_value={
                    "ok": True,
                    "channel": {"name": "general"}
                })

                # First response with pagination cursor
                first_response = {
                    "ok": True,
                    "messages": [{"type": "message", "ts": "1.0", "user": "U1", "text": "First"}],
                    "response_metadata": {"next_cursor": "cursor123"}
                }

                # Second response without cursor (last page)
                second_response = {
                    "ok": True,
                    "messages": [{"type": "message", "ts": "2.0", "user": "U2", "text": "Second"}],
                    "response_metadata": {}
                }

                mock_client.conversations_history = AsyncMock(
                    side_effect=[
                        first_response,
                        second_response
                    ]
                )

                messages = await ingestion_pipeline._fetch_slack_messages(None)

                assert len(messages) == 2
                assert messages[0]["content"] == "First"
                assert messages[1]["content"] == "Second"

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_filters_bot_messages(self, ingestion_pipeline, slack_config):
        """Test that bot messages are filtered out by default"""
        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'xoxb-test-token'}):
            ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
            ingestion_pipeline.app_configs["slack"]["monitored_channels"] = ["C123456"]

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.conversations_info = AsyncMock(return_value={
                    "ok": True,
                    "channel": {"name": "general"}
                })

                # Response with bot messages
                mock_client.conversations_history = AsyncMock(return_value={
                    "ok": True,
                    "messages": [
                        {
                            "type": "message",
                            "ts": "1.0",
                            "user": "U123",
                            "text": "User message"
                        },
                        {
                            "type": "message",
                            "ts": "2.0",
                            "bot_id": "B456",
                            "text": "Bot message"
                        }
                    ],
                    "response_metadata": {}
                })

                messages = await ingestion_pipeline._fetch_slack_messages(None)

                # Bot message should be filtered out
                assert len(messages) == 1
                assert messages[0]["content"] == "User message"

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_rate_limiting(self, ingestion_pipeline, slack_config):
        """Test handling of Slack API rate limiting"""
        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'xoxb-test-token'}):
            ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
            ingestion_pipeline.app_configs["slack"]["monitored_channels"] = ["C123456"]

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                from slack_sdk.errors import SlackApiError

                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                # Mock rate limit error
                rate_limit_error = SlackApiError(
                    message="Rate limited",
                    response={"error": "ratelimited"},
                    headers={"Retry-After": "60"}
                )

                mock_client.conversations_history = AsyncMock(side_effect=rate_limit_error)

                messages = await ingestion_pipeline._fetch_slack_messages(None)

                # Should return empty list and log warning
                assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_incremental(self, ingestion_pipeline, slack_config):
        """Test incremental fetching with timestamp filtering"""
        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'xoxb-test-token'}):
            ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
            ingestion_pipeline.app_configs["slack"]["monitored_channels"] = ["C123456"]

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.conversations_info = AsyncMock(return_value={
                    "ok": True,
                    "channel": {"name": "general"}
                })

                # Track the oldest parameter
                oldest_param = None

                def check_oldest(*args, **kwargs):
                    nonlocal oldest_param
                    oldest_param = kwargs.get('oldest')
                    return {
                        "ok": True,
                        "messages": [],
                        "response_metadata": {}
                    }

                mock_client.conversations_history = AsyncMock(side_effect=check_oldest)

                last_fetch = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
                await ingestion_pipeline._fetch_slack_messages(last_fetch)

                # Verify oldest timestamp was passed
                assert oldest_param is not None
                assert oldest_param == str(last_fetch.timestamp())

    @pytest.mark.asyncio
    async def test_fetch_slack_messages_multiple_channels(self, ingestion_pipeline, slack_config):
        """Test fetching messages from multiple channels"""
        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'xoxb-test-token'}):
            ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
            ingestion_pipeline.app_configs["slack"]["monitored_channels"] = ["C111", "C222"]

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.conversations_info = AsyncMock(
                    side_effect=[
                        {"ok": True, "channel": {"name": "general"}},
                        {"ok": True, "channel": {"name": "random"}}
                    ]
                )

                mock_client.conversations_history = AsyncMock(
                    side_effect=[
                        {
                            "ok": True,
                            "messages": [{"type": "message", "ts": "1.0", "user": "U1", "text": "Channel 1"}],
                            "response_metadata": {}
                        },
                        {
                            "ok": True,
                            "messages": [{"type": "message", "ts": "2.0", "user": "U2", "text": "Channel 2"}],
                            "response_metadata": {}
                        }
                    ]
                )

                messages = await ingestion_pipeline._fetch_slack_messages(None)

                # Should get messages from both channels
                assert len(messages) == 2
                # Should be sorted by timestamp
                assert messages[0]["content"] == "Channel 1"
                assert messages[1]["content"] == "Channel 2"


class TestSlackMessageNormalization:
    """Test Slack message normalization and metadata"""

    @pytest.mark.asyncio
    async def test_message_normalization_structure(self):
        """Test that Slack messages are properly normalized"""
        pipeline = CommunicationIngestionPipeline(Mock())

        # Mock the client and channel lookup
        with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_client.conversations_info = AsyncMock(return_value={
                "ok": True,
                "channel": {"name": "general"}
            })

            mock_client.conversations_history = AsyncMock(return_value={
                "ok": True,
                "messages": [{
                    "type": "message",
                    "ts": "1638360000.000100",
                    "user": "U123456",
                    "text": "Test message",
                    "thread_ts": "1638360000.000100",
                    "reactions": [{"name": "thumbsup", "users": ["U123"]}]
                }]
            })

            with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'token'}):
                pipeline.app_configs["slack"] = {"monitored_channels": ["C123"]}
                messages = await pipeline._fetch_slack_messages(None)

            assert len(messages) == 1
            msg = messages[0]

            # Verify structure
            assert msg["app_type"] == "slack"
            assert msg["direction"] == "inbound"
            assert msg["sender"] == "U123456"
            assert msg["recipient"] == "C123"
            assert msg["content"] == "Test message"
            assert msg["subject"] is None

            # Verify metadata
            assert "metadata" in msg
            assert msg["metadata"]["channel_id"] == "C123"
            assert msg["metadata"]["channel_name"] == "general"
            assert msg["metadata"]["thread_ts"] == "1638360000.000100"
            assert msg["metadata"]["reactions"][0]["name"] == "thumbsup"


class TestSlackErrorHandling:
    """Test error handling in Slack integration"""

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self):
        """Test graceful handling of Slack API errors"""
        pipeline = CommunicationIngestionPipeline(Mock())

        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'token'}):
            pipeline.app_configs["slack"] = {"monitored_channels": ["C123"]}

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                # API returns error
                mock_client.conversations_history = AsyncMock(return_value={
                    "ok": False,
                    "error": "channel_not_found"
                })

                messages = await pipeline._fetch_slack_messages(None)

                # Should handle gracefully and return empty list
                assert messages == []

    @pytest.mark.asyncio
    async def test_handles_channel_name_lookup_failure(self):
        """Test that channel name lookup failures don't break message fetching"""
        pipeline = CommunicationIngestionPipeline(Mock())

        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'token'}):
            pipeline.app_configs["slack"] = {"monitored_channels": ["C123"]}

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                # conversations_info fails
                mock_client.conversations_info = AsyncMock(
                    side_effect=Exception("Channel not found")
                )

                mock_client.conversations_history = AsyncMock(return_value={
                    "ok": True,
                    "messages": [{
                        "type": "message",
                        "ts": "1.0",
                        "user": "U1",
                        "text": "Test"
                    }],
                    "response_metadata": {}
                })

                messages = await pipeline._fetch_slack_messages(None)

                # Should still work, just without channel name
                assert len(messages) == 1
                assert messages[0]["metadata"]["channel_name"] is None


class TestSlackIngestionIntegration:
    """Integration tests for Slack message ingestion"""

    @pytest.mark.asyncio
    async def test_full_slack_ingestion_flow(self):
        """Test complete flow: fetch -> ingest"""
        mock_manager = Mock()
        mock_manager.db = Mock()
        mock_manager.ingest_communication = Mock(return_value=True)

        pipeline = CommunicationIngestionPipeline(mock_manager)

        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'token'}):
            pipeline.configure_app(
                CommunicationAppType.SLACK,
                IngestionConfig(
                    app_type=CommunicationAppType.SLACK,
                    enabled=True,
                    real_time=True,
                    batch_size=50,
                    ingest_attachments=True,
                    embed_content=True,
                    retention_days=30
                )
            )
            pipeline.app_configs["slack"]["monitored_channels"] = ["C123"]

            with patch('integrations.atom_communication_ingestion_pipeline.AsyncWebClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.conversations_info = AsyncMock(return_value={
                    "ok": True,
                    "channel": {"name": "general"}
                })

                mock_client.conversations_history = AsyncMock(return_value={
                    "ok": True,
                    "messages": [{
                        "type": "message",
                        "ts": "1.0",
                        "user": "U1",
                        "text": "Hello from Slack!"
                    }],
                    "response_metadata": {}
                })

                # Fetch messages
                messages = await pipeline._fetch_slack_messages(None)

                assert len(messages) == 1

                # Ingest messages
                for msg in messages:
                    result = await pipeline.ingest_message("slack", msg)
                    assert result is not None

                # Verify ingest was called
                assert mock_manager.ingest_communication.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
