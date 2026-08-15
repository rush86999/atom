# -*- coding: utf-8 -*-
"""W87A — coverage push: 8 governance/ops core services to >=95% statement coverage.

Targets (standalone coverage):
  core/agent_marketplace_service.py      (baseline 100% via other suites — re-covered here)
  core/blueprint_healer.py               (baseline 100% via other suites — re-covered here)
  core/budget_guardrail.py               (baseline 100% via other suites — re-covered here)
  core/bulk_operations_processor.py      (baseline 70% via existing suites — gaps: full
                                         _process_job lifecycle, queue concurrency, asana
                                         update/delete/complete/unsupported/exception paths,
                                         jira/salesforce update+error, integration error
                                         branches, save-results failure)
  core/chronological_integrity.py        (baseline 100% via other suites — re-covered here)
  core/conflict_resolution_service.py    (baseline 100% via other suites — re-covered here)
  core/alert_service.py                  (baseline 100% via other suites — re-covered here)
  core/admin_bootstrap.py                (baseline 100% via other suites — re-covered here)

Style: fully mocked deps (fake sessions, submodule patches), zero network,
zero LLM spend, no real DB.
"""
from __future__ import annotations

import asyncio
import builtins
import contextlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.agent_marketplace_service import AgentMarketplaceService
from core.admin_bootstrap import (
    _write_password_to_secure_file,
    ensure_admin_user,
    ensure_default_tenant_and_workspace,
    ensure_demo_agent,
)
from core.alert_service import (
    AlertEvaluationResult,
    AlertSeverity,
    AlertStatus,
    AlertThresholdService,
    AlertViolation,
)
from core.blueprint_healer import BlueprintHealer
from core.budget_guardrail import BudgetGuardrailService
from core.bulk_operations_processor import (
    BulkJob,
    IntegrationBulkProcessor,
    OperationStatus,
    get_bulk_processor,
)
from core.chronological_integrity import ChronologicalIntegrityValidator
from core.conflict_resolution_service import ConflictResolutionService
from core.integration_data_mapper import BulkOperation
from core.models import (
    AgentInstallation,
    AgentRegistry,
    AgentSkill,
    ConflictLog,
    FinancialAudit,
    OperationErrorResolution,
    Tenant,
    User,
    UserStatus,
    Workspace,
)
from accounting.models import Bill, Transaction
from sqlalchemy import func
from service_delivery.models import BudgetStatus, Project, ProjectTask

# ---------------------------------------------------------------------------
# Shared fake DB primitives
# ---------------------------------------------------------------------------


class FakeQuery:
    """Chainable fake query; results resolved lazily via results_fn when set."""

    def __init__(self, results=None, results_fn=None):
        self._results = results if results is not None else []
        self._results_fn = results_fn
        self.filter_calls = []
        self._deleted = 0

    def filter(self, *args, **kwargs):
        self.filter_calls.append((args, kwargs))
        return self

    def filter_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, n):
        return self

    def limit(self, n):
        return self

    def join(self, *args, **kwargs):
        return self

    def first(self):
        if self._results_fn is not None:
            return self._results_fn()
        return self._results[0] if self._results else None

    def all(self):
        return list(self._results)

    def scalar(self):
        if self._results_fn is not None:
            return self._results_fn()
        return self._results[0] if self._results else None

    def count(self):
        return len(self._results)

    def delete(self, *args, **kwargs):
        self._deleted = len(self._results)
        self._results = []
        return self._deleted


