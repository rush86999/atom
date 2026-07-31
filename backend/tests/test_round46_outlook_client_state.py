"""
Round 46 — Outlook webhook: clientState verification not enforced (Red-Green-Refactor).

api/routes/webhooks/ingestion_webhooks.py outlook_webhook_handler:
  - verify_client_state(client_state_signed) result is logged but IGNORED —
    on failure the handler continues to resolve the tenant (via the
    attacker-controlled Host/X-Forwarded-Host header), resolve the connection,
    and enqueue the notification (or run the deletion path, which deletes
    DiscoveredEntity rows). A forged clientState (valid JSON, no signature)
    is enough: no HMAC knowledge required.
  - The outer exception handler leaks str(e) to the client (line ~1007).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.database import get_db

SENTINEL = "SENTINEL_LEAK_round46"


def make_client(db=None):
    from api.routes.webhooks.ingestion_webhooks import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def make_db(tenant_id="t-1"):
    """db mock: Tenant query resolves; UserConnection/DiscoveredEntity return None."""
    from core.models import Tenant

    db = MagicMock()

    def query_side_effect(model, *a, **k):
        q = MagicMock()
        if model is Tenant:
            tenant = MagicMock()
            tenant.id = tenant_id
            q.filter.return_value.first.return_value = tenant
        else:
            q.filter.return_value.first.return_value = None
            q.filter.return_value.all.return_value = []
        return q

    db.query.side_effect = query_side_effect
    return db


def forged_notification(change_type="created", client_state=None):
    if client_state is None:
        # Valid JSON, NO signature — fails verify_client_state
        client_state = json.dumps({"c": "conn-abc"})
    return {
        "value": [
            {
                "clientState": client_state,
                "changeType": change_type,
                "resource": "Users/u-1/Messages/m-1",
                "subscriptionId": "sub-1",
                "subscriptionExpirationDateTime": "2026-12-31T00:00:00Z",
            }
        ]
    }


class TestOutlookClientStateEnforced:
    def test_invalid_client_state_not_enqueued(self):
        db = make_db()
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        queue.get_queue_depth = AsyncMock(return_value=1)
        queue.redis_client = None
        queue.queue_key = "k"

        with patch("api.routes.webhooks.ingestion_webhooks.webhook_queue", queue):
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json=forged_notification(),
                headers={"host": "victim.example.com"},
            )
        body = resp.json()
        # Must NOT be enqueued when clientState verification fails
        assert body.get("job_count", 0) == 0
        queue.enqueue_ingestion_job.assert_not_called()

    def test_invalid_client_state_no_deletion(self):
        """Forged 'deleted' events must not delete DiscoveredEntity rows."""
        from core.models import DiscoveredEntity, Tenant

        db = MagicMock()

        def query_side_effect(model, *a, **k):
            q = MagicMock()
            if model is Tenant:
                tenant = MagicMock()
                tenant.id = "t-1"
                q.filter.return_value.first.return_value = tenant
            elif model is DiscoveredEntity:
                q.filter.return_value.all.return_value = [
                    MagicMock(source_record_id="m-1")
                ]
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.all.return_value = []
            return q

        db.query.side_effect = query_side_effect

        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        queue.get_queue_depth = AsyncMock(return_value=1)
        queue.redis_client = None
        queue.queue_key = "k"

        with patch("api.routes.webhooks.ingestion_webhooks.webhook_queue", queue):
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json=forged_notification(change_type="deleted"),
                headers={"host": "victim.example.com"},
            )
        body = resp.json()
        assert body.get("job_count", 0) == 0
        db.delete.assert_not_called()

    def test_valid_client_state_is_enqueued(self, monkeypatch):
        """Regression guard: legitimately signed clientState still works."""
        from core.webhook_security import sign_client_state

        monkeypatch.setenv("WEBHOOK_CLIENT_STATE_SECRET", "round46-test-secret")

        db = make_db()
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        queue.get_queue_depth = AsyncMock(return_value=1)
        queue.redis_client = None
        queue.queue_key = "k"

        signed = sign_client_state(json.dumps({"c": "conn-abc"}))
        with patch("api.routes.webhooks.ingestion_webhooks.webhook_queue", queue):
            resp = make_client(db).post(
                "/webhooks/communication/outlook",
                json=forged_notification(client_state=signed),
                headers={"host": "victim.example.com"},
            )
        assert resp.status_code == 200
        assert resp.json().get("job_count") == 1
        queue.enqueue_ingestion_job.assert_awaited_once()

    def test_no_leak_on_processing_error(self):
        """str(e) must not reach the client when processing fails."""
        # A non-dict payload makes payload.get() raise before the loop —
        # reaching the outer handler that previously leaked str(e).
        resp = make_client(db=make_db()).post(
            "/webhooks/communication/outlook",
            json=[1, 2, 3],
            headers={"host": "victim.example.com"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # The client must see a generic message, not the exception text
        assert body.get("message") == "Webhook processing failed"
