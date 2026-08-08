"""Coverage-push + bug-hunt tests for the enterprise integration services.

Targets:
- integrations.atom_workflow_automation_service
- integrations.atom_enterprise_security_service
- integrations.atom_enterprise_unified_service

External calls (AI, DB, platform integrations) are mocked; circuit breaker /
rate limiter paths are exercised with patches.
"""
import asyncio
import importlib
import json
from datetime import datetime, date, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _mod(name: str):
    return importlib.import_module(f"integrations.{name}")


SECURITY = "integrations.atom_enterprise_security_service"
UNIFIED = "integrations.atom_enterprise_unified_service"
WORKFLOW = "integrations.atom_workflow_automation_service"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    for name in (SECURITY, UNIFIED, WORKFLOW):
        mod = importlib.import_module(name)
        mod.rate_limiter._tracking.clear()
    yield
    for name in (SECURITY, UNIFIED, WORKFLOW):
        mod = importlib.import_module(name)
        mod.rate_limiter._tracking.clear()


class TestSecurityPolicyLifecycle:
    def _policy_data(self, **overrides):
        data = {
            "name": "Policy X",
            "description": "desc",
            "security_level": "advanced",
            "compliance_standards": ["soc2", "GDPR"],
            "rules": [{"name": "r1", "action": "block"}],
            "enforcement_actions": [{"type": "block"}],
            "exceptions": ["legacy-user"],
        }
        data.update(overrides)
        return data

    async def test_create_policy_stores_in_db(self):
        mod = _mod("atom_enterprise_security_service")
        db = MagicMock()
        db.store_security_policy = AsyncMock()
        db.store_security_audit = AsyncMock()
        service = mod.AtomEnterpriseSecurityService(config={"database": db})
        result = await service.create_security_policy(self._policy_data(), "user-9")
        assert result["ok"] is True
        db.store_security_policy.assert_awaited_once()
        assert result["policy_id"].startswith("policy_")

    async def test_create_policy_invalid_compliance_standard(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        result = await service.create_security_policy(
            self._policy_data(compliance_standards=["not_a_standard"]), "user-1"
        )
        assert result["ok"] is False
        assert "Invalid compliance standard" in result["error"]

    async def test_create_policy_validation_failure(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service._validate_security_policy = AsyncMock(
            return_value={"valid": False, "errors": ["bad rule"]}
        )
        result = await service.create_security_policy(self._policy_data(), "user-1")
        assert result["ok"] is False
        assert "Policy validation failed" in result["error"]

    async def test_create_policy_exception_contained(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        result = await service.create_security_policy({"no": "name"}, "user-1")
        assert result["ok"] is False

    async def test_get_security_metrics_and_info(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        metrics = await service.get_security_metrics()
        assert metrics["active_policies"] == 0
        info = await service.get_service_info()
        assert info["status"] == "ACTIVE"

    async def test_close_with_http_session(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service.http_session = AsyncMock()
        await service.close()
        service.http_session.close.assert_awaited_once()


class TestSecurityCircuitBreakerAndRateLimit:
    async def test_circuit_breaker_open_raises_503(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        with patch.object(
            mod.circuit_breaker, "is_enabled", AsyncMock(return_value=False)
        ):
            for method, args in [
                ("encrypt_data", ("secret",)),
                ("decrypt_data", ("abc",)),
            ]:
                with pytest.raises(HTTPException) as exc_info:
                    await getattr(service, method)(*args)
                assert exc_info.value.status_code == 503

    def _policy_data(self):
        return {
            "name": "P",
            "description": "d",
            "security_level": "advanced",
            "compliance_standards": ["soc2"],
            "rules": [],
            "enforcement_actions": [],
        }

    async def test_circuit_breaker_swallowed_into_error_results(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        with patch.object(
            mod.circuit_breaker, "is_enabled", AsyncMock(return_value=False)
        ):
            assert (await service.create_security_policy(self._policy_data(), "u"))["ok"] is False
            assert await service.detect_threat({"event_type": "login"}) is None
            assert await service.audit_event({"event_type": "login"}) is None
            assert await service.check_compliance(mod.ComplianceStandard.GDPR) is None
            assert (await service.validate_password("pw"))["valid"] is False
            assert "error" in await service.analyze_user_behavior("u1")
            with pytest.raises(HTTPException):
                await service.get_security_metrics()
            with pytest.raises(HTTPException):
                await service.close()

    async def test_rate_limited_raises_429(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        with patch.object(
            mod.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.encrypt_data("secret")
            assert exc_info.value.status_code == 429
            assert await service.detect_threat({"event_type": "login"}) is None
            assert (await service.create_security_policy(self._policy_data(), "u"))["ok"] is False

    async def test_private_detection_circuit_breaker(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        with patch.object(
            mod.circuit_breaker, "is_enabled", AsyncMock(return_value=False)
        ):
            with pytest.raises(HTTPException):
                await service._pattern_based_detection({"content": "x"})
        with patch.object(
            mod.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))
        ):
            with pytest.raises(HTTPException):
                await service._pattern_based_detection({"content": "x"})


class TestSecurityThreatDetection:
    async def test_pattern_detection_sql_injection(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        threats = await service._pattern_based_detection(
            {"content": "SELECT * FROM users; DROP TABLE x"}
        )
        assert any(t["type"] == "sql_injection" for t in threats)

    async def test_pattern_detection_xss_and_traversal(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        threats = await service._pattern_based_detection(
            {"content": "<script>alert(1)</script>"}
        )
        assert any(t["type"] == "xss" for t in threats)
        threats = await service._pattern_based_detection(
            {"url": "https://x/../../etc/passwd"}
        )
        assert any(t["type"] == "auth_bypass" for t in threats)

    async def test_pattern_detection_no_match(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        threats = await service._pattern_based_detection({"content": "hello world"})
        assert threats == []

    async def test_matches_pattern_direct(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        info = {"patterns": [r"DROP TABLE"]}
        assert service._matches_pattern({"content": "DROP TABLE users"}, info) is True
        assert service._matches_pattern({"headers": "no match"}, info) is False
        assert service._matches_pattern({}, info) is False

    async def test_behavioral_anomaly_no_user(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        assert await service._behavioral_anomaly_detection({"event_type": "x"}) == []

    async def test_behavioral_anomaly_with_user(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service._detect_anomalies = MagicMock(
            return_value=[
                {
                    "severity": "high",
                    "confidence": 0.8,
                    "description": "odd login",
                    "indicators": ["ip"],
                }
            ]
        )
        threats = await service._behavioral_anomaly_detection({"user_id": "u1"})
        assert threats[0]["type"] == "anomalous_behavior"

    async def test_ai_threat_detection_high_confidence(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, confidence=0.95, output_data="x")
        )
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        with patch(f"{SECURITY}.AIRequest", create=True, new=MagicMock()), patch(f"{SECURITY}.AITaskType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIModelType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIServiceType", create=True, new=MagicMock()):
            threats = await service._ai_threat_detection({"event_type": "login"})
        assert threats == []
        ai.process_ai_request.assert_awaited_once()

    async def test_ai_threat_detection_low_confidence(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, confidence=0.5, output_data="x")
        )
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        with patch(f"{SECURITY}.AIRequest", create=True, new=MagicMock()), patch(f"{SECURITY}.AITaskType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIModelType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIServiceType", create=True, new=MagicMock()):
            threats = await service._ai_threat_detection({"event_type": "login"})
        assert threats == []

    async def test_ai_threat_detection_not_ok(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False))
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        with patch(f"{SECURITY}.AIRequest", create=True, new=MagicMock()), patch(f"{SECURITY}.AITaskType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIModelType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIServiceType", create=True, new=MagicMock()):
            assert await service._ai_threat_detection({}) == []

    async def test_ai_threat_detection_exception(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("ai down"))
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        with patch(f"{SECURITY}.AIRequest", create=True, new=MagicMock()), patch(f"{SECURITY}.AITaskType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIModelType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIServiceType", create=True, new=MagicMock()):
            assert await service._ai_threat_detection({}) == []

    async def test_detect_threat_no_ai_service(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService(config={"ai_threat_detection": True})
        service._pattern_based_detection = AsyncMock(
            return_value=[
                {
                    "type": "xss",
                    "severity": "medium",
                    "confidence": 0.8,
                    "description": "xss",
                    "indicators": [],
                }
            ]
        )
        service._behavioral_anomaly_detection = AsyncMock(return_value=[])
        result = await service.detect_threat({"event_type": "login"})
        assert result is not None
        assert result.threat_type == mod.ThreatType.XSS
        assert service.security_metrics["total_threats_detected"] == 1

    async def test_detect_threat_real_mitigation_path(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service.active_sessions["sess-1"] = {"user": "u1"}
        service.user_security_contexts["u-insider"] = {}
        threats = [
            {
                "type": "sql_injection",
                "severity": "high",
                "confidence": 0.9,
                "description": "blocked",
                "indicators": [],
            },
            {
                "type": "compromised_account",
                "severity": "critical",
                "confidence": 0.9,
                "description": "session",
                "indicators": [],
            },
            {
                "type": "insider_threat",
                "severity": "critical",
                "confidence": 0.9,
                "description": "insider",
                "indicators": [],
            },
        ]
        service._pattern_based_detection = AsyncMock(return_value=threats)
        service._behavioral_anomaly_detection = AsyncMock(return_value=[])
        service._ai_threat_detection = AsyncMock(return_value=[])
        result = await service.detect_threat(
            {"event_type": "login", "source_ip": "10.0.0.5", "session_id": "sess-1", "user_id": "u-insider"}
        )
        assert result is not None
        assert result.mitigated is True
        assert "10.0.0.5" in service.blocked_ips
        assert "sess-1" not in service.active_sessions
        assert service.user_security_contexts["u-insider"]["locked"] is True
        assert service.security_metrics["threats_mitigated"] == 3

    async def test_detect_threat_exception_returns_none(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service._pattern_based_detection = AsyncMock(side_effect=RuntimeError("boom"))
        assert await service.detect_threat({"event_type": "login"}) is None

    async def test_mitigate_threat_exception_contained(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service._block_ip = AsyncMock(side_effect=RuntimeError("fail"))
        threat = mod.ThreatDetection(
            detection_id="t1",
            threat_type=mod.ThreatType.SQL_INJECTION,
            severity="high",
            confidence=0.9,
            source_ip="1.2.3.4",
            user_id=None,
            session_id=None,
            timestamp=datetime.now(timezone.utc),
            description="d",
            indicators=[],
        )
        await service._mitigate_threat(threat)
        assert threat.mitigated is False

    async def test_block_ip_and_terminate_and_lock(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service.active_sessions["s1"] = {}
        service.user_security_contexts["u1"] = {}
        await service._block_ip("9.9.9.9", 60)
        assert "9.9.9.9" in service.blocked_ips
        await service._terminate_session("s1")
        assert "s1" not in service.active_sessions
        await service._terminate_session("missing")
        await service._lock_user_account("u1")
        assert service.user_security_contexts["u1"]["locked"] is True
        await service._lock_user_account("u-missing")

    async def test_quarantine_resource(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        await service._quarantine_resource("res-1")
        assert service.quarantined_resources["res-1"] is not None

    async def test_parse_ai_threat_results_stub(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        assert service._parse_ai_threat_results("{}") == []


class TestSecurityCompliance:
    async def test_check_compliance_with_findings(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        findings = [
            {"severity": "critical"},
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "low"},
            {"severity": "unknown"},
        ]
        service._get_compliance_data = AsyncMock(return_value={})
        service._ai_compliance_analysis = AsyncMock(
            return_value={"findings": findings, "recommendations": ["r"], "score": 0.5}
        )
        report = await service.check_compliance(mod.ComplianceStandard.SOC2, "weekly")
        assert report.overall_score == pytest.approx(100 - 20 - 15 - 10 - 5)
        assert report.period == "weekly"

    async def test_check_compliance_ai_path(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, output_data="{}")
        )
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        with patch(f"{SECURITY}.AIRequest", create=True, new=MagicMock()), patch(f"{SECURITY}.AITaskType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIModelType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIServiceType", create=True, new=MagicMock()):
            report = await service.check_compliance(mod.ComplianceStandard.GDPR)
        assert report.overall_score == 100.0

    async def test_check_compliance_ai_not_ok(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False))
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        with patch(f"{SECURITY}.AIRequest", create=True, new=MagicMock()), patch(f"{SECURITY}.AITaskType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIModelType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIServiceType", create=True, new=MagicMock()):
            analysis = await service._ai_compliance_analysis(mod.ComplianceStandard.GDPR, {})
        assert analysis["score"] == 0.0

    async def test_check_compliance_ai_exception(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("no"))
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        with patch(f"{SECURITY}.AIRequest", create=True, new=MagicMock()), patch(f"{SECURITY}.AITaskType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIModelType", create=True, new=MagicMock()), patch(f"{SECURITY}.AIServiceType", create=True, new=MagicMock()):
            analysis = await service._ai_compliance_analysis(mod.ComplianceStandard.GDPR, {})
        assert analysis["findings"] == []

    async def test_check_compliance_no_ai_service(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": None})
        service._get_compliance_data = AsyncMock(return_value={})
        report = await service.check_compliance(mod.ComplianceStandard.CCPA)
        assert report.overall_score == 100.0
        assert service.security_metrics["compliance_checks_passed"] == 1

    async def test_check_compliance_exception_returns_none(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service._get_compliance_data = AsyncMock(side_effect=RuntimeError("boom"))
        assert await service.check_compliance(mod.ComplianceStandard.GDPR) is None

    async def test_calculate_compliance_score_exception(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        assert service._calculate_compliance_score({"findings": [1, 2]}) == 0.0

    async def test_compliance_requirements_all_standards(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        for standard in mod.ComplianceStandard:
            requirements = service._get_compliance_requirements(standard)
            assert isinstance(requirements, list)

    async def test_check_compliance_for_event_branches(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        audit = mod.SecurityAudit(
            audit_id="a1",
            event_type=mod.AuditEventType.DATA_ACCESS,
            user_id="u1",
            resource="r",
            action="data_access",
            result="success",
            ip_address="1.1.1.1",
            user_agent="",
            timestamp=datetime.now(timezone.utc),
            metadata={},
        )
        issues = await service._check_compliance_for_event(audit)
        assert any(i["standard"] == "SOC2" for i in issues)
        audit.action = "data_export"
        audit.metadata = {"encrypted": True}
        issues = await service._check_compliance_for_event(audit)
        assert issues == []
        audit.metadata = {}
        issues = await service._check_compliance_for_event(audit)
        assert any(i["standard"] == "GDPR" for i in issues)

    async def test_parse_ai_compliance_results_stub(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        result = service._parse_ai_compliance_results("{}", mod.ComplianceStandard.SOC2)
        assert result["score"] == 0.0

    async def test_audit_event_with_db(self):
        mod = _mod("atom_enterprise_security_service")
        db = MagicMock()
        db.store_security_audit = AsyncMock()
        service = mod.AtomEnterpriseSecurityService(config={"database": db})
        result = await service.audit_event(
            {
                "event_type": "user_login",
                "user_id": "u1",
                "resource": "r",
                "action": "login",
                "result": "success",
                "ip_address": "1.1.1.1",
            }
        )
        assert result is not None
        db.store_security_audit.assert_awaited_once()

    async def test_audit_event_exception_returns_none(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        assert await service.audit_event({"user_id": "u1"}) is None

    async def test_audit_event_unknown_type_coerced(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        result = await service.audit_event(
            {
                "event_type": "automation_created",
                "user_id": "u1",
                "resource": "r",
                "action": "log",
                "result": "success",
                "ip_address": "1.1.1.1",
            }
        )
        assert result is not None
        assert result.event_type == mod.AuditEventType.CONFIG_CHANGED
        assert service.security_metrics["audit_events_logged"] == 1

    async def test_log_security_audit(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        audit = await service._log_security_audit(
            event_type=mod.AuditEventType.SECURITY_ALERT,
            user_id="sys",
            resource="r",
            action="block",
            result="success",
            metadata={"k": "v"},
        )
        assert audit is not None
        assert service.security_metrics["audit_events_logged"] == 1


class TestSecurityCrypto:
    async def test_encrypt_decrypt_roundtrip(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        encrypted = await service.encrypt_data("value", {"user": "u1"})
        data, context = await service.decrypt_data(encrypted)
        assert data == "value"
        assert context == {"user": "u1"}

    async def test_decrypt_no_context(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        encrypted = await service.encrypt_data("plain")
        data, context = await service.decrypt_data(encrypted)
        assert data == "plain"
        assert context is None

    async def test_encrypt_exception_raises(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service.cipher_suite.encrypt = MagicMock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError):
            await service.encrypt_data("x")

    async def test_decrypt_exception_raises(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        with pytest.raises(Exception):
            await service.decrypt_data("not-base64!!!")

    async def test_generate_encryption_key(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        key = service._generate_encryption_key()
        assert key != service._generate_encryption_key()


class TestSecurityPasswordAndBehavior:
    async def test_validate_password_strong(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        result = await service.validate_password("Str0ng!Passw0rd")
        assert result["valid"] is True
        assert result["score"] == 100

    async def test_validate_password_weak_common_pattern(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        result = await service.validate_password("password123")
        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert len(result["suggestions"]) == 3

    async def test_validate_password_relaxed_policy(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService(
            config={
                "password_policy": {
                    "min_length": 4,
                    "require_upper": False,
                    "require_lower": False,
                    "require_numbers": False,
                    "require_special": False,
                    "prevent_reuse": 1,
                }
            }
        )
        result = await service.validate_password("abc")
        assert result["score"] == 20
        assert result["valid"] is False

    async def test_analyze_user_behavior_no_ai(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": None})
        result = await service.analyze_user_behavior("u1", "48h")
        assert result["risk_score"] == 0.0

    async def test_analyze_user_behavior_with_ai(self):
        mod = _mod("atom_enterprise_security_service")
        ai = MagicMock()
        service = mod.AtomEnterpriseSecurityService(config={"ai_service": ai})
        service._ai_behavior_analysis = AsyncMock(
            return_value={"risk_score": 0.7, "anomalies": [{"a": 1}]}
        )
        result = await service.analyze_user_behavior("u1")
        assert result["risk_score"] == 0.7
        assert result["anomalies"] == [{"a": 1}]

    async def test_analyze_user_behavior_exception(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        service._get_user_activities = AsyncMock(side_effect=RuntimeError("no"))
        result = await service.analyze_user_behavior("u1")
        assert "error" in result

    async def test_behavior_stub_methods(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        assert service._calculate_login_frequency([]) == 0.0
        assert service._analyze_access_patterns([]) == {}
        assert service._calculate_data_access_volume([]) == 0
        assert service._detect_unusual_activities([]) == []
        assert await service._ai_behavior_analysis("u1", []) == {}
        assert service._detect_anomalies({}, {}) == []
        assert await service._get_user_activities("u1", "24h") == []
        assert await service._validate_security_policy(MagicMock()) == {"valid": True, "errors": []}

    async def test_initialize_real_substeps(self):
        mod = _mod("atom_enterprise_security_service")
        service = mod.AtomEnterpriseSecurityService()
        assert await service.initialize() is True
        assert service.monitoring_active is True


class TestUnifiedCoercion:
    async def test_coerce_compliance_standard(self):
        mod = _mod("atom_enterprise_unified_service")
        assert mod._coerce_compliance_standard("GDPR") == mod.ComplianceStandard.GDPR
        assert mod._coerce_compliance_standard("gdpr") == mod.ComplianceStandard.GDPR
        assert (
            mod._coerce_compliance_standard(mod.ComplianceStandard.SOC2)
            == mod.ComplianceStandard.SOC2
        )
        with pytest.raises(ValueError):
            mod._coerce_compliance_standard("bogus")
        with pytest.raises(ValueError):
            mod._coerce_compliance_standard(42)

    async def test_enums(self):
        mod = _mod("atom_enterprise_unified_service")
        assert len(list(mod.EnterpriseServiceType)) == 7
        assert len(list(mod.WorkflowSecurityLevel)) == 5
        assert len(list(mod.ComplianceWorkflowType)) == 6
        assert len(list(mod.AutomationTriggerType)) == 8


class TestUnifiedInitialize:
    async def test_initialize_missing_services(self):
        mod = _mod("atom_enterprise_unified_service")
        with patch.object(mod, "atom_enterprise_security_service", None, create=True):
            service = mod.AtomEnterpriseUnifiedService()
            assert await service.initialize() is False

    async def test_initialize_resolves_security_service_via_fallback(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService(config={"ai_service": MagicMock()})
        assert service.security_service is not None
        assert await service.initialize() is True

    async def test_initialize_success(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService(config={"ai_service": MagicMock()})
        service._initialize_enterprise_services = AsyncMock()
        service._setup_workflow_security_integration = AsyncMock()
        service._setup_compliance_automation = AsyncMock()
        service._setup_ai_powered_automation = AsyncMock()
        service._start_enterprise_monitoring = AsyncMock()
        assert await service.initialize() is True
        assert service.is_initialized is True

    async def test_initialize_exception(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service._initialize_enterprise_services = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        assert await service.initialize() is False

    async def test_enterprise_service_setup_methods(self):
        mod = _mod("atom_enterprise_unified_service")
        security = MagicMock()
        security.setup_workflow_monitoring = AsyncMock()
        security.setup_compliance_automation = AsyncMock()
        security.start_monitoring = AsyncMock()
        ai = MagicMock()
        ai.setup_workflow_automation = AsyncMock()
        ai.start_monitoring = AsyncMock()
        service = mod.AtomEnterpriseUnifiedService(
            config={"security_service": security, "ai_integration": ai}
        )
        await service._setup_workflow_security_integration()
        await service._setup_compliance_automation()
        await service._setup_ai_powered_automation()
        await service._start_enterprise_monitoring()
        security.setup_workflow_monitoring.assert_awaited_once()
        security.setup_compliance_automation.assert_awaited_once()
        ai.setup_workflow_automation.assert_awaited_once()
        security.start_monitoring.assert_awaited_once()
        ai.start_monitoring.assert_awaited_once()

    async def test_enterprise_service_setup_exceptions(self):
        mod = _mod("atom_enterprise_unified_service")
        security = MagicMock()
        security.setup_workflow_monitoring = AsyncMock(side_effect=RuntimeError("x"))
        service = mod.AtomEnterpriseUnifiedService(config={"security_service": security})
        await service._setup_workflow_security_integration()
        await service._setup_compliance_automation()
        await service._setup_ai_powered_automation()
        await service._start_enterprise_monitoring()

    async def test_initialize_enterprise_services_without_deps(self):
        mod = _mod("atom_enterprise_unified_service")
        with patch.object(mod, "atom_enterprise_security_service", None, create=True):
            service = mod.AtomEnterpriseUnifiedService()
            await service._initialize_enterprise_services()
            assert service.security_service is not None


class TestUnifiedWorkflowLifecycle:
    def _workflow_data(self, **overrides):
        data = {
            "name": "WF-Test",
            "description": "d",
            "service_type": "security",
            "security_level": "confidential",
            "compliance_standards": ["SOC2"],
            "triggers": [{"type": "event", "event_type": "login"}],
            "steps": [{"name": "s", "type": "security_check", "config": {}}],
            "actions": [{"type": "notify"}],
            "metadata": {"m": 1},
        }
        data.update(overrides)
        return data

    async def test_create_enterprise_workflow_with_workflow_service(self):
        mod = _mod("atom_enterprise_unified_service")
        wf_service = MagicMock()
        wf_service.create_workflow = AsyncMock(return_value={"ok": True, "id": "x"})
        service = mod.AtomEnterpriseUnifiedService(config={"workflow_service": wf_service})
        result = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        assert result["ok"] is True
        wf_service.create_workflow.assert_awaited_once()
        assert len(result["security_actions"]) == 1
        assert len(result["compliance_automations"]) == 1

    async def test_create_enterprise_workflow_workflow_service_failure(self):
        mod = _mod("atom_enterprise_unified_service")
        wf_service = MagicMock()
        wf_service.create_workflow = AsyncMock(return_value={"ok": False, "error": "no"})
        service = mod.AtomEnterpriseUnifiedService(config={"workflow_service": wf_service})
        result = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        assert result["ok"] is False

    async def test_create_enterprise_workflow_invalid_standard(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.create_enterprise_workflow(
            self._workflow_data(compliance_standards=["NOT_A_STD"]), "u1"
        )
        assert result["ok"] is False

    async def test_create_enterprise_workflow_exception(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.create_enterprise_workflow({"name": "x"}, "u1")
        assert result["ok"] is False

    async def test_create_enterprise_workflow_validation_failure(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service._validate_enterprise_workflow = AsyncMock(
            return_value={"valid": False, "errors": ["bad"]}
        )
        result = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        assert result["ok"] is False
        assert "Workflow validation failed" in result["error"]

    async def test_create_enterprise_workflow_with_db(self):
        mod = _mod("atom_enterprise_unified_service")
        db = MagicMock()
        db.store_enterprise_workflow = AsyncMock()
        service = mod.AtomEnterpriseUnifiedService(config={"database": db})
        result = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        assert result["ok"] is True
        db.store_enterprise_workflow.assert_awaited_once()

    async def test_execute_enterprise_workflow_all_step_types(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        step_types = [
            "security_check",
            "compliance_check",
            "ai_analysis",
            "data_processing",
            "notification",
            "custom_step",
        ]
        data = self._workflow_data(
            steps=[{"name": f"s{i}", "type": t, "config": {}} for i, t in enumerate(step_types)]
        )
        created = await service.create_enterprise_workflow(data, "u1")
        result = await service.execute_enterprise_workflow(
            created["workflow_id"], {"trigger": "t"}, "u1"
        )
        assert result["ok"] is True
        assert len(result["execution_results"]) == 6
        assert service.enterprise_metrics["automations_executed"] == 1

    async def test_execute_enterprise_workflow_not_found(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.execute_enterprise_workflow("nope", {}, "u1")
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_execute_workflow_security_precheck_failure(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        created = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        service._security_pre_check = AsyncMock(
            return_value={"passed": False, "reason": "unauthorized"}
        )
        result = await service.execute_enterprise_workflow(
            created["workflow_id"], {}, "u1"
        )
        assert result["ok"] is False
        assert "Security check failed" in result["error"]

    async def test_execute_workflow_compliance_precheck_failure(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        created = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        service._compliance_pre_check = AsyncMock(
            return_value={"passed": False, "reason": "noncompliant"}
        )
        result = await service.execute_enterprise_workflow(
            created["workflow_id"], {}, "u1"
        )
        assert result["ok"] is False
        assert "Compliance check failed" in result["error"]

    async def test_execute_workflow_with_alerts_and_violations(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        created = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        security = MagicMock()
        security.log_security_alert = AsyncMock()
        security.log_compliance_violation = AsyncMock()
        service.security_service = security
        service._monitor_step_execution = AsyncMock(
            return_value={"alert": True, "severity": "high"}
        )
        service._monitor_step_compliance = AsyncMock(
            return_value={"violation": True, "severity": "high"}
        )
        result = await service.execute_enterprise_workflow(
            created["workflow_id"], {}, "u1"
        )
        assert result["ok"] is True
        security.log_security_alert.assert_awaited_once()
        security.log_compliance_violation.assert_awaited_once()
        assert created["workflow_id"] in service.enterprise_workflows
        assert service.enterprise_workflows[created["workflow_id"]].status == "blocked"

    async def test_execute_workflow_medium_severity_handlers(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        created = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        service._monitor_step_execution = AsyncMock(
            return_value={"alert": True, "severity": "medium"}
        )
        service._monitor_step_compliance = AsyncMock(
            return_value={"violation": True, "severity": "medium"}
        )
        result = await service.execute_enterprise_workflow(
            created["workflow_id"], {}, "u1"
        )
        assert result["ok"] is True
        assert created["workflow_id"] in service.workflow_monitoring

    async def test_execute_workflow_exception(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        created = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        service._security_pre_check = AsyncMock(side_effect=RuntimeError("boom"))
        result = await service.execute_enterprise_workflow(
            created["workflow_id"], {}, "u1"
        )
        assert result["ok"] is False

    async def test_security_pre_check_failures(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service._check_user_authorization = AsyncMock(return_value={"authorized": False})
        wf = MagicMock()
        result = await service._security_pre_check(wf, {}, "u1")
        assert result["passed"] is False
        service._check_user_authorization = AsyncMock(return_value={"authorized": True})
        service._validate_context_security = AsyncMock(return_value={"valid": False})
        result = await service._security_pre_check(wf, {}, "u1")
        assert result["passed"] is False
        service._validate_context_security = AsyncMock(side_effect=RuntimeError("x"))
        result = await service._security_pre_check(wf, {}, "u1")
        assert result["passed"] is False

    async def test_compliance_pre_check_failures(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        wf = MagicMock()
        wf.compliance_standards = [mod.ComplianceStandard.SOC2]
        service._check_compliance_requirements = AsyncMock(
            return_value={"compliant": False}
        )
        result = await service._compliance_pre_check(wf, {}, "u1")
        assert result["passed"] is False
        service._check_compliance_requirements = AsyncMock(
            return_value={"compliant": True}
        )
        result = await service._compliance_pre_check(wf, {}, "u1")
        assert result["passed"] is True
        service._check_compliance_requirements = AsyncMock(side_effect=RuntimeError("x"))
        result = await service._compliance_pre_check(wf, {}, "u1")
        assert result["passed"] is False

    async def test_ai_enhanced_context_paths(self):
        mod = _mod("atom_enterprise_unified_service")
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, output_data="insight", confidence=0.8)
        )
        service = mod.AtomEnterpriseUnifiedService(config={"ai_service": ai})
        now = datetime.now(timezone.utc)
        wf = mod.EnterpriseWorkflow(
            workflow_id="w1",
            name="n",
            description="d",
            service_type=mod.EnterpriseServiceType.SECURITY,
            security_level=mod.WorkflowSecurityLevel.CONFIDENTIAL,
            compliance_standards=[mod.ComplianceStandard.SOC2],
            triggers=[],
            steps=[],
            actions=[],
            created_at=now,
            updated_at=now,
            created_by="u",
            status="active",
            metadata={},
            audit_trail=[],
            compliance_checks=[],
        )
        with patch(f"{UNIFIED}.AIRequest", create=True, new=MagicMock()), patch(
            f"{UNIFIED}.AITaskType", create=True, new=MagicMock()
        ), patch(f"{UNIFIED}.AIModelType", create=True, new=MagicMock()), patch(
            f"{UNIFIED}.AIServiceType", create=True, new=MagicMock()
        ):
            result = await service._get_ai_enhanced_context(wf, {"k": "v"})
        assert result["ai_enhanced"] is True
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False))
        with patch(f"{UNIFIED}.AIRequest", create=True, new=MagicMock()), patch(
            f"{UNIFIED}.AITaskType", create=True, new=MagicMock()
        ), patch(f"{UNIFIED}.AIModelType", create=True, new=MagicMock()), patch(
            f"{UNIFIED}.AIServiceType", create=True, new=MagicMock()
        ):
            result = await service._get_ai_enhanced_context(wf, {})
        assert result["ai_enhanced"] is False
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        with patch(f"{UNIFIED}.AIRequest", create=True, new=MagicMock()), patch(
            f"{UNIFIED}.AITaskType", create=True, new=MagicMock()
        ), patch(f"{UNIFIED}.AIModelType", create=True, new=MagicMock()), patch(
            f"{UNIFIED}.AIServiceType", create=True, new=MagicMock()
        ):
            result = await service._get_ai_enhanced_context(wf, {})
        assert result["ai_enhanced"] is False
        no_ai = mod.AtomEnterpriseUnifiedService(config={"ai_service": None})
        result = await no_ai._get_ai_enhanced_context(wf, {"k": "v"})
        assert result["ai_enhanced"] is False

    async def test_execute_workflow_step_all_types(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        for step_type in ["security_check", "compliance_check", "ai_analysis", "data_processing", "notification", "other"]:
            result = await service._execute_workflow_step(
                {"type": step_type, "config": {}}, {}, "u1"
            )
            assert result["success"] is True
            assert "execution_time" in result

    async def test_execute_workflow_step_exception(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service._execute_security_check = AsyncMock(side_effect=RuntimeError("x"))
        result = await service._execute_workflow_step({"type": "security_check"}, {}, "u1")
        assert result["success"] is False

    async def test_security_and_compliance_post_checks(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        assert await service._security_post_check(MagicMock(), [], "u1") == {"passed": True}
        assert await service._compliance_post_check(MagicMock(), [], "u1") == {"passed": True}

    async def test_step_sub_implementations(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        assert (await service._execute_security_check({}, {}))["security_status"] == "passed"
        assert (await service._execute_compliance_check({}, {}))["compliance_status"] == "compliant"
        assert (await service._execute_ai_analysis({}, {}))["success"] is True
        assert (await service._execute_data_processing({}, {}))["success"] is True
        assert (await service._execute_notification({}, {}))["success"] is True
        assert (await service._execute_custom_step({}, {}))["success"] is True
        assert (await service._monitor_step_execution({}, {}, "u1"))["alert"] is False
        assert (await service._monitor_step_compliance({}, {}, "u1"))["violation"] is False
        assert await service._validate_workflow_security(MagicMock()) == {"valid": True, "errors": []}
        assert await service._validate_workflow_compliance(MagicMock()) == {"valid": True, "errors": []}
        assert (await service._assess_action_risk({}, MagicMock()))["risk_level"] == "medium"
        assert await service._check_user_authorization("u", MagicMock()) == {"authorized": True}
        assert await service._validate_context_security({}, MagicMock()) == {"valid": True}
        assert await service._check_compliance_requirements("SOC2", {}, "u") == {"compliant": True}
        assert "ai_analysis" in await service._get_security_ai_analysis({})
        assert "ai_analysis" in await service._get_compliance_ai_analysis({})

    async def test_validate_enterprise_workflow_exception(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service._validate_workflow_security = AsyncMock(side_effect=RuntimeError("boom"))
        result = await service._validate_enterprise_workflow(MagicMock())
        assert result["valid"] is False

    async def test_validate_enterprise_workflow_security_invalid(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service._validate_workflow_security = AsyncMock(
            return_value={"valid": False, "errors": ["e1"]}
        )
        result = await service._validate_enterprise_workflow(MagicMock())
        assert result["valid"] is False
        assert result["errors"] == ["e1"]


class TestUnifiedAutomations:
    def _workflow_data(self, **overrides):
        data = {
            "name": "WF-Test",
            "description": "d",
            "service_type": "security",
            "security_level": "confidential",
            "compliance_standards": ["SOC2"],
            "triggers": [],
            "steps": [{"name": "s", "type": "security_check", "config": {}}],
            "actions": [{"type": "notify"}],
            "metadata": {},
        }
        data.update(overrides)
        return data

    async def test_create_security_automation_full(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.create_security_automation(
            {"name": "SA", "description": "d"}, "u1"
        )
        assert result["ok"] is True
        assert result["automation_id"] in service.active_automations

    async def test_create_security_automation_bad_workflow(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service.create_enterprise_workflow = AsyncMock(
            return_value={"ok": False, "error": "x"}
        )
        result = await service.create_security_automation({"name": "SA", "description": "d"}, "u1")
        assert result["ok"] is False

    async def test_create_compliance_automation_full(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.create_compliance_automation(
            {
                "name": "CA",
                "description": "d",
                "compliance_standards": ["SOC2"],
                "workflow_type": "audit_remediation",
                "triggers": ["audit_failure"],
                "schedule": "daily",
            },
            "u1",
        )
        assert result["ok"] is True
        assert result["automation_id"] in service.compliance_automations

    async def test_create_compliance_automation_missing_standards(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.create_compliance_automation({"name": "CA"}, "u1")
        assert result["ok"] is False

    async def test_handle_security_event_no_automations(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.handle_security_event({"threat_type": "xss", "severity": "high"})
        assert result["ok"] is True
        assert result["relevant_automations"] == 0

    async def test_handle_security_event_with_automation(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        created = await service.create_security_automation(
            {"name": "SA", "description": "d", "threat_types": ["xss"]}, "u1"
        )
        result = await service.handle_security_event(
            {"threat_type": "xss", "severity": "critical"}
        )
        assert result["ok"] is True
        assert result["relevant_automations"] == 1
        assert service.enterprise_metrics["security_incidents_resolved"] == 1

    async def test_handle_security_event_severity_mismatch(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service.create_security_automation(
            {"name": "SA", "description": "d", "severity_levels": ["critical"]}, "u1"
        )
        result = await service.handle_security_event(
            {"threat_type": "xss", "severity": "low"}
        )
        assert result["relevant_automations"] == 0

    async def test_handle_compliance_violation_with_automation(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service.create_compliance_automation(
            {
                "name": "CA",
                "description": "d",
                "compliance_standards": ["SOC2"],
                "workflow_type": "audit_remediation",
            },
            "u1",
        )
        result = await service.handle_compliance_violation(
            {"standard": "SOC2", "violation_type": "audit_failure", "severity": "high"}
        )
        assert result["ok"] is True
        assert result["relevant_automations"] == 1
        assert service.enterprise_metrics["compliance_violations_resolved"] == 1

    async def test_handle_compliance_violation_no_match(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        result = await service.handle_compliance_violation(
            {"standard": "GDPR", "violation_type": "x"}
        )
        assert result["relevant_automations"] == 0

    async def test_handle_compliance_violation_unmatched_standard(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service.create_compliance_automation(
            {
                "name": "CA",
                "description": "d",
                "compliance_standards": ["GDPR"],
                "workflow_type": "audit_remediation",
            },
            "u1",
        )
        result = await service.handle_compliance_violation(
            {"standard": "SOC2", "violation_type": "x"}
        )
        assert result["relevant_automations"] == 0

    async def test_create_security_workflow_actions_direct(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        wf = mod.EnterpriseWorkflow(
            workflow_id="w1",
            name="n",
            description="d",
            service_type=mod.EnterpriseServiceType.SECURITY,
            security_level=mod.WorkflowSecurityLevel.RESTRICTED,
            compliance_standards=[mod.ComplianceStandard.SOC2],
            triggers=[],
            steps=[],
            actions=[{"type": "block", "config": {"x": 1}, "requires_approval": True}],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="u",
            status="active",
            metadata={},
            audit_trail=[],
            compliance_checks=[],
        )
        actions = await service._create_security_workflow_actions(wf, "u1")
        assert len(actions) == 1
        assert actions[0].approval_workflow == "approval_w1"
        assert actions[0].execution_timeout == 300

    async def test_create_compliance_automations_direct(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        wf = MagicMock()
        wf.workflow_id = "w2"
        wf.compliance_standards = [mod.ComplianceStandard.SOC2, mod.ComplianceStandard.GDPR]
        automations = await service._create_compliance_automations(wf, "u1")
        assert len(automations) == 2

    async def test_handle_alert_and_violation_handlers(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        created = await service.create_enterprise_workflow(self._workflow_data(), "u1")
        wf = service.enterprise_workflows[created["workflow_id"]]
        security = MagicMock()
        security.log_security_alert = AsyncMock()
        security.log_compliance_violation = AsyncMock()
        service.security_service = security
        await service._handle_security_alert({"severity": "high", "type": "x"}, wf, {"id": "s"}, "u1")
        assert wf.status == "blocked"
        await service._handle_security_alert({"severity": "medium"}, wf, {"id": "s"}, "u1")
        await service._handle_security_alert({"severity": "low"}, wf, {"id": "s"}, "u1")
        await service._handle_compliance_violation({"severity": "high"}, wf, {"id": "s"}, "u1")
        await service._handle_compliance_violation({"severity": "medium"}, wf, {"id": "s"}, "u1")
        await service._handle_compliance_violation({"severity": "low"}, wf, {"id": "s"}, "u1")
        security.log_security_alert.assert_awaited()
        security.log_compliance_violation.assert_awaited()
        assert wf.status == "blocked"

    async def test_handle_alert_without_security_service(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service.security_service = None
        wf = MagicMock()
        wf.workflow_id = "w1"
        await service._handle_security_alert({"severity": "high"}, wf, {"id": "s"}, "u1")
        await service._handle_compliance_violation({"severity": "high"}, wf, {"id": "s"}, "u1")

    async def test_block_workflow_execution(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        active = MagicMock()
        active.status = "running"
        service.active_workflows["w1"] = active
        wf = MagicMock()
        wf.status = "active"
        service.enterprise_workflows["w1"] = wf
        await service._block_workflow_execution("w1", "reason")
        assert active.status == "blocked"
        assert wf.status == "blocked"
        await service._block_workflow_execution("missing", "reason")

    async def test_monitoring_helpers(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service._increase_workflow_monitoring("w1")
        assert service.workflow_monitoring["w1"]["level"] == "enhanced"
        await service._enable_compliance_logging("w2")
        assert service.workflow_monitoring["w2"]["compliance_logging"] is True

    async def test_notify_teams(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service._notify_security_team({"type": "x"}, MagicMock(), "u1")
        await service._notify_compliance_team({"type": "x"}, MagicMock(), "u1")

    async def test_log_enterprise_event_with_security_service(self):
        mod = _mod("atom_enterprise_unified_service")
        security = MagicMock()
        security.audit_event = AsyncMock()
        service = mod.AtomEnterpriseUnifiedService(config={"security_service": security})
        await service._log_enterprise_event("created", "u1", "r", "create", "success")
        security.audit_event.assert_awaited_once()

    async def test_log_enterprise_event_without_security_service(self):
        mod = _mod("atom_enterprise_unified_service")
        with patch.object(mod, "atom_enterprise_security_service", None, create=True):
            service = mod.AtomEnterpriseUnifiedService()
            await service._log_enterprise_event("created", "u1", "r", "create", "success")


class TestUnifiedQueries:
    async def test_get_enterprise_workflows_filters(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service.create_enterprise_workflow(
            {
                "name": "WF-A",
                "description": "d",
                "service_type": "security",
                "security_level": "confidential",
                "compliance_standards": ["SOC2"],
                "triggers": [],
                "steps": [],
                "actions": [],
            },
            "u1",
        )
        assert len(await service.get_enterprise_workflows()) == 1
        assert len(await service.get_enterprise_workflows(filters={"service_type": "compliance"})) == 0
        assert len(await service.get_enterprise_workflows(filters={"security_level": "confidential"})) == 1
        assert len(await service.get_enterprise_workflows(filters={"compliance_standard": "GDPR"})) == 0
        assert len(await service.get_enterprise_workflows(filters={"compliance_standard": "SOC2"})) == 1

    async def test_get_automations_status(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service.create_security_automation({"name": "SA", "description": "d"}, "u1")
        status = await service.get_automations_status()
        assert status["total_automations"] == 1
        assert status["security_automations"] == 1
        assert status["active_automations"] == 1

    async def test_get_automations_status_exception(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        service.active_automations = {"a": "not-a-dict"}
        status = await service.get_automations_status()
        assert "error" in status

    async def test_get_enterprise_metrics_and_service_info(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        metrics = await service.get_enterprise_metrics()
        assert metrics["total_workflows"] == 0
        info = await service.get_service_info()
        assert info["status"] == "ACTIVE"

    async def test_close(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        await service.close()


class TestWorkflowAutomationLifecycle:
    def _automation_data(self, **overrides):
        data = {
            "name": "Auto-X",
            "description": "d",
            "automation_type": "security",
            "priority": "high",
            "conditions": [{"type": "event_triggered", "event_type": "login"}],
            "actions": [{"type": "notify", "config": {"channels": ["slack"]}}],
            "schedule": None,
            "timeout": 600,
            "notification_rules": [],
            "metadata": {},
        }
        data.update(overrides)
        return data

    async def test_create_automation(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_automation(self._automation_data(), "u1")
        assert result["ok"] is True
        assert service.automation_metrics["total_automations"] == 1

    async def test_create_automation_records_audit(self):
        mod = _mod("atom_workflow_automation_service")
        security = _mod("atom_enterprise_security_service").AtomEnterpriseSecurityService()
        service = mod.AtomWorkflowAutomationService(config={"security_service": security})
        result = await service.create_automation(self._automation_data(), "u1")
        assert result["ok"] is True
        assert len(security.audit_logs) == 1
        assert security.audit_logs[0].action == "log"

    async def test_create_automation_stores_db(self):
        mod = _mod("atom_workflow_automation_service")
        db = MagicMock()
        db.store_workflow_automation = AsyncMock()
        service = mod.AtomWorkflowAutomationService(config={"database": db})
        result = await service.create_automation(self._automation_data(), "u1")
        assert result["ok"] is True
        db.store_workflow_automation.assert_awaited_once()

    async def test_create_automation_validation_failure(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_automation(
            {"name": "x", "conditions": [{"no_type": 1}], "actions": [{"no_type": 2}]},
            "u1",
        )
        assert result["ok"] is False
        assert "validation" in result["error"].lower()

    async def test_create_automation_exception(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_automation({}, "u1")
        assert result["ok"] is False

    async def test_create_automation_enabled_flag(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_automation(
            self._automation_data(enabled=False), "u1"
        )
        assert result["ok"] is True
        assert service.automations[result["automation_id"]].enabled is False

    async def test_create_automation_scheduled(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_automation(
            self._automation_data(
                conditions=[{"type": "scheduled", "schedule": "0 2 * * *"}],
                schedule="0 2 * * *",
            ),
            "u1",
        )
        assert result["ok"] is True
        automation = service.automations[result["automation_id"]]
        assert automation.next_run is not None
        assert result["automation_id"] in service.scheduled_automations

    async def test_create_automation_all_trigger_types(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        for condition in [
            {"type": "event_triggered", "event_type": "msg"},
            {"type": "threshold_exceeded", "metric": "cpu", "threshold": 90},
            {"type": "anomaly_detected", "metric": "cpu"},
            {"type": "security_alert", "threat_type": "xss", "severity": "high"},
            {"type": "compliance_violation", "standard": "SOC2"},
        ]:
            result = await service.create_automation(
                self._automation_data(
                    name=f"A-{condition['type']}", conditions=[condition]
                ),
                "u1",
            )
            assert result["ok"] is True
        assert len(service.active_triggers) >= 5

    async def test_execute_automation_success(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            self._automation_data(
                actions=[
                    {"type": "notification", "config": {"channels": []}},
                    {"type": "logging"},
                ]
            ),
            "u1",
        )
        result = await service.execute_automation(
            created["automation_id"], {"authorized": True}, "user"
        )
        assert result["ok"] is True
        assert result["status"] == "completed"
        execution = service.executions[result["execution_id"]]
        assert len(execution.actions_executed) == 2

    async def test_execute_automation_not_found(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.execute_automation("nope", {}, "u")
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_execute_automation_not_active(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(self._automation_data(), "u1")
        service.automations[created["automation_id"]].status = mod.AutomationStatus.PAUSED
        result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is False
        assert "not active" in result["error"]

    async def test_execute_automation_security_check_fail(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(self._automation_data(), "u1")
        result = await service.execute_automation(
            created["automation_id"], {"authorized": False}, "u"
        )
        assert result["ok"] is False
        assert "Security check failed" in result["error"]

    async def test_execute_automation_compliance_check_fail(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._pre_execution_compliance_check = AsyncMock(
            return_value={"passed": False, "reason": "nope"}
        )
        created = await service.create_automation(self._automation_data(), "u1")
        result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is False
        assert "Compliance check failed" in result["error"]

    async def test_execute_automation_all_actions_fail(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            self._automation_data(actions=[{"type": "bogus_type"}]),
            "u1",
        )
        result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is True
        assert result["status"] == "failed"
        assert service.automations[created["automation_id"]].failure_count == 1

    async def test_execute_automation_stop_execution(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(self._automation_data(), "u1")
        service._execute_automation_action = AsyncMock(
            side_effect=[
                {"success": True, "stop_execution": True},
                {"success": True},
            ]
        )
        result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is True
        assert result["actions_executed"] == 1

    async def test_execute_automation_action_exception(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            self._automation_data(actions=[{"type": "notify", "config": {}}]), "u1"
        )
        service._execute_notification_action = AsyncMock(side_effect=RuntimeError("x"))
        result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is True
        assert result["status"] == "failed"

    async def test_execute_automation_exception_contained(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._pre_execution_security_check = AsyncMock(side_effect=RuntimeError("x"))
        created = await service.create_automation(self._automation_data(), "u1")
        result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is False

    async def test_execute_automation_with_db(self):
        mod = _mod("atom_workflow_automation_service")
        db = MagicMock()
        db.store_workflow_automation = AsyncMock()
        db.store_automation_execution = AsyncMock()
        service = mod.AtomWorkflowAutomationService(config={"database": db})
        created = await service.create_automation(
            self._automation_data(
                actions=[{"type": "notification", "config": {"channels": []}}]
            ),
            "u1",
        )
        result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is True
        db.store_automation_execution.assert_awaited_once()

    async def test_security_and_compliance_automation_creation(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_security_automation(
            {"threat_type": "xss", "severity": "high"}, {}
        )
        assert result["ok"] is True
        assert "execution_result" in result

    async def test_compliance_automation_creation(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_compliance_automation(
            {"standard": "SOC2", "violation_type": "audit", "severity": "medium"}, {}
        )
        assert result["ok"] is True
        assert "execution_result" in result

    async def test_integration_automation_creation(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_integration_automation("slack", {})
        assert result["ok"] is True

    async def test_integration_automation_unsupported_platform(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service.create_integration_automation("facebook", {})
        assert result["ok"] is False
        assert "Unsupported platform" in result["error"]

    async def test_get_automations_filters(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        await service.create_automation(self._automation_data(), "u1")
        assert len(await service.get_automations()) == 1
        assert len(await service.get_automations(filters={"automation_type": "compliance"})) == 0
        assert len(await service.get_automations(filters={"priority": "high"})) == 1
        assert len(await service.get_automations(filters={"status": "active"})) == 1
        assert len(await service.get_automations(filters={"created_by": "u1"})) == 1

    async def test_get_automations_string_arg(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        await service.create_automation(self._automation_data(), "u1")
        assert len(await service.get_automations("user-1")) == 1

    async def test_get_automation_executions_filters(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            self._automation_data(actions=[{"type": "logging"}]), "u1"
        )
        await service.execute_automation(created["automation_id"], {}, "trigger-src")
        assert len(await service.get_automation_executions()) == 1
        assert len(await service.get_automation_executions(automation_id="nope")) == 0
        assert len(await service.get_automation_executions(filters={"status": "completed"})) == 1
        assert len(await service.get_automation_executions(filters={"status": "failed"})) == 0
        assert len(await service.get_automation_executions(filters={"triggered_by": "trigger-src"})) == 1
        today = date.today()
        assert len(await service.get_automation_executions(filters={"date_from": today})) == 1
        assert len(await service.get_automation_executions(filters={"date_to": today})) == 1

    async def test_get_automation_metrics(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        metrics = await service.get_automation_metrics()
        assert metrics["total_automations"] == 0

    async def test_get_service_info(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        info = await service.get_service_info()
        assert info["status"] == "ACTIVE"

    async def test_initialize_success_and_failure(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService(config={"ai_service": MagicMock()})
        for method in [
            "_initialize_automation_templates",
            "_load_automations",
            "_initialize_automation_scheduling",
            "_initialize_trigger_listeners",
            "_initialize_integration_endpoints",
            "_start_automation_monitoring",
        ]:
            setattr(service, method, AsyncMock())
        assert await service.initialize() is True
        service2 = mod.AtomWorkflowAutomationService()
        service2._initialize_automation_templates = AsyncMock(
            side_effect=RuntimeError("x")
        )
        assert await service2.initialize() is False

    async def test_close(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service.scheduler_task = MagicMock()
        service.http_sessions = {"s1": AsyncMock()}
        await service.close()
        service.http_sessions["s1"].close.assert_awaited_once()


class TestWorkflowAutomationActions:
    async def _service(self, mod):
        return mod.AtomWorkflowAutomationService()

    async def test_execute_automation_action_dispatch(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        execution = MagicMock()
        for action_type in [
            "notification",
            "workflow_execution",
            "security_enforcement",
            "compliance_check",
            "data_processing",
            "api_call",
            "email_send",
            "message_send",
            "logging",
            "auditing",
            "reporting",
            "remediation",
        ]:
            result = await service._execute_automation_action(
                {"type": action_type, "config": {}}, {}, execution
            )
            assert isinstance(result, dict)
        result = await service._execute_automation_action(
            {"type": "unknown", "config": {}}, {}, execution
        )
        assert result["success"] is False

    async def test_execute_automation_action_exception(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._execute_notification_action = AsyncMock(side_effect=RuntimeError("x"))
        result = await service._execute_automation_action(
            {"type": "notification", "config": {}}, {}, MagicMock()
        )
        assert result["success"] is False

    async def test_notification_action_all_channels(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        for method in [
            "_notify_security_team",
            "_notify_compliance_officer",
            "_notify_management",
            "_notify_slack",
            "_notify_teams",
            "_notify_email",
        ]:
            setattr(service, method, AsyncMock())
        result = await service._execute_notification_action(
            {
                "channels": ["security_team", "compliance_officer", "management", "slack", "teams", "email", "unknown_chan"],
                "message": "m",
                "urgency": "high",
            },
            {},
        )
        assert result["success"] is True
        assert len(result["notification_results"]) == 7

    async def test_notification_action_exception(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._notify_slack = AsyncMock(side_effect=RuntimeError("x"))
        result = await service._execute_notification_action(
            {"channels": ["slack"]}, {}
        )
        assert result["success"] is False

    async def test_notify_methods_log(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        await service._notify_security_team("m", "high", {})
        await service._notify_compliance_officer("m", "high", {})
        await service._notify_management("m", "high", {})
        await service._notify_slack("m", "high", {})
        await service._notify_teams("m", "high", {})
        await service._notify_email("m", "high", {})

    async def test_workflow_action_paths(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service._execute_workflow_action({}, {})
        assert result["success"] is False
        assert "workflow_id" in result["error"]
        result = await service._execute_workflow_action({"workflow_id": "w1"}, {})
        assert result["success"] is False
        assert result["result"]["ok"] is False
        result = await service._execute_workflow_action(
            {"workflow_id": "w1"}, {}, 
        )
        unified = MagicMock()
        unified.execute_enterprise_workflow = AsyncMock(return_value={"ok": True})
        service.unified_service = unified
        result = await service._execute_workflow_action({"workflow_id": "w1"}, {})
        assert result["success"] is True
        service.unified_service = None
        result = await service._execute_workflow_action({"workflow_id": "w1"}, {})
        assert result["success"] is False
        service.unified_service = MagicMock()
        service.unified_service.execute_enterprise_workflow = AsyncMock(
            side_effect=RuntimeError("x")
        )
        result = await service._execute_workflow_action({"workflow_id": "w1"}, {})
        assert result["success"] is False

    async def test_security_enforcement_action_all_types(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service.security_service._block_ip = AsyncMock()
        service.security_service._lock_user_account = AsyncMock()
        service.security_service._terminate_session = AsyncMock()
        service.security_service._quarantine_resource = AsyncMock()
        for action in ["block_ip", "lock_user", "terminate_session", "quarantine"]:
            result = await service._execute_security_enforcement_action(
                {"action": action, "target": "t1"}, {}
            )
            assert result["success"] is True
        result = await service._execute_security_enforcement_action({}, {})
        assert result["success"] is False
        service.security_service = None
        result = await service._execute_security_enforcement_action({"action": "block_ip"}, {})
        assert result["success"] is False
        service.security_service = MagicMock()
        service.security_service._block_ip = AsyncMock(side_effect=RuntimeError("x"))
        result = await service._execute_security_enforcement_action({"action": "block_ip", "target": "t"}, {})
        assert result["success"] is False

    async def test_compliance_check_action(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        result = await service._execute_compliance_check_action({}, {})
        assert result["success"] is False
        result = await service._execute_compliance_check_action(
            {"standard": "soc2", "check_type": "manual"}, {"period": "monthly"}
        )
        assert result["success"] is True
        result = await service._execute_compliance_check_action({"standard": "bogus"}, {})
        assert result["success"] is False
        assert "Invalid compliance standard" in result["error"]
        service.security_service = None
        result = await service._execute_compliance_check_action({"standard": "soc2"}, {})
        assert result["success"] is False
        service.security_service = MagicMock()
        service.security_service.check_compliance = AsyncMock(side_effect=RuntimeError("x"))
        result = await service._execute_compliance_check_action({"standard": "soc2"}, {})
        assert result["success"] is False

    async def test_simple_action_types(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        assert (await service._execute_data_processing_action({}, {}))["success"] is True
        assert (await service._execute_api_call_action({}, {}))["success"] is True
        assert (await service._execute_email_action({}, {}))["success"] is True
        assert (await service._execute_message_action({}, {}))["success"] is True
        assert (await service._execute_logging_action({}, {}))["success"] is True
        assert (await service._execute_auditing_action({}, {}))["success"] is True
        assert (await service._execute_reporting_action({}, {}))["success"] is True
        assert (await service._execute_remediation_action({}, {}))["success"] is True

    async def test_pre_post_checks(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        sec = mod.WorkflowAutomation(
            automation_id="a",
            name="n",
            description="d",
            automation_type=mod.WorkflowAutomationType.SECURITY,
            priority=mod.AutomationPriority.HIGH,
            status=mod.AutomationStatus.ACTIVE,
            conditions=[],
            actions=[],
            schedule=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="u",
            last_executed=None,
            execution_count=0,
            success_count=0,
            failure_count=0,
            timeout=60,
            retry_policy={},
            notification_rules=[],
            metadata={},
            audit_trail=[],
        )
        assert (await service._pre_execution_security_check(sec, {}))["passed"] is True
        assert (await service._pre_execution_compliance_check(sec, {}))["passed"] is True
        comp = mod.WorkflowAutomation(
            automation_id="b",
            name="n",
            description="d",
            automation_type=mod.WorkflowAutomationType.COMPLIANCE,
            priority=mod.AutomationPriority.HIGH,
            status=mod.AutomationStatus.ACTIVE,
            conditions=[],
            actions=[],
            schedule=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="u",
            last_executed=None,
            execution_count=0,
            success_count=0,
            failure_count=0,
            timeout=60,
            retry_policy={},
            notification_rules=[],
            metadata={},
            audit_trail=[],
        )
        check = await service._pre_execution_compliance_check(comp, {})
        assert check["compliance_level"] == "compliant"
        assert (await service._post_execution_security_check(sec, [{"success": False}]))["passed"] is True
        assert (await service._post_execution_compliance_check(sec, []))["passed"] is True


class TestWorkflowSchedulerAndTriggers:
    async def test_scheduler_loop_runs_due_automation(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            {
                "name": "Sched",
                "description": "d",
                "automation_type": "security",
                "priority": "medium",
                "conditions": [{"type": "scheduled", "schedule": "0 2 * * *"}],
                "actions": [{"type": "logging"}],
                "schedule": "0 2 * * *",
            },
            "u1",
        )
        automation = service.automations[created["automation_id"]]
        automation.next_run = datetime.now(timezone.utc) - timedelta(minutes=1)
        service.scheduler_running = True
        with patch.object(
            mod.asyncio, "sleep", AsyncMock(side_effect=RuntimeError("stop"))
        ):
            with pytest.raises(RuntimeError):
                await service._scheduler_loop()
        assert any(
            e.automation_id == created["automation_id"] for e in service.executions.values()
        )

    async def test_handle_event_trigger_executes_automation(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            {
                "name": "Evt",
                "description": "d",
                "automation_type": "security",
                "priority": "medium",
                "conditions": [{"type": "event_triggered", "event_type": "msg"}],
                "actions": [{"type": "logging"}],
            },
            "u1",
        )
        service.trigger_listeners["security_alert"] = {
            "automations": [created["automation_id"]],
            "callback": service._handle_event_trigger,
        }
        await service._handle_event_trigger("security_alert", {"event": 1})
        assert any(
            e.automation_id == created["automation_id"] for e in service.executions.values()
        )

    async def test_handle_event_trigger_unknown_type(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        await service._handle_event_trigger("unknown_event", {})

    async def test_handle_event_trigger_disabled_automation(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            {
                "name": "Evt",
                "description": "d",
                "automation_type": "security",
                "priority": "medium",
                "conditions": [{"type": "event_triggered", "event_type": "msg"}],
                "actions": [{"type": "logging"}],
            },
            "u1",
        )
        automation = service.automations[created["automation_id"]]
        automation.enabled = False
        automation.status = mod.AutomationStatus.ACTIVE
        service.trigger_listeners["security_alert"] = {
            "automations": [created["automation_id"]],
            "callback": service._handle_event_trigger,
        }
        await service._handle_event_trigger("security_alert", {})
        assert len(service.executions) == 0

    async def test_initialize_trigger_listeners(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        assert await service._initialize_trigger_listeners() is True
        assert "event_triggered" in service.trigger_listeners
        result = await service.create_automation(
            {
                "name": "Evt",
                "description": "d",
                "automation_type": "security",
                "priority": "medium",
                "conditions": [{"type": "event_triggered", "event_type": "msg"}],
                "actions": [{"type": "logging"}],
            },
            "u1",
        )
        assert result["automation_id"] in service.trigger_listeners["msg"]["automations"]

    async def test_initialize_trigger_listeners_exception(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        automation.conditions = [{}]
        service.automations["a1"] = automation
        assert await service._initialize_trigger_listeners() is False

    async def test_initialize_scheduling(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        assert await service._initialize_automation_scheduling() is True
        assert service.scheduler_running is True
        assert await service._initialize_automation_scheduling() is True
        service.scheduler_task.cancel()

    async def test_schedule_automation_variants(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        automation.automation_id = "a1"
        automation.schedule = "0 2 * * *"
        automation.next_run = None
        assert (
            await service._schedule_automation(
                automation, {"type": "scheduled"}
            )
            is True
        )
        assert automation.next_run is not None
        assert (
            await service._schedule_automation(
                automation, {"type": "scheduled"}
            )
            is True
        )
        assert (
            await service._schedule_automation(automation, {"type": "event_triggered"})
            is False
        )
        automation.schedule = None
        assert (
            await service._schedule_automation(
                automation, {"type": "scheduled"}
            )
            is False
        )
        automation.schedule = "0 2 * * *"
        automation.next_run = MagicMock()
        automation.next_run + timedelta(days=1)
        assert (
            await service._schedule_automation(
                automation, {"type": "scheduled"}
            )
            is True
        )

    async def test_setup_event_trigger_variants(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        automation.automation_id = "a1"
        automation.enabled = True
        assert await service._setup_event_trigger(automation, {}) is False
        assert await service._setup_event_trigger(automation, {"type": "event_triggered"}) is True
        assert await service._setup_event_trigger(automation, {"event_type": "msg"}) is True
        assert service.active_triggers["a1"]["type"] == "event"

    async def test_setup_threshold_and_anomaly_triggers(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        automation.automation_id = "a1"
        automation.enabled = True
        assert await service._setup_threshold_trigger(automation, {"metric": "cpu"}) is False
        assert await service._setup_threshold_trigger(
            automation, {"metric": "cpu", "threshold": 90, "operator": "gte"}
        ) is True
        assert await service._setup_anomaly_trigger(automation, {}) is False
        assert await service._setup_anomaly_trigger(
            automation, {"metric": "cpu", "sensitivity": "high"}
        ) is True

    async def test_setup_security_trigger(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        automation.automation_id = "a1"
        automation.enabled = True
        assert await service._setup_security_trigger(automation, {"threat_type": "xss"}) is True
        security = MagicMock()
        security.register_security_trigger = AsyncMock()
        service.security_service = security
        assert await service._setup_security_trigger(automation, {"threat_type": "xss", "severity": "critical"}) is True
        security.register_security_trigger.assert_awaited_once()

    async def test_setup_compliance_trigger(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        automation.automation_id = "a1"
        automation.enabled = True
        assert await service._setup_compliance_trigger(automation, {"standard": "SOC2"}) is True
        unified = MagicMock()
        unified.register_compliance_trigger = AsyncMock()
        service.unified_service = unified
        assert await service._setup_compliance_trigger(automation, {"standard": "SOC2", "violation_type": "audit"}) is True
        unified.register_compliance_trigger.assert_awaited_once()

    async def test_setup_platform_triggers(self):
        mod = _mod("atom_workflow_automation_service")
        integration = MagicMock()
        integration.register_webhook = AsyncMock()
        integration.start_polling = AsyncMock()
        integration.subscribe_to_events = AsyncMock()
        with patch.object(
            mod, "atom_slack_integration", integration
        ):
            service = mod.AtomWorkflowAutomationService()
            assert await service._setup_platform_triggers("unknown", "a1", {}) is False
            assert await service._setup_platform_triggers("slack", "a1", {"trigger_type": "webhook", "webhook_url": "u", "events": ["e"]}) is True
            assert await service._setup_platform_triggers("slack", "a1", {"trigger_type": "polling", "polling_interval": 10}) is True
            assert await service._setup_platform_triggers("slack", "a1", {"trigger_type": "event_subscription", "events": ["e"]}) is True
            assert await service._setup_platform_triggers("slack", "a1", {"trigger_type": "none"}) is True
            integration.register_webhook.assert_awaited_once()
            integration.start_polling.assert_awaited_once()
            integration.subscribe_to_events.assert_awaited_once()

    async def test_setup_platform_triggers_not_available(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        assert await service._setup_platform_triggers("slack", "a1", {}) is False

    async def test_initialize_integration_endpoints(self):
        mod = _mod("atom_workflow_automation_service")
        integration = MagicMock()
        integration.test_connection = AsyncMock(return_value=True)
        with patch.object(mod, "atom_slack_integration", integration):
            service = mod.AtomWorkflowAutomationService()
            assert await service._initialize_integration_endpoints() is True
            integration.test_connection.assert_awaited_once()

    async def test_initialize_integration_endpoints_exception(self):
        mod = _mod("atom_workflow_automation_service")
        integration = MagicMock()
        integration.test_connection = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(mod, "atom_slack_integration", integration):
            service = mod.AtomWorkflowAutomationService()
            assert await service._initialize_integration_endpoints() is True

    async def test_start_monitoring_and_loop(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        assert await service._start_automation_monitoring() is True
        failed = MagicMock()
        failed.enabled = True
        failed.status = mod.AutomationStatus.ACTIVE
        failed.last_execution_status = "failed"
        failed.execution_count = 10
        failed.failure_count = 8
        service.automations["f1"] = failed
        with patch.object(
            mod.asyncio, "sleep", AsyncMock(side_effect=RuntimeError("stop"))
        ):
            with pytest.raises(RuntimeError):
                await service._monitoring_loop()
        assert service.automation_metrics["total_automations"] == 1
        assert service.automation_metrics["active_automations"] == 1

    async def test_initialize_templates(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        assert await service._initialize_automation_templates() is True
        assert len(service.automation_templates) >= 4

    async def test_initialize_templates_with_db(self):
        mod = _mod("atom_workflow_automation_service")
        db = MagicMock()
        row_with_id = ("", "",)
        db.execute.return_value = [
            (json.dumps({"template_id": "t1", "name": "n"}),),
            (json.dumps({"name": "no-id"}),),
            ({"template_id": "t2"},),
        ]
        service = mod.AtomWorkflowAutomationService(config={"database": db})
        assert await service._initialize_automation_templates() is True
        assert "t1" in service.automation_templates
        assert "t2" in service.automation_templates

    async def test_initialize_templates_db_error(self):
        mod = _mod("atom_workflow_automation_service")
        db = MagicMock()
        db.execute.side_effect = RuntimeError("db down")
        service = mod.AtomWorkflowAutomationService(config={"database": db})
        assert await service._initialize_automation_templates() is True

    async def test_initialize_templates_exception(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service.automation_templates = None
        result = await service._initialize_automation_templates()
        assert result is False

    async def test_load_automations_no_db(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        assert await service._load_automations() is False

    async def test_load_automations_with_rows(self):
        mod = _mod("atom_workflow_automation_service")
        db = MagicMock()
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=1)
        row = (
            "auto-1",
            "Loaded",
            "d",
            "security",
            json.dumps([{"type": "scheduled", "schedule": "0 2 * * *"}]),
            json.dumps([{"type": "logging"}]),
            "high",
            "active",
            True,
            "creator",
            now.isoformat(),
            now.isoformat(),
            "0 2 * * *",
            future.isoformat(),
            now.isoformat(),
            3,
            2,
            1,
            "success",
            json.dumps({"k": "v"}),
        )
        db.execute.return_value = [row]
        service = mod.AtomWorkflowAutomationService(config={"database": db})
        assert await service._load_automations() is True
        assert "auto-1" in service.automations
        assert service.automations["auto-1"].next_run is not None

    async def test_load_automations_exception(self):
        mod = _mod("atom_workflow_automation_service")
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        service = mod.AtomWorkflowAutomationService(config={"database": db})
        assert await service._load_automations() is False

    async def test_update_automation_metrics(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        execution = MagicMock()
        execution.execution_time = 5.0
        execution.status = mod.AutomationStatus.COMPLETED
        service.automation_metrics["executions_by_status"]["completed"] = 2
        await service._update_automation_metrics(automation, execution)
        assert service.automation_metrics["executed_today"] == 1
        assert service.automation_metrics["success_rate"] == 1.0
        execution.execution_time = 0.0
        await service._update_automation_metrics(automation, execution)


class TestWorkflowNotificationsAndMaturity:
    async def test_send_notifications_default_failure(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._notify_slack = AsyncMock()
        automation = MagicMock()
        automation.metadata = {}
        automation.name = "A"
        automation.automation_id = "a1"
        automation.notification_rules = []
        execution = MagicMock()
        execution.status = mod.AutomationStatus.FAILED
        execution.error = "err"
        assert await service._send_automation_notifications(automation, execution) is True
        service._notify_slack.assert_awaited_once()

    async def test_send_notifications_default_success_no_op(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._notify_slack = AsyncMock()
        automation = MagicMock()
        automation.metadata = {}
        automation.name = "A"
        automation.automation_id = "a1"
        automation.notification_rules = []
        execution = MagicMock()
        execution.status = mod.AutomationStatus.COMPLETED
        execution.error = None
        assert await service._send_automation_notifications(automation, execution) is True
        service._notify_slack.assert_not_awaited()

    async def test_send_notifications_configured_rules(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._notify_slack = AsyncMock()
        service._notify_email = AsyncMock()
        service._notify_teams = AsyncMock()
        automation = MagicMock()
        automation.metadata = {}
        automation.name = "A"
        automation.automation_id = "a1"
        automation.notification_rules = []
        automation.notification_rules = [
            {
                "status": "completed",
                "channels": ["slack:ops", "email:team", "teams:grp"],
                "message": "Configured msg",
                "urgency": "low",
            },
            {"on_error": True, "channels": ["slack:err"], "message": "Err msg"},
        ]
        execution = MagicMock()
        execution.status = mod.AutomationStatus.COMPLETED
        execution.error = None
        execution.value = None
        assert await service._send_automation_notifications(automation, execution) is True
        service._notify_slack.assert_awaited_once()
        service._notify_email.assert_awaited_once()
        service._notify_teams.assert_awaited_once()

    async def test_send_notifications_metadata_rules(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        service._notify_slack = AsyncMock()
        automation = MagicMock()
        automation.notification_rules = []
        automation.metadata = {
            "notification_rules": [
                {"on_error": True, "channels": ["slack:err"], "message": "m"}
            ]
        }
        automation.name = "A"
        execution = MagicMock()
        execution.status = mod.AutomationStatus.FAILED
        execution.error = "boom"
        assert await service._send_automation_notifications(automation, execution) is True
        service._notify_slack.assert_awaited_once()

    async def test_send_notifications_exception(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        automation = MagicMock()
        automation.metadata = {}
        automation.name = "A"
        automation.automation_id = "a1"
        automation.notification_rules = []
        execution = MagicMock()
        execution.status = mod.AutomationStatus.FAILED
        execution.error = "err"
        service._notify_slack = AsyncMock(side_effect=RuntimeError("x"))
        assert await service._send_automation_notifications(automation, execution) is False

    async def test_log_automation_event(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        await service._log_automation_event("a1", "created", "u1", {})
        security = MagicMock()
        security.audit_event = AsyncMock()
        service.security_service = security
        await service._log_automation_event("a1", "created", "u1", {"x": 1})
        security.audit_event.assert_awaited_once()

    async def test_maturity_interception_blocked(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            {
                "name": "Maturity",
                "description": "d",
                "automation_type": "security",
                "priority": "high",
                "conditions": [{"type": "event_triggered", "event_type": "x"}],
                "actions": [
                    {
                        "type": "workflow_execution",
                        "config": {"agent_id": "agent-1", "workflow_id": "w1"},
                    }
                ],
            },
            "u1",
        )
        interceptor = MagicMock()
        decision = SimpleNamespace(
            routing_decision=SimpleNamespace(value="blocked"),
            agent_maturity="STUDENT",
            confidence_score=0.3,
            execute=False,
            reason="Maturity too low",
        )
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.trigger_interceptor.TriggerInterceptor", MagicMock(return_value=interceptor)):
            result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is False
        assert result["maturity_check"]["blocked"] is True

    async def test_maturity_interception_allowed(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            {
                "name": "Maturity2",
                "description": "d",
                "automation_type": "security",
                "priority": "high",
                "conditions": [{"type": "event_triggered", "event_type": "x"}],
                "actions": [
                    {
                        "type": "workflow_execution",
                        "config": {"agent_id": "agent-1", "workflow_id": "w1"},
                    }
                ],
            },
            "u1",
        )
        interceptor = MagicMock()
        decision = SimpleNamespace(
            routing_decision=SimpleNamespace(value="allowed"),
            agent_maturity="AUTONOMOUS",
            confidence_score=0.95,
            execute=True,
            reason="ok",
        )
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.trigger_interceptor.TriggerInterceptor", MagicMock(return_value=interceptor)):
            result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is True

    async def test_maturity_interception_value_error(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        created = await service.create_automation(
            {
                "name": "Maturity3",
                "description": "d",
                "automation_type": "security",
                "priority": "high",
                "conditions": [{"type": "event_triggered", "event_type": "x"}],
                "actions": [
                    {
                        "type": "agent_trigger",
                        "config": {"agent_id": "agent-1"},
                    }
                ],
            },
            "u1",
        )
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(side_effect=ValueError("no agent"))
        with patch("core.trigger_interceptor.TriggerInterceptor", MagicMock(return_value=interceptor)):
            result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is True

    async def test_maturity_interception_with_db_commit(self):
        mod = _mod("atom_workflow_automation_service")
        db = MagicMock()
        db.store_workflow_automation = AsyncMock()
        service = mod.AtomWorkflowAutomationService(config={"database": db})
        created = await service.create_automation(
            {
                "name": "Maturity4",
                "description": "d",
                "automation_type": "security",
                "priority": "high",
                "conditions": [{"type": "event_triggered", "event_type": "x"}],
                "actions": [
                    {"type": "agent_trigger", "config": {"agent_id": "agent-1"}}
                ],
            },
            "u1",
        )
        interceptor = MagicMock()
        decision = SimpleNamespace(
            routing_decision=SimpleNamespace(value="blocked"),
            agent_maturity="STUDENT",
            confidence_score=0.3,
            execute=False,
            reason="low",
        )
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.trigger_interceptor.TriggerInterceptor", MagicMock(return_value=interceptor)):
            result = await service.execute_automation(created["automation_id"], {}, "u")
        assert result["ok"] is False
        db.commit.assert_called_once()


class TestWorkflowAutomationGuards:
    async def test_circuit_breaker_open(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        with patch.object(
            mod.circuit_breaker, "is_enabled", AsyncMock(return_value=False)
        ):
            result = await service.create_automation({}, "u")
            assert result["ok"] is False
            with pytest.raises(HTTPException) as exc_info:
                await service.close()
            assert exc_info.value.status_code == 503

    async def test_rate_limited(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        with patch.object(
            mod.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))
        ):
            result = await service.execute_automation("x", {}, "u")
            assert result["ok"] is False
            with pytest.raises(HTTPException) as exc_info:
                await service.close()
            assert exc_info.value.status_code == 429

    async def test_validate_automation_data_guards(self):
        mod = _mod("atom_workflow_automation_service")
        service = mod.AtomWorkflowAutomationService()
        with patch.object(
            mod.circuit_breaker, "is_enabled", AsyncMock(return_value=False)
        ):
            with pytest.raises(HTTPException):
                await service._validate_automation_data({})
        with patch.object(
            mod.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))
        ):
            with pytest.raises(HTTPException):
                await service._validate_automation_data({})

    async def test_unified_guards(self):
        mod = _mod("atom_enterprise_unified_service")
        service = mod.AtomEnterpriseUnifiedService()
        with patch.object(
            mod.circuit_breaker, "is_enabled", AsyncMock(return_value=False)
        ):
            result = await service.create_enterprise_workflow({}, "u")
            assert result["ok"] is False
            with pytest.raises(HTTPException):
                await service.get_enterprise_metrics()
        with patch.object(
            mod.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))
        ):
            result = await service.get_automations_status()
            assert "error" in result
            with pytest.raises(HTTPException):
                await service.close()
        with patch.object(
            mod.circuit_breaker, "is_enabled", AsyncMock(return_value=False)
        ):
            result = await service._validate_enterprise_workflow(MagicMock())
            assert result["valid"] is False
        with patch.object(
            mod.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))
        ):
            result = await service._validate_enterprise_workflow(MagicMock())
            assert result["valid"] is False
