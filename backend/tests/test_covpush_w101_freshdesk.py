# -*- coding: utf-8 -*-
"""Coverage wave 101 — integrations/freshdesk_routes.

Standalone route tests via a minimal FastAPI TestClient app that includes only
this router; `get_freshdesk_service` is patched per test. Zero network, zero
LLM spend.

Covers: /auth/url, /status (configured / not), /health (healthy / not
configured / error -> generic), /tickets GET+POST, /tickets/{id} GET+PUT,
/contacts, /agents, /search/tickets — success, 503 fail-closed when the
service is None, and 500 "Internal error" with no str(e) leak. Query
validation (page ge=1, per_page le=100 -> 422).

Bugs fixed (TDD RED -> GREEN):
- freshdesk_routes imported `get_freshdesk_service` from freshdesk_service,
  but that factory never existed -> ImportError on module import, so every
  route was dead (404/500). Added get_freshdesk_service() to
  integrations/freshdesk_service.py: returns a FreshdeskService built from
  FRESHDESK_API_KEY/FRESHDESK_DOMAIN env, or None (fail-closed -> routes 503).
- /health leaked str(e) in the error branch; now generic with server-side log.
"""
import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.freshdesk_routes import router, TicketCreateRequest, TicketUpdateRequest, SearchRequest


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def patched_service():
    with patch("integrations.freshdesk_routes.get_freshdesk_service") as m:
        svc = AsyncMock()
        svc.health_check.return_value = {"status": "healthy", "healthy": True}
        svc.get_tickets.return_value = [{"id": 1}]
        svc.create_ticket.side_effect = lambda data: {"id": 2, **data}
        svc.get_ticket.side_effect = lambda ticket_id: {"id": ticket_id}
        svc.update_ticket.side_effect = lambda ticket_id, data: {"id": ticket_id, **data}
        svc.get_contacts.return_value = [{"id": 10}]
        svc.get_agents.return_value = [{"id": 20}]
        svc.search_tickets.side_effect = lambda query: [{"id": 30, "subject": query}]
        m.return_value = svc
        yield svc


class TestModels:
    def test_ticket_create_request_defaults(self):
        r = TicketCreateRequest(subject="s", description="d", email="e@x.com")
        assert r.priority == 1
        assert r.status == 2

    def test_ticket_update_request_all_optional(self):
        r = TicketUpdateRequest()
        assert r.status is None and r.priority is None

    def test_search_request(self):
        assert SearchRequest(query="q").query == "q"


class TestAuthUrl:
    def test_returns_info(self, client):
        resp = client.get("/freshdesk/auth/url")
        assert resp.status_code == 200
        body = resp.json()
        assert "API key" in body["message"]
        assert "timestamp" in body


