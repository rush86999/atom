import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from ingestion_pipeline.msteams_extractor import extract_data_from_msteams

@pytest.fixture
def mock_db_conn_pool():
    """Mocks the database connection pool."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_record = {
        "encrypted_refresh_token": "mock_encrypted_refresh_token",
        "account_json": json.dumps({"home_account_id": "mock_home_account_id"})
    }
    mock_cursor.fetchone.return_value = mock_record

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_cursor
    mock_context_manager.__exit__.return_value = None

    mock_conn.cursor.return_value = mock_context_manager
    mock_pool.getconn.return_value = mock_conn

    yield mock_pool

@pytest.fixture
def mock_msal_app():
    """Mocks the MSAL ConfidentialClientApplication."""
    with patch('ingestion_pipeline.msteams_extractor.msal.ConfidentialClientApplication') as MockMsal:
        mock_instance = MockMsal.return_value
        mock_instance.acquire_token_by_refresh_token.return_value = {
            "access_token": "mock_access_token"
        }
        yield mock_instance

@pytest.fixture
def mock_httpx_client():
    """Mocks the httpx.AsyncClient for MS Graph API calls."""

    teams_response = {"value": [{"id": "team1"}], "@odata.nextLink": None}
    channels_response = {"value": [{"id": "channel1", "displayName": "General"}], "@odata.nextLink": None}
    messages_response = {
        "value": [{
            "id": "msg1",
            "body": {"content": "Hello from Teams"},
            "webUrl": "http://teams.example.com/msg1",
            "createdDateTime": "2023-01-01T12:00:00Z",
            "lastModifiedDateTime": "2023-01-01T12:00:00Z"
        }],
        "@odata.nextLink": None
    }

    async def get_side_effect(url, headers):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        if "/me/joinedTeams" in url:
            mock_resp.json.return_value = teams_response
        elif "/teams/team1/channels" in url:
            mock_resp.json.return_value = channels_response
        elif "/teams/team1/channels/channel1/messages" in url:
            mock_resp.json.return_value = messages_response
        else:
            mock_resp.json.return_value = {"value": []}
        return mock_resp

    mock_client = AsyncMock()
    mock_client.get.side_effect = get_side_effect

    with patch('ingestion_pipeline.msteams_extractor.httpx.AsyncClient', return_value=mock_client) as Patcher:
        yield mock_client

@pytest.fixture
def mock_decrypt():
    """Mocks the decrypt function."""
    with patch('ingestion_pipeline.msteams_extractor.decrypt', return_value="decrypted_refresh_token") as mock:
        yield mock

@pytest.mark.asyncio
async def test_extract_data_from_msteams_happy_path(
    mock_db_conn_pool, mock_msal_app, mock_httpx_client, mock_decrypt
):
    # Arrange
    user_id = "test_user_msteams"

    # Act
    results = await extract_data_from_msteams(user_id=user_id, db_conn_pool=mock_db_conn_pool)

    # Assert
    assert len(results) == 1
    result = results[0]
    assert result["document_id"] == "msteams:channel1:msg1"
    assert result["document_title"] == "Message in #General"
    assert result["full_text"] == "Hello from Teams"
    assert result["source"] == "msteams"

    # Verify mocks
    mock_decrypt.assert_called_once()
    mock_msal_app.acquire_token_by_refresh_token.assert_called_once()
    assert mock_httpx_client.get.call_count == 3 # 1 for teams, 1 for channels, 1 for messages
