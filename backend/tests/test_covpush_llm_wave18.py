"""Coverage wave 18 — deeplinks REST routes (TDD)."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deeplinks import router
from core.auth import get_current_user
from core.database import get_db
from core.deeplinks import DeepLinkParseException


def _user(role="member", uid="u-1"):
    u = SimpleNamespace(id=uid)
    if role:
        u.role = role
    return u


def _make_client(role="member", uid="u-1", db_provider=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = db_provider or (lambda: MagicMock())
    app.dependency_overrides[get_current_user] = lambda: _user(role, uid)
    return TestClient(app, raise_server_exceptions=False)


def _audit_row(**kw):
    row = SimpleNamespace(
        id="a1", user_id="u-1", agent_id="ag-1", agent_execution_id="ex-1",
        resource_type="agent", resource_id="ag-1", action="run",
        source="external", deeplink_url="atom://agent/ag-1",
        parameters={}, status="success", error_message=None,
        governance_check_passed=True, created_at=datetime.now(),
    )
    for k, v in kw.items():
        setattr(row, k, v)
    return row


class TestExecuteEndpoint:
    def test_disabled_returns_503(self):
        with patch("api.deeplinks.DEEPLINK_ENABLED", False):
            client = _make_client()
            r = client.post("/api/deeplinks/execute", json={"deeplink_url": "atom://agent/x"})
        assert r.status_code == 503

    def test_success(self):
        client = _make_client()
        with patch(
            "api.deeplinks.execute_deep_link",
            AsyncMock(return_value={
                "success": True, "agent_id": "ag-1", "agent_name": "A",
                "execution_id": "ex-1", "resource_type": "agent",
                "resource_id": "ag-1", "action": "run", "source": "external",
            }),
        ):
            r = client.post(
                "/api/deeplinks/execute",
                json={"deeplink_url": "atom://agent/ag-1", "source": "external"},
            )
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["agent_id"] == "ag-1"

    def test_failure_result_is_validation_error(self):
        client = _make_client()
        with patch(
            "api.deeplinks.execute_deep_link",
            AsyncMock(return_value={"success": False, "error": "nope"}),
        ):
            r = client.post("/api/deeplinks/execute", json={"deeplink_url": "atom://bad"})
        assert r.status_code == 400 or r.status_code == 422

    def test_parse_exception(self):
        client = _make_client()
        with patch(
            "api.deeplinks.execute_deep_link",
            AsyncMock(side_effect=DeepLinkParseException("bad url")),
        ):
            r = client.post("/api/deeplinks/execute", json={"deeplink_url": "bad"})
        assert r.status_code == 400 or r.status_code == 422

    def test_generic_error_500(self):
        client = _make_client()
        with patch(
            "api.deeplinks.execute_deep_link",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            r = client.post("/api/deeplinks/execute", json={"deeplink_url": "atom://x"})
        assert r.status_code == 500


class TestAuditEndpoint:
    def test_scoped_to_current_user(self):
        client = _make_client(uid="u-2")
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = [_audit_row()]
        db.query.return_value = q
        client = _make_client(uid="u-2", db_provider=lambda: db)
        r = client.get("/api/deeplinks/audit?user_id=u-1")
        assert r.status_code == 200
        # user scoping filter applied (audit rows never cross users)
        assert q.filter.called

    def test_with_filters_and_pagination(self):
        client = _make_client()
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = [_audit_row()]
        db.query.return_value = q
        client = _make_client(db_provider=lambda: db)
        r = client.get(
            "/api/deeplinks/audit?agent_id=ag-1&resource_type=agent&limit=50&offset=5"
        )
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["agent_id"] == "ag-1"


class TestGenerateEndpoint:
    def test_disabled_returns_503(self):
        with patch("api.deeplinks.DEEPLINK_ENABLED", False):
            client = _make_client()
            r = client.post(
                "/api/deeplinks/generate",
                json={"resource_type": "agent", "resource_id": "x"},
            )
        assert r.status_code == 503

    def test_invalid_resource_type(self):
        client = _make_client()
        r = client.post(
            "/api/deeplinks/generate",
            json={"resource_type": "bogus", "resource_id": "x"},
        )
        assert r.status_code == 400 or r.status_code == 422

    def test_success(self):
        client = _make_client()
        with patch("api.deeplinks.generate_deep_link", return_value="atom://agent/x?a=1"):
            r = client.post(
                "/api/deeplinks/generate",
                json={"resource_type": "agent", "resource_id": "x", "parameters": {"a": 1}},
            )
        assert r.status_code == 200
        assert r.json()["deeplink_url"] == "atom://agent/x?a=1"
        assert r.json()["parameters"] == {"a": 1}

    def test_value_error_validation(self):
        client = _make_client()
        with patch("api.deeplinks.generate_deep_link", side_effect=ValueError("bad")):
            r = client.post(
                "/api/deeplinks/generate",
                json={"resource_type": "agent", "resource_id": "x"},
            )
        assert r.status_code == 400 or r.status_code == 422


class TestStatsEndpoint:
    def _db(self, counts):
        db = MagicMock()
        base_q = MagicMock()
        count_vals = iter(counts["counts"] + [0] * 50)  # pad: counts may exceed the list
        base_q.count.side_effect = lambda: next(count_vals)
        base_q.filter.return_value = base_q
        base_q.with_entities.return_value = MagicMock(
            distinct=MagicMock(return_value=MagicMock(
                all=MagicMock(return_value=counts.get("sources", []))
            ))
        )
        db.query.return_value = base_q
        return db

    def test_non_admin_scoped(self):
        counts = {
            "counts": [10, 6, 2, 1, 1, 1, 1, 2, 1],  # total, success, failed, 4 resource, 2 source-counts, 24h, 7d
            "sources": [("external",), ("internal",)],
        }
        db = self._db(counts)
        client = _make_client(role="member", db_provider=lambda: db)
        r = client.get("/api/deeplinks/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["total_executions"] == 10
        assert body["successful_executions"] == 6
        assert body["by_resource_type"] == {"agent": 1, "workflow": 1, "canvas": 1, "tool": 1}
        # non-admin: the user-scoping filter is applied to aggregates
        assert db.query.return_value.filter.called

    def test_admin_sees_all(self):
        counts = {
            "counts": [5, 3, 1, 1, 1, 1, 1, 1, 1],
            "sources": [("external",)],
        }
        db = self._db(counts)
        client = _make_client(role="admin", db_provider=lambda: db)
        r = client.get("/api/deeplinks/stats")
        assert r.status_code == 200
        assert r.json()["total_executions"] == 5

    def test_top_agents(self):
        db = MagicMock()
        base_q = MagicMock()
        base_q.count.return_value = 7
        base_q.filter.return_value = base_q
        base_q.with_entities.return_value = MagicMock(
            distinct=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        joined = MagicMock()
        joined.filter.return_value = joined
        joined.group_by.return_value = joined
        joined.order_by.return_value = joined
        joined.limit.return_value = joined
        joined.all.return_value = [("ag-1", "Agent One")]
        base_q.join.return_value = joined
        db.query.return_value = base_q
        client = _make_client(db_provider=lambda: db)
        r = client.get("/api/deeplinks/stats")
        assert r.status_code == 200
        agents = r.json()["top_agents"]
        assert agents[0]["agent_id"] == "ag-1"
        assert agents[0]["agent_name"] == "Agent One"
        assert agents[0]["execution_count"] == 7