class TestStatus:
    def test_configured(self, client, patched_service):
        resp = client.get("/freshdesk/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["configured"] is True
        assert body["service"] == "freshdesk"

    def test_not_configured(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.get("/freshdesk/status")
        assert resp.status_code == 200
        assert resp.json()["configured"] is False


class TestHealth:
    def test_healthy(self, client, patched_service):
        resp = client.get("/freshdesk/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_not_configured(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.get("/freshdesk/health")
        assert resp.status_code == 200
        assert resp.json() == {"ok": False, "status": "not_configured",
                               "timestamp": resp.json()["timestamp"]}

    def test_service_unhealthy(self, client):
        class BadService:
            async def health_check(self):
                return {"status": "unhealthy", "healthy": False, "error": "x"}
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.get("/freshdesk/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_exception_generic_no_leak(self, client):
        """RED: leaked str(e) to clients; must be generic."""
        class ThrowingService:
            async def health_check(self):
                raise RuntimeError("secret-detail")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=ThrowingService()):
            resp = client.get("/freshdesk/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
        assert resp.json()["status"] == "unhealthy"
        assert "secret-detail" not in resp.text


class TestGetTickets:
    def test_success(self, client, patched_service):
        resp = client.get("/freshdesk/tickets", params={"page": 2, "per_page": 50, "status": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["tickets"] == [{"id": 1}]
        patched_service.get_tickets.assert_awaited_once_with(
            page=2, per_page=50, status="3")

    def test_success_no_status(self, client, patched_service):
        client.get("/freshdesk/tickets")
        patched_service.get_tickets.assert_awaited_once_with(
            page=1, per_page=30, status=None)

    def test_not_configured_503(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.get("/freshdesk/tickets")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Freshdesk not configured"

    def test_service_error_500_no_leak(self, client):
        class BadService:
            async def get_tickets(self, **kw):
                raise RuntimeError("ticket-secret")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.get("/freshdesk/tickets")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"
        assert "ticket-secret" not in resp.text

    def test_invalid_page_422(self, client, patched_service):
        resp = client.get("/freshdesk/tickets", params={"page": 0})
        assert resp.status_code == 422

    def test_invalid_per_page_422(self, client, patched_service):
        resp = client.get("/freshdesk/tickets", params={"per_page": 101})
        assert resp.status_code == 422


class TestCreateTicket:
    def test_success(self, client, patched_service):
        payload = {"subject": "Help", "description": "desc", "email": "a@b.c", "priority": 2, "status": 3}
        resp = client.post("/freshdesk/tickets", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["ticket"]["id"] == 2
        patched_service.create_ticket.assert_awaited_once_with(payload)

    def test_not_configured_503(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.post("/freshdesk/tickets", json={"subject": "s", "description": "d", "email": "e@x.com"})
        assert resp.status_code == 503

    def test_service_error_500_no_leak(self, client):
        class BadService:
            async def create_ticket(self, data):
                raise RuntimeError("create-secret")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.post("/freshdesk/tickets", json={"subject": "s", "description": "d", "email": "e@x.com"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"
        assert "create-secret" not in resp.text

    def test_validation_422(self, client, patched_service):
        resp = client.post("/freshdesk/tickets", json={"subject": "s"})
        assert resp.status_code == 422


class TestGetTicket:
    def test_success(self, client, patched_service):
        resp = client.get("/freshdesk/tickets/42")
        assert resp.status_code == 200
        assert resp.json()["ticket"] == {"id": 42}
        patched_service.get_ticket.assert_awaited_once_with(42)

    def test_not_configured_503(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.get("/freshdesk/tickets/42")
        assert resp.status_code == 503

    def test_service_error_500_no_leak(self, client):
        class BadService:
            async def get_ticket(self, ticket_id):
                raise RuntimeError("get-secret")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.get("/freshdesk/tickets/42")
        assert resp.status_code == 500
        assert "get-secret" not in resp.text


class TestUpdateTicket:
    def test_success_partial(self, client, patched_service):
        resp = client.put("/freshdesk/tickets/42", json={"priority": 4})
        assert resp.status_code == 200
        assert resp.json()["ticket"] == {"id": 42, "priority": 4}
        patched_service.update_ticket.assert_awaited_once_with(42, {"priority": 4})

    def test_success_empty_body(self, client, patched_service):
        resp = client.put("/freshdesk/tickets/42", json={})
        assert resp.status_code == 200
        patched_service.update_ticket.assert_awaited_once_with(42, {})

    def test_not_configured_503(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.put("/freshdesk/tickets/42", json={"status": 4})
        assert resp.status_code == 503

    def test_service_error_500_no_leak(self, client):
        class BadService:
            async def update_ticket(self, ticket_id, data):
                raise RuntimeError("update-secret")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.put("/freshdesk/tickets/42", json={"status": 4})
        assert resp.status_code == 500
        assert "update-secret" not in resp.text


class TestGetContacts:
    def test_success(self, client, patched_service):
        resp = client.get("/freshdesk/contacts", params={"page": 2})
        assert resp.status_code == 200
        assert resp.json()["contacts"] == [{"id": 10}]
        patched_service.get_contacts.assert_awaited_once_with(page=2, per_page=30)

    def test_not_configured_503(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.get("/freshdesk/contacts")
        assert resp.status_code == 503

    def test_service_error_500(self, client):
        class BadService:
            async def get_contacts(self, **kw):
                raise RuntimeError("contacts-secret")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.get("/freshdesk/contacts")
        assert resp.status_code == 500
        assert "contacts-secret" not in resp.text


class TestGetAgents:
    def test_success(self, client, patched_service):
        resp = client.get("/freshdesk/agents")
        assert resp.status_code == 200
        assert resp.json()["agents"] == [{"id": 20}]
        patched_service.get_agents.assert_awaited_once()

    def test_not_configured_503(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.get("/freshdesk/agents")
        assert resp.status_code == 503

    def test_service_error_500(self, client):
        class BadService:
            async def get_agents(self):
                raise RuntimeError("agents-secret")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.get("/freshdesk/agents")
        assert resp.status_code == 500
        assert "agents-secret" not in resp.text


class TestSearchTickets:
    def test_success(self, client, patched_service):
        resp = client.post("/freshdesk/search/tickets", json={"query": "billing"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "billing"
        assert body["results"] == [{"id": 30, "subject": "billing"}]
        patched_service.search_tickets.assert_awaited_once_with("billing")

    def test_not_configured_503(self, client):
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=None):
            resp = client.post("/freshdesk/search/tickets", json={"query": "x"})
        assert resp.status_code == 503

    def test_service_error_500(self, client):
        class BadService:
            async def search_tickets(self, query):
                raise RuntimeError("search-secret")
        with patch("integrations.freshdesk_routes.get_freshdesk_service",
                   return_value=BadService()):
            resp = client.post("/freshdesk/search/tickets", json={"query": "x"})
        assert resp.status_code == 500
        assert "search-secret" not in resp.text

    def test_validation_422(self, client, patched_service):
        resp = client.post("/freshdesk/search/tickets", json={})
        assert resp.status_code == 422
