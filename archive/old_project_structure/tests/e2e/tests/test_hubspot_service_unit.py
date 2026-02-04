import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from integrations.hubspot_service import HubSpotService

@pytest.fixture
def hubspot_service():
    with patch.dict(os.environ, {"HUBSPOT_ACCESS_TOKEN": "test_token"}):
        service = HubSpotService()
        service.client = AsyncMock()
        return service

@pytest.mark.asyncio
async def test_authenticate_success(hubspot_service):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new_token",
        "refresh_token": "refresh_token",
        "expires_in": 1800
    }
    hubspot_service.client.post.return_value = mock_response

    result = await hubspot_service.authenticate("client_id", "secret", "http://callback", "code")

    assert result["access_token"] == "new_token"
    assert hubspot_service.access_token == "new_token"

@pytest.mark.asyncio
async def test_get_contacts_success(hubspot_service):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "1", "properties": {"email": "test@example.com"}}]
    }
    hubspot_service.client.get.return_value = mock_response

    contacts = await hubspot_service.get_contacts()

    assert len(contacts) == 1
    assert contacts[0]["properties"]["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_get_companies_success(hubspot_service):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "1", "properties": {"name": "Test Company"}}]
    }
    hubspot_service.client.get.return_value = mock_response

    companies = await hubspot_service.get_companies()

    assert len(companies) == 1
    assert companies[0]["properties"]["name"] == "Test Company"

@pytest.mark.asyncio
async def test_get_deals_success(hubspot_service):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "1", "properties": {"dealname": "Big Deal", "amount": "10000"}}]
    }
    hubspot_service.client.get.return_value = mock_response

    deals = await hubspot_service.get_deals()

    assert len(deals) == 1
    assert deals[0]["properties"]["dealname"] == "Big Deal"

@pytest.mark.asyncio
async def test_create_contact_success(hubspot_service):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "123", "properties": {"email": "new@example.com"}}
    hubspot_service.client.post.return_value = mock_response

    result = await hubspot_service.create_contact("new@example.com", "New", "User")

    assert result["id"] == "123"

@pytest.mark.asyncio
async def test_search_content_success(hubspot_service):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "1", "properties": {"email": "found@example.com"}}]
    }
    hubspot_service.client.post.return_value = mock_response

    results = await hubspot_service.search_content("found@example.com", "contact")

    assert "results" in results
    assert len(results["results"]) == 1

@pytest.mark.asyncio
async def test_health_check(hubspot_service):
    result = await hubspot_service.health_check()

    assert result["ok"] == True
    assert result["status"] == "healthy"
    assert result["service"] == "hubspot"
