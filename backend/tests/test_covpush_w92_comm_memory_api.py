"""Coverage wave 92 — integrations/atom_communication_memory_api.py (15% → 95%+).

Closes the never-wave-tested gaps: system status (init-on-demand, connection
table stats, error), configured apps listing, single + batch ingestion
(invalid app 404, success with websocket broadcast, partial failures, 500),
memory search (time-windowed with app/query/tag filters, regular search,
bad date 400, 500), per-app communications (time-windowed, regular, invalid
app 404, 500), analytics (full record analytics: response rate, avg response
time seconds/minutes/hours/days, thread grouping via metadata/subject/id
fallbacks, datetime vs string timestamps, corrupt metadata, invalid
timestamps, time-filtered, bad date 400, 500), app configuration
(success/invalid 404/500).

Security: router-level Depends(get_current_user) — every endpoint asserts
401 anonymous.
"""
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from integrations import atom_communication_memory_api as cma

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(cma.atom_memory_router)
    return application


@pytest.fixture
def anon_client(app):
    return TestClient(app)


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(app)


@pytest.fixture
def deps():
    with patch.object(cma, "memory_manager") as mm, \
         patch.object(cma, "ingestion_pipeline") as ip:
        yield SimpleNamespace(mm=mm, ip=ip)


def analytics_records():
    return [
        {"id": "m1", "app_type": "slack", "direction": "inbound",
         "priority": "high", "status": "read", "timestamp": "2026-01-01T10:00:00",
         "metadata": json.dumps({"thread_id": "t1"}), "subject": "S"},
        {"id": "m2", "app_type": "slack", "direction": "outbound",
         "priority": "normal", "status": "sent", "timestamp": "2026-01-01T10:00:30",
         "metadata": {"thread_id": "t1"}, "subject": "S"},
        {"id": "m3", "app_type": "email", "direction": "outbound",
         "priority": "normal", "status": "sent", "timestamp": "2026-01-01T11:00:00",
         "metadata": "{corrupt json", "subject": "Reply"},
        {"id": "m4", "app_type": "slack", "direction": "internal",
         "priority": "normal", "status": "read", "timestamp": "2026-01-02T09:00:00",
         "metadata": "{}", "subject": None},
        {"id": "m5", "app_type": "teams", "direction": "inbound",
         "priority": "normal", "status": "read",
         "timestamp": datetime(2026, 1, 2, 10, 0), "metadata": "{}", "subject": None},
        {"id": "m6", "app_type": "slack", "direction": "inbound",
         "priority": "normal", "status": "read", "timestamp": "not-a-date",
         "metadata": "{}", "subject": None},
    ]


def set_connections_table(mm, records):
    df = MagicMock()
    df.__len__.return_value = len(records)
    df.to_dict.return_value = records
    df.__getitem__.return_value.value_counts.return_value.to_dict.return_value = {
        "slack": 3, "email": 1}
    mm.connections_table = MagicMock()
    mm.connections_table.to_pandas.return_value = df


class TestRouteAuth:
    """Security: every router endpoint rejects anonymous callers."""

    @pytest.mark.parametrize("method,path", [
        ("get", "/api/atom/communication/memory/status"),
        ("get", "/api/atom/communication/memory/apps"),
        ("post", "/api/atom/communication/memory/ingest?app_id=slack"),
        ("post", "/api/atom/communication/memory/ingest/batch?app_id=slack"),
        ("get", "/api/atom/communication/memory/search?query=q"),
        ("get", "/api/atom/communication/memory/communications/slack"),
        ("get", "/api/atom/communication/memory/analytics"),
        ("post", "/api/atom/communication/memory/configure?app_id=slack"),
    ])
    def test_anonymous_rejected(self, anon_client, method, path):
        resp = getattr(anon_client, method)(path)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


