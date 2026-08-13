"""Coverage wave 71 — core/integration_enhancement_endpoints.py (81% → 95%+).

Closes the remaining holes:
- REAL BUG (TDD red→green): only 3 write endpoints required auth
  (register_schema/create_mapping/submit_bulk_operation); all 12 read
  endpoints (schemas, mappings, transform, validate, job status/cancel,
  stats, analytics, templates) were anonymous. Router now carries
  dependencies=[Depends(get_current_user)] so the whole surface is gated.
  RED: anonymous GET /api/v1/integrations/schemas must 401 instead of 200.
- register_schema: non-admin 403, exception → 500
- create_mapping: success path (FieldType/TransformationType conversion),
  ValueError → 400, generic exception → 500
- validate_data generic exception → 500
- submit_bulk_operation: optional mapping_id/schema_id wiring, exception → 500
- bulk stats route, analytics export-failure tolerance, analytics 500
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.integration_enhancement_endpoints as iee
from core.bulk_operations_processor import BulkOperation, OperationStatus, get_bulk_processor
from core.integration_data_mapper import (
    FieldMapping,
    FieldType,
    IntegrationDataMapper,
    IntegrationSchema,
    TransformationType,
    get_data_mapper,
)
from core.integration_enhancement_endpoints import router


@pytest.fixture
def mapper():
    m = Mock(spec=IntegrationDataMapper)
    m.list_schemas.return_value = ["asana_task"]
    m.get_schema_info.return_value = IntegrationSchema(
        integration_id="asana_task",
        integration_name="Asana Task",
        version="1.0",
        fields={"name": {"type": "string", "required": True}},
        supported_operations=["create"],
        bulk_operations_supported=True,
        max_bulk_size=50,
    )
    m.list_mappings.return_value = ["m1"]
    m.export_mapping.return_value = {"field_mappings": [], "exported_at": "2026-08-13T00:00:00"}
    m.validate_data.return_value = {"valid": True, "errors": []}
    m.transform_data.return_value = []
    return m


@pytest.fixture
def processor():
    p = Mock()
    p.submit_bulk_job = AsyncMock(return_value="bulk_1")
    p.get_job_status = AsyncMock(return_value=None)
    p.cancel_job = AsyncMock(return_value=True)
    p.get_performance_stats.return_value = {"total_jobs": 3, "average_processing_time": 1.2}
    return p


@pytest.fixture
def client(mapper, processor):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_data_mapper] = lambda: mapper
    app.dependency_overrides[get_bulk_processor] = lambda: processor
    app.dependency_overrides[iee.get_current_user] = lambda: Mock(id="u1", is_admin=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def authed_user():
    def _user(**kw):
        u = Mock(id="u1")
        u.is_admin = kw.get("is_admin", True)
        return u
    return _user


class TestAuthGate:
    def _anon_client(self, mapper, processor):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_data_mapper] = lambda: mapper
        app.dependency_overrides[get_bulk_processor] = lambda: processor
        return TestClient(app)

    def test_anonymous_schemas_list_rejected(self, mapper, processor):
        # RED before fix: anonymous read access to schemas/mappings.
        resp = self._anon_client(mapper, processor).get("/api/v1/integrations/schemas")
        assert resp.status_code == 401

    def test_anonymous_mappings_rejected(self, mapper, processor):
        resp = self._anon_client(mapper, processor).get("/api/v1/integrations/mappings")
        assert resp.status_code == 401

    def test_anonymous_bulk_status_rejected(self, mapper, processor):
        resp = self._anon_client(mapper, processor).get("/api/v1/integrations/bulk/bulk_1")
        assert resp.status_code == 401

    def test_anonymous_mapping_templates_rejected(self, mapper, processor):
        resp = self._anon_client(mapper, processor).get("/api/v1/integrations/mapping-templates")
        assert resp.status_code == 401


class TestSchemaRoutes:
    def test_list_schemas(self, client):
        resp = client.get("/api/v1/integrations/schemas")
        assert resp.status_code == 200
        assert resp.json()["total_schemas"] == 1

    def test_get_schema_details_found(self, client):
        resp = client.get("/api/v1/integrations/schemas/asana_task")
        assert resp.status_code == 200
        assert resp.json()["schema"]["integration_name"] == "Asana Task"

    def test_get_schema_details_not_found(self, client, mapper):
        mapper.get_schema_info.return_value = None
        resp = client.get("/api/v1/integrations/schemas/nope")
        assert resp.status_code == 404

    def test_register_schema_non_admin_forbidden(self, client, authed_user):
        client.app.dependency_overrides[iee.get_current_user] = lambda: authed_user(is_admin=False)
        resp = client.post("/api/v1/integrations/schemas", json={
            "integration_id": "x", "integration_name": "X", "fields": {},
            "supported_operations": ["read"],
        })
        assert resp.status_code == 403

    def test_register_schema_admin_success(self, client, mapper):
        resp = client.post("/api/v1/integrations/schemas", json={
            "integration_id": "slack_msg", "integration_name": "Slack Message",
            "version": "1.0", "fields": {"text": {"type": "string"}},
            "supported_operations": ["read", "create"],
            "bulk_operations_supported": True, "max_bulk_size": 100,
        })
        assert resp.status_code == 200
        mapper.register_schema.assert_called_once()
        assert resp.json()["schema_id"] == "slack_msg"

    def test_register_schema_exception_500(self, client, mapper):
        mapper.register_schema.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/integrations/schemas", json={
            "integration_id": "x", "integration_name": "X", "fields": {},
            "supported_operations": ["read"],
        })
        assert resp.status_code == 500


class TestMappingRoutes:
    def test_list_mappings_with_export_error_tolerated(self, client, mapper):
        mapper.export_mapping.side_effect = RuntimeError("bad export")
        resp = client.get("/api/v1/integrations/mappings")
        assert resp.status_code == 200
        assert resp.json()["mappings"]["m1"] == {"error": "bad export"}

    def test_create_mapping_success(self, client, mapper):
        resp = client.post("/api/v1/integrations/mappings", json={
            "mapping_id": "m_new",
            "source_schema": "asana_task",
            "target_schema": "jira_issue",
            "field_mappings": [
                {
                    "source_field": "name", "target_field": "summary",
                    "source_type": "string", "target_type": "string",
                    "transformation": "direct_copy", "required": True,
                },
                {
                    "source_field": "completed", "target_field": "status",
                    "source_type": "boolean", "target_type": "string",
                    "transformation": "conditional",
                    "transformation_config": {"conditions": []}, "required": False,
                },
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["field_count"] == 2
        assert resp.json()["mapping_id"] == "m_new"

    def test_create_mapping_value_error_400(self, client, mapper):
        mapper.create_mapping.side_effect = ValueError("bad schema")
        resp = client.post("/api/v1/integrations/mappings", json={
            "mapping_id": "m_bad", "source_schema": "asana_task",
            "target_schema": "jira_issue",
            "field_mappings": [{
                "source_field": "a", "target_field": "b",
                "source_type": "string", "target_type": "string",
                "transformation": "direct_copy",
            }],
        })
        assert resp.status_code == 400

    def test_create_mapping_generic_500(self, client, mapper):
        mapper.create_mapping.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/integrations/mappings", json={
            "mapping_id": "m_bad2", "source_schema": "asana_task",
            "target_schema": "jira_issue",
            "field_mappings": [{
                "source_field": "a", "target_field": "b",
                "source_type": "string", "target_type": "string",
                "transformation": "direct_copy",
            }],
        })
        assert resp.status_code == 500

    def test_get_mapping_details_found(self, client):
        resp = client.get("/api/v1/integrations/mappings/m1")
        assert resp.status_code == 200
        assert resp.json()["mapping"]["field_mappings"] == []

    def test_get_mapping_details_not_found(self, client, mapper):
        mapper.export_mapping.side_effect = ValueError("missing")
        resp = client.get("/api/v1/integrations/mappings/missing")
        assert resp.status_code == 404

    def test_transform_data_success(self, client, mapper):
        mapper.transform_data.return_value = [{"summary": "hi"}]
        resp = client.post("/api/v1/integrations/mappings/m1/transform",
                           json={"data": [{"name": "hi"}], "mapping_id": "m1"})
        assert resp.status_code == 200
        assert resp.json()["items_transformed"] == 1

    def test_transform_data_mapping_missing_404(self, client, mapper):
        mapper.list_mappings.return_value = []
        resp = client.post("/api/v1/integrations/mappings/missing/transform",
                           json={"data": [], "mapping_id": "missing"})
        assert resp.status_code == 404

    def test_transform_data_exception_500(self, client, mapper):
        mapper.transform_data.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/integrations/mappings/m1/transform",
                           json={"data": [], "mapping_id": "m1"})
        assert resp.status_code == 500

    def test_validate_data_success(self, client):
        resp = client.post("/api/v1/integrations/validate?schema_id=asana_task",
                           json=[{"name": "x"}])
        assert resp.status_code == 200
        assert resp.json()["validation"]["valid"] is True

    def test_validate_data_value_error_404(self, client, mapper):
        mapper.validate_data.side_effect = ValueError("no schema")
        resp = client.post("/api/v1/integrations/validate?schema_id=ghost",
                           json=[{"name": "x"}])
        assert resp.status_code == 404

    def test_validate_data_generic_500(self, client, mapper):
        mapper.validate_data.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/integrations/validate?schema_id=asana_task",
                           json=[{"name": "x"}])
        assert resp.status_code == 500


class TestBulkRoutes:
    def test_submit_bulk_success_with_optional_fields(self, client, processor):
        resp = client.post("/api/v1/integrations/bulk", json={
            "operation_type": "create", "integration_id": "asana",
            "items": [{"name": "t1"}, {"name": "t2"}],
            "batch_size": 10, "parallel_processing": False,
            "stop_on_error": True, "mapping_id": "m1", "schema_id": "asana_task",
        })
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "bulk_1"
        op = processor.submit_bulk_job.call_args[0][0]
        assert isinstance(op, BulkOperation)
        assert op.mapping_id == "m1"
        assert op.schema_id == "asana_task"

    def test_submit_bulk_without_optional_fields(self, client, processor):
        resp = client.post("/api/v1/integrations/bulk", json={
            "operation_type": "delete", "integration_id": "jira",
            "items": [{"id": "1"}],
        })
        assert resp.status_code == 200
        op = processor.submit_bulk_job.call_args[0][0]
        assert not hasattr(op, "mapping_id")

    def test_submit_bulk_exception_500(self, client, processor):
        processor.submit_bulk_job.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/integrations/bulk", json={
            "operation_type": "create", "integration_id": "asana",
            "items": [{"name": "t1"}],
        })
        assert resp.status_code == 500

    def test_get_bulk_job_status_404(self, client, processor):
        resp = client.get("/api/v1/integrations/bulk/missing")
        assert resp.status_code == 404

    def test_get_bulk_job_status_success(self, client, processor):
        job = Mock()
        job.job_id = "bulk_1"
        job.status = OperationStatus.COMPLETED
        job.created_at = datetime.now(timezone.utc)
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        job.total_items = 10
        job.processed_items = 10
        job.successful_items = 9
        job.failed_items = 1
        job.progress_percentage = 100.0
        job.estimated_completion = None
        job.errors = [{"i": 1}, {"i": 2}, {"i": 3}]
        processor.get_job_status.return_value = job
        resp = client.get("/api/v1/integrations/bulk/bulk_1")
        assert resp.status_code == 200
        body = resp.json()["job"]
        assert body["status"] == "completed"
        assert body["error_count"] == 3
        assert len(body["recent_errors"]) == 3

    def test_cancel_bulk_job_success(self, client, processor):
        resp = client.post("/api/v1/integrations/bulk/bulk_1/cancel")
        assert resp.status_code == 200

    def test_cancel_bulk_job_404(self, client, processor):
        processor.cancel_job.return_value = False
        resp = client.post("/api/v1/integrations/bulk/bulk_1/cancel")
        assert resp.status_code == 404

    def test_bulk_processing_stats(self, client):
        resp = client.get("/api/v1/integrations/bulk/stats")
        assert resp.status_code == 200
        assert resp.json()["stats"]["total_jobs"] == 3


class TestAnalyticsRoutes:
    def test_integration_analytics_success(self, client):
        resp = client.get("/api/v1/integrations/analytics")
        assert resp.status_code == 200
        analytics = resp.json()["analytics"]
        assert analytics["schemas"]["bulk_capable"] == 1
        assert analytics["mappings"]["total_count"] == 1

    def test_integration_analytics_export_failure_tolerated(self, client, mapper):
        mapper.export_mapping.side_effect = RuntimeError("bad export")
        with patch.object(iee.logger, "debug") as dbg:
            resp = client.get("/api/v1/integrations/analytics")
        assert resp.status_code == 200
        assert resp.json()["analytics"]["mappings"]["average_complexity"] == 0
        dbg.assert_called()

    def test_integration_analytics_generic_500(self, client, mapper):
        mapper.list_schemas.side_effect = RuntimeError("boom")
        resp = client.get("/api/v1/integrations/analytics")
        assert resp.status_code == 500


class TestTemplateRoutes:
    def test_get_mapping_templates(self, client):
        resp = client.get("/api/v1/integrations/mapping-templates")
        assert resp.status_code == 200
        assert resp.json()["total_templates"] == 2
        assert "asana_to_jira" in resp.json()["templates"]

    def test_apply_mapping_template_404(self, client):
        resp = client.post("/api/v1/integrations/mapping-templates/ghost?mapping_id=m9")
        assert resp.status_code == 404

    def test_apply_mapping_template_success(self, client, mapper):
        resp = client.post("/api/v1/integrations/mapping-templates/asana_to_jira?mapping_id=m9")
        assert resp.status_code == 200
        assert resp.json()["mapping_id"] == "m9"
        mapper.create_mapping.assert_called_once()
        args = mapper.create_mapping.call_args[0]
        assert args[0] == "m9"
        assert all(isinstance(fm, FieldMapping) for fm in args[3])

    def test_apply_mapping_template_exception_500(self, client, mapper):
        mapper.create_mapping.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/integrations/mapping-templates/asana_to_jira?mapping_id=m9")
        assert resp.status_code == 500
