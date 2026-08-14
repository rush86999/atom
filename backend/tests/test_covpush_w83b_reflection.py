"""Coverage wave 83b — push 6 backend modules to >=95% statement coverage.

Modules covered (standalone, zero LLM spend / no network / no real DB):
  1. core/group_reflection_service.py     (GEA reflection module)
  2. core/hypothesis_tree.py              (HTR tree structures)
  3. core/integration_constants.py        (multi-entity integration lists)
  4. core/automation_settings_endpoints.py(settings API routes)
  5. core/agent_objective.py              (W5 objective/termination predicate)
  6. core/external_integration_service.py (node-bridge-backed integration service)

Style: mocked deps only; TestClient with app.dependency_overrides for routes;
patch REAL module names (no `backend.` prefix).
"""
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ─────────────────────────────────────────────────────────────────────────────
# 3. core/integration_constants.py
# ─────────────────────────────────────────────────────────────────────────────

from core import integration_constants as ic


class TestIntegrationConstants:
    def test_communication_integrations(self):
        assert "outlook" in ic.COMMUNICATION_INTEGRATIONS
        assert "gmail" in ic.COMMUNICATION_INTEGRATIONS
        assert "slack" in ic.COMMUNICATION_INTEGRATIONS
        assert "whatsapp" in ic.COMMUNICATION_INTEGRATIONS
        assert "teams" in ic.COMMUNICATION_INTEGRATIONS
        assert "hubspot" in ic.COMMUNICATION_INTEGRATIONS

    def test_document_integrations(self):
        assert ic.DOCUMENT_INTEGRATIONS == ["document"]

    def test_multi_entity_integrations_is_combined(self):
        assert ic.MULTI_ENTITY_INTEGRATIONS == (
            ic.COMMUNICATION_INTEGRATIONS + ic.DOCUMENT_INTEGRATIONS
        )
        assert "document" in ic.MULTI_ENTITY_INTEGRATIONS
        assert "slack" in ic.MULTI_ENTITY_INTEGRATIONS

    def test_email_thread_integrations(self):
        assert ic.EMAIL_THREAD_INTEGRATIONS == ["outlook", "gmail"]
        assert "teams" not in ic.EMAIL_THREAD_INTEGRATIONS


# ─────────────────────────────────────────────────────────────────────────────
# 5. core/agent_objective.py
# ─────────────────────────────────────────────────────────────────────────────

from core.agent_objective import (
    Objective,
    _env_bool,
    objective_from_context,
    objective_loop_enabled,
)


class TestAgentObjectiveEnvBool:
    def test_env_bool_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("ATOM_TEST_BOOL_X", raising=False)
        assert _env_bool("ATOM_TEST_BOOL_X", True) is True
        assert _env_bool("ATOM_TEST_BOOL_X", False) is False

    def test_env_bool_truthy_variants(self, monkeypatch):
        for val in ("1", "true", "True", " yes ", "on", "ON"):
            monkeypatch.setenv("ATOM_TEST_BOOL_X", val)
            assert _env_bool("ATOM_TEST_BOOL_X", False) is True

    def test_env_bool_falsy_variants(self, monkeypatch):
        for val in ("0", "false", "no", "off", "random"):
            monkeypatch.setenv("ATOM_TEST_BOOL_X", val)
            assert _env_bool("ATOM_TEST_BOOL_X", True) is False

    def test_objective_loop_enabled_default(self, monkeypatch):
        monkeypatch.delenv("ATOM_OBJECTIVE_LOOP_ENABLED", raising=False)
        assert objective_loop_enabled() is True

    def test_objective_loop_enabled_false(self, monkeypatch):
        monkeypatch.setenv("ATOM_OBJECTIVE_LOOP_ENABLED", "false")
        assert objective_loop_enabled() is False


class TestObjective:
    def test_is_satisfied_no_predicate(self):
        obj = Objective(goal="g")
        assert obj.is_satisfied({}) is False

    def test_is_satisfied_predicate_true(self):
        obj = Objective(goal="g", definition_of_done=lambda s: s["done"] is True)
        assert obj.is_satisfied({"done": True}) is True

    def test_is_satisfied_predicate_false(self):
        obj = Objective(goal="g", definition_of_done=lambda s: False)
        assert obj.is_satisfied({}) is False

    def test_is_satisfied_predicate_raises(self):
        def boom(state):
            raise ValueError("bad state")
        obj = Objective(goal="g", definition_of_done=boom)
        assert obj.is_satisfied({}) is False

    def test_defaults(self):
        obj = Objective(goal="g")
        assert obj.constraints == {}
        assert obj.success_criteria == []


class TestObjectiveFromContext:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("ATOM_OBJECTIVE_LOOP_ENABLED", "false")
        assert objective_from_context({"objective": Objective(goal="g")}) is None

    def test_objective_instance_passthrough(self, monkeypatch):
        monkeypatch.delenv("ATOM_OBJECTIVE_LOOP_ENABLED", raising=False)
        obj = Objective(goal="g")
        assert objective_from_context({"objective": obj}) is obj

    def test_goal_and_done_predicate(self, monkeypatch):
        monkeypatch.delenv("ATOM_OBJECTIVE_LOOP_ENABLED", raising=False)
        done = lambda s: True
        result = objective_from_context({
            "objective_goal": "finish",
            "objective_done": done,
            "objective_criteria": ["c1"],
        })
        assert result is not None
        assert result.goal == "finish"
        assert result.definition_of_done is done
        assert result.success_criteria == ["c1"]
        assert result.is_satisfied({}) is True

    def test_missing_objective_returns_none(self, monkeypatch):
        monkeypatch.delenv("ATOM_OBJECTIVE_LOOP_ENABLED", raising=False)
        assert objective_from_context({}) is None

    def test_goal_without_callable_done_returns_none(self, monkeypatch):
        monkeypatch.delenv("ATOM_OBJECTIVE_LOOP_ENABLED", raising=False)
        assert objective_from_context({"objective_goal": "g"}) is None

    def test_non_objective_type_returns_none(self, monkeypatch):
        monkeypatch.delenv("ATOM_OBJECTIVE_LOOP_ENABLED", raising=False)
        assert objective_from_context({"objective": "not-an-objective"}) is None


# ─────────────────────────────────────────────────────────────────────────────
# 6. core/external_integration_service.py
# ─────────────────────────────────────────────────────────────────────────────

from core.external_integration_service import ExternalIntegrationService


