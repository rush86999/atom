"""Coverage wave 81 — core/multi_entity_extraction_routes.py (0% → ~100%).

Five routes: trigger extraction (mock background job), list discovered
entities (status/type filters + pagination), approve one, bulk-approve,
and stats aggregation. Fully mocked deps: get_current_user + a FakeDB that
records filter/order/pagination calls and returns seeded rows.
"""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace

import core.multi_entity_extraction_routes as mer
from core.auth import get_current_user
from core.models import DiscoveredEntity
from core.multi_entity_extraction_routes import (
    ApproveEntityRequest,
    BulkApproveRequest,
    DiscoveredEntityResponse,
    ExtractEntitiesRequest,
    ExtractEntitiesResponse,
)


class FakeQuery:
    """Records the query chain and returns seeded rows."""

    def __init__(self, rows=None, scalar=None):
        self._rows = rows if rows is not None else []
        self._scalar = scalar
        self.calls = []

    def filter(self, *args, **kwargs):
        self.calls.append(("filter", args))
        return self

    def order_by(self, *args):
        self.calls.append(("order_by", args))
        return self

    def limit(self, n):
        self.calls.append(("limit", n))
        return self

    def offset(self, n):
        self.calls.append(("offset", n))
        return self

    def all(self):
        return self._rows

    def count(self):
        return len(self._rows)

    def group_by(self, *args):
        self.calls.append(("group_by", args))
        return self

    def scalar(self):
        return self._scalar


class FakeDB:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows if rows is not None else []
        self._scalar = scalar
        self.queries = []
        self.last_query = None

    def query(self, *models):
        self.queries.append(models)
        self.last_query = FakeQuery(self._rows, self._scalar)
        return self.last_query