class TestStatus:
    def test_initializes_on_demand(self, client, deps):
        deps.mm.db = None

        def _init():
            deps.mm.db = MagicMock()
            deps.mm.db.table_names.return_value = ["connections"]

        deps.mm.initialize.side_effect = _init
        deps.mm.connections_table = None
        deps.mm.db_path = "/data/atom_memory/default"
        deps.ip.get_ingestion_stats.return_value = {
            "configured_apps": ["slack"], "active_streams": ["slack"],
            "total_messages": 42}
        resp = client.get("/api/atom/communication/memory/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"
        assert body["total_apps_configured"] == 1
        assert body["total_messages_ingested"] == 42
        assert body["database_statistics"]["tables"] == ["connections"]
        deps.mm.initialize.assert_called_once()

    def test_connection_stats(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.db.table_names.return_value = ["connections"]
        set_connections_table(deps.mm, analytics_records())
        deps.ip.get_ingestion_stats.return_value = {}
        resp = client.get("/api/atom/communication/memory/status")
        body = resp.json()
        assert body["database_statistics"]["total_records"] == 6
        assert body["database_statistics"]["app_distribution"]["slack"] == 3

    def test_error_500(self, client, deps):
        deps.mm.db = None  # initialize() never sets db -> table_names explodes
        resp = client.get("/api/atom/communication/memory/status")
        assert resp.status_code == 500


class TestApps:
    def test_lists_all_app_types(self, client, deps):
        deps.ip.ingestion_configs = {
            "slack": {"enabled": True, "real_time": True, "batch_size": 100,
                      "ingest_attachments": True, "embed_content": True},
            "email": {"enabled": False, "real_time": False, "batch_size": 0,
                      "ingest_attachments": False, "embed_content": False},
        }
        resp = client.get("/api/atom/communication/memory/apps")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 20  # every CommunicationAppType member listed
        by_id = {a["id"]: a for a in body["apps"]}
        assert by_id["slack"]["memory_ingestion_enabled"] is True
        assert by_id["slack"]["batch_support"] is True
        assert by_id["email"]["memory_ingestion_enabled"] is False
        assert by_id["email"]["batch_support"] is False

    def test_error_500(self, client, deps):
        deps.ip.ingestion_configs = MagicMock()
        deps.ip.ingestion_configs.get.side_effect = RuntimeError("boom")
        resp = client.get("/api/atom/communication/memory/apps")
        assert resp.status_code == 500


class TestIngest:
    def test_initializes_db_on_demand(self, client, deps):
        deps.mm.db = None

        def _init():
            deps.mm.db = MagicMock()

        deps.mm.initialize.side_effect = _init
        deps.ip.ingest_message = AsyncMock(return_value=True)
        resp = client.post("/api/atom/communication/memory/ingest?app_id=slack",
                           json={"id": "m1"})
        assert resp.status_code == 200
        deps.mm.initialize.assert_called_once()

    def test_invalid_app_404(self, client, deps):
        resp = client.post("/api/atom/communication/memory/ingest?app_id=nope",
                           json={"id": "m1", "content": "x"})
        assert resp.status_code == 404

    def test_success_broadcasts(self, client, deps):
        deps.mm.db = MagicMock()
        deps.ip.ingest_message = AsyncMock(return_value=True)
        with patch("core.websockets.manager.broadcast_event",
                   new=AsyncMock()) as bc:
            resp = client.post("/api/atom/communication/memory/ingest?app_id=slack",
                               json={"id": "msg1", "content": "hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message_id"] == "msg1"
        assert body["memory_system"] == "LanceDB"
        deps.ip.ingest_message.assert_awaited_once_with("slack", {"id": "msg1",
                                                                  "content": "hello"})
        bc.assert_awaited()

    def test_ingest_false_500(self, client, deps):
        deps.mm.db = MagicMock()
        deps.ip.ingest_message = AsyncMock(return_value=False)
        resp = client.post("/api/atom/communication/memory/ingest?app_id=slack",
                           json={"id": "m1"})
        assert resp.status_code == 500

    def test_error_500(self, client, deps):
        deps.mm.db = MagicMock()
        deps.ip.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/atom/communication/memory/ingest?app_id=slack",
                           json={"id": "m1"})
        assert resp.status_code == 500


class TestIngestBatch:
    def test_initializes_db_on_demand(self, client, deps):
        deps.mm.db = None

        def _init():
            deps.mm.db = MagicMock()

        deps.mm.initialize.side_effect = _init
        deps.ip.ingest_message = AsyncMock(return_value=True)
        resp = client.post("/api/atom/communication/memory/ingest/batch?app_id=slack",
                           json=[{"id": "m1"}])
        assert resp.status_code == 200
        deps.mm.initialize.assert_called_once()

    def test_invalid_app_404(self, client, deps):
        resp = client.post("/api/atom/communication/memory/ingest/batch?app_id=nope",
                           json=[{"id": "m1"}])
        assert resp.status_code == 404

    def test_partial_success(self, client, deps):
        deps.mm.db = MagicMock()
        deps.ip.ingest_message = AsyncMock(side_effect=[True, False, True])
        resp = client.post("/api/atom/communication/memory/ingest/batch?app_id=slack",
                           json=[{"id": "m1"}, {"id": "m2"}, {"id": "m3"}])
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_messages"] == 3
        assert body["success_count"] == 2
        assert body["failure_count"] == 1
        assert body["success_rate"] == "66.7%"

    def test_empty_batch(self, client, deps):
        deps.mm.db = MagicMock()
        resp = client.post("/api/atom/communication/memory/ingest/batch?app_id=slack",
                           json=[])
        assert resp.json()["success_rate"] == "0.0%"

    def test_error_500(self, client, deps):
        deps.mm.db = MagicMock()
        deps.ip.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/atom/communication/memory/ingest/batch?app_id=slack",
                           json=[{"id": "m1"}])
        assert resp.status_code == 500


class TestSearch:
    def test_initializes_db_on_demand(self, client, deps):
        deps.mm.db = None

        def _init():
            deps.mm.db = MagicMock()

        deps.mm.initialize.side_effect = _init
        deps.mm.search_communications.return_value = []
        resp = client.get("/api/atom/communication/memory/search",
                          params={"query": "q"})
        assert resp.status_code == 200
        deps.mm.initialize.assert_called_once()

    def test_time_windowed_search(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.get_communications_by_timeframe.return_value = [
            {"app_type": "slack", "content": "Alpha project update", "tags": ["sales"]},
            {"app_type": "email", "content": "other", "tags": []},
        ]
        resp = client.get("/api/atom/communication/memory/search", params={
            "query": "alpha", "app_id": "slack", "tag": "sales",
            "time_start": "2026-01-01T00:00:00", "time_end": "2026-01-31T00:00:00"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_results"] == 1
        assert body["results"][0]["app_type"] == "slack"
        deps.mm.get_communications_by_timeframe.assert_called_once()
        deps.mm.search_communications.assert_not_called()

    def test_regular_search(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.search_communications.return_value = [{"content": "hi"}]
        resp = client.get("/api/atom/communication/memory/search",
                          params={"query": "hi", "limit": 5})
        assert resp.status_code == 200
        assert resp.json()["total_results"] == 1
        deps.mm.search_communications.assert_called_once_with("hi", 5, None, None)

    def test_invalid_time_400(self, client, deps):
        deps.mm.db = MagicMock()
        resp = client.get("/api/atom/communication/memory/search", params={
            "query": "q", "time_start": "not-a-date", "time_end": "2026-01-01"})
        assert resp.status_code == 400

    def test_error_500(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.search_communications.side_effect = RuntimeError("boom")
        resp = client.get("/api/atom/communication/memory/search",
                          params={"query": "q"})
        assert resp.status_code == 500


class TestCommunications:
    def test_initializes_db_on_demand(self, client, deps):
        deps.mm.db = None

        def _init():
            deps.mm.db = MagicMock()

        deps.mm.initialize.side_effect = _init
        deps.mm.get_communications_by_app.return_value = []
        resp = client.get("/api/atom/communication/memory/communications/slack")
        assert resp.status_code == 200
        deps.mm.initialize.assert_called_once()

    def test_time_windowed(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.get_communications_by_timeframe.return_value = [
            {"app_type": "slack", "content": "a"},
            {"app_type": "email", "content": "b"},
        ]
        resp = client.get("/api/atom/communication/memory/communications/slack",
                          params={"time_start": "2026-01-01T00:00:00",
                                  "time_end": "2026-01-02T00:00:00"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_results"] == 1
        assert body["app_name"] == "Slack"

    def test_regular(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.get_communications_by_app.return_value = [{"content": "a"}]
        resp = client.get("/api/atom/communication/memory/communications/slack",
                          params={"limit": 25})
        assert resp.status_code == 200
        assert resp.json()["total_results"] == 1
        deps.mm.get_communications_by_app.assert_called_once_with("slack", 25)

    def test_invalid_app_404(self, client, deps):
        deps.mm.db = MagicMock()
        resp = client.get("/api/atom/communication/memory/communications/nope")
        assert resp.status_code == 404

    def test_error_500(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.get_communications_by_app.side_effect = RuntimeError("boom")
        resp = client.get("/api/atom/communication/memory/communications/slack")
        assert resp.status_code == 500


class TestAnalytics:
    def test_initializes_db_on_demand(self, client, deps):
        deps.mm.db = None

        def _init():
            deps.mm.db = MagicMock()

        deps.mm.initialize.side_effect = _init
        deps.mm.connections_table = None
        deps.ip.get_ingestion_stats.return_value = {}
        resp = client.get("/api/atom/communication/memory/analytics")
        assert resp.status_code == 200
        deps.mm.initialize.assert_called_once()

    def _analytics_with_gap(self, client, deps, gap_seconds):
        from datetime import timedelta
        deps.mm.db = MagicMock()
        outbound_ts = (datetime.fromisoformat("2026-01-01T10:00:00")
                       + timedelta(seconds=gap_seconds)).isoformat()
        records = [
            {"id": "m1", "app_type": "slack", "direction": "inbound",
             "priority": "normal", "status": "read",
             "timestamp": "2026-01-01T10:00:00",
             "metadata": json.dumps({"thread_id": "t1"}), "subject": None},
            {"id": "m2", "app_type": "slack", "direction": "outbound",
             "priority": "normal", "status": "sent",
             "timestamp": outbound_ts, "metadata": {"thread_id": "t1"},
             "subject": None},
        ]
        set_connections_table(deps.mm, records)
        deps.ip.get_ingestion_stats.return_value = {}
        return client.get("/api/atom/communication/memory/analytics").json()[
            "analytics"]["performance"]

    def test_avg_response_seconds(self, client, deps):
        perf = self._analytics_with_gap(client, deps, 45)
        assert perf["avg_response_time"] == "45s"

    def test_avg_response_minutes(self, client, deps):
        perf = self._analytics_with_gap(client, deps, 90)
        assert perf["avg_response_time"] == "1m"

    def test_avg_response_hours(self, client, deps):
        perf = self._analytics_with_gap(client, deps, 7200)
        assert perf["avg_response_time"] == "2h"

    def test_avg_response_days(self, client, deps):
        perf = self._analytics_with_gap(client, deps, 172800)
        assert perf["avg_response_time"] == "2d"

    def test_full_analytics(self, client, deps):
        deps.mm.db = MagicMock()
        set_connections_table(deps.mm, analytics_records())
        deps.ip.get_ingestion_stats.return_value = {"total_messages": 6}
        resp = client.get("/api/atom/communication/memory/analytics")
        assert resp.status_code == 200
        a = resp.json()["analytics"]
        assert a["summary"]["total_messages"] == 6
        assert a["summary"]["unique_apps"] == 3
        assert a["app_distribution"] == {"slack": 4, "email": 1, "teams": 1}
        assert a["direction_distribution"] == {"inbound": 3, "outbound": 2,
                                               "internal": 1}
        assert a["priority_distribution"] == {"high": 1, "normal": 5}
        assert a["status_distribution"] == {"read": 4, "sent": 2}
        assert a["timeline_data"] == {"2026-01-01": 3, "2026-01-02": 2}
        perf = a["performance"]
        assert perf["response_rate"] == 66.7
        assert perf["total_responses"] == 1
        assert perf["avg_response_time"] == "30s"

    def test_time_filtered(self, client, deps):
        deps.mm.db = MagicMock()
        df = MagicMock()
        df.to_dict.return_value = [
            {"id": "m1", "app_type": "slack", "direction": "inbound",
             "timestamp": "2026-01-01T10:00:00", "metadata": "{}"},
            {"id": "m2", "app_type": "slack", "direction": "inbound",
             "timestamp": "2026-02-01T10:00:00", "metadata": "{}"},
        ]
        deps.mm.connections_table = MagicMock()
        deps.mm.connections_table.to_pandas.return_value = df
        resp = client.get("/api/atom/communication/memory/analytics",
                          params={"time_start": "2026-01-01T00:00:00",
                                  "time_end": "2026-01-31T00:00:00"})
        assert resp.status_code == 200
        a = resp.json()["analytics"]
        assert a["summary"]["total_messages"] == 1
        assert a["summary"]["date_range"] == {"start": "2026-01-01T00:00:00",
                                              "end": "2026-01-31T00:00:00"}

    def test_no_connections_table(self, client, deps):
        deps.mm.db = MagicMock()
        deps.mm.connections_table = None
        deps.ip.get_ingestion_stats.return_value = {}
        resp = client.get("/api/atom/communication/memory/analytics")
        assert resp.status_code == 200
        assert resp.json()["analytics"]["summary"]["total_messages"] == 0

    def test_invalid_time_400(self, client, deps):
        deps.mm.db = MagicMock()
        set_connections_table(deps.mm, [])
        resp = client.get("/api/atom/communication/memory/analytics",
                          params={"time_start": "junk", "time_end": "2026-01-01"})
        assert resp.status_code == 400

    def test_error_500(self, client, deps):
        deps.mm.db = MagicMock()
        deps.ip.get_ingestion_stats.side_effect = RuntimeError("boom")
        resp = client.get("/api/atom/communication/memory/analytics")
        assert resp.status_code == 500


class TestConfigure:
    CONFIG = {
        "app_type": "slack",
        "enabled": True,
        "real_time": True,
        "batch_size": 50,
        "ingest_attachments": True,
        "embed_content": True,
        "retention_days": 30,
    }

    def test_success(self, client, deps):
        resp = client.post("/api/atom/communication/memory/configure?app_id=slack",
                           json=self.CONFIG)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["app_name"] == "Slack"
        assert body["configuration"]["batch_size"] == 50
        deps.ip.configure_app.assert_called_once()

    def test_invalid_app_404(self, client, deps):
        resp = client.post("/api/atom/communication/memory/configure?app_id=nope",
                           json=self.CONFIG)
        assert resp.status_code == 404

    def test_error_500(self, client, deps):
        deps.ip.configure_app.side_effect = RuntimeError("boom")
        resp = client.post("/api/atom/communication/memory/configure?app_id=slack",
                           json=self.CONFIG)
        assert resp.status_code == 500
