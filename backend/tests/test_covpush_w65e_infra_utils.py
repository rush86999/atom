"""
Coverage wave 65e — infra/utils modules (TDD, mocked deps, zero LLM spend,
no network, no real DB).

Covers:
- core.workflow_metrics: ExecutionRecord.to_dict (completed_at set/None),
  record_execution (template usage, success/failure counters, duration),
  get_summary (recent/empty/day-filter, top templates, retries, fallbacks),
  get_recent_executions (ordering + limit), get_workflow_stats (populated /
  empty workflow), module-level global instance.
- core.sync_health_monitor: check_health aggregation (healthy/degraded/
  unhealthy), _check_last_sync (no records, fresh, stale, very stale,
  exception), placeholder checks (websocket/scheduler/errors), get_http_status
  (200/503), singleton getter (first call + reuse).
- core.document_learner: learn_from_file for .xlsx/.csv/.docx/.pdf/
  unsupported/empty-content, _parse_excel (csv vs multi-sheet xlsx, error),
  _parse_word (paragraphs + tables, error), _parse_pdf (no library, success,
  error), pypdf/PyPDF2 import fallbacks via reload.
- core.marketplace_sync_worker: __init__ (default SessionLocal), instance
  registration (existing, auto-register success, failure, exception),
  sync_usage (disabled, no instance, no records, push success incl. timestamp
  update + instance last_sync, rejection, exception), close, run_sync entry
  point (own session + closed), and the `__main__` guard via runpy.
- core.http_client: lazy singleton creation + reuse (async/sync), client
  config (timeout/limits/http2), close_http_clients (both/none), reset_http_clients
  (running loop task, non-running loop asyncio.run, no-loop sync close, close
  error warnings), all 12 convenience wrappers, h2-present reload branch.
- core.directory_permission: full service — cache hit/miss (real GovernanceCache
  mocked), blocked dirs (exact + subdir, sibling-prefix NOT blocked), maturity
  allow/suggest-only for all 4 statuses + unknown status, ~ and .. resolution,
  _expand_path error fallback, _is_blocked resolve-error branch, _is_within_allowed
  boundary matching, _get_reason both branches, _get_from_cache malformed key,
  _cache_result, singleton getter + convenience function.

Bugs found (fixed in core/directory_permission.py):
  1. `_is_within_allowed` used bare startswith -> sibling prefix `/tmp2`
     was treated as within `/tmp` (security false positive for AUTONOMOUS).
  2. `_is_blocked` used bare startswith -> sibling prefix `/etc2` was
     blocked as if it were `/etc`. Boundary-aware matching added (os.sep).

No real DB writes: SQLAlchemy sessions are fakes; the real atom_dev.db is
never touched.
"""

import asyncio
import importlib
import os
import runpy
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import httpx

import core.directory_permission as dirperm
import core.document_learner as doc_learner
import core.http_client as http_client
import core.marketplace_sync_worker as msw
import core.sync_health_monitor as shm
import core.workflow_metrics as wfm
from core.directory_permission import DirectoryPermissionService, get_directory_permission_service
from core.document_learner import DocumentLifecycleLearner
from core.marketplace_sync_worker import AnalyticsSyncWorker
from core.models import AgentStatus
from core.sync_health_monitor import SyncHealthMonitor, get_sync_health_monitor
from core.workflow_metrics import ExecutionRecord, WorkflowMetrics


def _fake_cache():
    """In-memory GovernanceCache stand-in with get/set (misses by default)."""
    cache = MagicMock()
    cache.get.return_value = None
    return cache


# ============================================================================
# core.workflow_metrics
# ============================================================================


class TestExecutionRecord:
    def test_to_dict_with_completed_at(self):
        rec = ExecutionRecord(
            execution_id="e1",
            workflow_id="wf1",
            template_id="t1",
            status="completed",
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            completed_at=datetime(2026, 1, 1, 10, 1, 0),
            duration_ms=60000.0,
            steps_executed=3,
            steps_failed=0,
            retries_used=2,
            agent_fallback_used=True,
        )
        d = rec.to_dict()
        assert d["execution_id"] == "e1"
        assert d["completed_at"] == "2026-01-01T10:01:00"
        assert d["started_at"] == "2026-01-01T10:00:00"
        assert d["retries_used"] == 2
        assert d["agent_fallback_used"] is True

    def test_to_dict_without_completed_at(self):
        rec = ExecutionRecord(
            execution_id="e2",
            workflow_id="wf1",
            template_id=None,
            status="running",
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            completed_at=None,
            duration_ms=0.0,
            steps_executed=0,
            steps_failed=0,
        )
        d = rec.to_dict()
        assert d["completed_at"] is None
        assert d["template_id"] is None


