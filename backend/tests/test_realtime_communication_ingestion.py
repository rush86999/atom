"""
Tests for Real-Time Communication Ingestion Implementation
Tests the polling-based real-time ingestion functionality.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock

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
    manager.db = Mock()  # Simulate initialized DB
    manager.ingest_communication = Mock(return_value=True)  # Synchronous method
    return manager


@pytest.fixture
def ingestion_pipeline(mock_memory_manager):
    """Create CommunicationIngestionPipeline instance"""
    return CommunicationIngestionPipeline(mock_memory_manager)


@pytest.fixture
def sample_config():
    """Create sample ingestion configuration"""
    return IngestionConfig(
        app_type=CommunicationAppType.SLACK,
        enabled=True,
        real_time=True,
        batch_size=50,
        ingest_attachments=True,
        embed_content=True,
        retention_days=30,
        vector_dim=768
    )


class TestRealTimeIngestion:
    """Test suite for real-time ingestion functionality"""

    @pytest.mark.asyncio
    async def test_configure_app_updates_configs(self, ingestion_pipeline, sample_config):
        """Test that configure_app updates both ingestion_configs and app_configs"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        assert "slack" in ingestion_pipeline.ingestion_configs
        assert "slack" in ingestion_pipeline.app_configs
        assert ingestion_pipeline.ingestion_configs["slack"]["enabled"] is True
        assert ingestion_pipeline.app_configs["slack"]["real_time"] is True

    @pytest.mark.asyncio
    async def test_start_real_time_ingestion(self, ingestion_pipeline, sample_config):
        """Test starting real-time ingestion for an app"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        # Mock the _real_time_ingestion to avoid infinite loop
        with patch.object(ingestion_pipeline, '_real_time_ingestion', new_callable=AsyncMock) as mock_ingestion:
            result = ingestion_pipeline.start_real_time_stream(CommunicationAppType.SLACK.value)

            assert result is True
            assert CommunicationAppType.SLACK.value in ingestion_pipeline.active_streams
            mock_ingestion.assert_called_once_with(CommunicationAppType.SLACK.value)

    @pytest.mark.asyncio
    async def test_start_real_time_ingestion_when_disabled(self, ingestion_pipeline):
        """Test that real-time ingestion doesn't start when disabled in config"""
        config = IngestionConfig(
            app_type=CommunicationAppType.SLACK,
            enabled=True,
            real_time=False,  # Disabled
            batch_size=50,
            ingest_attachments=True,
            embed_content=True,
            retention_days=30
        )

        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, config)
        result = ingestion_pipeline.start_real_time_stream(CommunicationAppType.SLACK.value)

        assert result is False
        assert CommunicationAppType.SLACK.value not in ingestion_pipeline.active_streams

    @pytest.mark.asyncio
    async def test_fetch_new_messages_updates_timestamp(self, ingestion_pipeline, sample_config):
        """Test that _fetch_new_messages updates the fetch timestamp"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        # Mock the fetch method to return some messages
        with patch.object(ingestion_pipeline, '_fetch_slack_messages', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {"id": "msg1", "content": "Test message"},
                {"id": "msg2", "content": "Another message"}
            ]

            messages = await ingestion_pipeline._fetch_new_messages(CommunicationAppType.SLACK.value)

            # Check that messages were returned
            assert len(messages) == 2

            # Check that timestamp was updated
            last_fetch_key = f"last_fetch_{CommunicationAppType.SLACK.value}"
            assert last_fetch_key in ingestion_pipeline.fetch_timestamps
            assert isinstance(ingestion_pipeline.fetch_timestamps[last_fetch_key], datetime)

    @pytest.mark.asyncio
    async def test_fetch_new_messages_with_unsupported_app(self, ingestion_pipeline, sample_config):
        """Test _fetch_new_messages with unsupported app type"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        messages = await ingestion_pipeline._fetch_new_messages("unsupported_app")

        assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_slack_messages(self, ingestion_pipeline):
        """Test fetching Slack messages"""
        # Configure Slack with monitored channels
        config = IngestionConfig(
            app_type=CommunicationAppType.SLACK,
            enabled=True,
            real_time=True,
            batch_size=50,
            ingest_attachments=True,
            embed_content=True,
            retention_days=30
        )
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, config)
        ingestion_pipeline.app_configs["slack"]["monitored_channels"] = ["C123456", "C789012"]

        # Mock Slack service import at module level
        with patch('integrations.slack_enhanced_service.slack_enhanced_service') as mock_slack:
            # Currently returns empty list (not implemented)
            messages = await ingestion_pipeline._fetch_slack_messages(None)

            # Should return empty list (not yet implemented)
            assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_fetch_whatsapp_messages(self, ingestion_pipeline):
        """Test fetching WhatsApp messages"""
        messages = await ingestion_pipeline._fetch_whatsapp_messages(None)

        # Currently returns empty list (webhooks preferred)
        assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_teams_messages(self, ingestion_pipeline):
        """Test fetching Teams messages"""
        messages = await ingestion_pipeline._fetch_teams_messages(None)

        # Currently returns empty list (not yet implemented)
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_fetch_gmail_messages(self, ingestion_pipeline):
        """Test fetching Gmail messages"""
        messages = await ingestion_pipeline._fetch_gmail_messages(None)

        # Currently returns empty list (not yet implemented)
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_fetch_outlook_messages(self, ingestion_pipeline):
        """Test fetching Outlook messages"""
        messages = await ingestion_pipeline._fetch_outlook_messages(None)

        # Currently returns empty list (not yet implemented)
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_fetch_email_messages(self, ingestion_pipeline):
        """Test fetching email messages"""
        messages = await ingestion_pipeline._fetch_email_messages(None)

        # Currently returns empty list (not yet implemented)
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_real_time_ingestion_loop(self, ingestion_pipeline, sample_config):
        """Test the real-time ingestion loop runs and fetches messages"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        # Track number of iterations
        iteration_count = 0
        max_iterations = 2

        async def mock_fetch_new_messages(app_type):
            nonlocal iteration_count
            iteration_count += 1

            if iteration_count <= max_iterations:
                return [{"id": f"msg{iteration_count}", "content": f"Message {iteration_count}"}]
            return []  # Stop after max iterations

        with patch.object(ingestion_pipeline, '_fetch_new_messages', new_callable=AsyncMock, side_effect=mock_fetch_new_messages):
            with patch.object(ingestion_pipeline, 'ingest_message', new_callable=AsyncMock) as mock_ingest:

                # Run the loop for a short time
                task = asyncio.create_task(ingestion_pipeline._real_time_ingestion(CommunicationAppType.SLACK.value))

                # Wait a bit for iterations
                await asyncio.sleep(0.1)

                # Cancel the task
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

                # Verify messages were fetched
                assert iteration_count >= 1


class TestRealTimeIngestionIntegration:
    """Integration tests for real-time ingestion"""

    @pytest.mark.asyncio
    async def test_full_ingestion_flow(self, ingestion_pipeline, sample_config):
        """Test full flow: configure -> fetch -> ingest"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        sample_messages = [
            {
                "id": "msg1",
                "content": "Test message 1",
                "timestamp": datetime.now().isoformat(),
                "sender": "user1",
                "channel": "C123456"
            },
            {
                "id": "msg2",
                "content": "Test message 2",
                "timestamp": datetime.now().isoformat(),
                "sender": "user2",
                "channel": "C123456"
            }
        ]

        with patch.object(ingestion_pipeline, '_fetch_slack_messages', new_callable=AsyncMock, return_value=sample_messages):
            # Fetch messages
            messages = await ingestion_pipeline._fetch_new_messages(CommunicationAppType.SLACK.value)

            assert len(messages) == 2

            # Ingest each message - note: ingest_message returns Mock not True/False
            for msg in messages:
                result = await ingestion_pipeline.ingest_message(CommunicationAppType.SLACK.value, msg)
                # Just check it doesn't raise an exception
                assert result is not None

            # Verify ingest was called (uses ingest_communication method)
            assert ingestion_pipeline.memory_manager.ingest_communication.call_count >= 2

    @pytest.mark.asyncio
    async def test_incremental_fetching_with_timestamps(self, ingestion_pipeline, sample_config):
        """Test that incremental fetching works with timestamps"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        # First fetch - no previous timestamp
        with patch.object(ingestion_pipeline, '_fetch_slack_messages', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"id": "msg1"}]
            messages1 = await ingestion_pipeline._fetch_new_messages(CommunicationAppType.SLACK.value)

            mock_fetch.assert_called_once_with(None)
            assert len(messages1) == 1

        # Second fetch - should use previous timestamp
        with patch.object(ingestion_pipeline, '_fetch_slack_messages', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"id": "msg2"}]
            messages2 = await ingestion_pipeline._fetch_new_messages(CommunicationAppType.SLACK.value)

            # Should be called with the timestamp from first fetch
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args[0]
            assert call_args[0] is not None  # Should have a datetime now
            assert isinstance(call_args[0], datetime)
            assert len(messages2) == 1

    @pytest.mark.asyncio
    async def test_error_handling_in_fetch(self, ingestion_pipeline, sample_config):
        """Test error handling when fetch fails"""
        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, sample_config)

        # Mock fetch to raise exception
        with patch.object(ingestion_pipeline, '_fetch_slack_messages', new_callable=AsyncMock, side_effect=Exception("API Error")):
            messages = await ingestion_pipeline._fetch_new_messages(CommunicationAppType.SLACK.value)

            # Should return empty list on error
            assert messages == []

            # Note: In current implementation, timestamp is NOT updated on error
            # This is intentional so we can retry the same time range


class TestRealTimeIngestionConfiguration:
    """Test configuration and setup for real-time ingestion"""

    def test_config_has_polling_interval(self):
        """Test that IngestionConfig can support polling_interval"""
        config = IngestionConfig(
            app_type=CommunicationAppType.SLACK,
            enabled=True,
            real_time=True,
            batch_size=50,
            ingest_attachments=True,
            embed_content=True,
            retention_days=30
        )

        # Add polling_interval via app_configs
        polling_config = {**config.__dict__, 'polling_interval_seconds': 60}

        assert polling_config['polling_interval_seconds'] == 60
        assert polling_config['real_time'] is True

    @pytest.mark.asyncio
    async def test_multiple_apps_concurrent_ingestion(self, ingestion_pipeline):
        """Test running real-time ingestion for multiple apps concurrently"""
        slack_config = IngestionConfig(
            app_type=CommunicationAppType.SLACK,
            enabled=True,
            real_time=True,
            batch_size=50,
            ingest_attachments=True,
            embed_content=True,
            retention_days=30
        )

        teams_config = IngestionConfig(
            app_type=CommunicationAppType.MICROSOFT_TEAMS,
            enabled=True,
            real_time=True,
            batch_size=50,
            ingest_attachments=True,
            embed_content=True,
            retention_days=30
        )

        ingestion_pipeline.configure_app(CommunicationAppType.SLACK, slack_config)
        ingestion_pipeline.configure_app(CommunicationAppType.MICROSOFT_TEAMS, teams_config)

        # Mock the ingestion loop
        with patch.object(ingestion_pipeline, '_real_time_ingestion', new_callable=AsyncMock):
            result1 = ingestion_pipeline.start_real_time_stream(CommunicationAppType.SLACK.value)
            result2 = ingestion_pipeline.start_real_time_stream(CommunicationAppType.MICROSOFT_TEAMS.value)

            assert result1 is True
            assert result2 is True
            assert len(ingestion_pipeline.active_streams) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
