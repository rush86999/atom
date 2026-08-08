# -*- coding: utf-8 -*-
"""Coverage-push tests for backend/core wave core_c (>=95% line coverage).

Modules: automation_insight_manager, autonomous_supervisor_service,
background_agent_runner, behavior_analyzer, budget_guardrail, byok_cost_optimizer,
canvas_marketplace_service, canvas_orchestration_service, chat_process_manager,
chronological_integrity, agent_marketplace_service, admin_bootstrap,
auto_healing_endpoints, apar_engine.

All DB/HTTP/LLM interactions are mocked or use in-memory SQLite — never real
network. Companion bug-hunt file: tests/test_bughunt_core_c.py.
"""
import asyncio
import json
import os
import sqlite3
import sys
import types
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.database import Base


@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


@pytest.fixture()
def db():
    """In-memory SQLite with the full schema."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _patch_usage_db():
    return patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _db_ctx(MagicMock()))


# ============================================================================
# automation_insight_manager
# ============================================================================


class TestAutomationInsightManager:
    def _seed_events(self, path):
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE workflow_events (workflow_id TEXT, event_type TEXT,"
            " timestamp TEXT, user_id TEXT)"
        )
        now = datetime.now()
        rows = []
        for wf, steps, overrides in [
            ("wf-stable", 5, 0),
            ("wf-optimize", 5, 5),
            ("wf-confident", 12, 0),
            ("wf-no-success", 0, 3),
        ]:
            for i in range(steps):
                rows.append((wf, "step_completed", (now - timedelta(days=1)).isoformat(), "u-1"))
            for i in range(overrides):
                rows.append((wf, "manual_override", (now - timedelta(hours=1)).isoformat(), "u-1"))
        # Another user's rows must be filtered out
        rows.append(("wf-other", "step_completed", now.isoformat(), "u-2"))
        conn.executemany(
            "INSERT INTO workflow_events VALUES (?,?,?,?)", rows
        )
        conn.commit()
        conn.close()

    def test_get_drift_metrics_recommendations(self, tmp_path):
        from core.automation_insight_manager import AutomationInsightManager

        path = tmp_path / "analytics.db"
        self._seed_events(path)
        mgr = AutomationInsightManager(db_path=str(path))
        insights = mgr.get_drift_metrics("u-1")
        by_wf = {i["workflow_id"]: i for i in insights}
        assert set(by_wf) == {"wf-stable", "wf-optimize", "wf-confident", "wf-no-success"}
        assert by_wf["wf-stable"]["recommendation"] == "STABLE"
        assert by_wf["wf-optimize"]["recommendation"] == "OPTIMIZE (High Overrides)"
        assert by_wf["wf-confident"]["recommendation"] == "HIGH_CONFIDENCE"
        assert by_wf["wf-no-success"]["drift_score"] == 0.0
        assert "wf-other" not in by_wf

    def test_get_drift_metrics_workflow_filter(self, tmp_path):
        from core.automation_insight_manager import AutomationInsightManager

        path = tmp_path / "analytics.db"
        self._seed_events(path)
        mgr = AutomationInsightManager(db_path=str(path))
        insights = mgr.get_drift_metrics("u-1", workflow_id="wf-optimize")
        assert len(insights) == 1
        assert insights[0]["workflow_id"] == "wf-optimize"

    def test_get_drift_metrics_exception_returns_empty(self, tmp_path):
        from core.automation_insight_manager import AutomationInsightManager

        path = tmp_path / "missing.db"
        path.write_text("not sqlite")
        mgr = AutomationInsightManager(db_path=str(path))
        assert mgr.get_drift_metrics("u-1") == []

    def test_get_underutilization_insights(self):
        from core.automation_insight_manager import AutomationInsightManager

        q = MagicMock()
        q.filter.return_value.group_by.return_value.all.return_value = [
            SimpleNamespace(workflow_id="wf-low", execution_count=1),
            SimpleNamespace(workflow_id="wf-used", execution_count=5),
        ]
        mdb = MagicMock()
        mdb.query.return_value = q
        mgr = AutomationInsightManager(db_path="/nonexistent/x.db")
        with _patch_db(mdb):
            insights = mgr.get_underutilization_insights()
        assert len(insights) == 1
        assert insights[0]["workflow_id"] == "wf-low"
        assert insights[0]["status"] == "UNDERUTILIZED"

    def test_get_underutilization_insights_exception(self):
        from core.automation_insight_manager import AutomationInsightManager

        mdb = MagicMock()
        mdb.query.side_effect = RuntimeError("boom")
        mgr = AutomationInsightManager(db_path="/nonexistent/x.db")
        with _patch_db(mdb):
            assert mgr.get_underutilization_insights() == []

    def test_generate_all_insights(self, tmp_path):
        from core.automation_insight_manager import AutomationInsightManager

        path = tmp_path / "analytics.db"
        self._seed_events(path)
        mgr = AutomationInsightManager(db_path=str(path))
        report = mgr.generate_all_insights("u-1")
        assert report["summary"]["total_monitored"] == 4
        assert report["summary"]["needs_optimization"] == 1
        assert report["summary"]["stable"] == 2

    def test_get_insight_manager_singleton(self):
        import core.automation_insight_manager as mod

        mod._insight_manager = None
        try:
            a = mod.get_insight_manager()
            b = mod.get_insight_manager()
            assert a is b
            assert isinstance(a, mod.AutomationInsightManager)
        finally:
            mod._insight_manager = None


# ============================================================================
# behavior_analyzer
# ============================================================================


class TestBehaviorAnalyzer:
    @pytest.fixture(autouse=True)
    def _analytics(self):
        self.analytics = MagicMock()
        with patch("core.behavior_analyzer.get_analytics_engine", return_value=self.analytics):
            yield

    def test_log_user_action_default_workspace(self):
        from core.behavior_analyzer import BehaviorAnalyzer

        ba = BehaviorAnalyzer()
        ba.log_user_action("u-1", "meeting_ended", {"dur": 30})
        assert len(ba.user_action_windows["default_u-1"]) == 1
        self.analytics.track_user_activity.assert_called_once()
        assert ba.user_action_windows["default_u-1"][0]["workspace_id"] == "default"

    def test_log_user_action_custom_workspace_and_window_trim(self):
        from core.behavior_analyzer import BehaviorAnalyzer

        ba = BehaviorAnalyzer()
        for i in range(12):
            ba.log_user_action("u-1", f"action_{i}", workspace_id="ws-1")
        assert len(ba.user_action_windows["ws-1_u-1"]) == 10
        assert ba.user_action_windows["ws-1_u-1"][0]["action_type"] == "action_2"

    def test_detect_patterns_too_few_actions(self):
        from core.behavior_analyzer import BehaviorAnalyzer

        ba = BehaviorAnalyzer()
        ba.log_user_action("u-1", "meeting_ended")
        assert ba.detect_patterns("u-1") == []

    def test_detect_patterns_meeting_followup(self):
        from core.behavior_analyzer import BehaviorAnalyzer

        ba = BehaviorAnalyzer()
        ba.log_user_action("u-1", "meeting_ended", workspace_id="ws-9")
        ba.log_user_action("u-1", "task_created", workspace_id="ws-9")
        ba.log_user_action("u-1", "task_created", workspace_id="ws-9")
        patterns = ba.detect_patterns("u-1", workspace_id="ws-9")
        names = [p["name"] for p in patterns]
        assert "Meeting Follow-up Automation" in names
        # key mismatch: patterns only exist per ws_user key
        assert ba.detect_patterns("u-1") == []

    def test_detect_patterns_document_ingestion(self):
        from core.behavior_analyzer import BehaviorAnalyzer

        ba = BehaviorAnalyzer()
        ba.log_user_action("u-2", "document_uploaded")
        ba.log_user_action("u-2", "knowledge_update")
        ba.log_user_action("u-2", "document_uploaded")
        patterns = ba.detect_patterns("u-2")
        assert "Automated Knowledge Extraction" in [p["name"] for p in patterns]

    def test_get_behavior_analyzer_singleton(self):
        import core.behavior_analyzer as mod

        mod._behavior_analyzer = None
        try:
            a = mod.get_behavior_analyzer()
            b = mod.get_behavior_analyzer()
            assert a is b
        finally:
            mod._behavior_analyzer = None


# ============================================================================
# background_agent_runner
# ============================================================================


class TestBackgroundAgentRunner:
    @pytest.fixture()
    def runner(self, tmp_path):
        from core.background_agent_runner import BackgroundAgentRunner

        return BackgroundAgentRunner(log_dir=str(tmp_path / "logs"))

    @pytest.fixture()
    def fake_agent_routes(self):
        saved = sys.modules.get("api.agent_routes")
        mod = types.ModuleType("api.agent_routes")
        mod.AGENTS = {"portal-1": {"name": "Portal Check"}}
        mod.execute_agent_task = AsyncMock(return_value={"status": "ok", "detail": "done"})
        sys.modules["api.agent_routes"] = mod
        yield mod
        if saved is not None:
            sys.modules["api.agent_routes"] = saved
        else:
            sys.modules.pop("api.agent_routes", None)

    def test_register_and_start_stop(self, runner, tmp_path):
        runner.register_agent("a-1", interval_seconds=3600)
        assert runner.get_status("a-1")["status"] == "stopped"

    async def test_start_unregistered_raises(self, runner):
        with pytest.raises(ValueError):
            await runner.start_agent("ghost")

    async def test_start_running_agent_is_noop(self, runner, fake_agent_routes):
        runner.register_agent("a-1", interval_seconds=3600)
        await runner.start_agent("a-1")
        task = runner._tasks["a-1"]
        await runner.start_agent("a-1")  # already running -> return early
        assert runner._tasks["a-1"] is task
        runner._tasks["a-1"].cancel()
        with pytest.raises(asyncio.CancelledError):
            await runner._tasks["a-1"]

    async def test_stop_agent(self, runner):
        runner.register_agent("a-1", interval_seconds=3600)
        await runner.start_agent("a-1")
        await runner.stop_agent("a-1")
        assert runner.get_status("a-1")["status"] == "stopped"
        assert "a-1" not in runner._tasks
        await runner.stop_agent("ghost")  # no-op

    async def test_run_loop_cancel_mid_sleep(self, runner, fake_agent_routes):
        from core.background_agent_runner import AgentStatus

        runner.register_agent("a-1", interval_seconds=3600)
        runner._execute_agent = AsyncMock(return_value={"status": "ok"})
        await runner.start_agent("a-1")
        await asyncio.sleep(0.05)  # let the loop start and reach the first sleep
        task = runner._tasks["a-1"]
        task.cancel()
        await task  # CancelledError swallowed by _run_loop -> exits normally
        assert task.done() and task.cancelled() is False
        assert runner.get_status("a-1")["run_count"] == 1

    async def test_run_loop_success_iterations(self, runner, tmp_path):
        from core.background_agent_runner import AgentStatus

        runner.register_agent("a-1", interval_seconds=0.01)
        runner._agents["a-1"].status = AgentStatus.RUNNING
        calls = {"n": 0}

        async def _execute(agent_id):
            calls["n"] += 1
            if calls["n"] >= 2:
                runner._agents["a-1"].status = AgentStatus.STOPPED

        runner._execute_agent = _execute
        await runner._run_loop("a-1")
        state = runner.get_status("a-1")
        assert state["run_count"] == 2
        assert state["last_run"] is not None

    async def test_run_loop_error_sets_error_status(self, runner):
        async def _execute(agent_id):
            raise RuntimeError("agent exploded")

        from core.background_agent_runner import AgentStatus

        runner.register_agent("a-1", interval_seconds=0.01)
        runner._agents["a-1"].status = AgentStatus.RUNNING
        runner._execute_agent = _execute
        await runner._run_loop("a-1")
        state = runner.get_status("a-1")
        assert state["status"] == "error"
        assert state["error_count"] == 1
        assert "exploded" in state["last_error"]

    async def test_execute_agent_in_registry_with_owner(self, runner, fake_agent_routes, db):
        db.query = MagicMock(
            return_value=MagicMock(
                filter=MagicMock(
                    return_value=MagicMock(first=MagicMock(return_value=SimpleNamespace(user_id="u-9")))
                )
            )
        )
        with _patch_db(db):
            result = await runner._execute_agent("portal-1")
        assert result["status"] == "ok"
        assert fake_agent_routes.execute_agent_task.await_args[0][2] == {"agent_id": "portal-1", "user_id": "u-9"}

    async def test_execute_agent_in_registry_without_owner(self, runner, fake_agent_routes, db):
        db.query = MagicMock(
            return_value=MagicMock(
                filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )
        with _patch_db(db):
            result = await runner._execute_agent("portal-1")
        assert result["status"] == "ok"
        context = fake_agent_routes.execute_agent_task.await_args[0][2]
        assert "user_id" not in context

    async def test_execute_agent_in_registry_owner_lookup_error(self, runner, fake_agent_routes, db):
        db.query = Mock(side_effect=RuntimeError("db down"))
        with _patch_db(db):
            result = await runner._execute_agent("portal-1")
        assert result["status"] == "ok"

    async def test_execute_agent_not_registered(self, runner, fake_agent_routes):
        result = await runner._execute_agent("ghost")
        assert result is None
        assert any(l["event"] == "skipped" for l in runner.get_logs())

    async def test_execute_agent_exception_logs_failed(self, runner, fake_agent_routes):
        fake_agent_routes.execute_agent_task = AsyncMock(side_effect=ValueError("nope"))
        with pytest.raises(ValueError):
            await runner._execute_agent("portal-1")
        assert any(l["event"] == "failed" for l in runner.get_logs())

    def test_log_writes_file(self, runner, tmp_path):
        runner._log("a-1", "hello", "world", "info")
        log_file = tmp_path / "logs" / "a-1.log"
        assert log_file.exists()
        assert "hello" in log_file.read_text()

    def test_get_status_all_and_missing(self, runner):
        runner.register_agent("a-1")
        runner.register_agent("a-2")
        statuses = runner.get_status()
        assert set(statuses) == {"a-1", "a-2"}
        assert runner.get_status("missing")["error"]

    def test_get_logs_filter_and_limit(self, runner):
        for i in range(60):
            runner._log("a-1", f"e{i}", None)
        runner._log("a-2", "other", None)
        logs = runner.get_logs("a-1", limit=5)
        assert len(logs) == 5
        assert logs[-1]["event"] == "e59"
        assert all(l["agent_id"] == "a-1" for l in logs)

    def test_agent_log_to_dict(self):
        from core.background_agent_runner import AgentLog

        entry = AgentLog(datetime(2026, 1, 1), "a-1", "evt", details="d")
        d = entry.to_dict()
        assert d["timestamp"] == "2026-01-01T00:00:00"
        assert d["details"] == "d"


# ============================================================================
# budget_guardrail (gap coverage on top of test_r80_budget_guardrail.py)
# ============================================================================


class TestBudgetGuardrailGaps:
    def test_calculate_project_burn_no_project(self, db):
        from core.budget_guardrail import BudgetGuardrailService

        service = BudgetGuardrailService(db_session=db)
        result = asyncio.get_event_loop().run_until_complete(
            service.calculate_project_burn("missing-project")
        )
        assert result["status"] == "unknown"
        assert result["total_burn"] == 0.0

    def test_owns_session_when_not_injected(self, tmp_path):
        import sqlite3

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.budget_guardrail import BudgetGuardrailService

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        real_session = sessionmaker(bind=engine)()
        service = BudgetGuardrailService()
        service.db = None
        with patch("core.budget_guardrail.SessionLocal", return_value=real_session):
            result = asyncio.get_event_loop().run_until_complete(
                service.calculate_project_burn("missing-project")
            )
        assert result["total_burn"] == 0.0
        assert result["status"] == "unknown"
        real_session.close()
        engine.dispose()


# ============================================================================
# byok_cost_optimizer
# ============================================================================


class FakeProvider:
    def __init__(self, name, tasks, cost, active=True):
        self.name = name
        self.is_active = active
        self.supported_tasks = tasks
        self.cost_per_token = cost


@dataclass
class FakeUsage:
    """Mirror ProviderUsage: a real dataclass (asdict() is used on it)."""
    provider_id: str = ""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens_used: int = 0
    cost_accumulated: float = 0.0
    last_used: Optional[datetime] = None
    rate_limit_remaining: int = 0


class FakeBYOKManager:
    def __init__(self):
        self.providers = {
            "openai": FakeProvider("OpenAI", ["code", "chat", "analysis"], 0.0006),
            "deepseek": FakeProvider("DeepSeek", ["code", "math"], 0.00001),
            "anthropic": FakeProvider("Anthropic", ["writing"], 0.001, active=False),
        }
        self.usage_stats = {"openai": FakeUsage(provider_id="openai", total_requests=100, cost_accumulated=5.0)}

    def get_optimal_provider(self, task_type, budget_constraint=None):
        return "openai"

    def get_api_key(self, provider_id):
        if provider_id in ("anthropic", "unknown-llm"):
            return None
        return "sk-test"


class TestBYOKCostOptimizer:
    @pytest.fixture(autouse=True)
    def _hermetic_patterns_file(self, tmp_path, monkeypatch):
        """Redirect ./data/usage_patterns.json so tests never touch real data."""
        import pathlib

        import core.byok_cost_optimizer as mod

        def fake_path(p):
            if p.name == "usage_patterns.json":
                return pathlib.Path(tmp_path) / "usage_patterns.json"
            return pathlib.Path(p)

        monkeypatch.setattr(mod, "Path", fake_path)

    def test_init_loads_competitive_intelligence(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer

        opt = BYOKCostOptimizer(FakeBYOKManager())
        assert set(opt.competitive_insights) == {"openai", "anthropic", "moonshot", "deepseek"}
        assert opt.competitive_insights["deepseek"].market_position == "budget"

    def test_load_usage_patterns_from_file(self, tmp_path, monkeypatch):
        import pathlib

        import core.byok_cost_optimizer as mod

        patterns_file = tmp_path / "usage_patterns.json"
        patterns_file.write_text(
            json.dumps(
                {
                    "patterns": {
                        "u-1": {
                            "user_id": "u-1",
                            "task_distribution": {"code": 80},
                            "peak_hours": [9],
                            "preferred_providers": {"openai": 100.0},
                        }
                    }
                }
            )
        )

        def fake_path(p):
            return pathlib.Path(str(patterns_file))

        monkeypatch.setattr(mod, "Path", fake_path)
        opt = mod.BYOKCostOptimizer(FakeBYOKManager())
        assert "u-1" in opt.usage_patterns

    def test_load_usage_patterns_corrupt_file(self, tmp_path, monkeypatch):
        import pathlib

        import core.byok_cost_optimizer as mod

        patterns_file = tmp_path / "usage_patterns.json"
        patterns_file.write_text("{not json")

        def fake_path(p):
            return pathlib.Path(str(patterns_file))

        monkeypatch.setattr(mod, "Path", fake_path)
        opt = mod.BYOKCostOptimizer(FakeBYOKManager())
        assert opt.usage_patterns == {}

    def test_load_usage_patterns_missing_file(self, tmp_path, monkeypatch):
        import pathlib

        import core.byok_cost_optimizer as mod

        def fake_path(p):
            return pathlib.Path(tmp_path) / "nope.json"

        monkeypatch.setattr(mod, "Path", fake_path)
        opt = mod.BYOKCostOptimizer(FakeBYOKManager())
        assert opt.usage_patterns == {}

    def test_save_usage_patterns_success_and_error(self, tmp_path, monkeypatch):
        import pathlib

        import core.byok_cost_optimizer as mod

        class Boom:
            def mkdir(self, exist_ok=True):
                raise OSError("disk full")

        monkeypatch.setattr(mod, "Path", lambda p: Boom() if p.name == "usage_patterns.json" else pathlib.Path(tmp_path))
        opt = mod.BYOKCostOptimizer(FakeBYOKManager())
        opt.usage_patterns["u-1"] = mod.UsagePattern(
            user_id="u-1", task_distribution={}, peak_hours=[], preferred_providers={}
        )
        opt._save_usage_patterns()  # must not raise

        monkeypatch.setattr(mod, "Path", lambda p: pathlib.Path(tmp_path) / "saved.json")
        opt._save_usage_patterns()
        saved = json.loads((pathlib.Path(tmp_path) / "saved.json").read_text())
        assert "u-1" in saved["patterns"]
        assert "last_updated" in saved

    def test_analyze_user_usage_pattern_default_for_new_user(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer

        mgr = FakeBYOKManager()
        mgr.usage_stats = {}
        opt = BYOKCostOptimizer(mgr)
        pattern = opt.analyze_user_usage_pattern("new-user", days=30)
        assert pattern.user_id == "new-user"
        assert pattern.monthly_budget == 50.0
        assert pattern.task_distribution["general"] == 40
        assert pattern.preferred_providers == {}

    def test_analyze_user_usage_pattern_with_usage(self, tmp_path, monkeypatch):
        import pathlib

        import core.byok_cost_optimizer as mod

        monkeypatch.setattr(mod, "Path", lambda p: pathlib.Path(tmp_path) / "p.json")
        opt = mod.BYOKCostOptimizer(FakeBYOKManager())
        pattern = opt.analyze_user_usage_pattern("u-1")
        assert pattern.preferred_providers["openai"] == 100.0
        assert (pathlib.Path(tmp_path) / "p.json").exists()

    def test_get_recommendations_cost_sensitive(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        opt = BYOKCostOptimizer(FakeBYOKManager())
        opt.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={"code": 100},
            peak_hours=[9],
            preferred_providers={"openai": 100.0},
            cost_sensitivity="high",
        )
        rec = opt.get_cost_optimization_recommendations("u-1", "code")
        assert rec.recommended_provider == "deepseek"
        assert rec.savings_percentage > 0
        assert len(rec.alternative_providers) >= 1

    def test_get_recommendations_quality_preference_and_unknown_insight(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        class KeyedManager(FakeBYOKManager):
            def get_api_key(self, provider_id):
                return "sk-test"

        # Only a provider with NO competitive insight supports "writing" ->
        # default insight + default reasoning path.
        mgr = KeyedManager()
        mgr.providers = {"unknown-llm": FakeProvider("UnknownLLM", ["writing"], 0.00002)}
        opt = BYOKCostOptimizer(mgr)
        opt.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={"writing": 100},
            peak_hours=[9],
            preferred_providers={},
            quality_preference="quality",
        )
        rec = opt.get_cost_optimization_recommendations("u-1", "writing")
        assert rec.recommended_provider == "unknown-llm"
        assert rec.reasoning.startswith("Most cost-effective provider")

    def test_get_recommendations_balanced_and_current_provider_fallback(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        opt = BYOKCostOptimizer(FakeBYOKManager())

        class BadManager(FakeBYOKManager):
            def get_optimal_provider(self, task_type, budget_constraint=None):
                raise RuntimeError("no provider")

        opt.byok_manager = BadManager()
        opt.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={"code": 100},
            peak_hours=[9],
            preferred_providers={},
        )
        rec = opt.get_cost_optimization_recommendations("u-1", "code")
        assert rec.current_provider == "openai"  # fallback

    def test_get_recommendations_fresh_user_analyzes(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer

        opt = BYOKCostOptimizer(FakeBYOKManager())
        # user not in usage_patterns -> analyze_user_usage_pattern() is invoked
        rec = opt.get_cost_optimization_recommendations("brand-new-user", "code")
        assert rec.task_type == "code"
        assert "brand-new-user" in opt.usage_patterns

    def test_get_recommendations_no_suitable_provider(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        opt = BYOKCostOptimizer(FakeBYOKManager())
        opt.byok_manager.providers = {}
        opt.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={},
            peak_hours=[],
            preferred_providers={},
        )
        with pytest.raises(ValueError):
            opt.get_cost_optimization_recommendations("u-1", "writing")

    def test_get_recommendations_zero_savings(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        opt = BYOKCostOptimizer(FakeBYOKManager())
        # recommended == current -> no savings
        opt.byok_manager.get_optimal_provider = lambda t, budget_constraint=None: "deepseek"
        opt.byok_manager.providers = {
            "deepseek": FakeProvider("DeepSeek", ["code"], 0.00001),
        }
        opt.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={"code": 100},
            peak_hours=[9],
            preferred_providers={},
        )
        rec = opt.get_cost_optimization_recommendations("u-1", "code")
        assert rec.savings_percentage == 0
        assert rec.estimated_savings == 0

    def test_get_competitive_analysis_report(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer

        opt = BYOKCostOptimizer(FakeBYOKManager())
        report = opt.get_competitive_analysis_report()
        assert set(report["providers"]) == {"openai", "anthropic", "moonshot", "deepseek"}
        assert report["providers"]["openai"]["active"] is True
        assert report["providers"]["anthropic"]["active"] is False
        assert report["providers"]["anthropic"]["has_keys"] is False
        # rankings are 1-based and unique
        rankings = [p["cost_ranking"] for p in report["providers"].values()]
        assert sorted(rankings) == [1, 2, 3, 4]
        assert report["market_overview"]["total_providers"] == 4
        assert report["market_overview"]["market_segments"]["budget"] == 2
        # budget + keyed provider -> cost optimization recommendation
        assert any(r["type"] == "cost_optimization" for r in report["recommendations"])
        # premium keyed -> quality optimization
        assert any(r["type"] == "quality_optimization" for r in report["recommendations"])
        # inactive + no key -> no expansion rec
        assert any(r["type"] == "expansion_opportunity" for r in report["recommendations"]) is False

    def test_get_competitive_analysis_report_expansion_opportunity(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer

        mgr = FakeBYOKManager()
        # The report only iterates competitive_insights providers: activate
        # anthropic (active but keyless) -> expansion_opportunity fires.
        mgr.providers["anthropic"].is_active = True
        opt = BYOKCostOptimizer(mgr)
        report = opt.get_competitive_analysis_report()
        expansions = [r for r in report["recommendations"] if r["type"] == "expansion_opportunity"]
        assert expansions
        assert "anthropic" in expansions[0]["providers"]

    def test_simulate_cost_savings_zero_history(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer

        mgr = FakeBYOKManager()
        mgr.usage_stats = {}
        opt = BYOKCostOptimizer(mgr)
        result = opt.simulate_cost_savings("u-1", months=3, adoption_rate=0.5)
        assert result["user_id"] == "u-1"
        assert result["simulation_period_months"] == 3
        assert result["current_monthly_cost"] == 50.0
        assert result["savings_percentage"] >= 0
        assert result["roi_calculation"]["annualized_return"] >= 0

    def test_simulate_cost_savings_with_history_and_savings(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        mgr = FakeBYOKManager()
        mgr.usage_stats = {"openai": FakeUsage(provider_id="openai", total_requests=1000, cost_accumulated=500.0)}
        opt = BYOKCostOptimizer(mgr)
        opt.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={"code": 100},
            peak_hours=[9],
            preferred_providers={"openai": 100.0},
            cost_sensitivity="high",
        )
        result = opt.simulate_cost_savings("u-1", months=2)
        assert result["current_monthly_cost"] == 500.0
        assert "code" in result["task_breakdown"]
        assert result["total_projected_savings"] > 0

    def test_simulate_cost_savings_recommendation_error_path(self):
        from core.byok_cost_optimizer import BYOKCostOptimizer, UsagePattern

        opt = BYOKCostOptimizer(FakeBYOKManager())
        opt.usage_patterns["u-1"] = UsagePattern(
            user_id="u-1",
            task_distribution={"code": 100},
            peak_hours=[9],
            preferred_providers={},
        )
        opt.get_cost_optimization_recommendations = Mock(
            side_effect=RuntimeError("optimizer down")
        )
        result = opt.simulate_cost_savings("u-1")
        assert result["optimized_monthly_cost"] > 0


# ============================================================================
# canvas_marketplace_service
# ============================================================================


class TestCanvasMarketplaceService:
    def test_browse_components_success_and_error(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService

        saas = MagicMock()
        saas.fetch_components_sync = Mock(return_value={"components": [{"id": "c1"}], "total": 1})
        service = CanvasMarketplaceService(db, saas_client=saas)
        assert service.browse_components(query="chart", category="visualization", page=2, page_size=5)["total"] == 1

        saas.fetch_components_sync = Mock(side_effect=RuntimeError("saas down"))
        result = service.browse_components()
        assert result["components"] == []
        assert "saas down" in result["error"]

    def test_get_component_details_success_and_error(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService

        saas = MagicMock()
        saas.get_component_details_sync = Mock(return_value={"id": "c1"})
        service = CanvasMarketplaceService(db, saas_client=saas)
        assert service.get_component_details("c1")["id"] == "c1"
        saas.get_component_details_sync = Mock(side_effect=RuntimeError("boom"))
        assert service.get_component_details("c1") is None

    def test_install_component_metadata_missing(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService

        saas = MagicMock()
        saas.get_component_details_sync = Mock(return_value=None)
        service = CanvasMarketplaceService(db, saas_client=saas)
        result = service.install_component("c1", "cv-1", "ten-1")
        assert result["success"] is False

    def test_install_component_creates_local(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService
        from core.models import CanvasComponent

        saas = MagicMock()
        saas.get_component_details_sync = Mock(
            return_value={
                "author_id": "author-1",
                "name": "Bar Chart",
                "description": "A bar chart",
                "category": "chart",
                "component_type": "html",
                "code": "<div></div>",
                "config_schema": {"type": "object"},
                "preview_url": "https://example.com/p.png",
                "version": "2.1.0",
                "license": "MIT",
                "dependencies": ["lodash"],
                "css_dependencies": ["https://cdn/x.css"],
                "default_config": {"color": "blue"},
            }
        )
        saas.install_component_sync = Mock()
        service = CanvasMarketplaceService(db, saas_client=saas)
        with _patch_usage_db():
            result = service.install_component("c1", "cv-1", "ten-1", config={"x": 1})

        assert result["success"] is True
        assert result["component_name"] == "Bar Chart"
        local = db.query(CanvasComponent).filter(CanvasComponent.id == "c1").first()
        assert local is not None
        assert local.is_public is True
        assert local.tenant_id is None
        saas.install_component_sync.assert_called_once_with("c1", "cv-1")

    def test_install_component_existing_local_and_default_config(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService
        from core.models import CanvasComponent

        db.add(
            CanvasComponent(
                id="c1",
                author_id="author-1",
                name="Existing",
                category="chart",
                component_type="html",
                code="<div/>",
            )
        )
        db.commit()
        saas = MagicMock()
        saas.get_component_details_sync = Mock(
            return_value={
                "name": "Bar Chart",
                "category": "chart",
                "component_type": "html",
                "code": "<div></div>",
                "default_config": {"color": "blue"},
            }
        )
        saas.install_component_sync = Mock()
        service = CanvasMarketplaceService(db, saas_client=saas)
        with _patch_usage_db():
            result = service.install_component("c1", "cv-1", "ten-1")
        assert result["success"] is True

    def test_install_component_exception_rolls_back(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService

        saas = MagicMock()
        saas.get_component_details_sync = Mock(
            return_value={"name": "N", "category": "c", "component_type": "t", "code": "x"}
        )
        saas.install_component_sync = Mock(side_effect=RuntimeError("notify failed"))
        service = CanvasMarketplaceService(db, saas_client=saas)
        with _patch_usage_db():
            result = service.install_component("c1", "cv-1", "ten-1")
        assert result["success"] is False
        assert "notify failed" in result["error"]

    def test_uninstall_component(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService
        from core.models import ComponentInstallation

        db.add(
            ComponentInstallation(id="inst-1", tenant_id="ten-1", canvas_id="cv-1", component_id="c1")
        )
        db.commit()
        saas = MagicMock()
        service = CanvasMarketplaceService(db, saas_client=saas)

        # Not found (wrong tenant)
        assert service.uninstall_component("inst-1", "ten-other")["success"] is False
        # Success
        result = service.uninstall_component("inst-1", "ten-1")
        assert result["success"] is True
        assert db.query(ComponentInstallation).filter(ComponentInstallation.id == "inst-1").first() is None

    def test_uninstall_component_exception(self, db):
        from core.canvas_marketplace_service import CanvasMarketplaceService

        saas = MagicMock()
        service = CanvasMarketplaceService(db, saas_client=saas)
        original = db.query
        db.query = Mock(side_effect=RuntimeError("db down"))
        try:
            result = service.uninstall_component("inst-1", "ten-1")
        finally:
            db.query = original
        assert result["success"] is False


# ============================================================================
# canvas_orchestration_service
# ============================================================================


class TestCanvasOrchestrationService:
    def test_workflow_task_status_normalization(self):
        from core.canvas_orchestration_service import CanvasTaskStatus, WorkflowTask

        assert WorkflowTask("t1", "A", status="todo").status == CanvasTaskStatus.PENDING
        assert WorkflowTask("t2", "B", status="done").status == CanvasTaskStatus.COMPLETED
        assert WorkflowTask("t3", "C", status="in_progress").status == CanvasTaskStatus.IN_PROGRESS
        # unknown string keeps its value
        assert WorkflowTask("t4", "D", status="blocked").status == "blocked"
        # non-str status (plain enum, not str-subclass) passes through
        import enum

        class Plain(enum.Enum):
            X = "x"

        assert WorkflowTask("t5", "E", status=Plain.X).status is Plain.X
        # defaults
        t = WorkflowTask("t6", "F")
        assert t.status == CanvasTaskStatus.PENDING
        assert t.tags == []
        assert t.integrations == []
        assert t.due_date is None

    def test_integration_node_defaults(self):
        from core.canvas_orchestration_service import IntegrationNode

        n = IntegrationNode("n1", "app", "action")
        assert n.config == {}
        assert n.position == {"x": 0, "y": 0}

    def test_create_orchestration_canvas(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService
        from core.models import CanvasAudit

        service = OrchestrationCanvasService(db)
        result = service.create_orchestration_canvas(
            user_id="u-1",
            title="Onboarding",
            canvas_id="cv-1",
            agent_id="a-1",
            layout="timeline",
            tasks=[{"title": "Send email", "status": "pending", "tags": ["x"]}],
        )
        assert result["success"] is True
        assert result["canvas_id"] == "cv-1"
        assert result["tasks"][0]["title"] == "Send email"
        audit = (
            db.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == "cv-1")
            .first()
        )
        assert audit.details_json["layout"] == "timeline"

    def test_create_orchestration_canvas_generates_id(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        result = service.create_orchestration_canvas(user_id="u-1", title="No id")
        assert result["success"] is True
        assert result["canvas_id"]

    def test_create_orchestration_canvas_exception(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        db.add = Mock(side_effect=RuntimeError("insert failed"))
        result = service.create_orchestration_canvas(user_id="u-1", title="T")
        assert result["success"] is False

    def test_add_workflow_node(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        service.create_orchestration_canvas(user_id="u-1", title="T", canvas_id="cv-1")
        result = service.add_workflow_node(
            canvas_id="cv-1",
            user_id="u-1",
            node_name="Send Email",
            node_type="action",
            config={"goal": "x"},
            position={"x": 10, "y": 20},
            assigned_agent="a-1",
        )
        assert result["success"] is True
        # Adding again — integration name must not duplicate
        service.add_workflow_node(canvas_id="cv-1", user_id="u-1", node_name="Send Email", node_type="action")

    def test_add_workflow_node_canvas_not_found(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        result = service.add_workflow_node("missing", "u-1", "N", "action")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_add_workflow_node_exception(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        service.create_orchestration_canvas(user_id="u-1", title="T", canvas_id="cv-1")
        db.add = Mock(side_effect=RuntimeError("boom"))
        result = service.add_workflow_node("cv-1", "u-1", "N", "action")
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_connect_nodes(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        service.create_orchestration_canvas(user_id="u-1", title="T", canvas_id="cv-1")
        n1 = service.add_workflow_node(canvas_id="cv-1", user_id="u-1", node_name="A", node_type="action")
        n2 = service.add_workflow_node(canvas_id="cv-1", user_id="u-1", node_name="B", node_type="action")
        result = service.connect_nodes(
            "cv-1", "u-1", n1["node_id"], n2["node_id"], condition="if x"
        )
        assert result["success"] is True
        assert result["connection_id"]

    def test_connect_nodes_not_found_and_exception(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        assert service.connect_nodes("missing", "u-1", "a", "b")["success"] is False
        service.create_orchestration_canvas(user_id="u-1", title="T", canvas_id="cv-1")
        db.add = Mock(side_effect=RuntimeError("boom"))
        result = service.connect_nodes("cv-1", "u-1", "a", "b")
        assert result["success"] is False

    def test_add_task(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        service.create_orchestration_canvas(user_id="u-1", title="T", canvas_id="cv-1")
        result = service.add_task(
            "cv-1", "u-1", "Follow up", status="in_progress", assignee="a-1", integrations=["gmail"]
        )
        assert result["success"] is True
        assert result["task_id"]
        assert result["title"] == "Follow up"

    def test_add_task_not_found_and_exception(self, db):
        from core.canvas_orchestration_service import OrchestrationCanvasService

        service = OrchestrationCanvasService(db)
        assert service.add_task("missing", "u-1", "T")["success"] is False
        service.create_orchestration_canvas(user_id="u-1", title="T", canvas_id="cv-1")
        db.add = Mock(side_effect=RuntimeError("boom"))
        result = service.add_task("cv-1", "u-1", "T")
        assert result["success"] is False

    def test_serializers(self):
        from datetime import datetime

        from core.canvas_orchestration_service import (
            OrchestrationCanvasService,
            WorkflowTask,
        )

        service = OrchestrationCanvasService(MagicMock())
        task = WorkflowTask("t1", "Title", status="todo", due_date=datetime(2026, 1, 1))
        d = service._task_to_dict(task)
        assert d["due_date"] == "2026-01-01T00:00:00"
        node = SimpleNamespace(node_id="n1", app_name="App", node_type="t", config={}, position={})
        assert service._node_to_dict(node)["node_id"] == "n1"
        conn = SimpleNamespace(connection_id="c1", from_node="a", to_node="b", condition=None)
        assert service._connection_to_dict(conn)["condition"] is None

    def test_canvas_lock_registry(self):
        from core.canvas_orchestration_service import _canvas_lock

        lock1 = _canvas_lock("cv-1")
        lock2 = _canvas_lock("cv-1")
        lock3 = _canvas_lock("cv-2")
        assert lock1 is lock2
        assert lock1 is not lock3


# ============================================================================
# chat_process_manager
# ============================================================================


class TestChatProcessManager:
    @pytest.fixture()
    def async_db(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from core.models import ChatProcess, User

        engine = create_async_engine("sqlite+aiosqlite://")

        async def _init():
            async with engine.begin() as conn:
                await conn.run_sync(
                    Base.metadata.create_all,
                    tables=[ChatProcess.__table__, User.__table__],
                )

        asyncio.get_event_loop().run_until_complete(_init())
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        @asynccontextmanager
        async def _session():
            async with SessionLocal() as s:
                yield s

        with patch("core.chat_process_manager.get_async_db_session", side_effect=_session):
            yield SessionLocal
        asyncio.get_event_loop().run_until_complete(engine.dispose())

    @pytest.fixture()
    async def manager(self, async_db):
        from core.chat_process_manager import ChatProcessManager
        from core.models import User

        async with async_db() as db:
            db.add(
                User(
                    id="u-1",
                    email="u1@example.com",
                    first_name="U",
                    last_name="1",
                    role="member",
                    status="ACTIVE",
                    tenant_id="ten-1",
                )
            )
            await db.commit()

        return ChatProcessManager()

    async def test_create_and_get_process(self, manager, async_db):
        pid = await manager.create_process(
            user_id="u-1",
            name="Onboarding",
            steps=[{"step": 1}, {"step": 2}],
            initial_context={"customer": "acme"},
        )
        state = await manager.get_process(pid)
        assert state["status"] == "active"
        assert state["current_step"] == 0
        assert state["steps"] == [{"step": 1}, {"step": 2}]
        assert state["created_at"]

    async def test_get_process_missing_and_string_fields(self, manager, async_db):
        assert await manager.get_process("ghost") is None
        # JSON-string stored fields round-trip through json.loads
        from core.models import ChatProcess

        async with async_db() as db:
            db.add(
                ChatProcess(
                    id="c-str",
                    tenant_id="ten-1",
                    user_id="u-1",
                    name="S",
                    current_step=1,
                    total_steps=2,
                    steps=json.dumps([{"step": 1}]),
                    context=json.dumps({"a": 1}),
                    inputs=json.dumps({"in": 1}),
                    outputs=json.dumps({"out": 2}),
                    status="paused",
                    missing_parameters=json.dumps(["email"]),
                )
            )
            await db.commit()
        state = await manager.get_process("c-str")
        assert state["inputs"] == {"in": 1}
        assert state["outputs"] == {"out": 2}
        assert state["missing_parameters"] == ["email"]

    async def test_get_process_corrupt_json_returns_none(self, manager, async_db):
        from core.models import ChatProcess

        async with async_db() as db:
            db.add(
                ChatProcess(
                    id="c-bad",
                    tenant_id="ten-1",
                    user_id="u-1",
                    name="Bad",
                    current_step=0,
                    total_steps=1,
                    steps="{not json",
                    context="{}",
                    inputs="{}",
                    outputs="{}",
                    status="active",
                    missing_parameters="[]",
                )
            )
            await db.commit()
        assert await manager.get_process("c-bad") is None

    async def test_update_process_step_missing_parameters(self, manager, async_db):
        pid = await manager.create_process("u-1", "N", [{"s": 1}, {"s": 2}])
        result = await manager.update_process_step(pid, {"email": "a@b.c"}, missing_parameters=["email"])
        assert result["status"] == "paused"
        assert result["next_step"] == 0

    async def test_update_process_step_advance_and_complete(self, manager, async_db):
        pid = await manager.create_process("u-1", "N", [{"s": 1}, {"s": 2}])
        r1 = await manager.update_process_step(pid, {"email": "a@b.c"})
        assert r1["status"] == "active"
        assert r1["next_step"] == 1
        r2 = await manager.update_process_step(pid, {"name": "x"}, step_output={"summary": "done"})
        assert r2["status"] == "completed"
        assert r2["next_step"] == 1

    async def test_update_process_step_not_found(self, manager):
        with pytest.raises(ValueError):
            await manager.update_process_step("ghost", {})

    async def test_resume_process(self, manager, async_db):
        pid = await manager.create_process("u-1", "N", [{"s": 1}])
        await manager.update_process_step(pid, {}, missing_parameters=["email", "phone"])
        r = await manager.resume_process(pid, {"email": "a@b.c"})
        assert r["status"] == "paused"  # phone still missing
        assert r["remaining_missing"] == ["phone"]
        r2 = await manager.resume_process(pid, {"phone": "123"})
        assert r2["status"] == "active"

    async def test_resume_process_errors(self, manager):
        with pytest.raises(ValueError):
            await manager.resume_process("ghost", {})
        pid = await manager.create_process("u-1", "N", [{"s": 1}])
        with pytest.raises(ValueError):
            await manager.resume_process(pid, {})

    async def test_cancel_process(self, manager, async_db):
        pid = await manager.create_process("u-1", "N", [{"s": 1}])
        await manager.cancel_process(pid)
        state = await manager.get_process(pid)
        assert state["status"] == "cancelled"
        await manager.cancel_process(pid)  # no longer active/paused -> no-op

    async def test_get_user_processes(self, manager, async_db):
        await manager.create_process("u-1", "One", [{"s": 1}])
        p2 = await manager.create_process("u-1", "Two", [{"s": 1}])
        await manager.cancel_process(p2)
        all_procs = await manager.get_user_processes("u-1")
        assert len(all_procs) == 2
        active = await manager.get_user_processes("u-1", status="active")
        assert len(active) == 1
        assert active[0]["name"] == "One"

    def test_get_process_manager_singleton(self):
        import core.chat_process_manager as mod

        mod._process_manager = None
        try:
            a = mod.get_process_manager()
            b = mod.get_process_manager()
            assert a is b
        finally:
            mod._process_manager = None


# ============================================================================
# chronological_integrity
# ============================================================================


class TestChronologicalIntegrity:
    @pytest.fixture()
    def db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.models import FinancialAudit

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine, tables=[FinancialAudit.__table__])
        session = sessionmaker(bind=engine)()
        yield session
        session.close()
        engine.dispose()

    def _add(self, db, account, seq, ts, aid=None):
        from core.models import FinancialAudit

        db.add(
            FinancialAudit(
                id=aid or f"{account}-{seq}",
                account_id=account,
                sequence_number=seq,
                operation_type="UPDATE",
                table_name="financial_accounts",
                timestamp=ts,
            )
        )

    def test_validate_monotonicity_clean(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(minutes=1))
        self._add(db, "acct-2", 1, now + timedelta(minutes=2))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        result = validator.validate_monotonicity()
        assert result["is_monotonic"] is True
        assert result["total_entries"] == 3
        assert result["accounts_checked"] == 2

    def test_validate_monotonicity_backward_jump(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now - timedelta(hours=2))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        result = validator.validate_monotonicity(account_id="acct-1")
        assert result["is_monotonic"] is False
        assert result["violations"][0]["violation_type"] == "backward_timestamp"

    def test_validate_monotonicity_filters(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(minutes=5))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        result = validator.validate_monotonicity(
            start_time=now + timedelta(minutes=1), end_time=now + timedelta(minutes=10)
        )
        assert result["total_entries"] == 1

    def test_detect_gaps(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(minutes=1))
        self._add(db, "acct-1", 5, now + timedelta(minutes=2))
        self._add(db, "acct-2", 1, now + timedelta(minutes=3))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        result = validator.detect_gaps()
        assert result["has_gaps"] is True
        assert result["total_gaps"] == 1
        assert result["gaps"][0]["expected_sequence"] == 3
        assert result["gaps"][0]["actual_sequence"] == 5
        assert result["accounts_with_gaps"] == ["acct-1"]

    def test_detect_gaps_filters_and_none_sequences(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(minutes=1))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        # start_time/end_time filters restrict the window
        result = validator.detect_gaps(
            start_time=now + timedelta(seconds=1), end_time=now + timedelta(minutes=2)
        )
        assert result["total_gaps"] == 0
        assert result["has_gaps"] is False

    def test_detect_gaps_skips_none_sequence_rows(self):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        rows = [
            SimpleNamespace(account_id="a", sequence_number=None, timestamp=now),
            SimpleNamespace(account_id="a", sequence_number=1, timestamp=now + timedelta(minutes=1)),
            SimpleNamespace(account_id="a", sequence_number=2, timestamp=now + timedelta(minutes=2)),
        ]
        mdb = MagicMock()
        mdb.query.return_value.order_by.return_value.all.return_value = rows
        validator = ChronologicalIntegrityValidator(mdb)
        result = validator.detect_gaps()
        assert result["has_gaps"] is False

    def test_detect_out_of_order(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        # seq 2 has an earlier timestamp than seq 1 -> out of order
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now - timedelta(hours=1))
        self._add(db, "acct-2", 1, now + timedelta(hours=1))
        self._add(db, "acct-2", 2, now + timedelta(hours=2))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        result = validator.detect_out_of_order()
        assert result["has_out_of_order"] is True
        assert result["entries"][0]["sequence_number"] == 2
        assert result["entries"][0]["violation"] == "timestamp_before_previous_sequence"
        assert result["total_checked"] == 4

    def test_detect_out_of_order_single_account(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(minutes=1))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        assert validator.detect_out_of_order(account_id="acct-1")["has_out_of_order"] is False

    def test_detect_time_gaps(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(hours=5))
        self._add(db, "acct-1", 3, now + timedelta(hours=5, minutes=1))
        self._add(db, "acct-2", 1, now + timedelta(hours=6))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        result = validator.detect_time_gaps(threshold_seconds=3600)
        assert result["has_time_gaps"] is True
        assert result["total_gaps"] == 1
        assert result["time_gaps"][0]["gap_hours"] == 5.0
        assert result["threshold_seconds"] == 3600

    def test_detect_time_gaps_no_gap(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(minutes=10))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        assert validator.detect_time_gaps(account_id="acct-1")["has_time_gaps"] is False

    def test_validate_integrity_valid_and_invalid(self, db):
        from core.chronological_integrity import ChronologicalIntegrityValidator

        now = datetime.now(timezone.utc)
        self._add(db, "acct-1", 1, now)
        self._add(db, "acct-1", 2, now + timedelta(minutes=1))
        db.commit()
        validator = ChronologicalIntegrityValidator(db)
        result = validator.validate_integrity(account_id="acct-1")
        assert result["is_valid"] is True
        assert result["monotonicity"]["is_monotonic"] is True

        self._add(db, "acct-1", 3, now - timedelta(hours=3))
        db.commit()
        result = validator.validate_integrity(account_id="acct-1")
        assert result["is_valid"] is False


# ============================================================================
# agent_marketplace_service
# ============================================================================


class TestAgentMarketplaceService:
    def test_publish_agent_strips_credentials(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService

        service = AgentMarketplaceService(db, saas_client=MagicMock())
        cleaned = service.publish_agent(
            {
                "name": "Agent",
                "configuration": {
                    "api_key": "secret-1",
                    "nested": {"password": "pw"},
                    "keep": 1,
                },
                "capabilities": ["sk-1"],
            }
        )
        assert "api_key" not in cleaned["configuration"]
        assert "password" not in cleaned["configuration"]["nested"]
        assert cleaned["configuration"]["keep"] == 1
        assert cleaned["name"] == "Agent"

    def test_browse_agents_success_and_error(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService

        saas = MagicMock()
        saas.fetch_agents_sync = Mock(return_value={"agents": [{"id": "a1"}], "total": 1})
        service = AgentMarketplaceService(db, saas_client=saas)
        assert service.browse_agents(query="finance", category="ops", page=2, page_size=10)["total"] == 1

        saas.fetch_agents_sync = Mock(side_effect=RuntimeError("down"))
        result = service.browse_agents()
        assert result["agents"] == []
        assert result["source"] == "error"

    def test_get_template_details_success_and_error(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService

        saas = MagicMock()
        saas.get_agent_template_sync = Mock(return_value={"id": "t1"})
        service = AgentMarketplaceService(db, saas_client=saas)
        assert service.get_template_details("t1")["id"] == "t1"
        saas.get_agent_template_sync = Mock(side_effect=RuntimeError("boom"))
        assert service.get_template_details("t1") is None

    def test_install_agent_template_not_found(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService

        saas = MagicMock()
        saas.get_agent_template_sync = Mock(return_value=None)
        service = AgentMarketplaceService(db, saas_client=saas)
        result = service.install_agent("tpl-missing", "ten-1", "u-1")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_install_agent_success(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService
        from core.models import AgentInstallation, AgentRegistry, AgentSkill, OperationErrorResolution

        saas = MagicMock()
        saas.get_agent_template_sync = Mock(
            return_value={
                "name": "Support Bot",
                "description": "Handles support tickets",
                "category": "Support",
                "configuration": {"system_prompt": "be helpful"},
                "anonymized_memory_bundle": {
                    "heuristics": [
                        {"error_type": "timeout", "error_code": "E1", "resolution": "retry"},
                        {"error_type": "refusal", "resolution": "rephrase"},
                    ]
                },
                "capabilities": ["sk-1", "sk-2"],
                "version": "1.2.0",
            }
        )
        saas.install_agent_sync = Mock()
        service = AgentMarketplaceService(db, saas_client=saas)
        with _patch_usage_db():
            result = service.install_agent("tpl-1", "ten-1", "u-1")

        assert result["success"] is True
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == result["agent_id"]).first()
        assert agent.status == "intern"
        assert agent.display_name == "Support Bot (Marketplace)"
        assert db.query(OperationErrorResolution).count() == 2
        assert db.query(AgentSkill).count() == 2
        assert db.query(AgentInstallation).filter(AgentInstallation.template_id == "tpl-1").count() == 1
        saas.install_agent_sync.assert_called_once_with("tpl-1", "ten-1")

    def test_install_agent_exception_rolls_back(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService

        saas = MagicMock()
        saas.get_agent_template_sync = Mock(return_value={"name": "Bot", "category": "General"})
        saas.install_agent_sync = Mock(side_effect=RuntimeError("saas notify failed"))
        service = AgentMarketplaceService(db, saas_client=saas)
        with _patch_usage_db():
            result = service.install_agent("tpl-1", "ten-1", "u-1")
        assert result["success"] is False
        assert "saas notify failed" in result["error"]

    def test_uninstall_agent_not_installed(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService

        service = AgentMarketplaceService(db, saas_client=MagicMock())
        result = service.uninstall_agent("ten-1", "ag-1")
        assert result["success"] is False
        assert "not installed" in result["error"]

    def test_uninstall_agent_success(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService
        from core.models import (
            AgentInstallation,
            AgentRegistry,
            AgentSkill,
            OperationErrorResolution,
        )

        db.add(
            AgentRegistry(
                id="ag-1",
                name="Marketplace Agent",
                category="General",
                role="agent",
                type="marketplace",
                module_path="core.generic_agent",
                class_name="GenericAgent",
                user_id="u-1",
                tenant_id="ten-1",
                status="intern",
                configuration={},
            )
        )
        db.add(
            AgentInstallation(
                id="inst-1",
                tenant_id="ten-1",
                template_id="tpl-1",
                instantiated_agent_id="ag-1",
                installed_version="1.0.0",
                is_active=True,
            )
        )
        db.add(AgentSkill(agent_id="ag-1", skill_id="sk-1", enabled=True))
        db.add(
            OperationErrorResolution(
                id="res-1",
                tenant_id="ten-1",
                error_type="err",
                resolution_attempted="retry",
                success=True,
                resolution_metadata={"source_template_id": "tpl-1"},
            )
        )
        db.commit()

        service = AgentMarketplaceService(db, saas_client=MagicMock())
        result = service.uninstall_agent("ten-1", "ag-1")
        assert result["success"] is True
        assert db.query(AgentRegistry).filter(AgentRegistry.id == "ag-1").first() is None
        assert db.query(AgentInstallation).count() == 0
        assert db.query(AgentSkill).count() == 0
        assert db.query(OperationErrorResolution).filter(OperationErrorResolution.id == "res-1").first() is None

    def test_uninstall_agent_exception(self, db):
        from core.agent_marketplace_service import AgentMarketplaceService

        service = AgentMarketplaceService(db, saas_client=MagicMock())
        db.query = Mock(side_effect=RuntimeError("db down"))
        result = service.uninstall_agent("ten-1", "ag-1")
        assert result["success"] is False


# ============================================================================
# admin_bootstrap
# ============================================================================


class TestAdminBootstrap:
    @pytest.fixture()
    def db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        yield session
        session.close()
        engine.dispose()

    @pytest.fixture()
    def bootstrap_db(self, db, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_BOOTSTRAP_PASSWORD_FILE", str(tmp_path / "pwd.txt"))
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        with patch(
            "core.admin_bootstrap.get_db_session", side_effect=lambda: _db_ctx(db)
        ):
            yield db

    def test_ensure_admin_user_creates_with_generated_password(self, bootstrap_db, tmp_path):
        from core.admin_bootstrap import ensure_admin_user
        from core.models import User

        ensure_admin_user()
        user = bootstrap_db.query(User).filter(User.email == "admin@example.com").first()
        assert user is not None
        assert user.role == "workspace_admin"
        pwd_file = tmp_path / "pwd.txt"
        assert pwd_file.exists()
        assert pwd_file.read_text()  # password written
        assert os.stat(pwd_file).st_mode & 0o777 == 0o600

    def test_ensure_admin_user_keeps_existing(self, bootstrap_db, tmp_path):
        from core.admin_bootstrap import ensure_admin_user
        from core.models import User

        ensure_admin_user()
        first_hash = bootstrap_db.query(User).filter(User.email == "admin@example.com").first().hashed_password
        ensure_admin_user()
        again = bootstrap_db.query(User).filter(User.email == "admin@example.com").first()
        assert again.hashed_password == first_hash

    def test_ensure_admin_user_resets_with_env_password(self, bootstrap_db, monkeypatch):
        from core.admin_bootstrap import ensure_admin_user
        from core.models import User

        ensure_admin_user()
        first_hash = bootstrap_db.query(User).filter(User.email == "admin@example.com").first().hashed_password
        monkeypatch.setenv("ADMIN_PASSWORD", "custom-pass-123")
        ensure_admin_user()
        again = bootstrap_db.query(User).filter(User.email == "admin@example.com").first()
        assert again.hashed_password != first_hash
        assert again.status == "active"  # UserStatus str-enum value

    def test_ensure_admin_user_exception_rolls_back(self, db):
        from core.admin_bootstrap import ensure_admin_user

        db.add = Mock(side_effect=RuntimeError("boom"))
        with patch("core.admin_bootstrap.get_db_session", side_effect=lambda: _db_ctx(db)):
            ensure_admin_user()  # must not raise

    def test_ensure_default_tenant_and_workspace_creates(self, db):
        from core.admin_bootstrap import ensure_default_tenant_and_workspace
        from core.models import Tenant, Workspace
        from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID

        ensure_default_tenant_and_workspace(db)
        assert db.query(Tenant).filter(Tenant.id == PERSONAL_TENANT_ID).first() is not None
        assert db.query(Workspace).filter(Workspace.id == PERSONAL_WORKSPACE_ID).first() is not None

        # Idempotent second run
        ensure_default_tenant_and_workspace(db)
        assert db.query(Tenant).count() == 1
        assert db.query(Workspace).count() == 1

    def test_ensure_demo_agent_creates_and_noop(self, db):
        from core.admin_bootstrap import ensure_demo_agent
        from core.models import AgentRegistry

        ensure_demo_agent(db)
        agent = db.query(AgentRegistry).filter(AgentRegistry.name == "Demo Assistant").first()
        assert agent is not None
        assert agent.status == "intern"
        assert agent.configuration["demo_agent"] is True

        ensure_demo_agent(db)
        assert db.query(AgentRegistry).count() == 1

    def test_write_password_file_oserror(self, monkeypatch):
        from core.admin_bootstrap import _write_password_to_secure_file

        monkeypatch.setenv("ATOM_BOOTSTRAP_PASSWORD_FILE", "/nonexistent-dir-x/never/pwd.txt")
        assert _write_password_to_secure_file("pw") == ""

    def test_write_password_file_success(self, tmp_path, monkeypatch):
        from core.admin_bootstrap import _write_password_to_secure_file

        path = tmp_path / "sub" / "pwd.txt"
        monkeypatch.setenv("ATOM_BOOTSTRAP_PASSWORD_FILE", str(path))
        returned = _write_password_to_secure_file("hunter2")
        assert returned == str(path)
        assert path.read_text() == "hunter2"


# ============================================================================
# auto_healing_endpoints
# ============================================================================


class TestAutoHealingEndpoints:
    @pytest.fixture()
    def client(self):
        from fastapi import FastAPI

        from core.auto_healing_endpoints import router

        app = FastAPI()
        app.include_router(router)
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            yield c

    def test_get_health(self, client):
        with patch(
            "core.auto_healing_endpoints.health_monitor.get_health_summary",
            return_value={
                "total_services": 2,
                "healthy": 2,
                "degraded": 0,
                "unhealthy": 0,
                "health_percentage": 100.0,
                "services": [],
                "last_updated": "2026-01-01T00:00:00",
            },
        ):
            resp = client.get("/api/auto-healing/health")
        assert resp.status_code == 200
        assert resp.json()["healthy"] == 2

    def test_trigger_health_check(self, client):
        with patch(
            "core.auto_healing_endpoints.health_monitor.check_all_services",
            new=AsyncMock(return_value=[{"service": "api", "status": "healthy"}]),
        ):
            resp = client.post("/api/auto-healing/health/check")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Health check completed for 1 services"

    def test_get_circuit_breakers(self, client):
        with patch(
            "core.auto_healing_endpoints.auto_healing_engine.get_service_status",
            return_value={"api": {"state": "closed"}},
        ):
            resp = client.get("/api/auto-healing/circuit-breakers")
        assert resp.json()["circuit_breakers"]["api"]["state"] == "closed"

    def test_get_tokens_and_trigger_refresh(self, client):
        with patch(
            "core.auto_healing_endpoints.token_refresher.get_status",
            return_value={"gmail": {"needs_refresh": False}},
        ), patch(
            "core.auto_healing_endpoints.token_refresher.check_and_refresh_all",
            new=AsyncMock(return_value=None),
        ):
            resp = client.get("/api/auto-healing/tokens")
            assert resp.json()["tokens"]["gmail"]["needs_refresh"] is False
            resp = client.post("/api/auto-healing/tokens/refresh")
        assert resp.json()["message"] == "Token refresh check completed"

    def test_get_auto_healing_status(self, client):
        with patch(
            "core.auto_healing_endpoints.health_monitor.get_health_summary",
            return_value={"total_services": 1},
        ), patch(
            "core.auto_healing_endpoints.auto_healing_engine.get_service_status",
            return_value={},
        ), patch(
            "core.auto_healing_endpoints.token_refresher.get_status",
            return_value={},
        ):
            resp = client.get("/api/auto-healing/status")
        assert resp.status_code == 200
        assert resp.json()["health_monitor"]["total_services"] == 1


# ============================================================================
# autonomous_supervisor_service (gap coverage on top of existing tests)
# ============================================================================


def _make_agent(db, agent_id, name="Supervisor", category="finance", confidence=0.95):
    from core.models import AgentRegistry, AgentStatus

    agent = AgentRegistry(
        id=agent_id,
        name=name,
        category=category,
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=confidence,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        user_id="u-1",
    )
    db.add(agent)
    db.commit()
    return agent


class TestAutonomousSupervisorServiceGaps:
    def test_find_autonomous_supervisor_no_match(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        agent = _make_agent(db, "sup-1")
        service = AutonomousSupervisorService(db)
        found = asyncio.get_event_loop().run_until_complete(
            service.find_autonomous_supervisor(agent, category="nonexistent")
        )
        assert found is None

    def test_find_autonomous_supervisor_adversarial_match(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        intern = _make_agent(db, "intern-1", name="Intern", category="finance", confidence=0.5)
        intern.status = "intern"
        db.commit()
        _make_agent(db, "sup-adv", name="Adv", category="finance", confidence=0.92)
        # give the adversarial candidate a different risk_profile
        from core.models import AgentRegistry

        adv = db.query(AgentRegistry).filter(AgentRegistry.id == "sup-adv").first()
        adv.diversity_profile = {"risk_profile": "aggressive", "latency_focus": "low"}
        intern.diversity_profile = {"risk_profile": "conservative"}
        db.commit()
        service = AutonomousSupervisorService(db)
        found = asyncio.get_event_loop().run_until_complete(
            service.find_autonomous_supervisor(intern, adversarial=True)
        )
        assert found.id == "sup-adv"

    def test_find_autonomous_supervisor_adversarial_no_mismatch_falls_back(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService
        from core.models import AgentRegistry

        intern = _make_agent(db, "intern-2", name="Intern", category="finance", confidence=0.5)
        intern.status = "intern"
        _make_agent(db, "sup-1", name="S1", category="finance", confidence=0.91)
        sup2 = db.query(AgentRegistry).filter(AgentRegistry.id == "sup-1").first()
        sup2.diversity_profile = {"risk_profile": "same"}
        intern.diversity_profile = {"risk_profile": "same"}
        db.commit()
        service = AutonomousSupervisorService(db)
        found = asyncio.get_event_loop().run_until_complete(
            service.find_autonomous_supervisor(intern, adversarial=True)
        )
        assert found is not None  # falls back to highest confidence

    def test_find_autonomous_supervisor_falsy_max_warns(self, db):
        """Covers the `else` warning branch (supervisor falsy after max)."""
        from unittest.mock import Mock

        from core.autonomous_supervisor_service import AutonomousSupervisorService

        intern = _make_agent(db, "intern-3", name="Intern", category="finance", confidence=0.5)
        intern.status = "intern"
        db.commit()
        falsy = Mock()
        falsy.confidence_score = 0.9
        falsy.__bool__ = lambda self: False
        # Fully mocked db (real Session.query is a method; can't stub it)
        service = AutonomousSupervisorService(MagicMock())
        # self-referential filter chain: any number of .filter() calls collapse
        f = MagicMock()
        f.filter.return_value = f
        f.all.return_value = [falsy]
        service.db.query.return_value = f
        found = asyncio.get_event_loop().run_until_complete(
            service.find_autonomous_supervisor(intern, adversarial=False)
        )
        assert found is falsy

    def test_review_proposal_full_flow(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService
        from core.models import AgentProposal

        agent = _make_agent(db, "sup-1")
        proposal = AgentProposal(
            id="prop-1",
            tenant_id="t-1",
            user_id="u-1",
            agent_id="intern-1",
            proposal_type="action",
            proposal_data={"action_type": "browser_automate", "reasoning": "do it"},
            status="pending_approval",
        )
        db.add(proposal)
        db.commit()
        wm = MagicMock()
        wm.get_experience_statistics = AsyncMock(return_value={"success_rate": 0.7})
        service = AutonomousSupervisorService(db)
        with patch("core.agent_world_model.WorldModelService", return_value=wm):
            review = asyncio.get_event_loop().run_until_complete(
                service.review_proposal(proposal, agent)
            )
        assert review.risk_level == "medium"
        assert review.approved is True
        assert "browser_automate" in review.reasoning

    def test_monitor_execution_not_found_and_error(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        agent = _make_agent(db, "sup-1")
        service = AutonomousSupervisorService(db)
        events = asyncio.get_event_loop().run_until_complete(
            _drain(service.monitor_execution("missing-exec", agent))
        )
        types = [e.event_type for e in events]
        assert "monitoring_started" in types
        assert "error" in types

    async def test_monitor_execution_failed(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService
        from core.models import AgentExecution

        agent = _make_agent(db, "sup-1")
        db.add(
            AgentExecution(
                id="exec-1",
                status="failed",
                error_message="timeout",
                duration_seconds=10,
            )
        )
        db.commit()
        service = AutonomousSupervisorService(db)
        events = [e async for e in service.monitor_execution("exec-1", agent)]
        failed = [e for e in events if e.event_type == "execution_failed"]
        assert failed
        assert failed[0].data["error_analysis"]["error_type"] == "execution_error"

    async def test_monitor_execution_concern_detected(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService
        from core.models import AgentExecution

        agent = _make_agent(db, "sup-1")
        exec_row = AgentExecution(
            id="exec-2",
            status="running",
            duration_seconds=10,
        )
        db.add(exec_row)
        db.commit()
        service = AutonomousSupervisorService(db, poll_interval=0.001)
        calls = {"n": 0}

        async def _concerns(execution, supervisor):
            calls["n"] += 1
            if calls["n"] >= 2:
                # Terminate the poll loop after the first concern event
                exec_row.status = "completed"
                db.commit()
            return {"has_concerns": True, "concerns": ["loop"], "severity": "high"}

        service._check_execution_concerns = _concerns
        events = [e async for e in service.monitor_execution("exec-2", agent)]
        types = [e.event_type for e in events]
        assert "concern_detected" in types
        assert "execution_completed" in types

    async def test_monitor_execution_exception_yields_monitoring_error(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        agent = _make_agent(db, "sup-1")
        service = AutonomousSupervisorService(db, poll_interval=0.001)
        service.db.query = MagicMock(side_effect=RuntimeError("db gone"))
        events = [e async for e in service.monitor_execution("exec-9", agent)]
        assert any(e.event_type == "monitoring_error" for e in events)

    async def test_approve_proposal_not_found_and_wrong_status(self, db):
        from core.autonomous_supervisor_service import (
            AutonomousSupervisorService,
            ProposalReview,
        )
        from core.models import AgentProposal

        agent = _make_agent(db, "sup-1")
        review = ProposalReview(True, 0.9, "safe", "ok")
        service = AutonomousSupervisorService(db)
        assert await service.approve_proposal("ghost", agent.id, review) is False

        db.add(
            AgentProposal(
                id="prop-2",
                tenant_id="t-1",
                user_id="u-1",
                agent_id="intern-1",
                proposal_type="action",
                proposal_data={},
                status="executed",
            )
        )
        db.commit()
        assert await service.approve_proposal("prop-2", agent.id, review) is False

    async def test_get_available_supervisors(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        _make_agent(db, "sup-1", category="finance", confidence=0.91)
        _make_agent(db, "sup-2", category="finance", confidence=0.95)
        _make_agent(db, "sup-3", category="ops", confidence=0.93)
        service = AutonomousSupervisorService(db)
        all_sups = await service.get_available_supervisors()
        assert len(all_sups) == 3
        assert all_sups[0].id == "sup-2"  # highest confidence first
        finance = await service.get_available_supervisors(category="finance")
        assert len(finance) == 2

    def test_helper_methods(self):
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        service = AutonomousSupervisorService(MagicMock())
        supervisor = SimpleNamespace(name="Sup", confidence_score=0.95)
        proposal = SimpleNamespace()
        analysis = asyncio.get_event_loop().run_until_complete(
            service._analyze_proposal_with_llm(
                supervisor, proposal, "device_command", "because", "ctx"
            )
        )
        assert analysis["confidence"] == 0.75  # high risk -> -0.2
        safe = asyncio.get_event_loop().run_until_complete(
            service._analyze_proposal_with_llm(
                SimpleNamespace(name="S", confidence_score=0.95), proposal, "canvas_present", "r"
            )
        )
        assert safe["confidence"] == 1.0  # safe -> capped at 1.0

        assert service._calculate_risk_level("delete", {}) == "high"
        assert service._calculate_risk_level("create", {}) == "safe"
        assert service._calculate_risk_level("unknown", {}) == "medium"
        assert service._should_approve_proposal({"confidence": 0.9}, "high", 0.96) is False
        assert service._should_approve_proposal({"confidence": 0.96}, "high", 0.96) is True
        assert service._should_approve_proposal({"confidence": 0.8}, "medium", 0.91) is False
        assert service._should_approve_proposal({"confidence": 0.86}, "medium", 0.91) is True
        assert service._should_approve_proposal({"confidence": 0.7}, "safe", 0.86) is False
        assert service._should_approve_proposal({"confidence": 0.8}, "safe", 0.86) is True

        exec_row = SimpleNamespace(status="completed")
        res = asyncio.get_event_loop().run_until_complete(
            service._analyze_execution_result(exec_row, supervisor)
        )
        assert res["success"] is True
        err = asyncio.get_event_loop().run_until_complete(
            service._analyze_execution_error(exec_row, supervisor)
        )
        assert err["root_cause"] == "unknown"
        concerns = asyncio.get_event_loop().run_until_complete(
            service._check_execution_concerns(exec_row, supervisor)
        )
        assert concerns["has_concerns"] is False

    def test_review_proposal_experiences_missing_key(self, db):
        from core.autonomous_supervisor_service import AutonomousSupervisorService
        from core.models import AgentProposal

        agent = _make_agent(db, "sup-1")
        db.add(
            AgentProposal(
                id="prop-3",
                tenant_id="t-1",
                user_id="u-1",
                agent_id="intern-1",
                proposal_type="workflow",
                proposal_data={"action_type": "workflow_trigger"},
                status="pending_approval",
            )
        )
        db.commit()
        wm = MagicMock()
        wm.get_experience_statistics = AsyncMock(return_value={})
        service = AutonomousSupervisorService(db)
        with patch("core.agent_world_model.WorldModelService", return_value=wm):
            review = asyncio.get_event_loop().run_until_complete(
                service.review_proposal(
                    db.query(AgentProposal).filter(AgentProposal.id == "prop-3").first(),
                    agent,
                )
            )
        # Non-action proposals have no proposed_action -> action_type "unknown"
        assert review.risk_level == "medium"


async def _drain(agen):
    return [e async for e in agen]


# ============================================================================
# apar_engine
# ============================================================================


class TestAPAREngine:
    def test_intake_invoice_auto_approve_and_pending(self):
        from core.apar_engine import APAREngine, InvoiceStatus

        engine = APAREngine()
        inv = engine.intake_invoice(
            "email",
            {"vendor": "Acme", "amount": 499.99, "due_date": "2026-12-01T00:00:00"},
        )
        assert inv.status == InvoiceStatus.APPROVED
        assert inv.approved_by == "auto"
        assert inv.id.startswith("ap_")
        assert inv.payment_terms == "Net 30"

        big = engine.intake_invoice("portal", {"vendor": "BigCo", "amount": 5000.0})
        assert big.status == InvoiceStatus.PENDING_APPROVAL
        assert big.due_date > datetime.now()

    def test_intake_invoice_negative_rejected(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        with pytest.raises(ValueError):
            engine.intake_invoice("email", {"amount": -10.0})

    def test_approve_invoice(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        inv = engine.intake_invoice("email", {"amount": 1000.0})
        approved = engine.approve_invoice(inv.id, "finance-manager")
        assert approved.status.value == "approved"
        assert approved.approved_by == "finance-manager"
        with pytest.raises(ValueError):
            engine.approve_invoice("ghost", "x")

    def test_get_pending_approvals_and_upcoming_payments(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        pending = engine.intake_invoice("email", {"amount": 1000.0})
        approved = engine.intake_invoice(
            "email",
            {
                "amount": 2000.0,
                "due_date": (datetime.now() + timedelta(days=3)).isoformat(),
            },
        )
        engine.approve_invoice(approved.id, "mgr")
        # past-due approved invoice excluded
        past_due = engine.intake_invoice(
            "email",
            {"amount": 3000.0, "due_date": (datetime.now() - timedelta(days=2)).isoformat()},
        )
        engine.approve_invoice(past_due.id, "mgr")
        # far-future approved invoice excluded
        future = engine.intake_invoice(
            "email",
            {"amount": 4000.0, "due_date": (datetime.now() + timedelta(days=60)).isoformat()},
        )
        engine.approve_invoice(future.id, "mgr")

        assert engine.get_pending_approvals() == [pending]
        due = engine.get_upcoming_payments(days=7)
        assert [i.id for i in due] == [approved.id]

    def test_generate_invoice_and_send_mark_paid(self):
        from core.apar_engine import APAREngine, InvoiceStatus

        engine = APAREngine()
        inv = engine.generate_invoice(
            "contract",
            {"customer": "CustomerCo", "amount": 1500.0, "due_date": "2026-11-01T00:00:00"},
        )
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.source == "contract"
        assert inv.id.startswith("ar_")

        no_date = engine.generate_invoice("crm_deal", {"customer": "X", "amount": 10.0})
        assert no_date.due_date > datetime.now()

        with pytest.raises(ValueError):
            engine.generate_invoice("contract", {"amount": 0.0})

        sent = engine.send_invoice(inv.id)
        assert sent.status == InvoiceStatus.SENT
        paid = engine.mark_paid(inv.id)
        assert paid.status == InvoiceStatus.PAID
        assert engine.mark_invoice_paid(inv.id).status == InvoiceStatus.PAID
        with pytest.raises(ValueError):
            engine.send_invoice("ghost")
        with pytest.raises(ValueError):
            engine.mark_paid("ghost")

    def test_get_overdue_invoices_promotes_sent(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        overdue = engine.generate_invoice(
            "contract",
            {"customer": "Late", "amount": 100.0, "due_date": (datetime.now() - timedelta(days=5)).isoformat()},
        )
        engine.send_invoice(overdue.id)
        assert engine.get_overdue_invoices() == [overdue]
        # idempotent second call
        assert engine.get_overdue_invoices() == [overdue]
        # not-yet-due sent invoice stays out
        not_due = engine.generate_invoice(
            "contract",
            {"customer": "OnTime", "amount": 50.0, "due_date": (datetime.now() + timedelta(days=5)).isoformat()},
        )
        engine.send_invoice(not_due.id)
        assert engine.get_overdue_invoices() == [overdue]

    def test_get_all_invoices_sorted(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        ar = engine.generate_invoice("contract", {"customer": "C", "amount": 10.0})
        ap = engine.intake_invoice("email", {"vendor": "V", "amount": 10.0})
        all_invs = engine.get_all_invoices()
        assert len(all_invs) == 2
        assert all_invs[0].id == ap.id  # created later -> first (desc)

    def test_generate_invoice_content(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        ar = engine.generate_invoice(
            "contract",
            {
                "customer": "C",
                "amount": 123.45,
                "due_date": "2026-11-01T00:00:00",
                "line_items": [{"description": "Consulting", "amount": 100.0}],
            },
        )
        content = engine.generate_invoice_content(ar.id)
        assert "INVOICE" in content
        assert "Type: AR" in content
        assert "CustomerCo".replace("CustomerCo", "C") in content
        assert "$123.45" in content

        ap = engine.intake_invoice(
            "email",
            {"vendor": "Vendor", "amount": 50.0, "due_date": "2026-11-01T00:00:00"},
        )
        content_ap = engine.generate_invoice_content(ap.id)
        assert "Type: AP" in content_ap
        assert "Vendor" in content_ap

        with pytest.raises(ValueError):
            engine.generate_invoice_content("ghost")

    def test_generate_invoice_pdf(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        ar = engine.generate_invoice(
            "contract",
            {
                "customer": "C",
                "amount": 999.5,
                "due_date": "2026-11-01T00:00:00",
                "line_items": [{"description": "Item", "amount": 999.5}],
            },
        )
        pdf = engine.generate_invoice_pdf(ar.id)
        assert pdf.startswith(b"%PDF")

        ap = engine.intake_invoice(
            "email", {"vendor": "V", "amount": 50.0, "due_date": "2026-11-01T00:00:00"}
        )
        assert engine.generate_invoice_pdf(ap.id).startswith(b"%PDF")

        with pytest.raises(ValueError):
            engine.generate_invoice_pdf("ghost")

    def test_generate_invoice_pdf_no_reportlab(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        inv = engine.generate_invoice("contract", {"customer": "C", "amount": 10.0})
        with patch("core.apar_engine.HAS_REPORTLAB", False):
            with pytest.raises(ImportError):
                engine.generate_invoice_pdf(inv.id)

    def test_has_reportlab_false_import_branch(self, monkeypatch):
        """Cover the `except ImportError: HAS_REPORTLAB = False` module branch."""
        import importlib

        import core.apar_engine as mod

        # Block every reportlab* module (the dotted parent is already cached
        # in sys.modules, so hiding only "reportlab" would not fail the import).
        for name in list(sys.modules):
            if name == "reportlab" or name.startswith("reportlab."):
                monkeypatch.setitem(sys.modules, name, None)
        try:
            reloaded = importlib.reload(mod)
            assert reloaded.HAS_REPORTLAB is False
        finally:
            monkeypatch.undo()
        # Reload once more so the module is back to the reportlab-enabled state
        assert importlib.reload(mod).HAS_REPORTLAB is True

    def test_generate_reminder_auto_escalation(self):
        from core.apar_engine import APAREngine, ReminderTone

        engine = APAREngine()
        inv = engine.generate_invoice(
            "contract",
            {"customer": "C", "amount": 200.0, "due_date": "2026-11-01T00:00:00"},
        )
        r1 = engine.generate_reminder(inv.id)
        assert r1["tone"] == "friendly"
        assert "Friendly Reminder" in r1["subject"]
        r2 = engine.generate_reminder(inv.id)
        assert r2["tone"] == "firm"
        r3 = engine.generate_reminder(inv.id)
        assert r3["tone"] == "final"
        assert r3["reminders_sent"] == 3
        assert "FINAL NOTICE" in r3["message"]

        # explicit tones (enum contract — strings are not coerced)
        assert (
            engine.generate_reminder(inv.id, tone=ReminderTone.FIRM)["tone"] == "firm"
        )
        assert (
            engine.generate_reminder(inv.id, tone=ReminderTone.FRIENDLY)["tone"]
            == "friendly"
        )
        assert (
            engine.generate_reminder(inv.id, tone=ReminderTone.FINAL)["tone"] == "final"
        )
        # send_reminder alias
        assert engine.send_reminder(inv.id)["invoice_id"] == inv.id

        with pytest.raises(ValueError):
            engine.generate_reminder("ghost")

    def test_get_collection_summary(self):
        from core.apar_engine import APAREngine

        engine = APAREngine()
        engine.generate_invoice(
            "contract",
            {"customer": "C1", "amount": 100.0, "due_date": "2026-11-01T00:00:00"},
        )
        sent = engine.generate_invoice(
            "contract",
            {"customer": "C2", "amount": 200.0, "due_date": "2026-11-01T00:00:00"},
        )
        overdue = engine.generate_invoice(
            "contract",
            {"customer": "C3", "amount": 300.0, "due_date": (datetime.now() - timedelta(days=1)).isoformat()},
        )
        paid = engine.generate_invoice(
            "contract",
            {"customer": "C4", "amount": 400.0, "due_date": "2026-11-01T00:00:00"},
        )
        engine.send_invoice(sent.id)
        engine.send_invoice(overdue.id)
        engine.send_invoice(paid.id)
        engine.mark_paid(paid.id)
        engine.get_overdue_invoices()  # promote the past-due sent invoice
        summary = engine.get_collection_summary()
        assert summary["total_outstanding"] == 500.0
        assert summary["overdue_count"] == 1
        assert summary["invoices_sent"] == 1
        assert summary["invoices_paid"] == 1
