"""
Service Mock Fixtures for External Service E2E Tests.

This module provides mock fixtures for external services when credentials
are unavailable (e.g., CI environments). Fixtures return high-quality
mocks that simulate real API responses for testing integration logic.
"""
import os
import httpx
import pytest
from typing import Any, Dict, List, Optional
from unittest import mock


# ============================================================================
# Tavily Search Mock Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_tavily_search():
    """Mock Tavily search API for testing without credentials."""
    class MockTavilyResponse:
        def __init__(self, status_code: int = 200):
            self.status_code = status_code
            self.headers = {"Content-Type": "application/json"}

        def json(self):
            return {
                "answer": "Test search result answer",
                "query": "test query",
                "results": [
                    {
                        "title": "Test Result 1",
                        "url": "https://example.com/test1",
                        "content": "Test content for result 1",
                        "score": 0.95,
                        "published_date": "2026-02-20"
                    },
                    {
                        "title": "Test Result 2",
                        "url": "https://example.com/test2",
                        "content": "Test content for result 2",
                        "score": 0.87,
                        "published_date": "2026-02-19"
                    }
                ]
            }

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {self.status_code}",
                    request=mock.Mock(),
                    response=self
                )

    def mock_post(url, *args, **kwargs):
        if "tavily" in url.lower() or "search" in url.lower():
            return MockTavilyResponse()
        return MockTavilyResponse()

    with mock.patch("httpx.post", side_effect=mock_post):
        yield


@pytest.fixture(scope="function")
def mock_tavily_error():
    """Mock Tavily search error for testing error handling."""
    class MockTavilyErrorResponse:
        status_code = 401
        headers = {"Content-Type": "application/json"}

        def json(self):
            return {
                "error": "Invalid API key",
                "code": "INVALID_API_KEY"
            }

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "HTTP 401",
                request=mock.Mock(),
                response=self
            )

    def mock_post(*args, **kwargs):
        return MockTavilyErrorResponse()

    with mock.patch("httpx.post", side_effect=mock_post):
        yield


# ============================================================================
# Slack Mock Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_slack_webhook():
    """Mock Slack webhook for testing without credentials."""
    class MockSlackResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def json(self):
            return {"ok": True}

        def raise_for_status(self):
            pass

    def mock_post(url, *args, **kwargs):
        if "hooks.slack.com" in url or "slack" in url.lower():
            return MockSlackResponse()
        return MockSlackResponse()

    with mock.patch("httpx.post", side_effect=mock_post):
        yield


@pytest.fixture(scope="function")
def mock_slack_api():
    """Mock Slack Web API for testing channel operations."""
    class MockSlackClient:
        def __init__(self):
            self.channels_sent = []

        async def chat_postMessage(self, channel: str, text: str, **kwargs):
            self.channels_sent.append({
                "channel": channel,
                "text": text,
                "kwargs": kwargs
            })
            return {
                "ok": True,
                "channel": channel,
                "ts": "1234567890.123456",
                "message": {"text": text}
            }

        async def conversations_list(self, **kwargs):
            return {
                "ok": True,
                "channels": [
                    {"id": "C01", "name": "general", "is_member": True},
                    {"id": "C02", "name": "random", "is_member": True},
                    {"id": "C03", "name": "alerts", "is_member": False}
                ]
            }

        async def users_list(self, **kwargs):
            return {
                "ok": True,
                "members": [
                    {"id": "U01", "name": "alice", "real_name": "Alice Smith"},
                    {"id": "U02", "name": "bob", "real_name": "Bob Jones"}
                ]
            }

    yield MockSlackClient()


# ============================================================================
# Shopify Mock Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_shopify_api():
    """Mock Shopify API for testing without credentials."""
    class MockShopifyClient:
        def __init__(self):
            self.products = [
                {
                    "id": 1,
                    "title": "Test Product 1",
                    "handle": "test-product-1",
                    "inventory_quantity": 100,
                    "variants": [{"id": 101, "inventory_quantity": 100}],
                    "status": "active"
                },
                {
                    "id": 2,
                    "title": "Test Product 2",
                    "handle": "test-product-2",
                    "inventory_quantity": 50,
                    "variants": [{"id": 201, "inventory_quantity": 50}],
                    "status": "active"
                }
            ]
            self.orders = []
            self.next_order_id = 1

        def get(self, endpoint, **kwargs):
            if "products" in endpoint:
                return {"products": self.products}
            elif "orders" in endpoint:
                return {"orders": self.orders}
            return {}

        def post(self, endpoint, **kwargs):
            if "orders" in endpoint:
                new_order = {
                    "id": self.next_order_id,
                    "order_number": self.next_order_id + 1000,
                    "status": "pending",
                    **kwargs.get("json", {})
                }
                self.orders.append(new_order)
                self.next_order_id += 1
                return {"order": new_order}
            return {}

        def put(self, endpoint, **kwargs):
            if "products" in endpoint:
                # Extract product ID from endpoint
                product_id = int(endpoint.split("/")[-1].split("?")[0])
                for product in self.products:
                    if product["id"] == product_id:
                        data = kwargs.get("json", {})
                        product.update(data)
                        return {"product": product}
            return {}

    yield MockShopifyClient()


