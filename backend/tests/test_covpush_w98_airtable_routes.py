"""Coverage wave 98 — integrations/airtable_routes.py (TDD, 0% baseline).

Fully mocked (AirtableService methods patched on the module singleton, fake
get_current_user), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the READ endpoints
GET /records/{base_id}/{table_name} and GET /records/{base_id}/{table_name}/
{record_id} had NO authentication — anonymous users could read any Airtable
base/table the integration key can reach (data exposure). The anonymous-401
tests below were RED (200) before the fix; `get_current_user` is now required
on both. (POST/PATCH/DELETE /records and /search were already authed; /status
and /health stay public, matching the wave-93 dropbox convention.)

Covers: /status (connected + not_configured), /health (healthy/unhealthy),
list_records (defaults, all params, HTTPException passthrough, 500, anon 401),
get_record (success, passthrough, 500, anon 401), create_record (success, 500,
anon 401), update_record (success, 500, anon 401), delete_record (success,
500, anon 401), search (with base+table success, with base+table service
failure -> ok=False, without base/table -> empty guidance, anon 401).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import airtable_routes as ar


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "airtable98-user"
    u.email = "airtable98@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(ar.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(ar.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    ar.airtable_service.api_key = "key-1"
    with patch.object(ar.airtable_service, "health_check",
                      new=AsyncMock(return_value={"ok": True})), \
            patch.object(ar.airtable_service, "list_records",
                         new=AsyncMock(return_value=[])), \
            patch.object(ar.airtable_service, "get_record",
                         new=AsyncMock(return_value={"id": "rec1"})), \
            patch.object(ar.airtable_service, "create_record",
                         new=AsyncMock(
                             return_value={"id": "rec2", "fields": {}})), \
            patch.object(ar.airtable_service, "update_record",
                         new=AsyncMock(
                             return_value={"id": "rec1", "fields": {}})), \
            patch.object(ar.airtable_service, "delete_record",
                         new=AsyncMock(return_value={"deleted": True})):
        yield ar.airtable_service


class TestStatusHealth:
    def test_status_connected(self, anon_client):
        ar.airtable_service.api_key = "key-1"
        response = anon_client.get("/api/airtable/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "connected"
        assert body["features"]["record_management"] is True

    def test_status_not_configured(self, anon_client):
        ar.airtable_service.api_key = None
        response = anon_client.get("/api/airtable/status?user_id=u1")
        assert response.status_code == 200
        assert response.json()["status"] == "not_configured"
        assert response.json()["user_id"] == "u1"

    def test_health_healthy(self, anon_client):
        response = anon_client.get("/api/airtable/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["configured"] is True

    def test_health_unhealthy(self, anon_client):
        ar.airtable_service.health_check.return_value = {"ok": False}
        response = anon_client.get("/api/airtable/health")
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"

    def test_health_not_configured(self, anon_client):
        ar.airtable_service.api_key = None
        response = anon_client.get("/api/airtable/health")
        assert response.json()["configured"] is False


class TestListRecords:
    def test_success_defaults(self, client):
        ar.airtable_service.list_records.return_value = [
            {"id": "rec1"}, {"id": "rec2"}]
        response = client.get("/api/airtable/records/base1/table1")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["count"] == 2
        assert "timestamp" in body

    def test_success_all_params(self, client):
        response = client.get(
            "/api/airtable/records/base1/table1",
            params={"max_records": 50, "view": "Grid view",
                    "filter_formula": "{Name} = 'x'"})
        assert response.status_code == 200
        ar.airtable_service.list_records.assert_awaited_once_with(
            base_id="base1", table_name="table1", max_records=50,
            view="Grid view", filter_formula="{Name} = 'x'")

    def test_http_exception_passthrough(self, client):
        ar.airtable_service.list_records.side_effect = HTTPException(
            status_code=401, detail="Not authenticated")
        response = client.get("/api/airtable/records/base1/table1")
        assert response.status_code == 401

    def test_error_500(self, client):
        ar.airtable_service.list_records.side_effect = \
            RuntimeError("boom")
        response = client.get("/api/airtable/records/base1/table1")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/airtable/records/base1/table1")
        assert response.status_code == 401

    def test_max_records_validation_422(self, client):
        response = client.get(
            "/api/airtable/records/base1/table1",
            params={"max_records": 1001})
        assert response.status_code == 422


class TestGetRecord:
    def test_success(self, client):
        response = client.get(
            "/api/airtable/records/base1/table1/rec1")
        assert response.status_code == 200
        assert response.json()["record"]["id"] == "rec1"

    def test_http_exception_passthrough(self, client):
        ar.airtable_service.get_record.side_effect = HTTPException(
            status_code=404, detail="Not found")
        response = client.get(
            "/api/airtable/records/base1/table1/missing")
        assert response.status_code == 404

    def test_error_500(self, client):
        ar.airtable_service.get_record.side_effect = \
            RuntimeError("boom")
        response = client.get(
            "/api/airtable/records/base1/table1/rec1")
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/airtable/records/base1/table1/rec1")
        assert response.status_code == 401


class TestCreateRecord:
    def test_success(self, client):
        response = client.post("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "fields": {"Name": "Rushi"}})
        assert response.status_code == 200
        assert response.json()["record"]["id"] == "rec2"

    def test_error_500(self, client):
        ar.airtable_service.create_record.side_effect = \
            RuntimeError("boom")
        response = client.post("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "fields": {"Name": "x"}})
        assert response.status_code == 500

    def test_http_exception_passthrough(self, client):
        ar.airtable_service.create_record.side_effect = HTTPException(
            status_code=400, detail="Invalid fields")
        response = client.post("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "fields": {}})
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "fields": {"Name": "x"}})
        assert response.status_code == 401


class TestUpdateRecord:
    def test_success(self, client):
        response = client.patch("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "record_id": "rec1", "fields": {"Name": "New"}})
        assert response.status_code == 200
        assert response.json()["record"]["id"] == "rec1"

    def test_error_500(self, client):
        ar.airtable_service.update_record.side_effect = \
            RuntimeError("boom")
        response = client.patch("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "record_id": "rec1", "fields": {}})
        assert response.status_code == 500

    def test_http_exception_passthrough(self, client):
        ar.airtable_service.update_record.side_effect = HTTPException(
            status_code=403, detail="Forbidden")
        response = client.patch("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "record_id": "rec1", "fields": {}})
        assert response.status_code == 403

    def test_anonymous_401(self, anon_client):
        response = anon_client.patch("/api/airtable/records", json={
            "base_id": "base1", "table_name": "table1",
            "record_id": "rec1", "fields": {}})
        assert response.status_code == 401


class TestDeleteRecord:
    def test_success(self, client):
        response = client.delete(
            "/api/airtable/records/base1/table1/rec1")
        assert response.status_code == 200
        assert response.json()["deleted"] is True
        assert response.json()["record_id"] == "rec1"

    def test_error_500(self, client):
        ar.airtable_service.delete_record.side_effect = \
            RuntimeError("boom")
        response = client.delete(
            "/api/airtable/records/base1/table1/rec1")
        assert response.status_code == 500

    def test_http_exception_passthrough(self, client):
        ar.airtable_service.delete_record.side_effect = HTTPException(
            status_code=409, detail="Conflict")
        response = client.delete(
            "/api/airtable/records/base1/table1/rec1")
        assert response.status_code == 409

    def test_anonymous_401(self, anon_client):
        response = anon_client.delete(
            "/api/airtable/records/base1/table1/rec1")
        assert response.status_code == 401


class TestSearch:
    def test_with_base_and_table_success(self, client):
        ar.airtable_service.list_records.return_value = [{"id": "rec1"}]
        response = client.post("/api/airtable/search", json={
            "query": "Rushi", "base_id": "base1",
            "table_name": "table1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["results"] == [{"id": "rec1"}]

    def test_with_base_and_table_failure(self, client):
        ar.airtable_service.list_records.side_effect = \
            RuntimeError("boom")
        response = client.post("/api/airtable/search", json={
            "query": "Rushi", "base_id": "base1",
            "table_name": "table1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["results"] == []

    def test_without_base_table_guidance(self, client):
        response = client.post("/api/airtable/search", json={
            "query": "Rushi"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["results"] == []
        assert body["query"] == "Rushi"

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/airtable/search", json={
            "query": "Rushi"})
        assert response.status_code == 401