class FakeSession:
    """Fake SQLAlchemy session: per-model FakeQuery factories."""

    def __init__(self):
        self._queries = {}
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.deleted = []

    def register(self, model, query):
        self._queries[self._key(model)] = query
        return self

    def register_fn(self, model, fn):
        self._queries[self._key(model)] = FakeQuery(results_fn=fn)
        return self

    @staticmethod
    def _key(model):
        return model.__name__ if hasattr(model, "__name__") else str(model)

    def query(self, model):
        key = self._key(model)
        if key in self._queries:
            return self._queries[key]
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def flush(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True

    def refresh(self, obj):
        pass

    def delete(self, obj):
        self.deleted.append(obj)


def _bulk_op(operation_type="create", integration_id="test", items=None, batch_size=None):
    return BulkOperation(
        operation_type=operation_type,
        integration_id=integration_id,
        items=items if items is not None else [{"id": 1}],
        batch_size=batch_size if batch_size is not None else 100,
    )


def _job(operation, job_id="job-1", status=OperationStatus.PENDING):
    return BulkJob(
        job_id=job_id,
        operation=operation,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. agent_marketplace_service
# ---------------------------------------------------------------------------


class TestMarketplacePublish:
    def test_publish_agent_strips_credentials(self):
        service = AgentMarketplaceService(db=Mock(), saas_client=Mock())
        template = {"name": "x", "api_key": "secret", "nested": {"password": "pw"}}
        with patch(
            "core.blueprint_sanitizer.strip_credentials",
            return_value={"name": "x"},
        ) as mock_strip:
            result = service.publish_agent(template)
        mock_strip.assert_called_once_with(template)
        assert result == {"name": "x"}


class TestMarketplaceBrowse:
    @pytest.fixture
    def service(self):
        return AgentMarketplaceService(db=Mock(), saas_client=Mock())

    def test_browse_agents_success(self, service):
        payload = {"agents": [{"id": "a1"}], "total": 1}
        service.saas_client.fetch_agents_sync.return_value = payload
        result = service.browse_agents(query="sales", category="sales", page=2, page_size=10)
        service.saas_client.fetch_agents_sync.assert_called_once_with(
            query="sales", category="sales", page=2, page_size=10
        )
        assert result == payload

    def test_browse_agents_error(self, service):
        service.saas_client.fetch_agents_sync.side_effect = RuntimeError("boom")
        result = service.browse_agents(query="q", category=None, page=1, page_size=20)
        assert result["source"] == "error"
        assert result["error"] == "boom"
        assert result["agents"] == []
        assert result["total"] == 0
        assert result["page"] == 1

    def test_get_template_details_success(self, service):
        service.saas_client.get_agent_template_sync.return_value = {"id": "t1"}
        assert service.get_template_details("t1") == {"id": "t1"}

    def test_get_template_details_error(self, service):
        service.saas_client.get_agent_template_sync.side_effect = ValueError("nope")
        assert service.get_template_details("t1") is None


class TestMarketplaceInstall:
    def _template(self):
        return {
            "name": "x" * 150,
            "description": "y" * 600,
            "category": "ops",
            "version": "2.1.0",
            "configuration": {"capabilities": ["chat"]},
            "anonymized_memory_bundle": {
                "heuristics": [
                    {"error_type": "e1", "error_code": "c1", "resolution": "retry"},
                    {"error_type": "e2", "error_code": "c2", "resolution": "wait"},
                ]
            },
            "capabilities": ["skill-1", "skill-2"],
        }

    def test_install_agent_template_not_found(self):
        service = AgentMarketplaceService(db=Mock(), saas_client=Mock())
        service.saas_client.get_agent_template_sync.return_value = None
        result = service.install_agent("t1", "tenant-1", "user-1")
        assert result == {"success": False, "error": "Agent template not found in marketplace"}

    def test_install_agent_success(self):
        db = FakeSession()
        service = AgentMarketplaceService(db=db, saas_client=Mock())
        template = self._template()
        service.saas_client.get_agent_template_sync.return_value = template
        with patch("core.agent_marketplace_service.MarketplaceUsageTracker.track_usage") as mock_track:
            result = service.install_agent("t1", "tenant-1", "user-1")
        assert result["success"] is True
        assert result["message"] == f"Installed {'x' * 150} successfully"
        agent = db.added[0]
        assert agent.name == "x" * 100
        assert agent.display_name == "x" * 100  # [:100] truncates the suffix
        assert agent.description == "y" * 500
        assert agent.module_path == "core.generic_agent"
        assert agent.class_name == "GenericAgent"
        assert agent.tenant_id == "tenant-1"
        assert agent.status == "intern"
        assert db.committed is True
        # 2 heuristics -> OperationErrorResolution rows
        resolutions = [o for o in db.added if o.__class__.__name__ == "OperationErrorResolution"]
        assert len(resolutions) == 2
        assert resolutions[0].resolution_metadata["source_template_id"] == "t1"
        # 2 skills + 1 installation
        skills = [o for o in db.added if o.__class__.__name__ == "AgentSkill"]
        assert len(skills) == 2
        installs = [o for o in db.added if o.__class__.__name__ == "AgentInstallation"]
        assert len(installs) == 1
        assert installs[0].installed_version == "2.1.0"
        service.saas_client.install_agent_sync.assert_called_once_with("t1", "tenant-1")
        mock_track.assert_called_once_with(item_type="agent", item_id="t1", success=True)

    def test_install_agent_no_memory_or_capabilities(self):
        db = FakeSession()
        service = AgentMarketplaceService(db=db, saas_client=Mock())
        service.saas_client.get_agent_template_sync.return_value = {
            "name": "plain", "description": "", "category": "gen"
        }
        with patch("core.agent_marketplace_service.MarketplaceUsageTracker.track_usage"):
            result = service.install_agent("t2", "tenant-1", "user-1")
        assert result["success"] is True
        assert not any(o.__class__.__name__ == "OperationErrorResolution" for o in db.added)
        assert not any(o.__class__.__name__ == "AgentSkill" for o in db.added)

    def test_install_agent_error_rolls_back(self):
        class BoomSession(FakeSession):
            def flush(self):
                raise RuntimeError("flush failed")

        db = BoomSession()
        service = AgentMarketplaceService(db=db, saas_client=Mock())
        service.saas_client.get_agent_template_sync.return_value = {"name": "x", "description": ""}
        with patch("core.agent_marketplace_service.MarketplaceUsageTracker.track_usage"):
            result = service.install_agent("t1", "tenant-1", "user-1")
        assert result["success"] is False
        assert result["error"] == "flush failed"
        assert db.rolled_back is True


class TestMarketplaceUninstall:
    def test_uninstall_agent_not_installed(self):
        db = FakeSession()
        service = AgentMarketplaceService(db=db, saas_client=Mock())
        result = service.uninstall_agent("tenant-1", "agent-1")
        assert result == {"success": False, "error": "Agent was not installed from marketplace"}

    def test_uninstall_agent_success(self):
        db = FakeSession()
        installation = SimpleNamespace(template_id="t1", tenant_id="tenant-1",
                                       instantiated_agent_id="agent-1")
        agent = SimpleNamespace(id="agent-1")
        db._queries["AgentInstallation"] = FakeQuery([installation])
        db._queries["OperationErrorResolution"] = FakeQuery([1, 2])
        db._queries["AgentSkill"] = FakeQuery([1])
        db._queries["AgentRegistry"] = FakeQuery([agent])
        service = AgentMarketplaceService(db=db, saas_client=Mock())
        result = service.uninstall_agent("tenant-1", "agent-1")
        assert result == {"success": True, "message": "Agent uninstalled successfully"}
        assert db.deleted == [installation, agent]
        assert db.committed is True

    def test_uninstall_agent_no_agent_record(self):
        db = FakeSession()
        installation = SimpleNamespace(template_id="t1", tenant_id="tenant-1",
                                       instantiated_agent_id="agent-1")
        db._queries["AgentInstallation"] = FakeQuery([installation])
        service = AgentMarketplaceService(db=db, saas_client=Mock())
        result = service.uninstall_agent("tenant-1", "agent-1")
        assert result["success"] is True
        assert db.deleted == [installation]

    def test_uninstall_agent_error_rolls_back(self):
        class BoomSession(FakeSession):
            def commit(self):
                raise RuntimeError("commit failed")

        db = BoomSession()
        installation = SimpleNamespace(template_id="t1", tenant_id="tenant-1",
                                       instantiated_agent_id="agent-1")
        db._queries["AgentInstallation"] = FakeQuery([installation])
        service = AgentMarketplaceService(db=db, saas_client=Mock())
        result = service.uninstall_agent("tenant-1", "agent-1")
        assert result["success"] is False
        assert result["error"] == "commit failed"
        assert db.rolled_back is True


# ---------------------------------------------------------------------------
# 2. blueprint_healer
# ---------------------------------------------------------------------------


class TestBlueprintHealer:
    @pytest.fixture
    def healer(self):
        return BlueprintHealer(db=Mock(), llm_service=Mock())

    @pytest.fixture
    def blueprint(self):
        return {"nodes": [{"id": "n1"}], "name": "bp"}

    @pytest.mark.asyncio
    async def test_heal_blueprint_success_with_fence(self, healer, blueprint):
        healer.llm.generate_response = AsyncMock(
            return_value='```json\n[{"id": "n2", "name": "fixed"}]\n```'
        )
        healed = await healer.heal_blueprint(blueprint, "n1", "timeout")
        assert healed["nodes"] == [{"id": "n2", "name": "fixed"}]
        assert healed["status"] == "healed"
        assert "n1" in healed["healing_notes"]
        assert healed["name"] == "bp"

    @pytest.mark.asyncio
    async def test_heal_blueprint_success_plain_json(self, healer, blueprint):
        healer.llm.generate_response = AsyncMock(return_value='[{"id": "n2"}]')
        healed = await healer.heal_blueprint(blueprint, "n1", "err")
        assert healed["nodes"] == [{"id": "n2"}]
        assert healed["status"] == "healed"

    @pytest.mark.asyncio
    async def test_heal_blueprint_empty_content_returns_original(self, healer, blueprint):
        healer.llm.generate_response = AsyncMock(return_value="")
        healed = await healer.heal_blueprint(blueprint, "n1", "err")
        assert healed is blueprint

    @pytest.mark.asyncio
    async def test_heal_blueprint_invalid_json_returns_original(self, healer, blueprint):
        healer.llm.generate_response = AsyncMock(return_value="not json at all")
        healed = await healer.heal_blueprint(blueprint, "n1", "err")
        assert healed is blueprint

    @pytest.mark.asyncio
    async def test_heal_blueprint_llm_raises_returns_original(self, healer, blueprint):
        healer.llm.generate_response = AsyncMock(side_effect=RuntimeError("llm down"))
        healed = await healer.heal_blueprint(blueprint, "n1", "err")
        assert healed is blueprint

    def test_queen_property(self, healer):
        with patch("core.service_factory.ServiceFactory.get_queen_agent", return_value="QUEEN") as m:
            assert healer.queen == "QUEEN"
        m.assert_called_once_with(healer.db)

    @pytest.mark.asyncio
    async def test_summarize_healing_as_directive_success(self, healer):
        healer.llm.generate_response = AsyncMock(return_value="Always add a search node.")
        directive = await healer.summarize_healing_as_directive(
            {"name": "n1", "type": "tool"}, [{"id": "n2"}], "boom"
        )
        assert directive == "Always add a search node."

    @pytest.mark.asyncio
    async def test_summarize_healing_as_directive_empty_fallback(self, healer):
        healer.llm.generate_response = AsyncMock(return_value="")
        directive = await healer.summarize_healing_as_directive({"name": "n1"}, [], "e")
        assert directive == "Improve architectural robustness for the failing node type."

    @pytest.mark.asyncio
    async def test_summarize_healing_as_directive_exception_fallback(self, healer):
        healer.llm.generate_response = AsyncMock(side_effect=RuntimeError("down"))
        directive = await healer.summarize_healing_as_directive({"name": "n1"}, [], "e")
        assert directive == "Refine dependencies for failed node types."


# ---------------------------------------------------------------------------
# 3. budget_guardrail
# ---------------------------------------------------------------------------


def _project(actual_burn=0.0, budget_amount=1000.0, block_pct=None, warn_pct=None):
    return SimpleNamespace(
        id="p1",
        budget_amount=budget_amount,
        actual_burn=actual_burn,
        budget_status=BudgetStatus.ON_TRACK,
        block_threshold_pct=block_pct,
        warn_threshold_pct=warn_pct,
    )


def _task(assigned_to=None, actual_hours=0.0):
    return SimpleNamespace(assigned_to=assigned_to, actual_hours=actual_hours)


class TestBudgetGuardrailBurn:
    def test_calculate_project_burn_with_injected_session(self):
        db = FakeSession()
        db.register(ProjectTask, FakeQuery([]))
        db.register(Project, FakeQuery([_project()]))
        db.register_fn(func.sum(Transaction.amount), lambda: Decimal("12.50"))
        db.register_fn(func.sum(Bill.amount), lambda: None)
        service = BudgetGuardrailService(db_session=db)
        result = asyncio.run(service.calculate_project_burn("p1"))
        assert result["project_id"] == "p1"
        assert result["labor_burn"] == 0.0
        assert result["expense_burn"] == 12.5
        assert result["total_burn"] == 12.5
        assert result["status"] == "on_track"
        assert db.committed is True
        assert db.closed is False

    def test_calculate_project_burn_owns_session(self):
        db = FakeSession()
        db.register(ProjectTask, FakeQuery([]))
        db.register(Project, FakeQuery([_project()]))
        db.register_fn(func.sum(Transaction.amount), lambda: Decimal("1.5"))
        db.register_fn(func.sum(Bill.amount), lambda: Decimal("2.5"))
        with patch("core.budget_guardrail.SessionLocal", return_value=db):
            service = BudgetGuardrailService(db_session=None)
            result = asyncio.run(service.calculate_project_burn("p1"))
        assert result["status"] == "on_track"
        assert result["total_burn"] == 4.0
        assert db.closed is True

    def test_calculate_project_burn_no_project(self):
        db = FakeSession()
        db.register(ProjectTask, FakeQuery([]))
        db.register(Project, FakeQuery([]))
        service = BudgetGuardrailService(db_session=db)
        result = asyncio.run(service.calculate_project_burn("missing"))
        assert result["status"] == "unknown"
        assert db.committed is False

    def test_labor_burn_rate_matrix(self):
        tasks = [
            _task(assigned_to="u1", actual_hours=2),   # user with rate 100 -> 200
            _task(assigned_to="missing", actual_hours=3),  # user not found -> 50*3
            _task(assigned_to="u3", actual_hours=4),   # user w/o attr -> 50*4
            _task(assigned_to="u4", actual_hours=None),  # user with rate None -> 0
            _task(assigned_to=None, actual_hours=5),   # no assignee -> 50*5
        ]
        users = [
            SimpleNamespace(id="u1", hourly_cost_rate=100.0),
            None,
            SimpleNamespace(id="u3"),
            SimpleNamespace(id="u4", hourly_cost_rate=None),
        ]
        db = FakeSession()
        db.register(ProjectTask, FakeQuery(tasks))
        db.register_fn(User, lambda: users.pop(0) if users else None)
        service = BudgetGuardrailService(db_session=db)
        total = service._calculate_labor_burn("p1", db)
        assert total == 200 + 150 + 200 + 0 + 250

    def test_expense_burn_transaction_only(self):
        db = FakeSession()
        db.register_fn(func.sum(Transaction.amount), lambda: Decimal("12.50"))
        service = BudgetGuardrailService(db_session=db)
        assert service._calculate_expense_burn("p1", db) == 12.5

    def test_expense_burn_both_sources(self):
        db = FakeSession()
        db.register_fn(func.sum(Transaction.amount), lambda: Decimal("2.50"))
        db.register_fn(func.sum(Bill.amount), lambda: Decimal("3.00"))
        service = BudgetGuardrailService(db_session=db)
        assert service._calculate_expense_burn("p1", db) == 5.5

    def test_expense_burn_both_none(self):
        db = FakeSession()
        service = BudgetGuardrailService(db_session=db)
        assert service._calculate_expense_burn("p1", db) == 0.0

    def test_expense_burn_only_bill(self):
        db = FakeSession()
        db.register_fn(func.sum(Bill.amount), lambda: Decimal("7.25"))
        service = BudgetGuardrailService(db_session=db)
        assert service._calculate_expense_burn("p1", db) == 7.25


class TestBudgetGuardrailStatus:
    @pytest.fixture
    def service(self):
        return BudgetGuardrailService(db_session=None)

    def test_update_status_no_budget(self, service):
        project = _project(budget_amount=None, actual_burn=999.0)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.ON_TRACK

    def test_update_status_zero_budget(self, service):
        project = _project(budget_amount=0, actual_burn=10.0)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.ON_TRACK

    def test_update_status_over_budget(self, service):
        project = _project(budget_amount=100, actual_burn=100.0)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.OVER_BUDGET

    def test_update_status_at_risk(self, service):
        project = _project(budget_amount=100, actual_burn=85.0)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.AT_RISK

    def test_update_status_on_track(self, service):
        project = _project(budget_amount=100, actual_burn=50.0)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.ON_TRACK

    def test_update_status_custom_thresholds(self, service):
        project = _project(budget_amount=100, actual_burn=75.0, block_pct=70, warn_pct=50)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.OVER_BUDGET

        project = _project(budget_amount=100, actual_burn=60.0, block_pct=70, warn_pct=50)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.AT_RISK

        project = _project(budget_amount=100, actual_burn=40.0, block_pct=70, warn_pct=50)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.ON_TRACK

    def test_update_status_default_thresholds(self, service):
        project = _project(budget_amount=100, actual_burn=100.0, block_pct=None, warn_pct=None)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.OVER_BUDGET

        project = _project(budget_amount=100, actual_burn=85.0, block_pct=None, warn_pct=None)
        service._update_status(project)
        assert project.budget_status == BudgetStatus.AT_RISK


# ---------------------------------------------------------------------------
# 4. bulk_operations_processor
# ---------------------------------------------------------------------------


class TestBulkJobCoverage:
    def test_progress_percentage_zero_when_no_items(self):
        op = _bulk_op(items=[])
        job = _job(op)
        assert job.total_items == 0
        assert job.progress_percentage == 0.0

    def test_progress_percentage_calculated(self):
        op = _bulk_op(items=[{"a": 1}, {"b": 2}])
        job = _job(op)
        job.processed_items = 1
        assert job.progress_percentage == 50.0

    def test_progress_percentage_setter_is_noop(self):
        op = _bulk_op(items=[{"a": 1}])
        job = _job(op)
        job.progress_percentage = 42.0
        assert job.progress_percentage == 0.0


class TestQueueProcessing:
    @pytest.fixture
    def processor(self, tmp_path):
        p = IntegrationBulkProcessor()
        p._job_results_dir = tmp_path
        return p

    @pytest.mark.asyncio
    async def test_get_job_status_found(self, processor):
        job = _job(_bulk_op())
        processor.active_jobs["j1"] = job
        assert await processor.get_job_status("j1") is job

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, processor):
        assert await processor.get_job_status("nope") is None

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, processor):
        job = _job(_bulk_op())
        processor.active_jobs["j1"] = job
        assert await processor.cancel_job("j1") is True
        assert job.status == OperationStatus.CANCELLED
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, processor):
        job = _job(_bulk_op(), status=OperationStatus.RUNNING)
        processor.active_jobs["j1"] = job
        assert await processor.cancel_job("j1") is True
        assert job.status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(self, processor):
        job = _job(_bulk_op(), status=OperationStatus.COMPLETED)
        processor.active_jobs["j1"] = job
        assert await processor.cancel_job("j1") is False

    @pytest.mark.asyncio
    async def test_cancel_unknown_job_fails(self, processor):
        assert await processor.cancel_job("nope") is False

    @pytest.mark.asyncio
    async def test_submit_bulk_job_success(self, processor):
        with patch("asyncio.create_task") as mock_ct:
            job_id = await processor.submit_bulk_job(_bulk_op(items=[{"a": 1}]))
        assert job_id in processor.active_jobs
        assert job_id in processor.job_queue
        mock_ct.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_bulk_job_unique_ids(self, processor):
        with patch("asyncio.create_task"):
            id1 = await processor.submit_bulk_job(_bulk_op(items=[{"a": 1}]))
            id2 = await processor.submit_bulk_job(_bulk_op(items=[{"a": 1}]))
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_process_queue_starts_job(self, processor):
        job = _job(_bulk_op(integration_id="notion", items=[{"a": 1}]))
        processor.active_jobs["j1"] = job
        processor.job_queue.append("j1")
        with patch("asyncio.create_task") as mock_ct:
            await processor._process_queue()
        mock_ct.assert_called_once()
        assert processor.job_queue == []

    @pytest.mark.asyncio
    async def test_process_queue_concurrency_limit(self, processor):
        processor.max_concurrent_jobs = 0
        running = _job(_bulk_op(), job_id="running", status=OperationStatus.RUNNING)
        processor.active_jobs["running"] = running
        queued = _job(_bulk_op(), job_id="queued")
        processor.active_jobs["queued"] = queued
        processor.job_queue.append("queued")

        async def _drain(delay):
            processor.job_queue.pop(0)

        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=_drain) as mock_sleep:
            with patch("asyncio.create_task"):
                await processor._process_queue()
        mock_sleep.assert_awaited_once()


