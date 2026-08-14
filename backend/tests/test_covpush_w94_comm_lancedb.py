# -*- coding: utf-8 -*-
"""Coverage wave 94 — integrations/atom_communication_apps_lancedb_integration.py
(TDD, fully mocked — no LanceDB, no network).

Closes the branch gaps left by earlier waves (intgr_c covered ~96%): the
memory-manager initialization branches when memory_manager.db is None (batch
ingest, search, timeline), the not-configured 404 path on
GET /apps/{app_id}, the app-filtered timeline, timeline date-parse 400,
timeline/status/stats error paths, ingest failure 500, stream start
success/failure, app communications listing, and memory stats with and
without a connections table. Also drives the default-config initialization
for every app and the configured-apps listing.
"""
import asyncio
import json
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from integrations import atom_communication_apps_lancedb_integration as lancedb_intgr
from integrations.atom_communication_ingestion_pipeline import CommunicationAppType


def route_endpoint(router, path, method="POST"):
    for r in router.routes:
        if getattr(r, "path", None) == path and method in (r.methods or set()):
            return r.endpoint
    raise AssertionError(f"route {method} {path} not found")


def make_request(body: bytes):
    scope = {
        "type": "http", "method": "POST", "path": "/webhook", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "scheme": "http",
        "client": ("1.2.3.4", 1234),
    }
    req = types.SimpleNamespace()
    async def _body():
        return body
    req._body = _body
    req.scope = scope
    req.body = _body
    return req


def _integration():
    return lancedb_intgr.CommunicationAppIngestionIntegration()


def _memory_manager(initialized=True):
    mm = Mock()
    if initialized:
        mm.db = Mock()
    else:
        mm.db = None
    mm.initialize = Mock()
    mm.db_path = "db"
    mm.search_communications = Mock(return_value=[{"id": "m1"}])
    mm.get_communications_by_timeframe = Mock(return_value=[{"id": "m1", "app_type": "slack"}])
    mm.get_communications_by_app = Mock(return_value=[{"id": "m1"}])
    mm.connections_table = None
    return mm


def _pipeline():
    pipe = Mock()
    pipe.get_ingestion_stats = Mock(return_value={
        "configured_apps": ["slack"], "active_streams": ["slack"],
        "total_messages": 3, "app_stats": {"slack": {"messages": 3}}})
    pipe.ingestion_configs = {"slack": Mock()}
    pipe.ingest_message = AsyncMock(return_value=True)
    pipe.start_real_time_stream = Mock(return_value=True)
    return pipe


class TestDefaultConfigs:
    def test_all_apps_configured(self):
        with patch.object(lancedb_intgr.ingestion_pipeline, "configure_app") as m:
            _integration()
        configured = {c.args[0] for c in m.call_args_list}
        documented = {
            CommunicationAppType.WHATSAPP, CommunicationAppType.SLACK,
            CommunicationAppType.EMAIL, CommunicationAppType.TELEGRAM,
            CommunicationAppType.DISCORD, CommunicationAppType.SMS,
            CommunicationAppType.CALLS, CommunicationAppType.MICROSOFT_TEAMS,
            CommunicationAppType.ZOOM, CommunicationAppType.NOTION,
            CommunicationAppType.LINEAR, CommunicationAppType.OUTLOOK,
            CommunicationAppType.GMAIL, CommunicationAppType.SALESFORCE,
            CommunicationAppType.ASANA, CommunicationAppType.DROPBOX,
            CommunicationAppType.BOX, CommunicationAppType.TABLEAU,
            CommunicationAppType.ZOHO, CommunicationAppType.XERO,
            CommunicationAppType.QUICKBOOKS,
        }
        assert configured == documented

    def test_sms_and_calls_disable_attachments(self):
        with patch.object(lancedb_intgr.ingestion_pipeline, "configure_app") as m:
            _integration()
        calls = {c.args[0]: c.args[1] for c in m.call_args_list}
        assert calls[CommunicationAppType.SMS].ingest_attachments is False
        assert calls[CommunicationAppType.CALLS].ingest_attachments is False
        assert calls[CommunicationAppType.WHATSAPP].ingest_attachments is True


