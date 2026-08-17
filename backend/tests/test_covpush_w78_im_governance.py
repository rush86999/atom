# -*- coding: utf-8 -*-
"""Coverage wave 78 — core/im_governance_service. Webhook signature
verification, rate limiting, governance checks and audit trail — all deps
mocked (governance cache, adapters); real in-memory SQLite for IMAuditLog.

Bug-driven TDD (wave 78):
- RED: log_to_audit_trail never persisted a row — it constructed IMAuditLog
  with kwargs the model doesn't have (payload_hash, metadata_json, sender_id,
  success, rate_limited, signature_valid, governance_check_passed,
  agent_maturity_level) and omitted required tenant_id/chat_id/status. Every
  call raised TypeError inside the fire-and-forget task, so the entire Stage-3
  compliance audit pipeline was dead. Fixed: model extended with the missing
  nullable columns, tenant_id/chat_id relaxed to nullable, and status derived
  from success/rate_limited.

Coverage:
- verify_and_rate_limit: success, missing sender_id → 400, rate limit exceeded
  → 429 with headers, unknown platform → 400, invalid signature → 403,
  adapter.verify_request exception → 403.
- check_permissions: blocked user → 403, STUDENT agent → 403, mature agent →
  allowed dict, no agent → generic allowed.
- log_to_audit_trail: row persisted (all fields + payload hash + maturity),
  db error swallowed, maturity metadata omitted when absent.
- _extract_sender_id: telegram message/callback/malformed, whatsapp
  entry/changes/value/messages/malformed, unknown platform, bad JSON.
- _check_rate_limit / get_rate_limit_status: window pruning, limits.
"""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.im_governance_service import IMGovernanceService
from core.models import IMAuditLog  # noqa: F401 (register model)


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


class _ImmediateTasks:
    """Patches asyncio.create_task to collect coroutines so tests can drain
    the fire-and-forget audit task deterministically."""

    def __init__(self):
        self.coros = []

    def __call__(self, coro):
        self.coros.append(coro)
        return MagicMock()

    async def drain(self):
        for coro in self.coros:
            await coro


def _drain(service_call, svc, *args, **kwargs):
    """Run the service call and await any audit task it spawned."""
    async def _run():
        tasks = _ImmediateTasks()
        with patch("core.im_governance_service.asyncio.create_task", tasks):
            await service_call(*args, **kwargs)
        await tasks.drain()

    asyncio.run(_run())


def _request() -> Request:
    return MagicMock(spec=Request)


def _cache_mock(blocked=None, agent=None):
    """GovernanceCache substitute: async lookups returning per-key rows.

    Mirrors GovernanceCache's real API: get_async(agent_id, action_type).
    IM block flags are stored as decisions under
    ("im_user:<platform>:<sender_id>", "blocked").
    """
    cache = MagicMock()

    async def _get(key, *args):
        return agent

    async def _get_async(key, action_type=""):
        if isinstance(key, str) and key.startswith("im_user:"):
            return blocked
        return agent

    cache.get = AsyncMock(side_effect=_get)
    cache.get_async = AsyncMock(side_effect=_get_async)
    return cache


class TestVerifyAndRateLimit:
    def test_success(self, db):
        svc = IMGovernanceService(db)
        svc.adapters["telegram"].verify_request = AsyncMock(return_value=True)
        svc._extract_sender_id = MagicMock(return_value="u-1")
        body = b'{"message": {"from": {"id": 42}}}'
        result = asyncio.run(svc.verify_and_rate_limit(_request(), body, "telegram"))
        assert result == {"verified": True, "platform": "telegram", "sender_id": "u-1"}

    def test_missing_sender_id_400(self, db):
        svc = IMGovernanceService(db)
        svc._extract_sender_id = MagicMock(return_value=None)
        with pytest.raises(Exception) as ei:
            asyncio.run(svc.verify_and_rate_limit(_request(), b"{}", "telegram"))
        assert ei.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid request format" in ei.value.detail

    def test_rate_limited_429(self, db):
        svc = IMGovernanceService(db)
        svc._extract_sender_id = MagicMock(return_value="u-1")
        svc._check_rate_limit = MagicMock(return_value=False)
        with pytest.raises(Exception) as ei:
            asyncio.run(svc.verify_and_rate_limit(_request(), b"{}", "telegram"))
        err = ei.value
        assert err.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert err.headers["Retry-After"] == str(svc.rate_limit_window)
        assert err.headers["X-RateLimit-Limit"] == str(svc.rate_limit_requests)

    def test_unknown_platform_400(self, db):
        svc = IMGovernanceService(db)
        svc._extract_sender_id = MagicMock(return_value="u-1")
        with pytest.raises(Exception) as ei:
            asyncio.run(svc.verify_and_rate_limit(_request(), b"{}", "matrix"))
        assert ei.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported platform" in ei.value.detail

    def test_invalid_signature_403(self, db):
        svc = IMGovernanceService(db)
        svc.adapters["telegram"].verify_request = AsyncMock(return_value=False)
        body = b'{"message": {"from": {"id": 42}}}'
        with pytest.raises(Exception) as ei:
            asyncio.run(svc.verify_and_rate_limit(_request(), body, "telegram"))
        assert ei.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Invalid webhook signature" in ei.value.detail

    def test_verify_exception_403(self, db):
        svc = IMGovernanceService(db)
        svc.adapters["telegram"].verify_request = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        body = b'{"message": {"from": {"id": 42}}}'
        with pytest.raises(Exception) as ei:
            asyncio.run(svc.verify_and_rate_limit(_request(), body, "telegram"))
        assert ei.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Webhook verification failed" in ei.value.detail


