import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from ingestion_pipeline.slack_extractor import extract_data_from_slack

@pytest.fixture
def mock_get_token():
    """Mocks the token retrieval function from the token service."""
    with patch('ingestion_pipeline.slack_extractor.get_slack_token_from_service', new_callable=AsyncMock) as mock_func:
        mock_func.return_value = "mock_slack_token"
        yield mock_func

@pytest.fixture
def mock_slack_client():
    """Fixture to mock the slack_sdk AsyncWebClient."""
    with patch('ingestion_pipeline.slack_extractor.AsyncWebClient', new_callable=MagicMock) as MockClient:
        mock_instance = MockClient.return_value

        mock_instance.conversations_list = AsyncMock(return_value={
            "ok": True,
            "channels": [
                {"id": "C01", "name": "general"},
                {"id": "C02", "name": "random"}
            ]
        })

        mock_instance.conversations_history = AsyncMock(return_value={
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "ts": "1629884400.000100",
                    "text": "Hello world",
                    "user": "U01"
                }
            ]
        })

        mock_instance.chat_getPermalink = AsyncMock(return_value={
            "ok": True,
            "permalink": "https://example.slack.com/archives/C01/p1629884400000100"
        })

        yield mock_instance

@pytest.mark.asyncio
async def test_extract_data_from_slack_happy_path(mock_get_token, mock_slack_client):
    # Arrange
    user_id = "test_user_slack"
    db_conn_pool = None # No longer used directly

    # Act
    results = await extract_data_from_slack(user_id=user_id, db_conn_pool=db_conn_pool)

    # Assert
    assert len(results) == 2

    result = results[0]
    assert result["document_id"] == "slack:C01:1629884400.000100"

    # Verify mocks
    mock_get_token.assert_called_once_with(user_id)
    mock_slack_client.conversations_list.assert_called_once_with(types="public_channel", limit=200)
    assert mock_slack_client.conversations_history.call_count == 2
    assert mock_slack_client.chat_getPermalink.call_count == 2
