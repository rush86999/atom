"""Coverage wave 96 — integrations/atom_communication_memory_production_api.py
(TDD, 0% baseline).

Class-based router (atom_memory_production_router) with router-level
get_current_user dependency + a per-endpoint verify_token dependency (the
class method wraps core.jwt_verifier.verify_token). Everything is mocked:
memory_manager / ingestion_pipeline singletons, check_uptime, and the
verify_token bound-method dependency override (dependency_overrides keyed
on the bound method works — bound methods hash/eq on (self, func)).

Covers: health (healthy/unhealthy/exception), status (with records/without/
exception->500), ingest/single (success, ValueError->404, ingest-false->500,
exception->500, missing app_id->422), ingest/batch (success mixed,
ValueError->404, exception->500), search/production (regular search,
time-range+app+query filters, include_metadata=False strip, ValueError->400,
exception->500, db-init branch), analytics/production (records analysis,
time/app filters, detailed metrics with real db dir walk, missing-db-dir
fallback, walk-exception fallback, ValueError->400, exception->500), and
anonymous 401 on every route.
"""
import json
import os
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user

from integrations import atom_communication_memory_production_api as mod
from integrations.atom_communication_ingestion_pipeline import (
    ingestion_pipeline,
    memory_manager,
)

router = mod.atom_memory_production_router


@pytest.fixture
def user():
    u = MagicMock()
    u.id = f"cma96-{uuid.uuid4().hex[:8]}"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[mod.atom_memory_production_api.verify_token] = (
        lambda: {"sub": "user-96"})
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _sample_frame():
    return pd.DataFrame([
        {"app_type": "whatsapp", "timestamp": "2026-08-01T10:00:00",
         "content": "hello world", "direction": "inbound",
         "priority": "high", "status": "delivered",
         "attachments": "[]"},
        {"app_type": "slack", "timestamp": "2026-08-02T11:00:00",
         "content": "budget report", "direction": "outbound",
         "priority": "normal", "status": "read",
         "attachments": '["f1.png"]'},
    ])


# ── Health ───────────────────────────────────────────────────────────────────
class TestHealth:
    def test_healthy(self, client):
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": ["whatsapp"]}):
            response = client.get("/api/atom/communication/memory/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["database"] == "healthy"

    def test_unhealthy_no_db(self, client):
        with patch.object(memory_manager, "db", new=None), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": ["whatsapp"]}):
            response = client.get("/api/atom/communication/memory/health")
        assert response.json()["status"] == "unhealthy"
        assert response.json()["database"] == "unhealthy"

    def test_unhealthy_no_apps(self, client):
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = client.get("/api/atom/communication/memory/health")
        assert response.json()["status"] == "unhealthy"
        assert response.json()["ingestion_pipeline"] == "unhealthy"

    def test_exception_unhealthy(self, client):
        with patch.object(ingestion_pipeline, "get_ingestion_stats",
                          side_effect=RuntimeError("boom")):
            response = client.get("/api/atom/communication/memory/health")
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"
        assert "boom" in response.json()["error"]

    def test_anonymous_401(self, anon_client):
        assert anon_client.get(
            "/api/atom/communication/memory/health").status_code == 401


# ── Status ───────────────────────────────────────────────────────────────────
class TestStatus:
    def test_success_with_records(self, client):
        conn = MagicMock()
        conn.to_pandas.return_value = _sample_frame()
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path",
                             new=__import__("pathlib").Path("/tmp/cma96")), \
                patch.object(memory_manager, "db",
                             new=MagicMock()) as db_mock, \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": ["whatsapp"]}), \
                patch.object(mod, "check_uptime",
                      return_value={"uptime_formatted": "2h",
                                    "uptime_percentage": 99.9}):
            db_mock.table_names.return_value = ["atom_communications"]
            response = client.get("/api/atom/communication/memory/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["database"]["statistics"]["total_records"] == 2
        assert body["database"]["statistics"]["app_distribution"]["whatsapp"] == 1
        assert body["database"]["statistics"]["date_range"]["earliest"] == \
            "2026-08-01T10:00:00"
        assert body["performance"]["uptime"] == "2h"

    def test_success_no_connections_table(self, client):
        db_mock = MagicMock()
        db_mock.table_names.return_value = []
        with patch.object(memory_manager, "connections_table", new=None), \
                patch.object(memory_manager, "db", new=db_mock), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}), \
                patch.object(mod, "check_uptime",
                             return_value={"uptime_formatted": "1h",
                                           "uptime_percentage": 98.0}):
            response = client.get("/api/atom/communication/memory/status")
        assert response.status_code == 200
        assert response.json()["database"]["statistics"] == {}

    def test_exception_500(self, client):
        with patch.object(ingestion_pipeline, "get_ingestion_stats",
                          side_effect=RuntimeError("boom")):
            response = client.get("/api/atom/communication/memory/status")
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        assert anon_client.get(
            "/api/atom/communication/memory/status").status_code == 401


