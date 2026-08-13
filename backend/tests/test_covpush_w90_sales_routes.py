"""Coverage wave 90 — api/sales_routes.py (100% line target, auth + alias-bug fixes).

SECURITY RED TESTS: prior waves require auth verification on EVERY endpoint.
api/sales_routes.py exposes financial data (/api/sales/pipeline,
/api/sales/dashboard/summary) with NO get_current_user dependency — an
anonymous route (latent; module is not mounted in main_api_app today).

Also covers the documented 500-bug on /dashboard/summary (calls
get_sales_pipeline() without the db dependency) so the alias actually works.

Tests are written against the EXPECTED fixed behavior: 401 when unauthenticated,
200 with auth, working summary alias, generic 500 on service failure.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from api import sales_routes
from core.auth import get_current_user


class FakeUser:
    id = "user-1"
    tenant_id = "t1"
    workspace_id = "ws-1"


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def client(mock_db):
    app = FastAPI()
    app.include_router(sales_routes.router)
    app.dependency_overrides[sales_routes.get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def anon_client(mock_db):
    app = FastAPI()
    app.include_router(sales_routes.router)
    app.dependency_overrides[sales_routes.get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides = {}


def _metrics(rows):
    """Build the chained query mock returning `rows` from .filter().all()."""
    q = MagicMock()
    f = MagicMock()
    f.all.return_value = rows
    q.filter.return_value = f
    return q


def _m(key, value):
    m = MagicMock()
    m.metric_key = key
    m.value = value
    return m


class TestSalesPipelineAuth:
    def test_pipeline_requires_auth(self, anon_client):
        """RED regression: financial data must never be served anonymously."""
        assert anon_client.get("/api/sales/pipeline").status_code == 401

    def test_summary_requires_auth(self, anon_client):
        assert anon_client.get("/api/sales/dashboard/summary").status_code == 401


class TestSalesPipeline:
    def test_success_aggregates_metrics(self, client, mock_db):
        mock_db.query.return_value = _metrics([
            _m("pipeline_value", 150000.00),
            _m("active_opportunities_count", 25),
            _m("active_deals_count", 30),
        ])
        resp = client.get("/api/sales/pipeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_value"] == 150000.0
        assert data["active_deals"] == 55
        assert data["currency"] == "USD"
        assert data["source"] == "synced_database"

    def test_empty_metrics_zero_defaults(self, client, mock_db):
        mock_db.query.return_value = _metrics([])
        resp = client.get("/api/sales/pipeline")
        assert resp.status_code == 200
        assert resp.json()["pipeline_value"] == 0.0
        assert resp.json()["active_deals"] == 0

    def test_none_values_treated_as_zero(self, client, mock_db):
        mock_db.query.return_value = _metrics([
            _m("pipeline_value", None), _m("active_deals_count", None),
        ])
        resp = client.get("/api/sales/pipeline")
        assert resp.json()["pipeline_value"] == 0.0
        assert resp.json()["active_deals"] == 0

    def test_user_id_param_ignored_but_route_still_serves(self, client, mock_db):
        mock_db.query.return_value = _metrics([_m("pipeline_value", 10)])
        resp = client.get("/api/sales/pipeline?user_id=custom")
        assert resp.status_code == 200
        assert resp.json()["pipeline_value"] == 10.0

    def test_db_failure_returns_generic_500(self, client, mock_db):
        mock_db.query.side_effect = Exception("db down")
        resp = client.get("/api/sales/pipeline")
        assert resp.status_code == 500
        assert "Internal error" in resp.text
        assert "db down" not in resp.text

    def test_filter_failure_returns_generic_500(self, client, mock_db):
        q = MagicMock()
        q.filter.side_effect = Exception("filter boom")
        mock_db.query.return_value = q
        resp = client.get("/api/sales/pipeline")
        assert resp.status_code == 500


class TestSalesDashboardSummary:
    def test_summary_aliases_pipeline(self, client, mock_db):
        """FIXED: summary previously 500'd (missing db dependency)."""
        mock_db.query.return_value = _metrics([_m("pipeline_value", 42.0)])
        resp = client.get("/api/sales/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_value"] == 42.0
        assert data["active_deals"] == 0

    def test_summary_db_failure_500(self, client, mock_db):
        mock_db.query.side_effect = Exception("db down")
        resp = client.get("/api/sales/dashboard/summary")
        assert resp.status_code == 500
