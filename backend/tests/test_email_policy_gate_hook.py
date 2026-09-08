"""Hook tests: email policy gate wired into the universal send boundary.

Verifies the gate runs BEFORE any provider branch in
``UniversalIntegrationService._execute_communication`` and that a gate
failure fails OPEN (never blocks a real send).
"""
import sys

import pytest

from integrations.universal_integration_service import UniversalIntegrationService


class _FakeCommService:
    access_token = "tok"

    def send_message(self, **kwargs):
        return {"id": "sent-1"}

    def reply_to_message(self, thread_id, body, token):
        return {"id": "replied-1"}


class _FakeRegistry:
    def __init__(self, service_instance=None):
        self._inst = service_instance

    async def get_service_instance(self, service, tenant_id):
        return self._inst


def _ctx(registry):
    return {"registry": registry, "tenant_id": "tenant-x"}


@pytest.mark.asyncio
async def test_reply_without_thread_blocked_before_provider_call():
    svc = UniversalIntegrationService()
    reg = _FakeRegistry(service_instance=None)  # even a dead service must not be reached
    result = await svc._execute_communication(
        "gmail", "send_message",
        {"to": "a@b.com", "subject": "Re: Quote for SR48P", "body": "Hi"},
        _ctx(reg),
    )
    assert result["status"] == "blocked"
    assert result["policy"] == "email_send_policy"
    assert result["violations"][0]["code"] == "reply_without_thread"


@pytest.mark.asyncio
async def test_unverified_price_blocked_for_outlook():
    svc = UniversalIntegrationService()
    reg = _FakeRegistry(service_instance=None)
    result = await svc._execute_communication(
        "outlook", "send_message",
        {"to": "a@b.com", "subject": "Quote", "body": "It is $1,250."},
        _ctx(reg),
    )
    assert result["status"] == "blocked"
    assert result["violations"][0]["code"] == "unverified_price"


@pytest.mark.asyncio
async def test_zoho_mail_also_gated():
    svc = UniversalIntegrationService()
    reg = _FakeRegistry(service_instance=None)
    result = await svc._execute_communication(
        "zoho_mail", "send_message",
        {"to": "a@b.com", "subject": "Re: hi", "body": "yo"},
        _ctx(reg),
    )
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_clean_new_email_passes_through_to_provider():
    svc = UniversalIntegrationService()
    reg = _FakeRegistry(service_instance=_FakeCommService())
    result = await svc._execute_communication(
        "gmail", "send_message",
        {"to": "new@b.com", "subject": "Introducing Brennan Machinery", "body": "Hello"},
        _ctx(reg),
    )
    assert result["status"] == "success"
    assert result["data"]["id"] == "sent-1"


@pytest.mark.asyncio
async def test_threaded_reply_with_verified_price_passes():
    svc = UniversalIntegrationService()
    reg = _FakeRegistry(service_instance=_FakeCommService())
    result = await svc._execute_communication(
        "gmail", "send_message",
        {
            "subject": "Re: Quote for SR48P",
            "thread_id": "t-123",
            "body": "Confirmed: $1,250.",
            "price_verified": True,
            "price_source": "price list",
        },
        _ctx(reg),
    )
    assert result["status"] == "success"
    assert result["data"]["id"] == "replied-1"


@pytest.mark.asyncio
async def test_gate_import_failure_fails_open(monkeypatch):
    """A broken policy module must never block a real send."""
    monkeypatch.setitem(sys.modules, "core.email_policy_gate", None)
    svc = UniversalIntegrationService()
    reg = _FakeRegistry(service_instance=_FakeCommService())
    result = await svc._execute_communication(
        "gmail", "send_message",
        {"to": "a@b.com", "subject": "Re: quote", "body": "It is $1,250."},
        _ctx(reg),
    )
    assert result["status"] == "success"
