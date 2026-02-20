"""
External Service Integration E2E Tests.

This module provides end-to-end tests for external service integrations
including Tavily search, Slack API, WhatsApp Business API, Shopify API,
and Atom SaaS marketplace sync.

Tests use real API calls when credentials are available, with high-quality
mocks for CI environments. All tests gracefully skip when credentials are
not configured.
"""
import asyncio
import os
import pytest
from datetime import datetime
from typing import Dict, Any

# Import service mock fixtures
from tests.e2e.fixtures.service_mock_fixtures import *


# ============================================================================
# Tavily Search Tests
# ============================================================================

class TestTavilySearch:
    """Test Tavily search integration with mock and real API."""

    @pytest.mark.asyncio
    async def test_tavily_search_basic(self, mock_tavily_search):
        """Test basic Tavily search functionality with mock."""
        import httpx

        # Simulate search request
        search_payload = {
            "query": "test search query",
            "search_depth": "basic",
            "max_results": 5
        }

        # Mock response will be returned
        response = httpx.post("https://api.tavily.com/search", json=search_payload)
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] == 0.95
        assert data["results"][0]["url"] == "https://example.com/test1"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("TAVILY_API_KEY") or os.getenv("TAVILY_API_KEY").startswith("test-"),
        reason="TAVILY_API_KEY not configured or is test value"
    )
    async def test_tavily_search_real(self):
        """Test real Tavily API call when credentials available."""
        import httpx

        api_key = os.getenv("TAVILY_API_KEY")
        search_url = "https://api.tavily.com/search"

        payload = {
            "api_key": api_key,
            "query": "Python programming",
            "search_depth": "basic",
            "max_results": 3
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(search_url, json=payload, timeout=10.0)
            response.raise_for_status()
            data = response.json()

        # Verify real API response
        assert "answer" in data or "results" in data
        assert isinstance(data.get("results", []), list)

    @pytest.mark.asyncio
    async def test_tavily_error_handling(self, mock_tavily_error):
        """Test Tavily error handling with mock error response."""
        import httpx

        search_payload = {
            "query": "test query",
            "api_key": "invalid_key"
        }

        try:
            response = httpx.post("https://api.tavily.com/search", json=search_payload)
            response.raise_for_status()
            assert False, "Should have raised HTTPStatusError"
        except Exception as e:
            # Error handling works
            assert "401" in str(e) or "INVALID" in str(e)

    @pytest.mark.asyncio
    async def test_tavily_search_result_parsing(self, mock_tavily_search):
        """Test Tavily search result parsing and extraction."""
        import httpx

        payload = {"query": "machine learning frameworks", "max_results": 5}
        response = httpx.post("https://api.tavily.com/search", json=payload)
        data = response.json()

        # Parse results
        results = data.get("results", [])
        assert len(results) > 0

        # Extract fields
        for result in results:
            assert "title" in result
            assert "url" in result
            assert "content" in result
            assert "score" in result
            assert isinstance(result["score"], float)
            assert 0.0 <= result["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_tavily_empty_results(self, mock_tavily_search):
        """Test Tavily search with no results."""
        import httpx
        from unittest import mock

        # Override mock to return empty results
        class EmptyResponse:
            status_code = 200
            def json(self):
                return {"answer": "", "results": []}

        def mock_post_with_empty(*args, **kwargs):
            return EmptyResponse()

        with mock.patch("httpx.post", side_effect=mock_post_with_empty):
            response = httpx.post("https://api.tavily.com/search", json={"query": "xyz"})
            data = response.json()

            assert data["results"] == []
            assert data["answer"] == ""


# ============================================================================
# Slack API Tests
# ============================================================================

class TestSlackAPI:
    """Test Slack API integration with mock and real webhook."""

    @pytest.mark.asyncio
    async def test_slack_webhook_basic(self, mock_slack_webhook):
        """Test basic Slack webhook post with mock."""
        import httpx

        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX"
        message = {
            "text": "Test message from Atom",
            "username": "Atom Bot",
            "icon_emoji": ":robot_face:"
        }

        response = httpx.post(webhook_url, json=message)
        data = response.json()

        assert response.status_code == 200
        assert data.get("ok") is True

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("SLACK_WEBHOOK_URL"),
        reason="SLACK_WEBHOOK_URL not configured"
    )
    async def test_slack_webhook_real(self):
        """Test real Slack webhook post when configured."""
        import httpx

        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        message = {
            "text": "E2E test message from Atom",
            "username": "Atom E2E Tests",
            "icon_emoji": ":test_tube:"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=message, timeout=5.0)
            response.raise_for_status()

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_slack_channel_message(self, mock_slack_api):
        """Test posting message to Slack channel via API."""
        client = mock_slack_api

        result = await client.chat_postMessage(
            channel="#general",
            text="Test message from API",
            username="Atom Bot"
        )

        assert result["ok"] is True
        assert "channel" in result
        assert result["message"]["text"] == "Test message from API"

    @pytest.mark.asyncio
    async def test_slack_conversations_list(self, mock_slack_api):
        """Test listing Slack conversations."""
        client = mock_slack_api

        result = await client.conversations_list()

        assert result["ok"] is True
        assert "channels" in result
        assert len(result["channels"]) == 3
        assert result["channels"][0]["name"] == "general"

    @pytest.mark.asyncio
    async def test_slack_users_list(self, mock_slack_api):
        """Test listing Slack users."""
        client = mock_slack_api

        result = await client.users_list()

        assert result["ok"] is True
        assert "members" in result
        assert len(result["members"]) == 2
        assert result["members"][0]["name"] == "alice"

    @pytest.mark.asyncio
    async def test_slack_formatted_message(self, mock_slack_webhook):
        """Test Slack message with formatting (blocks, attachments)."""
        import httpx

        webhook_url = "https://hooks.slack.com/services/T00/B00/XXX"
        message = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Test Message*\nFrom Atom E2E tests"
                    }
                }
            ]
        }

        response = httpx.post(webhook_url, json=message)
        assert response.status_code == 200


