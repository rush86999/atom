"""TDD bug-hunt tests for backend/integrations core services.

RED->GREEN: each test asserts the CORRECT behavior for a real bug found in
source review. Run before fixes to confirm RED, then after to confirm GREEN.
"""
import asyncio
import importlib
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# universal_integration_service.py
# ---------------------------------------------------------------------------
class TestUniversalBudgetGuard:
    async def test_execute_returns_success_when_budget_service_missing(self):
        """core.budget_service does NOT exist (guarded import -> None). The
        success path must not crash on the None budget_service (AttributeError
        was caught and converted into a false 'error' status for EVERY call)."""
        import integrations.universal_integration_service as mod

        with patch.object(mod, "budget_service", None):
            with patch("core.database.SessionLocal") as session_cls, patch(
            "core.integration_registry.IntegrationRegistry"
        ) as reg_cls:
                session_cls.return_value.__enter__.return_value = MagicMock()
                instance = MagicMock()
                instance.access_token = "tok"
                instance.get_contacts = AsyncMock(return_value=[{"id": "1"}])
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=instance)
                result = await mod.UniversalIntegrationService().execute(
                    "hubspot",
                    "list",
                    {"entity": "contact"},
                    context={"user_id": "u1", "tenant_id": "t1"},
                )
        assert result["status"] == "success"
        assert result["data"] == [{"id": "1"}]

    async def test_execute_error_path_does_not_crash_when_budget_service_missing(self):
        import integrations.universal_integration_service as mod

        with patch.object(mod, "budget_service", None):
            with patch("core.database.SessionLocal") as session_cls, patch(
                "core.integration_registry.IntegrationRegistry"
            ) as reg_cls:
                session_cls.return_value.__enter__.return_value = MagicMock()
                reg_cls.return_value.get_service_instance = AsyncMock(
                    side_effect=RuntimeError("boom")
                )
                result = await mod.UniversalIntegrationService().execute(
                    "hubspot",
                    "list",
                    {"entity": "contact"},
                    context={"user_id": "u1", "tenant_id": "t1"},
                )
        assert result["status"] == "error"
        assert "boom" in result["error"]


class TestUniversalOsImport:
    async def test_hubspot_execute_uses_os_env_fallback_without_nameerror(self):
        """os is not imported in the module; the `or os.getenv(...)` fallback in
        _execute_hubspot/_search_hubspot raised NameError whenever the service
        instance carried no access_token."""
        import integrations.universal_integration_service as mod

        with patch("core.database.SessionLocal") as session_cls, patch(
            "core.integration_registry.IntegrationRegistry"
        ) as reg_cls:
            session_cls.return_value.__enter__.return_value = MagicMock()
            instance = MagicMock()
            instance.access_token = None
            instance.get_contacts = AsyncMock(return_value=[{"id": "1"}])
            reg_cls.return_value.get_service_instance = AsyncMock(return_value=instance)
            with patch("integrations.universal_integration_service.os.getenv") as getenv:
                getenv.return_value = "env-token"
                result = await mod.UniversalIntegrationService().execute(
                    "hubspot",
                    "list",
                    {"entity": "contact"},
                    context={"user_id": "u1", "tenant_id": "t1"},
                )
        assert result["status"] == "success"