@pytest.fixture(scope="function")
def mock_shopify_webhook():
    """Mock Shopify webhook payload for testing."""
    return {
        "topic": "products/create",
        "shop": "test-shop.myshopify.com",
        "data": {
            "id": 123456789,
            "title": "New Webhook Product",
            "status": "active",
            "inventory_quantity": 25
        },
        "timestamp": "2026-02-20T13:00:00Z"
    }


# ============================================================================
# WhatsApp Mock Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_whatsapp_api():
    """Mock WhatsApp Business API for testing."""
    class MockWhatsAppResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def json(self):
            return {
                "messaging_product": "whatsapp",
                "contacts": [{"input": "+15551234567", "wa_id": "5551234567"}],
                "messages": [{"id": "wamid.xxx", "status": "sent"}]
            }

        def raise_for_status(self):
            pass

    def mock_post(url, *args, **kwargs):
        if "whatsapp" in url.lower() or "graph.facebook.com" in url:
            return MockWhatsAppResponse()
        return MockWhatsAppResponse()

    with mock.patch("httpx.post", side_effect=mock_post):
        yield


@pytest.fixture(scope="function")
def mock_whatsapp_webhook():
    """Mock WhatsApp webhook payload for testing."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "15551234567",
                                    "id": "wamid.abc123",
                                    "timestamp": "1708440000",
                                    "text": {"body": "Hello from WhatsApp!"}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }


# ============================================================================
# Rate Limit Mock Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_rate_limit():
    """Mock rate limit response for testing error handling."""
    class MockRateLimitResponse:
        status_code = 429
        headers = {"Retry-After": "60", "X-RateLimit-Reset": "1708440060"}

        def json(self):
            return {
                "error": {
                    "message": "Rate limited",
                    "code": 429,
                    "type": "rate_limit_error"
                }
            }

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "HTTP 429",
                request=mock.Mock(),
                response=self
            )

    def mock_get(*args, **kwargs):
        return MockRateLimitResponse()

    def mock_post(*args, **kwargs):
        return MockRateLimitResponse()

    with mock.patch("httpx.get", side_effect=mock_get):
        with mock.patch("httpx.post", side_effect=mock_post):
            yield


@pytest.fixture(scope="function")
def mock_rate_limit_recovery():
    """Mock rate limit with automatic recovery after first call."""
    call_count = [0]

    class MockRateLimitRecoveryResponse:
        def __init__(self, is_rate_limited: bool):
            self.status_code = 429 if is_rate_limited else 200
            self.headers = {
                "Retry-After": "1",
                "X-RateLimit-Reset": "1708440061"
            } if is_rate_limited else {}

        def json(self):
            if self.status_code == 429:
                return {
                    "error": {
                        "message": "Rate limited",
                        "code": 429
                    }
                }
            return {"data": "success"}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {self.status_code}",
                    request=mock.Mock(),
                    response=self
                )

    def mock_get(*args, **kwargs):
        call_count[0] += 1
        is_limited = call_count[0] == 1
        return MockRateLimitRecoveryResponse(is_limited)

    with mock.patch("httpx.get", side_effect=mock_get):
        yield


# ============================================================================
# Real Client Fixtures (with API key detection)
# ============================================================================

@pytest.fixture(scope="function")
def real_tavily_client():
    """
    Create real Tavily client if API key available.

    Skips test if TAVILY_API_KEY not configured or is a test value.
    """
    import httpx

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        pytest.skip("TAVILY_API_KEY not configured")
    if api_key.startswith("test-") or len(api_key) < 20:
        pytest.skip("TAVILY_API_KEY appears to be a test value")

    return {
        "api_key": api_key,
        "base_url": "https://api.tavily.com"
    }


@pytest.fixture(scope="function")
def real_slack_webhook():
    """
    Create real Slack webhook URL if available.

    Skips test if SLACK_WEBHOOK_URL not configured.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        pytest.skip("SLACK_WEBHOOK_URL not configured")
    if not webhook_url.startswith("https://hooks.slack.com/"):
        pytest.skip("SLACK_WEBHOOK_URL appears invalid")

    return webhook_url


