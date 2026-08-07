"""Repair + coverage tests for backend/integrations services.

Covers the modules that previously failed to parse (syntax errors broke
coverage reporting and mypy), plus behavioral coverage of their public
service methods with all external HTTP/OAuth calls mocked.
"""
import asyncio
import importlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "atom_enterprise_security_service",
        "atom_enterprise_unified_service",
        "atom_quickbooks_integration_service",
        "atom_video_ai_service",
        "atom_voice_ai_service",
        "atom_workflow_automation_service",
        "atom_zendesk_integration_service",
        "whatsapp_start_development",
    ],
)
def test_repaired_module_imports_cleanly(module_name):
    module = importlib.import_module(f"integrations.{module_name}")
    assert module is not None


def _qb_config():
    return {
        "auto_categorization": False,
        "fraud_detection": False,
        "enable_stripe_integration": False,
        "enable_enterprise_features": False,
        "quickbooks_access_token": "test-token",
        "quickbooks_company_id": "123",
    }


def _zd_config():
    return {
        "zendesk_subdomain": "test",
        "zendesk_api_token": "test-token",
        "enable_salesforce_integration": False,
        "ticket_auto_assignment": False,
        "priority_auto_classification": False,
        "sentiment_analysis": False,
        "ai_response_suggestions": False,
        "sla_monitoring": False,
        "escalation_rules": False,
        "customer_journey_tracking": False,
        "enable_enterprise_features": False,
    }