# ============================================================================
# WhatsApp Tests
# ============================================================================

class TestWhatsAppAPI:
    """Test WhatsApp Business API integration."""

    @pytest.mark.asyncio
    async def test_whatsapp_send_message(self, mock_whatsapp_api):
        """Test sending WhatsApp text message."""
        import httpx

        payload = {
            "messaging_product": "whatsapp",
            "to": "15551234567",
            "type": "text",
            "text": {"body": "Hello from Atom!"}
        }

        response = httpx.post(
            "https://graph.facebook.com/v18.0/123456789/messages",
            json=payload
        )
        data = response.json()

        assert response.status_code == 200
        assert data["messaging_product"] == "whatsapp"
        assert len(data["contacts"]) == 1
        assert len(data["messages"]) == 1

    @pytest.mark.asyncio
    async def test_whatsapp_send_template(self, mock_whatsapp_api):
        """Test sending WhatsApp template message."""
        import httpx

        payload = {
            "messaging_product": "whatsapp",
            "to": "15551234567",
            "type": "template",
            "template": {
                "name": "hello_world",
                "language": {"code": "en_US"}
            }
        }

        response = httpx.post(
            "https://graph.facebook.com/v18.0/123456789/messages",
            json=payload
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_whatsapp_webhook_handling(self):
        """Test handling incoming WhatsApp webhook."""
        webhook_data = mock_whatsapp_webhook()

        assert webhook_data["object"] == "whatsapp_business_account"
        assert len(webhook_data["entry"]) == 1

        # Extract message
        entry = webhook_data["entry"][0]
        changes = entry["changes"][0]
        message = changes["value"]["messages"][0]

        assert message["from"] == "15551234567"
        assert message["text"]["body"] == "Hello from WhatsApp!"

    @pytest.mark.asyncio
    async def test_whatsapp_media_handling(self, mock_whatsapp_api):
        """Test sending/receiving WhatsApp media messages."""
        import httpx

        payload = {
            "messaging_product": "whatsapp",
            "to": "15551234567",
            "type": "image",
            "image": {
                "link": "https://example.com/image.jpg",
                "caption": "Test image"
            }
        }

        response = httpx.post(
            "https://graph.facebook.com/v18.0/123456789/messages",
            json=payload
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_whatsapp_location_message(self, mock_whatsapp_api):
        """Test sending WhatsApp location message."""
        import httpx

        payload = {
            "messaging_product": "whatsapp",
            "to": "15551234567",
            "type": "location",
            "location": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "name": "San Francisco",
                "address": "CA, USA"
            }
        }

        response = httpx.post(
            "https://graph.facebook.com/v18.0/123456789/messages",
            json=payload
        )

        assert response.status_code == 200


# ============================================================================
# Shopify Tests
# ============================================================================

class TestShopifyAPI:
    """Test Shopify API integration."""

    def test_shopify_list_products(self, mock_shopify_api):
        """Test listing Shopify products."""
        client = mock_shopify_api

        result = client.get("admin/api/2023-10/products.json")

        assert "products" in result
        assert len(result["products"]) == 2
        assert result["products"][0]["title"] == "Test Product 1"
        assert result["products"][0]["inventory_quantity"] == 100

    def test_shopify_create_order(self, mock_shopify_api):
        """Test creating Shopify order."""
        client = mock_shopify_api

        order_data = {
            "order": {
                "line_items": [
                    {
                        "product_id": 1,
                        "quantity": 2
                    }
                ],
                "customer": {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com"
                }
            }
        }

        result = client.post("admin/api/2023-10/orders.json", json=order_data)

        assert "order" in result
        assert result["order"]["id"] == 1
        assert result["order"]["status"] == "pending"

    def test_shopify_update_inventory(self, mock_shopify_api):
        """Test updating Shopify product inventory."""
        client = mock_shopify_api

        update_data = {
            "product": {
                "id": 1,
                "inventory_quantity": 75
            }
        }

        result = client.put("admin/api/2023-10/products/1.json", json=update_data)

        assert "product" in result
        assert result["product"]["inventory_quantity"] == 75

    def test_shopify_webhook_handling(self, mock_shopify_webhook):
        """Test handling Shopify webhook payload."""
        webhook_data = mock_shopify_webhook

        assert webhook_data["topic"] == "products/create"
        assert webhook_data["shop"] == "test-shop.myshopify.com"
        assert webhook_data["data"]["id"] == 123456789
        assert webhook_data["data"]["title"] == "New Webhook Product"

    def test_shopify_product_variants(self, mock_shopify_api):
        """Test Shopify product with variants."""
        client = mock_shopify_api

        result = client.get("admin/api/2023-10/products/1.json")

        assert "products" in result
        product = result["products"][0]
        assert "variants" in product
        assert len(product["variants"]) == 1
        assert product["variants"][0]["id"] == 101

    def test_shopify_order_status_update(self, mock_shopify_api):
        """Test updating Shopify order status."""
        client = mock_shopify_api

        # First create an order
        order_data = {"order": {"customer": {"email": "test@example.com"}}}
        order_result = client.post("admin/api/2023-10/orders.json", json=order_data)

        # Update order status
        update_data = {"order": {"status": "fulfilled"}}
        result = client.put(
            f"admin/api/2023-10/orders/{order_result['order']['id']}.json",
            json=update_data
        )

        assert result["order"]["status"] == "fulfilled"


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Test rate limiting behavior and error handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_429_handling(self, mock_rate_limit):
        """Test handling 429 rate limit responses."""
        import httpx

        try:
            response = httpx.get("https://api.example.com/data")
            response.raise_for_status()
            assert False, "Should have raised HTTPStatusError"
        except Exception as e:
            # Verify rate limit error captured
            assert "429" in str(e)

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after_header(self, mock_rate_limit):
        """Test parsing Retry-After header from rate limit response."""
        import httpx

        response = httpx.get("https://api.example.com/data")

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert retry_after == 60

    @pytest.mark.asyncio
    async def test_rate_limit_backoff(self, mock_rate_limit_recovery):
        """Test exponential backoff on rate limit."""
        import httpx
        import asyncio

        # First call: rate limited, second call: success
        max_retries = 3
        backoff_base = 1

        for attempt in range(max_retries):
            response = httpx.get("https://api.example.com/data")

            if response.status_code == 429:
                wait_time = backoff_base * (2 ** attempt)
                await asyncio.sleep(wait_time * 0.01)  # Reduced for testing
                continue
            else:
                assert response.status_code == 200
                return  # Success

        assert False, "Should have succeeded after retry"

    @pytest.mark.asyncio
    async def test_rate_limit_recovery(self, mock_rate_limit_recovery):
        """Test recovery after rate limit expires."""
        import httpx

        # First call: rate limited
        response1 = httpx.get("https://api.example.com/data")
        assert response1.status_code == 429

        # Second call: success
        response2 = httpx.get("https://api.example.com/data")
        assert response2.status_code == 200
        assert response2.json()["data"] == "success"


# ============================================================================
# Atom SaaS Sync Tests
# ============================================================================

class TestAtomSaaSSync:
    """Test Atom SaaS marketplace sync functionality."""

    @pytest.mark.asyncio
    async def test_marketplace_skill_sync(self, mock_atom_saas_marketplace):
        """Test syncing skills from Atom SaaS marketplace."""
        client = mock_atom_saas_marketplace

        result = await client.sync_skills()

        assert result["synced"] == 2
        assert result["updated"] >= 0
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_marketplace_skill_list(self, mock_atom_saas_marketplace):
        """Test listing skills from marketplace."""
        client = mock_atom_saas_marketplace

        # List all skills
        all_skills = await client.list_skills()
        assert len(all_skills) == 2
        assert all_skills[0]["name"] == "Test CRM Sync"

        # Filter by category
        integration_skills = await client.list_skills(category="integration")
        assert len(integration_skills) == 1
        assert integration_skills[0]["category"] == "integration"

    @pytest.mark.asyncio
    async def test_rating_sync(self, mock_atom_saas_marketplace):
        """Test syncing ratings from marketplace."""
        client = mock_atom_saas_marketplace

        skill_ids = ["skill-001", "skill-002"]
        result = await client.sync_ratings(skill_ids)

        assert result["synced"] == 2
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_skill_rating_retrieval(self, mock_atom_saas_marketplace):
        """Test retrieving ratings for a specific skill."""
        client = mock_atom_saas_marketplace

        ratings = await client.get_skill_ratings("skill-001")

        assert len(ratings) == 2
        assert ratings[0]["rating"] == 5
        assert ratings[1]["rating"] == 4

    @pytest.mark.asyncio
    async def test_marketplace_incremental_sync(self, mock_atom_saas_marketplace):
        """Test incremental sync with timestamp filter."""
        client = mock_atom_saas_marketplace

        # Sync with last_sync timestamp
        result = await client.sync_skills(last_sync="2026-02-19T00:00:00Z")

        assert result["synced"] >= 0
        assert result["updated"] >= 0


# ============================================================================
# Integration Tests (Service Composition)
# ============================================================================

class TestServiceIntegration:
    """Test multiple services working together."""

    @pytest.mark.asyncio
    async def test_shopify_slack_notification(self, mock_shopify_api, mock_slack_api):
        """Test Shopify order triggering Slack notification."""
        shopify_client = mock_shopify_api
        slack_client = mock_slack_api

        # Create order in Shopify
        order_data = {"order": {"customer": {"email": "customer@example.com"}}}
        order_result = shopify_client.post(
            "admin/api/2023-10/orders.json",
            json=order_data
        )

        # Send Slack notification
        message = f"New order #{order_result['order']['order_number']} received!"
        slack_result = await slack_client.chat_postMessage(
            channel="#orders",
            text=message
        )

        assert order_result["order"]["id"] == 1
        assert slack_result["ok"] is True

    @pytest.mark.asyncio
    async def test_tavily_whatsapp_search_result(self, mock_tavily_search, mock_whatsapp_api):
        """Test Tavily search result sent via WhatsApp."""
        import httpx

        # Perform Tavily search
        search_payload = {"query": "Python tutorials"}
        tavily_response = httpx.post(
            "https://api.tavily.com/search",
            json=search_payload
        )
        search_data = tavily_response.json()

        # Send top result via WhatsApp
        top_result = search_data["results"][0]
        whatsapp_payload = {
            "messaging_product": "whatsapp",
            "to": "15551234567",
            "type": "text",
            "text": {"body": f"{top_result['title']}\n{top_result['url']}"}
        }

        whatsapp_response = httpx.post(
            "https://graph.facebook.com/v18.0/123456789/messages",
            json=whatsapp_payload
        )

        assert tavily_response.status_code == 200
        assert whatsapp_response.status_code == 200

    @pytest.mark.asyncio
    async def test_marketplace_skill_install_sync(self, mock_atom_saas_marketplace, mock_slack_api):
        """Test marketplace skill sync triggering notification."""
        marketplace_client = mock_atom_saas_marketplace
        slack_client = mock_slack_api

        # Sync skills
        sync_result = await marketplace_client.sync_skills()

        # Notify about new skills
        if sync_result["updated"] > 0:
            message = (
                f"Marketplace sync complete: "
                f"{sync_result['synced']} skills, "
                f"{sync_result['updated']} updated"
            )
            await slack_client.chat_postMessage(
                channel="#updates",
                text=message
            )

        assert sync_result["synced"] == 2
