# -*- coding: utf-8 -*-
"""Coverage wave 102 (last-100 push) — final residual-branch closure for:

1. integrations/atom_communication_memory_production_api.py
2. integrations/atom_communication_apps_lancedb_integration.py
3. integrations/ai_routes.py

Line coverage for all three was already 100% via waves 92/94/96; the only
residual gaps were partial branches (measured with --cov-branch):

- production_api: search time-range path with falsy app_id (247->251) and
  falsy query (251->258); analytics record whose direction is not one of
  inbound/outbound/internal (357->361); record without a "timestamp" key
  (369->350); db-walk filename whose path does not exist (410->408).
- lancedb: batch ingest with memory_manager already initialized (367->371).
- ai_routes: already 100% incl. branches — smoke tests keep it pinned.

Fully mocked (no network / no LanceDB / no LLM).
"""
import asyncio
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.security_dependencies import get_current_user as ai_get_current_user

from integrations import ai_routes as ar
from integrations import atom_communication_memory_production_api as prod_mod
from integrations import atom_communication_apps_lancedb_integration as lancedb_intgr
from integrations.atom_communication_ingestion_pipeline import (
    ingestion_pipeline,
    memory_manager,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ── production_api ───────────────────────────────────────────────────────────
@pytest.fixture
def prod_user():
    u = MagicMock()
    u.id = f"w102-{uuid.uuid4().hex[:8]}"
    return u


@pytest.fixture
def prod_client(prod_user):
    app = FastAPI()
    app.include_router(prod_mod.atom_memory_production_router)
    app.dependency_overrides[get_current_user] = lambda: prod_user
    app.dependency_overrides[
        prod_mod.atom_memory_production_api.verify_token
    ] = lambda: {"sub": "user-102"}
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestProductionApiBranchGaps:
    def test_search_time_range_without_app_and_empty_query(self, prod_client):
        """time-range branch with app_id falsy AND query falsy ('')."""
        results = [
            {"app_type": "whatsapp", "content": "alpha"},
            {"app_type": "slack", "content": "beta"},
        ]
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "get_communications_by_timeframe",
                             return_value=results) as tf:
            response = prod_client.get(
                "/api/atom/communication/memory/search/production",
                params={"query": "",  # falsy -> no content filter
                        "time_start": "2026-08-01T00:00:00",
                        "time_end": "2026-08-31T00:00:00"})
        assert response.status_code == 200
        tf.assert_called_once()
        body = response.json()
        # no app filter, no query filter -> both records survive
        assert body["total_results"] == 2

    def test_analytics_unknown_direction_and_missing_timestamp(self, prod_client):
        """direction outside {inbound,outbound,internal} and record lacking
        a timestamp key (timeline skipped)."""
        # NOTE: pandas pads per-row missing keys with NaN, so to make
        # "timestamp" genuinely absent from the record dicts the whole
        # frame must lack the column.
        frame = pd.DataFrame([
            {"app_type": "telegram", "content": "a",
             "direction": "archived",  # not tracked
             "priority": "low", "status": "queued", "attachments": "[]"},
            {"app_type": "telegram", "content": "b",
             "direction": "inbound",
             "priority": "normal", "status": "delivered", "attachments": "[]"},
        ])
        conn = MagicMock()
        conn.to_pandas.return_value = frame
        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path",
                             new=__import__("pathlib").Path(
                                 "/nonexistent/db/w102")), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}):
            response = prod_client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 200
        analytics = response.json()["analytics"]
        assert analytics["summary"]["total_messages"] == 2
        # unknown direction never counted
        assert analytics["direction_distribution"] == {
            "inbound": 1, "outbound": 0, "internal": 0}
        # no timestamps at all -> empty timeline
        assert analytics["timeline_data"] == {}

    def test_analytics_walk_with_vanished_file(self, prod_client, tmp_path):
        """db-walk yields a filename whose path fails os.path.exists."""
        (tmp_path / "gone.lance").write_bytes(b"x" * 10)
        conn = MagicMock()
        conn.to_pandas.return_value = pd.DataFrame([
            {"app_type": "whatsapp", "timestamp": "2026-08-01T10:00:00",
             "content": "c", "direction": "inbound", "priority": "normal",
             "status": "delivered", "attachments": "[]"},
        ])
        real_exists = os.path.exists

        def _exists(path):
            # db dir itself exists, walked files appear to have vanished
            if str(path) == str(tmp_path):
                return real_exists(path)
            return False

        with patch.object(memory_manager, "db", new=object()), \
                patch.object(memory_manager, "connections_table", new=conn), \
                patch.object(memory_manager, "db_path", new=tmp_path), \
                patch.object(ingestion_pipeline, "get_ingestion_stats",
                             return_value={"configured_apps": []}), \
                patch.object(os.path, "exists", side_effect=_exists), \
                patch.object(os.path, "getsize", return_value=5) as _gs:
            response = prod_client.get(
                "/api/atom/communication/memory/analytics/production")
        assert response.status_code == 200
        detail = response.json()["analytics"]["detailed_metrics"]
        # vanished file contributes nothing to the on-disk size
        assert "storage_efficiency" in detail
        _gs.assert_not_called()


# ── lancedb integration ──────────────────────────────────────────────────────
def _route(router, path, method="POST"):
    for r in router.routes:
        if getattr(r, "path", None) == path and method in (r.methods or set()):
            return r.endpoint
    raise AssertionError(f"route {method} {path} not found")


class TestLancedbBranchGaps:
    def test_batch_ingest_with_memory_already_initialized(self):
        """memory_manager.db is NOT None -> initialize() skipped (367->371)."""
        mm = Mock()
        mm.db = Mock()  # already initialized
        mm.initialize = Mock()
        with patch.object(lancedb_intgr, "memory_manager", mm), \
                patch.object(lancedb_intgr, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            result = asyncio.run(_route(
                lancedb_intgr.CommunicationAppIngestionIntegration().router,
                "/api/memory/ingestion/ingest/{app_id}/batch")(
                app_id="slack", messages=[{"id": "m1"}, {"id": "m2"}]))
        mm.initialize.assert_not_called()
        assert result["success_count"] == 2
        assert result["failure_count"] == 0


# ── ai_routes (already 100% — pin it) ────────────────────────────────────────
@pytest.fixture
def ai_client():
    app = FastAPI()
    app.include_router(ar.router)
    app.dependency_overrides[ai_get_current_user] = lambda: MagicMock(
        id="u102", tenant_id="t102")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestAiRoutesSmoke:
    def test_root(self, ai_client):
        body = ai_client.get("/ai/").json()
        assert "endpoints" in body

    def test_health_healthy(self, ai_client):
        with patch.object(ar, "nlp_engine") as nlp, \
                patch.object(ar, "data_engine") as data, \
                patch.object(ar, "automation_engine") as auto:
            nlp.parse_command.return_value = MagicMock(confidence=0.9)
            data.entity_registry = {}
            data.relationship_registry = {}
            auto.workflows = {}
            auto.executions = {}
            response = ai_client.get("/ai/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["components"]["nlp_engine"] == "healthy"

    def test_health_nlp_degraded(self, ai_client):
        with patch.object(ar, "nlp_engine") as nlp, \
                patch.object(ar, "data_engine") as data, \
                patch.object(ar, "automation_engine") as auto:
            nlp.parse_command.return_value = MagicMock(confidence=-1)
            data.entity_registry = {}
            data.relationship_registry = {}
            auto.workflows = {}
            auto.executions = {}
            response = ai_client.get("/ai/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["components"]["nlp_engine"] == "degraded"
