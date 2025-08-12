import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from ingestion_pipeline.slack_extractor import extract_data_from_slack

@pytest.fixture
def mock_db_conn_pool():
    """Fixture to mock the psycopg2 connection pool with a correctly handled cursor context manager."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()

    # This is the mock for the cursor object itself.
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {'encrypted_access_token': 'xoxp-test-token', 'team_id': 'T12345'}

    # This is the mock for the context manager returned by `conn.cursor()`.
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_cursor
    mock_context_manager.__exit__.return_value = None

    # Configure the connection's cursor() method to return our mock context manager.
    mock_conn.cursor.return_value = mock_context_manager

    # Configure the pool to return our mock connection.
    mock_pool.getconn.return_value = mock_conn

    yield mock_pool

@pytest.fixture
def mock_slack_client():
    """Fixture to mock the slack_sdk AsyncWebClient."""
    with patch('ingestion_pipeline.slack_extractor.AsyncWebClient', new_callable=MagicMock) as MockClient:
        mock_instance = MockClient.return_value

        # Mock conversations.list response
        mock_instance.conversations_list = AsyncMock(return_value={
            "ok": True,
            "channels": [
                {"id": "C01", "name": "general"},
                {"id": "C02", "name": "random"}
            ]
        })

        # Mock conversations.history response
        mock_instance.conversations_history = AsyncMock(return_value={
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "ts": "1629884400.000100", # 2021-08-25 10:00:00 UTC
                    "text": "Hello world",
                    "user": "U01"
                }
            ]
        })

        # Mock chat.getPermalink response
        mock_instance.chat_getPermalink = AsyncMock(return_value={
            "ok": True,
            "permalink": "https://example.slack.com/archives/C01/p1629884400000100"
        })

        yield mock_instance

@pytest.mark.asyncio
async def test_extract_data_from_slack_happy_path(mock_db_conn_pool, mock_slack_client):
    # Arrange
    user_id = "test_user_slack"

    # Act
    results = await extract_data_from_slack(user_id=user_id, db_conn_pool=mock_db_conn_pool)

    # Assert
    assert len(results) == 2 # One message from each of the two mock channels

    # Check the structure of the first result
    result = results[0]
    assert result["document_id"] == "slack:C01:1629884400.000100"
    assert result["document_title"] == "Message in #general"
    assert result["full_text"] == "Hello world"
    assert result["source"] == "slack"
    assert result["user_id"] == user_id
    assert result["url"] == "https://example.slack.com/archives/C01/p1629884400000100"

    created_at_dt = datetime.fromisoformat(result["created_at"])
    assert created_at_dt.year == 2021
    assert created_at_dt.month == 8
    assert created_at_dt.day == 25

    # Verify mocks were called
    mock_db_conn_pool.getconn.assert_called_once()
    mock_slack_client.conversations_list.assert_called_once_with(types="public_channel", limit=200)
    assert mock_slack_client.conversations_history.call_count == 2
    mock_slack_client.conversations_history.assert_any_call(channel="C01", limit=100)
    mock_slack_client.conversations_history.assert_any_call(channel="C02", limit=100)
    assert mock_slack_client.chat_getPermalink.call_count == 2