class TestProcessJob:
    @pytest.fixture
    def processor(self, tmp_path):
        p = IntegrationBulkProcessor()
        p._job_results_dir = tmp_path
        return p

    @pytest.mark.asyncio
    async def test_process_job_completed(self, processor, tmp_path):
        operation = _bulk_op(integration_id="airtable", items=[{"id": i} for i in range(10)], batch_size=3)
        calls = []
        async def callback(job):
            calls.append(job.job_id)
        operation.progress_callback = callback
        job = _job(operation)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await processor._process_job(job)
        assert job.status == OperationStatus.COMPLETED
        assert job.successful_items == 10
        assert job.failed_items == 0
        assert job.started_at is not None
        assert job.estimated_completion is not None
        assert len(calls) == 4
        assert (tmp_path / "job-1_results.json").exists()

    @pytest.mark.asyncio
    async def test_process_job_callback_raises(self, processor):
        operation = _bulk_op(integration_id="notion", items=[{"a": 1}, {"b": 2}], batch_size=1)
        async def callback(job):
            raise RuntimeError("callback blew up")
        operation.progress_callback = callback
        job = _job(operation)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await processor._process_job(job)
        assert job.status == OperationStatus.COMPLETED
        assert job.successful_items == 2

    @pytest.mark.asyncio
    async def test_process_job_partial_success(self, processor):
        async def mixed(items, operation):
            return [{"success": i % 2 == 0, "item": item} for i, item in enumerate(items)]
        processor.integration_processors["test"] = mixed
        job = _job(_bulk_op(integration_id="test", items=[{"i": x} for x in range(4)]))
        await processor._process_job(job)
        assert job.status == OperationStatus.PARTIAL_SUCCESS
        assert job.successful_items == 2
        assert job.failed_items == 2

    @pytest.mark.asyncio
    async def test_process_job_all_failed(self, processor):
        async def fail_all(items, operation):
            return [{"success": False, "error": "nope", "item": item} for item in items]
        processor.integration_processors["test"] = fail_all
        job = _job(_bulk_op(integration_id="test", items=[{"i": 1}]))
        await processor._process_job(job)
        assert job.status == OperationStatus.FAILED
        assert len(job.errors) == 1

    @pytest.mark.asyncio
    async def test_process_job_cancelled_mid_batches(self, processor):
        async def cancelling(items, operation):
            job.status = OperationStatus.CANCELLED
            return [{"success": True, "item": item} for item in items]
        processor.integration_processors["test"] = cancelling
        job = _job(_bulk_op(integration_id="test", items=[{"i": x} for x in range(4)], batch_size=1))
        await processor._process_job(job)
        assert job.status == OperationStatus.CANCELLED
        assert job.processed_items == 1
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_process_job_cancelled_before_start(self, processor):
        job = _job(_bulk_op(integration_id="notion", items=[{"a": 1}]), status=OperationStatus.CANCELLED)
        await processor._process_job(job)
        assert job.status == OperationStatus.CANCELLED
        assert job.processed_items == 0

    @pytest.mark.asyncio
    async def test_process_job_unknown_integration(self, processor):
        job = _job(_bulk_op(integration_id="unknown", items=[{"a": 1}]))
        await processor._process_job(job)
        assert job.status == OperationStatus.FAILED
        assert job.errors[0]["type"] == "job_error"
        assert "No processor found" in job.errors[0]["error"]

    @pytest.mark.asyncio
    async def test_process_job_processor_raises(self, processor):
        async def boom(items, operation):
            raise ValueError("integration broke")
        processor.integration_processors["test"] = boom
        job = _job(_bulk_op(integration_id="test", items=[{"a": 1}]))
        await processor._process_job(job)
        assert job.status == OperationStatus.FAILED
        assert job.errors[0]["error"] == "integration broke"

    @pytest.mark.asyncio
    async def test_update_job_progress_stop_on_error(self, processor):
        operation = _bulk_op()
        operation.stop_on_error = True
        job = _job(operation, status=OperationStatus.RUNNING)
        await processor._update_job_progress(
            job,
            [{"success": True, "item": {"a": 1}}, {"success": False, "error": "fatal"}],
            current_batch=1,
            total_batches=1,
        )
        assert job.status == OperationStatus.FAILED
        assert job.failed_items == 1
        assert job.processed_items == 2

    @pytest.mark.asyncio
    async def test_prepare_items_transformation_error(self, processor):
        operation = _bulk_op()
        operation.mapping_id = "m-1"
        processor.data_mapper.transform_data = Mock(side_effect=ValueError("transform failed"))
        items = await processor._prepare_items(operation)
        assert items == operation.items

    @pytest.mark.asyncio
    async def test_prepare_items_validation_warnings(self, processor):
        operation = _bulk_op()
        operation.schema_id = "s-1"
        processor.data_mapper.validate_data = Mock(
            return_value={"valid": False, "warnings": ["field x missing"]}
        )
        items = await processor._prepare_items(operation)
        assert items == operation.items

    @pytest.mark.asyncio
    async def test_prepare_items_validation_error(self, processor):
        operation = _bulk_op()
        operation.schema_id = "s-1"
        processor.data_mapper.validate_data = Mock(side_effect=ValueError("validate failed"))
        items = await processor._prepare_items(operation)
        assert items == operation.items

    @pytest.mark.asyncio
    async def test_save_job_results_failure_logged(self, processor, tmp_path):
        processor._job_results_dir = tmp_path
        job = _job(_bulk_op())
        with patch.object(builtins, "open", side_effect=OSError("disk full")):
            await processor._save_job_results(job)
        assert (tmp_path / "job-1_results.json").exists() is False

    @pytest.mark.asyncio
    async def test_save_job_results_success(self, processor, tmp_path):
        job = _job(_bulk_op())
        job.status = OperationStatus.COMPLETED
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        await processor._save_job_results(job)
        data = json.loads((tmp_path / "job-1_results.json").read_text())
        assert data["job_id"] == "job-1"
        assert data["status"] == "completed"


