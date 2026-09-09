"""Tests: real Communication Hub draft backend (draft_response / approve_draft)
— replaces the former phantom module. Covers the hub service itself, the
universal-service create_draft branches, and Outlook's draft-reply method.
"""
import sys

import pytest

from core.collaboration_hub_service import (
    CollaborationHubService,
    get_collaboration_hub_service,
)


# --- hub service (unit, universal service faked) ----------------------------


class _FakeUniversal:
    """Stand-in for UniversalIntegrationService; scripted per provider."""

    def __init__(self, results):
        # results: {platform: {"status": ..., "data": ...} or callable}
        self._results = results
        self.calls = []

    async def execute(self, service, action, params, context=None):
        self.calls.append((service, action, params))
        res = self._results.get(service)
        if callable(res):
            return res(service, action, params)
        return dict(res or {"status": "error", "message": "n/a"})


@pytest.fixture
def fake_universal(monkeypatch):
    def _install(results):
        fake = _FakeUniversal(results)
        monkeypatch.setattr(
            "integrations.universal_integration_service.UniversalIntegrationService",
            lambda workspace_id="default": fake,
        )
        return fake
    return _install


async def _draft(hub, **kw):
    return await hub.save_draft_response(
        kw.get("message_id", "m-1"), kw.get("content", "Hi there"),
        kw.get("confidence", 0.8), platform=kw.get("platform"),
        user_id=kw.get("user_id"), workspace_id=kw.get("workspace_id", "default"),
    )


@pytest.mark.asyncio
async def test_draft_requires_message_id():
    hub = CollaborationHubService()
    r = await hub.save_draft_response(None, "hi")
    assert r["status"] == "error"


@pytest.mark.asyncio
async def test_draft_requires_content():
    hub = CollaborationHubService()
    r = await hub.save_draft_response("m-1", "   ")
    assert r["status"] == "error"


@pytest.mark.asyncio
async def test_draft_outlook_success(fake_universal):
    fake = fake_universal({
        "outlook": {"status": "success", "data": {"draft_id": "d-1"}},
    })
    hub = CollaborationHubService()
    r = await _draft(hub, platform="outlook")
    assert r["status"] == "success"
    assert r["draft_id"] == "d-1"
    assert fake.calls[0][1] == "create_draft"


@pytest.mark.asyncio
async def test_draft_gmail_success(fake_universal):
    fake = fake_universal({
        "gmail": {"status": "success", "data": {"id": "draft-g"}},
    })
    hub = CollaborationHubService()
    r = await _draft(hub, platform="gmail")
    assert r["status"] == "success"
    assert r["draft_id"] == "draft-g"


@pytest.mark.asyncio
async def test_draft_autodetect_tries_providers_in_order(fake_universal):
    def first_success(service, action, params):
        if service == "outlook":
            return {"status": "error", "message": "no outlook token"}
        return {"status": "success", "data": {"id": "g-ok"}}

    fake = fake_universal({"outlook": first_success, "gmail": first_success})
    hub = CollaborationHubService()
    r = await _draft(hub)  # no platform
    assert r["status"] == "success"
    assert r["platform"] == "gmail"
    assert [c[0] for c in fake.calls] == ["outlook", "gmail"]


@pytest.mark.asyncio
async def test_draft_all_providers_fail_reports(fake_universal):
    fake_universal({"outlook": {"status": "error", "message": "boom"}})
    hub = CollaborationHubService()
    r = await _draft(hub, platform="outlook")
    assert r["status"] == "error"
    assert "boom" in r["error"]


@pytest.mark.asyncio
async def test_approve_draft_sends_in_thread(fake_universal):
    fake = fake_universal({"gmail": {"status": "success", "data": {"id": "s1"}}})
    hub = CollaborationHubService()
    r = await hub.approve_draft("m-1", "final text", platform="gmail")
    assert r["status"] == "success"
    svc, action, params = fake.calls[0]
    assert action == "send_message"
    assert params["reply_to_message_id"] == "m-1"


