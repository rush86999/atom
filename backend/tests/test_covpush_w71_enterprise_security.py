"""Coverage wave 71 — core/enterprise_security.py (99% → 100%).

Closes the remaining holes:
- REAL BUG (TDD red→green): the entire router (audit events, security
  alerts, compliance status/scan, stats) had ZERO auth — any anonymous
  caller could read the full audit trail (user emails, IPs, actions).
  Sibling router core/enterprise_user_management.py carries
  dependencies=[Depends(get_current_user)] for the same class of data;
  this one now does too. RED: anonymous GET /api/enterprise/security/audit
  must 401 instead of 200.
- audit-event cap trim (>100000 events, line ~186)
- security_middleware: rate-limit-exceeded 429 + audit log, pass-through
- service branches: suspicious-IP alert threshold, get_audit_events with
  every filter, get_security_alerts with every filter, expired-lock cleanup
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import core.enterprise_security as es_mod
from core import enterprise_security as es  # noqa: F401  (module alias check)
from core.enterprise_security import (
    AuditEvent,
    ComplianceCheck,
    EnterpriseSecurity,
    EventType,
    SecurityAlert,
    SecurityLevel,
    ThreatLevel,
    enterprise_security,
    router,
    security_middleware,
)


def _event(**overrides):
    defaults = {
        "event_type": EventType.USER_LOGIN,
        "security_level": SecurityLevel.MEDIUM,
        "action": "login",
        "description": "user login",
        "success": True,
    }
    defaults.update(overrides)
    return AuditEvent(**defaults)


class TestAuditEventCapTrim:
    def test_audit_events_trimmed_at_cap(self):
        sec = EnterpriseSecurity()
        for i in range(100001):
            sec.log_audit_event(_event(action=f"a{i}"))
        assert len(sec.audit_events) == 100000

    def test_audit_events_not_trimmed_below_cap(self):
        sec = EnterpriseSecurity()
        for i in range(50):
            sec.log_audit_event(_event(action=f"a{i}"))
        assert len(sec.audit_events) == 50


class TestAuthGate:
    """REAL BUG: audit surface was anonymous. Now requires auth."""

    def _app(self):
        app = FastAPI()
        app.include_router(router)
        return app

    def _anon_client(self):
        with patch.object(es_mod, "enterprise_security", EnterpriseSecurity()):
            return TestClient(self._app())

    def test_anonymous_audit_events_rejected(self):
        # RED before fix: returned 200 with full audit trail.
        resp = self._anon_client().get("/api/enterprise/security/audit")
        assert resp.status_code == 401

    def test_anonymous_alerts_rejected(self):
        resp = self._anon_client().get("/api/enterprise/security/alerts")
        assert resp.status_code == 401

    def test_anonymous_compliance_rejected(self):
        resp = self._anon_client().get("/api/enterprise/security/compliance")
        assert resp.status_code == 401

    def test_anonymous_compliance_scan_rejected(self):
        resp = self._anon_client().post("/api/enterprise/security/compliance/scan")
        assert resp.status_code == 401

    def test_anonymous_stats_rejected(self):
        resp = self._anon_client().get("/api/enterprise/security/stats")
        assert resp.status_code == 401

    def test_authenticated_audit_events_allowed(self):
        sec = EnterpriseSecurity()
        sec.log_audit_event(_event(user_email="a@b.com"))
        app = self._app()
        app.dependency_overrides[es_mod.get_current_user] = lambda: Mock(id="u1")
        with patch.object(es_mod, "enterprise_security", sec):
            client = TestClient(app)
            resp = client.get("/api/enterprise/security/audit")
            assert resp.status_code == 200
            assert resp.json()["total_count"] == 1

    def test_authenticated_scan_allowed(self):
        sec = EnterpriseSecurity()
        app = self._app()
        app.dependency_overrides[es_mod.get_current_user] = lambda: Mock(id="u1")
        with patch.object(es_mod, "enterprise_security", sec):
            client = TestClient(app)
            resp = client.post("/api/enterprise/security/compliance/scan")
            assert resp.status_code == 200
            assert resp.json()["checks_performed"] == 15


class TestSecurityMiddleware:
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_raises_429(self):
        request = Mock()
        request.client = Mock(host="203.0.113.9")
        with patch.object(enterprise_security, "check_rate_limit", return_value=False), \
             patch.object(enterprise_security, "log_audit_event") as log_mock:
            with pytest.raises(HTTPException) as exc:
                await security_middleware(request, AsyncMock())
            assert exc.value.status_code == 429
            log_mock.assert_called_once()
            logged = log_mock.call_args[0][0]
            assert logged.event_type == EventType.API_ACCESS
            assert logged.success is False

    @pytest.mark.asyncio
    async def test_passes_request_through_when_allowed(self):
        request = Mock()
        request.client = Mock(host="203.0.113.9")
        response = Mock(status_code=200)
        call_next = AsyncMock(return_value=response)
        with patch.object(enterprise_security, "check_rate_limit", return_value=True):
            result = await security_middleware(request, call_next)
        assert result is response
        call_next.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_missing_client_uses_unknown_ip(self):
        request = Mock()
        request.client = None
        call_next = AsyncMock(return_value=Mock(status_code=200))
        with patch.object(enterprise_security, "check_rate_limit", return_value=True) as rl:
            await security_middleware(request, call_next)
        identifier, ts = rl.call_args[0]
        assert identifier == "unknown"
        assert isinstance(ts, datetime)


class TestServiceBranches:
    def test_suspicious_ip_alert_threshold(self):
        sec = EnterpriseSecurity()
        sec.suspicious_threshold = 2
        sec.log_audit_event(_event(success=False, ip_address="198.51.100.7"))
        sec.log_audit_event(_event(success=False, ip_address="198.51.100.7"))
        alerts = [a for a in sec.security_alerts if a.alert_type == "suspicious_ip_activity"]
        assert len(alerts) == 1
        assert alerts[0].severity == SecurityLevel.MEDIUM

    def test_get_audit_events_all_filters(self):
        sec = EnterpriseSecurity()
        sec.log_audit_event(_event(user_id="u1", event_type=EventType.USER_LOGIN,
                                   security_level=SecurityLevel.LOW))
        sec.log_audit_event(_event(user_id="u2", event_type=EventType.USER_LOGOUT,
                                   security_level=SecurityLevel.HIGH))
        now = datetime.now()
        results = sec.get_audit_events(
            start_time=now - timedelta(minutes=1),
            end_time=now + timedelta(minutes=1),
            event_type=EventType.USER_LOGIN,
            user_id="u1",
            security_level=SecurityLevel.LOW,
            limit=1,
        )
        assert len(results) == 1
        assert results[0].user_id == "u1"

    def test_get_security_alerts_all_filters(self):
        sec = EnterpriseSecurity()
        sec.create_security_alert("x", SecurityLevel.HIGH, "d1")
        sec.create_security_alert("y", SecurityLevel.LOW, "d2")
        results = sec.get_security_alerts(
            severity=SecurityLevel.HIGH,
            status="open",
            start_time=datetime.now() - timedelta(minutes=1),
            limit=5,
        )
        assert len(results) == 1
        assert results[0].alert_type == "x"

    def test_brute_force_lock_created_and_checked(self):
        sec = EnterpriseSecurity()
        sec.max_login_attempts = 2
        sec.login_lockout_duration = timedelta(minutes=30)
        for _ in range(2):
            sec.log_audit_event(_event(event_type=EventType.USER_LOGIN, success=False,
                                       user_email="victim@example.com",
                                       ip_address="203.0.113.55"))
        assert sec.is_account_locked("victim@example.com") is True
        assert sec.locked_accounts["victim@example.com"] is not None

    def test_expired_lock_cleaned(self):
        sec = EnterpriseSecurity()
        sec.locked_accounts["old@example.com"] = datetime.now() - timedelta(hours=1)
        sec.failed_login_attempts["old@example.com"] = [datetime.now() - timedelta(hours=2)]
        assert sec.is_account_locked("old@example.com") is False
        assert "old@example.com" not in sec.locked_accounts
        assert "old@example.com" not in sec.failed_login_attempts

    def test_run_compliance_scan_logs_event(self):
        sec = EnterpriseSecurity()
        result = sec.run_compliance_scan()
        assert result["checks_performed"] == 15
        assert result["success_rate"] == 80.0
        assert any(e.event_type == EventType.COMPLIANCE_CHECK for e in sec.audit_events)

    def test_compliance_status_standard_filter(self):
        sec = EnterpriseSecurity()
        status = sec.get_compliance_status("SOC2")
        assert status["total_checks"] == 3
        assert status["compliant_checks"] == 3

    def test_compliance_status_empty(self):
        sec = EnterpriseSecurity()
        sec.compliance_checks = []
        status = sec.get_compliance_status()
        assert status["total_checks"] == 0
        assert status["compliance_rate"] == 0


class TestRoutePayloads:
    def test_security_stats_shape(self):
        sec = EnterpriseSecurity()
        sec.log_audit_event(_event(event_type=EventType.API_ACCESS, user_id="u1"))
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[es_mod.get_current_user] = lambda: Mock(id="u1")
        with patch.object(es_mod, "enterprise_security", sec):
            client = TestClient(app)
            resp = client.get("/api/enterprise/security/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_audit_events"] == 1
            assert "api_access" in body["event_type_counts"]

    def test_alerts_route_open_count(self):
        sec = EnterpriseSecurity()
        sec.create_security_alert("x", SecurityLevel.HIGH, "d")
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[es_mod.get_current_user] = lambda: Mock(id="u1")
        with patch.object(es_mod, "enterprise_security", sec):
            client = TestClient(app)
            resp = client.get("/api/enterprise/security/alerts?status=open")
            assert resp.status_code == 200
            assert resp.json()["open_alerts"] == 1