# ── Ingest single ────────────────────────────────────────────────────────────
class TestIngestSingle:
    def test_success(self, client):
        with patch.object(ingestion_pipeline, "ingest_message",
                          new=AsyncMock(return_value=True)) as ingest:
            response = client.post(
                "/api/atom/communication/memory/ingest/single",
                params={"app_id": "whatsapp"},
                json={"id": "msg-1", "content": "hi"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message_id"] == "msg-1"
        assert body["environment"] == "production"
        call = ingest.call_args
        assert call.args[0] == "whatsapp"
        assert call.args[1]["metadata"]["environment"] == "production"
        assert call.args[1]["metadata"]["token_used"].endswith("...")

    def test_invalid_app_id_404(self, client):
        response = client.post(
            "/api/atom/communication/memory/ingest/single",
            params={"app_id": "not_an_app"},
            json={"id": "m"})
        assert response.status_code == 404

    def test_ingest_failure_500(self, client):
        with patch.object(ingestion_pipeline, "ingest_message",
                          new=AsyncMock(return_value=False)):
            response = client.post(
                "/api/atom/communication/memory/ingest/single",
                params={"app_id": "whatsapp"},
                json={"id": "m"})
        assert response.status_code == 500

    def test_exception_500(self, client):
        with patch.object(ingestion_pipeline, "ingest_message",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post(
                "/api/atom/communication/memory/ingest/single",
                params={"app_id": "whatsapp"},
                json={"id": "m"})
        assert response.status_code == 500

    def test_missing_app_id_422(self, client):
        response = client.post(
            "/api/atom/communication/memory/ingest/single",
            json={"id": "m"})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/atom/communication/memory/ingest/single",
            params={"app_id": "whatsapp"}, json={"id": "m"})
        assert response.status_code == 401


# ── Ingest batch ─────────────────────────────────────────────────────────────
class TestIngestBatch:
    def test_success_mixed(self, client):
        async def fake_ingest(app_id, message):
            return message.get("id") != "fail"
        with patch.object(ingestion_pipeline, "ingest_message",
                          new=AsyncMock(side_effect=fake_ingest)):
            response = client.post(
                "/api/atom/communication/memory/ingest/batch",
                params={"app_id": "slack"},
                json=[{"id": "ok1"}, {"id": "fail"}, {"id": "ok2"}])
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total_messages"] == 3
        assert body["success_count"] == 2
        assert body["failure_count"] == 1
        assert body["success_rate"] == "66.7%"
        assert body["batch_id"].startswith("batch_")

    def test_invalid_app_id_404(self, client):
        response = client.post(
            "/api/atom/communication/memory/ingest/batch",
            params={"app_id": "NOPE"},
            json=[{"id": "m"}])
        assert response.status_code == 404

    def test_exception_500(self, client):
        with patch.object(ingestion_pipeline, "ingest_message",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post(
                "/api/atom/communication/memory/ingest/batch",
                params={"app_id": "slack"},
                json=[{"id": "m"}])
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/atom/communication/memory/ingest/batch",
            params={"app_id": "slack"}, json=[{"id": "m"}])
        assert response.status_code == 401


# ── Search ───────────────────────────────────────────────────────────────────
class TestSearch:
    def test_regular_search(self, client):
        results = [{"app_type": "whatsapp", "content": "hello",
                    "metadata": {"x": 1}, "vector": "v", "search_vector": "s"}]
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "search_communications",
                             return_value=results):
            response = client.get(
                "/api/atom/communication/memory/search/production",
                params={"query": "hello", "limit": 5})
        assert response.status_code == 200
        body = response.json()
        assert body["total_results"] == 1
        assert body["results"][0]["content"] == "hello"
        assert body["search_metadata"]["token_used"].endswith("...")

    def test_time_range_filters(self, client):
        results = [
            {"app_type": "whatsapp", "content": "hello world"},
            {"app_type": "slack", "content": "nothing here"},
        ]
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager,
                             "get_communications_by_timeframe",
                             return_value=results):
            response = client.get(
                "/api/atom/communication/memory/search/production",
                params={"query": "hello", "app_id": "whatsapp",
                        "time_start": "2026-08-01T00:00:00",
                        "time_end": "2026-08-31T00:00:00"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_results"] == 1
        assert body["time_range"]["start"] == "2026-08-01T00:00:00"

    def test_include_metadata_false_strips(self, client):
        results = [{"app_type": "whatsapp", "content": "c",
                    "metadata": {"m": 1}, "vector": "v", "search_vector": "s"}]
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "search_communications",
                             return_value=results):
            response = client.get(
                "/api/atom/communication/memory/search/production",
                params={"query": "c", "include_metadata": "false"})
        body = response.json()
        result = body["results"][0]
        assert "metadata" not in result
        assert "vector" not in result
        assert "search_vector" not in result

    def test_db_none_initializes(self, client):
        with patch.object(memory_manager, "db", new=None), \
                patch.object(memory_manager, "initialize",
                             new=MagicMock()) as initialize, \
                patch.object(memory_manager, "search_communications",
                             return_value=[]):
            response = client.get(
                "/api/atom/communication/memory/search/production",
                params={"query": "q"})
            assert response.status_code == 200
            initialize.assert_called_once()

    def test_value_error_400(self, client):
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "search_communications",
                             side_effect=ValueError("bad")):
            response = client.get(
                "/api/atom/communication/memory/search/production",
                params={"query": "q"})
        assert response.status_code == 400

    def test_exception_500(self, client):
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "search_communications",
                             side_effect=RuntimeError("boom")):
            response = client.get(
                "/api/atom/communication/memory/search/production",
                params={"query": "q"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        assert anon_client.get(
            "/api/atom/communication/memory/search/production",
            params={"query": "q"}).status_code == 401


# ── Analytics ────────────────────────────────────────────────────────────────
class TestAnalytics:
    def test_full_analytics_with_walk(self, client, tmp_path):
        conn = MagicMock()
        conn.to_pandas.return_value = _sample_frame()
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "blob").write_bytes(b"x" * 20)
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path", new=tmp_path), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": ["whatsapp"]}):
            response = client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 200
        body = response.json()
        analytics = body["analytics"]
        assert analytics["summary"]["total_messages"] == 2
        assert analytics["summary"]["unique_apps"] == 2
        assert analytics["app_distribution"] == {"whatsapp": 1, "slack": 1}
        assert analytics["direction_distribution"]["inbound"] == 1
        assert analytics["priority_distribution"]["high"] == 1
        assert analytics["status_distribution"]["delivered"] == 1
        assert len(analytics["timeline_data"]) == 2
        detail = analytics["detailed_metrics"]
        assert detail["total_attachments"] == 1
        assert detail["most_active_app"] == ["whatsapp", 1]
        assert "compression" in detail["storage_efficiency"]
        assert body["production_metrics"]["token_used"].endswith("...")

    def test_time_and_app_filters(self, client):
        conn = MagicMock()
        conn.to_pandas.return_value = _sample_frame()
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path",
                             new=__import__("pathlib").Path(
                                 "/nonexistent/db/96")), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = client.get(
                "/api/atom/communication/memory/analytics/production",
                params={"app_id": "slack",
                        "time_start": "2026-08-01T00:00:00",
                        "time_end": "2026-08-31T00:00:00"})
        assert response.status_code == 200
        body = response.json()
        analytics = body["analytics"]
        assert analytics["summary"]["total_messages"] == 1
        assert analytics["summary"]["app_filter"] == "slack"
        # missing db dir -> estimate fallback (65% compression)
        assert "65.0% compression" in \
            analytics["detailed_metrics"]["storage_efficiency"]

    def test_no_detailed_metrics(self, client):
        conn = MagicMock()
        conn.to_pandas.return_value = _sample_frame()
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path",
                             new=__import__("pathlib").Path("/tmp/x96")), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = client.get(
                "/api/atom/communication/memory/analytics/production",
                params={"include_detailed_metrics": "false"})
        assert response.status_code == 200
        assert "detailed_metrics" not in response.json()["analytics"]

    def test_walk_exception_fallback(self, client, tmp_path):
        conn = MagicMock()
        conn.to_pandas.return_value = _sample_frame()
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path", new=tmp_path), \
                patch.object(os, "walk",
                             side_effect=OSError("permission denied")), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 200
        assert "65.0% compression" in response.json()["analytics"][
            "detailed_metrics"]["storage_efficiency"]

    def test_empty_records(self, client, tmp_path):
        conn = MagicMock()
        conn.to_pandas.return_value = pd.DataFrame(
            columns=["app_type", "timestamp", "content"])
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path", new=tmp_path), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 200
        analytics = response.json()["analytics"]
        assert analytics["summary"]["total_messages"] == 0
        assert analytics["detailed_metrics"]["peak_day"] is None
        assert analytics["detailed_metrics"]["most_active_app"] is None

    def test_value_error_400(self, client):
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table",
                             new=MagicMock(
                                 to_pandas=MagicMock(
                                     side_effect=ValueError("bad")))), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             side_effect=ValueError("bad")):
            response = client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 400

    def test_db_none_initializes(self, client):
        with patch.object(memory_manager, "db", new=None), \
                patch.object(memory_manager, "initialize",
                             new=MagicMock()) as initialize, \
                patch.object(memory_manager, "connections_table", new=None), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = client.get(
                "/api/atom/communication/memory/analytics/production")
            assert response.status_code == 200
            initialize.assert_called_once()

    def test_bad_timestamp_and_attachments_skipped(self, client, tmp_path):
        conn = MagicMock()
        conn.to_pandas.return_value = pd.DataFrame([
            {"app_type": "whatsapp", "timestamp": "not-a-date",
             "content": "x", "direction": "inbound",
             "priority": "normal", "status": "ok",
             "attachments": "not-json"},
        ])
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path", new=tmp_path), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 200
        analytics = response.json()["analytics"]
        assert analytics["timeline_data"] == {}
        assert analytics["detailed_metrics"]["total_attachments"] == 0

    def test_exception_500(self, client):
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             side_effect=RuntimeError("boom")):
            response = client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        assert anon_client.get(
            "/api/atom/communication/memory/analytics/production"
        ).status_code == 401


# ── verify_token passthrough ─────────────────────────────────────────────────
class TestVerifyToken:
    def test_method_passthrough(self):
        payload = {"sub": "user-x"}
        assert mod.atom_memory_production_api.verify_token(payload) == payload