class TestUniversalShopifyImport:
    async def test_shopify_execute_resolves_service_without_nameerror(self):
        """ShopifyService was never imported in this module -> NameError on
        every shopify dispatch."""
        import integrations.universal_integration_service as mod

        with patch("core.database.SessionLocal") as session_cls, patch(
            "core.integration_registry.IntegrationRegistry"
        ) as reg_cls, patch(
            "integrations.universal_integration_service.ShopifyService"
        ) as shopify_cls:
            session_cls.return_value.__enter__.return_value = MagicMock()
            instance = MagicMock()
            instance.get_products = AsyncMock(return_value=[{"id": 1}])
            reg_cls.return_value.get_service_instance = AsyncMock(return_value=instance)
            shopify_cls.return_value = instance
            result = await mod.UniversalIntegrationService().execute(
                "shopify",
                "list",
                {"entity": "product", "access_token": "tok", "shop": "myshop.myshopify.com"},
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert result["status"] == "success"
        assert result["data"] == [{"id": 1}]


class TestUniversalAwsSesKwargs:
    async def test_aws_ses_send_email_does_not_duplicate_from_email(self):
        """send_email(from_email, ..., from_email=...) -> TypeError on every
        aws_ses send_email action."""
        import integrations.universal_integration_service as mod

        with patch("core.database.SessionLocal") as session_cls, patch(
            "core.integration_registry.IntegrationRegistry"
        ) as reg_cls:
            session_cls.return_value.__enter__.return_value = MagicMock()
            instance = MagicMock()
            instance.send_email = AsyncMock(return_value={"MessageId": "m1"})
            reg_cls.return_value.get_service_instance = AsyncMock(return_value=instance)
            result = await mod.UniversalIntegrationService().execute(
                "aws_ses",
                "send_email",
                {"to": ["a@b.c"], "subject": "hi", "text_body": "x"},
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# atom_workflow_automation_service.py
# ---------------------------------------------------------------------------
def _wf_config():
    return {
        "database": AsyncMock(),
        "cache": None,
        "security_service": None,
        "unified_service": None,
        "ai_service": None,
    }


class TestWorkflowAutomationWorkspaceId:
    async def test_execute_automation_with_agent_trigger_does_not_attributeerror(self):
        """self.workspace_id was never assigned in __init__ -> AttributeError
        in execute_automation for agent-trigger actions (silently returned as
        error via the outer except)."""
        import integrations.atom_workflow_automation_service as mod

        svc = mod.AtomWorkflowAutomationService("t1", _wf_config())
        automation = mod.WorkflowAutomation(
            automation_id="auto_1",
            name="n",
            description="d",
            automation_type=mod.WorkflowAutomationType.SECURITY,
            priority=mod.AutomationPriority.HIGH,
            status=mod.AutomationStatus.ACTIVE,
            conditions=[],
            actions=[{"type": "agent_trigger", "config": {"agent_id": "ag1"}}],
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
        svc.automations["auto_1"] = automation
        with patch.object(
            mod, "circuit_breaker"
        ) as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            cb.record_success = AsyncMock()
            with patch.object(mod, "rate_limiter") as rl:
                rl.is_rate_limited = AsyncMock(return_value=(False, 10))
                with patch(
                    "core.trigger_interceptor.TriggerInterceptor"
                ) as ti:
                    ti.return_value.intercept_trigger = AsyncMock(
                        side_effect=ValueError("agent not found")
                    )
                    result = await svc.execute_automation(
                        "auto_1", {"k": "v"}, "test"
                    )
        # Backward-compat: ValueError from maturity check must not abort the run.
        assert result["ok"] is True


class TestWorkflowAutomationLoad:
    async def test_load_automations_accepts_db_row_shape(self):
        """_load_automations constructed WorkflowAutomation with nonexistent
        kwargs (type=/next_run=/last_run=/last_execution_status=) -> TypeError
        on every DB-backed load."""
        import integrations.atom_workflow_automation_service as mod

        db = MagicMock()
        row = (
            "auto_1", "name", "desc", "security", "[]", "[]",
            "high", "active", True, "u1",
            "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
            "0 2 * * *", "2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
            5, 4, 1, "completed", "{}",
        )
        db.execute.return_value = [row]
        svc = mod.AtomWorkflowAutomationService("t1", {"database": db})
        ok = await svc._load_automations()
        assert ok is True
        assert "auto_1" in svc.automations
        assert svc.automations["auto_1"].automation_type == mod.WorkflowAutomationType.SECURITY


class TestWorkflowAutomationMonitoring:
    async def test_monitoring_loop_survives_automations_without_last_execution_status(self):
        import integrations.atom_workflow_automation_service as mod

        svc = mod.AtomWorkflowAutomationService("t1", _wf_config())
        automation = mod.WorkflowAutomation(
            automation_id="auto_1",
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
            execution_count=2,
            success_count=1,
            failure_count=1,
            timeout=60,
            retry_policy={},
            notification_rules=[],
            metadata={},
            audit_trail=[],
        )
        svc.automations["auto_1"] = automation
        with patch.object(mod.asyncio, "sleep", new=AsyncMock(side_effect=RuntimeError("stop"))):
            with pytest.raises(RuntimeError):
                await svc._monitoring_loop()
        assert svc.automation_metrics["total_automations"] == 1


class TestWorkflowAutomationNotifications:
    async def test_notifications_use_existing_notify_methods(self):
        """_send_automation_notifications called nonexistent _notify_via_slack/
        _notify_via_email/_notify_via_teams -> AttributeError on every failed
        automation and every rule-driven notification."""
        import integrations.atom_workflow_automation_service as mod

        svc = mod.AtomWorkflowAutomationService("t1", _wf_config())
        automation = mod.WorkflowAutomation(
            automation_id="auto_1",
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
            execution_count=1,
            success_count=0,
            failure_count=1,
            timeout=60,
            retry_policy={},
            notification_rules=[
                {"status": "failed", "channels": ["slack:ops", "email:admin", "teams:sec"]}
            ],
            metadata={},
            audit_trail=[],
        )
        execution = mod.AutomationExecution(
            execution_id="exec_1",
            automation_id="auto_1",
            triggered_by="t",
            trigger_context={},
            status=mod.AutomationStatus.FAILED,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            execution_time=1.0,
            result={},
            error="oops",
            actions_executed=[],
            notifications_sent=[],
            compliance_checks=[],
            security_checks=[],
            metadata={},
        )
        ok = await svc._send_automation_notifications(automation, execution)
        assert ok is True


# ---------------------------------------------------------------------------
# atom_enterprise_unified_service.py
# ---------------------------------------------------------------------------
class TestEnterpriseUnifiedAutomationType:
    async def test_handle_security_event_works_for_created_automation(self):
        """automation_config stored by create_security_automation lacked the
        'automation_type' key -> KeyError in handle_security_event (returned as
        error instead of executing)."""
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc.security_service.audit_event = AsyncMock()
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch.object(mod, "rate_limiter") as rl:
                rl.is_rate_limited = AsyncMock(return_value=(False, 10))
                with patch.object(
                    svc, "create_enterprise_workflow", new=AsyncMock(
                        return_value={"ok": True, "workflow_id": "enterprise_wf_1"}
                    )
                ):
                    created = await svc.create_security_automation(
                        {
                            "name": "malware response",
                            "description": "d",
                            "threat_types": ["malware"],
                            "severity_levels": ["high"],
                        },
                        "u1",
                    )
        assert created["ok"] is True
        automation = svc.active_automations[created["automation_id"]]
        assert automation["automation_type"] == "security"
        with patch.object(mod, "circuit_breaker") as cb2:
            cb2.is_enabled = AsyncMock(return_value=True)
            cb2.record_failure = AsyncMock()
            with patch.object(mod, "rate_limiter") as rl2:
                rl2.is_rate_limited = AsyncMock(return_value=(False, 10))
                with patch.object(
                    svc, "_get_security_ai_analysis", new=AsyncMock(return_value={})
                ):
                    with patch.object(
                        svc, "execute_enterprise_workflow", new=AsyncMock(
                            return_value={"ok": True}
                        )
                    ):
                        result = await svc.handle_security_event(
                            {"threat_type": "malware", "severity": "high"}
                        )
        assert result["ok"] is True
        assert result["relevant_automations"] == 1


class TestEnterpriseUnifiedCompliance:
    async def test_handle_compliance_violation_runs_matching_automation(self):
        """Reused loop variable `automation_id` from a previous loop (NameError
        when empty / wrong workflow id otherwise) + .value crash on string
        compliance_standard."""
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc.security_service.audit_event = AsyncMock()
        automation = mod.ComplianceAutomation(
            automation_id="comp_1",
            compliance_standard="SOC2",
            workflow_type=mod.ComplianceWorkflowType.AUDIT_REMEDIATION,
            triggers=[mod.AutomationTriggerType.AUDIT_FAILURE],
            actions=[],
            schedule="daily",
            approval_required=True,
            escalation_rules=[],
            reporting_frequency="weekly",
            artifact_generation=[],
            audit_requirements=[],
        )
        svc.compliance_automations["comp_1"] = automation
        workflow = mod.EnterpriseWorkflow(
            workflow_id="enterprise_wf_1",
            name="w",
            description="d",
            service_type=mod.EnterpriseServiceType.COMPLIANCE,
            security_level=mod.WorkflowSecurityLevel.CONFIDENTIAL,
            compliance_standards=["SOC2"],
            triggers=[],
            steps=[],
            actions=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="u",
            status="active",
            metadata={"automation_id": "comp_1"},
            audit_trail=[],
            compliance_checks=[],
        )
        svc.enterprise_workflows["enterprise_wf_1"] = workflow
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch.object(mod, "rate_limiter") as rl:
                rl.is_rate_limited = AsyncMock(return_value=(False, 10))
                with patch.object(
                    svc, "_get_compliance_ai_analysis", new=AsyncMock(return_value={})
                ):
                    with patch.object(
                        svc, "execute_enterprise_workflow", new=AsyncMock(
                            return_value={"ok": True, "execution_results": []}
                        )
                    ) as exec_wf:
                        result = await svc.handle_compliance_violation(
                            {"standard": "SOC2", "violation_type": "x"}
                        )
        assert result["ok"] is True
        assert result["relevant_automations"] == 1
        assert exec_wf.call_args.kwargs["workflow_id"] == "enterprise_wf_1"

    async def test_handle_compliance_violation_with_no_matching_automation(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc.security_service.audit_event = AsyncMock()
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch.object(mod, "rate_limiter") as rl:
                rl.is_rate_limited = AsyncMock(return_value=(False, 10))
                with patch.object(
                    svc, "_get_compliance_ai_analysis", new=AsyncMock(return_value={})
                ):
                    result = await svc.handle_compliance_violation(
                        {"standard": "GDPR", "violation_type": "x"}
                    )
        assert result["ok"] is True
        assert result["relevant_automations"] == 0


class TestEnterpriseUnifiedHandlers:
    async def test_security_alert_handler_uses_workflow_id_not_id(self):
        """_handle_security_alert used workflow.id (AttributeError -
        EnterpriseWorkflow has workflow_id), so alerts were never handled."""
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        svc.security_service = MagicMock()
        workflow = mod.EnterpriseWorkflow(
            workflow_id="wf_1",
            name="w",
            description="d",
            service_type=mod.EnterpriseServiceType.SECURITY,
            security_level=mod.WorkflowSecurityLevel.RESTRICTED,
            compliance_standards=["SOC2"],
            triggers=[],
            steps=[],
            actions=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="u",
            status="active",
            metadata={},
            audit_trail=[],
            compliance_checks=[],
        )
        svc.enterprise_workflows["wf_1"] = workflow
        with patch.object(svc.security_service, "log_security_alert", new=AsyncMock()) as log:
            await svc._handle_security_alert(
                {"severity": "high", "type": "malware"}, workflow, {"id": "s1"}, "u1"
            )
        assert log.call_args.kwargs["workflow_id"] == "wf_1"
        assert workflow.status == "blocked"

    async def test_compliance_violation_handler_uses_workflow_id(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        svc.security_service = MagicMock()
        workflow = mod.EnterpriseWorkflow(
            workflow_id="wf_2",
            name="w",
            description="d",
            service_type=mod.EnterpriseServiceType.COMPLIANCE,
            security_level=mod.WorkflowSecurityLevel.CONFIDENTIAL,
            compliance_standards=["GDPR"],
            triggers=[],
            steps=[],
            actions=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="u",
            status="active",
            metadata={},
            audit_trail=[],
            compliance_checks=[],
        )
        svc.enterprise_workflows["wf_2"] = workflow
        with patch.object(svc.security_service, "log_compliance_violation", new=AsyncMock()) as log:
            await svc._handle_compliance_violation(
                {"severity": "high", "type": "gdpr"}, workflow, {"id": "s1"}, "u1"
            )
        assert log.call_args.kwargs["workflow_id"] == "wf_2"
        assert workflow.status == "blocked"


# ---------------------------------------------------------------------------
# module-level singleton config (all three enterprise services)
# ---------------------------------------------------------------------------
class TestSingletonConfig:
    def test_workflow_automation_singleton_keeps_config(self):
        """AtomWorkflowAutomationService({...}) passed the config dict as the
        positional tenant_id -> config kwarg never supplied -> singleton lost
        every config value."""
        import integrations.atom_workflow_automation_service as mod

        svc = mod.atom_workflow_automation_service
        assert svc is not None
        assert "database" in svc.config
        assert "security_service" in svc.config

    def test_enterprise_unified_singleton_keeps_config(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.atom_enterprise_unified_service
        assert "database" in svc.config
        assert "workflow_service" in svc.config

    def test_enterprise_security_singleton_keeps_config(self):
        import integrations.atom_enterprise_security_service as mod

        svc = mod.atom_enterprise_security_service
        assert "database" in svc.config
        assert "encryption_key" in svc.config


class TestMcpNoDeadDuplicateBranches:
    def test_duplicated_tool_handlers_removed(self):
        """execute_tool had unreachable duplicated elif branches for
        trigger_workflow / finance_close_check / whatsapp_send_message (a
        later identical elif can never run). Removing them eliminates dead
        code that silently shadowed the second implementation."""
        import integrations.mcp_service as mod

        src = open(mod.__file__).read()
        assert src.count('tool_name == "trigger_workflow"') == 1
        assert src.count('tool_name == "finance_close_check"') == 1
        assert src.count('tool_name == "whatsapp_send_message"') == 1


class TestMcpRegisterSessionClose:
    async def test_register_integration_tools_closes_created_session(self):
        """finally: `if not db: db.close()` was inverted — a session created by
        the method itself was NEVER closed (leak), while the comment promised
        exactly the opposite."""
        import integrations.mcp_service as mod

        svc = mod.MCPService.__new__(mod.MCPService)
        svc.initialized = True
        svc.active_servers = {}
        svc.config = {}
        db = MagicMock()
        with patch.object(mod, "SessionLocal", return_value=db), \
             patch("core.models.TenantIntegration", new=MagicMock()), \
             patch("core.integration_registry.IntegrationRegistry") as reg_cls:
            db.query.return_value.filter.return_value.all.return_value = []
            reg_cls.return_value.get_service_instance = AsyncMock(return_value=None)
            await svc.register_integration_tools("tenant1")
        db.close.assert_called_once()


class TestMcpIngestionKwarg:
    async def test_ingest_knowledge_passes_workspace_id_not_tenant_id(self):
        """KnowledgeIngestionManager.process_document takes workspace_id;
        mcp_service passed tenant_id= -> TypeError on every ingest call."""
        import integrations.mcp_service as mod

        svc = mod.MCPService.__new__(mod.MCPService)
        svc.initialized = True
        svc.active_servers = {}
        svc.config = {}
        ing = MagicMock()
        ing.process_document = AsyncMock(return_value={"ok": 1})
        with patch.dict(sys.modules, {
            "core.knowledge_ingestion": MagicMock(get_knowledge_ingestion=lambda: ing),
        }), patch("integrations.mcp_service.get_tool_registry") as _reg:
            _reg.return_value.get.return_value = False
            r = await svc.execute_tool(
                "local-tools", "ingest_knowledge_from_text",
                {"text": "hello"}, {"workspace_id": "w", "user_id": "u"},
            )
        assert r == {"success": True, "stats": {"ok": 1}}
        assert "workspace_id" in ing.process_document.call_args.kwargs
        assert "tenant_id" not in ing.process_document.call_args.kwargs


# ---------------------------------------------------------------------------
# mcp_service.py
# ---------------------------------------------------------------------------
class TestMcpExecuteIntegrationTool:
    async def test_execute_integration_tool_routes_to_real_service(self):
        """core.entity_skill_executor is a phantom module (never existed).
        execute_integration_tool always returned
        {'status':'error','error':'No module named core.entity_skill_executor'}.
        It must delegate to the real UniversalIntegrationService."""
        import integrations.mcp_service as mod

        svc = mod.MCPService.__new__(mod.MCPService)
        svc.initialized = True
        svc.active_servers = {}
        svc.config = {}
        with patch(
            "integrations.universal_integration_service.UniversalIntegrationService.execute",
            new=AsyncMock(return_value={"status": "success", "data": [1]}),
        ) as exec_mock:
            result = await svc.execute_integration_tool(
                "salesforce_list",
                {"entity": "contact"},
                {"tenant_id": "t1", "agent_id": "ag1", "user_id": "u1"},
            )
        assert result["status"] == "success"
        assert exec_mock.call_args.args[0] == "salesforce"
        assert exec_mock.call_args.args[1] == "list"

    async def test_execute_integration_tool_requires_tenant_and_agent(self):
        import integrations.mcp_service as mod

        svc = mod.MCPService.__new__(mod.MCPService)
        svc.initialized = True
        result = await svc.execute_integration_tool(
            "salesforce_list", {}, {}
        )
        assert result["status"] == "error"
        assert "tenant_id and agent_id" in result["error"]
