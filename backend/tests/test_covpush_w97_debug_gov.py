# -*- coding: utf-8 -*-
"""Coverage wave 97 — debug/governance batch.

Targets:
1.  core/debug_insights/performance.py
2.  core/integrations/adapters/zoho.py
3.  core/canvas_recording_service.py
4.  core/fleet_orchestration/fleet_progress_service.py
5.  core/local_agent_service.py
6.  core/formula_extractor.py
7.  api/project_health_routes.py
8.  core/cache.py
9.  core/openclaw_parser.py
10. core/webhook_renewal_service.py

No network, no real LLM, no real Redis — every external boundary
(httpx, DB sessions, Redis, ws manager, subprocess, backend API) is mocked.
Plain pytest + unittest.mock (asyncio_mode=auto).
"""
import asyncio
import json as _json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# --------------------------------------------------------------------------- #
# Shared fakes
# --------------------------------------------------------------------------- #
class FakeQuery:
    def __init__(self, items=None, first=None, count=0):
        self._items = list(items or [])
        self._first = first
        self._count = count

    def filter(self, *a, **k): return self
    def filter_by(self, *a, **k): return self
    def order_by(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def offset(self, *a, **k): return self
    def group_by(self, *a, **k): return self
    def distinct(self, *a, **k): return self
    def all(self): return self._items
    def first(self): return self._first
    def count(self): return self._count


class EntityDB:
    """DB fake dispatching query() by entity class name."""

    def __init__(self):
        self._map = {}
        self.added = []
        self.committed = 0
        self.rolled_back = 0
        self.expired = 0

    def register(self, entity, query):
        self._map[getattr(entity, "__name__", str(entity))] = query
        return query

    def query(self, entity):
        name = getattr(entity, "__name__", str(entity))
        return self._map.get(name, FakeQuery())

    def add(self, obj): self.added.append(obj)
    def commit(self): self.committed += 1
    def rollback(self): self.rolled_back += 1
    def refresh(self, obj): pass
    def expire_all(self): self.expired += 1
    def close(self): pass


def _HC(client):
    """httpx.AsyncClient mock usable as `async with ... as c:`."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


def _async_client(get_json=None, post_json=None, get_raises=None, post_raises=None):
    """Mock httpx client whose .get/.post are awaitable."""
    c = MagicMock()
    if get_raises:
        c.get = AsyncMock(side_effect=get_raises)
    else:
        c.get = AsyncMock(return_value=_http_response(200, get_json))
    if post_raises:
        c.post = AsyncMock(side_effect=post_raises)
    else:
        c.post = AsyncMock(return_value=_http_response(200, post_json))
    return c


def _http_response(status_code=200, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data if json_data is not None else {}
    r.text = text
    return r


# =========================================================================== #
# 1. core/debug_insights/performance.py
# =========================================================================== #
import core.debug_insights.performance as perf_mod
from core.debug_insights.performance import PerformanceInsightGenerator


class QDB:
    """DB fake whose query() always returns the configured FakeQuery."""

    def __init__(self, q=None):
        self.q = q or FakeQuery()

    def query(self, *a, **k):
        return self.q


class TestPerformanceInsights:
    def _event(self, duration=None, ctype="agent", cid="a1", msg="step"):
        data = {"duration_ms": duration} if duration is not None else {}
        return NS(component_type=ctype, component_id=cid, message=msg,
                  data=data, timestamp=datetime.now(timezone.utc))

    def _metric(self, name, value, ctype="node", cid="node-1"):
        return NS(metric_name=name, component_type=ctype, component_id=cid, value=value)

    @pytest.fixture()
    def db(self):
        return QDB()

    @pytest.fixture()
    def gen(self, db):
        return PerformanceInsightGenerator(db)

    # -- analyze_component_latency -------------------------------------------
    async def test_latency_high_p95_warning(self, gen, db):
        events = [self._event(10) for _ in range(9)] + [self._event(20000)]
        db.q = FakeQuery(items=events)
        ins = await gen.analyze_component_latency("agent", "a1")
        assert ins.severity == perf_mod.DebugInsightSeverity.WARNING.value
        assert ins.evidence["p95_ms"] == 20000

    async def test_latency_acceptable_info(self, gen, db):
        events = [self._event(100 + i) for i in range(12)]
        db.q = FakeQuery(items=events)
        ins = await gen.analyze_component_latency("agent", "a1")
        assert ins.severity == perf_mod.DebugInsightSeverity.INFO.value

    async def test_latency_insufficient_data(self, gen, db):
        db.q = FakeQuery(items=[self._event(5)] * 5)
        assert await gen.analyze_component_latency("agent", "a1") is None

    async def test_latency_exception_returns_none(self, gen, db):
        db.query = Mock(side_effect=RuntimeError("db down"))
        assert await gen.analyze_component_latency("agent", "a1") is None

    # -- identify_bottlenecks --------------------------------------------------
    async def test_bottleneck_dominant_step(self, gen, db):
        events = [self._event(9000, ctype="db", cid="q"),
                  self._event(100, ctype="api", cid="r"),
                  NS(component_type="x", component_id="y", message="no-dur",
                     data={}, timestamp=datetime.now(timezone.utc))]
        db.q = FakeQuery(items=events)
        ins = await gen.identify_bottlenecks("corr-1")
        assert ins is not None
        assert "Bottleneck" in ins.summary
        assert ins.evidence["correlation_id"] == "corr-1"

    async def test_bottleneck_no_dominant(self, gen, db):
        events = [self._event(50), self._event(50), self._event(50)]
        db.q = FakeQuery(items=events)
        assert await gen.identify_bottlenecks("corr-1") is None

    async def test_bottleneck_no_events_and_no_durations(self, gen, db):
        db.q = FakeQuery(items=[])
        assert await gen.identify_bottlenecks("c") is None
        db.q = FakeQuery(
            items=[NS(component_type="a", component_id="b", message="m",
                      data={}, timestamp=datetime.now(timezone.utc))])
        assert await gen.identify_bottlenecks("c") is None

    async def test_bottleneck_exception(self, gen, db):
        db.query = Mock(side_effect=RuntimeError("boom"))
        assert await gen.identify_bottlenecks("c") is None

    # -- track_resource_utilization ---------------------------------------------
    async def test_resource_high_cpu_and_memory(self, gen, db):
        q = FakeQuery(items=[
            self._metric("cpu_usage", 90), self._metric("cpu_usage", 85),
            self._metric("memory_usage", 95), self._metric("memory_usage", 92),
        ])
        db.q = q
        insights = await gen.track_resource_utilization()
        titles = " ".join(i.title for i in insights)
        assert "High CPU usage" in titles
        assert "High memory usage" in titles

    async def test_resource_normal_returns_empty(self, gen, db):
        db.q = FakeQuery(items=[self._metric("cpu_usage", 30)])
        assert await gen.track_resource_utilization() == []

    async def test_resource_exception_returns_empty(self, gen, db):
        db.query = Mock(side_effect=RuntimeError("x"))
        assert await gen.track_resource_utilization() == []

    # -- detect_performance_degradation -------------------------------------------
    async def test_degradation_detected(self, gen, db):
        events = [self._event(100) for _ in range(10)] + \
                 [self._event(500) for _ in range(10)]
        db.q = FakeQuery(items=events)
        ins = await gen.detect_performance_degradation("agent", "a1")
        assert ins is not None
        assert ins.evidence["degradation_percent"] == pytest.approx(400.0)

    async def test_degradation_stable_returns_none(self, gen, db):
        events = [self._event(100) for _ in range(20)]
        db.q = FakeQuery(items=events)
        assert await gen.detect_performance_degradation("agent", "a1") is None

    async def test_degradation_too_few_events(self, gen, db):
        events = [self._event(100) for _ in range(15)]
        db.q = FakeQuery(items=events)
        assert await gen.detect_performance_degradation("agent", "a1") is None

    async def test_degradation_exception(self, gen, db):
        db.query = Mock(side_effect=RuntimeError("x"))
        assert await gen.detect_performance_degradation("a", "b") is None

    # -- analyze_throughput --------------------------------------------------------
    async def test_throughput_low(self, gen, db):
        db.q = FakeQuery(
            items=[("2026-08-15 10:00", 5), ("2026-08-15 10:01", 7)])
        ins = await gen.analyze_throughput("agent")
        assert "Low throughput" in ins.title

    async def test_throughput_high(self, gen, db):
        db.q = FakeQuery(
            items=[("m1", 900), ("m2", 1200)])
        ins = await gen.analyze_throughput("agent")
        assert "High throughput" in ins.title

    async def test_throughput_normal_and_empty(self, gen, db):
        db.q = FakeQuery(
            items=[("m1", 100), ("m2", 200)])
        assert await gen.analyze_throughput("agent") is None
        db.q = FakeQuery(items=[])
        assert await gen.analyze_throughput("agent") is None

    async def test_throughput_exception(self, gen, db):
        db.query = Mock(side_effect=RuntimeError("x"))
        assert await gen.analyze_throughput("agent") is None

    # -- _parse_time_range -----------------------------------------------------------
    @pytest.mark.parametrize("tr,hours", [
        ("last_1h", 1), ("last_24h", 24), ("last_7d", 24 * 7), ("bogus", 1),
    ])
    def test_parse_time_range(self, gen, tr, hours):
        cutoff = gen._parse_time_range(tr)
        expected = datetime.now(timezone.utc) - timedelta(hours=hours)
        assert abs((cutoff - expected).total_seconds()) < 5


# =========================================================================== #
# 2. core/integrations/adapters/zoho.py
# =========================================================================== #
import core.integrations.adapters.zoho as zoho_mod
from core.integrations.adapters.zoho import ZohoAdapter


class TestZohoAdapter:
    @pytest.fixture()
    def adapter(self):
        return ZohoAdapter(workspace_id="ws-1", instance_url="https://www.zohoapis.com")

    # -- base URL ---------------------------------------------------------------
    @pytest.mark.parametrize("module,expected", [
        ("crm", "https://www.zohoapis.com/crm/v2"),
        ("books", "https://www.zohoapis.com/books/v3"),
        ("inventory", "https://www.zohoapis.com/inventory/v1"),
        ("projects", "https://projectsapi.zoho.com/restapi/v1"),
        ("CRM", "https://www.zohoapis.com/crm/v2"),
        ("unknown", "https://www.zohoapis.com/crm/v2"),
    ])
    def test_get_base_url(self, adapter, module, expected):
        assert adapter._get_base_url(module) == expected

    # -- token loading -------------------------------------------------------------
    async def test_load_token_no_db(self, adapter):
        adapter.db = None
        await adapter._load_token()  # no-op
        assert adapter._access_token is None

    async def test_load_token_found(self, adapter):
        token = NS(access_token="enc-at", refresh_token="enc-rt",
                   expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                   instance_url="https://zoho.eu")
        db = EntityDB()
        db.register(zoho_mod.IntegrationToken if hasattr(zoho_mod, "IntegrationToken")
                    else NS(__name__="IntegrationToken"), FakeQuery(first=token))
        adapter.db = db
        with patch("core.privsec.token_encryption.decrypt_token",
                   side_effect=lambda v, **k: v.replace("enc-", "")):
            await adapter._load_token()
        assert adapter._access_token == "at"
        assert adapter._refresh_token == "rt"
        assert adapter.instance_url == "https://zoho.eu"

    async def test_load_token_none(self, adapter):
        db = EntityDB()
        db.register(NS(__name__="IntegrationToken"), FakeQuery(first=None))
        adapter.db = db
        await adapter._load_token()
        assert adapter._access_token is None

    # -- refresh / ensure ----------------------------------------------------------
    async def test_refresh_token_no_refresh_token(self, adapter):
        assert await adapter.refresh_token() is False

    async def test_refresh_token_success(self, adapter):
        adapter._refresh_token = "rt"
        token = NS(access_token="old", refresh_token="rt",
                   expires_at=None, instance_url=None)
        db = EntityDB()
        db.register(NS(__name__="IntegrationToken"), FakeQuery(first=token))
        adapter.db = db
        client = _async_client(
            post_json={"access_token": "new-at", "expires_in": 7200})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)), \
             patch("core.privsec.token_encryption.encrypt_token", side_effect=lambda v: f"E:{v}"), \
             patch("core.privsec.token_encryption.stamp_credential_metadata"):
            assert await adapter.refresh_token() is True
        assert adapter._access_token == "new-at"
        assert token.access_token == "E:new-at"
        assert db.committed == 1

    async def test_refresh_token_http_failure(self, adapter):
        adapter._refresh_token = "rt"
        client = _async_client(post_raises=RuntimeError("net down"))
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            assert await adapter.refresh_token() is False

    async def test_refresh_token_db_without_token_row(self, adapter):
        adapter._refresh_token = "rt"
        db = EntityDB()
        db.register(NS(__name__="IntegrationToken"), FakeQuery(first=None))
        adapter.db = db
        client = _async_client(post_json={"access_token": "x"})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            assert await adapter.refresh_token() is True

    async def test_ensure_token_expired_triggers_refresh(self, adapter):
        adapter._access_token = "stale"
        adapter._token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        adapter.refresh_token = AsyncMock(return_value=True)
        await adapter.ensure_token()
        adapter.refresh_token.assert_awaited_once()

    async def test_ensure_token_valid_skips_refresh(self, adapter):
        adapter._access_token = "ok"
        adapter._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        adapter.refresh_token = AsyncMock()
        await adapter.ensure_token()
        adapter.refresh_token.assert_not_awaited()

    # -- oauth url -------------------------------------------------------------------
    async def test_get_oauth_url_default_scopes(self, adapter):
        url = await adapter.get_oauth_url()
        assert url.startswith("https://accounts.zoho.com/oauth/v2/auth?")
        assert "ZohoCRM.modules.ALL" in url
        assert "state=ws-1" in url

    async def test_get_oauth_url_custom_scopes(self, adapter):
        url = await adapter.get_oauth_url(scopes=["ZohoCRM.tasks.READ"])
        assert "scope=ZohoCRM.tasks.READ" in url

    # -- CRUD fetchers -----------------------------------------------------------------
    def _fetch_case(self, adapter, key, payload):
        adapter._access_token = "tok"
        return _async_client(get_json=payload)

    async def test_get_leads(self, adapter):
        client = self._fetch_case(adapter, "data", {"data": [
            {"id": "L1", "Full_Name": "Bob", "Email": "b@x.test", "Company": "Co",
             "Lead_Status": "New"}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            leads = await adapter.get_leads(limit=5)
        assert leads[0]["name"] == "Bob"
        assert leads[0]["source"] == "zoho_crm"
        client.get.assert_called_once()

    async def test_get_deals(self, adapter):
        client = self._fetch_case(adapter, "data", {"data": [
            {"id": "D1", "Deal_Name": "Big", "Amount": 500, "Stage": "Won",
             "Closing_Date": "2026-01-01"}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            deals = await adapter.get_deals()
        assert deals[0]["amount"] == 500

    async def test_get_invoices(self, adapter):
        client = self._fetch_case(adapter, "invoices", {"invoices": [
            {"invoice_id": "I1", "invoice_number": "INV-1", "customer_name": "C",
             "total": 99, "status": "paid", "due_date": "2026-02-01"}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            inv = await adapter.get_invoices("org-1")
        assert inv[0]["number"] == "INV-1"

    async def test_get_portals(self, adapter):
        client = self._fetch_case(adapter, "portals", {"portals": [
            {"id_string": "P1", "name": "Portal", "is_default": True}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            portals = await adapter.get_portals()
        assert portals[0]["is_default"] is True

    async def test_get_projects(self, adapter):
        client = self._fetch_case(adapter, "projects", {"projects": [
            {"id_string": "PR1", "name": "Proj", "status": "active",
             "owner_name": "me", "created_date_format": "2026"}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            projects = await adapter.get_projects("P1")
        assert projects[0]["source"] == "zoho_projects"

    async def test_get_tasks(self, adapter):
        client = self._fetch_case(adapter, "tasks", {"tasks": [
            {"id_string": "T1", "name": "Task", "description": "d",
             "status": {"name": "open"}, "priority": "high", "end_date": "2026"}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            tasks = await adapter.get_tasks("P1", "PR1")
        assert tasks[0]["status"] == "open"

    async def test_get_items(self, adapter):
        client = self._fetch_case(adapter, "items", {"items": [
            {"item_id": "IT1", "name": "Widget", "sku": "W1", "rate": 5,
             "stock_on_hand": 10, "unit": "ea"}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            items = await adapter.get_items("org-1")
        assert items[0]["sku"] == "W1"

    async def test_get_sales_orders(self, adapter):
        client = self._fetch_case(adapter, "salesorders", {"salesorders": [
            {"salesorder_id": "SO1", "salesorder_number": "SO-1",
             "customer_name": "C", "total": 1, "status": "open", "date": "2026"}]})
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            orders = await adapter.get_sales_orders("org-1")
        assert orders[0]["type"] == "sales_order"

    async def test_fetch_error_returns_empty(self, adapter):
        adapter._access_token = "tok"
        client = _async_client()
        client.get = AsyncMock(return_value=_http_response(500))
        with patch.object(zoho_mod.httpx, "AsyncClient", _HC(client)):
            assert await adapter.get_leads() == []
            assert await adapter.get_deals() == []
            assert await adapter.get_invoices("o") == []
            assert await adapter.get_portals() == []
            assert await adapter.get_projects("p") == []
            assert await adapter.get_tasks("p", "pr") == []
            assert await adapter.get_items("o") == []
            assert await adapter.get_sales_orders("o") == []

    # -- mappers -----------------------------------------------------------------------
    def test_mappers_direct(self, adapter):
        assert adapter._map_lead({})["name"] is None
        assert adapter._map_deal({})["type"] == "deal"
        assert adapter._map_invoice({})["id"] is None
        assert adapter._map_portal({})["is_default"] is False
        assert adapter._map_project({})["owner_name"] is None
        assert adapter._map_task({})["status"] is None
        assert adapter._map_inventory_item({})["price"] is None
        assert adapter._map_sales_order({})["date"] is None


# =========================================================================== #
# 3. core/canvas_recording_service.py
# =========================================================================== #
import core.canvas_recording_service as crs_mod
from core.canvas_recording_service import (
    CanvasRecordingService, get_canvas_recording_service,
)


def _recording(status="recording", events=None, tags=None, **kw):
    r = NS(
        recording_id="rec-1", agent_id="a1", user_id="u1", canvas_id="c1",
        session_id="s1", reason="governance", status=status,
        tags=list(tags or []), events=list(events or []),
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        stopped_at=None, duration_seconds=None, event_count=None,
        summary=None, recording_metadata={}, expires_at=None,
        flagged_for_review=False, flag_reason=None, flagged_by=None,
        flagged_at=None,
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


class TestCanvasRecordingService:
    @pytest.fixture(autouse=True)
    def _gov(self):
        with patch("core.service_factory.ServiceFactory.get_governance_service"):
            yield

    @pytest.fixture()
    def db(self):
        db = EntityDB()
        db.register(crs_mod.AgentRegistry, FakeQuery(first=None))
        db.register(crs_mod.CanvasRecording, FakeQuery(first=None, items=[]))
        return db

    @pytest.fixture()
    def svc(self, db):
        with patch.object(crs_mod, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            svc = CanvasRecordingService(db, tenant_id="t-1")
            svc._ws = ws
            yield svc

    # -- start_recording -----------------------------------------------------------
    async def test_start_recording_success(self, svc, db):
        db._map["AgentRegistry"] = FakeQuery(
            first=NS(name="R2D2", status="autonomous"))
        rid = await svc.start_recording("u1", "a1", "canvas-1", "governance",
                                        session_id="s1", tags=["x"])
        assert rid
        assert len(db.added) == 2  # recording + audit
        assert svc._ws.broadcast.await_count == 1
        msg = svc._ws.broadcast.call_args[0][1]
        assert msg["type"] == "canvas:recording_started"

    async def test_start_recording_agent_missing(self, svc, db):
        rid = await svc.start_recording("u1", "ghost", None, "manual")
        assert rid
        rec = db.added[0]
        assert rec.recording_metadata["agent_name"] == "Unknown"

    async def test_start_recording_disabled(self, svc, db, monkeypatch):
        monkeypatch.setattr(crs_mod, "CANVAS_RECORDING_ENABLED", False)
        rid = await svc.start_recording("u1", "a1", None, "r")
        assert rid
        assert db.added == []

    async def test_start_recording_error_returns_uuid(self, svc, db):
        db.query = Mock(side_effect=RuntimeError("db down"))
        rid = await svc.start_recording("u1", "a1", None, "r")
        assert rid

    # -- record_event -----------------------------------------------------------------
    async def test_record_event_appends(self, svc, db):
        rec = _recording(events=[{"event_type": "a"}])
        db._map["CanvasRecording"] = FakeQuery(first=rec)
        await svc.record_event("rec-1", "update", {"x": 1})
        assert len(rec.events) == 2
        assert rec.events[-1]["event_type"] == "update"
        assert db.committed == 1
        assert db.expired == 1

    async def test_record_event_not_found(self, svc, db):
        db._map["CanvasRecording"] = FakeQuery(first=None)
        await svc.record_event("ghost", "update", {})  # no raise

    async def test_record_event_disabled_and_error(self, svc, db, monkeypatch):
        monkeypatch.setattr(crs_mod, "CANVAS_RECORDING_ENABLED", False)
        await svc.record_event("rec-1", "u", {})  # no-op
        db.query = Mock(side_effect=RuntimeError("x"))
        monkeypatch.setattr(crs_mod, "CANVAS_RECORDING_ENABLED", True)
        await svc.record_event("rec-1", "u", {})  # swallowed

    # -- stop_recording -----------------------------------------------------------------
    async def test_stop_recording(self, svc, db):
        rec = _recording(events=[{"event_type": "operation_complete"},
                                 {"event_type": "error"}])
        db._map["CanvasRecording"] = FakeQuery(first=rec)
        with patch.object(svc, "_trigger_auto_review", AsyncMock()):
            await svc.stop_recording("rec-1", status="completed")
        assert rec.status == "completed"
        assert rec.duration_seconds > 0
        assert "errors occurred" in rec.summary
        assert svc._ws.broadcast.await_count == 1

    async def test_stop_recording_naive_started_at(self, svc, db):
        rec = _recording(started_at=datetime.utcnow().replace(tzinfo=None))
        db._map["CanvasRecording"] = FakeQuery(first=rec)
        with patch.object(svc, "_trigger_auto_review", AsyncMock()):
            await svc.stop_recording("rec-1", summary="done")
        assert rec.summary == "done"

    async def test_stop_recording_not_found_and_error(self, svc, db):
        db._map["CanvasRecording"] = FakeQuery(first=None)
        await svc.stop_recording("ghost")  # no raise
        db.query = Mock(side_effect=RuntimeError("x"))
        await svc.stop_recording("rec-1")  # swallowed

    async def test_trigger_auto_review_paths(self, svc, db):
        with patch("core.recording_review_service.RecordingReviewService") as RS:
            RS.return_value.auto_review_recording = AsyncMock(return_value="rev-1")
            await svc._trigger_auto_review("rec-1")
            RS.return_value.auto_review_recording = AsyncMock(return_value=None)
            await svc._trigger_auto_review("rec-1")
            RS.side_effect = RuntimeError("boom")
            await svc._trigger_auto_review("rec-1")  # swallowed

    # -- get/list ------------------------------------------------------------------------
    async def test_get_recording(self, svc, db):
        rec = _recording(stopped_at=datetime.now(timezone.utc),
                         expires_at=datetime.now(timezone.utc), event_count=2)
        db._map["CanvasRecording"] = FakeQuery(first=rec)
        out = await svc.get_recording("rec-1")
        assert out["recording_id"] == "rec-1"
        assert out["stopped_at"] is not None

    async def test_get_recording_none_and_error(self, svc, db):
        db._map["CanvasRecording"] = FakeQuery(first=None)
        assert await svc.get_recording("ghost") is None
        db.query = Mock(side_effect=RuntimeError("x"))
        assert await svc.get_recording("rec-1") is None

    async def test_list_recordings(self, svc, db):
        db._map["CanvasRecording"] = FakeQuery(items=[_recording(), _recording()])
        out = await svc.list_recordings("u1", agent_id="a1", limit=10, offset=0)
        assert len(out) == 2

    async def test_list_recordings_error(self, svc, db):
        db.query = Mock(side_effect=RuntimeError("x"))
        assert await svc.list_recordings("u1") == []

    # -- auto_record_autonomous_action ------------------------------------------------------
    async def test_auto_record_not_autonomous(self, svc, db):
        db._map["AgentRegistry"] = FakeQuery(
            first=NS(name="A", status="supervised"))
        assert await svc.auto_record_autonomous_action("a1", "u1", "act", {}) is None
        db._map["AgentRegistry"] = FakeQuery(first=None)
        assert await svc.auto_record_autonomous_action("a1", "u1", "act", {}) is None

    async def test_auto_record_existing(self, svc, db):
        db._map["AgentRegistry"] = FakeQuery(
            first=NS(name="A", status="autonomous"))
        db._map["CanvasRecording"] = FakeQuery(first=_recording())
        assert await svc.auto_record_autonomous_action(
            "a1", "u1", "act", {"session_id": "s1"}) == "rec-1"

    async def test_auto_record_starts_new(self, svc, db):
        db._map["AgentRegistry"] = FakeQuery(
            first=NS(name="A", status="autonomous"))
        db._map["CanvasRecording"] = FakeQuery(first=None)
        rid = await svc.auto_record_autonomous_action(
            "a1", "u1", "act", {"session_id": "s1", "canvas_id": "c1"})
        assert rid

    async def test_auto_record_disabled_and_error(self, svc, db, monkeypatch):
        monkeypatch.setattr(crs_mod, "CANVAS_RECORDING_ENABLED", False)
        assert await svc.auto_record_autonomous_action("a1", "u1", "a", {}) is None
        monkeypatch.setattr(crs_mod, "CANVAS_RECORDING_ENABLED", True)
        db.query = Mock(side_effect=RuntimeError("x"))
        assert await svc.auto_record_autonomous_action("a1", "u1", "a", {}) is None

    # -- flag_for_review ------------------------------------------------------------------------
    async def test_flag_for_review(self, svc, db):
        rec = _recording(tags=["existing"])
        db._map["CanvasRecording"] = FakeQuery(first=rec)
        await svc.flag_for_review("rec-1", "suspicious", "admin")
        assert rec.flagged_for_review is True
        assert "flagged_review" in rec.tags

    async def test_flag_not_found_and_error(self, svc, db):
        db._map["CanvasRecording"] = FakeQuery(first=None)
        await svc.flag_for_review("ghost", "r", "u")  # no raise
        db.query = Mock(side_effect=RuntimeError("x"))
        await svc.flag_for_review("rec-1", "r", "u")  # swallowed

    # -- helpers ---------------------------------------------------------------------------------
    def test_generate_summary_variants(self, svc):
        assert svc._generate_summary(
            _recording(events=[{"event_type": "operation_complete"}])).endswith(
            "operation completed")
        assert svc._generate_summary(_recording(events=[])) == "0 events recorded"

    async def test_create_audit_error(self, svc, db):
        db.add = Mock(side_effect=RuntimeError("x"))
        await svc._create_audit("a", "u", "r", "act")  # swallowed

    def test_factory(self, db):
        assert isinstance(get_canvas_recording_service(db), CanvasRecordingService)


# =========================================================================== #
# 4. core/fleet_orchestration/fleet_progress_service.py
# =========================================================================== #
import core.fleet_orchestration.fleet_progress_service as fps_mod
from core.fleet_orchestration.fleet_progress_service import (
    AgentStatus, FleetProgress, FleetProgressService,
    get_fleet_progress_service,
)


def _fake_redis(pipeline_results=None, hgetall_map=None):
    r = MagicMock()
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=pipeline_results or [])
    r.pipeline.return_value = pipe
    r.hgetall = AsyncMock(
        side_effect=lambda key: (hgetall_map or {}).get(key, {}))
    r.publish = AsyncMock()
    r.close = AsyncMock()
    return r


class TestFleetProgressService:
    @pytest.fixture()
    def svc(self):
        return FleetProgressService(db=MagicMock())

    # -- _get_redis ---------------------------------------------------------------------------
    async def test_get_redis_no_url(self, svc, monkeypatch):
        for var in ("DRAGONFLY_URL", "UPSTASH_REDIS_URL", "REDIS_URL"):
            monkeypatch.delenv(var, raising=False)
        assert await svc._get_redis() is None

    async def test_get_redis_with_url(self, svc, monkeypatch):
        monkeypatch.setenv("DRAGONFLY_URL", "redis://localhost:6379/0")
        client = await svc._get_redis()
        assert client is not None
        await client.close()

    async def test_get_redis_exception(self, svc, monkeypatch):
        svc._redis_client = None
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        with patch.object(fps_mod.redis, "from_url", side_effect=RuntimeError("bad url")):
            assert await svc._get_redis() is None

    # -- record_agent_* ------------------------------------------------------------------------
    async def test_record_agent_start(self, svc):
        fake = _fake_redis()
        svc._redis_client = fake
        svc.publish_progress_update = AsyncMock()
        await svc.record_agent_start("ch1", "a1", "do work", "trace-1")
        pipe = fake.pipeline.return_value
        pipe.sadd.assert_called_once()
        pipe.hset.assert_called_once()
        pipe.incr.assert_called_once()
        assert pipe.expire.call_count == 3
        svc.publish_progress_update.assert_awaited_once()

    async def test_record_agent_start_no_redis(self, svc):
        svc._redis_client = None
        svc._get_redis = AsyncMock(return_value=None)
        await svc.record_agent_start("ch", "a", "t", "tr")  # no-op

    async def test_record_agent_start_error(self, svc):
        fake = _fake_redis()
        fake.pipeline.return_value.execute = AsyncMock(
            side_effect=RuntimeError("redis down"))
        svc._redis_client = fake
        await svc.record_agent_start("ch", "a", "t", "tr")  # swallowed

    async def test_record_agent_complete(self, svc):
        fake = _fake_redis()
        svc._redis_client = fake
        svc.publish_progress_update = AsyncMock()
        await svc.record_agent_complete("ch1", "a1", "done", 1500)
        pipe = fake.pipeline.return_value
        pipe.srem.assert_called_once()
        pipe.incrby.assert_called_once()
        svc.publish_progress_update.assert_awaited_once()

    async def test_record_agent_complete_error(self, svc):
        fake = _fake_redis()
        fake.pipeline.return_value.execute = AsyncMock(
            side_effect=RuntimeError("x"))
        svc._redis_client = fake
        await svc.record_agent_complete("ch", "a", "r", 1)

    async def test_record_agent_failed(self, svc):
        fake = _fake_redis()
        svc._redis_client = fake
        svc.publish_progress_update = AsyncMock()
        await svc.record_agent_failed("ch1", "a1", "boom")
        pipe = fake.pipeline.return_value
        pipe.incr.assert_called_once_with("fleet:ch1:counters:failed")
        svc.publish_progress_update.assert_awaited_once()

    async def test_record_agent_failed_error(self, svc):
        fake = _fake_redis()
        fake.pipeline.return_value.execute = AsyncMock(
            side_effect=RuntimeError("x"))
        svc._redis_client = fake
        await svc.record_agent_failed("ch", "a", "e")

    # -- get_fleet_progress ------------------------------------------------------------------------
    async def test_get_fleet_progress_no_redis(self, svc):
        svc._redis_client = None
        svc._get_redis = AsyncMock(return_value=None)
        prog = await svc.get_fleet_progress("ch")
        assert prog.active_count == 0 and prog.agent_details == []

    async def test_get_fleet_progress_bytes(self, svc):
        fake = _fake_redis(
            pipeline_results=[
                {b"a1", b"a2"}, b"2", b"5", b"1",
            ],
            hgetall_map={
                "fleet:ch1:agent:a1": {b"status": b"processing", b"task": b"t"},
                "fleet:ch1:agent:a2": {"status": "completed", "task": "done"},
            })
        svc._redis_client = fake
        prog = await svc.get_fleet_progress("ch1")
        assert sorted(prog.active_agents) == ["a1", "a2"]
        assert prog.processing_count == 2
        assert prog.completed_count == 5
        assert prog.failed_count == 1
        assert len(prog.agent_details) == 2
        assert sorted(d["status"] for d in prog.agent_details) == [
            "completed", "processing"]

    async def test_get_fleet_progress_none_values_and_detail_error(self, svc):
        fake = _fake_redis(
            pipeline_results=[{b"a1"}, None, None, None],
            hgetall_map={})
        fake.hgetall = AsyncMock(side_effect=RuntimeError("hget fail"))
        svc._redis_client = fake
        prog = await svc.get_fleet_progress("ch1")
        assert prog.processing_count == 0
        assert prog.agent_details == []

    async def test_get_fleet_progress_error(self, svc):
        fake = _fake_redis()
        fake.pipeline.return_value.execute = AsyncMock(
            side_effect=RuntimeError("x"))
        svc._redis_client = fake
        prog = await svc.get_fleet_progress("ch1")
        assert prog.active_count == 0

    # -- publish_progress_update ---------------------------------------------------------------------
    async def test_publish_progress_update(self, svc):
        fake = _fake_redis()
        svc._redis_client = fake
        await svc.publish_progress_update("ch", "a", "processing", {"task": "t"})
        fake.publish.assert_awaited_once()
        args = fake.publish.call_args[0]
        assert args[0] == "fleet:progress:ch"
        assert _json.loads(args[1])["agent_id"] == "a"

    async def test_publish_no_redis_and_error(self, svc):
        svc._redis_client = None
        svc._get_redis = AsyncMock(return_value=None)
        await svc.publish_progress_update("ch", "a", "s", {})  # no-op
        fake = _fake_redis()
        fake.publish = AsyncMock(side_effect=RuntimeError("x"))
        svc._redis_client = fake
        await svc.publish_progress_update("ch", "a", "s", {})  # swallowed

    async def test_close(self, svc):
        fake = _fake_redis()
        svc._redis_client = fake
        await svc.close()
        fake.close.assert_awaited_once()
        assert svc._redis_client is None

    def test_singleton_factory(self):
        s1 = get_fleet_progress_service(MagicMock())
        s2 = get_fleet_progress_service(MagicMock())
        assert s1 is s2

    def test_models(self):
        p = FleetProgress(chain_id="c")
        assert AgentStatus.PENDING.value == "pending"
        assert p.active_count == 0


# =========================================================================== #
# 5. core/local_agent_service.py
# =========================================================================== #
import core.local_agent_service as las_mod
from core.local_agent_service import LocalAgentService, get_local_agent_service


class FakeProc:
    def __init__(self, communicate=None, kill_raises=None, returncode=0):
        self._communicate = communicate or (lambda: (b"out", b"err"))
        self._kill_raises = kill_raises
        self.returncode = returncode
        self.killed = False

    async def communicate(self):
        if isinstance(self._communicate, Exception):
            raise self._communicate
        return self._communicate()

    def kill(self):
        self.killed = True
        if self._kill_raises:
            raise self._kill_raises


def _gov_payload(allowed=True, maturity="AUTONOMOUS", **kw):
    return dict({"allowed": allowed, "reason": "ok",
                 "requires_approval": False, "maturity_level": maturity}, **kw)


class TestLocalAgentService:
    @pytest.fixture()
    def svc(self):
        s = LocalAgentService.__new__(LocalAgentService)
        s.backend_url = "http://backend.test"
        s.client = MagicMock()
        s.client.post = AsyncMock()
        s.client.get = AsyncMock()
        s.client.aclose = AsyncMock()
        s.logger = las_mod.logger
        return s

    def _governance(self, svc, payload):
        resp = _http_response(200, payload)
        svc.client.post.return_value = resp

    # -- execute_command branches -----------------------------------------------------------------
    async def test_execute_governance_denied(self, svc):
        self._governance(svc, _gov_payload(allowed=False, reason="nope",
                                           requires_approval=True))
        out = await svc.execute_command("a1", "ls")
        assert out["allowed"] is False
        assert out["requires_approval"] is True

    async def test_execute_invalid_command_blocked_for_all(self, svc):
        self._governance(svc, _gov_payload())
        with patch.object(las_mod, "validate_command",
                          return_value={"valid": False, "reason": "forbidden",
                                        "category": None}), \
             patch.object(las_mod, "get_command_category", return_value=None):
            out = await svc.execute_command("a1", "dangerous-cmd")
        assert out["blocked"] is True
        assert svc.client.post.await_count == 2  # governance + blocked log

    async def test_execute_invalid_command_needs_higher_maturity(self, svc):
        self._governance(svc, _gov_payload(maturity="STUDENT"))
        with patch.object(las_mod, "validate_command",
                          return_value={"valid": False, "reason": "needs autonomy",
                                        "maturity_required": "AUTONOMOUS",
                                        "category": "file_delete"}):
            out = await svc.execute_command("a1", "rm -rf /")
        assert out["requires_approval"] is True
        assert out["maturity_required"] == "AUTONOMOUS"

    async def test_execute_directory_denied(self, svc):
        self._governance(svc, _gov_payload())
        with patch.object(las_mod, "validate_command",
                          return_value={"valid": True}), \
             patch.object(las_mod, "check_directory_permission",
                          return_value={"allowed": False, "reason": "blocked dir",
                                        "resolved_path": "/etc"}):
            out = await svc.execute_command("a1", "ls", working_directory="/etc")
        assert out["blocked_directory"] == "/etc"

    async def test_execute_suggest_only(self, svc):
        self._governance(svc, _gov_payload(maturity="STUDENT"))
        with patch.object(las_mod, "validate_command",
                          return_value={"valid": True}), \
             patch.object(las_mod, "check_directory_permission",
                          return_value={"allowed": True, "suggest_only": True,
                                        "reason": "approval needed",
                                        "resolved_path": "/tmp"}):
            out = await svc.execute_command("a1", "ls", working_directory="/tmp")
        assert out["requires_approval"] is True
        assert out["suggested_command"] == "ls"

    async def test_execute_success(self, svc):
        self._governance(svc, _gov_payload(maturity="AUTONOMOUS"))
        with patch.object(las_mod, "validate_command",
                          return_value={"valid": True}), \
             patch.object(las_mod, "check_directory_permission",
                          return_value={"allowed": True, "suggest_only": False,
                                        "reason": "ok", "resolved_path": "/tmp"}), \
             patch.object(svc, "_execute_locally", AsyncMock(return_value={
                 "exit_code": 0, "stdout": "hi", "stderr": "",
                 "timed_out": False, "duration_seconds": 0.1,
                 "operation_type": "read", "session_id": "sess-1"})):
            out = await svc.execute_command("a1", "ls", working_directory="/tmp")
        assert out["allowed"] is True
        assert out["stdout"] == "hi"
        assert out["maturity_level"] == "AUTONOMOUS"

    async def test_execute_bad_maturity_falls_back_to_student(self, svc):
        self._governance(svc, _gov_payload(maturity="NOT_A_LEVEL"))
        with patch.object(las_mod, "validate_command",
                          return_value={"valid": True}), \
             patch.object(las_mod, "check_directory_permission",
                          return_value={"allowed": True, "suggest_only": False,
                                        "reason": "ok", "resolved_path": "/tmp"}), \
             patch.object(svc, "_execute_locally", AsyncMock(return_value={
                 "exit_code": 0, "stdout": "", "stderr": "",
                 "timed_out": False, "duration_seconds": 0,
                 "operation_type": "execute"})):
            out = await svc.execute_command("a1", "ls")
        assert out["allowed"] is True

    # -- _check_governance ---------------------------------------------------------------------------
    async def test_check_governance_http_error_reraises(self, svc):
        import httpx
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        with pytest.raises(httpx.HTTPError):
            await svc._check_governance("a1", "ls", None)

    # -- _execute_locally ------------------------------------------------------------------------------
    async def test_execute_locally_empty_command(self, svc):
        with pytest.raises(ValueError):
            await svc._execute_locally("   ")

    async def test_execute_locally_bad_directory(self, svc):
        with pytest.raises(ValueError):
            await svc._execute_locally("echo hi", directory="/no/such/dir/xyz")

    async def test_execute_locally_success(self, svc, tmp_path):
        out = await svc._execute_locally("echo hello", directory=str(tmp_path))
        assert out["exit_code"] == 0
        assert out["stdout"].strip() == "hello"
        assert out["operation_type"] == "write"  # echo detected as write
        assert out["timed_out"] is False

    async def test_execute_locally_timeout(self, svc, monkeypatch, tmp_path):
        proc = FakeProc(communicate=RuntimeError("never reached"))
        monkeypatch.setattr(
            las_mod.asyncio, "create_subprocess_exec",
            AsyncMock(return_value=MagicMock(
                communicate=AsyncMock(side_effect=asyncio.TimeoutError),
                kill=lambda: None, returncode=None,
                __class__=type("P", (), {"kill": lambda self: None}))))
        fake = NS(communicate=AsyncMock(side_effect=asyncio.TimeoutError),
                  kill=lambda: None, returncode=None)
        monkeypatch.setattr(
            las_mod.asyncio, "create_subprocess_exec",
            AsyncMock(return_value=fake))
        out = await svc._execute_locally("sleep 999", directory=str(tmp_path))
        assert out["timed_out"] is True
        assert out["exit_code"] == -1
        assert "timed out" in out["stderr"]

    @pytest.mark.parametrize("post_kill_exc", [
        ProcessLookupError(), OSError("os"), RuntimeError("unexpected"),
    ])
    async def test_execute_locally_timeout_communication_errors(
            self, svc, monkeypatch, tmp_path, post_kill_exc):
        fake = NS(communicate=AsyncMock(side_effect=asyncio.TimeoutError),
                  kill=lambda: None, returncode=None)
        second = AsyncMock(side_effect=post_kill_exc)
        monkeypatch.setattr(las_mod.asyncio, "create_subprocess_exec",
                            AsyncMock(return_value=fake))
        # first communicate (in wait_for) raises TimeoutError, second raises exc
        fake.communicate = AsyncMock(side_effect=[asyncio.TimeoutError,
                                                  post_kill_exc])
        out = await svc._execute_locally("sleep 999", directory=str(tmp_path))
        assert out["timed_out"] is True

    # -- _detect_operation_type ---------------------------------------------------------------------------
    @pytest.mark.parametrize("cmd,expected", [
        ("ls", "read"), ("cat", "read"), ("grep", "read"),
        ("cp", "write"), ("mkdir", "write"), ("rm", "write"), ("rmdir", "write"),
        ("python3", "execute"),
    ])
    def test_detect_operation_type(self, svc, cmd, expected):
        assert svc._detect_operation_type(cmd) == expected

    # -- _log_execution ---------------------------------------------------------------------------------
    async def test_log_execution_success(self, svc):
        svc.client.post.return_value = _http_response(200, {})
        await svc._log_execution({"agent_id": "a", "command": "ls -la",
                                  "exit_code": 0})
        svc.client.post.assert_awaited_once()

    async def test_log_execution_http_error_swallowed(self, svc):
        import httpx
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        await svc._log_execution({"agent_id": "a", "command": "ls",
                                  "exit_code": 0})  # no raise

    # -- get_status / close --------------------------------------------------------------------------------
    async def test_get_status_reachable(self, svc):
        svc.client.get.return_value = _http_response(200)
        status = await svc.get_status()
        assert status["backend_reachable"] is True
        assert status["status"] == "running"

    async def test_get_status_request_error(self, svc):
        import httpx
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("down"))
        status = await svc.get_status()
        assert status["status"] == "backend_unreachable"

    async def test_get_status_unexpected_error(self, svc):
        svc.client.get = AsyncMock(side_effect=RuntimeError("weird"))
        status = await svc.get_status()
        assert status["backend_reachable"] is False

    async def test_close(self, svc):
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    def test_singleton_factory(self):
        s1 = get_local_agent_service("http://x.test")
        s2 = get_local_agent_service("http://y.test")
        assert s1 is s2


# =========================================================================== #
# 6. core/formula_extractor.py
# =========================================================================== #
from core.formula_extractor import FormulaExtractor, get_formula_extractor


def _make_xlsx(path, rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for row in rows:
        ws.append(row)
    wb.save(str(path))


class TestFormulaExtractor:
    @pytest.fixture()
    def fx(self):
        return FormulaExtractor()

    # -- extract_from_file dispatch ------------------------------------------------------------------------
    def test_dispatch_xlsx(self, fx, tmp_path):
        p = tmp_path / "f.xlsx"
        _make_xlsx(p, [["Revenue", "Cost", "Profit"],
                        [100, 60, "=A2-B2"],
                        [200, 80, "=SUM(A2:B2)"]])
        with patch.object(fx, "_store_formulas") as store:
            out = fx.extract_from_file(str(p))
        assert any(f["name"] == "Profit" for f in out)
        store.assert_called_once()

    def test_dispatch_gsheet(self, fx, tmp_path, monkeypatch):
        p = tmp_path / "f.gsheet"
        _make_xlsx(p, [["A"], ["=SUM(X1:X2)"]])
        called = {}
        monkeypatch.setattr(fx, "extract_from_excel",
                            lambda *a, **k: called.setdefault("x", True) and [])
        fx.extract_from_file(str(p))
        assert called.get("x")

    def test_dispatch_unsupported(self, fx, tmp_path):
        assert fx.extract_from_file(str(tmp_path / "f.txt")) == []

    # -- xlsx path with error -----------------------------------------------------------------------------
    def test_xlsx_open_error(self, fx, tmp_path):
        assert fx.extract_from_excel(str(tmp_path / "missing.xlsx")) == []

    # -- xls: xlrd not installed -> fallback to excel ---------------------------------------------------------
    def test_xls_fallback_to_excel(self, fx, tmp_path, monkeypatch):
        p = tmp_path / "f.xls"
        _make_xlsx(p, [["A"], ["=SUM(B1:B2)"]])
        out = fx.extract_from_xls(str(p), auto_store=False)
        assert isinstance(out, list)  # xlrd missing -> openpyxl fallback branch

    def test_xls_fallback_error(self, fx, tmp_path):
        assert fx.extract_from_xls(str(tmp_path / "nope.xls")) == []

    # -- helpers for xls (covered directly since xlrd absent) -------------------------------------------------
    def test_xls_parsers_direct(self, fx):
        headers = {1: "Revenue", 2: "Cost"}
        out = fx._parse_xls_formula("=A1-B1", row=1, col=2, headers=headers,
                                    sheet_name="S")
        assert out["name"] == "Column_3"
        assert out["expression"] == "Revenue - Cost"
        fake_sheet = NS(nrows=1, ncols=2,
                        cell=lambda r, c: NS(value="H" if c == 0 else "=A1"))
        assert fx._get_xls_headers(fake_sheet) == {1: "H", 2: "=A1"}

    # -- csv --------------------------------------------------------------------------------------------------
    def test_csv_with_formulas_and_implicit(self, fx, tmp_path):
        p = tmp_path / "f.csv"
        p.write_text(
            "Price,Quantity,Total,Note\n"
            "2,3,6,=SUM(A2:B2)\n"
            "4,5,20,plain\n"
            "6,7,42,x\n")
        out = fx.extract_from_csv(str(p), auto_store=False)
        assert any(f["original_formula"] == "=SUM(A2:B2)" for f in out)
        assert any(f["original_formula"] == "(implicit)" for f in out)

    def test_csv_empty_and_error(self, fx, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("")
        assert fx.extract_from_csv(str(p)) == []
        assert fx.extract_from_csv(str(tmp_path / "ghost.csv")) == []

    def test_csv_implicit_short_rows(self, fx):
        assert fx._detect_implicit_formulas([[ "a" ]], {}) == []
        assert fx._detect_implicit_formulas([["Total"], ["1"], ["2"]], {}) == []

    # -- ods: odfpy not installed -----------------------------------------------------------------------------
    def test_ods_import_error(self, fx, tmp_path):
        assert fx.extract_from_ods(str(tmp_path / "f.ods")) == []

    def test_ods_parser_direct(self, fx):
        out = fx._parse_ods_formula("of:SUM(A1:B1)", row=2, col=1,
                                    headers={1: "Total"}, sheet_name="S")
        assert out["expression"] == "sum(Total, B)"
        assert out["original_formula"] == "=SUM(A1:B1)"
        assert out["name"] == "Column_2"

    # -- semantic helpers ----------------------------------------------------------------------------------------
    @pytest.mark.parametrize("formula,expected_type", [
        ("=SUM(A1:A5)", "SUM"),
        ("=AVERAGE(B1:B2)", "AVERAGE"),
        ("=IF(A1>1,2,3)", "IF"),
        ("=VLOOKUP(A1,B:C,2)", "VLOOKUP"),
        ("=COUNT(A1:A2)", "COUNT"),
        ("=MAX(A1)", "MAX"),
        ("=MIN(A1)", "MIN"),
        ("=COUNTIF(A1:A2,1)", "IF"),  # substring match: IF precedes COUNT
        ("=CONCATENATE(A1,B1)", "CONCATENATE"),
        ("=A1+B1", "ARITHMETIC"),
        ("=SOMETHINGELSE(A1)", "CUSTOM"),
    ])
    def test_detect_formula_type(self, fx, formula, expected_type):
        assert fx._detect_formula_type(formula) == expected_type

    def test_extract_cell_references_dedupe(self, fx):
        refs = fx._extract_cell_references("=A1+B1+$C$3+A2")
        assert refs == [("A", 1), ("B", 2), ("C", 3)]

    def test_column_letter_to_number(self, fx):
        assert fx._column_letter_to_number("A") == 1
        assert fx._column_letter_to_number("Z") == 26
        assert fx._column_letter_to_number("AA") == 27

    @pytest.mark.parametrize("ftype,op,expected", [
        ("ARITHMETIC", "-", "Revenue - Cost"),
        ("ARITHMETIC", "+", "Revenue + Cost"),
        ("ARITHMETIC", "*", "Revenue * Cost"),
        ("ARITHMETIC", "/", "Revenue / Cost"),
    ])
    def test_semantic_expression_arithmetic_ops(self, fx, ftype, op, expected):
        params = [{"name": "Revenue"}, {"name": "Cost"}]
        assert fx._create_semantic_expression(f"=A1{op}B1", ftype, params) == expected

    def test_semantic_expression_sum_avg_default(self, fx):
        assert fx._create_semantic_expression(
            "=SUM(A:A)", "SUM", [{"name": "X"}]) == "sum(X)"
        assert fx._create_semantic_expression(
            "=AVERAGE(A:A)", "AVERAGE", [{"name": "X"}]) == "average(X)"
        assert fx._create_semantic_expression(
            "=IF(A)", "IF", [{"name": "X"}]) == "if(X)"

    @pytest.mark.parametrize("name,domain", [
        ("Revenue", "finance"), ("Sales Total", "sales"),
        ("Inventory Count", "operations"), ("Salary", "hr"),
        ("Campaign Reach", "marketing"), ("Random", "general"),
    ])
    def test_detect_domain(self, fx, name, domain):
        assert fx._detect_domain(name, []) == domain

    def test_generate_use_case_variants(self, fx):
        p = [{"name": "A"}, {"name": "B"}]
        assert "summing" in fx._generate_use_case("T", "SUM", p)
        assert "average" in fx._generate_use_case("T", "AVERAGE", p)
        assert "Compute" in fx._generate_use_case("T", "ARITHMETIC", p)
        assert "VLOOKUP formula" in fx._generate_use_case("T", "VLOOKUP", p)

    # -- store -------------------------------------------------------------------------------------------------------
    def test_store_formulas_with_manager(self, fx):
        manager = MagicMock()
        manager.add_formula.return_value = "fid"
        with patch("core.formula_memory.get_formula_manager", return_value=manager):
            fx._store_formulas([{"expression": "e", "name": "n", "domain": "d",
                                 "use_case": "u", "parameters": []}],
                               "user", "/tmp/somefile.xlsx")
        manager.add_formula.assert_called_once()

    def test_store_formulas_error_per_formula(self, fx):
        manager = MagicMock()
        manager.add_formula.side_effect = RuntimeError("nope")
        with patch("core.formula_memory.get_formula_manager", return_value=manager):
            fx._store_formulas([{"expression": "e", "name": "n", "domain": "d",
                                 "use_case": "u", "parameters": []}], "u", "f")

    def test_factory(self):
        assert isinstance(get_formula_extractor("ws"), FormulaExtractor)


# =========================================================================== #
# 7. api/project_health_routes.py
# =========================================================================== #
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.project_health_routes as phr
from api.project_health_routes import (
    HealthMetric, calculate_overall_score, generate_overall_recommendations,
)


def _metric(name="X", score=50.0, max_score=100.0, status="good"):
    return HealthMetric(name=name, score=score, max_score=max_score,
                        status=status, details={}, trend="stable")


class TestProjectHealthRoutes:
    @pytest.fixture()
    def client(self):
        app = FastAPI()
        app.include_router(phr.router)
        app.dependency_overrides[phr.get_current_user] = lambda: NS(id="u1")
        app.dependency_overrides[phr.get_db] = lambda: MagicMock()
        return TestClient(app)

    # -- endpoint ---------------------------------------------------------------------------------------------
    def test_health_full_payload(self, client):
        res = client.post("/api/v1/projects/health", json={
            "notion_api_key": "k", "notion_database_id": "d",
            "github_owner": "o", "github_repo": "r",
            "slack_channel_id": "c1", "time_range_days": 14})
        assert res.status_code == 200
        body = res.json()
        assert set(body["metrics"]) == {"notion", "github", "slack", "meetings"}
        assert body["overall_status"] in ("excellent", "good", "warning", "critical")
        assert body["recommendations"]

    def test_health_meetings_only(self, client):
        res = client.post("/api/v1/projects/health", json={})
        assert res.status_code == 200
        assert set(res.json()["metrics"]) == {"meetings"}

    def test_health_notion_missing_database(self, client):
        res = client.post("/api/v1/projects/health", json={"notion_api_key": "k"})
        assert res.status_code == 200
        assert "notion" not in res.json()["metrics"]

    def test_health_calculator_exception_skipped(self, client, monkeypatch):
        async def boom(*a, **k):
            raise RuntimeError("calc boom")
        monkeypatch.setattr(phr, "calculate_meeting_health", boom)
        res = client.post("/api/v1/projects/health", json={})
        assert res.status_code == 400  # no metrics at all

    def test_health_internal_error_500(self, client, monkeypatch):
        monkeypatch.setattr(phr, "calculate_overall_score",
                            Mock(side_effect=RuntimeError("boom")))
        res = client.post("/api/v1/projects/health", json={})
        assert res.status_code == 500

    def test_templates_endpoint(self, client):
        res = client.get("/api/v1/projects/health/templates")
        assert res.status_code == 200
        assert res.json()["total"] == 4

    # -- individual calculators ---------------------------------------------------------------------------------
    async def test_calculators(self):
        m = await phr.calculate_notion_health("k", "d", 7)
        assert m.status == "good"
        m = await phr.calculate_github_health("o", "r", 7)
        assert m.name == "Code Health"
        m = await phr.calculate_slack_health("chan", 7)
        assert m.name == "Communication"
        m = await phr.calculate_meeting_health(7)
        assert m.trend == "stable"

    # -- score / recommendations ----------------------------------------------------------------------------------
    @pytest.mark.parametrize("score,expected", [
        (85, "excellent"), (70, "good"), (50, "warning"), (10, "critical"),
    ])
    def test_overall_score_statuses(self, score, expected):
        s, st = calculate_overall_score({"m": _metric(score=score)})
        assert st == expected

    def test_overall_score_empty(self):
        assert calculate_overall_score({}) == (0.0, "unknown")

    def test_recommendations_warning_metrics(self):
        recs = generate_overall_recommendations({
            "notion": _metric("Task Management", status="warning"),
            "github": _metric("Code Health", status="critical"),
            "slack": _metric("Communication", status="warning"),
            "meetings": _metric("Meeting Balance", status="critical"),
        })
        assert len(recs) == 4

    def test_recommendations_all_good(self):
        assert "Project health is good! Maintain current practices." in generate_overall_recommendations(
            {"notion": _metric("Task Management", status="good")})


# =========================================================================== #
# 8. core/cache.py
# =========================================================================== #
import core.cache as cache_mod
from core.cache import (
    CircuitBreakerOpenError, CircuitState, RedisCircuitBreaker,
    SyncLocalCache, UniversalCacheService,
)


class TestRedisCircuitBreaker:
    def test_success_and_state(self):
        cb = RedisCircuitBreaker(failure_threshold=2, recovery_timeout=60)
        assert cb.call(lambda: "ok") == "ok"
        assert cb.get_state() == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = RedisCircuitBreaker(failure_threshold=2, recovery_timeout=60)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(Mock(side_effect=ValueError("fail")))
        assert cb.get_state() == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "x")

    def test_half_open_recovery(self):
        cb = RedisCircuitBreaker(failure_threshold=1, recovery_timeout=0)
        with pytest.raises(ValueError):
            cb.call(Mock(side_effect=ValueError("fail")))
        assert cb.get_state() == CircuitState.OPEN
        # recovery_timeout=0 -> immediately eligible for reset
        assert cb.call(lambda: "recovered") == "recovered"
        assert cb.get_state() == CircuitState.CLOSED

    def test_half_open_fails_again(self):
        cb = RedisCircuitBreaker(failure_threshold=1, recovery_timeout=0)
        with pytest.raises(ValueError):
            cb.call(Mock(side_effect=ValueError("f")))
        with pytest.raises(ValueError):
            cb.call(Mock(side_effect=ValueError("f")))
        assert cb.get_state() == CircuitState.OPEN

    def test_should_attempt_reset_no_failure_time(self):
        cb = RedisCircuitBreaker()
        assert cb._should_attempt_reset() is True

    def test_reset(self):
        cb = RedisCircuitBreaker(failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(Mock(side_effect=ValueError("f")))
        cb.reset()
        assert cb.get_state() == CircuitState.CLOSED


class TestSyncLocalCache:
    def test_get_set_delete(self):
        c = SyncLocalCache(max_size=10, default_ttl=60)
        assert c.get("missing") is None
        c.set("k", "v")
        assert c.get("k") == "v"
        c.delete("k")
        assert c.get("k") is None

    def test_expiry(self):
        c = SyncLocalCache(default_ttl=60)
        c.set("k", "v", ttl=-1)  # already expired
        assert c.get("k") is None
        assert c.misses >= 1

    def test_lru_eviction(self):
        c = SyncLocalCache(max_size=2, default_ttl=60)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")  # a becomes most recent
        c.set("c", 3)  # evicts b
        assert c.get("b") is None
        assert c.get("a") == 1

    def test_update_existing_no_eviction(self):
        c = SyncLocalCache(max_size=2, default_ttl=60)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 10)  # update, not insert
        assert c.get("a") == 10
        assert c.get("b") == 2

    def test_clear(self):
        c = SyncLocalCache()
        c.set("k", 1)
        c.get("k")
        c.clear()
        assert c.hits == 0 and c.misses == 0 and c.get("k") is None


class TestUniversalCacheService:
    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch):
        self.orig = UniversalCacheService._instance
        UniversalCacheService._instance = None
        yield
        UniversalCacheService._instance = self.orig

    @pytest.fixture()
    def cache(self, monkeypatch):
        monkeypatch.delenv("DRAGONFLY_URL", raising=False)
        monkeypatch.delenv("CACHE_REDIS_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
        monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
        monkeypatch.setenv("ENABLE_CACHE", "true")
        c = UniversalCacheService()
        yield c
        try:
            asyncio.get_event_loop()
        except Exception:
            pass

    # -- init branches ------------------------------------------------------------------
    def test_init_disabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CACHE", "false")
        UniversalCacheService._instance = None
        c = UniversalCacheService()
        assert c.enabled is False
        assert c.client is None

    def test_init_bad_redis_url(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
        UniversalCacheService._instance = None
        c = UniversalCacheService()
        assert c.client is None  # connection fails -> local memory

    def test_init_rest_fallback(self, monkeypatch):
        monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://cache.rest")
        monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "tok")
        UniversalCacheService._instance = None
        c = UniversalCacheService()
        assert c.use_rest_api is True

    def test_init_local_only(self, cache):
        assert cache.client is None and cache.use_rest_api is False

    # -- namespace/encode/decode -----------------------------------------------------------
    def test_namespace_key(self, cache):
        assert cache._namespace_key("k", "t1") == "tenant:t1:k"
        assert cache._namespace_key("k") == "k"

    def test_encode_decode(self, cache):
        assert cache._encode({"a": 1}) == '{"a": 1}'
        assert cache._encode("s") == "s"
        assert cache._decode('{"a": 1}') == {"a": 1}
        assert cache._decode("not json") == "not json"
        assert cache._decode(None) is None

    # -- sync get/set -------------------------------------------------------------------------
    def test_get_set_local(self, cache):
        assert cache.set("k", {"v": 1}, ttl=60) is True
        assert cache.get("k") == {"v": 1}
        assert cache.get("missing") is None

    def test_get_disabled(self, monkeypatch):
        UniversalCacheService._instance = None
        monkeypatch.setenv("ENABLE_CACHE", "false")
        c = UniversalCacheService()
        assert c.get("k") is None
        assert c.set("k", 1) is False

    def test_get_set_with_redis_client(self, cache):
        fake = MagicMock()
        fake.get.return_value = '{"x": 2}'
        cache.client = fake
        assert cache.get("k") == {"x": 2}
        cache.set("k", {"x": 2})
        fake.setex.assert_called_once()

    def test_get_redis_falsy_value_is_hit(self, cache):
        fake = MagicMock()
        fake.get.return_value = "0"
        cache.client = fake
        assert cache.get("k") == 0  # falsy JSON decodes to 0, still a hit

    def test_get_redis_error_falls_back_local(self, cache):
        cache.set("k", "local")
        fake = MagicMock()
        fake.get.side_effect = ConnectionError("down")
        cache.client = fake
        assert cache.get("k") == "local"

    def test_async_get_set_delete(self, cache):
        assert asyncio.get_event_loop()
        async def run():
            assert await cache.set_async("ak", [1, 2], ttl=30) is True
            assert await cache.get_async("ak") == [1, 2]
            assert await cache.get_async("nope") is None
            await cache.delete_async("ak")
            assert await cache.get_async("ak") is None
        asyncio.run(run())

    async def test_async_get_set_with_redis(self, cache):
        fake = MagicMock()
        fake.get.return_value = "42"
        cache.client = fake
        assert await cache.get_async("k") == 42
        await cache.set_async("k", 42)
        fake.setex.assert_called_once()

    async def test_async_get_disabled(self, monkeypatch):
        UniversalCacheService._instance = None
        monkeypatch.setenv("ENABLE_CACHE", "false")
        c = UniversalCacheService()
        assert await c.get_async("k") is None
        assert await c.set_async("k", 1) is False

    def test_sync_delete_with_backends(self, cache):
        fake = MagicMock()
        cache.client = fake
        cache.use_rest_api = True
        with patch.object(cache, "_rest_delete", return_value=True) as rd:
            cache.delete("k")
        fake.delete.assert_called_once()
        rd.assert_called_once()

    # -- REST API paths ---------------------------------------------------------------------------
    def test_rest_paths(self, cache):
        cache.use_rest_api = True
        cache.rest_api_url = "https://rest"
        cache.rest_api_token = "tok"
        with patch.object(cache_mod.httpx, "get", return_value=_http_response(
                200, {"result": "val"})) as hg, \
             patch.object(cache_mod.httpx, "post", return_value=_http_response(
                 200)) as hp:
            assert cache._rest_get("k") == "val"
            assert cache._rest_set("k", "v", 30) is True
            assert cache.get("rk") == "val"
            cache.set("rk", "v")
        assert hg.call_count == 2 and hp.call_count == 2  # direct + via get()/set()

    def test_rest_paths_disabled(self, cache):
        cache.use_rest_api = False
        assert cache._rest_get("k") is None
        assert cache._rest_set("k", "v", 1) is False
        assert cache._rest_delete("k") is False
        assert cache._rest_incr("k") is None

    def test_rest_error_paths(self, cache):
        cache.use_rest_api = True
        cache.rest_api_url = "https://rest"
        with patch.object(cache_mod.httpx, "get",
                          side_effect=RuntimeError("net")) as hg, \
             patch.object(cache_mod.httpx, "post",
                          side_effect=RuntimeError("net")):
            assert cache._rest_get("k") is None
            assert cache._rest_set("k", "v", 1) is False
            assert cache._rest_delete("k") is False
            assert cache._rest_incr("k") is None

    def test_rest_non_200(self, cache):
        cache.use_rest_api = True
        cache.rest_api_url = "https://rest"
        with patch.object(cache_mod.httpx, "get", return_value=_http_response(500)):
            assert cache._rest_delete("k") is False
            assert cache._rest_incr("k") is None

    # -- incr ------------------------------------------------------------------------------------------
    async def test_incr_redis_pipeline(self, cache):
        fake = MagicMock()
        pipe = MagicMock()
        pipe.execute.return_value = ["5", True]
        fake.pipeline.return_value = pipe
        cache.client = fake
        assert await cache.incr_async("rl") == 5

    async def test_incr_redis_error_to_local(self, cache):
        fake = MagicMock()
        fake.pipeline.return_value.execute.side_effect = ConnectionError("down")
        cache.client = fake
        v1 = await cache.incr_async("rl")
        v2 = await cache.incr_async("rl")
        assert (v1, v2) == (1, 2)

    async def test_incr_rest(self, cache):
        cache.use_rest_api = True
        cache.rest_api_url = "https://rest"
        with patch.object(cache, "_rest_incr", return_value=1), \
             patch.object(cache_mod.httpx, "get", return_value=_http_response(200)):
            assert await cache.incr_async("rl") == 1
        # val != 1 skips expire call
        with patch.object(cache, "_rest_incr", return_value=4):
            assert await cache.incr_async("rl") == 4

    async def test_incr_disabled(self, monkeypatch):
        UniversalCacheService._instance = None
        monkeypatch.setenv("ENABLE_CACHE", "false")
        c = UniversalCacheService()
        assert await c.incr_async("k") == 1

    # -- delete_tenant_all ----------------------------------------------------------------------------------
    async def test_delete_tenant_all_local_and_redis(self, cache):
        cache.set("tenant:t1:a", 1)
        cache.set("tenant:t1:b", 2)
        cache.set("tenant:t2:c", 3)
        fake = MagicMock()
        fake.get.return_value = None
        fake.scan_iter.return_value = iter(["tenant:t1:a", "tenant:t1:b"])
        fake.delete.return_value = 2
        cache.client = fake
        assert await cache.delete_tenant_all("t1") == 2
        assert cache.sync_local_cache.get("tenant:t2:c") == 3
        assert cache.sync_local_cache.get("tenant:t1:a") is None

    async def test_delete_tenant_all_pattern_and_disabled(self, cache):
        fake = MagicMock()
        fake.scan_iter.return_value = iter([])
        cache.client = fake
        assert await cache.delete_tenant_all("tenant:x:") == 0
        cache.enabled = False
        assert await cache.delete_tenant_all("zz") == 0

    async def test_delete_tenant_all_redis_error(self, cache):
        fake = MagicMock()
        fake.scan_iter.side_effect = ConnectionError("down")
        cache.client = fake
        assert await cache.delete_tenant_all("t9") == 0

    # -- status ------------------------------------------------------------------------------------------------
    def test_get_status_local(self, cache):
        s = cache.get_status()
        assert s["mode"] == "local_memory" and s["status"] == "operational"

    def test_get_status_redis_degraded(self, cache):
        fake = MagicMock()
        fake.ping.side_effect = ConnectionError("down")
        cache.client = fake
        assert cache.get_status()["status"] == "degraded"

    def test_get_status_redis_ok(self, cache):
        fake = MagicMock()
        cache.client = fake
        s = cache.get_status()
        assert s["status"] == "operational" and s["mode"] == "redis"

    def test_get_status_rest(self, cache):
        cache.use_rest_api = True
        cache.rest_api_url = "https://r"
        cache.rest_api_token = "t"
        assert cache.get_status()["mode"] == "upstash_rest"

    def test_get_status_rest_degraded(self, cache):
        cache.use_rest_api = True
        cache.rest_api_url = ""
        cache.rest_api_token = ""
        assert cache.get_status()["status"] == "degraded"

    def test_get_status_disabled(self, monkeypatch):
        UniversalCacheService._instance = None
        monkeypatch.setenv("ENABLE_CACHE", "false")
        c = UniversalCacheService()
        assert c.get_status()["status"] == "disabled"

    def test_circuit_state_accessor(self, cache):
        assert cache.get_circuit_state() == "closed"

    def test_legacy_alias(self):
        assert cache_mod.RedisCacheService is UniversalCacheService
        assert cache_mod.redis_cache is cache_mod.cache


# =========================================================================== #
# 9. core/openclaw_parser.py
# =========================================================================== #
from core.openclaw_parser import OpenClawParser, _quote_at_scalars


SKILL_FULL = """---
name: my-skill
description: Does something useful
author: @alice
version: 2.1.0
homepage: https://example.test
requirements:
  - numpy
  - 3.5
node_packages:
  - react
metadata:
  openclaw:
    install:
      - id: uv
        kind: uv
        package: nano-pdf
      - id: npm
        kind: npm
        package: lodash
      - id: bins
        kind: custom
        bins:
          - ffmpeg
          - 7
---

# Skill

```python
x = 1 + 2
```

```python
y = x * 3
```
"""


class TestOpenClawParser:
    @pytest.fixture()
    def parser(self):
        return OpenClawParser()

    def test_parse_full(self, parser):
        out = parser.parse_skill_md(SKILL_FULL)
        assert out["name"] == "my-skill"
        assert out["author"] == "@alice"
        assert out["version"] == "2.1.0"
        assert out["homepage"] == "https://example.test"
        assert len(out["code_blocks"]) == 2
        assert "numpy" in out["dependencies"]["python"]
        assert "nano-pdf" in out["dependencies"]["python"]
        assert "react" in out["dependencies"]["npm"]
        assert "lodash" in out["dependencies"]["npm"]
        assert "ffmpeg" in out["dependencies"]["bins"]
        assert out["raw_md"] == SKILL_FULL

    def test_parse_defaults(self, parser):
        md = "---\nname: s\ndescription: d\n---\nbody text"
        out = parser.parse_skill_md(md)
        assert out["author"] == "Unknown"
        assert out["version"] == "1.0.0"
        assert out["homepage"] is None
        assert out["dependencies"] == {"python": [], "npm": [], "bins": []}

    def test_parse_missing_required_fields(self, parser):
        with pytest.raises(ValueError, match="Missing required fields"):
            parser.parse_skill_md("---\nname: only-name\n---\nbody")

    def test_parse_failure_wrapped(self, parser):
        with pytest.raises(ValueError, match="Failed to parse SKILL.md"):
            parser.parse_skill_md("---\nname: {a\n---\nbody")

    def test_quote_at_scalars(self):
        assert _quote_at_scalars("plain") == "plain"
        quoted = _quote_at_scalars("---\nauthor: @bob\n---\nx")
        assert '"@bob"' in quoted
        # value with trailing content preserved
        q2 = _quote_at_scalars("---\nkey:   @val # comment\n---\n")
        assert '"@val"' in q2 and "# comment" in q2
        # non-@ values untouched
        assert _quote_at_scalars("---\na: b\n---\n") == "---\na: b\n---\n"

    def test_extract_python_blocks(self, parser):
        md = "```python\na=1\n```\n\ntext\n```python\nb=2\n```"
        assert len(parser._extract_python_blocks(md)) == 2
        assert parser._extract_python_blocks("no code") == []

    def test_validate_python_syntax(self, parser):
        assert parser.validate_python_syntax("x = 1\n") == (True, "")
        ok, err = parser.validate_python_syntax("def f(:\n")
        assert ok is False and err.startswith("Line ")

    def test_extract_npm_dependencies(self, parser):
        code = (
            "import React from 'react';\n"
            "import { useState } from \"react\";\n"
            "import * as X from '@scope/pkg';\n"
            "import './local.css';\n"
            "import '/abs/path';\n"
            "import 'side-effect';\n"
            "const fs = require('fs');\n"
            "const rel = require('./util');\n"
        )
        deps = parser.extract_npm_dependencies(code, "Comp")
        assert deps == ["@scope/pkg", "fs", "react", "side-effect"]

    def test_extract_npm_package_json_block(self, parser):
        code = ('// package.json\n"dependencies": {"react": "^18", '
                '"@scope/ui": "1.0"}')
        deps = parser.extract_npm_dependencies(code, "Comp")
        assert "react" in deps and "@scope/ui" in deps

    def test_extract_npm_package_json_no_match(self, parser):
        code = 'package.json mentions dependencies but no object'
        assert parser.extract_npm_dependencies(code, "C") == []

    def test_extract_dependencies_non_list_and_non_dict(self, parser):
        deps = parser._extract_dependencies({
            "requirements": "not-a-list",
            "node_packages": 42,
            "metadata": "not-a-dict",
        })
        assert deps == {"python": [], "npm": [], "bins": []}

    def test_extract_dependencies_malformed_steps(self, parser):
        deps = parser._extract_dependencies({
            "metadata": {"openclaw": {"install": [
                "not-a-dict",
                {"kind": "uv", "package": 123},      # non-str package skipped
                {"kind": "npm", "package": None},    # None skipped
                {"kind": "uv", "package": "ok-pkg"},
                {"bins": ["b1", None, 2]},           # mixed bins
            ]}}
        })
        assert deps["python"] == ["ok-pkg"]
        assert deps["bins"] == ["b1", "2"]


# =========================================================================== #
# 10. core/webhook_renewal_service.py
# =========================================================================== #
import core.webhook_renewal_service as wrs_mod
from core.webhook_renewal_service import (
    ScheduledWebhookRenewalService, supports_drive_subscription,
)


def _conn(integration_id="github", **kw):
    c = NS(
        id="conn-1", integration_id=integration_id, tenant_id="t1",
        credentials="encrypted", status="active",
        last_refresh_at=datetime.now(timezone.utc) - timedelta(days=30),
        updated_at=None, created_at=None, expires_at=None,
        refresh_failure_count=0, last_refresh_error=None,
    )
    for k, v in kw.items():
        setattr(c, k, v)
    return c


class TestWebhookRenewalService:
    @pytest.fixture()
    def svc(self):
        with patch.object(wrs_mod, "ConnectionService") as CS:
            CS.return_value._decrypt = Mock(return_value={"access_token": "tok"})
            CS.return_value._encrypt = Mock(side_effect=lambda c: "encrypted")
            CS.return_value._refresh_token_if_needed = AsyncMock(return_value=None)
            s = ScheduledWebhookRenewalService(MagicMock())
            s._cs = CS.return_value
            yield s

    # -- pure helpers ------------------------------------------------------------------
    def test_supports_drive_subscription(self):
        assert supports_drive_subscription("microsoft365") is True
        assert supports_drive_subscription("outlook") is False

    @pytest.mark.parametrize("iid,expected", [
        ("outlook", "tier_1_critical"), ("gmail", "tier_1_critical"),
        ("slack", "tier_1_critical"), ("salesforce", "tier_1_critical"),
        ("microsoft365", "tier_1_critical"),
        ("hubspot", "tier_2_business"), ("notion", "tier_2_business"),
        ("jira", "tier_2_business"), ("github", "tier_2_business"),
        ("asana", "tier_3_productivity"), ("trello", "tier_3_productivity"),
        ("monday", "tier_3_productivity"), ("figma", "tier_3_productivity"),
        ("unknown", "tier_4_nice_to_have"),
    ])
    def test_tier_for_integration(self, svc, iid, expected):
        assert svc.get_tier_for_integration(iid) == expected

    @pytest.mark.parametrize("tier,hours", [
        ("tier_1_critical", 12.0), ("tier_2_business", 24.0),
        ("tier_3_productivity", 48.0), ("other", 168.0),
    ])
    def test_renewal_interval(self, svc, tier, hours):
        assert svc.get_renewal_interval_hours(tier) == hours

    def test_is_renewal_due_variants(self, svc):
        assert svc.is_renewal_due(_conn(last_refresh_at=None, updated_at=None,
                                        created_at=None)) is True
        # naive datetime gets tz-assumed (40 days ago -> due for tier 2)
        assert svc.is_renewal_due(
            _conn(last_refresh_at=datetime.utcnow().replace(tzinfo=None)
                  - timedelta(days=40))) is True
        assert svc.is_renewal_due(
            _conn(last_refresh_at=datetime.now(timezone.utc))) is False
        # tier 4 needs 168h: 30d old github connection is due
        assert svc.is_renewal_due(_conn()) is True

    # -- renew_subscription_for_connection ----------------------------------------------------
    async def test_renew_decrypt_failure(self, svc):
        svc._cs._decrypt.return_value = None
        out = await svc.renew_subscription_for_connection(_conn())
        assert out == {"status": "failed", "error": "Decryption failure"}
        assert svc.db.commit.called

    async def test_renew_token_refresh_with_expiry(self, svc):
        svc._cs._refresh_token_if_needed.return_value = {
            "access_token": "new", "expires_in": 3600}
        with patch.object(svc, "_handle_failure"):
            # general integration -> recreated
            out = await svc.renew_subscription_for_connection(_conn())
        assert out["status"] == "success"
        assert out["action"] == "recreated"

    async def test_renew_outlook_no_subscription_ids(self, svc):
        conn = _conn(integration_id="outlook")
        out = await svc.renew_subscription_for_connection(conn)
        assert out["action"] == "recreated"

    async def test_renew_outlook_success_and_drive_cleanup(self, svc):
        conn = _conn(integration_id="outlook",
                     credentials=None)
        svc._cs._decrypt.return_value = {
            "access_token": "tok",
            "subscription_ids": ["sub-1", "sub-drive"],
        }
        client = _async_client()
        client.get = AsyncMock(return_value=_http_response(200, {"value": [
            {"id": "sub-1", "resource": "/me/messages"},
            {"id": "sub-drive", "resource": "/me/drive/root"},
        ]}))
        client.delete = AsyncMock(return_value=_http_response(204))
        with patch("httpx.AsyncClient", _HC(client)), \
             patch("integrations.microsoft365_service.microsoft365_service") as ms:
            ms.renew_subscription = AsyncMock(
                return_value={"status": "renewed"})
            out = await svc.renew_subscription_for_connection(conn)
        assert out["status"] == "success"
        client.delete.assert_called_once()  # legacy drive sub removed

    async def test_renew_outlook_renewal_error_recreates(self, svc):
        conn = _conn(integration_id="microsoft365")
        svc._cs._decrypt.return_value = {
            "access_token": "tok", "subscription_ids": ["sub-1"]}
        listing = _http_response(200, {"value": [
            {"id": "sub-1", "resource": "/me/messages"}]})
        client = MagicMock()
        client.get.return_value = listing
        with patch("httpx.AsyncClient", _HC(client)), \
             patch("integrations.microsoft365_service.microsoft365_service") as ms:
            ms.renew_subscription = AsyncMock(
                return_value={"status": "error", "message": "expired"})
            out = await svc.renew_subscription_for_connection(conn)
        assert out["action"] == "recreated"

    async def test_renew_exception_calls_handle_failure(self, svc):
        conn = _conn(integration_id="outlook")
        svc._cs._decrypt.return_value = {
            "access_token": "tok", "subscription_ids": ["sub-x"]}
        listing = _http_response(200, {"value": [
            {"id": "sub-x", "resource": "/me/messages"}]})
        client = _async_client()
        client.get = AsyncMock(return_value=listing)
        with patch("httpx.AsyncClient", _HC(client)), \
             patch("integrations.microsoft365_service.microsoft365_service") as ms:
            ms.renew_subscription = AsyncMock(
                side_effect=RuntimeError("graph down"))
            out = await svc.renew_subscription_for_connection(conn)
        assert out["status"] == "failed"
        assert out["error"] == "graph down"

    # -- _handle_failure -------------------------------------------------------------------------
    def test_handle_failure_below_threshold(self, svc):
        conn = _conn(refresh_failure_count=1)
        svc._handle_failure(conn, "err")
        assert conn.refresh_failure_count == 2
        assert conn.status == "active"

    def test_handle_failure_marks_error_and_alerts(self, svc):
        conn = _conn(refresh_failure_count=2)
        svc._handle_failure(conn, "err again")
        assert conn.status == "error"
        assert svc.db.add.called  # TrainingAlert recorded

    def test_handle_failure_alert_error_swallowed(self, svc):
        conn = _conn(refresh_failure_count=2)
        svc.db.add = Mock(side_effect=RuntimeError("alert fail"))
        svc._handle_failure(conn, "e")  # no raise
        assert svc.db.commit.called

    # -- run_staggered_renewal_cycle ------------------------------------------------------------------
    async def test_cycle_mixed_outcomes(self, svc, monkeypatch):
        due_conn = _conn(id="c-due")                     # due -> renewed
        not_due = _conn(id="c-fresh",
                        last_refresh_at=datetime.now(timezone.utc))
        results = [
            FakeQuery(items=[NS(id="c-due"), NS(id="c-fresh"), NS(id="c-gone")]),
            FakeQuery(first=due_conn), FakeQuery(first=not_due), FakeQuery(first=None),
        ]
        svc.db = MagicMock()
        svc.db.query = Mock(side_effect=lambda *a, **k: results.pop(0))
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        with patch.object(svc, "renew_subscription_for_connection",
                          AsyncMock(return_value={"status": "success",
                                                  "action": "recreated"})):
            out = await svc.run_staggered_renewal_cycle()
        assert out["total_checked"] == 3
        assert out["renewed"] == 1
        assert out["skipped"] == 2
        assert out["failed"] == 0

    async def test_cycle_failure_counted(self, svc, monkeypatch):
        due_conn = _conn(id="c1")
        results = [FakeQuery(items=[NS(id="c1")]), FakeQuery(first=due_conn)]
        svc.db = MagicMock()
        svc.db.query = Mock(side_effect=lambda *a, **k: results.pop(0))
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        with patch.object(svc, "renew_subscription_for_connection",
                          AsyncMock(return_value={"status": "failed",
                                                  "error": "x"})):
            out = await svc.run_staggered_renewal_cycle()
        assert out["failed"] == 1

    async def test_cycle_real_db_sessionlocal(self, svc, monkeypatch):
        # non-mock db path: SessionLocal() used per connection
        due_conn = _conn(id="cx")

        class InitialDB:
            def query(self, *a, **k):
                return FakeQuery(items=[("cx",)])

        class SessionDB:
            def __init__(self):
                self.closed = False

            def query(self, *a, **k):
                return FakeQuery(first=due_conn)

            def close(self):
                self.closed = True

        session = SessionDB()
        svc.db = InitialDB()
        monkeypatch.setattr("core.database.SessionLocal", lambda: session)
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        with patch.object(svc, "renew_subscription_for_connection",
                          AsyncMock(return_value={"status": "success"})):
            out = await svc.run_staggered_renewal_cycle()
        assert out["renewed"] == 1
        assert session.closed