class TestExternalIntegrationService:
    def _svc(self):
        return ExternalIntegrationService(max_concurrent=2)

    async def test_get_all_integrations_success(self):
        nb = AsyncMock()
        nb.get_catalog = AsyncMock(return_value=[{"name": "slack"}, {"name": "gmail"}])
        with patch("core.external_integration_service.node_bridge", nb):
            result = await self._svc().get_all_integrations()
        assert result == [{"name": "slack"}, {"name": "gmail"}]

    async def test_get_all_integrations_failure_returns_empty(self):
        nb = AsyncMock()
        nb.get_catalog = AsyncMock(side_effect=RuntimeError("Connection failed"))
        with patch("core.external_integration_service.node_bridge", nb):
            result = await self._svc().get_all_integrations()
        assert result == []

    async def test_get_piece_details_success(self):
        nb = AsyncMock()
        nb.get_piece_details = AsyncMock(return_value={"name": "slack", "version": "1.0"})
        with patch("core.external_integration_service.node_bridge", nb):
            result = await self._svc().get_piece_details("slack")
        assert result == {"name": "slack", "version": "1.0"}
        nb.get_piece_details.assert_awaited_once_with("slack")

    async def test_get_piece_details_failure_returns_none(self):
        nb = AsyncMock()
        nb.get_piece_details = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.external_integration_service.node_bridge", nb):
            result = await self._svc().get_piece_details("slack")
        assert result is None

    async def test_execute_integration_action_success(self):
        nb = AsyncMock()
        nb.execute_action = AsyncMock(return_value={"ok": True})
        with patch("core.external_integration_service.node_bridge", nb):
            result = await self._svc().execute_integration_action(
                integration_id="@activepieces/piece-slack",
                action_id="send_message",
                params={"text": "hi"},
                credentials={"apiKey": "k"},
            )
        assert result == {"ok": True}
        nb.execute_action.assert_awaited_once_with(
            piece_name="@activepieces/piece-slack",
            action_name="send_message",
            props={"text": "hi"},
            auth={"apiKey": "k"},
        )

    async def test_execute_integration_action_no_credentials(self):
        nb = AsyncMock()
        nb.execute_action = AsyncMock(return_value={})
        with patch("core.external_integration_service.node_bridge", nb):
            result = await self._svc().execute_integration_action(
                integration_id="p", action_id="a", params={}
            )
        assert result == {}
        nb.execute_action.assert_awaited_once_with(
            piece_name="p", action_name="a", props={}, auth=None
        )

    async def test_execute_integration_action_failure_reraises(self):
        nb = AsyncMock()
        nb.execute_action = AsyncMock(side_effect=RuntimeError("Action failed"))
        with patch("core.external_integration_service.node_bridge", nb):
            with pytest.raises(RuntimeError, match="Action failed"):
                await self._svc().execute_integration_action("p", "a", {})

    async def test_concurrent_executions_rate_limited(self):
        nb = AsyncMock()
        calls = 0

        async def slow_execute(**kwargs):
            nonlocal calls
            calls += 1
            return {"call": calls}

        nb.execute_action = slow_execute
        svc = ExternalIntegrationService(max_concurrent=1)
        with patch("core.external_integration_service.node_bridge", nb):
            results = await asyncio_gather([
                svc.execute_integration_action("p", "a", {}),
                svc.execute_integration_action("p", "a", {}),
            ])
        assert len(results) == 2

    def test_singleton_exists(self):
        from core.external_integration_service import external_integration_service
        assert isinstance(external_integration_service, ExternalIntegrationService)
        assert external_integration_service._rate_limit_semaphore is not None


async def asyncio_gather(coros):
    import asyncio
    return await asyncio.gather(*coros)


# ─────────────────────────────────────────────────────────────────────────────
# 4. core/automation_settings_endpoints.py
# ─────────────────────────────────────────────────────────────────────────────

from core.automation_settings_endpoints import router as automation_settings_router


def _sched_stub(fail=False):
    mod = types.ModuleType("ai.workflow_scheduler")
    sched = MagicMock()
    if fail:
        sched.reschedule_system_pipelines.side_effect = RuntimeError("scheduler down")
    mod.workflow_scheduler = sched
    return mod


@pytest.fixture
def settings_client():
    app = FastAPI()
    app.include_router(automation_settings_router)
    from core.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="u1")
    return TestClient(app)


@pytest.fixture
def settings_manager():
    manager = MagicMock()
    manager.get_settings.return_value = {
        "enable_automatic_knowledge_extraction": True,
        "pipelines": {"sales": {"mode": "scheduled"}},
    }
    manager.update_settings.return_value = {
        "enable_automatic_knowledge_extraction": False,
    }
    return manager


class TestAutomationSettingsEndpoints:
    def test_get_settings(self, settings_client, settings_manager):
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=settings_manager,
        ):
            resp = settings_client.get("/api/v1/settings/automations/")
        assert resp.status_code == 200
        assert resp.json()["enable_automatic_knowledge_extraction"] is True
        settings_manager.get_settings.assert_called_once()

    def test_update_settings_no_pipelines(self, settings_client, settings_manager):
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=settings_manager,
        ):
            resp = settings_client.post(
                "/api/v1/settings/automations/",
                json={"enable_automatic_knowledge_extraction": False},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["message"] == "Automation settings updated"
        assert body["settings"] == {"enable_automatic_knowledge_extraction": False}
        settings_manager.update_settings.assert_called_once_with(
            {"enable_automatic_knowledge_extraction": False}
        )

    def test_update_settings_all_none_fields(self, settings_client, settings_manager):
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=settings_manager,
        ):
            resp = settings_client.post(
                "/api/v1/settings/automations/", json={}
            )
        assert resp.status_code == 200
        settings_manager.update_settings.assert_called_once_with({})

    def test_update_settings_pipelines_refreshes_scheduler(
        self, settings_client, settings_manager
    ):
        stub = _sched_stub()
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=settings_manager,
        ), patch.dict(sys.modules, {"ai.workflow_scheduler": stub}):
            resp = settings_client.post(
                "/api/v1/settings/automations/",
                json={"pipelines": {"sales": {"mode": "manual"}}},
            )
        assert resp.status_code == 200
        stub.workflow_scheduler.reschedule_system_pipelines.assert_called_once()
        settings_manager.update_settings.assert_called_once_with(
            {"pipelines": {"sales": {"mode": "manual"}}}
        )

    def test_update_settings_scheduler_error_still_succeeds(
        self, settings_client, settings_manager
    ):
        stub = _sched_stub(fail=True)
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=settings_manager,
        ), patch.dict(sys.modules, {"ai.workflow_scheduler": stub}):
            resp = settings_client.post(
                "/api/v1/settings/automations/",
                json={"pipelines": {"projects": {"mode": "manual"}}},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        stub.workflow_scheduler.reschedule_system_pipelines.assert_called_once()

    def test_update_settings_with_unknown_fields_ignored(
        self, settings_client, settings_manager
    ):
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=settings_manager,
        ):
            resp = settings_client.post(
                "/api/v1/settings/automations/",
                json={"enable_out_of_workflow_automations": True},
            )
        assert resp.status_code == 200
        settings_manager.update_settings.assert_called_once_with(
            {"enable_out_of_workflow_automations": True}
        )


# ─────────────────────────────────────────────────────────────────────────────
# 1. core/group_reflection_service.py
# ─────────────────────────────────────────────────────────────────────────────

from core.group_reflection_service import (
    MIN_QUALITY_SCORE,
    DOMAIN_PROFILES,
    DomainProfile,
    DomainProfileRegistry,
    GroupReflectionService,
    _extract_conflict_signal,
    _extract_email_signal,
    _extract_error_lines,
    _extract_financial_signal,
    _extract_support_signal,
    _extract_traceback,
)


def _make_trace(
    benchmark_score=0.7,
    benchmark_passed=True,
    is_high_quality=True,
    model_patch="+ some fix",
    task_log="some log",
    tool_use_log=None,
    evolving_requirements="Add retry logic",
):
    t = MagicMock()
    t.benchmark_score = benchmark_score
    t.benchmark_passed = benchmark_passed
    t.is_high_quality = is_high_quality
    t.model_patch = model_patch
    t.task_log = task_log
    t.tool_use_log = tool_use_log or [{"tool_name": "bash", "success": True}]
    t.evolving_requirements = evolving_requirements
    return t


def _make_db(traces=None, agents=None):
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.return_value = traces or []
    q.first.return_value = (agents or [None])[0]
    db.query.return_value = q
    return db


def _make_svc(db):
    with patch(
        "core.service_factory.ServiceFactory.get_llm_service",
        return_value=MagicMock(),
    ):
        return GroupReflectionService(db)