class TestStatusAndAppsEndpoints:
    def test_status_endpoint_initializes_when_db_none(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={
                "configured_apps": ["slack"], "active_streams": [], "total_messages": 0,
                "app_stats": {}})
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/status", "GET")())
        mm.initialize.assert_called_once()
        assert result["status"] == "active"
        assert result["memory_database"] == "LanceDB"

    def test_status_endpoint_error_500(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/status", "GET")())
        assert getattr(exc.value, "status_code", None) == 500
        assert "boom" not in str(exc.value.detail)

    def test_apps_endpoint(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={})
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/apps", "GET")())
        assert result["total"] == len(CommunicationAppType)
        assert all(app["supports_ingestion"] for app in result["apps"])

    def test_apps_endpoint_error_500(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "CommunicationAppType") as app_types:
            app_types.return_value = app_types
            app_types.__iter__ = Mock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/apps", "GET")())
        assert getattr(exc.value, "status_code", None) == 500

    def test_app_config_endpoint(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingestion_configs = {"slack": {"app_type": "slack"}}
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/apps/{app_id}", "GET")(
                app_id="slack"))
        assert result["app_id"] == "slack"
        assert result["config"] == {"app_type": "slack"}

    def test_app_config_not_configured_404(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingestion_configs = {}
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/apps/{app_id}", "GET")(
                    app_id="gmail"))
        assert getattr(exc.value, "status_code", None) == 404
        assert "not configured" in str(exc.value.detail)

    def test_app_config_invalid_app_id_404(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingestion_configs = {}
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/apps/{app_id}", "GET")(
                    app_id="notanapp"))
        assert getattr(exc.value, "status_code", None) == 404
        assert "Invalid app_id" in str(exc.value.detail)

    def test_app_config_generic_error_500(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe, \
             patch.object(lancedb_intgr, "CommunicationAppType",
                          side_effect=RuntimeError("boom")):
            pipe.ingestion_configs = {}
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/apps/{app_id}", "GET")(
                    app_id="slack"))
        assert getattr(exc.value, "status_code", None) == 500
        assert "boom" not in str(exc.value.detail)


class TestIngestEndpoints:
    def test_ingest_success(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/ingest/{app_id}")(
                app_id="slack", message_data={"text": "hi"}))
        assert result["success"] is True
        assert "ingested successfully" in result["message"]

    def test_ingest_failure_500(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=False)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/ingest/{app_id}")(
                    app_id="slack", message_data={"text": "hi"}))
        assert getattr(exc.value, "status_code", None) == 500

    def test_ingest_invalid_app_404(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/ingest/{app_id}")(
                    app_id="nope", message_data={}))
        assert getattr(exc.value, "status_code", None) == 404

    def test_ingest_exception_500_no_leak(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("secret-55"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/ingest/{app_id}")(
                    app_id="slack", message_data={}))
        assert getattr(exc.value, "status_code", None) == 500
        assert "secret-55" not in str(exc.value.detail)

    def test_batch_success_with_uninitialized_memory(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            async def _ingest(app_id, msg):
                return msg.get("ok", False)
            pipe.ingest_message = AsyncMock(side_effect=_ingest)
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/ingest/{app_id}/batch")(
                app_id="slack", messages=[{"ok": True}, {"ok": False}, {"ok": True}]))
        mm.initialize.assert_called_once()
        assert result["total_messages"] == 3
        assert result["success_count"] == 2
        assert result["failure_count"] == 1

    def test_batch_invalid_app_404(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/ingest/{app_id}/batch")(
                    app_id="nope", messages=[]))
        assert getattr(exc.value, "status_code", None) == 404

    def test_batch_exception_500(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/ingest/{app_id}/batch")(
                    app_id="slack", messages=[{"x": 1}]))
        assert getattr(exc.value, "status_code", None) == 500


class TestStreamEndpoints:
    def test_stream_start_success(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.start_real_time_stream = Mock(return_value=True)
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/stream/start/{app_id}")(
                app_id="slack"))
        assert result["success"] is True
        assert "stream started" in result["message"]

    def test_stream_start_failure_500(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.start_real_time_stream = Mock(return_value=False)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/stream/start/{app_id}")(
                    app_id="slack"))
        assert getattr(exc.value, "status_code", None) == 500

    def test_stream_invalid_app_404(self):
        with patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.start_real_time_stream = Mock(return_value=True)
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/stream/start/{app_id}")(
                    app_id="nope"))
        assert getattr(exc.value, "status_code", None) == 404

    def test_stream_exception_500(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.start_real_time_stream = Mock(side_effect=RuntimeError("boom"))
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/stream/start/{app_id}")(
                    app_id="slack"))
        assert getattr(exc.value, "status_code", None) == 500


