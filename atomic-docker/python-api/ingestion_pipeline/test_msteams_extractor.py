import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ingestion_pipeline.msteams_extractor import extract_data_from_msteams

@pytest.fixture
def mock_get_token():
    """Mocks the token retrieval function from the token service."""
    with patch('ingestion_pipeline.msteams_extractor.get_msteams_token_from_service', new_callable=AsyncMock) as mock_func:
        mock_func.return_value = "mock_graph_api_token"
        yield mock_func

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

@pytest.mark.asyncio
async def test_extract_data_from_msteams_happy_path(mock_get_token, mock_httpx_client):
    # Arrange
    user_id = "test_user_msteams"
    db_conn_pool = None # No longer used directly

    # Act
    results = await extract_data_from_msteams(user_id=user_id, db_conn_pool=db_conn_pool)

    # Assert
    assert len(results) == 1
    result = results[0]
    assert result["document_id"] == "msteams:channel1:msg1"
    assert result["document_title"] == "Message in #General"
    assert result["full_text"] == "Hello from Teams"
    assert result["source"] == "msteams"

    # Verify mocks
    mock_get_token.assert_called_once_with(user_id)
    assert mock_httpx_client.get.call_count == 3
