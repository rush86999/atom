"""
Coverage-push tests — core modules wave B (part 1).

Targets modules with little/no existing coverage:
  - core.ai_service            (0%)
  - core.analytics_engine      (0%)
  - core.app_secrets           (0%)
  - core.audit_logger          (94% -> top-up)
  - core.capability_resolver   (79% -> top-up)

All DB/HTTP/LLM interactions are mocked; no real network or repo writes
(analytics data + secrets files are redirected to tmp dirs).
"""
import json
import logging
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# core.ai_service
# ============================================================================


class TestAIService:
    def _reload(self, monkeypatch, allow_mock):
        monkeypatch.setenv("ALLOW_MOCK_AI", "true" if allow_mock else "false")
        import importlib
        import core.ai_service as mod
        mod = importlib.reload(mod)
        return mod

    def _block_import(self, monkeypatch):
        """Force `from enhanced_ai_workflow_endpoints import ai_service` to
        raise ImportError (the module exists on disk, so deleting sys.modules
        is not enough)."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "enhanced_ai_workflow_endpoints":
                raise ImportError("no module named enhanced_ai_workflow_endpoints")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)

    def test_returns_real_service_when_import_succeeds(self, monkeypatch):
        mod = self._reload(monkeypatch, allow_mock=False)
        fake = MagicMock()
        fake_module = types.ModuleType("enhanced_ai_workflow_endpoints")
        fake_module.ai_service = fake
        monkeypatch.setitem(sys.modules, "enhanced_ai_workflow_endpoints", fake_module)
        assert mod.get_ai_service() is fake

    def test_returns_mock_when_import_fails_and_mock_allowed(self, monkeypatch):
        mod = self._reload(monkeypatch, allow_mock=True)
        self._block_import(monkeypatch)
        svc = mod.get_ai_service()
        assert isinstance(svc, mod.MockAIService)

    def test_raises_import_error_when_mock_not_allowed(self, monkeypatch):
        mod = self._reload(monkeypatch, allow_mock=False)
        self._block_import(monkeypatch)
        with pytest.raises(ImportError):
            mod.get_ai_service()

    @pytest.mark.asyncio
    async def test_mock_process_with_nlu(self):
        from core.ai_service import MockAIService
        svc = MockAIService()
        result = await svc.process_with_nlu("hello", user_id="u1")
        assert result["nlu_result"]["status"] == "mocked"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_mock_analyze_text(self):
        from core.ai_service import MockAIService
        svc = MockAIService()
        text = await svc.analyze_text("analyze", complexity=2, user_id="u1")
        assert "Mocked AI response" in text

    @pytest.mark.asyncio
    async def test_mock_run_react_agent(self):
        from core.ai_service import MockAIService
        svc = MockAIService()
        result = await svc.run_react_agent("do a thing", provider="openai")
        assert result["final_answer"] == "Mock ReAct agent response"
        assert result["confidence_score"] == 0.0


# ============================================================================
# core.analytics_engine
# ============================================================================


class TestAnalyticsEngine:
    _ORIG_INIT = None

    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch, tmp_path):
        from core import analytics_engine as m

        if TestAnalyticsEngine._ORIG_INIT is None:
            TestAnalyticsEngine._ORIG_INIT = m.AnalyticsEngine.__init__
        monkeypatch.setattr(m.AnalyticsEngine, "_instance", None)
        monkeypatch.setattr(m, "_analytics_engine", None)

        # Redirect every construction to the tmp dir. The real __init__
        # hard-codes backend/analytics_data (which holds real repo data and
        # must never be written by tests); the real constructor is exercised
        # separately in test_real_constructor.
        def _redirected_init(self):
            self.data_dir = str(tmp_path)
            self.workflow_metrics = {}
            self.integration_metrics = {}
            self._load_data()
            self._initialized = True

        monkeypatch.setattr(m.AnalyticsEngine, "__init__", _redirected_init)

    def test_real_constructor_initializes(self):
        """The REAL __init__ runs once (makedirs + _load_data + flag) with
        _load_data mocked so the repo analytics dir is never touched."""
        from core import analytics_engine as m
        from unittest.mock import patch as mpatch

        m.AnalyticsEngine.__init__ = TestAnalyticsEngine._ORIG_INIT
        m.AnalyticsEngine._instance = None
        try:
            with mpatch.object(m.AnalyticsEngine, "_load_data") as mock_load:
                e = m.AnalyticsEngine()
                mock_load.assert_called_once()
            assert e._initialized is True
            assert e.workflow_metrics == {}
        finally:
            m.AnalyticsEngine._instance = None

    def test_constructor_noop_on_second_init(self):
        from core import analytics_engine as m

        m.AnalyticsEngine.__init__ = TestAnalyticsEngine._ORIG_INIT
        m.AnalyticsEngine._instance = None
        try:
            with patch.object(m.AnalyticsEngine, "_load_data"):
                e = m.AnalyticsEngine()
            orig = e.workflow_metrics
            # Second __init__ on the same instance is a no-op (keeps state).
            m.AnalyticsEngine.__init__(e)
            assert e.workflow_metrics is orig
        finally:
            m.AnalyticsEngine._instance = None

    def test_singleton_and_properties(self, tmp_path):
        from core.analytics_engine import AnalyticsEngine, WorkflowMetric, IntegrationMetric

        e1 = AnalyticsEngine()
        e2 = AnalyticsEngine()
        assert e1 is e2
        assert e1.data_dir == str(tmp_path)
        assert e1.workflow_metrics == {}
        assert e1.integration_metrics == {}

        wf = WorkflowMetric()
        assert wf.success_rate == 0.0
        assert wf.average_duration == 0.0
        wf2 = WorkflowMetric(execution_count=4, success_count=3, total_duration_seconds=8)
        assert wf2.success_rate == 75.0
        assert wf2.average_duration == 2.0

        im = IntegrationMetric()
        assert im.error_rate == 0.0
        assert im.average_response_time == 0.0
        assert im.uptime_percentage == 100.0
        im2 = IntegrationMetric(call_count=10, error_count=3, total_response_time_ms=100)
        assert im2.error_rate == 30.0
        assert im2.average_response_time == 10.0
        assert im2.uptime_percentage == 70.0

    def test_track_workflow_execution_and_persistence(self, tmp_path):
        from core.analytics_engine import AnalyticsEngine, get_analytics_engine

        e = AnalyticsEngine()
        e.track_workflow_execution("wf1", success=True, duration_seconds=10, time_saved_seconds=60, business_value=99.5)
        e.track_workflow_execution("wf1", success=False, duration_seconds=5)
        assert e.workflow_metrics["wf1"].execution_count == 2
        assert e.workflow_metrics["wf1"].failure_count == 1
        assert e.workflow_metrics["wf1"].last_executed is not None

        # Files persisted -> a fresh instance reloads them.
        fresh = AnalyticsEngine.__new__(AnalyticsEngine)
        fresh._initialized = True
        fresh.data_dir = str(tmp_path)
        fresh.workflow_metrics = {}
        fresh.integration_metrics = {}
        fresh._load_data()
        assert fresh.workflow_metrics["wf1"].execution_count == 2

        # get_analytics_engine caches a singleton.
        assert get_analytics_engine() is not None

    def test_integration_metrics_reload_from_file(self, tmp_path):
        from core.analytics_engine import AnalyticsEngine

        e = AnalyticsEngine()
        e.track_integration_call("gmail", success=True, response_time_ms=25)
        fresh = AnalyticsEngine.__new__(AnalyticsEngine)
        fresh._initialized = True
        fresh.data_dir = str(tmp_path)
        fresh.workflow_metrics = {}
        fresh.integration_metrics = {}
        fresh._load_data()
        assert fresh.integration_metrics["gmail"].call_count == 1

    def test_track_integration_call_statuses(self, tmp_path):
        from core.analytics_engine import AnalyticsEngine

        e = AnalyticsEngine()
        e.track_integration_call("slack", success=True, response_time_ms=50)
        assert e.integration_metrics["slack"].status == "READY"
        # 1 failure in 100 calls -> 1% error rate -> PARTIAL (0 < rate <= 10).
        for _ in range(99):
            e.track_integration_call("slack", success=True, response_time_ms=50)
        e.track_integration_call("slack", success=False, response_time_ms=50)
        assert e.integration_metrics["slack"].status == "PARTIAL"
        # >10% failures -> ERROR.
        for _ in range(20):
            e.track_integration_call("slack", success=False, response_time_ms=50)
        assert e.integration_metrics["slack"].status == "ERROR"

    def test_summary_endpoints(self, tmp_path):
        from core.analytics_engine import AnalyticsEngine

        e = AnalyticsEngine()
        e.track_workflow_execution("wf1", success=True, duration_seconds=3600, time_saved_seconds=7200, business_value=100)
        e.track_integration_call("slack", success=True, response_time_ms=10)
        e.track_integration_call("gmail", success=True, response_time_ms=10)

        wf = e.get_workflow_analytics()
        assert wf["total_executions"] == 1
        assert wf["total_time_saved_hours"] == 2.0
        assert wf["total_business_value"] == 100.0
        assert wf["workflow_count"] == 1

        health = e.get_integration_health()
        assert health["total_integrations"] == 2
        assert health["ready_count"] == 2

    def test_load_data_corrupt_files(self, tmp_path, caplog):
        from core.analytics_engine import AnalyticsEngine

        (tmp_path / "workflow_metrics.json").write_text("{not json")
        (tmp_path / "integration_metrics.json").write_text("[1,2,3]")
        e = AnalyticsEngine.__new__(AnalyticsEngine)
        e._initialized = True
        e.data_dir = str(tmp_path)
        e.workflow_metrics = {}
        e.integration_metrics = {}
        with caplog.at_level(logging.ERROR):
            e._load_data()
        assert e.workflow_metrics == {}
        assert e.integration_metrics == {}

    def test_save_data_failure_logged(self, tmp_path, caplog):
        from core.analytics_engine import AnalyticsEngine

        e = AnalyticsEngine()
        # Force a save failure by pointing data_dir at an existing FILE.
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        e.data_dir = str(blocker)
        with caplog.at_level(logging.ERROR):
            e._save_data()
        assert "Error saving analytics data" in caplog.text


# ============================================================================
# core.app_secrets
# ============================================================================


class TestAppSecrets:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)

    def _make_manager(self, monkeypatch, tmp_path):
        """Fresh SecretManager redirected to a tmp dir (no repo writes)."""
        from core.app_secrets import SecretManager

        manager = SecretManager()
        manager._secrets_file = str(tmp_path / "secrets.json")
        manager._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        return manager

    def test_plaintext_lifecycle(self, monkeypatch, tmp_path):
        manager = self._make_manager(monkeypatch, tmp_path)
        assert manager._encryption_enabled is False
        manager.set_secret("API_KEY", "abc123")
        assert manager.get_secret("API_KEY") == "abc123"
        assert (tmp_path / "secrets.json").exists()
        # File contents persisted as plaintext JSON.
        data = json.loads((tmp_path / "secrets.json").read_text())
        assert data["API_KEY"] == "abc123"
        # Missing key falls back to default.
        assert manager.get_secret("NOPE", "def") == "def"

    def test_env_var_takes_priority(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MY_SECRET", "from-env")
        manager = self._make_manager(monkeypatch, tmp_path)
        manager.set_secret("MY_SECRET", "from-store")
        assert manager.get_secret("MY_SECRET") == "from-env"

    def test_get_security_status(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENVIRONMENT", "production")
        manager = self._make_manager(monkeypatch, tmp_path)
        status = manager.get_security_status()
        assert status["encryption_enabled"] is False
        assert status["storage_type"] == "plaintext"
        assert status["environment"] == "production"

    def test_encrypted_lifecycle(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key")
        monkeypatch.setenv("ENVIRONMENT", "development")
        manager = self._make_manager(monkeypatch, tmp_path)
        assert manager._encryption_enabled is True
        manager.set_secret("TOKEN", "t-123")
        assert manager.get_secret("TOKEN") == "t-123"
        enc_file = tmp_path / "secrets.enc"
        assert enc_file.exists()
        plain = tmp_path / "secrets.json"
        assert not plain.exists()
        # Encrypted bytes must not contain the raw value.
        assert b"t-123" not in enc_file.read_bytes()

    def test_load_encrypted_file_first(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key")
        manager = self._make_manager(monkeypatch, tmp_path)
        manager.set_secret("K1", "v1")
        # New manager instance with same paths loads encrypted content.
        from core.app_secrets import SecretManager

        manager2 = SecretManager()
        manager2._secrets_file = str(tmp_path / "secrets.json")
        manager2._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        manager2._init_encryption()
        manager2._load_secrets()
        assert manager2.get_secret("K1") == "v1"

    def test_migrates_plaintext_to_encrypted(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key")
        manager = self._make_manager(monkeypatch, tmp_path)
        # Write a legacy plaintext file, then load: auto-migrate removes it.
        (tmp_path / "secrets.json").write_text(json.dumps({"K2": "v2"}))
        manager._load_secrets()
        assert manager.get_secret("K2") == "v2"
        assert (tmp_path / "secrets.json").exists() is False
        assert (tmp_path / "secrets.enc").exists() is True

    def test_load_corrupt_plaintext_logs_error(self, monkeypatch, tmp_path, caplog):
        manager = self._make_manager(monkeypatch, tmp_path)
        (tmp_path / "secrets.json").write_text("{corrupt")
        with caplog.at_level(logging.ERROR):
            manager._load_secrets()
        assert manager._secrets == {}

    def test_save_failure_returns_false(self, monkeypatch, tmp_path, caplog):
        manager = self._make_manager(monkeypatch, tmp_path)
        manager._secrets_file = str(tmp_path / "no-such-dir" / "secrets.json")
        with caplog.at_level(logging.ERROR):
            assert manager._save_secrets() is False
        assert "Failed to save secrets" in caplog.text

    def test_encryption_init_failure_logs_warning(self, monkeypatch, tmp_path, caplog):
        """A broken cryptography import must degrade to plaintext + warning."""
        monkeypatch.setenv("ENCRYPTION_KEY", "k")
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "cryptography.fernet":
                raise ImportError("cryptography not installed")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        from core.app_secrets import SecretManager

        with caplog.at_level(logging.WARNING):
            manager = SecretManager()
        assert manager._encryption_enabled is False
        assert "Failed to initialize encryption" in caplog.text

    def test_load_encrypted_file_corrupt_falls_back(self, monkeypatch, tmp_path, caplog):
        monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key")
        manager = self._make_manager(monkeypatch, tmp_path)
        (tmp_path / "secrets.enc").write_bytes(b"not-valid-fernet-token")
        (tmp_path / "secrets.json").write_text(json.dumps({"FALLBACK": "y"}))
        with caplog.at_level(logging.ERROR):
            manager._load_secrets()
        assert manager.get_secret("FALLBACK") == "y"
        assert "Failed to load encrypted secrets" in caplog.text

    def test_production_plaintext_load_warns(self, monkeypatch, tmp_path, caplog):
        monkeypatch.setenv("ENVIRONMENT", "production")
        manager = self._make_manager(monkeypatch, tmp_path)
        (tmp_path / "secrets.json").write_text(json.dumps({"P": "1"}))
        with caplog.at_level(logging.WARNING):
            manager._load_secrets()
        assert "plaintext file in production" in caplog.text

    def test_get_secret_manager_global(self):
        from core.app_secrets import get_secret_manager
        assert get_secret_manager() is not None


# ============================================================================
# core.audit_logger
# ============================================================================


class TestAuditLogger:
    def test_sanitizes_nested_list_values(self):
        from core.audit_logger import IntegrationAuditLog

        log = IntegrationAuditLog(
            connector_id="slack", method="send",
            params={"channel": "c1", "nested": [{"password": "hunter2"}, "plain", 42]},
        )
        d = log.to_dict()
        assert d["params"]["nested"][0]["password"] == "***REDACTED***"
        assert d["params"]["nested"][1] == "plain"
        assert d["params"]["nested"][2] == 42
        assert "Z" in d["timestamp"]
        assert d["epoch"] is not None

    def test_log_integration_call_and_error(self, caplog):
        from core.audit_logger import log_integration_call, log_integration_error

        with caplog.at_level(logging.INFO):
            entry = log_integration_call("gmail", "get_emails", {"q": "x"}, {"count": 1})
        assert entry.error is None
        assert entry.params == {"q": "x"}
        assert any("gmail.get_emails" in r.getMessage() for r in caplog.records)

        with caplog.at_level(logging.ERROR):
            err = log_integration_error("gmail", "get_emails", ValueError("boom"),
                                        {"q": "x"})
        assert err.error == "boom"

    def test_attempt_complete_roundtrip(self):
        from core.audit_logger import log_integration_attempt, log_integration_complete

        ctx = log_integration_attempt("slack", "send_message", {"channel": "c"})
        assert ctx["start_time"] > 0
        duration = log_integration_complete(ctx, {"ok": True})
        assert duration >= 0
        duration2 = log_integration_complete(ctx, error=ValueError("nope"))
        assert duration2 >= 0

    def test_timestamp_override(self):
        from core.audit_logger import IntegrationAuditLog

        log = IntegrationAuditLog("c", "m", {}, timestamp=1_000_000.0)
        assert log.timestamp == 1_000_000.0
        assert log.to_dict()["timestamp"].startswith("1970-01-12")


# ============================================================================
# core.capability_resolver
# ============================================================================


class TestCapabilityResolver:
    def test_normalize_string_and_dedupe(self):
        from core.capability_resolver import _normalize_capabilities, UNRESTRICTED

        assert _normalize_capabilities("browser") == ("browser",)
        assert _normalize_capabilities(None) == UNRESTRICTED
        assert _normalize_capabilities([]) == UNRESTRICTED
        assert _normalize_capabilities(["*"]) == UNRESTRICTED
        assert _normalize_capabilities(["browser", "browser", "memory_search"]) == (
            "browser", "memory_search")
        assert _normalize_capabilities(42) == UNRESTRICTED  # not iterable

    def test_tier_floor_fallback(self):
        from core.capability_resolver import _tier_floor
        from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS

        assert _tier_floor("supervised") == TIER_FLOOR_TOOL_WHITELISTS["supervised"]
        assert _tier_floor(None) == TIER_FLOOR_TOOL_WHITELISTS["student"]
        assert _tier_floor("bogus-tier") == TIER_FLOOR_TOOL_WHITELISTS["student"]

    def test_resolve_allowed_tools_matrix(self):
        from types import SimpleNamespace
        from core.capability_resolver import resolve_allowed_tools, UNRESTRICTED
        from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS

        # Unrestricted agent at a bounded tier -> floor.
        agent = SimpleNamespace(capabilities=None, status="intern")
        assert resolve_allowed_tools(agent) == TIER_FLOOR_TOOL_WHITELISTS["intern"]
        # Explicit tier beats status.
        assert resolve_allowed_tools(agent, tier="supervised") == (
            TIER_FLOOR_TOOL_WHITELISTS["supervised"])
        # Autonomous floor is unrestricted.
        auto = SimpleNamespace(capabilities=None, status="autonomous")
        assert resolve_allowed_tools(auto) == UNRESTRICTED
        # Declared scopes at autonomous -> verbatim.
        scoped = SimpleNamespace(capabilities=["browser", "memory_search"])
        assert resolve_allowed_tools(scoped, tier="autonomous") == ("browser", "memory_search")
        # Intersection narrows.
        intern = SimpleNamespace(capabilities=["browser", "shell", "nope"])
        resolved = resolve_allowed_tools(intern, tier="student")
        assert resolved == tuple(
            c for c in ("browser", "shell", "nope") if c in TIER_FLOOR_TOOL_WHITELISTS["student"])
        # Status fallback to student.
        assert resolve_allowed_tools(SimpleNamespace(capabilities=None)) == (
            TIER_FLOOR_TOOL_WHITELISTS["student"])

    def test_is_tool_allowed_dotted_registry_actions(self):
        from core.capability_resolver import is_tool_allowed

        allowed = ("browser",)
        assert is_tool_allowed(("*",), "anything") is True
        assert is_tool_allowed(allowed, "browser") is True
        assert is_tool_allowed(allowed, "not_there") is False
        assert is_tool_allowed(allowed, 123) is False
        # Registered dotted action -> allowed (application-level action).
        from core.action_registry import action_registry

        actions = action_registry.list_actions()
        if actions:
            assert is_tool_allowed(allowed, actions[0]) is True
        # Unregistered dotted name -> denied.
        assert is_tool_allowed(allowed, "no.such.action.xyz") is False
        # Empty allowed set denies everything.
        assert is_tool_allowed((), "browser") is False

    def test_is_tool_allowed_registry_error_denies(self):
        """A failing action-registry lookup denies the dotted name."""
        from core.capability_resolver import is_tool_allowed

        with patch("core.action_registry.action_registry.get_action",
                   side_effect=RuntimeError("registry down")):
            assert is_tool_allowed(("browser",), "documents.search") is False

    def test_get_agent_for_context(self, db_session):
        from core.capability_resolver import get_agent_for_context
        from core.models import AgentRegistry

        assert get_agent_for_context(None) is None
        assert get_agent_for_context({}) is None
        assert get_agent_for_context({"agent_id": ""}) is None
        db_session.add(AgentRegistry(
            id="ctx-1", name="ctx", category="Ops", module_path="m",
            class_name="c", status="student",
        ))
        db_session.commit()

        with patch("core.database.get_db_session") as m:
            cm = MagicMock()
            cm.__enter__.return_value = db_session
            cm.__exit__.return_value = False
            m.return_value = cm
            agent = get_agent_for_context({"agent_id": "ctx-1"})
            assert agent is not None and agent.id == "ctx-1"

    def test_get_agent_for_context_db_error(self, caplog):
        from core.capability_resolver import get_agent_for_context

        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            assert get_agent_for_context({"agent_id": "x"}) is None