class TestSignalExtractors:
    def test_extract_error_lines_keyword_found_near_start(self):
        log = "line0\nline1\nerror happened\nline3\nline4\nline5\nline6"
        result = _extract_error_lines(log)
        assert result is not None
        assert "error happened" in result
        assert result.startswith("line1")

    def test_extract_error_lines_keyword_at_end(self):
        log = "a\nb\nerror at end"
        result = _extract_error_lines(log)
        assert "error at end" in result
        assert result.endswith("error at end")

    def test_extract_error_lines_no_keyword_long_log(self):
        log = "x" * 200
        result = _extract_error_lines(log, "zzz")
        assert result is not None
        assert len(result) <= 600
        assert result == "x" * 200

    def test_extract_error_lines_no_keyword_short_log(self):
        result = _extract_error_lines("short log", "zzz")
        assert result is None

    def test_extract_error_lines_truncates_to_max_chars(self):
        log = ("error " + "y" * 1000)
        result = _extract_error_lines(log, max_chars=100)
        assert len(result) <= 100

    def test_extract_traceback_finds_traceback(self):
        log = "stuff\nTraceback (most recent call last):\n  File x.py line 1\nValueError"
        result = _extract_traceback(log)
        assert result.startswith("Traceback")
        assert "ValueError" in result

    def test_extract_traceback_falls_back_to_error_lines(self):
        result = _extract_traceback("no traceback here\nbut an error\nline")
        assert "error" in result

    def test_extract_email_signal_keyword(self):
        result = _extract_email_signal("email sent\nbounce detected\nnext")
        assert "bounce" in result

    def test_extract_email_signal_no_keyword_long(self):
        result = _extract_email_signal("z" * 200)
        assert result == "z" * 200

    def test_extract_email_signal_no_keyword_short(self):
        assert _extract_email_signal("short") is None

    def test_extract_conflict_signal_keyword(self):
        result = _extract_conflict_signal("double booked slot\noverlap detected")
        assert "double" in result

    def test_extract_conflict_signal_no_keyword_long(self):
        result = _extract_conflict_signal("q" * 100)
        assert result == "q" * 100

    def test_extract_conflict_signal_no_keyword_short(self):
        assert _extract_conflict_signal("ok") is None

    def test_extract_financial_signal_keyword(self):
        result = _extract_financial_signal("reconciliation mismatch\nfailed posting")
        assert "mismatch" in result

    def test_extract_financial_signal_no_keyword_long(self):
        result = _extract_financial_signal("r" * 100)
        assert result == "r" * 100

    def test_extract_financial_signal_no_keyword_short(self):
        assert _extract_financial_signal("fine") is None

    def test_extract_support_signal_keyword(self):
        result = _extract_support_signal("ticket escalated\ncsat low")
        assert "escalat" in result

    def test_extract_support_signal_no_keyword_long(self):
        result = _extract_support_signal("s" * 100)
        assert result == "s" * 100

    def test_extract_support_signal_no_keyword_short(self):
        assert _extract_support_signal("fine") is None


class TestBuiltinProfileLambdas:
    def test_operations_extract_signal(self):
        profile = DOMAIN_PROFILES["operations"]
        result = profile.extract_signal("step blocked\nstep timeout\n" + "z" * 400)
        assert "blocked" in result or "timeout" in result

    def test_analytics_extract_signal(self):
        profile = DOMAIN_PROFILES["analytics"]
        result = profile.extract_signal("query error\n" + "z" * 100)
        assert "error" in result

    def test_marketing_extract_signal(self):
        profile = DOMAIN_PROFILES["marketing"]
        result = profile.extract_signal("unsubscribe rate high\n" + "z" * 100)
        assert "unsubscribe" in result

    def test_generic_extract_signal(self):
        profile = DomainProfileRegistry.resolve("totally_unknown_domain")
        result = profile.extract_signal("boom error\n" + "z" * 100)
        assert "error" in result


class TestDomainProfileRegistry:
    @pytest.mark.parametrize("category,name_part", [
        ("engineering", "Software"),
        ("crm", "CRM"),
        ("sales", "Sales"),
        ("scheduling", "Calendar"),
        ("finance", "Financial"),
        ("accounting", "AI Accounting"),
        ("support", "Customer Support"),
        ("operations", "Business Operations"),
        ("analytics", "Data Analytics"),
        ("marketing", "Marketing"),
    ])
    def test_resolves_builtin(self, category, name_part):
        profile = DomainProfileRegistry.resolve(category)
        assert name_part.lower() in profile.name.lower()

    def test_resolves_aliases(self):
        assert DomainProfileRegistry.resolve("software") is DOMAIN_PROFILES["engineering"]
        assert DomainProfileRegistry.resolve("dev") is DOMAIN_PROFILES["engineering"]
        assert DomainProfileRegistry.resolve("coding") is DOMAIN_PROFILES["engineering"]
        assert DomainProfileRegistry.resolve("financial") is DOMAIN_PROFILES["finance"]
        assert DomainProfileRegistry.resolve("customer_support") is DOMAIN_PROFILES["support"]
        assert DomainProfileRegistry.resolve("calendar") is DOMAIN_PROFILES["scheduling"]
        assert DomainProfileRegistry.resolve("crm_sales") is DOMAIN_PROFILES["crm"]

    def test_resolves_none_to_generic(self):
        profile = DomainProfileRegistry.resolve(None)
        assert profile.name == "General Purpose"

    def test_resolves_empty_string_to_generic(self):
        assert DomainProfileRegistry.resolve("").name == "General Purpose"

    def test_resolves_case_and_separator_insensitive(self):
        profile = DomainProfileRegistry.resolve("CRM Sales")
        assert profile.name == "CRM & Sales Outreach"

    def test_resolves_hyphenated(self):
        assert DomainProfileRegistry.resolve("customer-support").name == "Customer Support"

    def test_resolves_unknown_to_generic(self):
        # "legal" is registered at runtime by another suite; use a never-used key.
        profile = DomainProfileRegistry.resolve("quantum_agronomy")
        assert profile.name == "General Purpose"

    def test_list_domains_sorted(self):
        domains = DomainProfileRegistry.list_domains()
        assert domains == sorted(set(DOMAIN_PROFILES.keys()))
        assert "crm" in domains

    def test_domain_quality_weights(self):
        assert DOMAIN_PROFILES["crm"].quality_weight == 1.2
        assert DOMAIN_PROFILES["support"].quality_weight == 1.3
        assert DOMAIN_PROFILES["engineering"].quality_weight == 0.8


class TestGroupReflectionServiceInit:
    def test_init_wires_llm_service(self):
        db = _make_db()
        with patch(
            "core.service_factory.ServiceFactory.get_llm_service",
            return_value="FAKE_LLM",
        ):
            svc = GroupReflectionService(db)
        assert svc.db is db
        assert svc.llm == "FAKE_LLM"