class TestWorkflowMetrics:
    def _record(self, m, exec_id, wf_id, status, started_at, template_id=None,
                steps=2, failed=0, retries=0, fallback=False):
        m.record_execution(
            execution_id=exec_id,
            workflow_id=wf_id,
            status=status,
            started_at=started_at,
            completed_at=started_at + timedelta(minutes=1),
            steps_executed=steps,
            steps_failed=failed,
            template_id=template_id,
            retries_used=retries,
            agent_fallback_used=fallback,
        )

    def test_record_execution_increments_counters_and_template_usage(self):
        m = WorkflowMetrics()
        now = datetime.now()
        self._record(m, "e1", "wf1", "completed", now - timedelta(days=1), template_id="tpl-a")
        self._record(m, "e2", "wf1", "failed", now - timedelta(days=1), template_id="tpl-a", retries=1)
        self._record(m, "e3", "wf1", "cancelled", now - timedelta(days=1), template_id=None)
        assert m._success_count == 1
        assert m._failure_count == 2
        assert m._template_usage["tpl-a"] == 2
        assert len(m._executions) == 3

    def test_record_execution_duration(self):
        m = WorkflowMetrics()
        m.record_execution(
            "e1", "wf1", "completed",
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            completed_at=datetime(2026, 1, 1, 10, 0, 30),
            steps_executed=1,
        )
        assert m._executions[0].duration_ms == 30000.0

    def test_get_summary_empty_returns_zeroed(self):
        m = WorkflowMetrics()
        s = m.get_summary(days=7)
        assert s == {
            "period_days": 7,
            "total_executions": 0,
            "success_rate": 0,
            "avg_duration_ms": 0,
            "top_templates": [],
            "retries_total": 0,
            "agent_fallbacks": 0,
        }

    def test_get_summary_aggregates(self):
        m = WorkflowMetrics()
        now = datetime.now()
        self._record(m, "e1", "wf1", "completed", now - timedelta(hours=1), template_id="tpl-a", retries=2)
        self._record(m, "e2", "wf2", "failed", now - timedelta(hours=2), template_id="tpl-a", retries=1, fallback=True)
        self._record(m, "e3", "wf3", "completed", now - timedelta(hours=3), template_id="tpl-b")
        self._record(m, "e4", "wf4", "completed", now - timedelta(hours=4), template_id=None)
        s = m.get_summary(days=7)
        assert s["period_days"] == 7
        assert s["total_executions"] == 4
        assert s["success_rate"] == 75.0
        assert s["retries_total"] == 3
        assert s["agent_fallbacks"] == 1
        assert s["top_templates"][0] == {"id": "tpl-a", "count": 2}
        assert s["top_templates"][1] == {"id": "tpl-b", "count": 1}

    def test_get_summary_day_filter_excludes_old_records(self):
        m = WorkflowMetrics()
        now = datetime.now()
        self._record(m, "e1", "wf1", "completed", now - timedelta(days=1))
        self._record(m, "e2", "wf2", "completed", now - timedelta(days=10))
        s = m.get_summary(days=7)
        assert s["total_executions"] == 1

    def test_get_summary_rounds_avg_duration(self):
        m = WorkflowMetrics()
        now = datetime.now()
        self._record(m, "e1", "wf1", "completed", now - timedelta(hours=1))
        self._record(m, "e2", "wf1", "completed", now - timedelta(hours=2))
        s = m.get_summary(days=1)
        assert s["avg_duration_ms"] == 60000.0

    def test_get_recent_executions_orders_and_limits(self):
        m = WorkflowMetrics()
        now = datetime.now()
        self._record(m, "e1", "wf1", "completed", now - timedelta(hours=3))
        self._record(m, "e2", "wf2", "failed", now - timedelta(hours=2))
        self._record(m, "e3", "wf3", "completed", now - timedelta(hours=1))
        recent = m.get_recent_executions(limit=2)
        assert [r["execution_id"] for r in recent] == ["e3", "e2"]

    def test_get_recent_executions_default_limit(self):
        m = WorkflowMetrics()
        now = datetime.now()
        for i in range(25):
            self._record(m, f"e{i}", "wf1", "completed", now - timedelta(minutes=i))
        assert len(m.get_recent_executions()) == 20

    def test_get_workflow_stats_populated(self):
        m = WorkflowMetrics()
        now = datetime.now()
        self._record(m, "e1", "wf-a", "completed", now - timedelta(hours=2))
        self._record(m, "e2", "wf-a", "failed", now - timedelta(hours=1))
        self._record(m, "e3", "wf-b", "completed", now - timedelta(hours=1))
        s = m.get_workflow_stats("wf-a")
        assert s["workflow_id"] == "wf-a"
        assert s["executions"] == 2
        assert s["success_rate"] == 50.0
        assert s["last_run"] == (now - timedelta(hours=1)).isoformat()

    def test_get_workflow_stats_empty(self):
        m = WorkflowMetrics()
        self._record(m, "e1", "wf-a", "completed", datetime.now() - timedelta(hours=1))
        s = m.get_workflow_stats("nope")
        assert s == {"workflow_id": "nope", "executions": 0}

    def test_module_global_metrics_instance(self):
        assert isinstance(wfm.metrics, WorkflowMetrics)


# ============================================================================
# core.sync_health_monitor
# ============================================================================


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def order_by(self, *args):
        return self

    def first(self):
        return self._result


class _FakeDB:
    def __init__(self, first_result=None, raise_error=False):
        self._first = first_result
        self._raise = raise_error

    def query(self, model):
        if self._raise:
            raise RuntimeError("db exploded")
        return _FakeQuery(self._first)


def _sync_state(age_minutes):
    return SimpleNamespace(last_sync=datetime.now(timezone.utc) - timedelta(minutes=age_minutes))