class TestAsanaProcessorCoverage:
    @pytest.fixture
    def processor(self, tmp_path):
        p = IntegrationBulkProcessor()
        p._job_results_dir = tmp_path
        return p

    def _op(self, operation_type, items):
        op = _bulk_op(operation_type=operation_type, integration_id="asana", items=items)
        op.metadata = {"access_token": "tok"}
        return op

    @pytest.mark.asyncio
    async def test_no_token_fails_all_items(self, processor):
        op = self._op("create", [{"name": "T"}])
        op.metadata = {}
        with patch.dict("os.environ", {}, clear=True), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            results = await processor._process_asana_bulk(op.items, op)
        assert len(results) == 1
        assert results[0]["success"] is False
        assert results[0]["error"] == "Asana access token not configured"

    @pytest.mark.asyncio
    async def test_create_success(self, processor):
        op = self._op("create", [{"name": "T", "notes": "n", "projects": ["p"]}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.create_task = AsyncMock(return_value={"data": {"gid": "g-1"}})
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["id"] == "g-1"
        assert results[0]["result"]["created"] is True

    @pytest.mark.asyncio
    async def test_update_success(self, processor):
        op = self._op("update", [{"task_id": "t1", "updates": {"name": "x"}}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.update_task = AsyncMock(return_value={"data": {"gid": "t1"}})
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["updated"] is True

    @pytest.mark.asyncio
    async def test_delete_success(self, processor):
        op = self._op("delete", [{"task_id": "t1"}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.delete_task = AsyncMock(return_value={"data": {"gid": "t1"}})
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["deleted"] is True

    @pytest.mark.asyncio
    async def test_create_failure_no_data(self, processor):
        op = self._op("create", [{"name": "T"}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.create_task = AsyncMock(return_value={"errors": "denied"})
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert results[0]["error"] == "denied"

    @pytest.mark.asyncio
    async def test_update_missing_task_id(self, processor):
        op = self._op("update", [{"name": "T"}])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "Missing task_id" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_update_failure_no_data(self, processor):
        op = self._op("update", [{"task_id": "t1", "updates": {"name": "x"}}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.update_task = AsyncMock(return_value={})
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert results[0]["error"] == "Unknown error"

    @pytest.mark.asyncio
    async def test_delete_missing_task_id(self, processor):
        op = self._op("delete", [{"name": "T"}])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "Missing task_id" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_delete_failure_no_data(self, processor):
        op = self._op("delete", [{"task_id": "t1"}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.delete_task = AsyncMock(return_value={"errors": "gone"})
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert results[0]["error"] == "gone"

    @pytest.mark.asyncio
    async def test_complete_success(self, processor):
        op = self._op("complete", [{"task_id": "t1"}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.complete_task = AsyncMock(
                return_value={"data": {"gid": "t1", "completed": True}}
            )
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["completed"] is True
        mock_cls.return_value.complete_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_missing_task_id(self, processor):
        op = self._op("complete", [{"name": "T"}])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "Missing task_id" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_complete_failure_no_data(self, processor):
        op = self._op("complete", [{"task_id": "t1"}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.complete_task = AsyncMock(return_value={})
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_unsupported_operation(self, processor):
        op = self._op("upsert", [{"task_id": "t1"}])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "Unsupported operation" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_item_exception_caught(self, processor):
        op = self._op("create", [{"name": "T"}])
        with patch("integrations.asana_service.AsanaService") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_cls.return_value.create_task = AsyncMock(side_effect=RuntimeError("api down"))
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "api down" in results[0]["error"]


class TestOtherIntegrationCoverage:
    @pytest.fixture
    def processor(self, tmp_path):
        p = IntegrationBulkProcessor()
        p._job_results_dir = tmp_path
        return p

    @pytest.mark.asyncio
    async def test_jira_create_success(self, processor):
        op = _bulk_op("create", "jira", [{"summary": "issue"}])
        results = await processor._process_jira_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["key"].startswith("ATOM-")

    @pytest.mark.asyncio
    async def test_jira_update_success(self, processor):
        op = _bulk_op("update", "jira", [{"id": 1}])
        results = await processor._process_jira_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["updated"] is True

    @pytest.mark.asyncio
    async def test_jira_unsupported_operation(self, processor):
        op = _bulk_op("delete", "jira", [{"id": 1}])
        results = await processor._process_jira_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "Unsupported operation" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_jira_exception_caught(self, processor):
        op = _bulk_op("create", "jira", [{"id": 1}])
        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("net")):
            results = await processor._process_jira_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "net" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_salesforce_create_success(self, processor):
        op = _bulk_op("create", "salesforce", [{"firstName": "John"}])
        results = await processor._process_salesforce_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["id"].startswith("001")

    @pytest.mark.asyncio
    async def test_salesforce_update_success(self, processor):
        op = _bulk_op("update", "salesforce", [{"id": 1}])
        results = await processor._process_salesforce_bulk(op.items, op)
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_salesforce_unsupported_operation(self, processor):
        op = _bulk_op("delete", "salesforce", [{"id": 1}])
        results = await processor._process_salesforce_bulk(op.items, op)
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_salesforce_exception_caught(self, processor):
        op = _bulk_op("create", "salesforce", [{"id": 1}])
        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("net")):
            results = await processor._process_salesforce_bulk(op.items, op)
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_notion_success(self, processor):
        op = _bulk_op("create", "notion", [{"title": "P"}])
        results = await processor._process_notion_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["page_id"].startswith("notion_")

    @pytest.mark.asyncio
    async def test_notion_exception_caught(self, processor):
        op = _bulk_op("create", "notion", [{"title": "P"}])
        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("net")):
            results = await processor._process_notion_bulk(op.items, op)
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_airtable_exception_caught(self, processor):
        op = _bulk_op("create", "airtable", [{"Name": "R"}])
        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("net")):
            results = await processor._process_airtable_bulk(op.items, op)
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_hubspot_success(self, processor):
        op = _bulk_op("create", "hubspot", [{"email": "a@b.c"}])
        results = await processor._process_hubspot_bulk(op.items, op)
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_hubspot_exception_caught(self, processor):
        op = _bulk_op("create", "hubspot", [{"email": "a@b.c"}])
        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("net")):
            results = await processor._process_hubspot_bulk(op.items, op)
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_monday_success(self, processor):
        op = _bulk_op("create", "monday", [{"name": "Item"}])
        results = await processor._process_monday_bulk(op.items, op)
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_monday_exception_caught(self, processor):
        op = _bulk_op("create", "monday", [{"name": "Item"}])
        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("net")):
            results = await processor._process_monday_bulk(op.items, op)
        assert results[0]["success"] is False


class TestPerformanceStatsCoverage:
    @pytest.fixture
    def processor(self, tmp_path):
        p = IntegrationBulkProcessor()
        p._job_results_dir = tmp_path
        return p

    def test_stats_empty(self, processor):
        stats = processor.get_performance_stats()
        assert stats["completed_jobs"] == 0
        assert stats["success_rate"] == 0

    def test_stats_with_jobs(self, processor):
        started = datetime.now(timezone.utc)
        done = started + timedelta(seconds=10)
        op = _bulk_op(items=[{"a": 1}])
        job1 = _job(op, job_id="j1", status=OperationStatus.COMPLETED)
        job1.started_at = started
        job1.completed_at = done
        job1.total_items = 2
        job1.successful_items = 2
        job2 = _job(op, job_id="j2", status=OperationStatus.FAILED)
        job2.total_items = 2
        job2.successful_items = 0
        running = _job(op, job_id="j3", status=OperationStatus.RUNNING)
        processor.active_jobs.update({"j1": job1, "j2": job2, "j3": running})
        stats = processor.get_performance_stats()
        assert stats["total_jobs"] == 3
        assert stats["running_jobs"] == 1
        assert stats["completed_jobs"] == 2
        assert stats["average_processing_time"] == 5.0
        assert stats["total_items_processed"] == 4
        assert stats["success_rate"] == 50.0
        assert stats["queue_length"] == 0

    def test_stats_skips_job_without_started_at(self, processor):
        op = _bulk_op(items=[{"a": 1}])
        job = _job(op, job_id="j1", status=OperationStatus.COMPLETED)
        job.completed_at = datetime.now(timezone.utc)
        processor.active_jobs["j1"] = job
        stats = processor.get_performance_stats()
        assert stats["completed_jobs"] == 1
        assert stats["average_processing_time"] == 0.0


class TestGlobalProcessorCoverage:
    def test_singleton(self):
        with patch("core.bulk_operations_processor._bulk_processor", None):
            p1 = get_bulk_processor()
            p2 = get_bulk_processor()
        assert p1 is p2


# ---------------------------------------------------------------------------
# 5. chronological_integrity
# ---------------------------------------------------------------------------


def _audit(account_id, seq, ts, audit_id=None):
    return SimpleNamespace(
        account_id=account_id,
        sequence_number=seq,
        timestamp=ts,
        id=audit_id or f"{account_id}-{seq}",
    )


T0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)


class TestMonotonicity:
    def _validator(self, audits):
        db = FakeSession()
        db.register(FinancialAudit, FakeQuery(audits))
        return ChronologicalIntegrityValidator(db)

    def test_empty(self):
        result = self._validator([]).validate_monotonicity()
        assert result["is_monotonic"] is True
        assert result["total_entries"] == 0
        assert result["accounts_checked"] == 0

    def test_filters_applied(self):
        db = FakeSession()
        q = FakeQuery([])
        db.register(FinancialAudit, q)
        validator = ChronologicalIntegrityValidator(db)
        validator.validate_monotonicity(account_id="a1", start_time=T0, end_time=T0 + timedelta(hours=1))
        assert len(q.filter_calls) == 3

    def test_monotonic(self):
        audits = [
            _audit("a1", 1, T0),
            _audit("a1", 2, T0 + timedelta(seconds=1)),
            _audit("a2", 1, T0),
        ]
        result = self._validator(audits).validate_monotonicity()
        assert result["is_monotonic"] is True
        assert result["accounts_checked"] == 2

    def test_backward_jump_detected(self):
        audits = [
            _audit("a1", 1, T0),
            _audit("a1", 2, T0 + timedelta(seconds=5)),
            _audit("a1", 3, T0 + timedelta(seconds=2)),  # backward
        ]
        result = self._validator(audits).validate_monotonicity()
        assert result["is_monotonic"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["sequence_number"] == 3
        assert result["violations"][0]["violation_type"] == "backward_timestamp"


class TestGapDetection:
    def _validator(self, audits):
        db = FakeSession()
        db.register(FinancialAudit, FakeQuery(audits))
        return ChronologicalIntegrityValidator(db)

    def test_no_gaps(self):
        audits = [_audit("a1", 1, T0), _audit("a1", 2, T0 + timedelta(seconds=1))]
        result = self._validator(audits).detect_gaps()
        assert result["has_gaps"] is False

    def test_gap_found(self):
        audits = [_audit("a1", 1, T0), _audit("a1", 3, T0 + timedelta(seconds=1))]
        result = self._validator(audits).detect_gaps()
        assert result["has_gaps"] is True
        assert result["total_gaps"] == 1
        gap = result["gaps"][0]
        assert gap["expected_sequence"] == 2
        assert gap["actual_sequence"] == 3
        assert gap["gap_size"] == 1
        assert result["accounts_with_gaps"] == ["a1"]

    def test_sequence_none_skipped(self):
        audits = [
            SimpleNamespace(account_id="a1", sequence_number=None, timestamp=T0),
            SimpleNamespace(account_id="a1", sequence_number=None, timestamp=T0 + timedelta(seconds=1)),
        ]
        result = self._validator(audits).detect_gaps()
        assert result["has_gaps"] is False

    def test_filters(self):
        db = FakeSession()
        q = FakeQuery([])
        db.register(FinancialAudit, q)
        validator = ChronologicalIntegrityValidator(db)
        validator.detect_gaps(account_id="a1", start_time=T0, end_time=T0 + timedelta(hours=1))
        assert len(q.filter_calls) == 3


class TestOutOfOrder:
    def _validator(self, audits):
        db = FakeSession()
        db.register(FinancialAudit, FakeQuery(audits))
        return ChronologicalIntegrityValidator(db)

    def test_in_order(self):
        audits = [_audit("a1", 1, T0), _audit("a1", 2, T0 + timedelta(seconds=1))]
        result = self._validator(audits).detect_out_of_order()
        assert result["has_out_of_order"] is False

    def test_out_of_order_detected(self):
        audits = [
            _audit("a1", 1, T0),
            _audit("a1", 2, T0 - timedelta(seconds=5)),  # earlier timestamp for later seq
        ]
        result = self._validator(audits).detect_out_of_order()
        assert result["has_out_of_order"] is True
        entry = result["entries"][0]
        assert entry["sequence_number"] == 2
        assert entry["violation"] == "timestamp_before_previous_sequence"

    def test_multiple_accounts(self):
        audits = [
            _audit("a1", 1, T0),
            _audit("a2", 2, T0 - timedelta(minutes=1)),  # out of order vs a2 seq 1
            _audit("a2", 1, T0),
        ]
        result = self._validator(audits).detect_out_of_order()
        assert result["has_out_of_order"] is True
        assert len(result["entries"]) == 1
        assert result["entries"][0]["account_id"] == "a2"

    def test_no_sequence_numbers(self):
        audits = [
            SimpleNamespace(account_id="a1", sequence_number=None, timestamp=T0),
            SimpleNamespace(account_id="a1", sequence_number=None, timestamp=T0 + timedelta(seconds=1)),
        ]
        result = self._validator(audits).detect_out_of_order()
        assert result["has_out_of_order"] is False

    def test_account_filter(self):
        db = FakeSession()
        q = FakeQuery([])
        db.register(FinancialAudit, q)
        validator = ChronologicalIntegrityValidator(db)
        validator.detect_out_of_order(account_id="a1")
        assert len(q.filter_calls) == 1


class TestTimeGaps:
    def _validator(self, audits):
        db = FakeSession()
        db.register(FinancialAudit, FakeQuery(audits))
        return ChronologicalIntegrityValidator(db)

    def test_gap_detected(self):
        audits = [
            _audit("a1", 1, T0),
            _audit("a1", 2, T0 + timedelta(hours=2)),
        ]
        result = self._validator(audits).detect_time_gaps(threshold_seconds=3600)
        assert result["has_time_gaps"] is True
        assert result["time_gaps"][0]["gap_hours"] == 2.0
        assert result["total_gaps"] == 1

    def test_no_gap(self):
        audits = [_audit("a1", 1, T0), _audit("a1", 2, T0 + timedelta(minutes=30))]
        result = self._validator(audits).detect_time_gaps(threshold_seconds=3600)
        assert result["has_time_gaps"] is False

    def test_account_filter(self):
        db = FakeSession()
        q = FakeQuery([])
        db.register(FinancialAudit, q)
        validator = ChronologicalIntegrityValidator(db)
        validator.detect_time_gaps(account_id="a1")
        assert len(q.filter_calls) == 1


class TestIntegrityCombo:
    def test_valid(self):
        db = FakeSession()
        db.register(FinancialAudit, FakeQuery([]))
        result = ChronologicalIntegrityValidator(db).validate_integrity()
        assert result["is_valid"] is True
        assert result["monotonicity"]["is_monotonic"] is True
        assert "validated_at" in result

    def test_invalid_with_gap(self):
        audits = [_audit("a1", 1, T0), _audit("a1", 3, T0 + timedelta(seconds=1))]
        db = FakeSession()
        db.register(FinancialAudit, FakeQuery(audits))
        result = ChronologicalIntegrityValidator(db).validate_integrity(
            account_id="a1", start_time=T0, end_time=T0 + timedelta(hours=1),
            time_gap_threshold=60,
        )
        assert result["is_valid"] is False
        assert result["sequence_gaps"]["has_gaps"] is True


# ---------------------------------------------------------------------------
# 6. conflict_resolution_service
# ---------------------------------------------------------------------------


class TestConflictDetection:
    @pytest.fixture
    def service(self):
        return ConflictResolutionService(db=Mock())

    def test_version_conflict(self, service):
        assert service.detect_skill_conflict({"version": "1.0"}, {"version": "2.0"}) == "VERSION_MISMATCH"

    def test_content_conflict(self, service):
        local = {"version": "1.0", "code": "print(1)"}
        remote = {"version": "1.0", "code": "print(2)"}
        assert service.detect_skill_conflict(local, remote) == "CONTENT_MISMATCH"

    def test_dependency_conflict(self, service):
        local = {"version": "1.0", "code": "x", "python_packages": ["a"]}
        remote = {"version": "1.0", "code": "x", "python_packages": ["b"]}
        assert service.detect_skill_conflict(local, remote) == "DEPENDENCY_CONFLICT"

    def test_no_conflict(self, service):
        local = {"version": "1.0", "code": "x"}
        assert service.detect_skill_conflict(local, dict(local)) is None


class TestSeverity:
    @pytest.fixture
    def service(self):
        return ConflictResolutionService(db=Mock())

    def test_critical_code(self, service):
        assert service.calculate_severity({"code": "a"}, {"code": "b"}, "CONTENT_MISMATCH") == "CRITICAL"

    def test_critical_one_sided_field(self, service):
        assert service.calculate_severity({"code": "a"}, {}, "CONTENT_MISMATCH") == "CRITICAL"

    def test_high_version(self, service):
        assert service.calculate_severity({"version": "1"}, {"version": "2"}, "VERSION_MISMATCH") == "HIGH"

    def test_medium_parameters(self, service):
        assert service.calculate_severity({"parameters": {"a": 1}}, {"parameters": {"a": 2}}, "OTHER") == "MEDIUM"

    def test_low_description(self, service):
        assert service.calculate_severity({"description": "a"}, {"description": "b"}, "OTHER") == "LOW"


class TestComparators:
    @pytest.fixture
    def service(self):
        return ConflictResolutionService(db=Mock())

    def test_compare_versions_match(self, service):
        assert service.compare_versions({"version": "1.0"}, {"version": "1.0"}) is False

    def test_compare_versions_mismatch(self, service):
        assert service.compare_versions({"version": "1.0"}, {"version": "1.1"}) is True

    def test_compare_versions_none_defaults(self, service):
        assert service.compare_versions({"version": None}, {"version": None}) is False
        assert service.compare_versions({"version": None}, {}) is False
        assert service.compare_versions({}, {"version": "2.0"}) is True
        assert service.compare_versions({"version": 1}, {"version": "1"}) is False

    def test_compare_content_both_hashes(self, service):
        assert service.compare_content({"content_hash": "h1"}, {"content_hash": "h1"}) is False
        assert service.compare_content({"content_hash": "h1"}, {"content_hash": "h2"}) is True

    def test_compare_content_code_fallback(self, service):
        assert service.compare_content({"code": "a"}, {"code": "b"}) is True
        assert service.compare_content({"code": "  a  "}, {"code": "a"}) is False
        assert service.compare_content({"code": None}, {"code": "a"}) is True
        assert service.compare_content({}, {}) is False

    def test_compare_dependencies_match(self, service):
        local = {"python_packages": ["a", "b"], "npm_packages": ["x"]}
        remote = {"python_packages": ["b", "a"], "npm_packages": ["x"]}
        assert service.compare_dependencies(local, remote) is False

    def test_compare_dependencies_python_mismatch(self, service):
        local = {"python_packages": ["a"]}
        remote = {"python_packages": ["b"]}
        assert service.compare_dependencies(local, remote) is True

    def test_compare_dependencies_npm_mismatch(self, service):
        local = {"npm_packages": ["x"]}
        remote = {"npm_packages": ["y"]}
        assert service.compare_dependencies(local, remote) is True

    def test_compare_dependencies_non_list(self, service):
        local = {"python_packages": "a", "npm_packages": "x"}
        remote = {"python_packages": "b", "npm_packages": "x"}
        assert service.compare_dependencies(local, remote) is False
        assert service.compare_dependencies({}, {}) is False

    def test_calculate_content_hash(self, service):
        h1 = service.calculate_content_hash({"skill_id": "s1", "name": "n", "code": "c"})
        h2 = service.calculate_content_hash({"skill_id": "s1", "name": "n", "code": "c"})
        h3 = service.calculate_content_hash({"skill_id": "s1", "name": "n", "code": "DIFFERENT"})
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64


class TestConflictLogging:
    @pytest.fixture
    def db(self):
        return FakeSession()

    @pytest.fixture
    def service(self, db):
        return ConflictResolutionService(db=db)

    def test_log_conflict(self, service, db):
        conflict = service.log_conflict("s1", "VERSION_MISMATCH", "HIGH", {"a": 1}, {"b": 2})
        assert db.added == [conflict]
        assert db.committed is True
        assert conflict.tenant_id == "default"
        assert conflict.resolution_strategy is None

    def test_get_unresolved_conflicts(self, service, db):
        q = FakeQuery([SimpleNamespace(id=1)])
        db.register(ConflictLog, q)
        result = service.get_unresolved_conflicts(severity="HIGH", conflict_type="VERSION_MISMATCH", limit=5, offset=2)
        assert len(result) == 1
        assert len(q.filter_calls) == 3
        result = service.get_unresolved_conflicts()
        assert result == [SimpleNamespace(id=1)]

    def test_count_unresolved_conflicts(self, service, db):
        db.register(ConflictLog, FakeQuery([1, 2, 3]))
        assert service.count_unresolved_conflicts() == 3
        assert service.count_unresolved_conflicts(severity="LOW") == 3
        assert service.count_unresolved_conflicts(conflict_type="OTHER") == 3

    def test_get_conflict_by_id(self, service, db):
        found = SimpleNamespace(id=7)
        db.register(ConflictLog, FakeQuery([found]))
        assert service.get_conflict_by_id(7) == found

    def test_get_conflict_by_id_not_found(self):
        service = ConflictResolutionService(db=FakeSession())
        assert service.get_conflict_by_id(8) is None


class TestStrategies:
    @pytest.fixture
    def service(self):
        return ConflictResolutionService(db=Mock())

    def test_remote_wins(self, service):
        result = service.remote_wins({"a": 1}, {"b": 2})
        assert result == {"b": 2}
        assert result is not {"b": 2}

    def test_local_wins(self, service):
        result = service.local_wins({"a": 1}, {"b": 2})
        assert result == {"a": 1}

    def test_merge_automatic_and_critical_fields(self, service):
        local = {
            "skill_id": "s1",
            "description": "short",
            "tags": ["t"],
            "code": "local-code",
            "python_packages": ["a"],
            "npm_packages": [],
            "version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        remote = {
            "skill_id": "s1",
            "description": "a much longer remote description",
            "examples": ["e1"],
            "code": "remote-code",
            "python_packages": ["b", "a"],
            "npm_packages": ["x"],
            "version": "2.0",
            "updated_at": "2026-02-01T00:00:00Z",
        }
        merged = service.merge(local, remote)
        assert merged["description"] == "a much longer remote description"
        assert merged["examples"] == ["e1"]
        assert merged["code"] == "local-code"  # critical fields keep local
        assert merged["python_packages"] == ["a", "b"]
        assert merged["npm_packages"] == ["x"]
        assert merged["version"] == "1.0+merged+2.0"
        assert merged["updated_at"] == datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)

    def test_merge_keeps_local_description_when_longer(self, service):
        local = {"skill_id": "s1", "description": "local is longer than remote"}
        remote = {"skill_id": "s1", "description": "short"}
        merged = service.merge(local, remote)
        assert merged["description"] == "local is longer than remote"
        assert merged["version"] == "1.0.0+merged+1.0.0"
        assert "updated_at" not in merged

    def test_merge_skill_id_from_remote(self, service):
        merged = service.merge({}, {"skill_id": "remote-only"})
        assert merged["skill_id"] == "remote-only"

    def test_merge_updated_at_single_side(self, service):
        local = {"skill_id": "s1", "updated_at": "2026-01-01T00:00:00Z"}
        merged = service.merge(local, {})
        assert merged["updated_at"] == "2026-01-01T00:00:00Z"

    def test_manual_logs_conflict(self, service):
        service.db = FakeSession()
        result = service.manual({"a": 1}, {"b": 2}, "s1", "CONTENT_MISMATCH", "HIGH")
        assert result is None
        assert len(service.db.added) == 1
        assert service.db.added[0].skill_id == "s1"


class TestResolve:
    @pytest.fixture
    def db(self):
        return FakeSession()

    def _conflict(self, local=None, remote=None):
        return SimpleNamespace(
            local_data=local or {"skill_id": "s1", "version": "1.0"},
            remote_data=remote or {"skill_id": "s1", "version": "2.0"},
            resolution_strategy=None,
            resolved_data=None,
            resolved_at=None,
            resolved_by=None,
        )

    def test_resolve_not_found(self, db):
        service = ConflictResolutionService(db=db)
        assert service.resolve_conflict(99, "remote_wins", "admin") is None

    def test_resolve_remote_wins(self, db):
        conflict = self._conflict()
        db.register(ConflictLog, FakeQuery([conflict]))
        service = ConflictResolutionService(db=db)
        result = service.resolve_conflict(1, "remote_wins", "admin")
        assert result == conflict.remote_data
        assert conflict.resolution_strategy == "remote_wins"
        assert conflict.resolved_by == "admin"
        assert conflict.resolved_at is not None
        assert db.committed is True

    def test_resolve_local_wins(self, db):
        conflict = self._conflict()
        db.register(ConflictLog, FakeQuery([conflict]))
        service = ConflictResolutionService(db=db)
        assert service.resolve_conflict(1, "local_wins", "admin") == conflict.local_data

    def test_resolve_merge(self, db):
        conflict = self._conflict()
        db.register(ConflictLog, FakeQuery([conflict]))
        service = ConflictResolutionService(db=db)
        result = service.resolve_conflict(1, "merge", "admin")
        assert result["version"] == "1.0+merged+2.0"

    def test_resolve_manual_returns_none(self, db):
        conflict = self._conflict()
        db.register(ConflictLog, FakeQuery([conflict]))
        service = ConflictResolutionService(db=db)
        assert service.resolve_conflict(1, "manual", "admin") is None
        assert conflict.resolution_strategy is None


class TestAutoResolve:
    @pytest.fixture
    def service(self):
        return ConflictResolutionService(db=Mock())

    def test_no_conflict_returns_remote(self, service):
        local = {"version": "1.0", "code": "x"}
        remote = {"version": "1.0", "code": "x", "extra": True}
        result = service.auto_resolve_conflict(local, remote, "remote_wins")
        assert result == remote

    def test_remote_wins(self, service):
        local = {"version": "1.0"}
        remote = {"version": "2.0"}
        assert service.auto_resolve_conflict(local, remote, "remote_wins") == remote

    def test_local_wins(self, service):
        local = {"version": "1.0"}
        remote = {"version": "2.0"}
        assert service.auto_resolve_conflict(local, remote, "local_wins") == local

    def test_merge(self, service):
        local = {"skill_id": "s1", "version": "1.0"}
        remote = {"skill_id": "s1", "version": "2.0"}
        result = service.auto_resolve_conflict(local, remote, "merge")
        assert result["version"] == "1.0+merged+2.0"

    def test_manual_logs_and_returns_none(self, service):
        db = FakeSession()
        service.db = db
        local = {"skill_id": "s1", "version": "1.0"}
        remote = {"skill_id": "s1", "version": "2.0"}
        assert service.auto_resolve_conflict(local, remote, "manual") is None
        assert len(db.added) == 1

    def test_unknown_strategy(self, service):
        local = {"version": "1.0"}
        remote = {"version": "2.0"}
        assert service.auto_resolve_conflict(local, remote, "chaos") is None


# ---------------------------------------------------------------------------
# 7. alert_service
# ---------------------------------------------------------------------------


def _config(tenant_id="t1", connector_id="c1", error_rate=10.0, latency=None,
            channels=None, slack_channel=None, recipients=None):
    return SimpleNamespace(
        tenant_id=tenant_id,
        connector_id=connector_id,
        is_active=True,
        window_seconds=300,
        error_rate_threshold=error_rate,
        latency_threshold_ms=latency,
        notification_channels=channels or [],
        slack_channel_id=slack_channel,
        email_recipients=recipients or [],
    )


def _violation(severity=AlertSeverity.WARNING, actual=15.0, threshold=10.0):
    return AlertViolation(
        tenant_id="t1",
        connector_id="c1",
        metric_type="error_rate",
        actual_value=actual,
        threshold=threshold,
        severity=severity,
        timestamp=datetime.now(timezone.utc),
        window_start=datetime.now(timezone.utc) - timedelta(seconds=300),
        window_end=datetime.now(timezone.utc),
    )


def _metrics(successes=90, failures=10, p95=500.0):
    metrics = Mock()
    metrics._make_key.return_value = "k"
    metrics.success_counts = {"k": successes}
    metrics.failure_counts = {"k": failures}
    metrics.get_duration_percentiles.return_value = {"p95": p95}
    return metrics


class TestAlertServiceBasics:
    def test_enums(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertStatus.OK.value == "ok"
        assert AlertStatus.VIOLATED.value == "violated"
        assert AlertStatus.CLEARED.value == "cleared"

    def test_init_uses_stub_when_model_missing(self):
        # core.models has no AlertConfiguration -> ImportError -> stub fallback.
        service = AlertThresholdService(db_session=Mock())
        assert service.AlertConfiguration.__name__ == "_AlertConfigurationStub"

    def test_init_with_available_model(self):
        import core.models as models_mod
        fake_model = type("AlertConfiguration", (), {})
        with patch.object(models_mod, "AlertConfiguration", fake_model, create=True):
            service = AlertThresholdService(db_session=Mock())
        assert service.AlertConfiguration is fake_model


class TestErrorRateEvaluation:
    @pytest.fixture
    def service(self):
        return AlertThresholdService(db_session=Mock())

    def test_no_configuration(self):
        service = AlertThresholdService(db_session=FakeSession())
        assert service.evaluate_error_rate_threshold("t1", "c1") is None

    def test_violation_critical(self, service):
        config = _config(error_rate=10.0)
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(70, 30)):
            violation = service.evaluate_error_rate_threshold("t1", "c1", config)
        assert violation is not None
        assert violation.severity == AlertSeverity.CRITICAL
        assert violation.metric_type == "error_rate"
        assert violation.actual_value == 30.0

    def test_violation_warning(self, service):
        config = _config(error_rate=10.0)
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(89, 11)):
            violation = service.evaluate_error_rate_threshold("t1", "c1", config)
        assert violation.severity == AlertSeverity.WARNING

    def test_cleared_when_below_band(self, service):
        config = _config(error_rate=10.0)
        service._get_alert_state = Mock(return_value="violated")
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(98, 2)):
            violation = service.evaluate_error_rate_threshold("t1", "c1", config)
        assert violation is None

    def test_hysteresis_band_still_violated(self, service):
        config = _config(error_rate=10.0)
        service._get_alert_state = Mock(return_value="violated")
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(91, 9)):
            violation = service.evaluate_error_rate_threshold("t1", "c1", config)
        assert violation is not None
        assert violation.severity == AlertSeverity.WARNING

    def test_no_violation(self, service):
        config = _config(error_rate=10.0)
        service._get_alert_state = Mock(return_value="ok")
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(95, 5)):
            violation = service.evaluate_error_rate_threshold("t1", "c1", config)
        assert violation is None


class TestLatencyEvaluation:
    @pytest.fixture
    def service(self):
        return AlertThresholdService(db_session=Mock())

    def test_no_config(self):
        service = AlertThresholdService(db_session=FakeSession())
        assert service.evaluate_latency_threshold("t1", "c1") is None

    def test_no_threshold_configured(self, service):
        assert service.evaluate_latency_threshold("t1", "c1", _config(latency=None)) is None

    def test_violation(self, service):
        config = _config(latency=200.0)
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(p95=500.0)):
            violation = service.evaluate_latency_threshold("t1", "c1", config)
        assert violation is not None
        assert violation.metric_type == "latency_p95"
        assert violation.actual_value == 500.0
        assert violation.severity == AlertSeverity.WARNING

    def test_ok(self, service):
        config = _config(latency=200.0)
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(p95=100.0)):
            assert service.evaluate_latency_threshold("t1", "c1", config) is None


class TestEvaluateAll:
    def test_no_configs(self):
        service = AlertThresholdService(db_session=FakeSession())
        assert service.evaluate_all_thresholds() == []
        assert service.evaluate_all_thresholds("t1") == []

    def test_grouped_and_violated(self):
        db = FakeSession()
        service = AlertThresholdService(db_session=db)
        db.register(service.AlertConfiguration, FakeQuery([
            _config("t1", "c1", error_rate=10.0, latency=200.0),
            _config("t1", "c1", error_rate=5.0),  # duplicate key -> ignored
            _config("t2", "c2", error_rate=10.0, latency=100.0),
        ]))
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(70, 30, p95=500.0)):
            results = service.evaluate_all_thresholds()
        assert len(results) == 2
        by_connector = {r.connector_id: r for r in results}
        assert by_connector["c1"].status == AlertStatus.VIOLATED
        assert len(by_connector["c1"].violations) == 2
        assert by_connector["c2"].status == AlertStatus.VIOLATED
        assert len(by_connector["c2"].violations) == 2

    def test_tenant_filter_applied(self):
        db = FakeSession()
        service = AlertThresholdService(db_session=db)
        q = FakeQuery([_config("t1", "c1", error_rate=10.0)])
        db.register(service.AlertConfiguration, q)
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(95, 5)):
            service.evaluate_all_thresholds("t1")
        assert len(q.filter_calls) == 2  # is_active + tenant_id
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(95, 5)):
            service.evaluate_all_thresholds()
        assert len(q.filter_calls) == 3  # is_active only

    def test_ok_status(self):
        db = FakeSession()
        service = AlertThresholdService(db_session=db)
        db.register(service.AlertConfiguration, FakeQuery([_config("t1", "c1", error_rate=10.0, latency=200.0)]))
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(95, 5, p95=100.0)):
            results = service.evaluate_all_thresholds()
        assert len(results) == 1
        assert results[0].status == AlertStatus.OK
        assert results[0].violations == []

    def test_get_violations_for_tenant(self):
        db = FakeSession()
        service = AlertThresholdService(db_session=db)
        db.register(service.AlertConfiguration, FakeQuery([_config("t1", "c1", error_rate=10.0)]))
        with patch("core.integration_metrics.get_integration_metrics", return_value=_metrics(70, 30)):
            violations = service.get_violations_for_tenant("t1")
        assert len(violations) == 1
        assert isinstance(violations[0], AlertViolation)