class TestCheckPermissions:
    def test_blocked_user_403(self, db):
        svc = IMGovernanceService(db)
        with patch("core.im_governance_service.get_governance_cache",
                   return_value=_cache_mock(blocked={"blocked": True})):
            with pytest.raises(Exception) as ei:
                asyncio.run(svc.check_permissions("u-1", "telegram"))
        assert ei.value.status_code == status.HTTP_403_FORBIDDEN
        assert "blocked" in ei.value.detail

    def test_blocked_dict_missing_flag_allows(self, db):
        svc = IMGovernanceService(db)
        with patch("core.im_governance_service.get_governance_cache",
                   return_value=_cache_mock(blocked={})):
            result = asyncio.run(svc.check_permissions("u-1", "telegram"))
        assert result["allowed"] is True

    def test_student_agent_403(self, db):
        svc = IMGovernanceService(db)
        with patch("core.im_governance_service.get_governance_cache",
                   return_value=_cache_mock(agent={"maturity_level": "STUDENT"})):
            with pytest.raises(Exception) as ei:
                asyncio.run(svc.check_permissions("u-1", "telegram", "agent-1"))
        assert ei.value.status_code == status.HTTP_403_FORBIDDEN
        assert "STUDENT agents" in ei.value.detail

    def test_mature_agent_allowed(self, db):
        svc = IMGovernanceService(db)
        with patch("core.im_governance_service.get_governance_cache",
                   return_value=_cache_mock(agent={"maturity_level": "SUPERVISED"})):
            result = asyncio.run(svc.check_permissions("u-1", "whatsapp", "agent-1"))
        assert result["allowed"] is True
        assert result["agent_id"] == "agent-1"
        assert result["maturity_level"] == "SUPERVISED"
        assert result["platform"] == "whatsapp"

    def test_no_agent_generic(self, db):
        svc = IMGovernanceService(db)
        with patch("core.im_governance_service.get_governance_cache",
                   return_value=_cache_mock()):
            result = asyncio.run(svc.check_permissions("u-1", "telegram"))
        assert result == {"allowed": True, "platform": "telegram", "sender_id": "u-1"}

    def test_agent_entry_without_maturity_falls_back_to_generic(self, db):
        svc = IMGovernanceService(db)
        with patch("core.im_governance_service.get_governance_cache",
                   return_value=_cache_mock(agent={})):
            result = asyncio.run(svc.check_permissions("u-1", "telegram", "agent-1"))
        assert result["allowed"] is True
        assert "agent_id" not in result


class TestLogToAuditTrail:
    def test_row_persisted_with_all_fields(self, db):
        """RED (wave 78): constructing IMAuditLog with payload_hash etc. raised
        TypeError — no row was ever written."""
        svc = IMGovernanceService(db)
        payload = {"content": "hello", "media_id": "m1"}
        _drain(svc.log_to_audit_trail, svc, "telegram", "u-1", payload, "webhook_received",
               success=True, rate_limited=False, signature_valid=True,
               governance_check_passed=True, agent_maturity_level="SUPERVISED")
        rows = db.query(IMAuditLog).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.platform == "telegram"
        assert row.sender_id == "u-1"
        assert row.action == "webhook_received"
        assert row.success is True
        assert row.rate_limited is False
        assert row.signature_valid is True
        assert row.governance_check_passed is True
        assert row.agent_maturity_level == "SUPERVISED"
        assert row.status == "success"
        assert row.payload_hash
        import hashlib
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        assert row.payload_hash == expected
        assert row.metadata_json["has_media"] is True
        assert row.metadata_json["agent_maturity"] == "SUPERVISED"
        assert row.timestamp is not None

    def test_error_and_failure_status(self, db):
        svc = IMGovernanceService(db)
        _drain(svc.log_to_audit_trail, svc, "whatsapp", "u-2", {"x": 1}, "command_run",
               success=False, error_message="timeout", rate_limited=True)
        row = db.query(IMAuditLog).first()
        assert row.status == "rate_limited"
        assert row.error_message == "timeout"

    def test_metadata_omits_maturity_when_absent(self, db):
        svc = IMGovernanceService(db)
        _drain(svc.log_to_audit_trail, svc, "telegram", "u-3", {"t": "x"}, "webhook_received",
               success=True)
        row = db.query(IMAuditLog).first()
        assert "agent_maturity" not in row.metadata_json
        assert row.agent_maturity_level is None

    def test_db_error_swallowed(self, db):
        svc = IMGovernanceService(db)
        svc.db.add = MagicMock(side_effect=RuntimeError("db down"))
        # must not raise
        _drain(svc.log_to_audit_trail, svc, "telegram", "u-1", {}, "webhook_received",
               success=True)


