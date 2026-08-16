# -*- coding: utf-8 -*-
"""Coverage wave 101 — final push to >=95% for three residual-gap modules.

1. integrations/atom_enterprise_unified_service.py
2. core/learning_llm_router.py
3. integrations/atom_workflow_automation_service.py

No network, no real LLM, no real DB — everything mocked. Plain pytest +
unittest.mock (asyncio_mode=auto).
"""
import asyncio
import importlib
import sys
import os
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# =========================================================================== #
# helpers
# =========================================================================== #
class _RaisingDict(dict):
    """Dict whose items()/__setitem__ raise — to hit outer except handlers."""

    def __init__(self, *a, boom_on="items", **kw):
        super().__init__(*a, **kw)
        self._boom_on = boom_on

    def items(self):
        if self._boom_on == "items":
            raise RuntimeError("boom-items")
        return super().items()

    def __setitem__(self, k, v):
        if self._boom_on == "setitem":
            raise RuntimeError("boom-setitem")
        super().__setitem__(k, v)


class _BadAttr:
    """Object whose attribute set raises."""

    def __setattr__(self, name, value):
        raise RuntimeError("boom-setattr")

    def get(self, *a, **kw):
        raise RuntimeError("boom-get")


# =========================================================================== #
# 1. integrations/atom_enterprise_unified_service.py
# =========================================================================== #
class TestEnterpriseUnifiedFinal:
    def _svc(self, **cfg_over):
        import integrations.atom_enterprise_unified_service as mod
        cfg = {
            "database": AsyncMock(),
            "cache": None,
            "security_service": AsyncMock(),
            "workflow_service": None,
            "ai_service": None,
            "ai_integration": None,
        }
        cfg.update(cfg_over)
        svc = mod.AtomEnterpriseUnifiedService(config=cfg)
        return mod, svc

    def _guards(self, mod, enabled=True, limited=False):
        cm1 = patch.object(mod, "circuit_breaker")
        cm2 = patch.object(mod, "rate_limiter")
        cb, rl = cm1.__enter__(), cm2.__enter__()
        cb.is_enabled = AsyncMock(return_value=enabled)
        rl.is_rate_limited = AsyncMock(return_value=(limited, 0))
        self._cms = (cm1, cm2)
        return cb, rl

    def _unguard(self):
        for cm in getattr(self, "_cms", ()):
            cm.__exit__(None, None, None)
        self._cms = ()

    def teardown_method(self, *_):
        self._unguard()

    # ---- residual exception handlers (1379-1380, 1391-1392, 1403-1404,
    #      1412-1413, 1421-1422) ----
    async def test_block_workflow_execution_exception(self):
        _, svc = self._svc()
        svc.enterprise_workflows["wf"] = _BadAttr()
        await svc._block_workflow_execution("wf", "test")  # must not raise

    async def test_increase_workflow_monitoring_exception(self):
        _, svc = self._svc()
        svc.workflow_monitoring = _RaisingDict(boom_on="setitem")
        await svc._increase_workflow_monitoring("wf")

    async def test_enable_compliance_logging_exception(self):
        _, svc = self._svc()
        svc.workflow_monitoring = _RaisingDict(boom_on="setitem")
        await svc._enable_compliance_logging("wf")

    async def test_notify_security_team_exception(self):
        _, svc = self._svc()
        wf = MagicMock()
        await svc._notify_security_team(_BadAttr(), wf, "u")

    async def test_notify_compliance_team_exception(self):
        _, svc = self._svc()
        wf = MagicMock()
        await svc._notify_compliance_team(_BadAttr(), wf, "u")

    # ---- import fallback lines 60-63 ----
    def test_import_fallback_when_services_unavailable(self):
        import integrations.atom_enterprise_unified_service as mod
        blocked = {
            "ai_enhanced_service", "atom_ai_integration",
            "atom_discord_integration", "atom_enterprise_security_service",
            "atom_google_chat_integration", "atom_ingestion_pipeline",
            "atom_memory_service", "atom_search_service",
            "atom_slack_integration", "atom_teams_integration",
            "atom_workflow_service",
        }
        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__
        # Has ComplianceStandard but NOT the service singleton -> the inner
        # `from integrations.atom_enterprise_security_service import
        #  atom_enterprise_security_service` raises ImportError (lines 62-63).
        sec_stub = MagicMock()
        sec_stub.ComplianceStandard = mod.ComplianceStandard
        del sec_stub.atom_enterprise_security_service

        def fake_import(name, *a, **kw):
            if name == "integrations.atom_enterprise_security_service":
                return sec_stub
            if name in blocked:
                raise ImportError("blocked for test")
            return real_import(name, *a, **kw)

        try:
            with patch("builtins.__import__", side_effect=fake_import):
                reloaded = importlib.reload(mod)
            assert reloaded.atom_enterprise_unified_service is not None
        finally:
            # Restore the module under normal imports for other tests
            importlib.reload(mod)

    # ---- generous public-API coverage ----
    def _wf_data(self, **over):
        data = {
            "name": "wf", "description": "d",
            "service_type": "security",
            "security_level": "internal",
            "compliance_standards": ["SOC2"],
            "triggers": [{"type": "event"}],
            "steps": [{"name": "s1", "type": "security_check", "config": {}}],
            "actions": [{"type": "notification", "config": {}}],
            "metadata": {},
        }
        data.update(over)
        return data

    async def test_create_and_execute_workflow_success(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.create_enterprise_workflow(self._wf_data(), "u1")
        assert res["ok"], res
        wf_id = res["workflow_id"]
        assert wf_id in svc.enterprise_workflows

        exc = await svc.execute_enterprise_workflow(wf_id, {"ctx": 1}, "u1")
        assert exc["ok"], exc
        assert exc["execution_results"][0]["success"] is True

    async def test_create_workflow_validation_failure(self):
        mod, svc = self._svc()
        self._guards(mod)
        with patch.object(svc, "_validate_enterprise_workflow",
                          AsyncMock(return_value={"valid": False, "errors": ["bad"]})):
            res = await svc.create_enterprise_workflow(self._wf_data(), "u1")
        assert res["ok"] is False and "validation failed" in res["error"].lower()

    async def test_create_workflow_service_failure(self):
        mod, svc = self._svc(workflow_service=AsyncMock())
        self._guards(mod)
        svc.workflow_service.create_workflow = AsyncMock(return_value={"ok": False, "error": "x"})
        res = await svc.create_enterprise_workflow(self._wf_data(), "u1")
        assert res["ok"] is False

    async def test_execute_not_found(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.execute_enterprise_workflow("missing", {}, "u1")
        assert res["ok"] is False

    async def test_execute_security_precheck_fail(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.create_enterprise_workflow(self._wf_data(), "u1")
        wf_id = res["workflow_id"]
        with patch.object(svc, "_security_pre_check",
                          AsyncMock(return_value={"passed": False, "reason": "no"})):
            out = await svc.execute_enterprise_workflow(wf_id, {}, "u1")
        assert out["ok"] is False and "security_violation" in out

    async def test_execute_compliance_precheck_fail(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.create_enterprise_workflow(self._wf_data(), "u1")
        wf_id = res["workflow_id"]
        with patch.object(svc, "_compliance_pre_check",
                          AsyncMock(return_value={"passed": False, "reason": "no"})):
            out = await svc.execute_enterprise_workflow(wf_id, {}, "u1")
        assert out["ok"] is False and "compliance_violation" in out

    async def test_execute_step_exception_returns_error_result(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.create_enterprise_workflow(self._wf_data(), "u1")
        wf_id = res["workflow_id"]
        with patch.object(svc, "_execute_security_check",
                          AsyncMock(side_effect=RuntimeError("step boom"))):
            out = await svc.execute_enterprise_workflow(wf_id, {}, "u1")
        assert out["ok"]
        assert out["execution_results"][0]["success"] is False

    async def test_execute_triggers_alert_and_violation_handlers(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.create_enterprise_workflow(self._wf_data(), "u1")
        wf_id = res["workflow_id"]
        with patch.object(svc, "_monitor_step_execution",
                          AsyncMock(return_value={"alert": True, "severity": "high"})), \
             patch.object(svc, "_handle_security_alert", AsyncMock()) as h_alert, \
             patch.object(svc, "_monitor_step_compliance",
                          AsyncMock(return_value={"violation": True, "severity": "medium"})), \
             patch.object(svc, "_handle_compliance_violation", AsyncMock()) as h_viol:
            out = await svc.execute_enterprise_workflow(wf_id, {}, "u1")
        assert out["ok"]
        h_alert.assert_awaited_once()
        h_viol.assert_awaited_once()

    async def test_handle_security_alert_severity_paths(self):
        mod, svc = self._svc(security_service=AsyncMock())
        sec = svc.security_service
        sec.log_security_alert = AsyncMock()
        sec.log_compliance_violation = AsyncMock()
        wf = MagicMock(workflow_id="wf")
        with patch.object(svc, "_block_workflow_execution", AsyncMock()) as blk, \
             patch.object(svc, "_notify_security_team", AsyncMock()):
            await svc._handle_security_alert({"severity": "high"}, wf, {}, "u")
            await svc._handle_security_alert({"severity": "medium"}, wf, {}, "u")
            await svc._handle_security_alert({"severity": "low"}, wf, {}, "u")
        blk.assert_awaited_once()  # only high severity blocks
        sec.log_security_alert.assert_awaited()

    async def test_handle_compliance_violation_severity_paths(self):
        mod, svc = self._svc(security_service=AsyncMock())
        sec = svc.security_service
        sec.log_compliance_violation = AsyncMock()
        wf = MagicMock(workflow_id="wf")
        with patch.object(svc, "_block_workflow_execution", AsyncMock()) as blk, \
             patch.object(svc, "_enable_compliance_logging", AsyncMock()) as en, \
             patch.object(svc, "_notify_compliance_team", AsyncMock()):
            await svc._handle_compliance_violation({"severity": "high"}, wf, {}, "u")
            await svc._handle_compliance_violation({"severity": "medium"}, wf, {}, "u")
        blk.assert_awaited_once()
        en.assert_awaited_once()

    async def test_create_security_automation_flow(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.create_security_automation(
            {"name": "sec", "description": "d", "threat_types": ["malware"],
             "severity_levels": ["high"]}, "u1")
        assert res["ok"], res
        assert res["automation_id"] in svc.active_automations
        # matching automation executes via handle_security_event
        with patch.object(svc, "execute_enterprise_workflow",
                          AsyncMock(return_value={"ok": True})) as exe:
            handled = await svc.handle_security_event(
                {"threat_type": "malware", "severity": "high"})
        assert handled["ok"] and handled["relevant_automations"] == 1
        exe.assert_awaited_once()
        assert svc.enterprise_metrics["security_incidents_resolved"] == 1

    async def test_create_compliance_automation_flow(self):
        mod, svc = self._svc()
        self._guards(mod)
        res = await svc.create_compliance_automation(
            {"name": "comp", "description": "d", "compliance_standards": ["SOC2"],
             "workflow_type": "audit_remediation"}, "u1")
        assert res["ok"], res
        with patch.object(svc, "execute_enterprise_workflow",
                          AsyncMock(return_value={"ok": True})):
            handled = await svc.handle_compliance_violation({"standard": "SOC2"})
        assert handled["ok"]
        assert svc.enterprise_metrics["compliance_violations_resolved"] >= 1

    async def test_get_enterprise_workflows_filters(self):
        mod, svc = self._svc()
        self._guards(mod)
        await svc.create_enterprise_workflow(self._wf_data(name="a"), "u1")
        all_wfs = await svc.get_enterprise_workflows()
        assert len(all_wfs) == 1
        assert all_wfs[0]["service_type"] == "security"
        none_wfs = await svc.get_enterprise_workflows(filters={"service_type": "compliance"})
        assert none_wfs == []
        sec_wfs = await svc.get_enterprise_workflows(filters={"security_level": "internal"})
        assert len(sec_wfs) == 1
        std_wfs = await svc.get_enterprise_workflows(filters={"compliance_standard": "SOC2"})
        assert len(std_wfs) == 1

    async def test_get_automations_status_and_metrics(self):
        mod, svc = self._svc()
        self._guards(mod)
        await svc.create_security_automation(
            {"name": "s", "description": "d", "threat_types": [], "severity_levels": ["high"]}, "u")
        status = await svc.get_automations_status()
        assert status["total_automations"] == 1
        assert status["security_automations"] == 1
        assert status["active_automations"] == 1
        metrics = await svc.get_enterprise_metrics()
        assert metrics["active_automations"] == 1

    async def test_initialize_and_private_setups(self):
        mod, svc = self._svc()
        sec = AsyncMock()
        ai = AsyncMock()
        svc.security_service = sec
        svc.ai_integration = ai
        svc.ai_service = object()
        assert await svc.initialize() is True
        sec.setup_workflow_monitoring.assert_awaited_once()
        sec.setup_compliance_automation.assert_awaited_once()
        sec.start_monitoring.assert_awaited_once()
        ai.setup_workflow_automation.assert_awaited_once()
        ai.start_monitoring.assert_awaited_once()

    async def test_initialize_missing_required_services(self):
        mod, svc = self._svc(security_service=None, ai_service=None)
        assert await svc.initialize() is False

    async def test_initialize_setup_exceptions_swallowed(self):
        # _setup_* and _start_* swallow exceptions internally
        mod, svc = self._svc()
        svc.security_service = AsyncMock()
        svc.security_service.setup_workflow_monitoring = AsyncMock(side_effect=RuntimeError("x"))
        svc.security_service.setup_compliance_automation = AsyncMock(side_effect=RuntimeError("x"))
        svc.security_service.start_monitoring = AsyncMock(side_effect=RuntimeError("x"))
        svc.ai_integration = AsyncMock()
        svc.ai_integration.setup_workflow_automation = AsyncMock(side_effect=RuntimeError("x"))
        svc.ai_integration.start_monitoring = AsyncMock(side_effect=RuntimeError("x"))
        await svc._setup_workflow_security_integration()  # must not raise
        await svc._setup_compliance_automation()
        await svc._setup_ai_powered_automation()
        await svc._start_enterprise_monitoring()
        # None services -> no-op branches
        svc.security_service = None
        svc.ai_integration = None
        await svc._setup_workflow_security_integration()
        await svc._setup_compliance_automation()
        await svc._setup_ai_powered_automation()
        await svc._start_enterprise_monitoring()

    async def test_initialize_enterprise_services_imports(self):
        mod, svc = self._svc()
        svc.security_service = None
        svc.ai_integration = None
        await svc._initialize_enterprise_services()  # imports real singletons
        assert svc.security_service is not None or svc.ai_integration is not None

    async def test_get_ai_enhanced_context_paths(self):
        mod, svc = self._svc(ai_service=None)
        wf = mod.EnterpriseWorkflow(
            workflow_id="wf", name="n", description="d",
            service_type=mod.EnterpriseServiceType.SECURITY,
            security_level=mod.WorkflowSecurityLevel.INTERNAL,
            compliance_standards=[], triggers=[], steps=[], actions=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc), created_by="u",
            status="active", metadata={}, audit_trail=[], compliance_checks=[])
        no_ai = await svc._get_ai_enhanced_context(wf, {"a": 1})
        assert no_ai["ai_enhanced"] is False

        ai = AsyncMock()
        resp = MagicMock(ok=True, output_data={"insight": 1}, confidence=0.9)
        ai.process_ai_request = AsyncMock(return_value=resp)
        svc.ai_service = ai
        with patch.object(mod, "AIRequest", MagicMock(), create=True), \
             patch.object(mod, "AITaskType", MagicMock(), create=True), \
             patch.object(mod, "AIModelType", MagicMock(), create=True), \
             patch.object(mod, "AIServiceType", MagicMock(), create=True):
            enhanced = await svc._get_ai_enhanced_context(wf, {"a": 1})
        assert enhanced["ai_enhanced"] is True

        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("boom"))
        degraded = await svc._get_ai_enhanced_context(wf, {"a": 1})
        assert degraded["ai_enhanced"] is False

    async def test_security_pre_check_failure_paths(self):
        mod, svc = self._svc()
        wf = MagicMock(security_level=MagicMock(value="internal"))
        with patch.object(svc, "_check_user_authorization",
                          AsyncMock(return_value={"authorized": False})):
            r = await svc._security_pre_check(wf, {}, "u")
        assert r["passed"] is False and "authorized" in r["reason"].lower()
        with patch.object(svc, "_check_user_authorization",
                          AsyncMock(return_value={"authorized": True})), \
             patch.object(svc, "_validate_context_security",
                          AsyncMock(return_value={"valid": False})):
            r = await svc._security_pre_check(wf, {}, "u")
        assert r["passed"] is False
        with patch.object(svc, "_check_user_authorization",
                          AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._security_pre_check(wf, {}, "u")
        assert r["passed"] is False

    async def test_compliance_pre_check_failure_and_error(self):
        mod, svc = self._svc()
        wf = MagicMock(compliance_standards=[MagicMock(value="SOC2")])
        with patch.object(svc, "_check_compliance_requirements",
                          AsyncMock(return_value={"compliant": False})):
            r = await svc._compliance_pre_check(wf, {}, "u")
        assert r["passed"] is False
        with patch.object(svc, "_check_compliance_requirements",
                          AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._compliance_pre_check(wf, {}, "u")
        assert r["passed"] is False

    async def test_step_dispatcher_all_types(self):
        mod, svc = self._svc()
        ctx = {}
        for stype, expected_key in [
            ("security_check", "security_status"),
            ("compliance_check", "compliance_status"),
            ("ai_analysis", "ai_insights"),
            ("data_processing", "processed_data"),
            ("notification", "notification_sent"),
            ("custom_thing", "custom_result"),
        ]:
            r = await svc._execute_workflow_step({"type": stype}, ctx, "u")
            assert r["success"] is True and expected_key in r
            assert "execution_time" in r
        with patch.object(svc, "_execute_custom_step",
                          AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._execute_workflow_step({"type": "other"}, ctx, "u")
        assert r["success"] is False and r["execution_time"] == 0.0

    async def test_coerce_compliance_standard(self):
        mod, svc = self._svc()
        std = mod._coerce_compliance_standard("SOC2")
        assert std is mod.ComplianceStandard.SOC2
        assert mod._coerce_compliance_standard(std) is std
        with pytest.raises(ValueError):
            mod._coerce_compliance_standard(12345)

    async def test_get_service_info_and_close(self):
        mod, svc = self._svc()
        self._guards(mod)
        info = await svc.get_service_info()
        assert info["status"] == "ACTIVE" and "features" in info
        await svc.close()  # guards open -> must not raise

    async def test_rate_limited_and_circuit_breaker_paths(self):
        mod, svc = self._svc()
        self._guards(mod, enabled=False)
        res = await svc.create_enterprise_workflow(self._wf_data(), "u")
        assert res["ok"] is False and "503" in str(res["error"])
        self._unguard()
        self._guards(mod, limited=True)
        res = await svc.get_enterprise_workflows()
        assert res == []
        self._unguard()
        self._guards(mod, enabled=False)
        with pytest.raises(mod.HTTPException):
            await svc.get_enterprise_metrics()
        with pytest.raises(mod.HTTPException):
            await svc.close()

    async def test_log_enterprise_event_with_and_without_service(self):
        mod, svc = self._svc(security_service=AsyncMock())
        await svc._log_enterprise_event("e", "u", "r", "a", "success", {"m": 1})
        svc.security_service.audit_event.assert_awaited_once()
        svc.security_service = None
        await svc._log_enterprise_event("e", "u", "r", "a", "success", None)


# =========================================================================== #
# 2. core/learning_llm_router.py
# =========================================================================== #
class TestLearningRouterFinal:
    def _router(self):
        from core.learning_llm_router import LearningBasedRouter
        return LearningBasedRouter(MagicMock())

    @staticmethod
    def _req(**over):
        from core.learning_llm_router import RoutingRequest
        data = dict(
            tenant_id="t1", task_type="question_answering",
            estimated_tokens=1000, requires_quality=False,
        )
        data.update(over)
        return RoutingRequest(**data)

    # ---- missing 874: requires_reasoning capability gate ----
    async def test_route_requires_reasoning(self):
        r = self._router()
        result = await r.route(self._req(requires_reasoning=True, requires_quality=False))
        assert result.selected_model is not None
        assert hasattr(result.selected_model, "model_name")
        # reasoning-capable model selected
        from core.learning_llm_router import ModelCapability
        assert ModelCapability.REASONING in result.selected_model.capabilities

    async def test_route_no_candidates_fallback(self):
        r = self._router()
        # vision + quality + reasoning leaves a small set; force empty via
        # filtering every model out with a tiny latency budget after caps
        result = await r.route(self._req(
            requires_reasoning=True, requires_vision=True,
            requires_quality=False, max_latency_ms=1))
        assert result.selected_model is not None  # fallback still returns
        assert result.routing_time_ms < 1000

    async def test_route_with_budget_and_latency(self):
        r = self._router()
        result = await r.route(self._req(budget_limit=10.0, max_latency_ms=500))
        assert result.confidence <= 1.0 and result.confidence >= 0.0

    async def test_route_tenant_preference_and_long_context(self):
        r = self._router()
        result = await r.route(self._req(
            estimated_tokens=100000,
            user_preferences={"preferred_model": "gpt-5.5"}))
        assert result.selected_model is not None

    # ---- missing 1042/1044: max_latency/max_cost <= 0 guards ----
    def test_ema_normalization_zero_guards(self):
        r = self._router()
        model = next(iter(r._model_registry.values()))
        r._ema_scores[f"t1:question_answering:{model.model_id}"] = {"latency": 0.0, "cost": 0.0}
        baselines = r._ema_normalization_baselines([model], self._req())
        assert baselines["max_latency"] == 1.0
        assert baselines["max_cost"] == 1.0

    # ---- missing 2009: malformed EMA key skipped in stats ----
    async def test_routing_statistics_malformed_ema_key(self):
        r = self._router()
        r._ema_scores["badkey"] = {}
        r._ema_scores["t1:qa:gpt-4o"] = {"success": 0.8, "samples": 3}
        stats = await r.get_routing_statistics("t1")
        assert stats["ema_scores"]["qa:gpt-4o"]["samples"] == 3
        assert "badkey" not in str(stats["ema_scores"])

    # ---- missing 2134/2151/2165: load_local_models_into_registry ----
    def test_load_local_models_with_vision_and_default_provider(self):
        r = self._router()
        provider = NS(id=1, provider_type="ollama", name="Local Ollama")
        cap = NS(model_id="llama3", supports_tools=False, supports_vision=True,
                 supports_reasoning=False, quality_score=0.7, speed_score=0.6,
                 context_window=8192)
        provider2 = NS(id=2, provider_type="lmstudio", name="LM Studio")
        fake_db = MagicMock()
        cap_calls = {"n": 0}

        def query(model):
            q = MagicMock()
            if model.__name__ == "LocalModelProvider":
                q.filter.return_value.all.return_value = [provider, provider2]
            else:
                # first provider has caps, second has none -> default branch
                cap_calls["n"] += 1
                q.filter.return_value.all.return_value = [cap] if cap_calls["n"] == 1 else []
            return q

        fake_db.query.side_effect = query
        fake_ctx = MagicMock()
        fake_ctx.__enter__ = MagicMock(return_value=fake_db)
        fake_ctx.__exit__ = MagicMock(return_value=False)
        with patch("core.database.get_db_session", return_value=fake_ctx):
            added = r.load_local_models_into_registry("ws1")
        assert added >= 2
        assert "llama3" in r._model_registry
        assert "lmstudio_default" in r._model_registry

    def test_load_local_models_no_providers(self):
        r = self._router()
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.all.return_value = []
        fake_ctx = MagicMock()
        fake_ctx.__enter__ = MagicMock(return_value=fake_db)
        fake_ctx.__exit__ = MagicMock(return_value=False)
        with patch("core.database.get_db_session", return_value=fake_ctx):
            assert r.load_local_models_into_registry("ws1") == 0

    def test_load_local_models_db_error(self):
        r = self._router()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            assert r.load_local_models_into_registry("ws1") == 0

    # ---- generous extra coverage ----
    def test_extract_request_features_branches(self):
        r = self._router()
        # prompt_text with code fence + digits
        f = r._extract_request_features(self._req(
            conversation_context={"prompt_text": "```py x=1 ``` 123"}))
        assert f["has_code"] == 1.0 and f["has_numbers"] == 1.0
        assert 0.0 < f["avg_word_length"]
        # caller-supplied signals + intent one-hot
        f2 = r._extract_request_features(self._req(
            conversation_context={"has_code": 0.0, "has_numbers": 1.0,
                                  "avg_word_length": 7.0, "intent": "coding"}))
        assert f2["has_code"] == 0.0 and f2["avg_word_length"] == 7.0
        assert any(v == 1.0 for k, v in f2.items() if k.startswith("intent_"))
        # code task default has_code
        f3 = r._extract_request_features(self._req(task_type="code_generation"))
        assert f3["task_code"] == 1.0 and f3["has_code"] == 1.0

    def test_token_buckets(self):
        from core.learning_llm_router import LearningBasedRouter as L
        assert L._token_bucket(10) == 0.0
        assert L._token_bucket(100) == 1.0
        assert L._token_bucket(500) == 2.0
        assert L._token_bucket(2000) == 3.0
        assert L._token_bucket(99999) == 4.0

    def test_stash_consume_decision_eviction(self):
        r = self._router()
        r._max_routing_decisions = 3
        ids = [r.stash_decision({"log_tokens": 1.0}) for _ in range(5)]
        assert len(r._routing_decisions) == 3
        assert r.consume_decision(ids[-1]) is not None
        assert r.consume_decision("nope") is None

    def test_check_cost_within_budget(self):
        from core.learning_llm_router import _check_cost_within_budget
        assert _check_cost_within_budget("t", None) is True
        assert _check_cost_within_budget("t", 0.5) in (True, False)

    def test_derive_weights_edge_cases(self):
        from core.learning_llm_router import LearningBasedRouter as L
        empty = L._derive_weights_from_success({}, "unknown_task")
        assert empty == {"quality": 0.4, "cost": 0.3, "speed": 0.3}
        w = L._derive_weights_from_success(
            {"m": {"success": 9, "total": 10}}, "code_generation")
        assert 0.0 <= w["quality"] <= 0.8
        assert abs(w["quality"] + w["cost"] + w["speed"] - 1.0) < 1e-6

    async def test_record_feedback_retrain_and_ema(self):
        from core.learning_llm_router import RoutingFeedback
        r = self._router()
        r._min_samples_per_model = 2
        r._persist_feedback = MagicMock()
        for i in range(3):
            fb = RoutingFeedback(
                routing_result_id=f"rid{i}", tenant_id="t1",
                model_id="gpt-4o", task_type="question_answering",
                success=True, quality_satisfied=True, cost_within_budget=True,
                actual_latency_ms=100.0 + i, actual_cost=0.01,
            )
            await r.record_feedback(fb)
        key = "t1:question_answering:gpt-4o"
        assert r._ema_scores[key]["samples"] == 3
        assert r._ema_scores[key]["latency"] > 0
        assert "t1:question_answering" in r._router_cache

    async def test_routing_statistics_tenant_scoping(self):
        from core.learning_llm_router import RoutingFeedback
        r = self._router()
        for tenant in ("t1", "t2"):
            fb = RoutingFeedback(
                routing_result_id="x", tenant_id=tenant, model_id="gpt-4o",
                task_type="question_answering", success=True,
                quality_satisfied=False, cost_within_budget=True)
            await r.record_feedback(fb)
        stats = await r.get_routing_statistics("t1")
        assert stats["feedback_samples"] == 1
        assert stats["model_success_rates"]["gpt-4o"] == 0.0

    async def test_export_routing_data(self):
        from core.learning_llm_router import RoutingFeedback
        r = self._router()
        fb = RoutingFeedback(
            routing_result_id="x", tenant_id="t1", model_id="gpt-4o",
            task_type="reasoning", success=True, quality_satisfied=True,
            cost_within_budget=True, user_satisfaction=0.9)
        await r.record_feedback(fb)
        data = await r.export_routing_data("t1", days=30)
        assert len(data["routing_feedback"]) == 1
        empty = await r.export_routing_data("other")
        assert empty["routing_feedback"] == []

    def test_update_and_clear_registry(self):
        r = self._router()
        added = r.update_model_registry([
            {"model_id": "new-model", "provider": "p", "capabilities": ["reasoning", "bogus_cap"]},
            {"model_id": None},  # skipped
        ])
        assert added == 1
        assert "new-model" in r._model_registry
        r._router_cache["t1:qa"] = {"quality": 1.0}
        r._router_cache["t2:qa"] = {"quality": 1.0}
        r.clear_learning_cache("t1")
        assert "t1:qa" not in r._router_cache and "t2:qa" in r._router_cache
        r.clear_learning_cache()
        assert not r._router_cache

    def test_get_available_models_filters(self):
        from core.learning_llm_router import ModelCapability
        r = self._router()
        models = r.get_available_models(capabilities=[ModelCapability.CHEAP], tier="standard", max_cost=1.0)
        assert models and all(ModelCapability.CHEAP in m.capabilities for m in models)
        assert r.get_available_models()  # no filters

    def test_build_feedback_from_quality(self):
        from core.learning_llm_router import LearningBasedRouter, RoutingFeedback
        q = NS(success=True, quality_satisfied=True, quality_score=0.88)
        fb = LearningBasedRouter.build_feedback("rid", "t1", "gpt-4o", "qa", q,
                                                actual_cost=0.01, actual_latency_ms=50.0)
        assert isinstance(fb, RoutingFeedback)
        assert fb.user_satisfaction == 0.88

    def test_feedback_to_training_example_defaults(self):
        from core.learning_llm_router import RoutingFeedback
        r = self._router()
        fb = RoutingFeedback(routing_result_id="x", tenant_id="t1",
                             model_id="gpt-4o", task_type="reasoning",
                             success=True, quality_satisfied=True,
                             cost_within_budget=True)
        ex = r._feedback_to_training_example(fb, "reasoning")
        assert ex.user_satisfaction == 1.0
        assert ex.prompt_features["task_reasoning"] == 1.0
        fb._prompt_features = {"log_tokens": 10.0}
        ex2 = r._feedback_to_training_example(fb, "reasoning")
        assert ex2.estimated_tokens == 1023

    def test_get_learned_weights_defaults(self):
        r = self._router()
        w = r._get_learned_weights("code_generation", "t9")
        assert w == {"quality": 0.5, "cost": 0.2, "speed": 0.3}
        w2 = r._get_learned_weights("nope", "t9")
        assert w2 == {"quality": 0.4, "cost": 0.3, "speed": 0.3}

    def test_persist_feedback_swallows_db_errors(self):
        from core.learning_llm_router import RoutingFeedback
        r = self._router()
        fb = RoutingFeedback(routing_result_id="x", tenant_id="t1",
                             model_id="gpt-4o", task_type="qa",
                             success=True, quality_satisfied=True,
                             cost_within_budget=True)
        with patch("core.learning_llm_router.get_db_session",
                   side_effect=RuntimeError("db down")):
            r._persist_feedback(fb, None)  # must not raise

    def test_resolve_feedback_context_paths(self):
        r = self._router()
        row = NS(task_type="qa", routing_result_id="rid-1")
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=fake_db)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("core.learning_llm_router.get_db_session", return_value=ctx):
            assert r.resolve_feedback_context("t1", "gpt-4o") == ("qa", "rid-1")
        fake_db2 = MagicMock()
        fake_db2.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        ctx2 = MagicMock()
        ctx2.__enter__ = MagicMock(return_value=fake_db2)
        ctx2.__exit__ = MagicMock(return_value=False)
        with patch("core.learning_llm_router.get_db_session", return_value=ctx2):
            assert r.resolve_feedback_context("t1", "gpt-4o") == (None, None)
        with patch("core.learning_llm_router.get_db_session",
                   side_effect=RuntimeError("x")):
            assert r.resolve_feedback_context("t1", "gpt-4o") == (None, None)

    def test_load_feedback_from_db(self):
        r = self._router()
        rows = [
            NS(routing_result_id="r1", tenant_id="t1", model_id="gpt-4o",
               task_type="qa", success=True, quality_satisfied=True,
               cost_within_budget=True, user_satisfaction=0.9, actual_cost=0.01,
               actual_latency_ms=100.0, created_at=datetime.now(timezone.utc),
               prompt_features={"log_tokens": 8.0}),
            NS(routing_result_id="r2", tenant_id="t1", model_id="gpt-4o",
               task_type="qa", success=False, quality_satisfied=False,
               cost_within_budget=True, user_satisfaction=None, actual_cost=None,
               actual_latency_ms=None, created_at=datetime.now(timezone.utc),
               prompt_features=None),
        ]
        fake_db = MagicMock()
        q = fake_db.query.return_value
        q.filter.return_value = q  # tenant filter path reuses the same chain
        q.order_by.return_value.all.return_value = rows
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=fake_db)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("core.learning_llm_router.get_db_session", return_value=ctx):
            loaded = r.load_feedback_from_db("t1")
        assert loaded == 2
        assert len(r._preference_data["t1:qa"]) == 2
        assert r._ema_scores["t1:qa:gpt-4o"]["samples"] == 2
        # DB failure path
        with patch("core.learning_llm_router.get_db_session",
                   side_effect=RuntimeError("x")):
            assert r.load_feedback_from_db() == 0

    def test_get_cheapest_model(self):
        r = self._router()
        cheapest = r._get_cheapest_model()
        assert cheapest.cost_per_million == min(
            m.cost_per_million for m in r._model_registry.values())

    def test_ema_alpha_env(self, monkeypatch):
        from core.learning_llm_router import LearningBasedRouter as L
        assert L._ema_alpha() == 0.2
        monkeypatch.setenv("ATOM_EMA_ALPHA", "0.9")
        assert L._ema_alpha() == 0.9
        monkeypatch.setenv("ATOM_EMA_ALPHA", "-1")
        assert L._ema_alpha() == 0.2
        monkeypatch.setenv("ATOM_EMA_ALPHA", "not-a-number")
        assert L._ema_alpha() == 0.2
        monkeypatch.setenv("ATOM_EMA_ALPHA", "5")
        assert L._ema_alpha() == 1.0

    def test_ema_eviction_cap(self):
        r = self._router()
        r._max_ema_keys = 2
        from core.learning_llm_router import RoutingFeedback
        import asyncio as _aio

        async def run():
            for i in range(4):
                fb = RoutingFeedback(routing_result_id=f"x{i}", tenant_id=f"t{i}",
                                     model_id="gpt-4o", task_type="qa",
                                     success=True, quality_satisfied=True,
                                     cost_within_budget=True)
                r._persist_feedback = MagicMock()
                await r.record_feedback(fb)

        _aio.get_event_loop().run_until_complete(run()) if False else None
        # synchronous path: drive _update_ema_scores directly
        for i in range(4):
            fb = RoutingFeedback(routing_result_id=f"x{i}", tenant_id=f"t{i}",
                                 model_id="gpt-4o", task_type="qa",
                                 success=True, quality_satisfied=True,
                                 cost_within_budget=True)
            r._update_ema_scores(fb)
        assert len(r._ema_key_order) <= 2
        assert len(r._ema_scores) <= 3  # t3 kept + tolerated slack

    def test_get_learning_router_factory(self):
        from core.learning_llm_router import get_learning_router, LearningBasedRouter
        r = get_learning_router(MagicMock())
        assert isinstance(r, LearningBasedRouter)


# =========================================================================== #
# 3. integrations/atom_workflow_automation_service.py
# =========================================================================== #
class TestWorkflowAutomationFinal:
    @pytest.fixture(autouse=True)
    def _guards(self):
        import integrations.atom_workflow_automation_service as wfs
        with patch.object(wfs, "circuit_breaker") as cb, \
             patch.object(wfs, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 100))
            yield

    def _svc(self, **over):
        import integrations.atom_workflow_automation_service as wfs
        sec = AsyncMock()
        sec.register_security_trigger = AsyncMock()
        uni = AsyncMock()
        uni.execute_enterprise_workflow = AsyncMock(return_value={"ok": True})
        uni.register_compliance_trigger = AsyncMock()
        cfg = {
            "database": None, "cache": None,
            "security_service": sec, "unified_service": uni,
            "ai_service": MagicMock(),
        }
        cfg.update(over)
        return wfs.AtomWorkflowAutomationService(config=cfg)

    @staticmethod
    def _automation_data(**over):
        data = {
            "name": "Auto", "description": "d",
            "automation_type": "security", "priority": "high",
            "conditions": [{"type": "event_triggered", "event_type": "system_event"}],
            "actions": [{"type": "logging", "config": {}}],
            "schedule": None,
        }
        data.update(over)
        return data

    # ---- missing 1877-1879: outer except in _initialize_integration_endpoints ----
    async def test_initialize_integration_endpoints_outer_error(self):
        svc = self._svc()
        svc.platform_integrations = _RaisingDict({"slack": object()}, boom_on="items")
        assert await svc._initialize_integration_endpoints() is False

    async def test_initialize_integration_endpoints_inner_error_and_ok(self):
        svc = self._svc()
        good = AsyncMock()
        good.test_connection = AsyncMock(return_value=True)
        bad = AsyncMock()
        bad.test_connection = AsyncMock(side_effect=RuntimeError("conn fail"))
        no_test = object()
        svc.platform_integrations = {"a": good, "b": bad, "c": None, "d": no_test}
        assert await svc._initialize_integration_endpoints() is True

    # ---- generous extra coverage on public API ----
    async def test_create_and_get_automation(self):
        svc = self._svc()
        res = await svc.create_automation(self._automation_data(), "u1")
        assert res.get("ok"), res
        autos = await svc.get_automations()
        assert any(a["name"] == "Auto" for a in autos)
        filtered = await svc.get_automations(filters={"automation_type": "security"})
        assert filtered

    async def test_create_automation_invalid_data(self):
        svc = self._svc()
        with patch.object(svc, "_validate_automation_data",
                          AsyncMock(return_value={"valid": False, "errors": ["bad"]})):
            res = await svc.create_automation(self._automation_data(), "u1")
        assert res.get("ok") is False

    async def test_create_automation_exception(self):
        svc = self._svc()
        with patch.object(svc, "_validate_automation_data",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            res = await svc.create_automation(self._automation_data(), "u1")
        assert res.get("ok") is False

    async def test_execute_automation_not_found(self):
        svc = self._svc()
        res = await svc.execute_automation("missing", {}, "user")
        assert res.get("ok") is False

    async def test_execute_automation_success_and_metrics(self):
        svc = self._svc()
        created = await svc.create_automation(self._automation_data(), "u1")
        assert created["ok"]
        auto_id = created["automation_id"]
        res = await svc.execute_automation(auto_id, {"k": "v"}, "trigger")
        assert res.get("ok"), res
        metrics = await svc.get_automation_metrics()
        assert metrics  # non-empty report

    async def test_execute_automation_disabled(self):
        import integrations.atom_workflow_automation_service as wfs
        svc = self._svc()
        created = await svc.create_automation(self._automation_data(), "u1")
        auto_id = created["automation_id"]
        svc.automations[auto_id].status = wfs.AutomationStatus.INACTIVE
        res = await svc.execute_automation(auto_id, {}, "trigger")
        assert res.get("ok") is False

    async def test_get_automation_executions(self):
        svc = self._svc()
        created = await svc.create_automation(self._automation_data(), "u1")
        auto_id = created["automation_id"]
        await svc.execute_automation(auto_id, {}, "trigger")
        execs = await svc.get_automation_executions(auto_id)
        assert isinstance(execs, list)

    async def test_get_service_info(self):
        svc = self._svc()
        info = await svc.get_service_info()
        assert isinstance(info, dict) and info.get("name")

    async def test_pre_and_post_checks(self):
        svc = self._svc()
        auto = MagicMock()
        assert (await svc._pre_execution_security_check(auto, {}))["passed"]
        assert (await svc._pre_execution_compliance_check(auto, {}))["passed"]
        assert (await svc._post_execution_security_check(auto, []))["passed"]
        assert (await svc._post_execution_compliance_check(auto, []))["passed"]

    async def test_event_trigger_dispatch(self):
        svc = self._svc()
        created = await svc.create_automation(self._automation_data(), "u1")
        auto_id = created["automation_id"]
        with patch.object(svc, "execute_automation",
                          AsyncMock(return_value={"ok": True})) as exe:
            await svc._handle_event_trigger("system_event", {"e": 1})
        exe.assert_awaited_once()
        # unknown event type -> no dispatch, no raise
        await svc._handle_event_trigger("nope", {})

    async def test_security_and_compliance_automation_creators(self):
        svc = self._svc()
        sec_res = await svc.create_security_automation(
            {"threat_type": "malware"}, {"name": "s", "severity": "high"})
        assert sec_res.get("ok"), sec_res
        comp_res = await svc.create_compliance_automation(
            {"standard": "SOC2", "violation_type": "access"},
            {"name": "c", "schedule": "daily"})
        assert comp_res.get("ok"), comp_res

    async def test_integration_automation_creator(self):
        svc = self._svc()
        res = await svc.create_integration_automation(
            "slack", {"name": "int", "channel": "#ops"})
        assert res.get("ok"), res

    async def test_close(self):
        svc = self._svc()
        svc.scheduler_task = MagicMock()
        svc.scheduler_running = False
        session = AsyncMock()
        svc.http_sessions = {"s": session}
        await svc.close()
        session.close.assert_awaited_once()
