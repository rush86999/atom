"""Coverage wave 92 — integrations/outlook_routes.py (45% → 95%+).

Closes the never-wave-tested gaps: OAuth URL/callback, email list/send/
draft/get-by-id/delete, calendar list/create, contacts list/create, tasks
list/create, search, profile, unread, health, memory backfill (with/without
date parsing, failure), backfill status (found/404/500), plus every 500
error branch on each endpoint.

Security: the router had NO auth dependency — this wave asserts 401 for
anonymous callers on every endpoint (RED) and wires Depends(get_current_user)
on the router (GREEN).

Webhooks: outlook_routes.py has no webhook endpoints; webhook fail-closed
behavior for Outlook lives in integrations/outlook_service.py (R46, tested
in test_round46_outlook_client_state.py) and
atom_communication_memory_webhooks.py — verified separately.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security_dependencies import get_current_user
from integrations import outlook_routes as orr

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(orr.router)
    return application


@pytest.fixture
def anon_client(app):
    return TestClient(app)


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(app)


@pytest.fixture
def svc():
    with patch.object(orr, "outlook_service") as m:
        yield m


class TestRouteAuth:
    """Security: every /api/outlook endpoint rejects anonymous callers."""

    @pytest.mark.parametrize("method,path", [
        ("get", "/api/outlook/auth/url"),
        ("get", "/api/outlook/callback?code=abc"),
        ("post", "/api/outlook/emails"),
        ("post", "/api/outlook/emails/send"),
        ("post", "/api/outlook/emails/draft"),
        ("get", "/api/outlook/emails/m1?user_id=u"),
        ("delete", "/api/outlook/emails/m1?user_id=u"),
        ("post", "/api/outlook/calendar/events"),
        ("post", "/api/outlook/calendar/events/create"),
        ("post", "/api/outlook/contacts"),
        ("post", "/api/outlook/contacts/create"),
        ("post", "/api/outlook/tasks"),
        ("post", "/api/outlook/tasks/create"),
        ("post", "/api/outlook/search"),
        ("get", "/api/outlook/profile?user_id=u"),
        ("get", "/api/outlook/emails/unread?user_id=u"),
        ("get", "/api/outlook/health"),
        ("post", "/api/outlook/memory/backfill"),
        ("get", "/api/outlook/memory/backfill/status/job1"),
    ])
    def test_anonymous_rejected(self, anon_client, method, path):
        resp = getattr(anon_client, method)(path)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


class TestOAuth:
    def test_auth_url(self, client):
        resp = client.get("/api/outlook/auth/url")
        assert resp.status_code == 200
        body = resp.json()
        assert "login.microsoftonline.com" in body["url"]

    def test_callback(self, client):
        resp = client.get("/api/outlook/callback", params={"code": "authcode1"})
        assert resp.status_code == 200
        assert resp.json()["code"] == "authcode1"


class TestEmails:
    def test_list_success(self, client, svc):
        svc.get_user_emails = AsyncMock(return_value=[{"id": "m1"}, {"id": "m2"}])
        resp = client.post("/api/outlook/emails", json={
            "user_id": "u1", "folder": "inbox", "query": "q", "max_results": 5, "skip": 2})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        assert resp.json()["folder"] == "inbox"
        svc.get_user_emails.assert_awaited_once_with(
            user_id="u1", folder="inbox", query="q", max_results=5, skip=2)

    def test_list_error_500(self, client, svc):
        svc.get_user_emails = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/emails", json={"user_id": "u1"})
        assert resp.status_code == 500

    def test_send_success(self, client, svc):
        svc.send_email = AsyncMock(return_value={"id": "m9"})
        resp = client.post("/api/outlook/emails/send", json={
            "user_id": "u1", "to_recipients": ["a@b.com"], "subject": "S", "body": "B",
            "cc_recipients": ["c@d.com"], "bcc_recipients": ["e@f.com"]})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Email sent successfully"

    def test_send_falsy_500(self, client, svc):
        svc.send_email = AsyncMock(return_value=None)
        resp = client.post("/api/outlook/emails/send", json={
            "user_id": "u1", "to_recipients": ["a@b.com"], "subject": "S", "body": "B"})
        assert resp.status_code == 500

    def test_send_error_500(self, client, svc):
        svc.send_email = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/emails/send", json={
            "user_id": "u1", "to_recipients": ["a@b.com"], "subject": "S", "body": "B"})
        assert resp.status_code == 500

    def test_draft_success(self, client, svc):
        svc.create_draft_email = AsyncMock(return_value={"id": "d1"})
        resp = client.post("/api/outlook/emails/draft", json={
            "user_id": "u1", "to_recipients": ["a@b.com"], "subject": "S", "body": "B"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Draft email created successfully"

    def test_draft_falsy_500(self, client, svc):
        svc.create_draft_email = AsyncMock(return_value=None)
        resp = client.post("/api/outlook/emails/draft", json={
            "user_id": "u1", "to_recipients": ["a@b.com"], "subject": "S", "body": "B"})
        assert resp.status_code == 500

    def test_draft_error_500(self, client, svc):
        svc.create_draft_email = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/emails/draft", json={
            "user_id": "u1", "to_recipients": ["a@b.com"], "subject": "S", "body": "B"})
        assert resp.status_code == 500

    def test_get_email_success(self, client, svc):
        svc.get_email_by_id = AsyncMock(return_value={"id": "m1"})
        resp = client.get("/api/outlook/emails/m1", params={"user_id": "u1"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "m1"

    def test_get_email_404(self, client, svc):
        svc.get_email_by_id = AsyncMock(return_value=None)
        resp = client.get("/api/outlook/emails/m1", params={"user_id": "u1"})
        assert resp.status_code == 404

    def test_get_email_error_500(self, client, svc):
        svc.get_email_by_id = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.get("/api/outlook/emails/m1", params={"user_id": "u1"})
        assert resp.status_code == 500

    def test_delete_success(self, client, svc):
        svc.delete_email = AsyncMock(return_value=True)
        resp = client.delete("/api/outlook/emails/m1", params={"user_id": "u1"})
        assert resp.status_code == 200

    def test_delete_falsy_500(self, client, svc):
        svc.delete_email = AsyncMock(return_value=False)
        resp = client.delete("/api/outlook/emails/m1", params={"user_id": "u1"})
        assert resp.status_code == 500

    def test_delete_error_500(self, client, svc):
        svc.delete_email = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.delete("/api/outlook/emails/m1", params={"user_id": "u1"})
        assert resp.status_code == 500


class TestCalendar:
    def test_list_success(self, client, svc):
        svc.get_calendar_events = AsyncMock(return_value=[{"id": "e1"}])
        resp = client.post("/api/outlook/calendar/events", json={
            "user_id": "u1", "time_min": "2026-01-01", "time_max": "2026-01-02",
            "max_results": 10})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_list_error_500(self, client, svc):
        svc.get_calendar_events = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/calendar/events", json={"user_id": "u1"})
        assert resp.status_code == 500

    def test_create_success(self, client, svc):
        svc.create_calendar_event = AsyncMock(return_value={"id": "e9"})
        resp = client.post("/api/outlook/calendar/events/create", json={
            "user_id": "u1", "subject": "Sync", "body": "b",
            "start": {"dateTime": "x"}, "end": {"dateTime": "y"},
            "location": {"displayName": "Rm 1"}, "attendees": ["a@b.com"]})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Calendar event created successfully"

    def test_create_falsy_500(self, client, svc):
        svc.create_calendar_event = AsyncMock(return_value=None)
        resp = client.post("/api/outlook/calendar/events/create", json={
            "user_id": "u1", "subject": "S"})
        assert resp.status_code == 500

    def test_create_error_500(self, client, svc):
        svc.create_calendar_event = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/calendar/events/create", json={
            "user_id": "u1", "subject": "S"})
        assert resp.status_code == 500


class TestContacts:
    def test_list_success(self, client, svc):
        svc.get_user_contacts = AsyncMock(return_value=[{"id": "c1"}])
        resp = client.post("/api/outlook/contacts", json={
            "user_id": "u1", "query": "bob", "max_results": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_list_error_500(self, client, svc):
        svc.get_user_contacts = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/contacts", json={"user_id": "u1"})
        assert resp.status_code == 500

    def test_create_success(self, client, svc):
        svc.create_contact = AsyncMock(return_value={"id": "c9"})
        resp = client.post("/api/outlook/contacts/create", json={
            "user_id": "u1", "display_name": "Bob", "given_name": "B", "surname": "S",
            "email_addresses": [{"address": "b@c.com"}], "business_phones": ["1"],
            "company_name": "ACME"})
        assert resp.status_code == 200

    def test_create_falsy_500(self, client, svc):
        svc.create_contact = AsyncMock(return_value=None)
        resp = client.post("/api/outlook/contacts/create", json={
            "user_id": "u1", "display_name": "Bob"})
        assert resp.status_code == 500

    def test_create_error_500(self, client, svc):
        svc.create_contact = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/contacts/create", json={
            "user_id": "u1", "display_name": "Bob"})
        assert resp.status_code == 500


class TestTasks:
    def test_list_success(self, client, svc):
        svc.get_user_tasks = AsyncMock(return_value=[{"id": "t1"}])
        resp = client.post("/api/outlook/tasks", json={
            "user_id": "u1", "status": "completed", "max_results": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_list_error_500(self, client, svc):
        svc.get_user_tasks = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/tasks", json={"user_id": "u1"})
        assert resp.status_code == 500

    def test_create_success(self, client, svc):
        svc.create_task = AsyncMock(return_value={"id": "t9"})
        resp = client.post("/api/outlook/tasks/create", json={
            "user_id": "u1", "subject": "Task", "body": "b", "importance": "high",
            "due_date_time": {"dateTime": "x"}, "categories": ["work"]})
        assert resp.status_code == 200

    def test_create_falsy_500(self, client, svc):
        svc.create_task = AsyncMock(return_value=None)
        resp = client.post("/api/outlook/tasks/create", json={
            "user_id": "u1", "subject": "Task"})
        assert resp.status_code == 500

    def test_create_error_500(self, client, svc):
        svc.create_task = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/tasks/create", json={
            "user_id": "u1", "subject": "Task"})
        assert resp.status_code == 500


class TestSearchProfileUnread:
    def test_search_success(self, client, svc):
        svc.search_emails = AsyncMock(return_value=[{"id": "m1"}])
        resp = client.post("/api/outlook/search", json={
            "user_id": "u1", "query": "invoice", "max_results": 3})
        assert resp.status_code == 200
        assert resp.json()["query"] == "invoice"

    def test_search_error_500(self, client, svc):
        svc.search_emails = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/outlook/search", json={"user_id": "u1", "query": "q"})
        assert resp.status_code == 500

    def test_profile_success(self, client, svc):
        svc.get_user_profile = AsyncMock(return_value={"displayName": "Bob"})
        resp = client.get("/api/outlook/profile", params={"user_id": "u1"})
        assert resp.status_code == 200

    def test_profile_404(self, client, svc):
        svc.get_user_profile = AsyncMock(return_value=None)
        resp = client.get("/api/outlook/profile", params={"user_id": "u1"})
        assert resp.status_code == 404

    def test_profile_error_500(self, client, svc):
        svc.get_user_profile = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.get("/api/outlook/profile", params={"user_id": "u1"})
        assert resp.status_code == 500

    def test_unread_success(self, client, svc):
        svc.get_unread_emails = AsyncMock(return_value=[{"id": "u1"}, {"id": "u2"}])
        resp = client.get("/api/outlook/emails/unread",
                          params={"user_id": "u1", "max_results": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        svc.get_unread_emails.assert_awaited_once_with("u1", 5)

    def test_unread_error_500(self, client, svc):
        svc.get_unread_emails = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.get("/api/outlook/emails/unread", params={"user_id": "u1"})
        assert resp.status_code == 500


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/outlook/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestMemoryBackfill:
    def test_backfill_with_dates(self, client, svc):
        with patch("integrations.outlook_integration.outlook_integration") as oi:
            oi.backfill_to_memory = AsyncMock(return_value={"job_id": "j1"})
            resp = client.post("/api/outlook/memory/backfill",
                               params={"start_date": "2026-01-01T00:00:00Z",
                                       "end_date": "2026-01-02T00:00:00Z",
                                       "limit": 100})
        assert resp.status_code == 200
        assert resp.json()["data"] == {"job_id": "j1"}
        kwargs = oi.backfill_to_memory.await_args[1]
        assert kwargs["start_date"].isoformat() == "2026-01-01T00:00:00+00:00"
        assert kwargs["limit"] == 100

    def test_backfill_no_dates(self, client, svc):
        with patch("integrations.outlook_integration.outlook_integration") as oi:
            oi.backfill_to_memory = AsyncMock(return_value={"job_id": "j2"})
            resp = client.post("/api/outlook/memory/backfill")
        assert resp.status_code == 200
        kwargs = oi.backfill_to_memory.await_args[1]
        assert kwargs["start_date"] is None
        assert kwargs["end_date"] is None
        assert kwargs["limit"] == 500

    def test_backfill_error_500(self, client, svc):
        with patch("integrations.outlook_integration.outlook_integration") as oi:
            oi.backfill_to_memory = AsyncMock(side_effect=RuntimeError("boom"))
            resp = client.post("/api/outlook/memory/backfill",
                               params={"start_date": "not-a-date"})
        assert resp.status_code == 500

    def test_backfill_status_found(self, client, svc):
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin.get_job_status",
                   return_value={"status": "done"}) as js:
            resp = client.get("/api/outlook/memory/backfill/status/job1")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "done"
        js.assert_called_once_with("job1")

    def test_backfill_status_404(self, client, svc):
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin.get_job_status",
                   return_value=None):
            resp = client.get("/api/outlook/memory/backfill/status/missing")
        assert resp.status_code == 404

    def test_backfill_status_error_500(self, client, svc):
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin.get_job_status",
                   side_effect=RuntimeError("boom")):
            resp = client.get("/api/outlook/memory/backfill/status/job1")
        assert resp.status_code == 500