class TestExtractSenderId:
    def test_telegram_message(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"message": {"from": {"id": 4242}}}).encode()
        assert svc._extract_sender_id(_request(), body, "telegram") == "4242"

    def test_telegram_callback_query(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"callback_query": {"from": {"id": 99}}}).encode()
        assert svc._extract_sender_id(_request(), body, "telegram") == "99"

    def test_telegram_message_not_dict(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"message": [1, 2], "callback_query": [1]}).encode()
        assert svc._extract_sender_id(_request(), body, "telegram") is None

    def test_telegram_from_not_dict(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"message": {"from": "nope"}}).encode()
        assert svc._extract_sender_id(_request(), body, "telegram") is None

    def test_telegram_callback_from_not_dict(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"callback_query": {"from": 5}}).encode()
        assert svc._extract_sender_id(_request(), body, "telegram") is None

    def test_telegram_empty_message_falls_to_callback(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"message": {}, "callback_query": {"from": {"id": 7}}}).encode()
        assert svc._extract_sender_id(_request(), body, "telegram") == "7"

    def test_whatsapp_message(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({
            "entry": [{"changes": [{"value": {"messages": [{"from": "+15551234"}]}}]}]
        }).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") == "+15551234"

    def test_whatsapp_empty_entry(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": []}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_entry_not_list(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": {}}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_entry_not_dict(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": [1]}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_empty_changes(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": [{"changes": []}]}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_changes_not_dict(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": [{"changes": [1]}]}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_value_not_dict(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": [{"changes": [{"value": 5}]}]}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_empty_messages(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": []}}]}]}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_messages_not_list(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": {}}}]}]}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_whatsapp_message_not_dict(self, db):
        svc = IMGovernanceService(db)
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": [1]}}]}]}).encode()
        assert svc._extract_sender_id(_request(), body, "whatsapp") is None

    def test_unknown_platform(self, db):
        svc = IMGovernanceService(db)
        assert svc._extract_sender_id(_request(), b"{}", "signal") is None

    def test_bad_json(self, db):
        svc = IMGovernanceService(db)
        assert svc._extract_sender_id(_request(), b"{not json", "telegram") is None


class TestRateLimiting:
    def test_sliding_window_allows_and_blocks(self, db):
        svc = IMGovernanceService(db, )
        svc.rate_limit_requests = 3
        assert svc._check_rate_limit("telegram:u1") is True
        assert svc._check_rate_limit("telegram:u1") is True
        assert svc._check_rate_limit("telegram:u1") is True
        assert svc._check_rate_limit("telegram:u1") is False
        assert svc._check_rate_limit("telegram:u2") is True  # separate key

    def test_window_prunes_old_entries(self, db):
        svc = IMGovernanceService(db)
        svc.rate_limit_requests = 1
        svc.rate_limit_window = 60
        with patch("core.im_governance_service.datetime") as dt_mock:
            dt_mock.now.return_value.timestamp.return_value = 1000.0
            assert svc._check_rate_limit("k") is True
            dt_mock.now.return_value.timestamp.return_value = 1100.0
            assert svc._check_rate_limit("k") is True  # 100s later: window reset
        assert len(svc._rate_limit_store["k"]) == 1

    def test_get_rate_limit_status(self, db):
        svc = IMGovernanceService(db)
        svc.rate_limit_requests = 10
        with patch("core.im_governance_service.datetime") as dt_mock:
            dt_mock.now.return_value.timestamp.return_value = 1000.0
            svc._check_rate_limit("telegram:u1")
            status_dict = svc.get_rate_limit_status("telegram", "u1")
        assert status_dict["limit"] == 10
        assert status_dict["remaining"] == 9
        assert status_dict["window"] == svc.rate_limit_window
        assert status_dict["reset_at"] == 1000 + svc.rate_limit_window

    def test_get_rate_limit_status_unknown_key(self, db):
        svc = IMGovernanceService(db)
        status_dict = svc.get_rate_limit_status("telegram", "nobody")
        assert status_dict["remaining"] == svc.rate_limit_requests
        assert status_dict["reset_at"] is not None
