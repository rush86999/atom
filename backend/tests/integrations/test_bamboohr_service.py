"""
Tests for integrations/bamboohr_service.py and bamboohr_routes.py

Covers:
- Not-configured guard
- Happy path per operation (directory, employee, create, time-off)
- HTTP error propagation
- Basic route behaviour (status/health + endpoints when unconfigured)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi import FastAPI

from integrations.bamboohr_service import BambooHRService, bamboohr_configured
from integrations import bamboohr_routes


def make_response(status_code=200, json_data=None, content=b"json"):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.content = content
    resp.json.return_value = json_data if json_data is not None else {}
    if status_code >= 400:
        request = MagicMock()
        request.url = "https://api.bamboohr.com/test"
        resp.request = request
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=request, response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestBambooHRConfiguration:
    def test_not_configured_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("BAMBOOHR_SUBDOMAIN", raising=False)
        monkeypatch.delenv("BAMBOOHR_API_KEY", raising=False)
        assert bamboohr_configured() is False

    def test_configured_when_env_set(self, monkeypatch):
        monkeypatch.setenv("BAMBOOHR_SUBDOMAIN", "acme")
        monkeypatch.setenv("BAMBOOHR_API_KEY", "key123")
        assert bamboohr_configured() is True

    def test_base_url_includes_subdomain(self):
        service = BambooHRService(subdomain="acme", api_key="k")
        assert service.base_url == "https://api.bamboohr.com/api/gateway.php/acme/v1"


class TestBambooHRNotConfiguredGuard:
    async def test_operations_raise_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("BAMBOOHR_SUBDOMAIN", raising=False)
        monkeypatch.delenv("BAMBOOHR_API_KEY", raising=False)
        service = BambooHRService()
        with pytest.raises(HTTPException) as exc:
            await service.list_employees()
        assert exc.value.status_code == 503


class TestBambooHRHappyPaths:
    @pytest.fixture
    def service(self):
        svc = BambooHRService(subdomain="acme", api_key="key")
        svc.client = MagicMock()
        svc.client.request = AsyncMock()
        return svc

    async def test_list_employees(self, service):
        service.client.request.return_value = make_response(json_data={
            "employees": [{"id": "1", "firstName": "Ada", "lastName": "Lovelace"}]
        })
        employees = await service.list_employees()
        assert employees[0]["firstName"] == "Ada"
        call = service.client.request.call_args
        assert "employees/directory" in call.args[1]
        assert call.args[0] == "GET"

    async def test_get_employee(self, service):
        service.client.request.return_value = make_response(json_data={
            "id": "42", "firstName": "Grace", "lastName": "Hopper"
        })
        employee = await service.get_employee("42")
        assert employee["id"] == "42"
        assert "employees/42" in service.client.request.call_args.args[1]

    async def test_create_employee_sends_form_data(self, service):
        service.client.request.return_value = make_response(json_data={"id": "43"})
        result = await service.create_employee(
            "Alan", "Turing", work_email="alan@acme.com", job_title="Mathematician"
        )
        assert result["id"] == "43"
        call = service.client.request.call_args
        assert call.args[0] == "POST"
        assert "employees" in call.args[1]
        assert call.kwargs["data"] == {
            "firstName": "Alan",
            "lastName": "Turing",
            "workEmail": "alan@acme.com",
            "jobTitle": "Mathematician",
        }

    async def test_get_time_off_requests(self, service):
        service.client.request.return_value = make_response(json_data={
            "timeOffRequests": [{"id": "1", "status": "approved"}]
        })
        result = await service.get_time_off_requests(params={"start": "2026-01-01"})
        assert result["timeOffRequests"][0]["status"] == "approved"
        assert "time_off/requests" in service.client.request.call_args.args[1]

    def test_basic_auth_header(self):
        import base64
        service = BambooHRService(subdomain="acme", api_key="key123")
        headers = service._get_headers()
        expected = base64.b64encode(b"key123:x").decode()
        assert headers["Authorization"] == f"Basic {expected}"
        assert headers["Accept"] == "application/json"


class TestBambooHRHttpErrors:
    @pytest.fixture
    def service(self):
        svc = BambooHRService(subdomain="acme", api_key="key")
        svc.client = MagicMock()
        svc.client.request = AsyncMock()
        return svc

    async def test_http_status_error_propagates(self, service):
        service.client.request.return_value = make_response(status_code=404)
        with pytest.raises(HTTPException) as exc:
            await service.get_employee("999")
        assert exc.value.status_code == 404

    async def test_transport_error_raises_502(self, service):
        service.client.request.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await service.list_employees()
        assert exc.value.status_code == 502


# ---------------- Route tests ----------------

route_app = FastAPI()
route_app.include_router(bamboohr_routes.router)
route_client = TestClient(route_app)


class TestBambooHRRoutes:
    def test_status_endpoint(self):
        response = route_client.get("/api/bamboohr/status")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "bamboohr"
        assert data["available"] is True

    def test_health_endpoint(self):
        response = route_client.get("/api/bamboohr/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_employees_endpoint_unconfigured_returns_mock(self, monkeypatch):
        monkeypatch.delenv("BAMBOOHR_SUBDOMAIN", raising=False)
        monkeypatch.delenv("BAMBOOHR_API_KEY", raising=False)
        response = route_client.get("/api/bamboohr/employees")
        assert response.status_code == 200
        assert response.json()["employees"] == []

    def test_create_employee_unconfigured_returns_mock(self, monkeypatch):
        monkeypatch.delenv("BAMBOOHR_SUBDOMAIN", raising=False)
        monkeypatch.delenv("BAMBOOHR_API_KEY", raising=False)
        response = route_client.post(
            "/api/bamboohr/employees", json={"firstName": "A", "lastName": "B"}
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_time_off_endpoint_unconfigured_returns_mock(self, monkeypatch):
        monkeypatch.delenv("BAMBOOHR_SUBDOMAIN", raising=False)
        monkeypatch.delenv("BAMBOOHR_API_KEY", raising=False)
        response = route_client.get("/api/bamboohr/time-off/requests")
        assert response.status_code == 200
        assert response.json()["requests"] == []