class TestGroupReflectionGather:
    def test_empty_agent_list(self):
        svc = _make_svc(_make_db())
        pool = svc.gather_group_experience_pool([])
        assert pool["agent_count"] == 0
        assert pool["trace_count"] == 0
        assert pool["_category"] is None
        assert pool["_domain_profile"].name == "General Purpose"

    def test_auto_detect_category_from_agent(self):
        agent = MagicMock()
        agent.category = "crm"
        db = _make_db(agents=[agent])
        svc = _make_svc(db)
        pool = svc.gather_group_experience_pool(["a1"], category=None)
        assert pool["_category"] == "crm"
        assert pool["_domain_profile"].name == "CRM & Sales Outreach"

    def test_auto_detect_category_agent_missing(self):
        db = _make_db(agents=[None])
        svc = _make_svc(db)
        pool = svc.gather_group_experience_pool(["a1"])
        assert pool["_category"] is None

    def test_category_override_wins(self):
        db = _make_db(agents=[MagicMock(category="crm")])
        svc = _make_svc(db)
        pool = svc.gather_group_experience_pool(["a1"], category="finance")
        assert pool["_category"] == "finance"

    def test_filtered_low_quality_trace(self):
        trace = _make_trace(is_high_quality=False)
        svc = _make_svc(_make_db(traces=[trace]))
        pool = svc.gather_group_experience_pool(["a1"], category="crm")
        assert pool["trace_count"] == 0
        assert pool["filtered_count"] == 1

    def test_filtered_low_score_trace(self):
        trace = _make_trace(benchmark_score=0.1, is_high_quality=True)
        svc = _make_svc(_make_db(traces=[trace]))
        pool = svc.gather_group_experience_pool(["a1"], category="crm")
        assert pool["trace_count"] == 0
        assert pool["filtered_count"] == 1

    def test_domain_weighted_gate_filters_higher(self):
        # crm quality_weight=1.2 → threshold 0.36; score 0.4 passes standard
        # gate but fails the stricter crm gate.
        trace = _make_trace(benchmark_score=0.34)
        svc = _make_svc(_make_db(traces=[trace]))
        pool = svc.gather_group_experience_pool(["a1"], category="crm")
        assert pool["trace_count"] == 0
        assert pool["filtered_count"] == 1

    def test_trace_with_none_score_passes(self):
        trace = _make_trace(benchmark_score=None)
        svc = _make_svc(_make_db(traces=[trace]))
        pool = svc.gather_group_experience_pool(["a1"], category="crm")
        assert pool["trace_count"] == 1

    def test_pool_assembly_full(self):
        trace = _make_trace(
            tool_use_log=[
                {"tool_name": "bash", "success": True},
                {"tool_name": None, "success": False},
                {"success": True},
            ],
            task_log="bounce occurred in campaign",
            evolving_requirements="Use better subject lines",
        )
        svc = _make_svc(_make_db(traces=[trace]))
        pool = svc.gather_group_experience_pool(["a1"], category="crm")
        assert pool["trace_count"] == 1
        assert len(pool["tool_patterns"]) == 3
        assert pool["tool_patterns"][0]["tool_name"] == "bash"
        assert pool["tool_patterns"][1]["tool_name"] is None
        assert pool["tool_patterns"][2]["success"] is True
        assert any("bounce" in e for e in pool["task_log_excerpts"])
        assert pool["successful_patches"] == ["+ some fix"]
        assert "Use better subject lines" in pool["evolving_requirements"]

    def test_pool_skips_absent_fields(self):
        trace = MagicMock()
        trace.is_high_quality = True
        trace.benchmark_score = 0.9
        trace.tool_use_log = None
        trace.task_log = None
        trace.benchmark_passed = False
        trace.model_patch = None
        trace.evolving_requirements = None
        svc = _make_svc(_make_db(traces=[trace]))
        pool = svc.gather_group_experience_pool(["a1"], category="engineering")
        assert pool["trace_count"] == 1
        assert pool["tool_patterns"] == []
        assert pool["task_log_excerpts"] == []
        assert pool["successful_patches"] == []
        assert pool["evolving_requirements"] == []

    def test_patches_deduped(self):
        t1 = _make_trace(model_patch="+ identical patch content")
        t2 = _make_trace(model_patch="+ identical patch content")
        svc = _make_svc(_make_db(traces=[t1, t2]))
        pool = svc.gather_group_experience_pool(["a1", "a2"], category="engineering")
        assert len(pool["successful_patches"]) == 1

    def test_custom_profile_default_extractor(self):
        trace = _make_trace(task_log="z" * 200)
        svc = _make_svc(_make_db(traces=[trace]))
        GroupReflectionService.register_domain("w83custom", DomainProfile(
            name="Custom",
            success_label="done well",
            failure_label="went wrong",
            patch_label="config change",
            prompt_preamble="Custom preamble.",
            extract_signal=None,
        ))
        pool = svc.gather_group_experience_pool(["a1"], category="w83custom")
        assert pool["trace_count"] == 1
        assert len(pool["task_log_excerpts"]) == 1

    def test_quality_gate_direct_calls(self):
        svc = _make_svc(_make_db())
        low = _make_trace(is_high_quality=False)
        assert svc._passes_quality_gate(low) is False
        low_score = _make_trace(benchmark_score=0.1)
        assert svc._passes_quality_gate(low_score) is False
        none_score = _make_trace(benchmark_score=None)
        assert svc._passes_quality_gate(none_score) is True
        good = _make_trace(benchmark_score=0.9)
        assert svc._passes_quality_gate(good) is True

    def test_detect_category_direct(self):
        agent = MagicMock()
        agent.category = "sales"
        svc = _make_svc(_make_db(agents=[agent]))
        assert svc._detect_category(["a1"]) == "sales"
        assert svc._detect_category([]) is None
        empty_db = _make_db(agents=[None])
        assert _make_svc(empty_db)._detect_category(["a1"]) is None

    def test_max_traces_limit_applied(self):
        svc = _make_svc(_make_db(traces=[_make_trace()]))
        pool = svc.gather_group_experience_pool(["a1"], max_traces_per_agent=3)
        assert pool["trace_count"] == 1
        assert pool["agent_count"] == 1


