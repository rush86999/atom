"""R89 RED tests — the four never-verified webhook families must fail closed.

Finding: POST /webhooks/{zoho,pm-crm,communication,dev-prod}/{integration_id}
processed attacker-supplied bodies with NO signature verification (unlike
HubSpot/Salesforce/Notion/Outlook/Teams/Gmail/Shopify/Zendesk fixed in
R44-R69). Tenant resolution runs off public/enumerable payload fields and the
handlers dispatch CRUD — including deletions — using the victim tenant's
stored credentials.

Contract (R69 pattern): family secret env must be set (else 503), request
must carry X-Atom-Webhook-Signature = hex HMAC-SHA256 over the RAW body
(else 401).
"""
import hashlib
import hmac as hmac_mod
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.routes.webhooks.ingestion_webhooks import router

    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)


def _sig(secret: str, body: bytes) -> str:
    return hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


FAMILIES = [
    ("zoho", "zoho_crm", "ATOM_ZOHO_WEBHOOK_SECRET"),
    ("pm-crm", "monday", "ATOM_PMCRM_WEBHOOK_SECRET"),
    ("communication", "discord", "ATOM_COMMUNICATION_WEBHOOK_SECRET"),
    ("dev-prod", "github", "ATOM_DEVPROD_WEBHOOK_SECRET"),
]


@pytest.mark.parametrize("family,integration,env_name", FAMILIES)
def test_missing_secret_fails_closed(client, monkeypatch, family, integration, env_name):
    monkeypatch.delenv(env_name, raising=False)
    resp = client.post(
        f"/webhooks/{family}/{integration}",
        json={"orgId": "1", "event": {}},
    )
    assert resp.status_code == 503, (
        f"{family} webhook accepted events with no verification configured"
    )


@pytest.mark.parametrize("family,integration,env_name", FAMILIES)
def test_bad_signature_rejected(client, monkeypatch, family, integration, env_name):
    monkeypatch.setenv(env_name, "test-secret")
    body = b'{"orgId": "1", "event": {"type": "deleted"}}'
    resp = client.post(
        f"/webhooks/{family}/{integration}",
        content=body,
        headers={"X-Atom-Webhook-Signature": "deadbeef"},
    )
    assert resp.status_code == 401, f"{family}: {resp.status_code}"


@pytest.mark.parametrize("family,integration,env_name", FAMILIES)
def test_valid_signature_passes_verification(client, monkeypatch, family, integration, env_name):
    """With a correct signature the request proceeds past verification —
    downstream handling may still 4xx/5xx on business logic, but never on
    auth."""
    monkeypatch.setenv(env_name, "test-secret")
    body = b'{"orgId": "1", "event": {}}'
    resp = client.post(
        f"/webhooks/{family}/{integration}",
        content=body,
        headers={"X-Atom-Webhook-Signature": _sig("test-secret", body)},
    )
    assert resp.status_code not in (503, 401), (
        f"{family}: validly-signed request rejected at verification layer: "
        f"{resp.status_code}"
    )


def test_signature_binds_to_body_not_header_only(client, monkeypatch):
    """Replaying a valid signature over DIFFERENT bytes must fail."""
    monkeypatch.setenv("ATOM_ZOHO_WEBHOOK_SECRET", "test-secret")
    good = b'{"orgId": "1"}'
    evil = b'{"orgId": "999", "event": {"type": "deleted"}}'
    resp = client.post(
        "/webhooks/zoho/zoho_crm",
        content=evil,
        headers={"X-Atom-Webhook-Signature": _sig("test-secret", good)},
    )
    assert resp.status_code == 401