class TestQuickBooksIntegrationService:
    async def test_initialize_returns_true(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        service._test_quickbooks_connection = AsyncMock(return_value={"ok": True})
        assert await service.initialize() is True

    async def test_create_invoice_success(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"Invoice": {"Id": "inv-1", "TotalAmt": 100.0}}
        with patch(
            "integrations.atom_quickbooks_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = fake_response
            result = await service.create_invoice(
                {"amount": 100.0, "customer_id": "cust-1", "description": "test"}
            )
        assert result["success"] is True
        assert result["invoice_id"] == "inv-1"

    async def test_create_invoice_api_error(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        fake_response = MagicMock()
        fake_response.status_code = 400
        fake_response.text = "bad request"
        with patch(
            "integrations.atom_quickbooks_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = fake_response
            result = await service.create_invoice({"amount": 100.0, "customer_id": "c"})
        assert result["success"] is False
        assert "400" in result["error"]

    async def test_create_invoice_exception_is_contained(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        with patch(
            "integrations.atom_quickbooks_integration_service.httpx.AsyncClient",
            side_effect=RuntimeError("boom"),
        ):
            result = await service.create_invoice({"amount": 1.0, "customer_id": "c"})
        assert result["success"] is False

    async def test_create_payment_success(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"Payment": {"Id": "pay-1"}}
        with patch(
            "integrations.atom_quickbooks_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = fake_response
            result = await service.create_payment(
                {"amount": 50.0, "customer_id": "cust-1", "payment_method": "card"}
            )
        assert result["success"] is True

    async def test_create_expense_success(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"Purchase": {"Id": "exp-1"}}
        with patch(
            "integrations.atom_quickbooks_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = fake_response
            result = await service.create_expense(
                {"amount": 25.0, "vendor_id": "vend-1", "category": "Travel"}
            )
        assert result["success"] is True

    async def test_generate_financial_report(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"Rows": [{"Header": {"ColData": []}}]}
        with patch(
            "integrations.atom_quickbooks_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = fake_response
            result = await service.generate_financial_report(
                "P&L",
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
            )
        assert "success" in result or "report" in result

    async def test_get_service_status(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        result = await service.get_service_status()
        assert "status" in result

    async def test_close(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        assert await service.close() is None

    async def test_enterprise_features_key_present(self):
        module = importlib.import_module("integrations.atom_quickbooks_integration_service")
        service = module.AtomQuickBooksIntegrationService(config=_qb_config())
        assert service.quickbooks_config["enable_enterprise_features"] is False


class TestEnterpriseSecurityService:
    async def test_initialize(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        service._initialize_encryption = AsyncMock()
        service._load_security_policies = AsyncMock()
        service._initialize_threat_detection = AsyncMock()
        service._start_security_monitoring = AsyncMock()
        service._initialize_compliance_monitoring = AsyncMock()
        assert await service.initialize() is True

    async def test_initialize_failure(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        service._initialize_encryption = AsyncMock(side_effect=RuntimeError("no crypto"))
        assert await service.initialize() is False

    async def test_create_security_policy(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        policy_data = {
            "name": "Test Policy",
            "description": "test policy",
            "security_level": "enterprise",
            "compliance_standards": ["soc2"],
            "rules": [{"name": "rule1", "action": "block"}],
            "enforcement_actions": [{"type": "block"}],
            "exceptions": [],
        }
        result = await service.create_security_policy(policy_data, "user-1")
        assert result["ok"] is True
        assert result["policy"]["name"] == "Test Policy"

    async def test_create_security_policy_invalid_level(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        policy_data = {
            "name": "Bad",
            "description": "d",
            "security_level": "not-a-level",
            "compliance_standards": ["soc2"],
            "rules": [],
            "enforcement_actions": [],
        }
        result = await service.create_security_policy(policy_data, "user-1")
        assert result["ok"] is False

    async def test_detect_threat_no_threats(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        service._pattern_based_detection = AsyncMock(return_value=[])
        service._behavioral_anomaly_detection = AsyncMock(return_value=[])
        service._ai_threat_detection = AsyncMock(return_value=[])
        result = await service.detect_threat({"event_type": "login", "user_id": "u1"})
        assert result is None

    async def test_detect_threat_high_severity_mitigated(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        threat_info = {
            "type": "sql_injection",
            "severity": "high",
            "confidence": 0.9,
            "description": "bad ip",
            "indicators": ["1.2.3.4"],
        }
        service._pattern_based_detection = AsyncMock(return_value=[threat_info])
        service._behavioral_anomaly_detection = AsyncMock(return_value=[])
        service._ai_threat_detection = AsyncMock(return_value=[])
        service._mitigate_threat = AsyncMock()
        result = await service.detect_threat({"event_type": "login", "source_ip": "1.2.3.4"})
        assert result is not None
        service._mitigate_threat.assert_awaited_once()

    async def test_audit_event(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        result = await service.audit_event({
            "event_type": "user_login",
            "user_id": "u1",
            "resource": "test_resource",
            "action": "login",
            "result": "success",
            "ip_address": "127.0.0.1",
        })
        assert result is not None

    async def test_check_compliance(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        result = await service.check_compliance(module.ComplianceStandard.SOC2)
        assert result is not None
        assert result.overall_score >= 0

    async def test_encrypt_and_decrypt_data(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        encrypted = await service.encrypt_data("secret-value", {"user_id": "u1"})
        assert isinstance(encrypted, str)
        decrypted, context = await service.decrypt_data(encrypted)
        assert decrypted == "secret-value"
        assert context["user_id"] == "u1"

    async def test_get_security_metrics(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        result = await service.get_security_metrics()
        assert "total_threats_detected" in result

    async def test_validate_password(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        result = await service.validate_password("Str0ng!Pass1", {"user_id": "u1"})
        assert "valid" in result

    async def test_close(self):
        module = importlib.import_module("integrations.atom_enterprise_security_service")
        service = module.AtomEnterpriseSecurityService()
        assert await service.close() is None


class TestEnterpriseUnifiedService:
    def _workflow_data(self):
        return {
            "name": "WF1",
            "description": "test workflow",
            "service_type": "security",
            "security_level": "confidential",
            "compliance_standards": ["SOC2"],
            "triggers": [{"type": "event", "event_type": "login"}],
            "steps": [{"action": "api_call", "service": "test", "params": {}}],
            "actions": [{"type": "notify"}],
            "metadata": {},
        }

    async def test_create_enterprise_workflow(self):
        module = importlib.import_module("integrations.atom_enterprise_unified_service")
        service = module.AtomEnterpriseUnifiedService()
        result = await service.create_enterprise_workflow(self._workflow_data(), "user-1")
        assert result["ok"] is True
        assert result["workflow"]["name"] == "WF1"

    async def test_create_enterprise_workflow_missing_fields(self):
        module = importlib.import_module("integrations.atom_enterprise_unified_service")
        service = module.AtomEnterpriseUnifiedService()
        result = await service.create_enterprise_workflow({"name": "X"}, "user-1")
        assert result["ok"] is False

    async def test_get_enterprise_workflows(self):
        module = importlib.import_module("integrations.atom_enterprise_unified_service")
        service = module.AtomEnterpriseUnifiedService()
        result = await service.get_enterprise_workflows("user-1")
        assert isinstance(result, list)

    async def test_get_enterprise_metrics(self):
        module = importlib.import_module("integrations.atom_enterprise_unified_service")
        service = module.AtomEnterpriseUnifiedService()
        result = await service.get_enterprise_metrics()
        assert "total_workflows" in result

    async def test_close(self):
        module = importlib.import_module("integrations.atom_enterprise_unified_service")
        service = module.AtomEnterpriseUnifiedService()
        assert await service.close() is None


class TestVideoAiService:
    def _make_request(self, module, task_type):
        return module.VideoRequest(
            request_id="r1",
            task_type=task_type,
            model_type=module.VideoModelType.BLIP,
            video_path="test.mp4",
            video_data=None,
            format=module.VideoFormat.MP4,
            resolution=module.VideoResolution.HD_720P,
            duration=10.0,
            fps=30.0,
            platform="test",
            user_id="u1",
            metadata={},
        )

    async def test_process_video_request_summarization(self):
        module = importlib.import_module("integrations.atom_video_ai_service")
        service = module.AtomVideoAIService()
        request = self._make_request(module, module.VideoTaskType.SUMMARIZATION)
        service._preprocess_video = AsyncMock(return_value=b"data")
        service._summarize_video = AsyncMock(
            return_value=module.VideoResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                success=True,
                text="summary done",
                confidence=0.9,
                content_analysis=None,
                objects_detected=None,
                faces_detected=None,
                scenes_detected=None,
                speakers_detected=None,
                video_class=None,
                content_rating=None,
                quality_score=None,
                timestamp=datetime.now(timezone.utc),
                processing_time=1.0,
                metadata={},
            )
        )
        response = await service.process_video_request(request)
        assert response is not None
        assert response.success is True

    async def test_process_video_request_unsupported(self):
        module = importlib.import_module("integrations.atom_video_ai_service")
        service = module.AtomVideoAIService()
        request = self._make_request(module, module.VideoTaskType.SUMMARIZATION)
        request.task_type = "UNKNOWN_TYPE"
        service._preprocess_video = AsyncMock(return_value=b"data")
        response = await service.process_video_request(request)
        assert response.success is False

    async def test_initialize(self):
        module = importlib.import_module("integrations.atom_video_ai_service")
        service = module.AtomVideoAIService()
        service._load_video_models = AsyncMock(return_value=True)
        assert await service.initialize() is True

    async def test_get_service_status(self):
        module = importlib.import_module("integrations.atom_video_ai_service")
        service = module.AtomVideoAIService()
        result = await service.get_service_status()
        assert "status" in result or "success" in result

    async def test_close(self):
        module = importlib.import_module("integrations.atom_video_ai_service")
        service = module.AtomVideoAIService()
        assert await service.close() is None


class TestVoiceAiService:
    def _make_request(self, module):
        return module.VoiceRequest(
            request_id="r1",
            task_type=module.VoiceTaskType.TRANSCRIPTION,
            model_type=module.VoiceModelType.WHISPER,
            language=module.VoiceLanguage.ENGLISH,
            audio_path="test.wav",
            audio_data=None,
            format=module.VoiceFormat.WAV,
            sample_rate=16000,
            duration=5.0,
            platform="test",
            user_id="u1",
            metadata={},
        )

    async def test_process_voice_request(self):
        module = importlib.import_module("integrations.atom_voice_ai_service")
        service = module.AtomVoiceAIService()
        request = self._make_request(module)
        service._preprocess_audio = AsyncMock(return_value=b"data")
        service._transcribe_audio = AsyncMock(
            return_value=module.VoiceResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                success=True,
                text="transcribed text",
                confidence=0.95,
                language=None,
                sentiment=None,
                emotion=None,
                speaker_id=None,
                translation=None,
                timestamp=datetime.now(timezone.utc),
                processing_time=0.5,
                metadata={},
            )
        )
        response = await service.process_voice_request(request)
        assert response is not None
        assert response.success is True

    async def test_initialize(self):
        module = importlib.import_module("integrations.atom_voice_ai_service")
        service = module.AtomVoiceAIService()
        service._load_voice_models = AsyncMock(return_value=True)
        assert await service.initialize() is True

    async def test_get_service_status(self):
        module = importlib.import_module("integrations.atom_voice_ai_service")
        service = module.AtomVoiceAIService()
        result = await service.get_service_status()
        assert "status" in result or "success" in result

    async def test_close(self):
        module = importlib.import_module("integrations.atom_voice_ai_service")
        service = module.AtomVoiceAIService()
        assert await service.close() is None


class TestWorkflowAutomationService:
    def _automation_data(self):
        return {
            "name": "Auto1",
            "description": "test automation",
            "automation_type": "security",
            "priority": "high",
            "conditions": [{"type": "event_triggered", "event_type": "login"}],
            "actions": [{"type": "notify", "config": {"channel": "slack"}}],
            "security_policy": {"level": "confidential"},
            "compliance_requirements": [],
        }

    async def test_create_automation(self):
        module = importlib.import_module("integrations.atom_workflow_automation_service")
        service = module.AtomWorkflowAutomationService()
        result = await service.create_automation(self._automation_data(), "user-1")
        assert result["ok"] is True

    async def test_create_automation_validation_failure(self):
        module = importlib.import_module("integrations.atom_workflow_automation_service")
        service = module.AtomWorkflowAutomationService()
        result = await service.create_automation({"name": "X"}, "user-1")
        assert result["ok"] is False
        assert "validation" in result.get("error", "").lower()

    async def test_get_automations(self):
        module = importlib.import_module("integrations.atom_workflow_automation_service")
        service = module.AtomWorkflowAutomationService()
        result = await service.get_automations("user-1")
        assert isinstance(result, list)

    async def test_get_automation_metrics(self):
        module = importlib.import_module("integrations.atom_workflow_automation_service")
        service = module.AtomWorkflowAutomationService()
        result = await service.get_automation_metrics()
        assert "total_automations" in result

    async def test_close(self):
        module = importlib.import_module("integrations.atom_workflow_automation_service")
        service = module.AtomWorkflowAutomationService()
        assert await service.close() is None


class TestZendeskIntegrationService:
    async def test_create_ticket_success(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        ticket_data = {
            "subject": "Help",
            "description": "Need help",
            "requester_name": "Alice",
            "requester_email": "alice@example.com",
        }
        fake_response = MagicMock()
        fake_response.status_code = 201
        fake_response.json.return_value = {"ticket": {"id": "t-1"}}
        with patch(
            "integrations.atom_zendesk_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = fake_response
            result = await service.create_ticket(ticket_data, platform=None)
        assert result["success"] is True
        assert result["ticket_id"] == "t-1"

    async def test_create_ticket_api_error(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        fake_response = MagicMock()
        fake_response.status_code = 401
        fake_response.text = "unauthorized"
        with patch(
            "integrations.atom_zendesk_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = fake_response
            result = await service.create_ticket({"subject": "x", "description": "d"}, platform=None)
        assert result["success"] is False

    async def test_create_ticket_exception_is_contained(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        with patch(
            "integrations.atom_zendesk_integration_service.httpx.AsyncClient",
            side_effect=RuntimeError("boom"),
        ):
            result = await service.create_ticket({"subject": "x", "description": "d"}, platform=None)
        assert result["success"] is False

    async def test_update_ticket_success(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        service._get_ticket = AsyncMock(return_value={"id": "t-1", "tags": []})
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"ticket": {"id": "t-1"}}
        with patch(
            "integrations.atom_zendesk_integration_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.put.return_value = fake_response
            result = await service.update_ticket("t-1", {"status": "open"})
        assert result["success"] is True

    async def test_update_ticket_not_found(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        service._get_ticket = AsyncMock(return_value=None)
        result = await service.update_ticket("t-99", {"status": "open"})
        assert result["success"] is False

    async def test_get_service_status(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        result = await service.get_service_status()
        assert "status" in result or "success" in result

    async def test_initialize(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        service._test_zendesk_connection = AsyncMock(return_value={"ok": True})
        assert await service.initialize() is True

    async def test_initialize_connection_failure(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        service._test_zendesk_connection = AsyncMock(side_effect=RuntimeError("api down"))
        assert await service.initialize() is False

    async def test_enterprise_features_key_present(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        assert service.zendesk_config["enable_enterprise_features"] is False

    async def test_close(self):
        module = importlib.import_module("integrations.atom_zendesk_integration_service")
        service = module.AtomZendeskIntegrationService(config=_zd_config())
        assert await service.close() is None
