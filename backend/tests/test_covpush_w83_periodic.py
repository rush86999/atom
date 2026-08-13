# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/periodic_tasks.py to >=95% (heartbeat sweep
functions with SessionLocal + dependency mocks; zero LLM spend, zero network).

Covers:
- run_gateway_log_sweep: success (deleted count returned), exception ->
  error dict.
- run_global_ingestion_pulse: success path dispatching per-workspace
  sync/dashboard/freshness tasks, disabled integration skipped, exception ->
  error dict.
- run_doc_freshness_reevaluate: success (summary dict), exception -> error
  dict.
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

import core.periodic_tasks as mod


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeCtxDb:
    """Context-manager fake for SessionLocal()."""

    def __init__(self, workspaces):
        self.workspaces = workspaces
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def query(self, model):
        return self

    def all(self):
        return self.workspaces


class _FakeWs:
    def __init__(self, wid):
        self.id = wid


# ============================================================================
# run_gateway_log_sweep
# ============================================================================

def test_gateway_log_sweep_success():
    with patch.object(mod, "SessionLocal") as session_cls, \
         patch("core.llm.gateway.request_logger.sweep_gateway_logs", return_value=12) as sweep:
        result = _run(mod.run_gateway_log_sweep())
    assert result == {"gateway_logs_deleted": 12}
    sweep.assert_called_once()


def test_gateway_log_sweep_exception_returns_error():
    with patch.object(mod, "SessionLocal") as session_cls, \
         patch("core.llm.gateway.request_logger.sweep_gateway_logs",
               side_effect=RuntimeError("db locked")):
        result = _run(mod.run_gateway_log_sweep())
    assert "error" in result
    assert "db locked" in result["error"]


# ============================================================================
# run_global_ingestion_pulse
# ============================================================================

def _pulse_mocks(workspaces):
    fake_db = _FakeCtxDb(workspaces)
    session_cls = MagicMock(return_value=fake_db)
    dispatch = MagicMock()
    service = MagicMock()
    return session_cls, dispatch, service


def test_pulse_dispatches_for_enabled_integrations():
    session_cls, dispatch, service = _pulse_mocks([_FakeWs("w1"), _FakeWs("w2")])
    service.get_all_settings.return_value = [
        {"enabled": True, "integration_id": "outlook"},
        {"enabled": False, "integration_id": "gdrive"},
    ]
    with patch.object(mod, "SessionLocal", return_value=session_cls()), \
         patch("sqs_worker.dispatch_task", dispatch), \
         patch("core.auto_document_ingestion.get_document_ingestion_service", return_value=service):
        result = _run(mod.run_global_ingestion_pulse())
    assert result == {"workspaces_checked": 2, "tasks_dispatched": 2}
    calls = [c.kwargs["task_name"] for c in dispatch.call_args_list]
    # 2 syncs for enabled outlook (1 per workspace) + 2 dashboards + 2 freshness
    assert calls.count("handle_document_ingestion_sync") == 2
    assert calls.count("sync_dashboard_stats") == 2
    assert calls.count("reevaluate_doc_freshness") == 2
    payload = dispatch.call_args_list[0].kwargs["payload"]
    assert payload["integration_id"] == "outlook"
    assert payload["force"] is False


def test_pulse_no_enabled_integrations_dispatches_only_housekeeping():
    session_cls, dispatch, service = _pulse_mocks([_FakeWs("w1")])
    service.get_all_settings.return_value = [{"enabled": False, "integration_id": "gdrive"}]
    with patch.object(mod, "SessionLocal", return_value=session_cls()), \
         patch("sqs_worker.dispatch_task", dispatch), \
         patch("core.auto_document_ingestion.get_document_ingestion_service", return_value=service):
        result = _run(mod.run_global_ingestion_pulse())
    assert result == {"workspaces_checked": 1, "tasks_dispatched": 1}
    names = [c.kwargs["task_name"] for c in dispatch.call_args_list]
    assert "handle_document_ingestion_sync" not in names


def test_pulse_empty_workspaces():
    session_cls, dispatch, service = _pulse_mocks([])
    with patch.object(mod, "SessionLocal", return_value=session_cls()), \
         patch("sqs_worker.dispatch_task", dispatch), \
         patch("core.auto_document_ingestion.get_document_ingestion_service", return_value=service):
        result = _run(mod.run_global_ingestion_pulse())
    assert result == {"workspaces_checked": 0, "tasks_dispatched": 0}


def test_pulse_exception_returns_error():
    session_cls, dispatch, service = _pulse_mocks([_FakeWs("w1")])
    service.get_all_settings.side_effect = RuntimeError("ingestion down")
    with patch.object(mod, "SessionLocal", return_value=session_cls()), \
         patch("sqs_worker.dispatch_task", dispatch), \
         patch("core.auto_document_ingestion.get_document_ingestion_service", return_value=service):
        result = _run(mod.run_global_ingestion_pulse())
    assert "error" in result
    assert "ingestion down" in result["error"]


# ============================================================================
# run_doc_freshness_reevaluate
# ============================================================================

def test_freshness_reevaluate_success():
    summary = MagicMock()
    summary.as_dict.return_value = {"outdated": 3, "fresh": 5}
    svc = MagicMock()
    svc.reevaluate_workspace.return_value = summary
    with patch.object(mod, "SessionLocal") as session_cls, \
         patch("core.doc_freshness_service.DocFreshnessService", return_value=svc):
        result = _run(mod.run_doc_freshness_reevaluate("w1"))
    assert result == {"outdated": 3, "fresh": 5}
    svc.reevaluate_workspace.assert_called_once_with("w1", set())


def test_freshness_reevaluate_exception_returns_error():
    with patch.object(mod, "SessionLocal") as session_cls, \
         patch("core.doc_freshness_service.DocFreshnessService",
               side_effect=RuntimeError("freshness down")):
        result = _run(mod.run_doc_freshness_reevaluate("w1"))
    assert result == {"error": "freshness down"}