class TestSyncHealthMonitorChecks:
    def test_check_last_sync_no_records(self):
        m = SyncHealthMonitor()
        r = m._check_last_sync(_FakeDB(first_result=None))
        assert r["healthy"] is False
        assert r["degraded"] is True
        assert r["last_sync"] is None
        assert r["age_minutes"] is None

    def test_check_last_sync_fresh(self):
        m = SyncHealthMonitor()
        r = m._check_last_sync(_FakeDB(first_result=_sync_state(10)))
        assert r["healthy"] is True
        assert r["degraded"] is False
        assert r["last_sync"].endswith("Z")
        assert r["age_minutes"] == 10.0

    def test_check_last_sync_stale_degraded(self):
        m = SyncHealthMonitor()
        r = m._check_last_sync(_FakeDB(first_result=_sync_state(45)))
        assert r["healthy"] is False
        assert r["degraded"] is True
        assert "stale" in r["message"]
        assert r["age_minutes"] == 45.0

    def test_check_last_sync_very_stale(self):
        m = SyncHealthMonitor()
        r = m._check_last_sync(_FakeDB(first_result=_sync_state(90)))
        assert r["healthy"] is False
        assert r["degraded"] is False
        assert "very stale" in r["message"]

    def test_check_last_sync_exception(self):
        m = SyncHealthMonitor()
        r = m._check_last_sync(_FakeDB(raise_error=True))
        assert r["healthy"] is False
        assert r["last_sync"] is None
        assert "Error checking sync" in r["message"]

    def test_check_websocket_placeholder(self):
        r = SyncHealthMonitor()._check_websocket()
        assert r["healthy"] is True
        assert r["connected"] is None

    def test_check_scheduler_placeholder(self):
        r = SyncHealthMonitor()._check_scheduler()
        assert r["healthy"] is True
        assert r["running"] is None

    def test_check_recent_errors_placeholder(self):
        r = SyncHealthMonitor()._check_recent_errors()
        assert r["healthy"] is True
        assert r["error_count"] == 0


class TestSyncHealthMonitorOverall:
    def test_check_health_all_healthy(self):
        m = SyncHealthMonitor()
        with patch.object(m, "_check_last_sync", return_value={
            "healthy": True, "degraded": False, "last_sync": "2026-01-01T00:00:00Z",
            "age_minutes": 5.0,
        }):
            h = m.check_health(_FakeDB())
        assert h["status"] == "healthy"
        assert h["last_sync"] == "2026-01-01T00:00:00Z"
        assert h["sync_age_minutes"] == 5.0
        assert h["websocket_connected"] is None
        assert h["scheduler_running"] is None
        assert h["recent_errors"] == 0
        assert h["details"]["failed_checks"] == []
        assert h["details"]["degraded_checks"] == []
        assert h["details"]["total_checks"] == 4
        assert h["details"]["timestamp"].endswith("Z")

    def test_check_health_degraded_when_no_sync_records(self):
        m = SyncHealthMonitor()
        h = m.check_health(_FakeDB(first_result=None))
        # A check with healthy=False lands in failed_checks regardless of the
        # degraded flag, so the aggregate status is "unhealthy".
        assert h["status"] == "unhealthy"
        assert h["checks"]["last_sync"]["degraded"] is True
        assert h["details"]["degraded_checks"] == ["last_sync"]
        assert h["details"]["failed_checks"] == ["last_sync"]

    def test_check_health_degraded_when_healthy_but_degraded(self):
        m = SyncHealthMonitor()
        with patch.object(m, "_check_last_sync", return_value={
            "healthy": True, "degraded": True, "last_sync": None, "age_minutes": None,
        }):
            h = m.check_health(_FakeDB())
        assert h["status"] == "degraded"
        assert h["details"]["failed_checks"] == []

    def test_check_health_unhealthy_when_last_sync_exception(self):
        m = SyncHealthMonitor()
        h = m.check_health(_FakeDB(raise_error=True))
        assert h["status"] == "unhealthy"
        assert h["checks"]["last_sync"]["healthy"] is False
        assert h["details"]["failed_checks"] == ["last_sync"]

    def test_check_health_unhealthy_when_very_stale(self):
        m = SyncHealthMonitor()
        h = m.check_health(_FakeDB(first_result=_sync_state(120)))
        assert h["status"] == "unhealthy"

    def test_get_http_status_unhealthy(self):
        assert SyncHealthMonitor().get_http_status({"status": "unhealthy"}) == 503

    def test_get_http_status_healthy_and_degraded(self):
        m = SyncHealthMonitor()
        assert m.get_http_status({"status": "healthy"}) == 200
        assert m.get_http_status({"status": "degraded"}) == 200


class TestSyncHealthMonitorSingleton:
    def test_get_singleton_creates_and_reuses(self):
        _reset_singleton()
        try:
            first = get_sync_health_monitor()
            assert isinstance(first, SyncHealthMonitor)
            assert get_sync_health_monitor() is first
        finally:
            _reset_singleton()

    def test_singleton_is_shared_module_state(self):
        assert shm._health_monitor is None
        a = get_sync_health_monitor()
        assert a is get_sync_health_monitor()
        _reset_singleton()


def _reset_singleton():
    shm._health_monitor = None


# ============================================================================
# core.document_learner
# ============================================================================


class _FakePage:
    def extract_text(self):
        return "page text"


class _FakeReader:
    def __init__(self, pages):
        self.pages = pages


