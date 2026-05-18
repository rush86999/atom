from __future__ import annotations

"""
Shared test fixtures for webhook testing.

Provides:
- mock_webhook_payload: Valid webhook payloads for various providers
- webhook_test_client: TestClient with CSRF bypassed
- mock_tenant_integration: Creates tenant + integration in DB
- mock_redis_client: Mock Redis for queue testing
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.database import get_db
from core.models import Tenant, TenantIntegration, User, UserConnection


@pytest.fixture
def mock_webhook_payload():
    """Factory for generating valid webhook payloads by provider."""

    def _payload(provider_id: str, event_type: str = "created") -> dict[str, Any]:
        """Generate a mock webhook payload for testing."""
        payloads = {
            "slack": {
                "type": "event_callback",
                "team_id": "T_SLACK_123",
                "event": {
                    "type": "message",
                    "ts": "1234567890.123456",
                    "user": "U_USER_123",
                    "text": "Test message",
                    "channel": "C_CHANNEL_123",
                },
            },
            "hubspot": {
                "portalId": "PORTAL_123",
                "eventId": 123,
                "subscriptionId": 456,
                "eventType": "contact.creation",
                "objectId": 789,
            },
            "salesforce": {
                "orgId": "00D_SALESFORCE_123",
                "eventId": "event_123",
                "payload": {
                    "CreatedDate": "2024-01-01T00:00:00Z",
                    "CreatedById": "USER_123",
                },
            },
            "gmail": {
                "message": {
                    "data": base64_url_encode({
                        "emailAddress": "test@example.com",
                        "historyId": "123456",
                    }),
                },
                "attributes": {},
            },
            "notion": {
                "workspace_id": "WORKSPACE_123",
                "event": {
                    "type": "page.created",
                    "page": {
                        "id": "PAGE_123",
                    },
                },
            },
            "outlook": {
                "value": [
                    {
                        "clientState": "signed::state",
                        "subscriptionId": "SUB_123",
                        "resource": "messages/MSG_123",
                    }
                ]
            },
            "asana": {
                "events": [
                    {
                        "event": "created",
                        "resource": "TASK_123",
                        "workspace": "WORKSPACE_123",
                    }
                ]
            },
            "jira": {
                "issue": {
                    "id": "ISSUE_123",
                    "key": "PROJ-123",
                    "fields": {
                        "project": {"key": "PROJ"},
                    },
                }
            },
            "github": {
                "action": "opened",
                "installation": {"id": 123456},
                "repository": {
                    "id": 12345678,
                    "name": "test-repo",
                    "owner": {"login": "testowner"},
                },
            },
            "trello": {
                "model": {
                    "id": "CARD_123",
                    "idOrganization": "ORG_123",
                    "name": "Test Card",
                }
            },
        }

        return payloads.get(provider_id, {
            "provider": provider_id,
            "event_type": event_type,
            "data": {"test": "payload"},
        })

    return _payload


@pytest.fixture
def webhook_test_client(fastapi_app, db_session):
    """
    TestClient with CSRF bypassed for webhook testing.

    Webhooks don't have CSRF tokens, so we bypass CSRF validation.
    """
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # Mock CSRF bypass
    fastapi_app.middleware = []

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def mock_tenant_integration(db_session):
    """
    Creates a mock tenant and integration for testing.

    Returns:
        Dict with tenant_id, integration_id, and test data
    """
    tenant_id = str(uuid.uuid4())
    subdomain = f"test-{tenant_id[:8]}"

    # Create tenant
    tenant = Tenant(
        id=tenant_id,
        subdomain=subdomain,
        name="Test Tenant",
    )
    db_session.add(tenant)
    db_session.flush()

    # Create user
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email="test@example.com",
        name="Test User",
    )
    db_session.add(user)
    db_session.flush()

    # Create integration config
    integration = TenantIntegration(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        connector_id="slack",
        external_id="T_SLACK_123",
        is_active=True,
        config={
            "slack_signing_secret": "test_secret",
            "webhook_enabled": True,
        },
    )
    db_session.add(integration)
    db_session.flush()

    # Create user connection
    connection = UserConnection(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user.id,
        integration_id="slack",
        status="active",
        external_user_id="U_USER_123",
        credentials={},
    )
    db_session.add(connection)
    db_session.commit()

    return {
        "tenant_id": tenant_id,
        "subdomain": subdomain,
        "user_id": user.id,
        "integration_id": integration.id,
        "connection_id": connection.id,
        "external_id": "T_SLACK_123",
    }


@pytest.fixture
def mock_redis_client():
    """
    Mock Redis client for queue testing.

    Simulates Redis operations without actual Redis connection.
    """
    redis_mock = MagicMock()

    # Mock list operations
    redis_mock.lpush = MagicMock(return_value=1)
    redis_mock.rpop = MagicMock(return_value=None)
    redis_mock.llen = MagicMock(return_value=0)
    redis_mock.lrange = MagicMock(return_value=[])

    # Mock key operations
    redis_mock.get = MagicMock(return_value=None)
    redis_mock.set = MagicMock(return_value=True)
    redis_mock.setex = MagicMock(return_value=True)
    redis_mock.delete = MagicMock(return_value=1)
    redis_mock.exists = MagicMock(return_value=False)
    redis_mock.setex = MagicMock(return_value=True)

    # Mock pub/sub
    redis_mock.publish = MagicMock(return_value=0)

    # Mock scan
    redis_mock.scan_iter = MagicMock(return_value=[])

    # Mock async versions
    async_redis_mock = AsyncMock()
    async_redis_mock.get = AsyncMock(return_value=None)
    async_redis_mock.set = AsyncMock(return_value=True)
    async_redis_mock.lpush = AsyncMock(return_value=1)
    async_redis_mock.rpop = AsyncMock(return_value=None)
    async_redis_mock.llen = AsyncMock(return_value=0)
    async_redis_mock.lrange = AsyncMock(return_value=[])
    async_redis_mock.publish = AsyncMock(return_value=0)

    redis_mock.async_client = async_redis_mock

    return redis_mock


@pytest.fixture
def mock_tenant_discovery():
    """
    Mock TenantDiscoveryService for testing.

    Simulates tenant resolution without database queries.
    """
    discovery_mock = MagicMock()

    async def mock_get_tenant(integration_id: str, external_id: str):
        if integration_id == "slack" and external_id == "T_SLACK_123":
            return str(uuid.uuid4())
        return None

    discovery_mock.get_tenant_id_by_external_id = mock_get_tenant

    return discovery_mock


# Helper function for base64 encoding (used in Gmail payload)
def base64_url_encode(data: dict[str, Any]) -> str:
    """Encode dict as base64url string (Gmail Pub/Sub format)."""
    import json
    import base64

    json_str = json.dumps(data)
    return base64.b64encode(json_str.encode()).decode()


# Webhook signature helpers for testing
@pytest.fixture
def webhook_signature_helper():
    """
    Helper for generating webhook signatures.

    Supports Slack, HubSpot, GitHub, and custom HMAC signatures.
    """
    import hmac
    import hashlib
    import time

    def slack_signature(payload: bytes, signing_secret: str) -> str:
        """Generate Slack webhook signature."""
        timestamp = str(int(time.time()))
        signature_base = f"v0:{timestamp}:".encode() + payload
        signature = hmac.new(
            signing_secret.encode(),
            signature_base,
            hashlib.sha256
        ).hexdigest()
        return f"v0={signature}"

    def hubspot_signature(payload: bytes, client_secret: str) -> str:
        """Generate HubSpot SHA-256 signature."""
        signature = hmac.new(
            client_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return signature

    def github_signature(payload: bytes, webhook_secret: str) -> str:
        """Generate GitHub SHA-256 signature."""
        signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def custom_hmac(payload: bytes, secret: str, algorithm: str = "sha256") -> str:
        """Generate custom HMAC signature."""
        signature = hmac.new(
            secret.encode(),
            payload,
            getattr(hashlib, algorithm)
        ).hexdigest()
        return signature

    return {
        "slack": slack_signature,
        "hubspot": hubspot_signature,
        "github": github_signature,
        "custom": custom_hmac,
    }


# Standard transformer output format (for testing)
@pytest.fixture
def standard_transformer_output():
    """
    Standard transformer output format.

    All transformers should produce records in this format.
    """
    def _record(
        record_id: str,
        sender_id: str,
        subject: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": record_id,
            "sender_id": sender_id,
            "subject": subject,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

    return _record
