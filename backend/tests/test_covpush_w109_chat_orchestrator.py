# -*- coding: utf-8 -*-
"""Coverage wave 109 — integrations/chat_orchestrator.py (tracked 2026-08-09
at 94%; w109 closes the remaining 35 lines -> 100%. Zero LLM spend, no network,
no real DB. The stray `integrations/test_chat_orchestrator.py` scaffold was
moved to `tests/test_chat_orchestrator.py` (repaired to the current flow).

Covered w109: module import-fallback branches (LLMService unavailable,
execute_agent_task/get_automation_settings/accounting imports failing), session
dedup exception swallow, LKGP sticky-hint exception swallow, second
cancellation checkpoint, feature-handler exception in _route_to_features,
task-title colon split, automation unknown-agent branch, finance disabled /
check_overdue / get_aging / exception paths.
"""
import importlib
import importlib.util
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.chat_orchestrator as co


def _make_orch(**kwargs):
    orch = co.ChatOrchestrator()
    orch.ai_engines = {}
    orch.session_manager = None
    orch.conversation_sessions = {}
    orch.llm_service = None
    for k, v in kwargs.items():
        setattr(orch, k, v)
    return orch


class TestImportFallbacks:
    """Module-level try/except fallbacks via a fresh-name exec (w107 pattern)."""

    @staticmethod
    def _exec_with_blocked(blocked_names):
        import builtins
        path = co.__file__
        spec = importlib.util.spec_from_file_location("chat_orch_w109_fb", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["chat_orch_w109_fb"] = mod
        real_import = builtins.__import__

        def blocker(name, *args, **kwargs):
            if name in blocked_names or any(
                name.startswith(b + ".") for b in blocked_names if "." not in b
            ):
                raise ImportError(f"blocked: {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocker):
            spec.loader.exec_module(mod)
        return mod

    def test_llm_service_unavailable(self):
        mod = self._exec_with_blocked({"core.llm_service"})
        assert mod.LLM_SERVICE_AVAILABLE is False

    def test_agent_routes_unavailable(self):
        mod = self._exec_with_blocked({"api.agent_routes"})
        assert mod.execute_agent_task is None

    def test_automation_settings_unavailable(self):
        mod = self._exec_with_blocked({"core.automation_settings"})
        assert mod.get_automation_settings is None

    def test_accounting_unavailable(self):
        """Coverage: lines 69-73 only execute when the accounting imports
        SUCCEED (the try aborts at line 68 on failure), so fake modules are
        seeded for the exec; the except-branch guard (74-75) is covered by
        the normal import path in this environment."""
        fakes = {}
        for mod_name, attr in [
            ("accounting.assistant", "AccountingAssistant"),
            ("accounting.workflows", "CollectionAgent"),
            ("accounting.close_agent", "CloseChecklistAgent"),
            ("accounting.tax_service", "TaxService"),
            ("accounting.fpa_service", "FPAService"),
            ("accounting.multi_entity", "IntercompanyManager"),
        ]:
            fake = types.ModuleType(mod_name)
            setattr(fake, attr, object)
            fakes[mod_name] = fake

        import importlib
        import builtins
        path = co.__file__
        spec = importlib.util.spec_from_file_location("chat_orch_w109_acct", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["chat_orch_w109_acct"] = mod
        with patch.dict(sys.modules, fakes):
            spec.loader.exec_module(mod)
        assert mod.AccountingAssistant is not None
        assert mod.CollectionAgent is not None
        assert mod.IntercompanyManager is not None
        assert mod.TaxService is not None


class TestProcessMessageEdgePaths:
    async def test_dedup_exception_swallowed(self):
        orch = _make_orch()
        sid = "sess-1"
        orch.conversation_sessions[sid] = {
            "id": sid, "user_id": "u1", "history": [
                {"message": "hi", "response": {"message": "hello"}}
            ],
        }
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._analyze_intent = AsyncMock(return_value={
            "primary_intent": co.ChatIntent.SEARCH_REQUEST, "confidence": 0.9,
            "entities": [], "platforms": [],
        })
        orch._route_to_features = AsyncMock(return_value={})
        with patch("core.llm.compression.SESSION_DEDUP_ENABLED", True), \
             patch("core.llm.compression.session_dedup.get_or_create_dedup_index",
                   side_effect=RuntimeError("dedup broke")):
            resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["success"] is True

    async def test_lkgp_sticky_hint_exception_swallowed(self):
        orch = _make_orch()
        sid = "sess-2"
        orch.conversation_sessions[sid] = {"id": sid, "user_id": "u1", "history": []}
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._analyze_intent = AsyncMock(return_value={
            "primary_intent": co.ChatIntent.SEARCH_REQUEST, "confidence": 0.9,
            "entities": [], "platforms": [],
        })
        orch._route_to_features = AsyncMock(return_value={})
        with patch("os.getenv", side_effect=RuntimeError("env broke")):
            resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["success"] is True

    async def test_second_cancellation_checkpoint(self):
        orch = _make_orch()
        sid = "sess-3"
        orch.conversation_sessions[sid] = {"id": sid, "user_id": "u1", "history": []}
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._analyze_intent = AsyncMock(return_value={
            "primary_intent": co.ChatIntent.SEARCH_REQUEST, "confidence": 0.9,
            "entities": [], "platforms": [],
        })
        orch._route_to_features = AsyncMock(return_value={})
        # First checkpoint clears, second checkpoint cancels.
        orch._is_cancelled = MagicMock(side_effect=[False, True])
        resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["cancelled"] is True
        assert resp["success"] is False


class TestRouteToFeatures:
    async def test_handler_exception_recorded(self):
        orch = _make_orch()
        orch.feature_handlers[co.FeatureType.SEARCH] = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await orch._route_to_features(
            "find x",
            {"primary_intent": co.ChatIntent.SEARCH_REQUEST, "confidence": 0.5,
             "entities": [], "platforms": []},
            {}, None,
        )
        assert resp[co.FeatureType.SEARCH] == {"error": "internal_error"}


class TestHandlers:
    async def test_task_handler_colon_split(self):
        orch = _make_orch()
        with patch("core.unified_task_endpoints.create_task",
                   new=AsyncMock(return_value={"success": True,
                                               "task": SimpleNamespace(id="t-1")})) as create_task:
            result = await orch._handle_task_request("Remind me: call John", {}, {}, None)
        assert result["success"] is True
        assert result["data"]["task"]["title"] == "Remind me"
        assert result["data"]["task"]["description"] == "call John"
        create_task.assert_awaited_once()

    async def test_automation_unknown_agent(self):
        orch = _make_orch()
        result = await orch._handle_automation_request("run the thing please", {}, {}, None)
        assert result["success"] is False
        assert "not sure which one" in result["message"]

    async def test_finance_disabled(self):
        orch = _make_orch()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: False)):
            result = await orch._handle_finance_request("whats my cash", {}, {}, None)
        assert result["success"] is False
        assert "disabled" in result["message"].lower()

    async def test_finance_disabled_none_settings(self):
        orch = _make_orch()
        with patch.object(co, "get_automation_settings", None):
            result = await orch._handle_finance_request("whats my cash", {}, {}, None)
        assert result["success"] is False

    async def test_finance_check_overdue(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA, \
             patch.object(co, "CollectionAgent") as CA:
            aa_instance = AA.return_value
            aa_instance.process_query = AsyncMock(return_value={"intent": "check_overdue"})
            ca_instance = CA.return_value
            ca_instance.check_overdue_invoices = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
            result = await orch._handle_finance_request(
                "send reminders", {}, {"workspace_id": "ws-1"}, {}
            )
        assert result["success"] is True
        assert "2 overdue invoices" in result["data"]["answer"]
        assert result["data"]["reminders"] == [{"id": 1}, {"id": 2}]
        db.close.assert_called_once()

    async def test_finance_get_aging(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA, \
             patch.object(co, "CollectionAgent") as CA:
            aa_instance = AA.return_value
            aa_instance.process_query = AsyncMock(return_value={"intent": "get_aging"})
            ca_instance = CA.return_value
            ca_instance.generate_aging_report = MagicMock(return_value={"rows": 3})
            result = await orch._handle_finance_request(
                "aging report", {}, {"workspace_id": "ws-1"}, {}
            )
        assert result["success"] is True
        assert result["data"]["aging_report"] == {"rows": 3}
        assert "aging" in result["data"]["answer"].lower()

    async def test_finance_exception(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA:
            AA.return_value.process_query = AsyncMock(side_effect=RuntimeError("ledger blew up"))
            result = await orch._handle_finance_request(
                "p&l", {}, {"workspace_id": "ws-1"}, {}
            )
        assert result["success"] is False
        assert result["error"] == "finance_handler_failed"
        db.close.assert_called_once()