class TestAlertStateHelpers:
    def test_calculate_error_rate_window_total_zero(self):
        service = AlertThresholdService(db_session=Mock())
        assert service._calculate_error_rate_in_window(_metrics(0, 0), "t1", "c1", T0) == 0.0

    def test_calculate_error_rate_window(self):
        service = AlertThresholdService(db_session=Mock())
        rate = service._calculate_error_rate_in_window(_metrics(75, 25), "t1", "c1", T0)
        assert rate == 25.0

    def test_get_alert_state_no_redis(self):
        service = AlertThresholdService(db_session=Mock(), redis_client=None)
        assert service._get_alert_state("t1", "c1", "error_rate") == "ok"

    def test_get_alert_state_with_redis(self):
        redis = Mock()
        redis.get.return_value = b"violated"
        service = AlertThresholdService(db_session=Mock(), redis_client=redis)
        assert service._get_alert_state("t1", "c1", "error_rate") == "violated"
        redis.get.return_value = None
        assert service._get_alert_state("t1", "c1", "error_rate") == "ok"

    def test_set_alert_state_no_redis(self):
        service = AlertThresholdService(db_session=Mock(), redis_client=None)
        service._set_alert_state("t1", "c1", "error_rate", "violated")

    def test_set_alert_state_with_redis(self):
        redis = Mock()
        service = AlertThresholdService(db_session=Mock(), redis_client=redis)
        service._set_alert_state("t1", "c1", "error_rate", "violated")
        redis.setex.assert_called_once_with("alert_state:t1:c1:error_rate", 3600, "violated")