class TestDocumentLearnerParse:
    def test_parse_excel_csv(self):
        df = MagicMock()
        df.to_string.return_value = "a,b\n1,2"
        with patch("core.document_learner.pd") as pd_mock:
            pd_mock.read_csv.return_value = df
            out = DocumentLifecycleLearner()._parse_excel("/x/data.csv")
        assert out == "a,b\n1,2"
        pd_mock.read_csv.assert_called_once_with("/x/data.csv")

    def test_parse_excel_xlsx_multi_sheet(self):
        xls = MagicMock()
        xls.sheet_names = ["S1", "S2"]
        df = MagicMock()
        df.to_string.return_value = "x\ny"
        with patch("core.document_learner.pd") as pd_mock:
            pd_mock.ExcelFile.return_value = xls
            pd_mock.read_excel.return_value = df
            out = DocumentLifecycleLearner()._parse_excel("/x/data.xlsx")
        assert out == "--- Sheet: S1 ---\nx\ny\n--- Sheet: S2 ---\nx\ny"
        assert pd_mock.read_excel.call_count == 2

    def test_parse_excel_error_returns_empty(self):
        with patch("core.document_learner.pd") as pd_mock:
            pd_mock.read_csv.side_effect = ValueError("bad csv")
            out = DocumentLifecycleLearner()._parse_excel("/x/data.csv")
        assert out == ""

    def test_parse_word_paragraphs_and_tables(self):
        para = MagicMock()
        para.text = "hello"
        cell = MagicMock()
        cell.text = "c1"
        row = MagicMock()
        row.cells = [cell, cell]
        table = MagicMock()
        table.rows = [row]
        doc = MagicMock()
        doc.paragraphs = [para, para]
        doc.tables = [table]
        with patch("core.document_learner.Document", return_value=doc):
            out = DocumentLifecycleLearner()._parse_word("/x/doc.docx")
        assert out == "hello\nhello\nc1 | c1"

    def test_parse_word_error_returns_empty(self):
        with patch("core.document_learner.Document", side_effect=OSError("corrupt")):
            out = DocumentLifecycleLearner()._parse_word("/x/doc.docx")
        assert out == ""

    def test_parse_pdf_no_library(self, monkeypatch):
        monkeypatch.setattr(doc_learner, "PyPDF2", None)
        out = DocumentLifecycleLearner()._parse_pdf("/x/doc.pdf")
        assert out == ""

    def test_parse_pdf_success(self, monkeypatch):
        reader = _FakeReader([_FakePage(), _FakePage()])
        fake_lib = MagicMock()
        fake_lib.PdfReader.return_value = reader
        monkeypatch.setattr(doc_learner, "PyPDF2", fake_lib)
        with patch("builtins.open", MagicMock()):
            out = DocumentLifecycleLearner()._parse_pdf("/x/doc.pdf")
        assert out == "page text\npage text"
        fake_lib.PdfReader.assert_called_once()

    def test_parse_pdf_error_returns_empty(self, monkeypatch):
        fake_lib = MagicMock()
        fake_lib.PdfReader.side_effect = RuntimeError("pdf broken")
        monkeypatch.setattr(doc_learner, "PyPDF2", fake_lib)
        with patch("builtins.open", MagicMock()):
            out = DocumentLifecycleLearner()._parse_pdf("/x/doc.pdf")
        assert out == ""


class TestDocumentLearnerLearn:
    @pytest.fixture
    def learner(self):
        with patch("core.document_learner.KnowledgeExtractor") as ke_cls, \
                patch("core.document_learner.BusinessEventIntelligence") as bi_cls:
            ke_cls.return_value.extract_knowledge = AsyncMock(return_value={"events": ["x"]})
            bi_cls.return_value.process_extracted_events = AsyncMock()
            yield DocumentLifecycleLearner(ai_service=MagicMock(), db_session=MagicMock())

    async def test_learn_from_xlsx(self, learner):
        with patch.object(learner, "_parse_excel", return_value="sheet text"):
            await learner.learn_from_file("/docs/data.XLSX", "ws1")
        learner.extractor.extract_knowledge.assert_awaited_once_with(
            "sheet text", tenant_id="ws1", source="document_data.XLSX"
        )
        learner.biz_intel.process_extracted_events.assert_awaited_once_with(
            {"events": ["x"]}, "ws1"
        )

    async def test_learn_from_csv(self, learner):
        with patch.object(learner, "_parse_excel", return_value="csv text"):
            await learner.learn_from_file("/docs/data.csv", "ws1")
        learner.extractor.extract_knowledge.assert_awaited_once()

    async def test_learn_from_docx(self, learner):
        with patch.object(learner, "_parse_word", return_value="word text"):
            await learner.learn_from_file("/docs/doc.docx", "ws1")
        learner.extractor.extract_knowledge.assert_awaited_once()
        learner.extractor.extract_knowledge.assert_awaited_once_with(
            "word text", tenant_id="ws1", source="document_doc.docx"
        )

    async def test_learn_from_pdf(self, learner):
        with patch.object(learner, "_parse_pdf", return_value="pdf text"):
            await learner.learn_from_file("/docs/doc.pdf", "ws1")
        learner.extractor.extract_knowledge.assert_awaited_once_with(
            "pdf text", tenant_id="ws1", source="document_doc.pdf"
        )

    async def test_learn_unsupported_format_returns_without_extract(self, learner):
        with patch.object(learner, "_parse_excel") as pe:
            await learner.learn_from_file("/docs/doc.txt", "ws1")
        pe.assert_not_called()
        learner.extractor.extract_knowledge.assert_not_called()

    async def test_learn_empty_content_skips_extractor(self, learner):
        with patch.object(learner, "_parse_excel", return_value=""):
            await learner.learn_from_file("/docs/data.csv", "ws1")
        learner.extractor.extract_knowledge.assert_not_called()
        learner.biz_intel.process_extracted_events.assert_not_called()