@pytest.fixture(scope="function")
def real_shopify_credentials():
    """
    Create real Shopify credentials if available.

    Skips test if SHOPIFY_STORE_URL or SHOPIFY_ACCESS_TOKEN not configured.
    """
    store_url = os.getenv("SHOPIFY_STORE_URL")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")

    if not store_url or not access_token:
        pytest.skip("SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN not configured")

    if not store_url.startswith("https://"):
        pytest.skip("SHOPIFY_STORE_URL must start with https://")

    if len(access_token) < 20:
        pytest.skip("SHOPIFY_ACCESS_TOKEN appears invalid")

    return {
        "store_url": store_url,
        "access_token": access_token
    }


@pytest.fixture(scope="function")
def real_whatsapp_credentials():
    """
    Create real WhatsApp credentials if available.

    Skips test if WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN not configured.
    """
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        pytest.skip("WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN not configured")

    return {
        "phone_number_id": phone_number_id,
        "access_token": access_token,
        "base_url": "https://graph.facebook.com/v18.0"
    }


# ============================================================================
# Atom SaaS Mock Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_atom_saas_marketplace():
    """Mock Atom SaaS marketplace for sync testing."""
    class MockMarketplaceClient:
        def __init__(self):
            self.skills = [
                {
                    "id": "skill-001",
                    "name": "Test CRM Sync",
                    "category": "integration",
                    "version": "1.0.0",
                    "rating": 4.5,
                    "rating_count": 42,
                    "description": "Sync CRM data",
                    "author": "atom",
                    "updated_at": "2026-02-20T12:00:00Z"
                },
                {
                    "id": "skill-002",
                    "name": "Test Notifier",
                    "category": "messaging",
                    "version": "2.1.0",
                    "rating": 4.8,
                    "rating_count": 128,
                    "description": "Send notifications",
                    "author": "community",
                    "updated_at": "2026-02-19T15:30:00Z"
                }
            ]
            self.ratings = [
                {"skill_id": "skill-001", "user_id": "user-1", "rating": 5, "comment": "Great!"},
                {"skill_id": "skill-001", "user_id": "user-2", "rating": 4, "comment": "Good"}
            ]

        async def list_skills(self, category: Optional[str] = None):
            if category:
                return [s for s in self.skills if s["category"] == category]
            return self.skills

        async def get_skill_ratings(self, skill_id: str):
            return [r for r in self.ratings if r["skill_id"] == skill_id]

        async def sync_skills(self, last_sync: Optional[str] = None):
            """Simulate skill sync with pagination."""
            return {
                "synced": len(self.skills),
                "updated": 1,
                "timestamp": "2026-02-20T13:00:00Z"
            }

        async def sync_ratings(self, skill_ids: List[str]):
            """Simulate rating sync."""
            synced = [
                r for r in self.ratings
                if r["skill_id"] in skill_ids
            ]
            return {
                "synced": len(synced),
                "timestamp": "2026-02-20T13:00:00Z"
            }

    yield MockMarketplaceClient()


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_httpx_client():
    """Generic httpx client mock for custom testing."""
    class MockClient:
        def __init__(self):
            self.requests = []

        async def get(self, url, **kwargs):
            self.requests.append({"method": "GET", "url": url, "kwargs": kwargs})
            return mock.Mock(
                status_code=200,
                json=lambda: {"data": "test"},
                raise_for_status=lambda: None
            )

        async def post(self, url, **kwargs):
            self.requests.append({"method": "POST", "url": url, "kwargs": kwargs})
            return mock.Mock(
                status_code=200,
                json=lambda: {"success": True},
                raise_for_status=lambda: None
            )

        async def put(self, url, **kwargs):
            self.requests.append({"method": "PUT", "url": url, "kwargs": kwargs})
            return mock.Mock(
                status_code=200,
                json=lambda: {"updated": True},
                raise_for_status=lambda: None
            )

        async def delete(self, url, **kwargs):
            self.requests.append({"method": "DELETE", "url": url, "kwargs": kwargs})
            return mock.Mock(
                status_code=204,
                json=lambda: {},
                raise_for_status=lambda: None
            )

    yield MockClient()