class TestNotifications:
    @pytest.mark.asyncio
    async def test_send_notifications_no_channels(self):
        service = AlertThresholdService(db_session=Mock())
        assert await service.send_notifications(_violation(), _config()) == {}

    @pytest.mark.asyncio
    async def test_send_notifications_slack_and_email(self):
        service = AlertThresholdService(db_session=Mock())
        config = _config(channels=["slack", "email"], slack_channel="C1", recipients=["a@b.c"])
        with patch.object(service, "send_slack_notification", new_callable=AsyncMock, return_value=True), \
             patch.object(service, "send_email_notification", new_callable=AsyncMock, return_value=True):
            results = await service.send_notifications(_violation(), config)
        assert results == {"slack": True, "email": True}

    @pytest.mark.asyncio
    async def test_send_slack_no_token(self):
        service = AlertThresholdService(db_session=Mock())
        with patch("core.token_storage.token_storage") as mock_storage:
            mock_storage.get_token.return_value = None
            assert await service.send_slack_notification(_violation(), _config(slack_channel="C1")) is False

    @pytest.mark.asyncio
    async def test_send_slack_token_without_access_token(self):
        service = AlertThresholdService(db_session=Mock())
        with patch("core.token_storage.token_storage") as mock_storage:
            mock_storage.get_token.return_value = {"token": "x"}
            assert await service.send_slack_notification(_violation(), _config(slack_channel="C1")) is False

    @pytest.mark.asyncio
    async def test_send_slack_success(self):
        service = AlertThresholdService(db_session=Mock())
        with patch("core.token_storage.token_storage") as mock_storage, \
             patch("integrations.slack_enhanced_service.SlackEnhancedService") as mock_cls:
            mock_storage.get_token.return_value = {"access_token": "tok"}
            mock_cls.return_value.send_message = AsyncMock(return_value=True)
            assert await service.send_slack_notification(_violation(), _config(slack_channel="C1")) is True
            mock_cls.return_value.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_slack_exception(self):
        service = AlertThresholdService(db_session=Mock())
        with patch("core.token_storage.token_storage") as mock_storage, \
             patch("integrations.slack_enhanced_service.SlackEnhancedService") as mock_cls:
            mock_storage.get_token.return_value = {"access_token": "tok"}
            mock_cls.side_effect = RuntimeError("slack down")
            assert await service.send_slack_notification(_violation(), _config(slack_channel="C1")) is False

    @pytest.mark.asyncio
    async def test_send_email_no_recipients(self):
        service = AlertThresholdService(db_session=Mock())
        assert await service.send_email_notification(_violation(), _config(recipients=[])) is False

    @pytest.mark.asyncio
    async def test_send_email_partial_success(self):
        service = AlertThresholdService(db_session=Mock())
        with patch("integrations.email_routes.EmailService") as mock_cls:
            mock_cls.return_value.send_email = AsyncMock(side_effect=[True, False])
            assert await service.send_email_notification(
                _violation(), _config(recipients=["a@b.c", "c@d.e"])
            ) is True

    @pytest.mark.asyncio
    async def test_send_email_all_failed(self):
        service = AlertThresholdService(db_session=Mock())
        with patch("integrations.email_routes.EmailService") as mock_cls:
            mock_cls.return_value.send_email = AsyncMock(return_value=False)
            assert await service.send_email_notification(
                _violation(), _config(recipients=["a@b.c"])
            ) is False

    @pytest.mark.asyncio
    async def test_send_email_exception(self):
        service = AlertThresholdService(db_session=Mock())
        with patch("integrations.email_routes.EmailService", side_effect=RuntimeError("mail down")):
            assert await service.send_email_notification(
                _violation(), _config(recipients=["a@b.c"])
            ) is False

    @pytest.mark.asyncio
    async def test_send_alert_cleared_no_channels(self):
        service = AlertThresholdService(db_session=Mock())
        assert await service.send_alert_cleared_notification("t1", "c1", "error_rate", _config()) is False

    @pytest.mark.asyncio
    async def test_send_alert_cleared_slack_and_email(self):
        service = AlertThresholdService(db_session=Mock())
        config = _config(channels=["slack", "email"], slack_channel="C1", recipients=["a@b.c"])
        with patch("core.token_storage.token_storage") as mock_storage, \
             patch("integrations.slack_enhanced_service.SlackEnhancedService") as mock_slack, \
             patch("integrations.email_routes.EmailService") as mock_email:
            mock_storage.get_token.return_value = {"access_token": "tok"}
            mock_slack.return_value.send_message = AsyncMock(return_value=True)
            mock_email.return_value.send_email = AsyncMock(side_effect=[True, False])
            assert await service.send_alert_cleared_notification("t1", "c1", "error_rate", config) is True

    @pytest.mark.asyncio
    async def test_send_alert_cleared_all_failed(self):
        service = AlertThresholdService(db_session=Mock())
        config = _config(channels=["slack", "email"], slack_channel="C1", recipients=["a@b.c"])
        with patch("core.token_storage.token_storage") as mock_storage, \
             patch("integrations.slack_enhanced_service.SlackEnhancedService") as mock_slack, \
             patch("integrations.email_routes.EmailService") as mock_email:
            mock_storage.get_token.return_value = {"access_token": "tok"}
            mock_slack.return_value.send_message = AsyncMock(side_effect=RuntimeError("boom"))
            mock_email.return_value.send_email = AsyncMock(return_value=False)
            assert await service.send_alert_cleared_notification("t1", "c1", "error_rate", config) is False

    @pytest.mark.asyncio
    async def test_send_alert_cleared_exception(self):
        service = AlertThresholdService(db_session=Mock())
        config = _config(channels=["slack"], slack_channel="C1")
        with patch("core.token_storage.token_storage") as mock_storage:
            mock_storage.get_token.side_effect = RuntimeError("storage down")
            assert await service.send_alert_cleared_notification("t1", "c1", "error_rate", config) is False