class TestDocumentLearnerImportFallbacks:
    def test_reload_with_pypdf_installed(self, monkeypatch):
        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = MagicMock
        monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
        importlib.reload(doc_learner)
        try:
            assert doc_learner.PyPDF2 is fake_pypdf
        finally:
            monkeypatch.delitem(sys.modules, "pypdf")
            importlib.reload(doc_learner)

    def test_reload_with_legacy_pypdf2(self, monkeypatch):
        fake_pypdf2 = types.ModuleType("PyPDF2")
        fake_pypdf2.PdfReader = MagicMock
        monkeypatch.setitem(sys.modules, "PyPDF2", fake_pypdf2)
        importlib.reload(doc_learner)
        try:
            assert doc_learner.PyPDF2 is fake_pypdf2
        finally:
            monkeypatch.delitem(sys.modules, "PyPDF2")
            importlib.reload(doc_learner)

    def test_both_missing_logs_warning(self, monkeypatch):
        """pypdf AND legacy PyPDF2 both missing -> PyPDF2 = None + warning.

        The legacy `PyPDF2` package IS installed in this env, so block it at
        the import level with a builtins.__import__ shim before reloading."""
        import builtins
        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name in ("pypdf", "PyPDF2"):
                raise ImportError(f"{name} blocked for test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked_import)
        with patch.object(doc_learner.logger, "warning") as warn:
            importlib.reload(doc_learner)
        warn.assert_called_once()
        assert doc_learner.PyPDF2 is None
        importlib.reload(doc_learner)


# ============================================================================
# core.marketplace_sync_worker
# ============================================================================


def _usage_record(**overrides):
    d = {
        "item_type": "skill",
        "item_id": "it-1",
        "execution_count": 3,
        "success_count": 2,
        "total_duration_ms": 500,
    }
    d.update(overrides)
    return SimpleNamespace(**d)


def _make_worker(db=None, saas=None, enabled=True, session_factory=None):
    """Build an AnalyticsSyncWorker with all deps mocked."""
    if db is None:
        db = MagicMock()
    if saas is None:
        saas = MagicMock()
    worker = AnalyticsSyncWorker.__new__(AnalyticsSyncWorker)
    worker.db = db
    worker.saas_client = saas
    worker.analytics_enabled = enabled
    worker._session_factory = session_factory
    return worker


class TestMarketplaceWorkerInit:
    def test_init_default_session_local(self, monkeypatch):
        fake_db = MagicMock()
        monkeypatch.setattr(msw, "SessionLocal", lambda: fake_db)
        monkeypatch.setattr(msw, "AtomAgentOSMarketplaceClient", MagicMock)
        monkeypatch.setenv("ANALYTICS_ENABLED", "true")
        w = AnalyticsSyncWorker()
        assert w.db is fake_db
        assert w.analytics_enabled is True
        monkeypatch.setenv("ANALYTICS_ENABLED", "false")
        w2 = AnalyticsSyncWorker(db=MagicMock())
        assert w2.analytics_enabled is False


class TestMarketplaceInstanceRegistration:
    def test_returns_existing_instance(self):
        db = MagicMock()
        db.query.return_value.first.return_value = SimpleNamespace(saas_instance_id="inst-1")
        w = _make_worker(db=db, enabled=True)
        assert w._ensure_instance_registered() == "inst-1"
        w.saas_client.register_instance_sync.assert_not_called()

    def test_auto_registers_new_instance(self):
        db = MagicMock()
        db.query.return_value.first.return_value = None
        saas = MagicMock()
        saas.register_instance_sync.return_value = {
            "instance_id": "inst-new",
            "registration_token": "tok-1",
        }
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w._ensure_instance_registered() == "inst-new"
        saas.register_instance_sync.assert_called_once_with(
            instance_name="Self-Hosted-Atom", platform="docker", version="1.0.0"
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.saas_instance_id == "inst-new"
        assert added.registration_token == "tok-1"
        assert added.status == "active"

    def test_registration_rejected_returns_none(self):
        db = MagicMock()
        db.query.return_value.first.return_value = None
        saas = MagicMock()
        saas.register_instance_sync.return_value = {"error": "denied"}
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w._ensure_instance_registered() is None
        db.add.assert_not_called()

    def test_registration_exception_returns_none(self):
        db = MagicMock()
        db.query.return_value.first.return_value = None
        saas = MagicMock()
        saas.register_instance_sync.side_effect = RuntimeError("network down")
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w._ensure_instance_registered() is None


class TestMarketplaceSyncUsage:
    def test_disabled_returns_zero(self):
        w = _make_worker(enabled=False)
        assert w.sync_usage() == 0
        w.saas_client.push_analytics_sync.assert_not_called()

    def test_no_instance_aborts(self):
        db = MagicMock()
        db.query.return_value.first.return_value = None
        saas = MagicMock()
        saas.register_instance_sync.return_value = {"error": "denied"}
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w.sync_usage() == 0
        saas.push_analytics_sync.assert_not_called()

    def test_no_usage_records_returns_zero(self):
        db = MagicMock()
        db.query.return_value.first.return_value = SimpleNamespace(saas_instance_id="inst-1")
        db.query.return_value.all.return_value = []
        w = _make_worker(db=db, enabled=True)
        assert w.sync_usage() == 0
        w.saas_client.push_analytics_sync.assert_not_called()

    def test_push_success_updates_timestamps(self):
        records = [_usage_record(), _usage_record(item_id="it-2")]
        db = MagicMock()
        db.query.return_value.first.side_effect = [
            SimpleNamespace(saas_instance_id="inst-1"),
            SimpleNamespace(saas_instance_id="inst-1", last_sync_at=None),
        ]
        db.query.return_value.all.return_value = records
        saas = MagicMock()
        saas.push_analytics_sync.return_value = {"success": True}
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w.sync_usage() == 2
        assert all(r.last_reported_at is not None for r in records)
        assert db.query.return_value.all.return_value[0].last_reported_at == db.query.return_value.all.return_value[1].last_reported_at
        saas.push_analytics_sync.assert_called_once_with(
            instance_id="inst-1",
            reports=[
                {"item_type": "skill", "item_id": "it-1", "execution_count": 3,
                 "success_count": 2, "total_duration_ms": 500},
                {"item_type": "skill", "item_id": "it-2", "execution_count": 3,
                 "success_count": 2, "total_duration_ms": 500},
            ],
        )
        db.commit.assert_called_once()

    def test_push_success_without_instance_row(self):
        records = [_usage_record()]
        db = MagicMock()
        db.query.return_value.first.side_effect = [
            SimpleNamespace(saas_instance_id="inst-1"),
            None,
        ]
        db.query.return_value.all.return_value = records
        saas = MagicMock()
        saas.push_analytics_sync.return_value = {"success": True}
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w.sync_usage() == 1
        db.commit.assert_called_once()

    def test_push_rejected_returns_zero(self):
        records = [_usage_record()]
        db = MagicMock()
        db.query.return_value.first.return_value = SimpleNamespace(saas_instance_id="inst-1")
        db.query.return_value.all.return_value = records
        saas = MagicMock()
        saas.push_analytics_sync.return_value = {"success": False, "error": "nope"}
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w.sync_usage() == 0
        assert db.commit.call_count == 0

    def test_push_exception_returns_zero(self):
        records = [_usage_record()]
        db = MagicMock()
        db.query.return_value.first.return_value = SimpleNamespace(saas_instance_id="inst-1")
        db.query.return_value.all.return_value = records
        saas = MagicMock()
        saas.push_analytics_sync.side_effect = RuntimeError("boom")
        w = _make_worker(db=db, saas=saas, enabled=True)
        assert w.sync_usage() == 0

    def test_close(self):
        db = MagicMock()
        w = _make_worker(db=db, enabled=True)
        w.close()
        db.close.assert_called_once()


class TestMarketplaceRunSync:
    def test_run_sync_uses_own_session_and_closes(self, monkeypatch, capsys):
        fake_db = MagicMock()
        fake_worker = MagicMock()
        fake_worker.sync_usage.return_value = 7
        fake_worker.db = fake_db

        monkeypatch.setattr(msw, "SessionLocal", lambda: fake_db)
        monkeypatch.setattr(
            msw, "AtomAgentOSMarketplaceClient",
            lambda: MagicMock(),
        )
        monkeypatch.setenv("ANALYTICS_ENABLED", "true")
        with patch.object(msw, "AnalyticsSyncWorker", return_value=fake_worker):
            msw.run_sync()
        fake_worker.sync_usage.assert_called_once()
        fake_worker.close.assert_called_once()
        assert "Synced 7 marketplace usage records." in capsys.readouterr().out

    def test_run_sync_propagates_worker_exception_but_closes(self, monkeypatch, capsys):
        fake_worker = MagicMock()
        fake_worker.sync_usage.side_effect = RuntimeError("sync failed")
        monkeypatch.setenv("ANALYTICS_ENABLED", "false")
        with patch.object(msw, "AnalyticsSyncWorker", return_value=fake_worker):
            with pytest.raises(RuntimeError):
                msw.run_sync()
        fake_worker.close.assert_called_once()

    def test_main_guard_executes(self, monkeypatch, capsys):
        """Covers the `if __name__ == "__main__"` block via runpy."""
        fake_db = SimpleNamespace(close=lambda: None)
        fake_database = types.ModuleType("core.database")
        fake_database.SessionLocal = lambda: fake_db
        fake_client_mod = types.ModuleType("core.atom_saas_client")
        fake_client_mod.AtomAgentOSMarketplaceClient = MagicMock
        monkeypatch.setenv("ANALYTICS_ENABLED", "false")
        monkeypatch.setitem(sys.modules, "core.database", fake_database)
        monkeypatch.setitem(sys.modules, "core.atom_saas_client", fake_client_mod)
        runpy.run_path(msw.__file__, run_name="__main__")
        assert "Synced 0 marketplace usage records." in capsys.readouterr().out


# ============================================================================
# core.http_client
# ============================================================================


class TestHTTPClientLazyClients:
    def teardown_method(self):
        http_client._async_client = None
        http_client._sync_client = None

    def test_get_async_client_creates_and_reuses(self):
        c1 = http_client.get_async_client()
        c2 = http_client.get_async_client()
        assert c1 is c2
        assert isinstance(c1, httpx.AsyncClient)
        assert c1.timeout == httpx.Timeout(30.0)

    def test_get_sync_client_creates_and_reuses(self):
        c1 = http_client.get_sync_client()
        c2 = http_client.get_sync_client()
        assert c1 is c2
        assert c1.timeout == httpx.Timeout(30.0)

    def test_env_configured_defaults(self, monkeypatch):
        monkeypatch.setenv("HTTP_TIMEOUT", "12.5")
        monkeypatch.setenv("HTTP_MAX_CONNECTIONS", "7")
        monkeypatch.setenv("HTTP_MAX_KEEPALIVE", "3")
        importlib.reload(http_client)
        try:
            c = http_client.get_sync_client()
            assert c.timeout == httpx.Timeout(12.5)
        finally:
            http_client._sync_client = None
            http_client._async_client = None
            monkeypatch.delenv("HTTP_TIMEOUT", raising=False)
            monkeypatch.delenv("HTTP_MAX_CONNECTIONS", raising=False)
            monkeypatch.delenv("HTTP_MAX_KEEPALIVE", raising=False)
            importlib.reload(http_client)

    def test_http2_enabled_when_h2_installed(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "h2", types.ModuleType("h2"))
        importlib.reload(http_client)
        try:
            assert http_client.HTTP2_ENABLED is True
        finally:
            monkeypatch.delitem(sys.modules, "h2")
            importlib.reload(http_client)
        assert http_client.HTTP2_ENABLED is False


class TestHTTPClientLifecycle:
    async def test_close_http_clients_both(self):
        async_client = AsyncMock()
        sync_client = MagicMock()
        http_client._async_client = async_client
        http_client._sync_client = sync_client
        await http_client.close_http_clients()
        async_client.aclose.assert_awaited_once()
        sync_client.close.assert_called_once()
        assert http_client._async_client is None
        assert http_client._sync_client is None

    async def test_close_http_clients_none(self):
        http_client._async_client = None
        http_client._sync_client = None
        await http_client.close_http_clients()

    async def test_reset_async_client_running_loop(self):
        client = AsyncMock()
        http_client._async_client = client
        http_client.reset_http_clients()
        assert http_client._async_client is None
        await asyncio.sleep(0)

    def test_reset_async_client_non_running_loop(self):
        client = AsyncMock()
        http_client._async_client = client
        loop = MagicMock()
        loop.is_running.return_value = False
        with patch("asyncio.get_running_loop", return_value=loop):
            http_client.reset_http_clients()
        assert http_client._async_client is None

    def test_reset_async_client_no_loop(self):
        client = AsyncMock()
        http_client._async_client = client
        http_client.reset_http_clients()
        assert http_client._async_client is None

    def test_reset_async_client_close_error(self):
        client = AsyncMock()
        http_client._async_client = client
        with patch("asyncio.get_running_loop",
                   side_effect=ValueError("bogus")):
            http_client.reset_http_clients()
        assert http_client._async_client is None

    def test_reset_sync_client_and_error(self):
        ok = MagicMock()
        http_client._sync_client = ok
        http_client.reset_http_clients()
        ok.close.assert_called_once()
        assert http_client._sync_client is None

        broken = MagicMock()
        broken.close.side_effect = RuntimeError("Socket close error")
        http_client._sync_client = broken
        http_client.reset_http_clients()
        assert http_client._sync_client is None

    def test_reset_both_clients(self):
        http_client._async_client = AsyncMock()
        http_client._sync_client = MagicMock()
        http_client.reset_http_clients()
        assert http_client._async_client is None
        assert http_client._sync_client is None


class TestHTTPClientWrappers:
    def teardown_method(self):
        http_client._async_client = None
        http_client._sync_client = None

    @pytest.mark.asyncio
    async def test_async_wrappers_delegate(self):
        client = AsyncMock()
        client.get.return_value = "G"
        client.post.return_value = "P"
        client.put.return_value = "U"
        client.delete.return_value = "D"
        with patch("core.http_client.get_async_client", return_value=client):
            assert await http_client.async_get("http://x") == "G"
            assert await http_client.async_post("http://x", json={"a": 1}) == "P"
            assert await http_client.async_put("http://x", data=b"1") == "U"
            assert await http_client.async_delete("http://x") == "D"
        client.get.assert_awaited_once_with("http://x")
        client.post.assert_awaited_once_with("http://x", json={"a": 1})
        client.put.assert_awaited_once_with("http://x", data=b"1")
        client.delete.assert_awaited_once_with("http://x")

    def test_sync_wrappers_delegate(self):
        client = MagicMock()
        client.get.return_value = "G"
        client.post.return_value = "P"
        client.put.return_value = "U"
        client.delete.return_value = "D"
        with patch("core.http_client.get_sync_client", return_value=client):
            assert http_client.sync_get("http://x") == "G"
            assert http_client.sync_post("http://x", json={"a": 1}) == "P"
            assert http_client.sync_put("http://x", data=b"1") == "U"
            assert http_client.sync_delete("http://x") == "D"
        client.get.assert_called_once_with("http://x")
        client.post.assert_called_once_with("http://x", json={"a": 1})
        client.put.assert_called_once_with("http://x", data=b"1")
        client.delete.assert_called_once_with("http://x")


# ============================================================================
# core.directory_permission
# ============================================================================


class TestDirectoryPermissionService:
    def _service(self):
        cache = _fake_cache()
        with patch("core.directory_permission.get_governance_cache", return_value=cache):
            svc = DirectoryPermissionService()
        return svc, cache

    def test_cache_hit_returns_cached(self):
        svc, cache = self._service()
        cached = {"allowed": True, "suggest_only": False, "reason": "cached", "maturity_level": "AUTONOMOUS"}
        cache.get.return_value = cached
        r = svc.check_directory_permission("a1", "/tmp/x", AgentStatus.AUTONOMOUS)
        assert r == cached
        cache.get.assert_called_once_with("a1", "dir:/tmp/x")

    def test_student_suggest_only_in_tmp(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/tmp/work", AgentStatus.STUDENT)
        assert r["allowed"] is True
        assert r["suggest_only"] is True
        assert r["maturity_level"] == "student"
        assert r["resolved_path"] == str(os.path.realpath("/tmp/work"))

    def test_student_denied_outside_allowed(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/var/log", AgentStatus.STUDENT)
        assert r["allowed"] is False
        assert r["suggest_only"] is True

    def test_intern_documents_suggest_only(self):
        svc, _ = self._service()
        home = os.path.expanduser("~")
        r = svc.check_directory_permission("a1", f"{home}/Documents/report", AgentStatus.INTERN)
        assert r["allowed"] is True
        assert r["suggest_only"] is True

    def test_supervised_desktop_suggest_only(self):
        svc, _ = self._service()
        home = os.path.expanduser("~")
        r = svc.check_directory_permission("a1", f"{home}/Desktop", AgentStatus.SUPERVISED)
        assert r["allowed"] is True
        assert r["suggest_only"] is True

    def test_autonomous_tmp_auto_execute(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/tmp", AgentStatus.AUTONOMOUS)
        assert r["allowed"] is True
        assert r["suggest_only"] is False
        assert "auto-execute" in r["reason"]

    def test_autonomous_denied_desktop(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/somewhere/else", AgentStatus.AUTONOMOUS)
        assert r["allowed"] is False

    def test_unknown_maturity_defaults_deny(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/tmp", AgentStatus.PAUSED)
        assert r["allowed"] is False
        assert r["suggest_only"] is True
        assert r["maturity_level"] == "paused"

    def test_tilde_expansion(self):
        svc, _ = self._service()
        home = os.path.expanduser("~")
        r = svc.check_directory_permission("a1", "~/Downloads", AgentStatus.STUDENT)
        assert r["allowed"] is True
        assert r["resolved_path"].startswith(home)

    def test_dotdot_resolution(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/tmp/../tmp/work", AgentStatus.AUTONOMOUS)
        assert r["allowed"] is True

    def test_blocked_exact(self):
        svc, _ = self._service()
        for blocked in ["/etc", "/etc/passwd"]:
            r = svc.check_directory_permission("a1", blocked, AgentStatus.AUTONOMOUS)
            assert r["allowed"] is False
            assert "blocked" in r["reason"]

    def test_blocked_macos_canonical(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/private/etc", AgentStatus.AUTONOMOUS)
        assert r["allowed"] is False

    def test_sibling_prefix_not_blocked(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/etc2", AgentStatus.AUTONOMOUS)
        assert r["allowed"] is False  # not in allowed list either...
        assert "blocked" not in r["reason"].lower()  # ...but NOT a blocked-dir hit

    def test_sibling_prefix_not_allowed(self):
        svc, _ = self._service()
        r = svc.check_directory_permission("a1", "/tmp2", AgentStatus.AUTONOMOUS)
        assert r["allowed"] is False, r

    def test_cached_result_reused_without_recomputation(self):
        svc, cache = self._service()
        cache.get.return_value = None
        r1 = svc.check_directory_permission("a1", "/tmp", AgentStatus.AUTONOMOUS)
        assert r1["allowed"] is True
        assert cache.set.call_count == 1
        cache.get.return_value = r1
        r2 = svc.check_directory_permission("a1", "/tmp", AgentStatus.AUTONOMOUS)
        assert r2 is r1
        assert cache.set.call_count == 1

    def test_expand_path_happy(self):
        svc, _ = self._service()
        assert str(svc._expand_path("~/x")) == os.path.realpath(os.path.expanduser("~/x"))
        assert str(svc._expand_path("/tmp/../tmp")) == os.path.realpath("/tmp")

    def test_expand_path_error_falls_back(self):
        svc, _ = self._service()
        with patch("core.directory_permission.Path") as p_cls:
            p_cls.return_value.expanduser.return_value = p_cls.return_value
            p_cls.return_value.resolve.side_effect = OSError("bad path")
            out = svc._expand_path("/some/path")
        assert out == p_cls.return_value

    def test_is_blocked_resolve_error_still_matches(self):
        import pathlib
        svc, _ = self._service()
        d = pathlib.Path("/etc/passwd")
        with patch("core.directory_permission.Path") as p_cls:
            p_cls.return_value.resolve.side_effect = OSError("bad path")
            assert svc._is_blocked(d) is True

    def test_is_blocked_no_match(self):
        svc, _ = self._service()
        assert svc._is_blocked(os.path.realpath("/tmp")) is False

    def test_is_within_allowed_match_and_mismatch(self):
        svc, _ = self._service()
        tmp = os.path.realpath("/tmp")
        assert svc._is_within_allowed(tmp + "/sub", [tmp]) is True
        assert svc._is_within_allowed(tmp + "2", [tmp]) is False
        assert svc._is_within_allowed("/nowhere", [tmp]) is False

    def test_get_reason_both_branches(self):
        svc, _ = self._service()
        assert "can suggest" in svc._get_reason(AgentStatus.STUDENT, True)
        assert "can auto-execute" in svc._get_reason(AgentStatus.AUTONOMOUS, False)

    def test_get_from_cache_valid_key(self):
        svc, cache = self._service()
        cache.get.return_value = {"allowed": True}
        assert svc._get_from_cache("a1:dir:/tmp") == {"allowed": True}
        cache.get.assert_called_once_with("a1", "dir:/tmp")

    def test_get_from_cache_malformed_key(self):
        svc, _ = self._service()
        assert svc._get_from_cache("no-colons-here") is None

    def test_cache_result_writes(self):
        svc, cache = self._service()
        result = {"allowed": True}
        svc._cache_result("a1:dir:/tmp", result)
        cache.set.assert_called_once_with("a1", "dir:/tmp", result)


class TestDirectoryPermissionGlobals:
    def test_global_service_singleton(self):
        _reset_dir_service()
        try:
            svc = get_directory_permission_service()
            assert isinstance(svc, DirectoryPermissionService)
            assert get_directory_permission_service() is svc
        finally:
            _reset_dir_service()

    def test_convenience_function(self):
        _reset_dir_service()
        try:
            with patch.object(DirectoryPermissionService, "check_directory_permission",
                              return_value={"allowed": True}) as mock_check:
                from core.directory_permission import check_directory_permission
                r = check_directory_permission("a1", "/tmp", AgentStatus.AUTONOMOUS)
            assert r["allowed"] is True
            mock_check.assert_called_once_with("a1", "/tmp", AgentStatus.AUTONOMOUS)
        finally:
            _reset_dir_service()


def _reset_dir_service():
    dirperm._directory_permission_service = None
