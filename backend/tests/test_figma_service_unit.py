import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from integrations.figma_service import FigmaService


@pytest.fixture
def figma_service():
    with patch.dict(os.environ, {
        "FIGMA_CLIENT_ID": "test_client_id",
        "FIGMA_CLIENT_SECRET": "test_client_secret",
        "FIGMA_REDIRECT_URI": "http://localhost:3000/callback"
    }):
        service = FigmaService()
        service.client = AsyncMock()
        return service

@pytest.mark.asyncio
async def test_get_authorization_url(figma_service):
    url = figma_service.get_authorization_url(state="test_state")
    assert "https://www.figma.com/oauth" in url
    assert "client_id=test_client_id" in url
    assert "state=test_state" in url
    assert "scope=file_read" in url

@pytest.mark.asyncio
async def test_exchange_token_success(figma_service):
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 7776000,
        "user_id": "user_123"
    }
    figma_service.client.post.return_value = mock_response

    token_data = await figma_service.exchange_token("auth_code")

    assert token_data["access_token"] == "new_access_token"
    assert figma_service.access_token == "new_access_token"
    assert figma_service.refresh_token == "new_refresh_token"
    assert figma_service.token_expires_at is not None

@pytest.mark.asyncio
async def test_refresh_access_token_success(figma_service):
    figma_service.refresh_token = "old_refresh_token"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "refreshed_access_token",
        "expires_in": 7776000
    }
    figma_service.client.post.return_value = mock_response

    token_data = await figma_service.refresh_access_token()

    assert token_data["access_token"] == "refreshed_access_token"
    assert figma_service.access_token == "refreshed_access_token"

@pytest.mark.asyncio
async def test_get_user_info_success(figma_service):
    figma_service.access_token = "valid_token"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "123",
        "email": "test@example.com",
        "handle": "Test User"
    }
    figma_service.client.get.return_value = mock_response

    user_info = await figma_service.get_user_info()

    assert user_info["email"] == "test@example.com"
    assert figma_service.user_info == user_info

@pytest.mark.asyncio
async def test_get_file_success(figma_service):
    figma_service.access_token = "valid_token"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "document": {"id": "file_key", "name": "Test File"}
    }
    figma_service.client.get.return_value = mock_response

    file_data = await figma_service.get_file("file_key")

    assert file_data["document"]["name"] == "Test File"
    figma_service.client.get.assert_called_with(
        "https://api.figma.com/v1/files/file_key",
        headers={"Authorization": "Bearer valid_token", "Content-Type": "application/json"}
    )

@pytest.mark.asyncio
async def test_ensure_valid_token_refresh(figma_service):
    # Setup expired token
    figma_service.access_token = "expired_token"
    figma_service.token_expires_at = datetime.now() - timedelta(minutes=10)
    figma_service.refresh_token = "valid_refresh_token"

    # Mock refresh call
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new_token",
        "expires_in": 3600
    }
    figma_service.client.post.return_value = mock_response

    token = await figma_service.ensure_valid_token()

    assert token == "new_token"
    assert figma_service.access_token == "new_token"
