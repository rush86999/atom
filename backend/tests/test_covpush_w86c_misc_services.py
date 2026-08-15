# -*- coding: utf-8 -*-
"""W86C — coverage push: 10 misc core services to >=95% statement coverage.

Targets (standalone coverage):
  core/ai_service.py                    (baseline 100% via other suites — re-covered here)
  core/ai_trigger_coordinator.py        (baseline 75% — gaps: world-model error, memory
                                         confidence adjust, str data, medium+history decision,
                                         _trigger_agent paths, hooks, singleton)
  core/app_secrets.py                   (baseline 100% — re-covered here)
  core/credential_vault.py              (baseline 100% — re-covered here)
  core/feature_flags.py                 (baseline 47% — class methods + module functions)
  core/llm_call_tracker.py              (baseline 96% — gaps: fallback w/o provider, summary
                                         model filter, __len__)
  core/audit_service.py                 (baseline 92% — gap: create_package_audit)
  core/automation_insight_manager.py    (baseline 100% — re-covered here)
  core/background_agent_runner.py       (baseline 100% — re-covered here)
  core/enterprise_user_management.py    (baseline 100% — re-covered here)

Style: fully mocked deps (sqlalchemy sessions, submodules via sys.modules),
zero network, zero LLM spend, no real DB (tmp sqlite file only for the
analytics drift metrics, which requires a real sqlite3 connection).
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import logging
import os
import sqlite3
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.audit_service import AuditService, AuditType
from core.ai_trigger_coordinator import (
    AITriggerCoordinator,
    DataCategory,
    TriggerDecision,
)
from core.app_secrets import SecretManager, get_secret_manager
from core.background_agent_runner import (
    AgentLog,
    AgentState,
    AgentStatus,
    BackgroundAgentRunner,
)
from core.credential_vault import (
    CredentialVault,
    CredentialVaultError,
    delete_tenant_integration,
    find_tenant_by_platform_id,
    get_vault,
    list_tenant_integrations,
    load_tenant_integration,
    reset_vault,
    save_tenant_integration,
)
from core.enterprise_user_management import (
    TeamCreate,
    TeamUpdate,
    UserUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from core.feature_flags import FeatureFlags, get_feature_status, is_governance_required
from core.llm_call_tracker import LLMCallRecord, LLMCallTracker, get_llm_call_tracker
from core.models import TriggerSource


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# core/ai_service.py
# ===========================================================================

class TestGetAiService:
    def test_returns_real_service_when_available(self):
        fake_mod = SimpleNamespace(ai_service="fake-svc")
        with patch.dict(sys.modules, {"enhanced_ai_workflow_endpoints": fake_mod}):
            from core.ai_service import get_ai_service
            assert get_ai_service() == "fake-svc"

    def test_raises_import_error_without_mock_allowed(self):
        with patch.dict(sys.modules, {"enhanced_ai_workflow_endpoints": None}):
            from core.ai_service import get_ai_service
            with patch("core.ai_service.ALLOW_MOCK_AI", False):
                with pytest.raises(ImportError) as exc_info:
                    get_ai_service()
                assert "not found" in str(exc_info.value)

    def test_returns_mock_when_allow_mock_ai(self):
        with patch.dict(sys.modules, {"enhanced_ai_workflow_endpoints": None}):
            from core.ai_service import MockAIService, get_ai_service
            with patch("core.ai_service.ALLOW_MOCK_AI", True):
                svc = get_ai_service()
                assert isinstance(svc, MockAIService)


class TestMockAiService:
    def test_process_with_nlu_returns_mock_response(self):
        from core.ai_service import MockAIService
        svc = MockAIService()
        result = _run(svc.process_with_nlu(text="hello", user_id="u1"))
        assert result["nlu_result"]["status"] == "mocked"
        assert result["confidence"] == 0.5
        assert "warning" in result

    def test_analyze_text_returns_mock_response(self):
        from core.ai_service import MockAIService
        svc = MockAIService()
        result = _run(svc.analyze_text(prompt="p", complexity=3, user_id="u2"))
        assert "Mocked AI response" in result

    def test_run_react_agent_returns_mock_response(self):
        from core.ai_service import MockAIService
        svc = MockAIService()
        result = _run(svc.run_react_agent(text="task"))
        assert result["final_answer"] == "Mock ReAct agent response"
        assert result["ai_generated_tasks"] == []
        assert result["confidence_score"] == 0.0


# ===========================================================================
# core/ai_trigger_coordinator.py
# ===========================================================================

class TestAITriggerCoordinatorEnums:
    def test_data_categories(self):
        assert DataCategory.FINANCE.value == "finance"
        assert DataCategory.SALES.value == "sales"
        assert DataCategory.OPERATIONS.value == "operations"
        assert DataCategory.HR.value == "hr"
        assert DataCategory.MARKETING.value == "marketing"
        assert DataCategory.LEGAL.value == "legal"
        assert DataCategory.SUPPORT.value == "support"
        assert DataCategory.GENERAL.value == "general"

    def test_trigger_decisions(self):
        assert TriggerDecision.TRIGGER_AGENT.value == "trigger_agent"
        assert TriggerDecision.NO_ACTION.value == "no_action"
        assert TriggerDecision.QUEUE_FOR_REVIEW.value == "queue_for_review"

    def test_keyword_and_agent_maps(self):
        c = AITriggerCoordinator()
        assert "invoice" in c.CATEGORY_KEYWORDS[DataCategory.FINANCE]
        assert c.CATEGORY_TO_AGENT[DataCategory.FINANCE] == "finance_analyst"
        assert c.CATEGORY_TO_AGENT[DataCategory.LEGAL] is None


class TestIsEnabled:
    def test_cached_value_returned(self):
        c = AITriggerCoordinator()
        c._enabled = True
        assert _run(c.is_enabled()) is True

    def test_fetches_preference_when_bool(self):
        pref = SimpleNamespace(get_preference=MagicMock(return_value=True))
        cm = MagicMock()
        with patch("core.database.get_db_session", return_value=cm) as gds, \
             patch("core.user_preference_service.UserPreferenceService", return_value=pref) as ups:
            c = AITriggerCoordinator()
            assert _run(c.is_enabled()) is True
            assert c._enabled is True
            ups.assert_called_once_with(cm.__enter__.return_value)
            pref.get_preference.assert_called_once_with(
                user_id="system", workspace_id="default",
                key="ai_auto_trigger_enabled", default=True)

    def test_fetches_preference_when_false(self):
        pref = SimpleNamespace(get_preference=MagicMock(return_value=False))
        with patch("core.database.get_db_session", return_value=MagicMock()), \
             patch("core.user_preference_service.UserPreferenceService", return_value=pref):
            c = AITriggerCoordinator(user_id="u1")
            assert _run(c.is_enabled()) is False

    def test_non_bool_preference_defaults_true(self):
        pref = SimpleNamespace(get_preference=MagicMock(return_value="yes"))
        with patch("core.database.get_db_session", return_value=MagicMock()), \
             patch("core.user_preference_service.UserPreferenceService", return_value=pref):
            c = AITriggerCoordinator()
            assert _run(c.is_enabled()) is True

    def test_exception_defaults_true(self):
        with patch("core.database.get_db_session", side_effect=RuntimeError("boom")):
            c = AITriggerCoordinator()
            assert _run(c.is_enabled()) is True


class TestExtractText:
    def test_string_passthrough(self):
        assert AITriggerCoordinator()._extract_text("plain text") == "plain text"

    def test_known_text_field(self):
        assert AITriggerCoordinator()._extract_text({"subject": "hi", "body": "bye"}) == "bye"

    def test_first_text_field_wins(self):
        assert AITriggerCoordinator()._extract_text({"text": "a", "content": "b"}) == "a"

    def test_non_string_field_skipped(self):
        assert AITriggerCoordinator()._extract_text({"text": 42, "content": "b"}) == "b"

    def test_fallback_to_str(self):
        assert AITriggerCoordinator()._extract_text({"key": [1, 2]}) == "{'key': [1, 2]}"


class TestClassifyCategory:
    def test_general_when_no_keywords(self):
        category, conf = AITriggerCoordinator()._classify_category("zzz nothing here")
        assert category is DataCategory.GENERAL
        assert conf == 0.0

    def test_finance_keywords(self):
        category, conf = AITriggerCoordinator()._classify_category(
            "invoice payment expense budget tax")
        assert category is DataCategory.FINANCE
        assert conf == 1.0

    def test_best_category_wins(self):
        category, _ = AITriggerCoordinator()._classify_category("invoice lead deal")
        assert category is DataCategory.SALES

    def test_confidence_normalized_at_3(self):
        _, conf = AITriggerCoordinator()._classify_category("invoice payment expense")
        assert conf == 1.0
        _, conf2 = AITriggerCoordinator()._classify_category("invoice payment")
        assert conf2 == 2.0 / 3.0


class TestAdjustConfidenceWithMemory:
    def test_no_memory_unchanged(self):
        assert AITriggerCoordinator()._adjust_confidence_with_memory(0.7, {}) == 0.7

    def test_boost_from_successes(self):
        c = AITriggerCoordinator()
        assert c._adjust_confidence_with_memory(0.5, {"success_count": 2}) == 0.6
        assert c._adjust_confidence_with_memory(0.95, {"success_count": 5}) == 1.0

    def test_reduction_from_failures(self):
        c = AITriggerCoordinator()
        assert c._adjust_confidence_with_memory(0.8, {"success_count": 1, "failure_count": 3}) == pytest.approx(0.75)
        assert c._adjust_confidence_with_memory(0.05, {"failure_count": 1, "success_count": 0}) == 0.0


class TestMakeDecision:
    def test_low_confidence_no_action(self):
        decision, template, reason = AITriggerCoordinator()._make_decision(
            DataCategory.GENERAL, 0.2, "webhook", None, {})
        assert decision is TriggerDecision.NO_ACTION
        assert template is None
        assert "Low confidence" in reason

    def test_no_agent_template_no_action(self):
        decision, template, reason = AITriggerCoordinator()._make_decision(
            DataCategory.LEGAL, 0.8, "webhook", None, None)
        assert decision is TriggerDecision.NO_ACTION
        assert template is None
        assert "No agent template" in reason

    def test_medium_confidence_queues_for_review(self):
        decision, template, reason = AITriggerCoordinator()._make_decision(
            DataCategory.FINANCE, 0.4, "webhook", None, {})
        assert decision is TriggerDecision.QUEUE_FOR_REVIEW
        assert template == "finance_analyst"
        assert "requires review" in reason

    def test_medium_confidence_strong_history_triggers(self):
        decision, template, reason = AITriggerCoordinator()._make_decision(
            DataCategory.FINANCE, 0.4, "webhook", None,
            {"success_count": 3, "has_similar_history": True})
        assert decision is TriggerDecision.TRIGGER_AGENT
        assert template == "finance_analyst"
        assert "strong success history" in reason

    def test_high_confidence_triggers(self):
        decision, template, reason = AITriggerCoordinator()._make_decision(
            DataCategory.FINANCE, 0.9, "webhook", None, {"success_count": 0})
        assert decision is TriggerDecision.TRIGGER_AGENT
        assert template == "finance_analyst"
        assert "High confidence" in reason

    def test_high_confidence_with_memory_note(self):
        decision, template, reason = AITriggerCoordinator()._make_decision(
            DataCategory.SALES, 0.9, "gmail", None,
            {"success_count": 2, "has_similar_history": True})
        assert decision is TriggerDecision.TRIGGER_AGENT
        assert "memory-informed: 2 successes" in reason


class TestQueryMemoryForInsights:
    def test_success_path_counts_outcomes(self):
        exp_success = SimpleNamespace(outcome="Success")
        exp_failure = SimpleNamespace(outcome="Failure")
        wm = MagicMock()
        wm.recall_experiences = AsyncMock(return_value={
            "experiences": [exp_success, exp_failure],
            "knowledge": ["k1"],
        })
        with patch("core.agent_world_model.WorldModelService", return_value=wm):
            c = AITriggerCoordinator()
            out = _run(c._query_memory_for_insights("some text", DataCategory.FINANCE))
            assert out["success_count"] == 1
            assert out["failure_count"] == 1
            assert out["has_similar_history"] is True
            assert out["knowledge"] == ["k1"]
            wm.recall_experiences.assert_awaited_once()
            assert wm.recall_experiences.await_args.kwargs["current_task_description"] == "some text"[:500]

    def test_exception_returns_empty(self):
        with patch("core.agent_world_model.WorldModelService", side_effect=RuntimeError("wm down")):
            c = AITriggerCoordinator()
            out = _run(c._query_memory_for_insights("text", DataCategory.GENERAL))
            assert out == {"experiences": [], "success_count": 0, "failure_count": 0, "knowledge": []}


class TestEvaluateData:
    def test_disabled_returns_no_action(self):
        c = AITriggerCoordinator()
        c._enabled = False
        out = _run(c.evaluate_data({"text": "invoice"}, "webhook"))
        assert out["decision"] == TriggerDecision.NO_ACTION.value
        assert out["agent_template"] is None
        assert "disabled" in out["reasoning"]

    def test_high_confidence_triggers_agent(self):
        c = AITriggerCoordinator()
        c._enabled = True
        c._query_memory_for_insights = AsyncMock(return_value={
            "experiences": [SimpleNamespace(outcome="Success")],
            "success_count": 1, "failure_count": 0, "knowledge": [],
            "has_similar_history": True,
        })
        c._trigger_agent = AsyncMock()
        out = _run(c.evaluate_data({"text": "invoice payment expense budget tax"}, "gmail"))
        assert out["decision"] == TriggerDecision.TRIGGER_AGENT.value
        assert out["agent_template"] == "finance_analyst"
        assert out["category"] == "finance"
        assert out["confidence"] == 1.0
        assert out["memory_used"] is True
        assert out["source"] == "gmail"
        c._trigger_agent.assert_awaited_once()

    def test_no_template_category_returns_no_action(self):
        c = AITriggerCoordinator()
        c._enabled = True
        c._query_memory_for_insights = AsyncMock(return_value={
            "experiences": [], "success_count": 0, "failure_count": 0,
            "knowledge": [], "has_similar_history": False,
        })
        c._trigger_agent = AsyncMock()
        out = _run(c.evaluate_data({"text": "contract nda license compliance regulation"}, "doc_upload"))
        assert out["decision"] == TriggerDecision.NO_ACTION.value
        assert out["category"] == "legal"
        c._trigger_agent.assert_not_awaited()

    def test_general_data_low_confidence_no_action(self):
        c = AITriggerCoordinator()
        c._enabled = True
        c._query_memory_for_insights = AsyncMock(return_value={
            "experiences": [], "success_count": 0, "failure_count": 0,
            "knowledge": [], "has_similar_history": False,
        })
        c._trigger_agent = AsyncMock()
        out = _run(c.evaluate_data({"body": "unrelated words"}, "webhook"))
        assert out["decision"] == TriggerDecision.NO_ACTION.value
        assert out["confidence"] == 0.0
        c._trigger_agent.assert_not_awaited()


class TestTriggerAgent:
    def _coordinator_and_mocks(self, db_set=False):
        c = AITriggerCoordinator()
        agent = SimpleNamespace(id="ag-1", name="Finance Analyst")
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value=agent)
        atom.execute = AsyncMock(return_value={"final_output": "processed"})
        interceptor = MagicMock()
        return c, agent, atom, interceptor

    def _decision(self, execute=True, routing="high", proposal=None, blocked_context=None):
        return SimpleNamespace(
            execute=execute,
            routing_decision=SimpleNamespace(value=routing),
            proposal=proposal,
            blocked_context=blocked_context,
            reason="some reason",
            agent_maturity="SUPERVISED",
            confidence_score=0.9,
        )

    def _db_cm(self):
        cm = MagicMock()
        return cm

    def test_execute_path_with_get_db_session(self):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        interceptor.intercept_trigger = AsyncMock(return_value=self._decision(execute=True))
        cm = self._db_cm()
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.database.get_db_session", return_value=cm) as gds:
            _run(c._trigger_agent("finance_analyst", {"text": "invoice"}, {"m": 1}, {"success_count": 0}))
            gds.assert_called_once()
            interceptor.intercept_trigger.assert_awaited_once_with(
                agent_id="ag-1", trigger_source=TriggerSource.AI_COORDINATOR,
                trigger_context={
                    "action_type": "agent_message", "agent_template": "finance_analyst",
                    "data": {"text": "invoice"}, "metadata": {"m": 1},
                    "source": "ai_coordinator",
                })
            atom.spawn_agent.assert_awaited_once_with("finance_analyst", persist=False)
            atom.execute.assert_awaited_once()
            assert atom.execute.await_args.kwargs["trigger_mode"] is not None
            assert "auto_triggered" in atom.execute.await_args.kwargs["context"]

    def test_execute_path_with_existing_db(self):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        interceptor.intercept_trigger = AsyncMock(return_value=self._decision(execute=True))
        c.db = MagicMock()
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor) as ti, \
             patch("core.database.get_db_session") as gds:
            _run(c._trigger_agent("finance_analyst", "text", None, None))
            ti.assert_called_once_with(c.db, "default")
            gds.assert_not_called()
            atom.execute.assert_awaited_once()

    def test_training_blocked_with_proposal(self):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        decision = self._decision(execute=False, routing="training",
                                  proposal=SimpleNamespace(id="prop-1"))
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor):
            out = _run(c._trigger_agent("hr_assistant", {"text": "x"}, None, {}))
        assert out == {"blocked": True, "reason": "some reason",
                       "routing_decision": "training", "proposal_id": "prop-1"}
        atom.execute.assert_not_awaited()

    def test_training_blocked_without_proposal(self):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        decision = self._decision(execute=False, routing="training", proposal=None)
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor):
            out = _run(c._trigger_agent("hr_assistant", {"text": "x"}, None, {}))
        assert out["proposal_id"] is None

    def test_proposal_blocked_with_context(self):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        decision = self._decision(execute=False, routing="proposal",
                                  blocked_context=SimpleNamespace(id="bc-1"))
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor):
            out = _run(c._trigger_agent("sales_assistant", {"text": "x"}, None, {}))
        assert out == {"blocked": True, "reason": "some reason",
                       "routing_decision": "proposal", "blocked_context_id": "bc-1"}
        atom.execute.assert_not_awaited()

    def test_proposal_blocked_without_context(self):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        decision = self._decision(execute=False, routing="proposal", blocked_context=None)
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor):
            out = _run(c._trigger_agent("sales_assistant", {"text": "x"}, None, {}))
        assert out["blocked_context_id"] is None

    def test_supervision_proceeds_to_execution(self):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        decision = self._decision(execute=False, routing="supervision")
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor):
            out = _run(c._trigger_agent("ops_coordinator", {"text": "x"}, None, {}))
        assert out is None
        atom.execute.assert_awaited_once()

    def test_exception_is_swallowed(self, caplog):
        c, agent, atom, interceptor = self._coordinator_and_mocks()
        atom.execute = AsyncMock(side_effect=RuntimeError("exec failed"))
        interceptor.intercept_trigger = AsyncMock(return_value=self._decision(execute=True))
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.database.get_db_session", return_value=MagicMock()):
            with caplog.at_level(logging.ERROR, logger="core.ai_trigger_coordinator"):
                _run(c._trigger_agent("finance_analyst", {"text": "x"}, None, {}))
        assert "Failed to trigger agent" in caplog.text


class TestTriggerCoordinatorHooks:
    def test_on_data_ingested_delegates(self):
        with patch("core.ai_trigger_coordinator.AITriggerCoordinator") as cls:
            instance = cls.return_value
            instance.evaluate_data = AsyncMock(return_value={"decision": "no_action"})
            from core.ai_trigger_coordinator import on_data_ingested
            out = _run(on_data_ingested({"text": "x"}, "webhook", "ws-1", "u-1", {"a": 1}))
            assert out == {"decision": "no_action"}
            cls.assert_called_once_with("ws-1", "u-1")
            instance.evaluate_data.assert_awaited_once_with({"text": "x"}, "webhook", {"a": 1})

    def test_singleton_same_workspace_reused(self):
        import core.ai_trigger_coordinator as mod
        mod._coordinator_instance = None
        a = mod.get_ai_trigger_coordinator("ws1")
        b = mod.get_ai_trigger_coordinator("ws1")
        c = mod.get_ai_trigger_coordinator("ws2")
        assert a is b
        assert a is not c
        assert c.workspace_id == "ws2"


# ===========================================================================
# core/app_secrets.py
# ===========================================================================

class TestSecretManagerInit:
    def _make(self, monkeypatch, tmp_path, key=None, environment=None, **kw):
        if key is None:
            monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        else:
            monkeypatch.setenv("ENCRYPTION_KEY", key)
        if environment is None:
            monkeypatch.delenv("ENVIRONMENT", raising=False)
        else:
            monkeypatch.setenv("ENVIRONMENT", environment)
        m = SecretManager()
        m._secrets_file = str(tmp_path / "secrets.json")
        m._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        return m

    def test_init_without_key_development(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path)
        assert m._encryption_enabled is False
        assert m._fernet is None

    def test_init_without_key_production_warns(self, monkeypatch, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger="core.app_secrets"):
            m = self._make(monkeypatch, tmp_path, environment="production")
        assert m._encryption_enabled is False
        assert "ENCRYPTION_KEY not set in production" in caplog.text

    def test_init_with_key_enables_encryption(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path, key="correct horse battery staple")
        assert m._encryption_enabled is True
        assert m._fernet is not None

    def test_init_with_key_kdf_failure_disables(self, monkeypatch, tmp_path, caplog):
        with patch("cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC",
                   side_effect=Exception("kdf broken")):
            with caplog.at_level(logging.WARNING, logger="core.app_secrets"):
                m = self._make(monkeypatch, tmp_path, key="some key")
        assert m._encryption_enabled is False
        assert "Failed to initialize encryption" in caplog.text


class TestSecretManagerLoad:
    def _make(self, monkeypatch, tmp_path, key=None, environment=None):
        if key is None:
            monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        else:
            monkeypatch.setenv("ENCRYPTION_KEY", key)
        if environment is None:
            monkeypatch.delenv("ENVIRONMENT", raising=False)
        else:
            monkeypatch.setenv("ENVIRONMENT", environment)
        m = SecretManager()
        m._secrets_file = str(tmp_path / "secrets.json")
        m._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        return m

    def test_load_encrypted_file(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path, key="k")
        m._secrets = {"api_key": "abc"}
        assert m._save_secrets() is True
        assert (tmp_path / "secrets.enc").exists()
        m._secrets = {}
        m._load_secrets()
        assert m._secrets == {"api_key": "abc"}

    def test_load_encrypted_failure_falls_back(self, monkeypatch, tmp_path, caplog):
        m = self._make(monkeypatch, tmp_path, key="k")
        (tmp_path / "secrets.enc").write_bytes(b"garbage-not-fernet")
        with caplog.at_level(logging.ERROR, logger="core.app_secrets"):
            m._load_secrets()
        assert "Failed to load encrypted secrets" in caplog.text
        assert m._secrets == {}

    def test_load_plaintext_production_warns(self, monkeypatch, tmp_path, caplog):
        (tmp_path / "secrets.json").write_text(json.dumps({"a": "b"}))
        with caplog.at_level(logging.WARNING, logger="core.app_secrets"):
            m = self._make(monkeypatch, tmp_path, environment="production")
            m._load_secrets()
        assert m._secrets == {"a": "b"}
        assert "plaintext file in production" in caplog.text

    def test_load_plaintext_auto_migrates(self, monkeypatch, tmp_path):
        (tmp_path / "secrets.json").write_text(json.dumps({"api_key": "x"}))
        m = self._make(monkeypatch, tmp_path, key="k")
        m._load_secrets()
        assert m._secrets == {"api_key": "x"}
        assert not (tmp_path / "secrets.json").exists()
        assert (tmp_path / "secrets.enc").exists()

    def test_load_plaintext_migration_failure_keeps_file(self, monkeypatch, tmp_path):
        (tmp_path / "secrets.json").write_text(json.dumps({"api_key": "x"}))
        m = self._make(monkeypatch, tmp_path, key="k")
        with patch.object(m, "_save_secrets", return_value=False):
            m._load_secrets()
        assert m._secrets == {"api_key": "x"}
        assert (tmp_path / "secrets.json").exists()

    def test_load_plaintext_json_error(self, monkeypatch, tmp_path, caplog):
        (tmp_path / "secrets.json").write_text("not-json{")
        m = self._make(monkeypatch, tmp_path)
        with caplog.at_level(logging.ERROR, logger="core.app_secrets"):
            m._load_secrets()
        assert m._secrets == {}
        assert "Failed to load secrets" in caplog.text


class TestSecretManagerSave:
    def _make(self, monkeypatch, tmp_path, key=None):
        if key is None:
            monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        else:
            monkeypatch.setenv("ENCRYPTION_KEY", key)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        m = SecretManager()
        m._secrets_file = str(tmp_path / "secrets.json")
        m._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        return m

    def test_save_encrypted_sets_0600(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path, key="k")
        m._secrets = {"k": "v"}
        assert m._save_secrets() is True
        assert (tmp_path / "secrets.enc").exists()
        assert oct((tmp_path / "secrets.enc").stat().st_mode & 0o777) == "0o600"

    def test_save_plaintext_sets_0600(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path)
        m._secrets = {"k": "v"}
        assert m._save_secrets() is True
        assert json.loads((tmp_path / "secrets.json").read_text()) == {"k": "v"}
        assert oct((tmp_path / "secrets.json").stat().st_mode & 0o777) == "0o600"

    def test_save_failure_returns_false(self, monkeypatch, tmp_path, caplog):
        m = self._make(monkeypatch, tmp_path)
        target_dir = tmp_path / "is_a_directory"
        target_dir.mkdir()
        m._secrets_file = str(target_dir)
        with caplog.at_level(logging.ERROR, logger="core.app_secrets"):
            assert m._save_secrets() is False
        assert "Failed to save secrets" in caplog.text


class TestSecretManagerAccess:
    def _make(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        m = SecretManager()
        m._secrets_file = str(tmp_path / "secrets.json")
        m._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        return m

    def test_get_secret_env_wins(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path)
        m._secrets = {"MY_KEY": "stored"}
        monkeypatch.setenv("MY_KEY", "env")
        assert m.get_secret("MY_KEY") == "env"

    def test_get_secret_store_fallback(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path)
        m._secrets = {"MY_KEY": "stored"}
        monkeypatch.delenv("MY_KEY", raising=False)
        assert m.get_secret("MY_KEY") == "stored"

    def test_get_secret_default(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path)
        monkeypatch.delenv("MY_KEY", raising=False)
        assert m.get_secret("MY_KEY", "fallback") == "fallback"

    def test_set_secret_persists(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path)
        m.set_secret("NEW_KEY", "value1")
        assert m._secrets["NEW_KEY"] == "value1"
        assert json.loads((tmp_path / "secrets.json").read_text())["NEW_KEY"] == "value1"

    def test_security_status_plaintext(self, monkeypatch, tmp_path):
        m = self._make(monkeypatch, tmp_path)
        m._secrets = {"a": "b", "c": "d"}
        monkeypatch.setenv("ENVIRONMENT", "staging")
        status = m.get_security_status()
        assert status == {
            "encryption_enabled": False,
            "storage_type": "plaintext",
            "secrets_count": 2,
            "environment": "staging",
        }

    def test_security_status_encrypted(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENCRYPTION_KEY", "k")
        monkeypatch.setenv("ENVIRONMENT", "production")
        m = SecretManager()
        m._secrets_file = str(tmp_path / "secrets.json")
        m._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        status = m.get_security_status()
        assert status["encryption_enabled"] is True
        assert status["storage_type"] == "encrypted"


class TestGetSecretManagerGlobal:
    def test_returns_same_instance(self):
        assert get_secret_manager() is get_secret_manager()


# ===========================================================================
# core/credential_vault.py
# ===========================================================================

class TestCredentialVaultInit:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("SETTINGS_ENCRYPTION_KEY", raising=False)
        with pytest.raises(CredentialVaultError) as exc_info:
            CredentialVault()
        assert "SETTINGS_ENCRYPTION_KEY" in str(exc_info.value)

    def test_invalid_key_raises_with_preview(self, monkeypatch):
        monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", "garbage-key")
        with pytest.raises(CredentialVaultError) as exc_info:
            CredentialVault()
        msg = str(exc_info.value)
        assert "Invalid SETTINGS_ENCRYPTION_KEY" in msg
        assert "len=11" in msg and "preview='garbage-ke..." in msg

    def test_valid_str_key(self, monkeypatch):
        from cryptography.fernet import Fernet
        monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert CredentialVault()._fernet is not None

    def test_valid_bytes_key(self, monkeypatch):
        from cryptography.fernet import Fernet
        with patch("core.credential_vault.os.getenv", return_value=Fernet.generate_key()):
            assert CredentialVault()._fernet is not None


class TestCredentialVaultRoundtrip:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        from cryptography.fernet import Fernet
        monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())
        yield

    def test_encrypt_decrypt_roundtrip(self):
        vault = CredentialVault()
        data = {"api_key": "secret", "nested": {"a": 1}, "enabled": True}
        ct = vault.encrypt(data)
        assert isinstance(ct, str)
        assert vault.decrypt(ct) == data

    def test_encrypt_error_wrapped(self):
        vault = CredentialVault()
        vault._fernet = MagicMock()
        vault._fernet.encrypt = MagicMock(side_effect=Exception("enc boom"))
        with pytest.raises(CredentialVaultError) as exc_info:
            vault.encrypt({"a": 1})
        assert "Encryption failed" in str(exc_info.value)

    def test_decrypt_error_wrapped(self):
        vault = CredentialVault()
        with pytest.raises(CredentialVaultError) as exc_info:
            vault.decrypt("not-ciphertext")
        assert "Decryption failed" in str(exc_info.value)


class TestVaultSingleton:
    def test_get_vault_creates_and_resets(self, monkeypatch):
        from cryptography.fernet import Fernet
        monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())
        reset_vault()
        v1 = get_vault()
        assert isinstance(v1, CredentialVault)
        assert get_vault() is v1
        reset_vault()
        v2 = get_vault()
        assert v2 is not v1


class _FakeSetting:
    def __init__(self, tenant_id, setting_key, setting_value):
        self.tenant_id = tenant_id
        self.setting_key = setting_key
        self.setting_value = setting_value


class TestTenantIntegrationHelpers:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        from cryptography.fernet import Fernet
        monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())
        yield

    def test_save_new_integration(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        save_tenant_integration(db, "t1", "slack", {"api_key": "abc", "team_id": "T1"})
        db.add.assert_called_once()
        added = db.add.call_args.args[0]
        assert added.tenant_id == "t1"
        assert added.setting_key == "messaging_slack"
        vault = get_vault()
        assert vault.decrypt(added.setting_value) == {"api_key": "abc", "team_id": "T1"}
        db.commit.assert_called_once()

    def test_save_existing_integration(self):
        db = MagicMock()
        existing = _FakeSetting("t1", "messaging_slack", "old")
        db.query.return_value.filter_by.return_value.first.return_value = existing
        save_tenant_integration(db, "t1", "slack", {"api_key": "new"})
        db.add.assert_not_called()
        assert existing.setting_value != "old"
        db.commit.assert_called_once()

    def test_load_integration_missing_returns_none(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        assert load_tenant_integration(db, "t1", "slack") is None

    def test_load_integration_roundtrip(self):
        vault = get_vault()
        setting = _FakeSetting("t1", "messaging_slack",
                               vault.encrypt({"api_key": "abc"}))
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = setting
        assert load_tenant_integration(db, "t1", "slack") == {"api_key": "abc"}

    def test_delete_integration_true_and_false(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.delete.return_value = 1
        assert delete_tenant_integration(db, "t1", "slack") is True
        db.query.return_value.filter_by.return_value.delete.return_value = 0
        assert delete_tenant_integration(db, "t1", "discord") is False

    # ---- find_tenant_by_platform_id ----

    def test_find_tenant_token_match(self):
        from core.models import IntegrationToken, TenantSetting
        tok = SimpleNamespace(tenant_id="t-1", credential_metadata={"phone": "+1555"})
        db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is IntegrationToken:
                q.filter.return_value.all.return_value = [tok]
            else:
                q.filter_by.return_value.all.return_value = []
            return q

        db.query.side_effect = query_side
        assert find_tenant_by_platform_id(db, "whatsapp", "phone", "+1555") == "t-1"

    def test_find_tenant_token_no_metadata(self):
        from core.models import IntegrationToken, TenantSetting
        tok = SimpleNamespace(tenant_id="t-1", credential_metadata=None)
        db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is IntegrationToken:
                q.filter.return_value.all.return_value = [tok]
            else:
                q.filter_by.return_value.all.return_value = []
            return q

        db.query.side_effect = query_side
        assert find_tenant_by_platform_id(db, "whatsapp", "phone", "+1555") is None

    def test_find_tenant_setting_match(self):
        from core.models import IntegrationToken, TenantSetting
        vault = get_vault()
        setting = _FakeSetting("t-2", "messaging_slack",
                               vault.encrypt({"team_id": "T-99"}))
        db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is IntegrationToken:
                q.filter.return_value.all.return_value = []
            else:
                q.filter_by.return_value.all.return_value = [setting]
            return q

        db.query.side_effect = query_side
        assert find_tenant_by_platform_id(db, "slack", "team_id", "T-99") == "t-2"

    def test_find_tenant_setting_decrypt_error_skipped(self):
        from core.models import IntegrationToken, TenantSetting
        bad = _FakeSetting("t-2", "messaging_slack", "corrupt-ciphertext")
        good = _FakeSetting("t-3", "messaging_slack",
                            get_vault().encrypt({"team_id": "T-77"}))
        db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is IntegrationToken:
                q.filter.return_value.all.return_value = []
            else:
                q.filter_by.return_value.all.return_value = [bad, good]
            return q

        db.query.side_effect = query_side
        assert find_tenant_by_platform_id(db, "slack", "team_id", "T-77") == "t-3"

    def test_find_tenant_token_scan_error_warns(self):
        from core.models import IntegrationToken, TenantSetting
        db = MagicMock()
        db.query.side_effect = [RuntimeError("scan failed"), MagicMock()]
        assert find_tenant_by_platform_id(db, "slack", "team_id", "x") is None

    def test_find_tenant_setting_scan_error_warns(self):
        from core.models import IntegrationToken, TenantSetting
        db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is IntegrationToken:
                q.filter.return_value.all.return_value = []
            else:
                raise RuntimeError("settings scan failed")
            return q

        db.query.side_effect = query_side
        assert find_tenant_by_platform_id(db, "slack", "team_id", "x") is None

    def test_find_tenant_nothing(self):
        from core.models import IntegrationToken, TenantSetting
        db = MagicMock()

        def query_side(model):
            q = MagicMock()
            q.filter.return_value.all.return_value = []
            q.filter_by.return_value.all.return_value = []
            return q

        db.query.side_effect = query_side
        assert find_tenant_by_platform_id(db, "sms", "phone", "+1") is None

    # ---- list_tenant_integrations ----

    def test_list_integrations_redacts_secrets(self):
        from core.models import TenantSetting
        vault = get_vault()
        slack_setting = _FakeSetting("t1", "messaging_slack", vault.encrypt({
            "api_key": "SK-SECRET", "refresh_token": "RT", "team_id": "T1",
            "channel": "general",
        }))
        corrupted = _FakeSetting("t1", "messaging_discord", "bad-ciphertext")
        settings = {"messaging_slack": slack_setting, "messaging_discord": corrupted}
        db = MagicMock()

        def filter_by_side(**kwargs):
            q = MagicMock()
            q.first.return_value = settings.get(kwargs["setting_key"])
            return q

        db.query.return_value.filter_by.side_effect = filter_by_side
        result = list_tenant_integrations(db, "t1")
        assert len(result) == 6
        assert result["slack"]["connected"] is True
        assert result["slack"]["api_key"] == "***"
        assert result["slack"]["refresh_token"] == "***"
        assert result["slack"]["team_id"] == "T1"
        assert result["slack"]["channel"] == "general"
        assert result["discord"] == {"connected": False, "error": "credential_corrupted"}
        assert result["whatsapp"] == {"connected": False}
        assert result["telegram"] == {"connected": False}
        assert result["teams"] == {"connected": False}
        assert result["sms"] == {"connected": False}


# ===========================================================================
# core/feature_flags.py
# ===========================================================================

class TestFeatureFlagsGovernance:
    def test_is_governance_enabled_known(self):
        assert FeatureFlags.is_governance_enabled("browser") == FeatureFlags.BROWSER_GOVERNANCE_ENABLED

    def test_is_governance_enabled_unknown_defaults_true(self):
        assert FeatureFlags.is_governance_enabled("nonexistent") is True

    def test_emergency_bypass_active_logs_warning(self, monkeypatch, caplog):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", True)
        with caplog.at_level(logging.WARNING, logger="core.feature_flags"):
            assert FeatureFlags.is_emergency_bypass_active() is True
        assert "EMERGENCY GOVERNANCE BYPASS IS ACTIVE" in caplog.text

    def test_emergency_bypass_inactive(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        assert FeatureFlags.is_emergency_bypass_active() is False

    def test_should_enforce_false_when_bypass(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", True)
        assert FeatureFlags.should_enforce_governance("browser") is False

    def test_should_enforce_false_when_disabled(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        monkeypatch.setattr(FeatureFlags, "BROWSER_GOVERNANCE_ENABLED", False)
        assert FeatureFlags.should_enforce_governance("browser") is False

    def test_should_enforce_true_when_enabled(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        monkeypatch.setattr(FeatureFlags, "BROWSER_GOVERNANCE_ENABLED", True)
        assert FeatureFlags.should_enforce_governance("browser") is True


class TestFeatureFlagsRollout:
    def test_integration_action_disabled_global(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "INTEGRATION_ACTION_ENABLED", False)
        assert FeatureFlags.is_integration_action_enabled("t1") is False

    def test_integration_action_pct_100(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "INTEGRATION_ACTION_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "INTEGRATION_ACTION_ROLLOUT_PCT", 100)
        assert FeatureFlags.is_integration_action_enabled("t1") is True

    def test_integration_action_pct_0(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "INTEGRATION_ACTION_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "INTEGRATION_ACTION_ROLLOUT_PCT", 0)
        assert FeatureFlags.is_integration_action_enabled("t1") is False

    def test_integration_action_hash_rollout(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "INTEGRATION_ACTION_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "INTEGRATION_ACTION_ROLLOUT_PCT", 50)
        tenant_hash = int(hashlib.sha256("t1".encode()).hexdigest(), 16)
        expected = (tenant_hash % 100) + 1 <= 50
        assert FeatureFlags.is_integration_action_enabled("t1") is expected

    def test_normalize_disabled(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "TENANT_UUID_NORMALIZATION_ENABLED", False)
        assert FeatureFlags.should_normalize_tenant("slug") is False

    def test_normalize_pct_100(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "TENANT_UUID_NORMALIZATION_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "TENANT_UUID_NORMALIZATION_ROLLOUT_PCT", 100)
        assert FeatureFlags.should_normalize_tenant("slug") is True

    def test_normalize_pct_0(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "TENANT_UUID_NORMALIZATION_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "TENANT_UUID_NORMALIZATION_ROLLOUT_PCT", 0)
        assert FeatureFlags.should_normalize_tenant("slug") is False

    def test_normalize_hash_rollout(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "TENANT_UUID_NORMALIZATION_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "TENANT_UUID_NORMALIZATION_ROLLOUT_PCT", 50)
        tenant_hash = int(hashlib.sha256("slug".encode()).hexdigest(), 16)
        expected = (tenant_hash % 100) + 1 <= 50
        assert FeatureFlags.should_normalize_tenant("slug") is expected

    def test_atomic_oauth_disabled(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "ATOMIC_OAUTH_PERSISTENCE_ENABLED", False)
        assert FeatureFlags.is_atomic_oauth_persistence_enabled("t1") is False

    def test_atomic_oauth_pct_100(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "ATOMIC_OAUTH_PERSISTENCE_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "ATOMIC_OAUTH_PERSISTENCE_ROLLOUT_PCT", 100)
        assert FeatureFlags.is_atomic_oauth_persistence_enabled("t1") is True

    def test_atomic_oauth_pct_0(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "ATOMIC_OAUTH_PERSISTENCE_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "ATOMIC_OAUTH_PERSISTENCE_ROLLOUT_PCT", 0)
        assert FeatureFlags.is_atomic_oauth_persistence_enabled("t1") is False

    def test_atomic_oauth_hash_rollout(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "ATOMIC_OAUTH_PERSISTENCE_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "ATOMIC_OAUTH_PERSISTENCE_ROLLOUT_PCT", 50)
        tenant_hash = int(hashlib.sha256("t1".encode()).hexdigest(), 16)
        expected = (tenant_hash % 100) + 1 <= 50
        assert FeatureFlags.is_atomic_oauth_persistence_enabled("t1") is expected


class TestFeatureFlagsWebhooks:
    def test_webhook_enabled_default(self, monkeypatch):
        monkeypatch.delenv("ENABLE_WEBHOOK_SLACK", raising=False)
        assert FeatureFlags.is_webhook_enabled("slack") is True

    def test_webhook_enabled_explicit_false(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WEBHOOK_SLACK", "false")
        assert FeatureFlags.is_webhook_enabled("slack") is False

    def test_webhook_enabled_explicit_true(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WEBHOOK_SLACK", "True")
        assert FeatureFlags.is_webhook_enabled("slack") is True

    def test_webhook_canary_default_100(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_CANARY_PCT_SLACK", raising=False)
        assert FeatureFlags.is_webhook_canary_enabled("slack", "t1") is True

    def test_webhook_canary_invalid_pct_falls_back_100(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_CANARY_PCT_SLACK", "not-a-number")
        assert FeatureFlags.is_webhook_canary_enabled("slack", "t1") is True

    def test_webhook_canary_pct_0(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_CANARY_PCT_SLACK", "0")
        assert FeatureFlags.is_webhook_canary_enabled("slack", "t1") is False

    def test_webhook_canary_pct_100(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_CANARY_PCT_SLACK", "100")
        assert FeatureFlags.is_webhook_canary_enabled("slack", "t1") is True

    def test_webhook_canary_hash_rollout(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_CANARY_PCT_SLACK", "50")
        combined = "slack:t1"
        hasher = int(hashlib.sha256(combined.encode()).hexdigest(), 16)
        expected = (hasher % 100) + 1 <= 50
        assert FeatureFlags.is_webhook_canary_enabled("slack", "t1") is expected


class TestFeatureFlagsIntrospection:
    def test_get_all_flags_contains_uppercase_only(self):
        flags = FeatureFlags.get_all_flags()
        assert "BROWSER_GOVERNANCE_ENABLED" in flags
        assert all(k.isupper() for k in flags)

    def test_get_oauth_kill_switches(self):
        switches = FeatureFlags.get_oauth_kill_switches()
        assert set(switches) == {
            "DISABLE_PKCE_ENFORCEMENT", "DISABLE_HMAC_VALIDATION",
            "DISABLE_STATE_CONSUMPTION", "DISABLE_TENANT_ISOLATION",
        }

    def test_log_oauth_kill_switch_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="core.feature_flags"):
            FeatureFlags.log_oauth_kill_switch_warning("DISABLE_PKCE_ENFORCEMENT", "oauth")
        assert "OAuth kill-switch ACTIVE: DISABLE_PKCE_ENFORCEMENT" in caplog.text
        assert "Security enforcement disabled for oauth" in caplog.text

    def test_validate_flags_bypass_active(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", True)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        issues = FeatureFlags.validate_flags()
        assert issues.get("EMERGENCY_BYPASS_ACTIVE") is True

    def test_validate_flags_production_disabled_governance(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(FeatureFlags, "BROWSER_GOVERNANCE_ENABLED", False)
        monkeypatch.setattr(FeatureFlags, "DEVICE_GOVERNANCE_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "FINANCIAL_GOVERNANCE_ENABLED", False)
        monkeypatch.setattr(FeatureFlags, "BILLING_GOVERNANCE_ENABLED", True)
        issues = FeatureFlags.validate_flags()
        assert "BROWSER_GOVERNANCE_ENABLED_DISABLED_IN_PRODUCTION" in issues
        assert "FINANCIAL_GOVERNANCE_ENABLED_DISABLED_IN_PRODUCTION" in issues
        assert "DEVICE_GOVERNANCE_ENABLED_DISABLED_IN_PRODUCTION" not in issues

    def test_validate_flags_production_all_enabled(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(FeatureFlags, "BROWSER_GOVERNANCE_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "DEVICE_GOVERNANCE_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "FINANCIAL_GOVERNANCE_ENABLED", True)
        monkeypatch.setattr(FeatureFlags, "BILLING_GOVERNANCE_ENABLED", True)
        assert FeatureFlags.validate_flags() == {}

    def test_validate_flags_development(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert FeatureFlags.validate_flags() == {}

    def test_module_aliases_present(self):
        from core import feature_flags
        assert feature_flags.DISABLE_PKCE_ENFORCEMENT == FeatureFlags.DISABLE_PKCE_ENFORCEMENT
        assert feature_flags.DISABLE_HMAC_VALIDATION == FeatureFlags.DISABLE_HMAC_VALIDATION
        assert feature_flags.DISABLE_STATE_CONSUMPTION == FeatureFlags.DISABLE_STATE_CONSUMPTION
        assert feature_flags.DISABLE_TENANT_ISOLATION == FeatureFlags.DISABLE_TENANT_ISOLATION


class TestFeatureFlagsModuleFunctions:
    def test_is_governance_required_bypass(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", True)
        assert is_governance_required() is False

    def test_is_governance_required_with_feature(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        monkeypatch.setattr(FeatureFlags, "BROWSER_GOVERNANCE_ENABLED", False)
        assert is_governance_required("browser") is False
        monkeypatch.setattr(FeatureFlags, "BROWSER_GOVERNANCE_ENABLED", True)
        assert is_governance_required("browser") is True

    def test_is_governance_required_default_true(self, monkeypatch):
        monkeypatch.setattr(FeatureFlags, "EMERGENCY_GOVERNANCE_BYPASS", False)
        assert is_governance_required() is True

    def test_get_feature_status(self):
        status = get_feature_status()
        assert "BROWSER_GOVERNANCE_ENABLED" in status


# ===========================================================================
# core/llm_call_tracker.py
# ===========================================================================

class TestLLMCallTrackerRecord:
    def _tracker(self):
        return LLMCallTracker(maxlen=100)

    def test_success_record_populates_fields(self):
        t = self._tracker()
        t.record("openai", "gpt-5", True, latency_ms=150.0,
                 input_tokens=100, output_tokens=20)
        rec = t.get_recent_calls()[0]
        assert isinstance(rec, LLMCallRecord)
        assert rec.provider == "openai"
        assert rec.model == "gpt-5"
        assert rec.success is True
        assert rec.latency_ms == 150.0
        assert rec.input_tokens == 100
        assert rec.output_tokens == 20
        assert rec.fallback is False
        assert rec.error is None

    def test_failure_record_with_error_truncated(self):
        t = self._tracker()
        t.record("anthropic", "claude", False, error="e" * 600)
        rec = t.get_recent_calls()[0]
        assert rec.success is False
        assert len(rec.error) == 500

    def test_negative_tokens_clamped(self):
        t = self._tracker()
        t.record("x", "m", True, input_tokens=-5, output_tokens=-3, latency_ms=-1)
        rec = t.get_recent_calls()[0]
        assert rec.input_tokens == 0
        assert rec.output_tokens == 0
        assert rec.latency_ms == 0.0

    def test_fallback_without_provider_set_to_none(self):
        t = self._tracker()
        t.record("opencode-go", "deepseek-v4-flash", True, fallback=True)
        rec = t.get_recent_calls()[0]
        assert rec.fallback is True
        assert rec.fallback_provider is None

    def test_fallback_with_provider(self):
        t = self._tracker()
        t.record("deepseek", "deepseek-v4-pro", True,
                 fallback=True, fallback_provider="openai")
        rec = t.get_recent_calls()[0]
        assert rec.fallback_provider == "openai"

    def test_record_never_raises_on_bad_input(self):
        t = self._tracker()
        t.record("p", "m", "not-bool", latency_ms="abc")
        assert len(t) == 0

    def test_bounded_buffer(self):
        t = LLMCallTracker(maxlen=5)
        for i in range(20):
            t.record("p", f"m{i}", True)
        assert len(t) == 5
        assert t.get_recent_calls()[0].model == "m19"

    def test_maxlen_clamped_to_at_least_one(self):
        t = LLMCallTracker(maxlen=0)
        assert t._maxlen == 1

    def test_clear(self):
        t = self._tracker()
        t.record("p", "m", True)
        t.clear()
        assert len(t) == 0


class TestLLMCallTrackerReads:
    def _tracker(self):
        t = LLMCallTracker(maxlen=100)
        t.record("openai", "gpt-5", True, input_tokens=10, output_tokens=5, latency_ms=100.0)
        t.record("openai", "gpt-5", False, error="boom", latency_ms=50.0)
        t.record("anthropic", "claude", True, fallback=True,
                 fallback_provider="openai", input_tokens=3, output_tokens=1)
        t.record("openai", "gpt-4o", True, input_tokens=7, output_tokens=2)
        return t

    def test_get_recent_calls_newest_first(self):
        t = self._tracker()
        calls = t.get_recent_calls()
        assert len(calls) == 4
        assert calls[0].model == "gpt-4o"

    def test_get_recent_calls_provider_filter(self):
        t = self._tracker()
        calls = t.get_recent_calls(provider="anthropic")
        assert len(calls) == 1
        assert calls[0].provider == "anthropic"

    def test_get_recent_calls_model_filter(self):
        t = self._tracker()
        calls = t.get_recent_calls(model="gpt-5")
        assert len(calls) == 2
        assert all(c.model == "gpt-5" for c in calls)

    def test_get_recent_calls_limit_clamped(self):
        t = self._tracker()
        assert len(t.get_recent_calls(limit=2)) == 2
        assert len(t.get_recent_calls(limit=0)) == 4
        assert len(t.get_recent_calls(limit=999)) == 4

    def test_get_summary_overall(self):
        t = self._tracker()
        summary = t.get_summary()
        assert summary["total_calls"] == 4
        assert summary["successful_calls"] == 3
        assert summary["failed_calls"] == 1
        assert summary["fallback_calls"] == 1
        assert summary["total_input_tokens"] == 20
        assert summary["total_output_tokens"] == 8
        assert summary["total_tokens"] == 28
        assert summary["avg_latency_ms"] == pytest.approx(37.5)
        assert summary["last_call"] is not None

    def test_get_summary_provider_filter(self):
        t = self._tracker()
        summary = t.get_summary(provider="openai")
        assert summary["total_calls"] == 3
        assert "by_provider" in summary and "by_model" in summary
        assert summary["by_model"]["gpt-5"]["total_calls"] == 2

    def test_get_summary_model_filter(self):
        t = self._tracker()
        summary = t.get_summary(model="gpt-5")
        assert summary["total_calls"] == 2
        assert summary["failed_calls"] == 1

    def test_get_summary_empty(self):
        t = LLMCallTracker()
        summary = t.get_summary()
        assert summary["total_calls"] == 0
        assert summary["avg_latency_ms"] == 0.0
        assert summary["last_call"] is None

    def test_len(self):
        t = LLMCallTracker()
        assert len(t) == 0
        t.record("p", "m", True)
        assert len(t) == 1


class TestLLMCallTrackerSingleton:
    def test_get_singleton(self):
        import core.llm_call_tracker as mod
        mod._singleton = None
        s1 = get_llm_call_tracker()
        assert get_llm_call_tracker() is s1
        assert isinstance(s1, LLMCallTracker)
        assert mod.llm_call_tracker is not None


# ===========================================================================
# core/audit_service.py
# ===========================================================================

class TestAuditServiceGeneric:
    def _service(self, max_retries=2):
        return AuditService(max_retries=max_retries)

    def _request(self):
        req = MagicMock()
        req.client.host = "10.0.0.1"
        req.headers.get.return_value = "test-agent"
        return req

    def test_log_event_with_request(self):
        svc = self._service()
        db = MagicMock()
        audit_id = svc.log_event(
            db=db, event_type="login", action="user.login", description="Logged in",
            user_id="u1", user_email="a@b.c", workspace_id="w1",
            security_level="high", threat_level="low", resource="users",
            metadata={"ip": "x"}, success=True, error_message=None,
            request=self._request())
        assert audit_id is not None
        record = db.add.call_args.args[0]
        assert audit_id == record.id
        assert record.event_type == "login"
        assert record.action == "user.login"
        assert record.user_id == "u1"
        assert record.workspace_id == "w1"
        assert record.ip_address == "10.0.0.1"
        assert record.user_agent == "test-agent"
        assert json.loads(record.metadata_json) == {"ip": "x", "audit_subtype": "generic"}

    def test_log_event_without_request(self):
        svc = self._service()
        db = MagicMock()
        audit_id = svc.log_event(db=db, event_type="e", action="a", description="d")
        assert audit_id is not None
        record = db.add.call_args.args[0]
        assert record.ip_address is None
        assert json.loads(record.metadata_json) == {"audit_subtype": "generic"}

    def test_log_event_metadata_serialization_failure(self, caplog):
        svc = self._service()
        db = MagicMock()
        with caplog.at_level(logging.WARNING, logger="core.audit_service"):
            svc.log_event(db=db, event_type="e", action="a", description="d",
                          metadata={"bad": object()})
        assert "Failed to serialize audit metadata" in caplog.text
        record = db.add.call_args.args[0]
        assert isinstance(record.metadata_json, str)


class TestAuditServiceTyped:
    def _service(self):
        return AuditService()

    def _request(self):
        req = MagicMock()
        req.client.host = "10.0.0.2"
        req.headers.get.return_value = "req-agent"
        return req

    def test_canvas_audit(self):
        svc = self._service()
        db = MagicMock()
        audit_id = svc.create_canvas_audit(
            db=db, agent_id="ag1", agent_execution_id="ex1", user_id="u1",
            canvas_id="cv1", session_id="s1", canvas_type="chart", component_type="pie",
            component_name="Sales", action="render", governance_check_passed=True,
            metadata={"extra": 1}, request=self._request())
        assert audit_id is not None
        record = db.add.call_args.args[0]
        assert record.agent_id == "ag1"
        assert record.canvas_id == "cv1"
        assert record.action_type == "render"
        assert record.details_json["component_name"] == "Sales"
        assert record.details_json["ip_address"] == "10.0.0.2"
        assert record.details_json["user_agent"] == "req-agent"
        assert record.details_json["extra"] == 1

    def test_browser_audit_with_match_confidence(self):
        svc = self._service()
        db = MagicMock()
        metadata = {"match_confidence": {
            "level": "EXTERNAL_VERIFIED", "provenance": "oracle", "score": 0.97,
        }}
        svc.create_browser_audit(
            db=db, agent_id="ag1", agent_execution_id="ex1", user_id="u1",
            session_id="s1", action="navigate", url="https://example.com",
            metadata=metadata)
        record = db.add.call_args.args[0]
        assert record.action == "navigate"
        assert record.endpoint == "https://example.com"
        assert record.action_target == "https://example.com"
        assert record.match_level == "EXTERNAL_VERIFIED"
        assert record.match_confidence_provenance == "oracle"
        assert record.match_confidence_score == 0.97

    def test_browser_audit_without_url(self):
        svc = self._service()
        db = MagicMock()
        svc.create_browser_audit(db=db, agent_id=None, agent_execution_id=None,
                                 user_id="u1", session_id="s1", action="click")
        record = db.add.call_args.args[0]
        assert record.action == "click"
        assert record.endpoint == "click"

    def test_device_audit(self):
        svc = self._service()
        db = MagicMock()
        svc.create_device_audit(db=db, agent_id="ag1", agent_execution_id="ex1",
                                user_id="u1", action="capture", device_type="camera",
                                metadata={"mode": "photo"})
        record = db.add.call_args.args[0]
        assert record.device_type == "camera"
        assert record.action_type == "capture"
        assert record.metadata_json["mode"] == "photo"

    def test_agent_audit(self):
        svc = self._service()
        db = MagicMock()
        svc.create_agent_audit(db=db, agent_id="ag1", agent_execution_id="ex1",
                               user_id="u1", action="run", workspace_id="w1",
                               metadata={"steps": 3})
        record = db.add.call_args.args[0]
        assert record.action == "run"
        assert record.workspace_id == "w1"

    def test_agent_audit_default_workspace(self):
        svc = self._service()
        db = MagicMock()
        svc.create_agent_audit(db=db, agent_id="ag1", agent_execution_id="ex1",
                               user_id="u1", action="run")
        record = db.add.call_args.args[0]
        assert record.workspace_id == "default"


class TestAuditServiceRetry:
    def test_retry_then_success(self):
        svc = AuditService(max_retries=1)
        db = MagicMock()
        with patch.object(svc, "_create_generic_audit_record",
                          side_effect=[RuntimeError("first"), "id-2"]):
            audit_id = svc.log_event(db=db, event_type="e", action="a", description="d")
        assert audit_id == "id-2"

    def test_all_attempts_fail_returns_none(self):
        svc = AuditService(max_retries=2)
        db = MagicMock()
        with patch.object(svc, "_create_generic_audit_record",
                          side_effect=RuntimeError("always fails")):
            assert svc.log_event(db=db, event_type="e", action="a", description="d") is None

    def test_audit_type_routing(self):
        svc = AuditService()
        db = MagicMock()
        with patch.object(svc, "_create_canvas_audit_record", return_value="c") as canvas, \
             patch.object(svc, "_create_browser_audit_record", return_value="b") as browser, \
             patch.object(svc, "_create_device_audit_record", return_value="d") as device, \
             patch.object(svc, "_create_generic_audit_record", return_value="g") as generic:
            assert svc._log_with_retry(db, AuditType.CANVAS, {"user_id": "u"}) == "c"
            assert svc._log_with_retry(db, AuditType.BROWSER, {"user_id": "u"}) == "b"
            assert svc._log_with_retry(db, AuditType.DEVICE, {"user_id": "u"}) == "d"
            assert svc._log_with_retry(db, AuditType.AGENT, {"user_id": "u"}) == "g"
            assert svc._log_with_retry(db, AuditType.PACKAGE, {"user_id": "u"}) == "g"
            assert svc._log_with_retry(db, AuditType.GENERIC, {"user_id": "u"}) == "g"
            assert generic.call_count == 3
            assert generic.call_args_list[0].args[2] == "agent"
            assert generic.call_args_list[1].args[2] == "generic"


class TestAuditServicePackageAudit:
    def _service(self):
        return AuditService()

    def test_package_audit_basic(self):
        svc = self._service()
        db = MagicMock()
        audit_id = svc.create_package_audit(
            db=db, agent_id="ag1", agent_execution_id="ex1", user_id="u1",
            action="install", package_name="numpy", package_version="1.21.0",
            package_type="python")
        assert audit_id is not None
        record = db.add.call_args.args[0]
        assert record.event_type == "package_operation"
        assert record.action == "install"
        assert record.resource == "python:numpy:1.21.0"
        assert record.description == "install python package numpy@1.21.0"
        metadata = json.loads(record.metadata_json)
        assert metadata["package_name"] == "numpy"
        assert metadata["package_version"] == "1.21.0"
        assert metadata["package_type"] == "python"
        assert metadata["agent_id"] == "ag1"
        assert metadata["skill_id"] is None
        assert metadata["governance_decision"] is None

    def test_package_audit_with_governance_and_skill(self):
        svc = self._service()
        db = MagicMock()
        svc.create_package_audit(
            db=db, agent_id="ag1", agent_execution_id=None, user_id="u1",
            action="governance_decision", package_name="lodash", package_version="4.17.21",
            package_type="npm", skill_id="skill-1",
            governance_decision="denied", governance_reason="unsafe",
            metadata={"existing": True})
        record = db.add.call_args.args[0]
        assert record.description == "governance_decision npm package lodash@4.17.21 (denied) for skill skill-1"
        metadata = json.loads(record.metadata_json)
        assert metadata["governance_decision"] == "denied"
        assert metadata["governance_reason"] == "unsafe"
        assert metadata["skill_id"] == "skill-1"
        assert metadata["existing"] is True

    def test_global_audit_service_instance(self):
        from core.audit_service import audit_service
        assert isinstance(audit_service, AuditService)


# ===========================================================================
# core/automation_insight_manager.py
# ===========================================================================

class TestDriftMetrics:
    def _make_db(self, tmp_path, rows):
        path = tmp_path / "analytics.db"
        conn = sqlite3.connect(str(path))
        conn.execute("""
            CREATE TABLE workflow_events (
                workflow_id TEXT, event_type TEXT, user_id TEXT, timestamp TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO workflow_events VALUES (?, ?, ?, ?)", rows)
        conn.commit()
        conn.close()
        return str(path)

    def test_drift_metrics_recommendations(self, tmp_path):
        now = datetime.now().isoformat()
        rows = [
            ("wf-opt", "step_completed", "u1", now),
            ("wf-opt", "step_completed", "u1", now),
            ("wf-opt", "manual_override", "u1", now),
            ("wf-opt", "manual_override", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-high", "step_completed", "u1", now),
            ("wf-stable", "step_completed", "u1", now),
            ("wf-stable", "step_completed", "u1", now),
            ("wf-stable", "step_completed", "u1", now),
            ("wf-old", "step_completed", "u1", (datetime.now() - timedelta(days=40)).isoformat()),
            ("wf-other", "step_completed", "u2", now),
        ]
        path = self._make_db(tmp_path, rows)
        from core.automation_insight_manager import AutomationInsightManager
        mgr = AutomationInsightManager(db_path=path)
        insights = mgr.get_drift_metrics("u1")
        by_id = {i["workflow_id"]: i for i in insights}
        assert set(by_id) == {"wf-opt", "wf-high", "wf-stable"}
        assert by_id["wf-opt"]["recommendation"] == "OPTIMIZE (High Overrides)"
        assert by_id["wf-opt"]["drift_score"] == 1.0
        assert by_id["wf-high"]["recommendation"] == "HIGH_CONFIDENCE"
        assert by_id["wf-stable"]["recommendation"] == "STABLE"

    def test_drift_metrics_workflow_filter(self, tmp_path):
        now = datetime.now().isoformat()
        rows = [
            ("wf-1", "step_completed", "u1", now),
            ("wf-1", "manual_override", "u1", now),
            ("wf-2", "step_completed", "u1", now),
        ]
        path = self._make_db(tmp_path, rows)
        from core.automation_insight_manager import AutomationInsightManager
        mgr = AutomationInsightManager(db_path=path)
        insights = mgr.get_drift_metrics("u1", workflow_id="wf-1")
        assert len(insights) == 1
        assert insights[0]["workflow_id"] == "wf-1"

    def test_drift_metrics_no_rows(self, tmp_path):
        path = self._make_db(tmp_path, [])
        from core.automation_insight_manager import AutomationInsightManager
        mgr = AutomationInsightManager(db_path=path)
        assert mgr.get_drift_metrics("nobody") == []

    def test_drift_metrics_error_returns_empty(self, tmp_path):
        from core.automation_insight_manager import AutomationInsightManager
        db_file = tmp_path / "empty.db"
        db_file.write_bytes(b"")
        mgr = AutomationInsightManager(db_path=str(db_file))
        assert mgr.get_drift_metrics("u1") == []

    def test_generate_all_insights(self, tmp_path):
        from core.automation_insight_manager import AutomationInsightManager
        mgr = AutomationInsightManager(db_path=str(tmp_path / "x.db"))
        with patch.object(mgr, "get_drift_metrics", return_value=[
            {"workflow_id": "a", "recommendation": "OPTIMIZE (High Overrides)"},
            {"workflow_id": "b", "recommendation": "STABLE"},
            {"workflow_id": "c", "recommendation": "STABLE"},
        ]) as gdm:
            out = mgr.generate_all_insights("u1")
            gdm.assert_called_once_with("u1")
        assert out["summary"] == {"total_monitored": 3, "needs_optimization": 1, "stable": 2}
        assert "timestamp" in out


class TestUnderutilizationInsights:
    def test_returns_underutilized(self):
        from core.automation_insight_manager import AutomationInsightManager
        rows = [
            SimpleNamespace(workflow_id="w1", execution_count=0),
            SimpleNamespace(workflow_id="w2", execution_count=2),
            SimpleNamespace(workflow_id="w3", execution_count=5),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = rows
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.database.get_db_session", return_value=cm):
            mgr = AutomationInsightManager(db_path="/tmp/nonexistent-analytics.db")
            out = mgr.get_underutilization_insights()
        assert [i["workflow_id"] for i in out] == ["w1", "w2"]
        assert out[0]["status"] == "UNDERUTILIZED"

    def test_no_rows(self):
        from core.automation_insight_manager import AutomationInsightManager
        db = MagicMock()
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.database.get_db_session", return_value=cm):
            mgr = AutomationInsightManager(db_path="/tmp/nonexistent-analytics.db")
            assert mgr.get_underutilization_insights() == []

    def test_exception_returns_empty(self):
        from core.automation_insight_manager import AutomationInsightManager
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            mgr = AutomationInsightManager(db_path="/tmp/nonexistent-analytics.db")
            assert mgr.get_underutilization_insights() == []


class TestInsightManagerSingleton:
    def test_singleton(self):
        import core.automation_insight_manager as mod
        mod._insight_manager = None
        a = mod.get_insight_manager()
        b = mod.get_insight_manager()
        assert a is b
        assert isinstance(a, mod.AutomationInsightManager)

    def test_singleton_preset(self):
        import core.automation_insight_manager as mod
        sentinel = MagicMock()
        mod._insight_manager = sentinel
        assert mod.get_insight_manager() is sentinel


# ===========================================================================
# core/background_agent_runner.py
# ===========================================================================

class TestAgentDataClasses:
    def test_agent_log_to_dict(self):
        ts = datetime(2026, 1, 1, 12, 0, 0)
        log = AgentLog(timestamp=ts, agent_id="a1", event="started", details="d", status="info")
        assert log.to_dict() == {
            "timestamp": "2026-01-01T12:00:00", "agent_id": "a1", "event": "started",
            "details": "d", "status": "info",
        }

    def test_agent_log_defaults(self):
        log = AgentLog(timestamp=datetime.now(), agent_id="a1", event="e")
        assert log.details is None
        assert log.status == "info"

    def test_agent_state_defaults(self):
        state = AgentState(agent_id="a1")
        assert state.status is AgentStatus.STOPPED
        assert state.last_run is None
        assert state.run_count == 0
        assert state.interval_seconds == 3600

    def test_status_values(self):
        assert AgentStatus.STOPPED.value == "stopped"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.PAUSED.value == "paused"
        assert AgentStatus.ERROR.value == "error"


class TestBackgroundAgentRunner:
    def test_register_agent(self, tmp_path):
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        runner.register_agent("a1", interval_seconds=60)
        assert runner._agents["a1"].interval_seconds == 60
        assert runner._logs[-1].event == "registered"

    def test_start_agent_unregistered_raises(self, tmp_path):
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        with pytest.raises(ValueError):
            _run(runner.start_agent("nope"))

    def test_start_agent_idempotent_when_running(self, tmp_path):
        async def scenario():
            runner = BackgroundAgentRunner(log_dir=str(tmp_path))
            runner.register_agent("a1")
            with patch("core.background_agent_runner.asyncio.sleep", new=AsyncMock()):
                await runner.start_agent("a1")
                first_task = runner._tasks["a1"]
                await runner.start_agent("a1")
                assert runner._tasks["a1"] is first_task
            await runner.stop_agent("a1")
        _run(scenario())

    def test_stop_agent_unknown_id(self, tmp_path):
        async def scenario():
            runner = BackgroundAgentRunner(log_dir=str(tmp_path))
            await runner.stop_agent("ghost")
        _run(scenario())

    def test_run_loop_happy_path(self, tmp_path):
        async def scenario():
            runner = BackgroundAgentRunner(log_dir=str(tmp_path))
            runner.register_agent("a1", interval_seconds=0.001)
            with patch.object(runner, "_execute_agent", new=AsyncMock(return_value={"ok": 1})):
                await runner.start_agent("a1")
                task = runner._tasks["a1"]
                await asyncio.sleep(0.05)
                await runner.stop_agent("a1")
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            state = runner._agents["a1"]
            assert state.run_count >= 1
            assert state.last_run is not None
            assert state.next_run is not None
            assert state.status is AgentStatus.STOPPED
        _run(scenario())

    def test_run_loop_cancelled_during_sleep(self, tmp_path):
        async def scenario():
            runner = BackgroundAgentRunner(log_dir=str(tmp_path))
            runner.register_agent("a1")
            with patch.object(runner, "_execute_agent", new=AsyncMock(return_value={"ok": 1})), \
                 patch("core.background_agent_runner.asyncio.sleep",
                       new=AsyncMock(side_effect=asyncio.CancelledError)):
                await runner.start_agent("a1")
                task = runner._tasks["a1"]
                await task
            state = runner._agents["a1"]
            assert state.run_count == 1
            assert state.status is AgentStatus.RUNNING
        _run(scenario())

    def test_run_loop_error_sets_error_status(self, tmp_path):
        async def scenario():
            runner = BackgroundAgentRunner(log_dir=str(tmp_path))
            runner.register_agent("a1")
            with patch.object(runner, "_execute_agent",
                              new=AsyncMock(side_effect=RuntimeError("boom"))), \
                 patch("core.background_agent_runner.asyncio.sleep", new=AsyncMock()):
                await runner.start_agent("a1")
                task = runner._tasks["a1"]
                await task
            state = runner._agents["a1"]
            assert state.status is AgentStatus.ERROR
            assert state.error_count == 1
            assert state.last_error == "boom"
            assert runner._logs[-1].event == "error"
        _run(scenario())


class TestExecuteAgent:
    def _fake_api(self, in_registry=True, task_result={"status": "done"}):
        agents = {"a1": {"id": "a1"}} if in_registry else {}
        return SimpleNamespace(AGENTS=agents,
                               execute_agent_task=AsyncMock(return_value=task_result))

    def test_execute_with_owner_context(self, tmp_path):
        fake_api = self._fake_api()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(user_id="user-1")
        cm = MagicMock()
        cm.__enter__.return_value = db
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        with patch.dict(sys.modules, {"api.agent_routes": fake_api}), \
             patch("core.database.get_db_session", return_value=cm), \
             patch("core.models.AgentRegistry"):
            result = _run(runner._execute_agent("a1"))
        assert result == {"status": "done"}
        fake_api.execute_agent_task.assert_awaited_once_with(
            "a1", {"id": "a1"}, {"agent_id": "a1", "user_id": "user-1"})
        assert runner._logs[-1].event == "completed"

    def test_execute_without_owner(self, tmp_path):
        fake_api = self._fake_api()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(user_id=None)
        cm = MagicMock()
        cm.__enter__.return_value = db
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        with patch.dict(sys.modules, {"api.agent_routes": fake_api}), \
             patch("core.database.get_db_session", return_value=cm), \
             patch("core.models.AgentRegistry"):
            result = _run(runner._execute_agent("a1"))
        assert result == {"status": "done"}
        fake_api.execute_agent_task.assert_awaited_once_with(
            "a1", {"id": "a1"}, {"agent_id": "a1"})

    def test_execute_no_agent_record(self, tmp_path):
        fake_api = self._fake_api()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        cm = MagicMock()
        cm.__enter__.return_value = db
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        with patch.dict(sys.modules, {"api.agent_routes": fake_api}), \
             patch("core.database.get_db_session", return_value=cm), \
             patch("core.models.AgentRegistry"):
            _run(runner._execute_agent("a1"))
        fake_api.execute_agent_task.assert_awaited_once_with(
            "a1", {"id": "a1"}, {"agent_id": "a1"})

    def test_execute_db_fetch_error_warns_but_runs(self, tmp_path):
        fake_api = self._fake_api()
        db = MagicMock()
        db.query.side_effect = RuntimeError("db hiccup")
        cm = MagicMock()
        cm.__enter__.return_value = db
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        with patch.dict(sys.modules, {"api.agent_routes": fake_api}), \
             patch("core.database.get_db_session", return_value=cm), \
             patch("core.models.AgentRegistry"):
            _run(runner._execute_agent("a1"))
        fake_api.execute_agent_task.assert_awaited_once_with(
            "a1", {"id": "a1"}, {"agent_id": "a1"})

    def test_execute_agent_not_in_registry(self, tmp_path):
        fake_api = self._fake_api(in_registry=False)
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        with patch.dict(sys.modules, {"api.agent_routes": fake_api}):
            assert _run(runner._execute_agent("ghost")) is None
        assert runner._logs[-1].event == "skipped"
        fake_api.execute_agent_task.assert_not_awaited()

    def test_execute_task_error_propagates(self, tmp_path):
        fake_api = SimpleNamespace(AGENTS={"a1": {"id": "a1"}},
                                   execute_agent_task=AsyncMock(side_effect=RuntimeError("task failed")))
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        with patch.dict(sys.modules, {"api.agent_routes": fake_api}):
            with pytest.raises(RuntimeError, match="task failed"):
                _run(runner._execute_agent("a1"))
        assert runner._logs[-1].event == "failed"
        assert runner._logs[-1].status == "error"


class TestRunnerStatusAndLogs:
    def test_get_status_single(self, tmp_path):
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        runner.register_agent("a1")
        status = runner.get_status("a1")
        assert status["agent_id"] == "a1"
        assert status["status"] == "stopped"
        assert status["last_run"] is None
        assert status["run_count"] == 0

    def test_get_status_unknown(self, tmp_path):
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        assert runner.get_status("missing") == {"error": "Agent missing not found"}

    def test_get_status_all(self, tmp_path):
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        runner.register_agent("a1")
        runner.register_agent("a2")
        statuses = runner.get_status()
        assert set(statuses) == {"a1", "a2"}
        assert statuses["a1"]["status"] == "stopped"

    def test_get_logs_filtered_and_limited(self, tmp_path):
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        runner.register_agent("a1")
        runner.register_agent("a2")
        logs = runner.get_logs("a1")
        assert len(logs) == 1
        assert logs[0]["event"] == "registered"
        assert logs[0]["agent_id"] == "a1"
        assert len(runner.get_logs(limit=0)) == 2
        assert len(runner.get_logs(limit=10)) == 2

    def test_logs_written_to_file(self, tmp_path):
        runner = BackgroundAgentRunner(log_dir=str(tmp_path))
        runner.register_agent("a1")
        log_file = tmp_path / "a1.log"
        assert log_file.exists()
        assert "registered" in log_file.read_text()

    def test_global_runner_instance(self):
        from core.background_agent_runner import background_runner
        assert isinstance(background_runner, BackgroundAgentRunner)


# ===========================================================================
# core/enterprise_user_management.py
# ===========================================================================

class _EUFakeQuery:
    def __init__(self, store):
        self._store = store

    def filter(self, *a, **k):
        return self

    def filter_by(self, **k):
        return self

    def first(self):
        rows = self._store.get("rows", [])
        return rows[0] if rows else None

    def all(self):
        return self._store.get("rows", [])

    def delete(self):
        n = len(self._store.get("rows", []))
        self._store["rows"] = []
        return n


class _EUFakeDb:
    """Minimal db stand-in: query(Model) returns FakeQuery bound to a store."""

    def __init__(self):
        self.stores = {}
        self.commits = 0
        self.added = []
        self.deleted = []
        self.refreshed = []

    def query(self, model):
        return _EUFakeQuery(self.stores.setdefault(model, {}))

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)
        if not hasattr(obj, "id") or getattr(obj, "id") is None:
            obj.id = "auto-id"


def _ws(**overrides):
    base = dict(
        id="ws-1", name="Acme", description="desc", status="active",
        plan_tier="standard", created_at=datetime(2026, 1, 1),
        updated_at=None, users=[], teams=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _team(**overrides):
    base = dict(
        id="team-1", name="Eng", description="eng team", workspace_id="ws-1",
        created_at=datetime(2026, 1, 1), members=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _user(**overrides):
    base = dict(
        id="user-1", email="a@b.c", first_name="Ann", last_name="Bee",
        role="member", status="active", workspace_id="ws-1",
        created_at=datetime(2026, 1, 1), last_login=None, teams=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestEnterpriseWorkspaces:
    async def test_create_workspace(self):
        from core.enterprise_user_management import create_workspace
        db = _EUFakeDb()
        out = await create_workspace(data=WorkspaceCreate(name="Acme"), db=db)
        assert out == {"workspace_id": "auto-id"}
        assert db.commits == 1
        assert db.refreshed
        assert db.added[0].name == "Acme"
        assert db.added[0].plan_tier == "standard"

    async def test_list_workspaces(self):
        from core.enterprise_user_management import list_workspaces
        db = _EUFakeDb()
        db.stores.setdefault(None, {})["rows"] = None  # placeholder
        from core.models import Workspace
        db.stores[Workspace] = {"rows": [_ws(), _ws(id="ws-2", created_at=None, updated_at=None)]}
        out = await list_workspaces(db=db)
        assert len(out) == 2
        assert out[0]["workspace_id"] == "ws-1"
        assert out[0]["user_count"] == 0
        assert out[1]["created_at"] is None

    async def test_get_workspace_found(self):
        from core.enterprise_user_management import get_workspace
        db = _EUFakeDb()
        from core.models import Workspace
        db.stores[Workspace] = {"rows": [_ws()]}
        out = await get_workspace("ws-1", db=db)
        assert out["name"] == "Acme"
        assert out["updated_at"] is None

    async def test_get_workspace_not_found(self):
        from core.enterprise_user_management import get_workspace
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await get_workspace("missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_update_workspace_all_fields(self):
        from core.enterprise_user_management import update_workspace
        db = _EUFakeDb()
        from core.models import Workspace
        db.stores[Workspace] = {"rows": [_ws()]}
        out = await update_workspace("ws-1", data=WorkspaceUpdate(
            name="New", description="nd", status="suspended", plan_tier="enterprise"), db=db)
        assert out == {"message": "Workspace updated successfully"}
        ws = db.stores[Workspace]["rows"][0]
        assert ws.name == "New" and ws.description == "nd"
        assert ws.status == "suspended" and ws.plan_tier == "enterprise"
        assert db.commits == 1

    async def test_update_workspace_partial(self):
        from core.enterprise_user_management import update_workspace
        db = _EUFakeDb()
        from core.models import Workspace
        db.stores[Workspace] = {"rows": [_ws()]}
        await update_workspace("ws-1", data=WorkspaceUpdate(name="Only name"), db=db)
        ws = db.stores[Workspace]["rows"][0]
        assert ws.name == "Only name"
        assert ws.description == "desc"

    async def test_update_workspace_not_found(self):
        from core.enterprise_user_management import update_workspace
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await update_workspace("missing", data=WorkspaceUpdate(name="x"), db=db)
        assert exc_info.value.status_code == 404

    async def test_delete_workspace(self):
        from core.enterprise_user_management import delete_workspace
        db = _EUFakeDb()
        from core.models import Workspace
        db.stores[Workspace] = {"rows": [_ws()]}
        out = await delete_workspace("ws-1", db=db)
        assert out == {"message": "Workspace deleted successfully"}
        assert db.stores[Workspace]["rows"][0].status == "deleted"
        assert db.commits == 1

    async def test_delete_workspace_not_found(self):
        from core.enterprise_user_management import delete_workspace
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await delete_workspace("missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_get_workspace_teams(self):
        from core.enterprise_user_management import get_workspace_teams
        db = _EUFakeDb()
        from core.models import Team, Workspace
        db.stores[Workspace] = {"rows": [_ws()]}
        db.stores[Team] = {"rows": [_team(id="t1"), _team(id="t2", created_at=None)]}
        out = await get_workspace_teams("ws-1", db=db)
        assert len(out) == 2
        assert out[0]["team_id"] == "t1"
        assert out[1]["created_at"] is None

    async def test_get_workspace_teams_not_found(self):
        from core.enterprise_user_management import get_workspace_teams
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await get_workspace_teams("missing", db=db)
        assert exc_info.value.status_code == 404


class TestEnterpriseTeams:
    async def test_create_team(self):
        from core.enterprise_user_management import create_team
        db = _EUFakeDb()
        from core.models import Workspace
        db.stores[Workspace] = {"rows": [_ws()]}
        out = await create_team(data=TeamCreate(name="Eng", workspace_id="ws-1"), db=db)
        assert out == {"team_id": "auto-id"}
        assert db.added[0].workspace_id == "ws-1"

    async def test_create_team_workspace_missing(self):
        from core.enterprise_user_management import create_team
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await create_team(data=TeamCreate(name="Eng", workspace_id="missing"), db=db)
        assert exc_info.value.status_code == 404

    async def test_list_teams_all(self):
        from core.enterprise_user_management import list_teams
        db = _EUFakeDb()
        from core.models import Team
        db.stores[Team] = {"rows": [_team(), _team(id="t2")]}
        out = await list_teams(db=db)
        assert len(out) == 2

    async def test_list_teams_filtered(self):
        from core.enterprise_user_management import list_teams
        db = _EUFakeDb()
        from core.models import Team
        db.stores[Team] = {"rows": [_team()]}
        out = await list_teams(workspace_id="ws-1", db=db)
        assert len(out) == 1
        assert out[0]["workspace_id"] == "ws-1"

    async def test_get_team_with_members(self):
        from core.enterprise_user_management import get_team
        db = _EUFakeDb()
        from core.models import Team
        team = _team(members=[_user(), _user(id="user-2")])
        db.stores[Team] = {"rows": [team]}
        out = await get_team("team-1", db=db)
        assert out["team_id"] == "team-1"
        assert out["member_count"] == 2
        assert out["members"][0]["email"] == "a@b.c"

    async def test_get_team_not_found(self):
        from core.enterprise_user_management import get_team
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await get_team("missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_update_team(self):
        from core.enterprise_user_management import update_team
        db = _EUFakeDb()
        from core.models import Team
        db.stores[Team] = {"rows": [_team()]}
        out = await update_team("team-1", data=TeamUpdate(name="New", description="nd"), db=db)
        assert out == {"message": "Team updated successfully"}
        assert db.stores[Team]["rows"][0].name == "New"

    async def test_update_team_partial(self):
        from core.enterprise_user_management import update_team
        db = _EUFakeDb()
        from core.models import Team
        db.stores[Team] = {"rows": [_team()]}
        await update_team("team-1", data=TeamUpdate(name="Only"), db=db)
        assert db.stores[Team]["rows"][0].description == "eng team"

    async def test_update_team_not_found(self):
        from core.enterprise_user_management import update_team
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await update_team("missing", data=TeamUpdate(name="x"), db=db)
        assert exc_info.value.status_code == 404

    async def test_delete_team(self):
        from core.enterprise_user_management import delete_team
        db = _EUFakeDb()
        from core.models import Team
        db.stores[Team] = {"rows": [_team()]}
        out = await delete_team("team-1", db=db)
        assert out == {"message": "Team deleted successfully"}
        assert db.deleted[0].id == "team-1"
        assert db.commits == 1

    async def test_delete_team_not_found(self):
        from core.enterprise_user_management import delete_team
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await delete_team("missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_add_team_member(self):
        from core.enterprise_user_management import add_team_member
        db = _EUFakeDb()
        from core.models import Team, User
        db.stores[Team] = {"rows": [_team()]}
        db.stores[User] = {"rows": [_user()]}
        out = await add_team_member("team-1", "user-1", db=db)
        assert out == {"message": "User added to team successfully"}
        assert len(db.stores[Team]["rows"][0].members) == 1
        assert db.commits == 1

    async def test_add_team_member_team_missing(self):
        from core.enterprise_user_management import add_team_member
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await add_team_member("missing", "user-1", db=db)
        assert exc_info.value.status_code == 404

    async def test_add_team_member_user_missing(self):
        from core.enterprise_user_management import add_team_member
        db = _EUFakeDb()
        from core.models import Team
        db.stores[Team] = {"rows": [_team()]}
        with pytest.raises(Exception) as exc_info:
            await add_team_member("team-1", "missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_add_team_member_already_member(self):
        from core.enterprise_user_management import add_team_member
        db = _EUFakeDb()
        from core.models import Team, User
        user = _user()
        db.stores[Team] = {"rows": [_team(members=[user])]}
        db.stores[User] = {"rows": [user]}
        with pytest.raises(Exception) as exc_info:
            await add_team_member("team-1", "user-1", db=db)
        assert exc_info.value.status_code == 400

    async def test_remove_team_member(self):
        from core.enterprise_user_management import remove_team_member
        db = _EUFakeDb()
        from core.models import Team, User
        user = _user()
        team = _team(members=[user])
        db.stores[Team] = {"rows": [team]}
        db.stores[User] = {"rows": [user]}
        out = await remove_team_member("team-1", "user-1", db=db)
        assert out == {"message": "User removed from team successfully"}
        assert team.members == []
        assert db.commits == 1

    async def test_remove_team_member_team_missing(self):
        from core.enterprise_user_management import remove_team_member
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await remove_team_member("missing", "user-1", db=db)
        assert exc_info.value.status_code == 404

    async def test_remove_team_member_user_missing(self):
        from core.enterprise_user_management import remove_team_member
        db = _EUFakeDb()
        from core.models import Team
        db.stores[Team] = {"rows": [_team()]}
        with pytest.raises(Exception) as exc_info:
            await remove_team_member("team-1", "missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_remove_team_member_not_a_member(self):
        from core.enterprise_user_management import remove_team_member
        db = _EUFakeDb()
        from core.models import Team, User
        db.stores[Team] = {"rows": [_team()]}
        db.stores[User] = {"rows": [_user()]}
        with pytest.raises(Exception) as exc_info:
            await remove_team_member("team-1", "user-1", db=db)
        assert exc_info.value.status_code == 400


class TestEnterpriseUsers:
    async def test_list_users_all(self):
        from core.enterprise_user_management import list_users
        db = _EUFakeDb()
        from core.models import User
        db.stores[User] = {"rows": [_user(), _user(id="user-2", created_at=None)]}
        out = await list_users(db=db)
        assert len(out) == 2
        assert out[0]["email"] == "a@b.c"
        assert out[1]["created_at"] is None
        assert out[1]["last_login"] is None

    async def test_list_users_filtered(self):
        from core.enterprise_user_management import list_users
        db = _EUFakeDb()
        from core.models import User
        db.stores[User] = {"rows": [_user()]}
        out = await list_users(workspace_id="ws-1", db=db)
        assert len(out) == 1

    async def test_get_user_with_teams(self):
        from core.enterprise_user_management import get_user
        db = _EUFakeDb()
        from core.models import User
        user = _user(teams=[_team(id="t1"), _team(id="t2")])
        db.stores[User] = {"rows": [user]}
        out = await get_user("user-1", db=db)
        assert out["user_id"] == "user-1"
        assert [t["team_id"] for t in out["teams"]] == ["t1", "t2"]

    async def test_get_user_not_found(self):
        from core.enterprise_user_management import get_user
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await get_user("missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_update_user_all_fields(self):
        from core.enterprise_user_management import update_user
        db = _EUFakeDb()
        from core.models import User
        db.stores[User] = {"rows": [_user()]}
        out = await update_user("user-1", data=UserUpdate(
            first_name="New", last_name="Name", role="admin", status="suspended"), db=db)
        assert out == {"message": "User updated successfully"}
        u = db.stores[User]["rows"][0]
        assert u.first_name == "New" and u.last_name == "Name"
        assert u.role == "admin" and u.status == "suspended"

    async def test_update_user_invalid_role(self):
        from core.enterprise_user_management import update_user
        db = _EUFakeDb()
        from core.models import User
        db.stores[User] = {"rows": [_user()]}
        with pytest.raises(Exception) as exc_info:
            await update_user("user-1", data=UserUpdate(role="root"), db=db)
        assert exc_info.value.status_code == 400
        assert "Invalid role" in str(exc_info.value.detail)

    async def test_update_user_partial(self):
        from core.enterprise_user_management import update_user
        db = _EUFakeDb()
        from core.models import User
        db.stores[User] = {"rows": [_user()]}
        await update_user("user-1", data=UserUpdate(first_name="Only"), db=db)
        u = db.stores[User]["rows"][0]
        assert u.first_name == "Only"
        assert u.last_name == "Bee"

    async def test_update_user_not_found(self):
        from core.enterprise_user_management import update_user
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await update_user("missing", data=UserUpdate(first_name="x"), db=db)
        assert exc_info.value.status_code == 404

    async def test_deactivate_user(self):
        from core.enterprise_user_management import deactivate_user
        db = _EUFakeDb()
        from core.models import User, UserStatus
        db.stores[User] = {"rows": [_user()]}
        out = await deactivate_user("user-1", db=db)
        assert out == {"message": "User deactivated successfully"}
        assert db.stores[User]["rows"][0].status == UserStatus.DELETED.value
        assert db.commits == 1

    async def test_deactivate_user_not_found(self):
        from core.enterprise_user_management import deactivate_user
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await deactivate_user("missing", db=db)
        assert exc_info.value.status_code == 404

    async def test_get_user_teams(self):
        from core.enterprise_user_management import get_user_teams
        db = _EUFakeDb()
        from core.models import User
        user = _user(teams=[_team(id="t1")])
        db.stores[User] = {"rows": [user]}
        out = await get_user_teams("user-1", db=db)
        assert len(out) == 1
        assert out[0]["team_id"] == "t1"
        assert out[0]["description"] == "eng team"

    async def test_get_user_teams_not_found(self):
        from core.enterprise_user_management import get_user_teams
        db = _EUFakeDb()
        with pytest.raises(Exception) as exc_info:
            await get_user_teams("missing", db=db)
        assert exc_info.value.status_code == 404


class TestEnterpriseEmailStrFallback:
    def test_emailstr_import_fallback_branch(self):
        """Cover the ImportError fallback (EmailStr = str) via a pydantic swap + reload.

        The try branch (EMAIL_VALIDATION_AVAILABLE=True) is covered by the
        module's normal import in every other test.
        """
        import core.enterprise_user_management as eum
        real_pydantic = sys.modules.get("pydantic")
        fake = types.ModuleType("pydantic")

        def _getattr(name):
            if name == "EmailStr":
                raise ImportError("email-validator is not installed")
            return getattr(real_pydantic, name)

        fake.__getattr__ = _getattr
        sys.modules["pydantic"] = fake
        try:
            importlib.reload(eum)
            assert eum.EMAIL_VALIDATION_AVAILABLE is False
            assert eum.EmailStr is str
        finally:
            sys.modules["pydantic"] = real_pydantic