class TestAlertFormatting:
    @pytest.fixture
    def service(self):
        return AlertThresholdService(db_session=Mock())

    def test_emoji_for_severity(self, service):
        assert service._get_emoji_for_severity(AlertSeverity.INFO) == ":information_source:"
        assert service._get_emoji_for_severity(AlertSeverity.WARNING) == ":warning:"
        assert service._get_emoji_for_severity(AlertSeverity.CRITICAL) == ":rotating_light:"
        assert service._get_emoji_for_severity(None) == ":warning:"

    def test_format_slack_message(self, service):
        msg = service._format_slack_message(_violation(AlertSeverity.CRITICAL, 30.0, 10.0), _config())
        assert "Alert Violation Detected" in msg
        assert "error_rate" in msg
        assert "CRITICAL" in msg
        assert "30.00" in msg

    def test_format_email_subject(self, service):
        assert "🚨" in service._format_email_subject(_violation(AlertSeverity.CRITICAL))
        assert "⚠️" in service._format_email_subject(_violation(AlertSeverity.WARNING))
        assert "Alert:" in service._format_email_subject(_violation(AlertSeverity.INFO))
        assert "Alert:" in service._format_email_subject(_violation(None))

    def test_format_email_html(self, service):
        html = service._format_email_html(_violation(AlertSeverity.WARNING), _config())
        assert "c1" in html
        assert "#ffc107" in html
        assert "automated alert" in html


