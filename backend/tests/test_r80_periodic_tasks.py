# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/periodic_tasks.py.

TDD targets:
- ``run_global_ingestion_pulse`` called ``get_document_ingestion_service(ws.id)``
  but that factory takes **zero** positional arguments — TypeError on the very
  first workspace.
- It then read ``settings.enabled`` / ``settings.integration_id`` as
  attributes on ``get_all_settings()`` results, which are **dicts** —
  AttributeError on the first enabled setting.
- The remaining tasks (gateway log sweep, freshness reevaluate) are tested
  with mocked SessionLocal / services.
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from core.periodic_tasks import (
    run_doc_freshness_reevaluate,
    run_gateway_log_sweep,
    run_global_ingestion_pulse,
)


@pytest.fixture()
def db(monkeypatch):
    """Function-scoped in-memory SQLite with the needed tables, and
    SessionLocal patched so the tasks' own sessions hit it."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base
    from core.models import Workspace

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine, tables=[Workspace.__table__])
    session_factory = sessionmaker(bind=engine)
    # periodic_tasks does `from core.database import SessionLocal` — patch the
    # module-level name, not the core.database attribute.
    monkeypatch.setattr("core.periodic_tasks.SessionLocal", session_factory)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _workspace(session, ws_id="ws-1", name="Acme"):
    from core.models import Workspace

    ws = Workspace(id=ws_id, name=name)
    session.add(ws)
    session.commit()
    return ws


class TestGatewayLogSweep:
    def test_deleted_count_returned(self, db):
        with patch("core.llm.gateway.request_logger.sweep_gateway_logs",
                   return_value=7) as sweep:
            result = asyncio.run(run_gateway_log_sweep())
        assert result == {"gateway_logs_deleted": 7}
        sweep.assert_called_once()

    def test_exception_returns_error_dict(self, db):
        with patch("core.llm.gateway.request_logger.sweep_gateway_logs",
                   side_effect=RuntimeError("db locked")):
            result = asyncio.run(run_gateway_log_sweep())
        assert "error" in result


class _FakeIngestionService:
    def __init__(self, settings):
        self._settings = settings

    def get_all_settings(self):
        return list(self._settings)


class TestGlobalIngestionPulse:
    def test_dispatches_for_enabled_settings(self, db):
        _workspace(db, "ws-1")
        _workspace(db, "ws-2")
        service = _FakeIngestionService([
            {"integration_id": "drive-1", "enabled": True},
            {"integration_id": "dropbox-1", "enabled": False},
        ])
        dispatched = []

        def _fake_dispatch(task_name, payload=None, delay_seconds=0):
            dispatched.append((task_name, payload))

        with patch("core.auto_document_ingestion.get_document_ingestion_service",
                   return_value=service), \
             patch("sqs_worker.dispatch_task", side_effect=_fake_dispatch):
            result = asyncio.run(run_global_ingestion_pulse())

        assert result == {"workspaces_checked": 2, "tasks_dispatched": 2}
        names = [name for name, _ in dispatched]
        assert names.count("handle_document_ingestion_sync") == 2  # 1 per workspace (enabled only)
        assert names.count("sync_dashboard_stats") == 2
        assert names.count("reevaluate_doc_freshness") == 2

        sync_payloads = [payload for name, payload in dispatched
                         if name == "handle_document_ingestion_sync"]
        assert sync_payloads[0] == {"integration_id": "drive-1", "workspace_id": "ws-1", "force": False}
        assert sync_payloads[1] == {"integration_id": "drive-1", "workspace_id": "ws-2", "force": False}
        for _, payload in dispatched:
            assert payload.get("workspace_id") in ("ws-1", "ws-2")

    def test_no_settings_skips_sync_but_dispatches_analytics(self, db):
        _workspace(db, "ws-1")
        service = _FakeIngestionService([])
        dispatched = []

        def _fake_dispatch(task_name, payload=None, delay_seconds=0):
            dispatched.append(task_name)

        with patch("core.auto_document_ingestion.get_document_ingestion_service",
                   return_value=service), \
             patch("sqs_worker.dispatch_task", side_effect=_fake_dispatch):
            result = asyncio.run(run_global_ingestion_pulse())

        assert dispatched == ["sync_dashboard_stats", "reevaluate_doc_freshness"]
        assert result["tasks_dispatched"] == 1

    def test_no_workspaces(self, db):
        with patch("core.auto_document_ingestion.get_document_ingestion_service",
                   return_value=_FakeIngestionService([])), \
             patch("sqs_worker.dispatch_task") as dispatch:
            result = asyncio.run(run_global_ingestion_pulse())
        assert result == {"workspaces_checked": 0, "tasks_dispatched": 0}
        dispatch.assert_not_called()

    def test_exception_returns_error_dict(self, db):
        _workspace(db, "ws-1")
        with patch("core.auto_document_ingestion.get_document_ingestion_service",
                   side_effect=RuntimeError("boom")), \
             patch("sqs_worker.dispatch_task"):
            result = asyncio.run(run_global_ingestion_pulse())
        assert "error" in result


class TestDocFreshnessReevaluate:
    def test_returns_summary(self, db):
        summary = MagicMock()
        summary.as_dict.return_value = {"checked": 3, "outdated": 1}
        with patch("core.doc_freshness_service.DocFreshnessService") as svc_cls:
            svc_cls.return_value.reevaluate_workspace.return_value = summary
            result = asyncio.run(run_doc_freshness_reevaluate("ws-1"))
        assert result == {"checked": 3, "outdated": 1}
        svc_cls.assert_called_once()
        assert svc_cls.return_value.reevaluate_workspace.call_args.args[0] == "ws-1"
        assert svc_cls.return_value.reevaluate_workspace.call_args.args[1] == set()

    def test_exception_returns_error_dict(self, db):
        with patch("core.doc_freshness_service.DocFreshnessService") as svc_cls:
            svc_cls.return_value.reevaluate_workspace.side_effect = RuntimeError("boom")
            result = asyncio.run(run_doc_freshness_reevaluate("ws-1"))
        assert "error" in result
