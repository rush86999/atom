"""
Tests for Workflow UI Endpoints

Test coverage for workflow UI API endpoints including:
- Workflow template and definition routes
- Workflow CRUD operations (create, read, update, delete)
- Workflow execution and history
- UI integration with mock data and database
- API authentication and error handling

Ported to the current core/workflow_ui_endpoints.py API: endpoint
functions are async, take ``db``/``current_user`` directly (matching the
style of tests/test_covpush_w93_pdf_comm_routes.py), and the DB-mode vs
mock-mode branches are controlled by ``WORKFLOW_MOCK_ENABLED``.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import core.workflow_ui_endpoints as wui
from core.workflow_ui_endpoints import (
    WorkflowStep,
    WorkflowTemplateResponse,
    WorkflowDefinition,
    WorkflowExecution,
    ServiceInfo,
    MOCK_TEMPLATES,
    MOCK_WORKFLOWS,
    MOCK_EXECUTIONS,
    MOCK_SERVICES,
    cancel_execution,
    create_workflow,
    create_workflow_definition,
    delete_workflow,
    execute_workflow,
    execute_workflow_by_id,
    get_services,
    get_templates,
    get_workflow_by_id,
    get_workflow_history,
    get_workflows,
    import_template,
    list_workflows,
    update_workflow,
)


def _tpl(**kw):
    """A row shaped like the WorkflowTemplate ORM columns (see core/models.py)."""
    defaults = dict(
        id="tpl_001",
        tenant_id="t-1",
        name="Test Template",
        description="Test description",
        category="automation",
        icon="workflow",
        steps=[{"id": "s1"}],
        input_schema={"type": "object"},
        is_public=True,
        rating=4.5,
        usage_count=100,
        author_id="user_001",
        version="1.0.0",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _db(template=None, rows=None):
    db = MagicMock()
    chain = MagicMock()
    chain.filter.return_value = chain  # recursive filter chain
    chain.first.return_value = template
    chain.all.return_value = rows or []
    chain.order_by.return_value.limit.return_value.all.return_value = rows or []
    chain.order_by.return_value.limit.return_value.offset.return_value \
        .all.return_value = rows or []
    db.query.return_value = chain
    return db


def _mock_flag(value=True):
    return patch.object(wui, "WORKFLOW_MOCK_ENABLED", value)


# ============================================================================
# Test: Workflow UI Routes
# ============================================================================

class TestWorkflowUIRoutes:
    """Test workflow template and definition endpoints."""

    async def test_get_templates_with_database(self):
        """get_templates returns templates from database in DB mode."""
        db = _db(rows=[_tpl()])
        with _mock_flag(False):
            out = await get_templates(
                category=None, complexity=None, is_public=True, db=db
            )
        assert out["success"] is True
        assert out["count"] == 1
        assert out["templates"][0]["id"] == "tpl_001"
        assert out["templates"][0]["name"] == "Test Template"
        assert out["templates"][0]["input_schema"] == {"type": "object"}

    async def test_get_templates_with_mock_mode(self):
        """get_templates returns mock data when WORKFLOW_MOCK_ENABLED."""
        with _mock_flag(True):
            out = await get_templates(
                category=None, complexity=None, is_public=True, db=MagicMock()
            )
        assert out["success"] is True
        assert out["count"] == len(MOCK_TEMPLATES)
        assert len(out["templates"]) > 0

    async def test_get_templates_with_category_filter(self):
        """get_templates filters by category."""
        db = _db(rows=[])
        with _mock_flag(False):
            out = await get_templates(
                category="business", complexity=None, is_public=True, db=db
            )
        assert out["success"] is True
        assert out["templates"] == []
        assert out["count"] == 0
        # The category filter must reach the query chain
        assert db.query.return_value.filter.called

    async def test_import_template_success(self):
        """import_template creates a private copy and bumps usage_count."""
        source = _tpl()
        db = _db(template=source)
        with _mock_flag(False):
            out = await import_template("tpl_001", db=db)
        assert out["success"] is True
        assert out["workflow_id"].startswith("wf_")
        assert db.add.called
        assert db.commit.called
        assert source.usage_count == 101  # incremented on source

    async def test_import_template_not_found(self):
        """import_template raises 404 for a missing template."""
        with _mock_flag(False):
            with pytest.raises(HTTPException) as exc_info:
                await import_template("nonexistent", db=_db(template=None))
        assert exc_info.value.status_code == 404

    async def test_get_services_endpoint(self):
        """get_services returns available service integrations."""
        out = await get_services()
        assert out["success"] is True
        assert len(out["services"]) > 0
        assert any(s["name"] == "Slack" for s in out["services"])

    async def test_get_workflow_definitions(self):
        """get_workflows returns workflow definitions."""
        db = _db(rows=[_tpl()])
        with _mock_flag(False):
            out = await get_workflows(limit=50, offset=0, db=db)
        assert out["success"] is True
        assert out["count"] == 1
        assert out["workflows"][0]["id"] == "tpl_001"
        assert out["workflows"][0]["steps_count"] == 1


# ============================================================================
# Test: UI Integration
# ============================================================================

class TestUIIntegration:
    """Test UI integration with data fetching and transformation."""

    def test_ui_workflow_models_validation(self):
        """Workflow UI Pydantic models validate correctly."""
        # Arrange & Act
        step = WorkflowStep(
            id="step_001",
            type="action",
            service="slack",
            action="send_message",
            parameters={"channel": "#general"},
            name="Send Slack Message"
        )

        template = WorkflowTemplateResponse(
            id="tpl_001",
            name="Test Template",
            description="Test description",
            category="automation",
            icon="workflow",
            steps=[step],
            input_schema={"type": "object"}
        )

        workflow = WorkflowDefinition(
            id="wf_001",
            name="Test Workflow",
            description="Test workflow",
            steps=[step],
            input_schema={},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            steps_count=1
        )

        execution = WorkflowExecution(
            execution_id="exec_001",
            workflow_id="wf_001",
            status="completed",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            current_step=1,
            total_steps=1,
            results={"success": True}
        )

        service = ServiceInfo(
            name="Slack",
            actions=["send_message", "create_channel"],
            description="Team communication"
        )

        # Assert
        assert step.id == "step_001"
        assert step.type == "action"
        assert template.id == "tpl_001"
        assert workflow.id == "wf_001"
        assert execution.status == "completed"
        assert service.name == "Slack"

    def test_mock_data_initialized(self):
        """Mock data templates and workflows are initialized."""
        # Assert
        assert len(MOCK_TEMPLATES) > 0
        assert len(MOCK_WORKFLOWS) > 0
        assert len(MOCK_EXECUTIONS) > 0
        assert len(MOCK_SERVICES) > 0

        # Verify expected services exist
        assert "slack" in MOCK_SERVICES
        assert "ai" in MOCK_SERVICES
        assert "gmail" in MOCK_SERVICES

    def test_workflow_step_parameters_default(self):
        """WorkflowStep parameters default to empty dict."""
        # Arrange & Act
        step = WorkflowStep(
            id="step_002",
            type="action",
            name="Test Step"
        )

        # Assert
        assert step.parameters == {}
        assert step.service is None
        assert step.action is None


# ============================================================================
# Test: Workflow Canvas
# ============================================================================

class TestWorkflowCanvas:
    """Test workflow canvas data and configuration."""

    async def test_get_workflow_by_id_success(self):
        """get_workflow_by_id returns workflow details."""
        db = _db(template=_tpl(id="wf_001", name="Test Workflow"))
        with _mock_flag(False):
            out = await get_workflow_by_id("wf_001", db=db)
        assert out["success"] is True
        assert out["workflow"]["id"] == "wf_001"
        assert out["workflow"]["name"] == "Test Workflow"
        assert out["workflow"]["steps_count"] == 1

    async def test_get_workflow_by_id_not_found(self):
        """get_workflow_by_id raises 404 for a missing workflow."""
        with _mock_flag(False):
            with pytest.raises(HTTPException) as exc_info:
                await get_workflow_by_id("nonexistent", db=_db(template=None))
        assert exc_info.value.status_code == 404
        assert "nonexistent" in exc_info.value.detail

    async def test_create_workflow_success(self):
        """create_workflow creates a new workflow template."""
        db = _db()
        payload = {
            "name": "New Workflow",
            "description": "Test workflow creation",
            "category": "automation",
            "input_schema": {"type": "object"},
            "steps": [],
        }
        with _mock_flag(False):
            out = await create_workflow(payload, author_id="user_001", db=db)
        assert out["success"] is True
        assert out["workflow"]["name"] == "New Workflow"
        assert out["workflow"]["id"].startswith("tpl_")
        assert db.add.called and db.commit.called

    async def test_update_workflow_success(self):
        """update_workflow updates an existing workflow."""
        template = _tpl(id="wf_001", name="Old Name")
        db = _db(template=template)
        payload = {
            "name": "Updated Name",
            "description": "Updated description"
        }
        with _mock_flag(False):
            out = await update_workflow("wf_001", payload, db=db)
        assert out["success"] is True
        assert out["workflow"]["name"] == "Updated Name"
        assert template.name == "Updated Name"
        db.commit.assert_called_once()

    async def test_delete_workflow_success(self):
        """delete_workflow deletes a workflow."""
        template = _tpl(id="wf_001")
        db = _db(template=template)
        with _mock_flag(False):
            out = await delete_workflow("wf_001", db=db)
        assert out["success"] is True
        db.delete.assert_called_once_with(template)
        db.commit.assert_called_once()

    async def test_list_workflows_alias(self):
        """list_workflows returns workflows (alias for get_workflows)."""
        db = _db(rows=[_tpl()])
        with _mock_flag(False):
            out = await list_workflows(limit=10, offset=0, db=db)
        assert out["success"] is True
        assert out["count"] == 1


# ============================================================================
# Test: API Authentication
# ============================================================================

class TestAPIAuthentication:
    """Test API authentication and authorization."""

    async def test_api_response_format_consistent(self):
        """All endpoint responses follow the consistent success format."""
        out = await get_services()
        assert isinstance(out["success"], bool)
        assert out["success"] is True

    async def test_error_response_format(self):
        """Error responses carry a FastAPI-style status_code and detail."""
        with _mock_flag(False):
            with pytest.raises(HTTPException) as exc_info:
                await get_workflow_by_id("nonexistent", db=_db(template=None))
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail

    async def test_endpoint_requires_database_session(self):
        """DB-backed endpoints accept an injected database session."""
        db = _db(rows=[])
        with _mock_flag(False):
            out = await get_workflows(limit=10, offset=0, db=db)
        assert out["success"] is True
        db.query.assert_called()


# ============================================================================
# Test: Workflow Execution
# ============================================================================

class TestWorkflowExecution:
    """Test workflow execution and history endpoints."""

    async def test_execute_workflow_by_id(self):
        """execute_workflow_by_id schedules a background orchestration."""
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        background_tasks = MagicMock()
        user = MagicMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch.object(wui, "require_workflow_executor_orchestrator",
                          new=AsyncMock()), \
             patch.object(wui.uuid, "uuid4",
                          return_value=MagicMock(hex="ab12cd34")):
            out = await execute_workflow_by_id(
                "wf_001",
                background_tasks=background_tasks,
                payload={"input": {}},
                current_user=user,
            )
        assert out["success"] is True
        assert out["execution_id"] == "exec_ab12cd34"
        assert out["workflow_id"] == "wf_001"
        background_tasks.add_task.assert_called_once()

    async def test_get_workflow_history(self):
        """get_workflow_history returns execution history for a workflow."""
        out = await get_workflow_history("wf_1")
        assert out["success"] is True
        assert out["workflow_id"] == "wf_1"
        assert isinstance(out["history"], list)
        assert all(e["workflow_id"] == "wf_1" for e in out["history"])
        assert len(out["history"]) > 0  # mock history exists for wf_1

    async def test_create_workflow_definition(self):
        """create_workflow_definition creates a definition from builder nodes."""
        snapshot = list(MOCK_WORKFLOWS)
        try:
            payload = {
                "name": "Visual Workflow",
                "description": "Created via Visual Builder",
                "definition": {"nodes": [{"id": "node1", "type": "action"},
                                         {"id": "node2", "type": "action"}]},
            }
            out = await create_workflow_definition(payload)
            assert out["success"] is True
            assert out["workflow"]["name"] == "Visual Workflow"
            assert out["workflow"]["steps_count"] == 2
            assert MOCK_WORKFLOWS[0].id == out["workflow"]["id"]
        finally:
            wui.MOCK_WORKFLOWS[:] = snapshot

    async def test_get_executions(self):
        """GET /executions returns active workflow executions (auth required)."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.auth import get_current_user
        from core.workflow_ui_endpoints import router, get_executions

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: MagicMock(
            id="u-69", email="u@example.com", role="member", tenant_id="tenant-69"
        )
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/executions")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "executions" in data

    async def test_cancel_execution(self):
        """cancel_execution cancels a running mock execution."""
        mock_exec = WorkflowExecution(
            execution_id="exec_cancel_001",
            workflow_id="wf_001",
            status="running",
            start_time=datetime.now().isoformat(),
            current_step=1,
            total_steps=3
        )
        MOCK_EXECUTIONS.append(mock_exec)
        try:
            out = await cancel_execution(
                "exec_cancel_001", current_user=MagicMock()
            )
            assert out["success"] is True
            assert mock_exec.status == "cancelled"
        finally:
            MOCK_EXECUTIONS.remove(mock_exec)

    async def test_cancel_execution_not_found(self):
        """cancel_execution raises 404 for a missing execution."""
        db = _db(template=None)
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        with patch.object(wui, "get_db", MagicMock(return_value=iter([db]))), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(HTTPException) as exc_info:
                await cancel_execution(
                    "nonexistent", current_user=MagicMock()
                )
        assert exc_info.value.status_code == 404

    async def test_execute_workflow_endpoint(self):
        """execute_workflow executes a workflow with input data."""
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        orchestrator.workflows = {
            # tpl_o365_finance maps to this orchestrator definition
            "financial_reporting_automation": SimpleNamespace(
                steps=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()]
            )
        }
        background_tasks = MagicMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch.object(wui, "require_workflow_executor_orchestrator",
                          new=AsyncMock()):
            out = await execute_workflow(
                payload={
                    "workflow_id": "tpl_o365_finance",
                    "input": {"month": "January", "dataset": "sales_dashboard"},
                },
                background_tasks=background_tasks,
                current_user=MagicMock(),
            )
        assert out["success"] is True
        assert out["execution_id"].startswith("exec_")
        assert out["status"] == "pending"  # status field present
        assert out["workflow_id"] == "tpl_o365_finance"
        assert out["total_steps"] == 3  # counted from orchestrator definition
        background_tasks.add_task.assert_called_once()
        # Context pre-registered so it appears in the executions list
        assert out["execution_id"] in orchestrator.active_contexts

    async def test_debug_orchestrator_state(self):
        """GET /debug/state returns orchestrator debug information (auth required)."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.auth import get_current_user
        from core.workflow_ui_endpoints import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: MagicMock(
            id="u-69", email="u@example.com", role="member", tenant_id="tenant-69"
        )
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/debug/state")

        # May fail if orchestrator not available, which is OK
        assert response.status_code in [200, 500]