class TestReflectAndGenerateDirectives:
    async def test_empty_pool_bootstrap_with_category(self):
        svc = _make_svc(_make_db())
        pool = {
            "agent_count": 0, "trace_count": 0,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
        }
        directives = await svc.reflect_and_generate_directives(pool, category="crm")
        assert len(directives) == 1
        assert "Improve" in directives[0]

    async def test_empty_pool_bootstrap_resolves_generic(self):
        svc = _make_svc(_make_db())
        pool = {
            "agent_count": 0, "trace_count": 0,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_category": "unknown-domain",
        }
        directives = await svc.reflect_and_generate_directives(pool, category=None)
        assert len(directives) == 1

    async def test_success_generates_directives(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(
            return_value="1. First directive\n\n2. Second directive\n3. Third directive"
        )
        svc = _make_svc(_make_db())
        svc.llm = llm
        pool = {
            "agent_count": 2, "trace_count": 3,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_domain_profile": DomainProfileRegistry.resolve("crm"),
            "_category": "crm",
        }
        directives = await svc.reflect_and_generate_directives(
            pool, tenant_id="t-1", max_directives=2
        )
        assert directives == ["First directive", "Second directive"]
        llm.generate_response.assert_awaited_once()
        kwargs = llm.generate_response.await_args.kwargs
        assert kwargs["tenant_id"] == "t-1"
        assert len(kwargs["messages"]) == 2

    async def test_success_content_none(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value=None)
        svc = _make_svc(_make_db())
        svc.llm = llm
        pool = {
            "agent_count": 1, "trace_count": 1,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_domain_profile": DomainProfileRegistry.resolve("finance"),
        }
        directives = await svc.reflect_and_generate_directives(pool)
        assert directives == []

    async def test_llm_error_fallback(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(side_effect=RuntimeError("LLM down"))
        svc = _make_svc(_make_db())
        svc.llm = llm
        pool = {
            "agent_count": 2, "trace_count": 2,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_category": "support",
        }
        directives = await svc.reflect_and_generate_directives(pool)
        assert len(directives) == 1
        assert "Maintain current behavior" in directives[0]

    async def test_profile_resolved_from_category_when_not_in_pool(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="1. Do a thing")
        svc = _make_svc(_make_db())
        svc.llm = llm
        pool = {
            "agent_count": 1, "trace_count": 1,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
        }
        directives = await svc.reflect_and_generate_directives(pool, category="engineering")
        assert directives == ["Do a thing"]


class TestParseDirectives:
    def test_parse_numbered_list(self):
        svc = _make_svc(_make_db())
        result = svc._parse_directives("1. alpha\n2) beta\n- gamma\n• delta", 10)
        assert result == ["alpha", "beta", "gamma", "delta"]

    def test_parse_skips_empty_lines(self):
        svc = _make_svc(_make_db())
        result = svc._parse_directives("1. alpha\n\n   \n2. beta", 10)
        assert result == ["alpha", "beta"]

    def test_parse_respects_max(self):
        svc = _make_svc(_make_db())
        result = svc._parse_directives("1. a\n2. b\n3. c\n4. d\n5. e", 3)
        assert result == ["a", "b", "c"]

    def test_parse_blank_response(self):
        svc = _make_svc(_make_db())
        assert svc._parse_directives("   ", 5) == []
        assert svc._parse_directives("", 5) == []

    def test_parse_keeps_non_enumered_lines(self):
        svc = _make_svc(_make_db())
        result = svc._parse_directives("plain line\n2. numbered", 5)
        assert result == ["plain line", "numbered"]


class TestReflectionPrompt:
    def test_build_prompt_full(self):
        svc = _make_svc(_make_db())
        profile = DomainProfileRegistry.resolve("crm")
        pool = {
            "agent_count": 3, "trace_count": 2,
            "tool_patterns": [{"tool_name": "send_email", "success": True}],
            "task_log_excerpts": ["bounce received"],
            "successful_patches": ["+ patch content"],
            "evolving_requirements": ["Reduce follow-up cadence"],
            "_domain_profile": profile, "_category": "crm",
        }
        prompt = svc._build_reflection_prompt(pool, profile, 3)
        assert "CRM" in prompt
        assert "bounce received" in prompt
        assert "+ patch content" in prompt
        assert "Reduce follow-up cadence" in prompt
        assert "CREATE_SKILL" in prompt
        assert "exactly 3 concrete evolution directives" in prompt

    def test_build_prompt_empty_sections(self):
        svc = _make_svc(_make_db())
        profile = DomainProfileRegistry.resolve("engineering")
        pool = {
            "agent_count": 1, "trace_count": 0,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_domain_profile": profile, "_category": "engineering",
        }
        prompt = svc._build_reflection_prompt(pool, profile, 2)
        assert "No tool usage data available." in prompt
        assert "No successful" in prompt
        assert "No failure signals captured." in prompt
        assert "None — this is the first generation." in prompt

    def test_summarize_tool_patterns_empty(self):
        svc = _make_svc(_make_db())
        assert svc._summarize_tool_patterns([], DOMAIN_PROFILES["crm"]) == (
            "No tool usage data available."
        )

    def test_summarize_tool_patterns_star_and_unknown(self):
        svc = _make_svc(_make_db())
        summary = svc._summarize_tool_patterns([
            {"tool_name": "hubspot", "success": True},
            {"tool_name": "hubspot", "success": False},
            {"tool_name": None, "success": True},
        ], DOMAIN_PROFILES["crm"])
        assert "hubspot ★" in summary
        assert "unknown" in summary
        assert "2 calls, 50% success rate" in summary

    def test_summarize_sorted_by_total(self):
        svc = _make_svc(_make_db())
        summary = svc._summarize_tool_patterns([
            {"tool_name": "a", "success": True},
            {"tool_name": "b", "success": True},
            {"tool_name": "b", "success": True},
        ], DOMAIN_PROFILES["crm"])
        assert summary.index("b:") < summary.index("a:")


class TestDomainRegistration:
    def test_list_supported_domains(self):
        domains = GroupReflectionService.list_supported_domains()
        assert "crm" in domains
        assert isinstance(domains, list)

    def test_register_domain_and_resolve(self):
        GroupReflectionService.register_domain("w83legal", DomainProfile(
            name="Legal Review",
            success_label="clause extracted",
            failure_label="missed clause",
            patch_label="rule change",
            prompt_preamble="Legal preamble.",
            quality_weight=1.5,
        ))
        profile = DomainProfileRegistry.resolve("W83LEGAL")
        assert profile.name == "Legal Review"
        assert profile.quality_weight == 1.5
        assert profile.extract_signal is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. core/hypothesis_tree.py
# ─────────────────────────────────────────────────────────────────────────────

from core.hypothesis_tree import (
    CodeHypothesisNode,
    HypothesisNode,
    HypothesisTree,
    NodeMetrics,
    NodeStatus,
    OptimizationNode,
    OptimizationTree,
    PruningReason,
    RoutingHypothesisNode,
    TaskType,
    TreeSearchParams,
    WorkflowHypothesisNode,
    _now_utc,
)


class TestNodeMetrics:
    def test_lt_true(self):
        a = NodeMetrics(execution_time_ms=10, test_pass_rate=0.9, cpu_percent=5)
        b = NodeMetrics(execution_time_ms=20, test_pass_rate=0.8, cpu_percent=10)
        assert a < b

    def test_lt_false_slower(self):
        a = NodeMetrics(execution_time_ms=30, test_pass_rate=0.9, cpu_percent=5)
        b = NodeMetrics(execution_time_ms=20, test_pass_rate=0.8, cpu_percent=10)
        assert not (a < b)

    def test_lt_false_lower_pass_rate(self):
        a = NodeMetrics(execution_time_ms=10, test_pass_rate=0.7, cpu_percent=5)
        b = NodeMetrics(execution_time_ms=20, test_pass_rate=0.8, cpu_percent=10)
        assert not (a < b)

    def test_lt_false_higher_cpu(self):
        a = NodeMetrics(execution_time_ms=10, test_pass_rate=0.9, cpu_percent=50)
        b = NodeMetrics(execution_time_ms=20, test_pass_rate=0.8, cpu_percent=10)
        assert not (a < b)

    def test_lt_equal_metrics_false(self):
        a = NodeMetrics(execution_time_ms=10, test_pass_rate=0.9, cpu_percent=5)
        b = NodeMetrics(execution_time_ms=10, test_pass_rate=0.9, cpu_percent=5)
        assert not (a < b)

    def test_total_ordering_sorted(self):
        metrics = [
            NodeMetrics(execution_time_ms=50, test_pass_rate=0.5),
            NodeMetrics(execution_time_ms=10, test_pass_rate=1.0),
        ]
        assert sorted(metrics)[0].execution_time_ms == 10

    def test_defaults(self):
        m = NodeMetrics()
        assert m.cost_usd == 0.0
        assert m.tokens_used == 0


class TestHypothesisNode:
    def test_defaults(self):
        node = HypothesisNode()
        assert node.status == NodeStatus.PENDING
        assert node.children == []
        assert node.promise_score == 0.5
        assert node.created_at is not None
        assert node.id

    def test_is_leaf(self):
        node = HypothesisNode()
        assert node.is_leaf() is True
        node.children.append("c1")
        assert node.is_leaf() is False

    def test_is_successful(self):
        assert HypothesisNode(status=NodeStatus.SUCCESS).is_successful() is True
        assert HypothesisNode(status=NodeStatus.FAILED).is_successful() is False

    def test_is_failed(self):
        assert HypothesisNode(status=NodeStatus.FAILED).is_failed() is True
        assert HypothesisNode(status=NodeStatus.PRUNED).is_failed() is True
        assert HypothesisNode(status=NodeStatus.PENDING).is_failed() is False

    def test_ucb1_zero_visits_inf(self):
        node = HypothesisNode()
        assert node.get_ucb1_score() == float("inf")

    def test_ucb1_with_parent_visits(self):
        node = HypothesisNode(visit_count=4, total_value=2.0)
        score = node.get_ucb1_score(exploration_constant=1.41, parent_visits=16)
        import math
        expected = 0.5 + 1.41 * math.sqrt(math.log(16) / 4)
        assert score == pytest.approx(expected, rel=1e-3)

    def test_ucb1_falls_back_to_own_visits(self):
        import math
        node = HypothesisNode(visit_count=9, total_value=0.0)
        score = node.get_ucb1_score()
        assert score == pytest.approx(1.41 * math.sqrt(math.log(9) / 9), rel=1e-3)
        assert score > 0

    def test_calculate_promise_score_default(self):
        node = HypothesisNode(depth=0)
        assert node.calculate_promise_score() == pytest.approx(0.4)

    def test_calculate_promise_score_execution_clamp(self):
        node = HypothesisNode(depth=0)
        node.metrics.execution_time_ms = 20000
        node.metrics.test_pass_rate = 1.0
        assert node.calculate_promise_score() == pytest.approx(0.3)

    def test_calculate_promise_score_depth_and_lint(self):
        node = HypothesisNode(depth=5)
        node.metrics.execution_time_ms = 0
        node.metrics.test_pass_rate = 1.0
        node.metrics.lint_errors = 10
        score = node.calculate_promise_score()
        assert score == pytest.approx(0.7 / 1.5 / 2.0)

    def test_calculate_promise_score_upper_clamp(self):
        node = HypothesisNode(depth=0)
        node.metrics.execution_time_ms = 0
        node.metrics.test_pass_rate = 1.0
        assert node.calculate_promise_score(
            metrics_weight=0.6, tests_weight=0.5, depth_penalty=0.0, lint_penalty=0.0
        ) == pytest.approx(1.0)

    def test_calculate_promise_score_lower_clamp(self):
        node = HypothesisNode(depth=0)
        node.metrics.execution_time_ms = 10 ** 9
        node.metrics.test_pass_rate = 0.0
        assert node.calculate_promise_score() == pytest.approx(0.0)

    def test_to_dict_full(self):
        node = HypothesisNode(
            id="n1",
            parent_id="p1",
            depth=2,
            status=NodeStatus.SUCCESS,
            pruning_reason=PruningReason.LINT_FAILED,
            hypothesis="diff",
            description="desc",
            file_path="x.py",
            lint_output="warn",
            test_results={"t1": True},
            error_message=None,
            promise_score=0.8,
            visit_count=3,
            total_value=1.5,
            children=["c1"],
            session_id="s1",
            learning_tags=["tag"],
        )
        node.metrics.tokens_used = 100
        node.metrics.cost_usd = 0.01
        d = node.to_dict()
        assert d["id"] == "n1"
        assert d["status"] == "success"
        assert d["pruning_reason"] == "lint_failed"
        assert d["test_results"] == {"t1": True}
        assert d["metrics"]["tokens_used"] == 100
        assert d["children"] == ["c1"]
        assert d["learning_tags"] == ["tag"]
        assert d["created_at"] is not None
        assert d["updated_at"] is not None

    def test_to_dict_no_pruning_reason(self):
        node = HypothesisNode()
        assert node.to_dict()["pruning_reason"] is None

    def test_to_dict_none_datetimes(self):
        node = HypothesisNode()
        node.created_at = None
        node.updated_at = None
        d = node.to_dict()
        assert d["created_at"] is None
        assert d["updated_at"] is None

    def test_from_dict_full(self):
        data = {
            "id": "n1",
            "parent_id": "p1",
            "depth": 1,
            "status": "failed",
            "pruning_reason": "test_failed",
            "hypothesis": "h",
            "description": "d",
            "file_path": "f.py",
            "lint_output": "o",
            "test_results": {"a": False},
            "error_message": "err",
            "metrics": {
                "execution_time_ms": 5.0,
                "cpu_percent": 2.0,
                "memory_mb": 3.0,
                "tokens_used": 7,
                "test_pass_rate": 0.5,
                "lint_errors": 1,
                "lint_warnings": 2,
                "lines_changed": 10,
            },
            "promise_score": 0.9,
            "visit_count": 4,
            "total_value": 2.0,
            "children": ["c1"],
            "session_id": "s1",
            "learning_tags": ["t"],
        }
        node = HypothesisNode.from_dict(data)
        assert node.id == "n1"
        assert node.parent_id == "p1"
        assert node.status == NodeStatus.FAILED
        assert node.pruning_reason == PruningReason.TEST_FAILED
        assert node.metrics.tokens_used == 7
        assert node.metrics.test_pass_rate == 0.5
        assert node.visit_count == 4
        assert node.children == ["c1"]

    def test_from_dict_minimal(self):
        node = HypothesisNode.from_dict({"id": "x"})
        assert node.id == "x"
        assert node.status == NodeStatus.PENDING
        assert node.pruning_reason is None
        assert node.metrics.execution_time_ms == 0.0
        assert node.promise_score == 0.5

    def test_now_utc_aware(self):
        dt = _now_utc()
        assert dt.tzinfo is not None


class TestOptimizationNode:
    def test_multi_objective_score(self):
        node = OptimizationNode(quality_score=1.0, cost_score=0.0, latency_score=0.0, depth=0)
        assert node.calculate_multi_objective_score() == pytest.approx(1.0 * 0.4 + 0.3 + 0.2)

    def test_multi_objective_score_clamps(self):
        node = OptimizationNode(quality_score=1.0, cost_score=0.0, latency_score=0.0, depth=0)
        assert node.calculate_multi_objective_score(
            quality_weight=0.6, cost_weight=0.4, latency_weight=0.4
        ) == pytest.approx(1.0)
        node2 = OptimizationNode(quality_score=0.0, cost_score=1.0, latency_score=1.0, depth=0)
        assert node2.calculate_multi_objective_score() == pytest.approx(0.0)

    def test_multi_objective_depth_penalty(self):
        node = OptimizationNode(quality_score=1.0, cost_score=0.0, latency_score=0.0, depth=9)
        assert node.calculate_multi_objective_score() == pytest.approx(0.9 / (1 + 0.9))

    def test_to_dict_with_enum(self):
        node = OptimizationNode(task_type=TaskType.WORKFLOW, domain_metadata={"k": "v"})
        d = node.to_dict()
        assert d["task_type"] == "workflow"
        assert d["domain_metadata"] == {"k": "v"}
        assert d["budget_used"] == 0.0
        assert d["quality_score"] == 0.0

    def test_to_dict_with_string_task_type(self):
        node = OptimizationNode(task_type="routing")
        assert node.to_dict()["task_type"] == "routing"

    def test_default_task_type_coding(self):
        assert OptimizationNode().task_type == TaskType.CODING


class TestCodeHypothesisNode:
    def test_calculate_promise_score(self):
        node = CodeHypothesisNode(
            quality_score=1.0, cost_score=0.0, latency_score=0.0,
            cyclomatic_complexity=4, security_vulnerabilities=1, security_hotspots=2,
        )
        score = node.calculate_promise_score()
        base = 0.9
        assert score == pytest.approx(base * (1 - 0.2 * 0.3) * (1 - 0.4 * 0.5))

    def test_calculate_promise_score_penalties_capped(self):
        node = CodeHypothesisNode(
            quality_score=1.0, cost_score=0.0, latency_score=0.0,
            cyclomatic_complexity=100, security_vulnerabilities=10, security_hotspots=10,
        )
        assert 0.0 <= node.calculate_promise_score() <= 1.0

    def test_defaults(self):
        node = CodeHypothesisNode()
        assert node.task_type == TaskType.CODING
        assert node.language == ""
        assert node.code_coverage == 0.0


class TestWorkflowHypothesisNode:
    def test_calculate_promise_score(self):
        node = WorkflowHypothesisNode(
            parallelizable_ratio=1.0, cost_optimization_potential=1.0,
            cache_hit_rate_improvement=1.0,
            estimated_throughput_rps=100.0, estimated_latency_ms=0.0,
        )
        assert node.calculate_promise_score() == pytest.approx(1.0)

    def test_calculate_promise_score_clamped(self):
        node = WorkflowHypothesisNode(
            parallelizable_ratio=1.0, cost_optimization_potential=1.0,
            cache_hit_rate_improvement=1.0,
            estimated_throughput_rps=100.0, estimated_latency_ms=0.0,
        )
        assert node.calculate_promise_score() <= 1.0

    def test_calculate_promise_score_latency_zero(self):
        node = WorkflowHypothesisNode(estimated_throughput_rps=0.0, estimated_latency_ms=10 ** 9)
        assert node.calculate_promise_score() == pytest.approx(0.0)

    def test_defaults(self):
        node = WorkflowHypothesisNode()
        assert node.task_type == TaskType.WORKFLOW
        assert node.parallel_steps == []


class TestRoutingHypothesisNode:
    def test_calculate_promise_score_no_bonuses(self):
        node = RoutingHypothesisNode()
        score = node.calculate_promise_score()
        assert score == pytest.approx(0.2 * 0.5 + 0.3 + 0.15)

    def test_calculate_promise_score_full(self):
        node = RoutingHypothesisNode(
            accuracy_score=1.0, consistency_score=1.0, hallucination_risk=0.0,
            cost_per_1k_tokens=0.0, p95_latency_ms=0.0,
            caching_enabled=True, streaming_enabled=True,
        )
        score = node.calculate_promise_score()
        assert score == pytest.approx(1.0)

    def test_calculate_promise_score_clamped(self):
        node = RoutingHypothesisNode(
            accuracy_score=1.0, consistency_score=1.0, hallucination_risk=0.0,
            cost_per_1k_tokens=0.0, p95_latency_ms=0.0,
            caching_enabled=True, streaming_enabled=True,
        )
        assert 0.0 <= node.calculate_promise_score() <= 1.0

    def test_defaults(self):
        node = RoutingHypothesisNode()
        assert node.task_type == TaskType.ROUTING
        assert node.fallback_enabled is True
        assert node.caching_enabled is False
        assert node.model_sequence == []


class TestHypothesisTree:
    def test_default_tier_solo(self):
        tree = HypothesisTree()
        assert tree.max_nodes == 8
        assert tree.max_tokens == 10000
        assert tree.max_cost_usd == 0.50
        assert tree.tier == "solo"

    def test_post_init_free_tier(self):
        tree = HypothesisTree(tier="free")
        assert tree.max_nodes == 3
        assert tree.max_tokens == 5000
        assert tree.max_cost_usd == 0.25

    def test_post_init_enterprise_tier(self):
        tree = HypothesisTree(tier="enterprise")
        assert tree.max_nodes == 20
        assert tree.max_tokens == 50000
        assert tree.max_cost_usd == 2.00

    def test_set_tier_budget_all_tiers(self):
        tree = HypothesisTree()
        tree.set_tier_budget("free")
        assert (tree.max_nodes, tree.max_tokens, tree.max_cost_usd) == (3, 5000, 0.25)
        tree.set_tier_budget("solo")
        assert (tree.max_nodes, tree.max_tokens, tree.max_cost_usd) == (8, 10000, 0.50)
        tree.set_tier_budget("enterprise")
        assert (tree.max_nodes, tree.max_tokens, tree.max_cost_usd) == (20, 50000, 2.00)

    def test_set_tier_budget_unknown_keeps_limits(self):
        tree = HypothesisTree()
        tree.set_tier_budget("mega")
        assert tree.tier == "mega"
        assert tree.max_nodes == 8

    def test_add_node_success_and_parent_link(self):
        tree = HypothesisTree()
        parent = HypothesisNode()
        child = HypothesisNode(parent_id=parent.id)
        assert tree.add_node(parent) is True
        assert tree.add_node(child) is True
        assert tree.nodes[parent.id].children == [child.id]
        assert tree.total_tokens_used == child.metrics.tokens_used
        assert tree.updated_at is not None

    def test_add_node_node_budget_exceeded(self):
        tree = HypothesisTree(tier="free")  # max_nodes=3
        for _ in range(3):
            assert tree.add_node(HypothesisNode()) is True
        assert tree.add_node(HypothesisNode()) is False

    def test_add_node_token_budget_exceeded(self):
        tree = HypothesisTree()
        node = HypothesisNode()
        node.metrics.tokens_used = 99999
        assert tree.add_node(node) is False

    def test_add_node_cost_budget_exceeded(self):
        tree = HypothesisTree()
        big = HypothesisNode()
        big.metrics.cost_usd = 1.0
        assert tree.add_node(big) is True
        assert tree.total_cost_usd == 1.0
        small = HypothesisNode()
        assert tree.add_node(small) is False

    def test_add_node_parent_missing(self):
        tree = HypothesisTree()
        node = HypothesisNode(parent_id="ghost")
        assert tree.add_node(node) is True
        assert tree.nodes[node.id] is node

    def test_get_node(self):
        tree = HypothesisTree()
        node = HypothesisNode()
        tree.add_node(node)
        assert tree.get_node(node.id) is node
        assert tree.get_node("missing") is None

    def test_get_children(self):
        tree = HypothesisTree()
        parent = HypothesisNode()
        child = HypothesisNode(parent_id=parent.id)
        tree.add_node(parent)
        tree.add_node(child)
        assert tree.get_children(parent.id) == [child]
        assert tree.get_children("missing") == []

    def test_get_children_skips_missing_ids(self):
        tree = HypothesisTree()
        parent = HypothesisNode()
        tree.add_node(parent)
        parent.children.append("ghost")
        assert tree.get_children(parent.id) == []

    def test_get_path_to_root(self):
        tree = HypothesisTree()
        a = HypothesisNode()
        b = HypothesisNode(parent_id=a.id)
        c = HypothesisNode(parent_id=b.id)
        for n in (a, b, c):
            tree.add_node(n)
        assert tree.get_path_to_root(c.id) == [a.id, b.id, c.id]
        assert tree.get_path_to_root(a.id) == [a.id]
        assert tree.get_path_to_root("missing") == ["missing"]

    def test_get_path_to_root_breaks_on_missing_node(self):
        tree = HypothesisTree()
        a = HypothesisNode()
        tree.add_node(a)
        c = HypothesisNode(parent_id="ghost-parent")
        tree.add_node(c)
        assert tree.get_path_to_root(c.id) == ["ghost-parent", c.id]

    def test_get_successful_path(self):
        tree = HypothesisTree()
        a = HypothesisNode()
        b = HypothesisNode(parent_id=a.id, status=NodeStatus.SUCCESS)
        for n in (a, b):
            tree.add_node(n)
        assert tree.get_successful_path() == [a.id, b.id]

    def test_get_successful_path_none(self):
        tree = HypothesisTree()
        tree.add_node(HypothesisNode())
        assert tree.get_successful_path() == []

    def test_prune_branch(self):
        tree = HypothesisTree()
        a = HypothesisNode()
        b = HypothesisNode(parent_id=a.id)
        tree.add_node(a)
        tree.add_node(b)
        assert tree.prune_branch(a.id, PruningReason.LOW_PROMISE) == 2
        assert a.status == NodeStatus.PRUNED
        assert b.status == NodeStatus.PRUNED
        assert a.pruning_reason == PruningReason.LOW_PROMISE

    def test_prune_branch_missing_id(self):
        tree = HypothesisTree()
        assert tree.prune_branch("missing", PruningReason.MANUAL) == 0

    def test_prune_branch_skips_missing_children(self):
        tree = HypothesisTree()
        a = HypothesisNode()
        tree.add_node(a)
        a.children.append("ghost")
        assert tree.prune_branch(a.id, PruningReason.MANUAL) == 1

    def test_add_negative_constraint(self):
        tree = HypothesisTree()
        tree.add_negative_constraint("use redis")
        tree.add_negative_constraint("use redis")
        assert tree.negative_constraints == ["use redis"]

    def test_violates_constraint(self):
        tree = HypothesisTree()
        tree.add_negative_constraint("EVAL")
        assert tree.violates_constraint("never call eval") is True
        assert tree.violates_constraint("use safe math") is False

    def test_calculate_tree_cost(self):
        tree = HypothesisTree()
        tree.total_tokens_used = 1_000_000
        assert tree.calculate_tree_cost() == pytest.approx(0.50)
        assert tree.calculate_tree_cost(cost_per_million=1.0) == pytest.approx(1.0)

    def test_get_statistics(self):
        tree = HypothesisTree()
        tree.total_nodes_expanded = 4
        tree.add_node(HypothesisNode(status=NodeStatus.SUCCESS, depth=0))
        tree.add_node(HypothesisNode(status=NodeStatus.FAILED, depth=1))
        tree.add_node(HypothesisNode(status=NodeStatus.PRUNED, depth=2))
        tree.add_node(HypothesisNode(depth=3))
        stats = tree.get_statistics()
        assert stats["total_nodes"] == 4
        assert stats["successful_nodes"] == 1
        assert stats["failed_nodes"] == 2  # FAILED + PRUNED both count as failed
        assert stats["pruned_nodes"] == 1
        assert stats["pending_nodes"] == 0
        assert stats["average_depth"] == pytest.approx(1.5)
        assert stats["max_depth"] == 3
        assert stats["tier"] == "solo"
        assert stats["complexity_level"] == "standard"

    def test_get_statistics_empty_tree(self):
        stats = HypothesisTree().get_statistics()
        assert stats["total_nodes"] == 0
        assert stats["average_depth"] == 0
        assert stats["max_depth"] == 0

    def test_to_dict(self):
        tree = HypothesisTree(task_id="t1")
        node = HypothesisNode()
        tree.add_node(node)
        tree.completed_at = _now_utc()
        d = tree.to_dict()
        assert d["task_id"] == "t1"
        assert d["nodes"][node.id]["id"] == node.id
        assert d["completed_at"] is not None
        assert d["statistics"]["total_nodes"] == 1

    def test_to_dict_none_completed_at(self):
        d = HypothesisTree().to_dict()
        assert d["completed_at"] is None

    def test_from_dict_with_nodes(self):
        node = HypothesisNode(status=NodeStatus.SUCCESS, hypothesis="h1")
        data = {
            "id": "tree1",
            "root_id": node.id,
            "task_id": "task1",
            "task_description": "desc",
            "complexity_level": "high",
            "winning_path": [node.id],
            "total_nodes_expanded": 2,
            "total_tokens_used": 100,
            "total_cost_usd": 0.1,
            "session_id": "s1",
            "learning_insights": ["i1"],
            "negative_constraints": ["c1"],
            "tier": "enterprise",
            "nodes": {node.id: node.to_dict()},
        }
        tree = HypothesisTree.from_dict(data)
        assert tree.id == "tree1"
        assert tree.root_id == node.id
        assert tree.complexity_level == "high"
        assert tree.tier == "enterprise"
        assert tree.total_nodes_expanded == 2
        assert tree.nodes[node.id].status == NodeStatus.SUCCESS
        assert tree.nodes[node.id].hypothesis == "h1"

    def test_from_dict_no_nodes(self):
        tree = HypothesisTree.from_dict({"id": "t"})
        assert tree.nodes == {}
        assert tree.tier == "solo"

    def test_tree_search_params_defaults(self):
        p = TreeSearchParams()
        assert p.algorithm == "best_first"
        assert p.beam_width == 3
        assert p.exploration_constant == 1.41
        assert p.promise_threshold == 0.3
        assert p.max_depth == 5
        assert p.validate_lint is True
        assert p.prune_on_latency_regression is False
        assert p.latency_threshold_ms == 1000.0
        assert p.parallel_validation is True
        assert p.max_parallel_tasks == 4
        assert p.use_historical_insights is True
        assert p.track_metrics is True
        assert p.export_tree is True


class TestOptimizationTree:
    def test_post_init_default_coding(self):
        tree = OptimizationTree()
        assert tree.task_type == TaskType.CODING
        assert tree.max_nodes == 8

    def test_post_init_workflow_budget(self):
        tree = OptimizationTree(task_type=TaskType.WORKFLOW)
        assert tree.max_nodes == 5
        assert tree.max_cost_usd == 0.30

    def test_post_init_routing_budget(self):
        tree = OptimizationTree(task_type=TaskType.ROUTING)
        assert tree.max_nodes == 12
        assert tree.max_cost_usd == 0.80

    def test_create_node_coding(self):
        tree = OptimizationTree()
        node = tree.create_node(TaskType.CODING, code_diff="+x")
        assert isinstance(node, CodeHypothesisNode)
        assert node.task_type == TaskType.CODING
        assert node.code_diff == "+x"

    def test_create_node_workflow(self):
        tree = OptimizationTree()
        node = tree.create_node(TaskType.WORKFLOW, parallel_steps=["s1"])
        assert isinstance(node, WorkflowHypothesisNode)
        assert node.parallel_steps == ["s1"]

    def test_create_node_routing(self):
        tree = OptimizationTree()
        node = tree.create_node(TaskType.ROUTING, model_sequence=["m1"])
        assert isinstance(node, RoutingHypothesisNode)
        assert node.model_sequence == ["m1"]

    def test_create_node_unknown_type(self):
        tree = OptimizationTree()
        node = tree.create_node("bogus", quality_score=0.5)
        assert isinstance(node, OptimizationNode)
        assert node.quality_score == 0.5

    def test_create_node_default_type(self):
        tree = OptimizationTree()
        node = tree.create_node()
        assert isinstance(node, CodeHypothesisNode)

    def test_get_domain_statistics_coding(self):
        tree = OptimizationTree(task_type=TaskType.CODING)
        n1 = CodeHypothesisNode(language="python", cyclomatic_complexity=4)
        n1.domain_metadata["lines_changed"] = 10
        n2 = CodeHypothesisNode(language="python", cyclomatic_complexity=8)
        n2.domain_metadata["lines_changed"] = 20
        tree.add_node(n1)
        tree.add_node(n2)
        stats = tree.get_domain_statistics()
        assert stats["total_lines_changed"] == 30
        assert stats["languages_used"] == ["python"]
        assert stats["avg_complexity"] == pytest.approx(6.0)

    def test_get_domain_statistics_coding_empty(self):
        tree = OptimizationTree(task_type=TaskType.CODING)
        stats = tree.get_domain_statistics()
        assert stats["total_lines_changed"] == 0
        assert stats["languages_used"] == []
        assert stats["avg_complexity"] == 0

    def test_get_domain_statistics_workflow(self):
        tree = OptimizationTree(task_type=TaskType.WORKFLOW)
        n1 = WorkflowHypothesisNode(parallel_steps=["a", "b"])
        n1.domain_metadata["latency_reduction"] = 0.5
        n2 = WorkflowHypothesisNode(parallel_steps=["c"])
        n2.domain_metadata["latency_reduction"] = 0.3
        tree.add_node(n1)
        tree.add_node(n2)
        stats = tree.get_domain_statistics()
        assert stats["total_parallel_steps"] == 3
        assert stats["avg_latency_reduction"] == pytest.approx(0.4)

    def test_get_domain_statistics_workflow_empty(self):
        tree = OptimizationTree(task_type=TaskType.WORKFLOW)
        stats = tree.get_domain_statistics()
        assert stats["total_parallel_steps"] == 0
        assert stats["avg_latency_reduction"] == 0

    def test_get_domain_statistics_routing(self):
        tree = OptimizationTree(task_type=TaskType.ROUTING)
        n1 = RoutingHypothesisNode(
            model_sequence=["gpt-4o", "claude"], cost_per_1k_tokens=0.01,
            p95_latency_ms=100.0,
        )
        n2 = RoutingHypothesisNode(
            model_sequence=["gpt-4o"], cost_per_1k_tokens=0.03, p95_latency_ms=300.0
        )
        tree.add_node(n1)
        tree.add_node(n2)
        stats = tree.get_domain_statistics()
        assert sorted(stats["models_evaluated"]) == ["claude", "gpt-4o"]
        assert stats["avg_cost_per_1k_tokens"] == pytest.approx(0.02)
        assert stats["avg_p95_latency_ms"] == pytest.approx(200.0)

    def test_get_domain_statistics_routing_empty(self):
        tree = OptimizationTree(task_type=TaskType.ROUTING)
        stats = tree.get_domain_statistics()
        assert stats["models_evaluated"] == []
        assert stats["avg_cost_per_1k_tokens"] == 0
        assert stats["avg_p95_latency_ms"] == 0


class TestEnumValues:
    def test_node_status_values(self):
        assert NodeStatus.PENDING.value == "pending"
        assert NodeStatus.EXPANDING.value == "expanding"
        assert NodeStatus.SUCCESS.value == "success"
        assert NodeStatus.FAILED.value == "failed"
        assert NodeStatus.PRUNED.value == "pruned"

    def test_pruning_reason_values(self):
        assert PruningReason.LINT_FAILED.value == "lint_failed"
        assert PruningReason.TEST_FAILED.value == "test_failed"
        assert PruningReason.LATENCY_REGRESSION.value == "latency_regression"
        assert PruningReason.RESOURCE_EXCEEDED.value == "resource_exceeded"
        assert PruningReason.NEGATIVE_CONSTRAINT.value == "negative_constraint"
        assert PruningReason.BUDGET_EXCEEDED.value == "budget_exceeded"
        assert PruningReason.DUPLICATE_HYPOTHESIS.value == "duplicate_hypothesis"
        assert PruningReason.LOW_PROMISE.value == "low_promise"
        assert PruningReason.MANUAL.value == "manual"

    def test_task_type_values(self):
        assert TaskType.CODING.value == "coding"
        assert TaskType.WORKFLOW.value == "workflow"
        assert TaskType.ROUTING.value == "routing"