class TestSearchAndTimeline:
    def test_search_initializes_when_db_none(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/search", "GET")(
                query="hello", app_id="slack", limit=5))
        mm.initialize.assert_called_once()
        mm.search_communications.assert_called_once_with("hello", 5, "slack")
        assert result["total_results"] == 1

    def test_search_exception_500_no_leak(self):
        mm = _memory_manager()
        mm.search_communications = Mock(side_effect=RuntimeError("secret-77"))
        with patch.object(lancedb_intgr, "memory_manager", mm):
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/search", "GET")(
                    query="q"))
        assert getattr(exc.value, "status_code", None) == 500
        assert "secret-77" not in str(exc.value.detail)

    def test_timeline_initializes_when_db_none(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/communications/timeline",
                "GET")(start_date="2026-01-01T00:00:00", end_date="2026-01-02T00:00:00"))
        mm.initialize.assert_called_once()
        assert result["total_results"] == 1

    def test_timeline_with_app_filter(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/communications/timeline",
                "GET")(start_date="2026-01-01T00:00:00", end_date="2026-01-02T00:00:00",
                       app_id="gmail"))
        assert result["app_filter"] == "gmail"
        assert result["total_results"] == 0

    def test_timeline_bad_date_400(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm):
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/communications/timeline",
                    "GET")(start_date="not-a-date", end_date="2026-01-02T00:00:00"))
        assert getattr(exc.value, "status_code", None) == 400
        assert "not-a-date" not in str(exc.value.detail)

    def test_timeline_exception_500(self):
        mm = _memory_manager()
        mm.get_communications_by_timeframe = Mock(side_effect=RuntimeError("boom"))
        with patch.object(lancedb_intgr, "memory_manager", mm):
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/communications/timeline",
                    "GET")(start_date="2026-01-01T00:00:00", end_date="2026-01-02T00:00:00"))
        assert getattr(exc.value, "status_code", None) == 500

    def test_app_communications(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/communications/{app_id}",
                "GET")(app_id="slack", limit=10))
        assert result["total_results"] == 1
        mm.get_communications_by_app.assert_called_once_with("slack", 10)

    def test_app_communications_invalid_404(self):
        mm = _memory_manager()
        with patch.object(lancedb_intgr, "memory_manager", mm):
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/communications/{app_id}",
                    "GET")(app_id="nope"))
        assert getattr(exc.value, "status_code", None) == 404

    def test_app_communications_error_500(self):
        mm = _memory_manager()
        mm.get_communications_by_app = Mock(side_effect=RuntimeError("boom"))
        with patch.object(lancedb_intgr, "memory_manager", mm):
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/communications/{app_id}",
                    "GET")(app_id="slack"))
        assert getattr(exc.value, "status_code", None) == 500


class TestMemoryStats:
    def test_stats_with_connections_table(self):
        mm = _memory_manager()
        table = Mock()
        series = Mock()
        series.value_counts.return_value.to_dict.return_value = {"slack": 2}
        table.to_pandas.return_value = {"app_type": series}
        mm.connections_table = table
        mm.db.table_names = Mock(return_value=["atom_communications"])
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={
                "configured_apps": [], "active_streams": [], "total_messages": 0,
                "app_stats": {}})
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/memory/stats", "GET")())
        assert result["database_stats"]["database_type"] == "LanceDB"
        assert result["database_stats"]["total_communications"] == 1
        assert result["database_stats"]["app_distribution"] == {"slack": 2}

    def test_stats_without_connections_table(self):
        mm = _memory_manager()
        mm.db.table_names = Mock(return_value=[])
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={
                "configured_apps": [], "active_streams": [], "total_messages": 0,
                "app_stats": {}})
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/memory/stats", "GET")())
        assert "total_communications" not in result["database_stats"]

    def test_stats_error_500_no_leak(self):
        mm = _memory_manager()
        mm.db.table_names = Mock(side_effect=RuntimeError("secret-88"))
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={})
            with pytest.raises(Exception) as exc:
                asyncio.run(route_endpoint(
                    _integration().router, "/api/memory/ingestion/memory/stats", "GET")())
        assert getattr(exc.value, "status_code", None) == 500
        assert "secret-88" not in str(exc.value.detail)


class TestRemainingInitBranches:
    def test_ingest_initializes_when_db_none(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/ingest/{app_id}")(
                app_id="slack", message_data={"text": "hi"}))
        mm.initialize.assert_called_once()
        assert result["success"] is True

    def test_stream_initializes_when_db_none(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.start_real_time_stream = Mock(return_value=True)
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/stream/start/{app_id}")(
                app_id="slack"))
        mm.initialize.assert_called_once()
        assert result["success"] is True

    def test_app_communications_initializes_when_db_none(self):
        mm = _memory_manager(initialized=False)
        with patch.object(lancedb_intgr, "memory_manager", mm):
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/communications/{app_id}",
                "GET")(app_id="slack", limit=5))
        mm.initialize.assert_called_once()
        assert result["total_results"] == 1

    def test_memory_stats_initializes_when_db_none(self):
        mm = _memory_manager(initialized=False)
        dbm = Mock()
        dbm.table_names = Mock(return_value=[])
        mm.initialize = Mock(side_effect=lambda: setattr(mm, "db", dbm))
        with patch.object(lancedb_intgr, "memory_manager", mm), \
             patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.get_ingestion_stats = Mock(return_value={
                "configured_apps": [], "active_streams": [], "total_messages": 0,
                "app_stats": {}})
            result = asyncio.run(route_endpoint(
                _integration().router, "/api/memory/ingestion/memory/stats", "GET")())
        mm.initialize.assert_called_once()
        assert result["success"] is True


class TestModuleExports:
    def test_global_router_export(self):
        assert lancedb_intgr.communication_ingestion_router is not None
        assert lancedb_intgr.communication_ingestion_integration is not None
        assert lancedb_intgr.__all__ == [
            "communication_ingestion_integration", "communication_ingestion_router"]
