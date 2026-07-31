"""
Round 45 — Fail-open webhook signature verification (Red-Green-Refactor).

The HubSpot, Salesforce, and Notion webhook handlers in
api/routes/webhooks/ingestion_webhooks.py claim to "Verify HMAC signature",
but the check is skipped entirely when the integration is not configured or
the signing secret is missing:

    if integration and integration.config:
        client_secret = integration.config.get("client_secret")
        if client_secret:
            if not verify_hmac_signature(...):
                raise 401

→ an attacker who knows the tenant's portal_id/orgId/workspace_id can POST
forged events with NO signature and have them processed (CRUD dispatch /
ingestion → data poisoning, workflow triggers). The Slack handler is the
reference: fail-closed (401/503 when verification is not configured).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.database import get_db


def make_client(db=None):
    from api.routes.webhooks.ingestion_webhooks import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def _discovery(tenant_id="tenant-1"):
    """Patch TenantDiscoveryService to resolve any external id to a tenant."""
    service = MagicMock()
    service.get_tenant_id_by_external_id = AsyncMock(return_value=tenant_id)
    return patch(
        "api.routes.webhooks.ingestion_webhooks.TenantDiscoveryService",
        return_value=service,
    )


class TestHubSpotWebhookFailClosed:
    def test_unconfigured_webhook_is_rejected(self):
        """No integration/secret configured → forged events must be rejected."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with _discovery(), patch(
            "core.webhook_crud_dispatch.crud_dispatch",
            new=AsyncMock(),
        ) as dispatch:
            resp = make_client(db).post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
            )
        assert resp.status_code in (401, 503), "unverified webhook must be rejected"
        assert not dispatch.called, "forged events must not reach CRUD dispatch"

    def test_configured_webhook_still_verifies(self):
        """With a secret configured, bad signatures stay rejected."""
        db = MagicMock()
        integration = MagicMock()
        integration.config = {"client_secret": "s3cr3t"}
        db.query.return_value.filter.return_value.first.return_value = integration

        with _discovery():
            resp = make_client(db).post(
                "/webhooks/hubspot/events",
                json=[{"portalId": "P1", "type": "contact.creation", "objectId": 1}],
                headers={"X-HubSpot-Signature": "deadbeef"},
            )
        assert resp.status_code == 401


class TestSalesforceWebhookFailClosed:
    def test_unconfigured_webhook_is_rejected(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with _discovery(), patch(
            "core.webhook_crud_dispatch.crud_dispatch",
            new=AsyncMock(),
        ) as dispatch:
            resp = make_client(db).post(
                "/webhooks/salesforce/events",
                json={"orgId": "O1", "eventType": "created"},
            )
        assert resp.status_code in (401, 503)
        assert not dispatch.called

    def test_configured_webhook_still_verifies(self):
        db = MagicMock()
        integration = MagicMock()
        integration.config = {"client_secret": "s3cr3t"}
        db.query.return_value.filter.return_value.first.return_value = integration

        with _discovery():
            resp = make_client(db).post(
                "/webhooks/salesforce/events",
                json={"orgId": "O1", "eventType": "created"},
                headers={"X-Salesforce-Signature": "deadbeef"},
            )
        assert resp.status_code == 401


class TestNotionWebhookFailClosed:
    def test_unconfigured_webhook_is_rejected(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with _discovery(), patch(
            "core.webhook_crud_dispatch.crud_dispatch",
            new=AsyncMock(),
        ) as dispatch:
            resp = make_client(db).post(
                "/webhooks/notion/events",
                json={"workspace_id": "W1", "type": "page.created"},
            )
        assert resp.status_code in (401, 503)
        assert not dispatch.called

    def test_configured_webhook_still_verifies(self):
        db = MagicMock()
        integration = MagicMock()
        integration.config = {"client_secret": "s3cr3t"}
        db.query.return_value.filter.return_value.first.return_value = integration

        with _discovery():
            resp = make_client(db).post(
                "/webhooks/notion/events",
                json={"workspace_id": "W1", "type": "page.created"},
                headers={"X-Notion-Signature": "deadbeef"},
            )
        assert resp.status_code == 401