@pytest.mark.asyncio
async def test_approve_requires_edited_content():
    hub = CollaborationHubService()
    r = await hub.approve_draft("m-1")
    assert r["status"] == "error"


def test_update_ai_analysis_ok():
    hub = CollaborationHubService()
    r = hub.update_ai_analysis("m-1", {"tone": "professional"})
    assert r["status"] == "ok"


def test_factory_returns_singleton():
    assert get_collaboration_hub_service() is get_collaboration_hub_service()


def test_module_now_imports():
    # The phantom-import era is over: the real module must import cleanly.
    import core.collaboration_hub_service  # noqa: F401
    assert core.collaboration_hub_service.CollaborationHubService


# --- universal create_draft branches ---------------------------------------


class _GmailComm:
    access_token = "tok"

    def get_message(self, message_id, token=None):
        return {"id": message_id, "threadId": "th-1", "subject": "Quote",
                "sender": "a@b.com"}

    def draft_message(self, to, subject, body, thread_id=None, token=None):
        return {"id": f"draft-{thread_id}"}


class _OutlookComm:
    access_token = "tok"

    async def draft_reply_to_email(self, user_id, message_id, comment,
                                   subject=None, token=None):
        return "draft-outlook-1"

    async def get_latest_conversation_message_id(self, user_id, conversation_id,
                                                 token=None):
        return "m-9"

    async def create_draft_email(self, user_id, to_recipients, subject, body,
                                 token=None):
        return {"id": "draft-new-1"}


class _Registry:
    def __init__(self, inst):
        self._inst = inst

    async def get_service_instance(self, service, tenant_id):
        return self._inst


@pytest.mark.asyncio
async def test_universal_gmail_create_draft_threaded():
    from integrations.universal_integration_service import UniversalIntegrationService

    svc = UniversalIntegrationService()
    comm = _GmailComm()
    result = await svc._execute_communication(
        "gmail", "create_draft",
        {"message_id": "m-1", "body": "Draft text"},
        {"registry": _Registry(comm), "tenant_id": "t"},
    )
    assert result["status"] == "success"
    assert result["data"]["id"] == "draft-th-1"


@pytest.mark.asyncio
async def test_universal_outlook_create_draft_threaded():
    from integrations.universal_integration_service import UniversalIntegrationService

    svc = UniversalIntegrationService()
    comm = _OutlookComm()
    result = await svc._execute_communication(
        "outlook", "create_draft",
        {"message_id": "m-1", "body": "Draft text"},
        {"registry": _Registry(comm), "tenant_id": "t", "user_id": "u1"},
    )
    assert result["status"] == "success"
    assert result["data"]["draft_id"] == "draft-outlook-1"


@pytest.mark.asyncio
async def test_universal_outlook_create_draft_new_email():
    from integrations.universal_integration_service import UniversalIntegrationService

    svc = UniversalIntegrationService()
    comm = _OutlookComm()
    result = await svc._execute_communication(
        "outlook", "create_draft",
        {"to": ["new@x.com"], "subject": "Intro", "body": "Hello"},
        {"registry": _Registry(comm), "tenant_id": "t", "user_id": "u1"},
    )
    assert result["status"] == "success"
    assert result["data"]["id"] == "draft-new-1"


# --- outlook draft_reply_to_email (never sends) -----------------------------


def test_outlook_draft_reply_creates_draft_without_send():
    import asyncio

    from integrations.outlook_service import OutlookService

    svc = OutlookService("default", {})
    calls = []

    async def fake_graph(user_id, url, method="GET", data=None, access_token=None):
        calls.append((url, method))
        if url.endswith("/reply") or url.endswith("/replyAll"):
            return {"id": "draft-42"}
        if url.endswith("/draft-42"):
            return {"id": "draft-42", "body": {}}
        return None

    svc._make_graph_request = fake_graph
    draft_id = asyncio.run(svc.draft_reply_to_email("u1", "m-1", "<b>Hi</b>"))
    assert draft_id == "draft-42"
    methods = [m for _, m in calls]
    assert "POST" in methods and "PATCH" in methods
    assert not any("/send" in u for u, _ in calls), "draft must never call /send"