def make_entity(entity_id="e1", dtype="PurchaseOrder", status="pending",
                confidence=0.92):
    return DiscoveredEntity(
        id=entity_id,
        tenant_id="t1",
        workspace_id="w1",
        _discovered_type=dtype,
        properties={"amount": 100},
        source_record_id="msg-1",
        source_record_type="email",
        status=status,
        confidence_score=confidence,
        created_at=datetime(2026, 8, 1, 12, 0, 0),
    )


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(mer.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1", tenant_id="t1")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db():
    return FakeDB()


def override_db(app, db):
    app.dependency_overrides[mer.get_db] = lambda: db
    return app


class TestAuthentication:
    """All five routes already require auth — verify 401 for anonymous."""

    @pytest.mark.parametrize("method,path", [
        ("post", "/integrations/gmail-1/extract-entities"),
        ("get", "/entities/discovered"),
        ("post", "/entities/discovered/e1/approve"),
        ("post", "/entities/discovered/bulk-approve"),
        ("get", "/entities/discovered/stats"),
    ])
    def test_anon_401(self, method, path):
        app = FastAPI()
        app.include_router(mer.router)
        client = TestClient(app)
        kw = {"json": {}} if method == "post" else {}
        resp = getattr(client, method)(path, **kw)
        assert resp.status_code == 401


class TestExtractEntities:
    def test_success(self, client, db):
        app = override_db(client.app, db)
        resp = TestClient(app).post("/integrations/gmail-1/extract-entities",
                                    json={"force_resync": True, "batch_size": 25,
                                          "confidence_threshold": 0.8})
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "job-gmail-1"
        assert body["estimated_completion"] == "2-3 hours"
        assert body["emails_to_process"] == 7100
        assert body["estimated_entities"] == 14200

    def test_defaults(self, client, db):
        app = override_db(client.app, db)
        resp = TestClient(app).post("/integrations/outlook-1/extract-entities",
                                    json={})
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "job-outlook-1"

    @pytest.mark.parametrize("payload", [
        {"batch_size": 0},
        {"batch_size": 101},
        {"confidence_threshold": 1.5},
        {"confidence_threshold": -0.1},
    ])
    def test_validation_422(self, client, db, payload):
        app = override_db(client.app, db)
        resp = TestClient(app).post("/integrations/gmail-1/extract-entities",
                                    json=payload)
        assert resp.status_code == 422

    def test_request_model_direct(self):
        req = ExtractEntitiesRequest()
        assert req.force_resync is False
        assert req.batch_size == 50
        assert req.confidence_threshold == 0.7
        resp = ExtractEntitiesResponse(
            job_id="j", estimated_completion="1h",
            emails_to_process=10, estimated_entities=20)
        assert resp.emails_to_process == 10


class TestListDiscovered:
    def test_default_query(self, client, db):
        db._rows = [make_entity(), make_entity("e2", "SecurityEvent", "linked")]
        app = override_db(client.app, db)
        resp = TestClient(app).get("/entities/discovered")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["id"] == "e1"
        assert body[0]["_discovered_type"] == "PurchaseOrder"
        assert body[0]["confidence_score"] == 0.92
        assert body[0]["status"] == "pending"
        assert body[0]["properties"] == {"amount": 100}
        assert body[0]["created_at"] == "2026-08-01T12:00:00"
        q = db.queries[0]
        assert q[0] is DiscoveredEntity

    def test_filters_recorded(self, client, db):
        db._rows = []
        app = override_db(client.app, db)
        resp = TestClient(app).get(
            "/entities/discovered?status=linked&discovered_type=PurchaseOrder&limit=10&offset=5")
        assert resp.status_code == 200
        assert resp.json() == []
        assert db.queries[0][0] is DiscoveredEntity
        chain = db.last_query.calls
        assert ("filter",) in [(c[0],) for c in chain]
        assert ("limit", 10) in chain
        assert ("offset", 5) in chain
        assert any(c[0] == "order_by" for c in chain)

    @pytest.mark.parametrize("params", [
        "limit=0", "limit=1001", "offset=-1",
    ])
    def test_pagination_validation_422(self, client, db, params):
        app = override_db(client.app, db)
        resp = TestClient(app).get(f"/entities/discovered?{params}")
        assert resp.status_code == 422


class TestApproveEntity:
    def test_approve_success(self, client, db):
        app = override_db(client.app, db)
        resp = TestClient(app).post(
            "/entities/discovered/e1/approve",
            json={"entity_type_slug": "purchase_order"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "approved", "entity_id": "e1"}

    def test_approve_missing_body_422(self, client, db):
        app = override_db(client.app, db)
        resp = TestClient(app).post("/entities/discovered/e1/approve", json={})
        assert resp.status_code == 422

    def test_approve_request_model(self):
        r = ApproveEntityRequest(entity_type_slug="po")
        assert r.entity_type_slug == "po"


class TestBulkApprove:
    def test_bulk_approve_success(self, client, db):
        db._rows = [make_entity(), make_entity("e2")]
        app = override_db(client.app, db)
        resp = TestClient(app).post(
            "/entities/discovered/bulk-approve",
            json={"discovered_type": "PurchaseOrder",
                  "entity_type_slug": "purchase_order"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["discovered_type"] == "PurchaseOrder"
        assert body["entity_type_slug"] == "purchase_order"
        assert body["count"] == 2

    def test_bulk_approve_zero(self, client, db):
        app = override_db(client.app, db)
        resp = TestClient(app).post(
            "/entities/discovered/bulk-approve",
            json={"discovered_type": "None", "entity_type_slug": "x"})
        assert resp.json()["count"] == 0

    def test_bulk_approve_missing_422(self, client, db):
        app = override_db(client.app, db)
        resp = TestClient(app).post("/entities/discovered/bulk-approve", json={})
        assert resp.status_code == 422

    def test_bulk_approve_model(self):
        r = BulkApproveRequest(discovered_type="PO", entity_type_slug="po")
        assert r.discovered_type == "PO"


class TestStats:
    def test_stats_success(self, client, db):
        db._rows = [("pending", 3), ("linked", 1)]
        db._scalar = 0.85
        app = override_db(client.app, db)
        resp = TestClient(app).get("/entities/discovered/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_by_status"] == {"pending": 3, "linked": 1}
        assert body["average_confidence"] == 0.85
        assert body["total_entities"] == 4
        assert "top_types" in body

    def test_stats_empty(self, client, db):
        db._scalar = None
        app = override_db(client.app, db)
        resp = TestClient(app).get("/entities/discovered/stats")
        body = resp.json()
        assert body["total_by_status"] == {}
        assert body["average_confidence"] == 0.0
        assert body["total_entities"] == 0