class TestClearedAlertsCheck:
    @pytest.mark.asyncio
    async def test_no_redis(self):
        service = AlertThresholdService(db_session=Mock(), redis_client=None)
        assert await service.check_and_send_cleared_alerts("t1", "c1") is None

    @pytest.mark.asyncio
    async def test_cleared_state_sends_and_resets(self):
        db = FakeSession()
        service = AlertThresholdService(db_session=db)
        config = _config()
        db.register(service.AlertConfiguration, FakeQuery([config]))
        redis = Mock()
        redis.get.side_effect = lambda key: b"cleared" if key.endswith("error_rate") else b"ok"
        service.redis = redis
        with patch.object(service, "send_alert_cleared_notification", new_callable=AsyncMock) as mock_send:
            await service.check_and_send_cleared_alerts("t1", "c1")
        mock_send.assert_awaited_once_with("t1", "c1", "error_rate", config)
        assert redis.setex.call_count == 1

    @pytest.mark.asyncio
    async def test_cleared_state_no_config(self):
        redis = Mock()
        redis.get.return_value = b"cleared"
        service = AlertThresholdService(db_session=FakeSession(), redis_client=redis)
        with patch.object(service, "send_alert_cleared_notification", new_callable=AsyncMock) as mock_send:
            await service.check_and_send_cleared_alerts("t1", "c1")
        mock_send.assert_not_awaited()
        assert redis.setex.call_count == 2


# ---------------------------------------------------------------------------
# 8. admin_bootstrap
# ---------------------------------------------------------------------------


class TestWritePasswordFile:
    def test_writes_file_with_0600_env_path(self, tmp_path, monkeypatch):
        target = tmp_path / "sub" / "pw.txt"
        monkeypatch.setenv("ATOM_BOOTSTRAP_PASSWORD_FILE", str(target))
        path = _write_password_to_secure_file("s3cret")
        assert path == str(target)
        assert target.read_text() == "s3cret"
        assert (target.stat().st_mode & 0o777) == 0o600

    def test_default_path_anchored_to_backend(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ATOM_BOOTSTRAP_PASSWORD_FILE", raising=False)
        import core.admin_bootstrap as mod
        monkeypatch.setattr(mod, "__file__", str(tmp_path / "pkg" / "main_api_app.py"))
        path = _write_password_to_secure_file("pw2")
        expected = str(tmp_path / "logs" / "bootstrap_admin_password.txt")
        assert path == expected
        assert Path(expected).read_text() == "pw2"
        assert (Path(expected).stat().st_mode & 0o777) == 0o600

    def test_oserror_returns_empty(self, monkeypatch):
        import core.admin_bootstrap as mod
        monkeypatch.delenv("ATOM_BOOTSTRAP_PASSWORD_FILE", raising=False)
        monkeypatch.setattr(mod, "os", MagicMock(open=Mock(side_effect=OSError("nope"))))
        monkeypatch.setattr(mod.os, "getenv", lambda k, d=None: d)
        assert _write_password_to_secure_file("pw") == ""


class TestEnsureAdminUser:
    @pytest.fixture
    def fake_db(self):
        return FakeSession()

    @contextlib.contextmanager
    def _patch_db(self, db):
        with patch("core.admin_bootstrap.get_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = db
            mock_ctx.return_value.__exit__.return_value = False
            yield

    def test_user_exists_no_env_keeps_password(self, fake_db):
        user = SimpleNamespace(hashed_password="old", status="active", role="user")
        fake_db.register(User, FakeQuery([user]))
        with self._patch_db(fake_db), \
             patch("core.admin_bootstrap.os.getenv", return_value=None), \
             patch("core.admin_bootstrap.ensure_default_tenant_and_workspace") as mock_tenant, \
             patch("core.admin_bootstrap.ensure_demo_agent") as mock_demo:
            ensure_admin_user()
        assert user.hashed_password == "old"
        assert fake_db.committed is False
        mock_tenant.assert_called_once()
        mock_demo.assert_called_once()

    def test_user_exists_with_env_resets_password(self, fake_db):
        user = SimpleNamespace(hashed_password="old", status="active", role="user")
        fake_db.register(User, FakeQuery([user]))
        with self._patch_db(fake_db), \
             patch("core.admin_bootstrap.os.getenv", return_value="NewPass123"), \
             patch("core.admin_bootstrap.get_password_hash", return_value="HASHED"), \
             patch("core.admin_bootstrap.ensure_default_tenant_and_workspace"), \
             patch("core.admin_bootstrap.ensure_demo_agent"):
            ensure_admin_user()
        assert user.hashed_password == "HASHED"
        assert user.status == UserStatus.ACTIVE
        assert user.role == "workspace_admin"
        assert fake_db.committed is True

    def test_new_user_created_with_generated_password(self, fake_db, monkeypatch):
        with self._patch_db(fake_db), \
             patch("core.admin_bootstrap.os.getenv", return_value=None), \
             patch("core.admin_bootstrap.secrets.token_urlsafe", return_value="GenTok123"), \
             patch("core.admin_bootstrap.get_password_hash", return_value="HASHED"), \
             patch("core.admin_bootstrap._write_password_to_secure_file", return_value="/tmp/pw.txt"), \
             patch("core.admin_bootstrap.ensure_default_tenant_and_workspace"), \
             patch("core.admin_bootstrap.ensure_demo_agent"):
            ensure_admin_user()
        user = fake_db.added[0]
        assert user.email == "admin@example.com"
        assert user.hashed_password == "HASHED"
        assert user.role == "workspace_admin"
        assert user.status.value == "active"
        assert fake_db.committed is True

    def test_new_user_with_env_password_skips_file(self, fake_db):
        with self._patch_db(fake_db), \
             patch("core.admin_bootstrap.os.getenv", return_value="EnvPass456"), \
             patch("core.admin_bootstrap.get_password_hash", return_value="HASHED"), \
             patch("core.admin_bootstrap._write_password_to_secure_file") as mock_file, \
             patch("core.admin_bootstrap.ensure_default_tenant_and_workspace"), \
             patch("core.admin_bootstrap.ensure_demo_agent"):
            ensure_admin_user()
        mock_file.assert_not_called()

    def test_exception_rolls_back(self, fake_db):
        class BoomSession(FakeSession):
            def commit(self):
                raise RuntimeError("commit failed")

        db = BoomSession()
        with self._patch_db(db), \
             patch("core.admin_bootstrap.os.getenv", return_value=None), \
             patch("core.admin_bootstrap.secrets.token_urlsafe", return_value="Tok"), \
             patch("core.admin_bootstrap.get_password_hash", return_value="H"), \
             patch("core.admin_bootstrap._write_password_to_secure_file"), \
             patch("core.admin_bootstrap.ensure_default_tenant_and_workspace"), \
             patch("core.admin_bootstrap.ensure_demo_agent"):
            ensure_admin_user()
        assert db.rolled_back is True
        assert db.closed is True


class TestEnsureTenantWorkspace:
    def _db(self):
        return FakeSession()

    def test_both_exist(self):
        db = self._db()
        tenant = SimpleNamespace(id="t")
        workspace = SimpleNamespace(id="w")
        db.register(Tenant, FakeQuery([tenant]))
        db.register(Workspace, FakeQuery([workspace]))
        ensure_default_tenant_and_workspace(db)
        assert db.committed is True
        assert not db.added

    def test_creates_tenant_and_workspace(self):
        db = self._db()
        ensure_default_tenant_and_workspace(db)
        tenant, workspace = db.added
        assert tenant.id == "default"
        assert tenant.edition == "personal"
        assert workspace.tenant_id == "default"
        assert workspace.id == "default"
        assert db.committed is True

    def test_workspace_missing_only(self):
        db = self._db()
        tenant = SimpleNamespace(id="default")
        db.register(Tenant, FakeQuery([tenant]))
        ensure_default_tenant_and_workspace(db)
        assert db.added[0].id == "default"
        assert len(db.added) == 1


class TestEnsureDemoAgent:
    def test_existing_agent_noop(self):
        db = FakeSession()
        existing = SimpleNamespace(name="Demo Assistant")
        db.register(AgentRegistry, FakeQuery([existing]))
        ensure_demo_agent(db)
        assert not db.added
        assert db.committed is False

    def test_creates_demo_agent(self):
        db = FakeSession()
        ensure_demo_agent(db)
        agent = db.added[0]
        assert agent.name == "Demo Assistant"
        assert agent.category == "system"
        assert agent.status == "intern"
        assert agent.confidence_score == 0.6
        assert agent.workspace_id == "default"
        assert agent.tenant_id == "default"
        assert agent.configuration["demo_agent"] is True
        assert db.committed is True
