# -*- coding: utf-8 -*-
"""Coverage wave 80 — core/memory_integration_mixin.py to >=95% (standalone;
embedding service, entity extractor, and LanceDB handler fully mocked —
zero LLM spend, zero network, no real DB).

Covers:
- BackfillJob lifecycle + to_dict (with/without timestamps).
- Mixin __init__: lancedb handler resolved / ImportError fallback,
  ENABLE_LLM_EXTRACTION env toggle.
- get_integration_type: all 7 categories + unknown.
- backfill_to_memory: job creation + task scheduling; handle_error callback
  paths (exception / CancelledError / generic handler failure).
- _run_backfill: fetch exception → failed; empty records → completed/100;
  batch loop: entity without id (skip), short text (skip), embedding +
  add_documents retry (first-try success, transient failure then success,
  exhausted retries → failed_records), lancedb None → no storage path,
  progress %, completion summary.
- get_job_status found/missing.
- IntegrationBackfillManager.trigger_backfill: unsupported integration,
  dynamic import + backfill, import/instantiation/exception → error dict.
- trigger_all_backfills: mixed successes/errors/exceptions.
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.memory_integration_mixin as mod
from core.memory_integration_mixin import (
    BackfillJob,
    IntegrationBackfillManager,
    MemoryIntegrationMixin,
)


class _FakeIntegration(MemoryIntegrationMixin):
    """Concrete mixin subclass for tests."""

    def __init__(self, integration_id="outlook", workspace_id="ws1",
                 records=None, fetch_error=None):
        self._records = records or []
        self._fetch_error = fetch_error
        with patch.object(mod, "EmbeddingService", MagicMock), \
             patch.object(mod, "IntegrationEntityExtractor", MagicMock), \
             patch("core.lancedb_handler.get_lancedb_handler"):
            super().__init__(integration_id, workspace_id)

    async def fetch_records(self, start_date=None, end_date=None, limit=500):
        if self._fetch_error:
            raise self._fetch_error
        return self._records


def _await(task):
    """Run an asyncio.Task to completion, swallowing its outcome so the
    done-callback (which records the failure on the job) is drained."""
    loop = asyncio.get_event_loop_policy().get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    try:
        return loop.run_until_complete(task)
    except (asyncio.CancelledError, Exception):
        return None
    finally:
        pass


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ============================================================================
# BackfillJob
# ============================================================================

def test_backfill_job_to_dict_no_timestamps():
    job = BackfillJob("job-1", "outlook")
    d = job.to_dict()
    assert d["job_id"] == "job-1"
    assert d["integration_id"] == "outlook"
    assert d["status"] == "pending"
    assert d["progress"] == 0
    assert d["started_at"] is None
    assert d["completed_at"] is None
    assert d["error"] is None


def test_backfill_job_to_dict_with_timestamps():
    from datetime import datetime
    job = BackfillJob("job-2", "gmail")
    job.status = "completed"
    job.started_at = datetime(2026, 8, 1, 10, 0, 0)
    job.completed_at = datetime(2026, 8, 1, 10, 5, 0)
    job.progress = 100
    job.total_records = 10
    job.processed_records = 8
    job.failed_records = 2
    d = job.to_dict()
    assert d["started_at"] == "2026-08-01T10:00:00"
    assert d["completed_at"] == "2026-08-01T10:05:00"
    assert d["processed_records"] == 8


# ============================================================================
# Constructor / helpers
# ============================================================================

def test_init_resolves_lancedb_handler():
    fake_lancedb = MagicMock()
    with patch.object(mod, "EmbeddingService"), \
         patch.object(mod, "IntegrationEntityExtractor"), \
         patch("core.lancedb_handler.get_lancedb_handler",
               return_value=fake_lancedb) as get_handler:
        mixin = _FakeIntegration.__new__(_FakeIntegration)
        MemoryIntegrationMixin.__init__(mixin, "outlook", "ws1")
    get_handler.assert_called_once_with("ws1")
    assert mixin.lancedb is fake_lancedb
    assert mixin.use_llm_extraction is False


def test_init_lancedb_import_error_fallback():
    with patch.object(mod, "EmbeddingService"), \
         patch.object(mod, "IntegrationEntityExtractor"):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "core.lancedb_handler":
                raise ImportError("no lancedb")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            mixin = _FakeIntegration.__new__(_FakeIntegration)
            MemoryIntegrationMixin.__init__(mixin, "slack", "ws1")
    assert mixin.lancedb is None


def test_init_llm_extraction_env_toggle():
    with patch.dict(os.environ, {"ENABLE_LLM_EXTRACTION": "true"}), \
         patch.object(mod, "EmbeddingService"), \
         patch.object(mod, "IntegrationEntityExtractor"), \
         patch("core.lancedb_handler.get_lancedb_handler"):
        mixin = _FakeIntegration.__new__(_FakeIntegration)
        MemoryIntegrationMixin.__init__(mixin, "jira", "ws1")
    assert mixin.use_llm_extraction is True


def test_get_integration_type_all_categories():
    cases = {
        "outlook": "email", "gmail": "email", "email": "email",
        "salesforce": "crm", "hubspot": "crm", "zoho": "crm", "pipedrive": "crm",
        "slack": "communication", "teams": "communication", "discord": "communication",
        "jira": "project", "asana": "project", "notion": "project",
        "trello": "project", "monday": "project",
        "zendesk": "support", "intercom": "support", "freshdesk": "support",
        "google_calendar": "calendar", "outlook_calendar": "calendar",
        "calendar": "calendar",
        "random_thing": "other",
    }
    mixin = _FakeIntegration.__new__(_FakeIntegration)
    for integration_id, expected in cases.items():
        mixin.integration_id = integration_id
        assert mixin.get_integration_type() == expected


# ============================================================================
# backfill_to_memory + error callbacks
# ============================================================================

def test_backfill_to_memory_starts_job():
    mixin = _FakeIntegration(integration_id="outlook")
    result = _run(mixin.backfill_to_memory(limit=10))
    assert result["success"] is True
    assert result["integration_id"] == "outlook"
    assert result["status"] == "started"
    job = mod._backfill_jobs.get(result["job_id"])
    assert job is not None
    assert job.task is not None


def _run_on_same_loop(mixin, limit=10):
    """Run backfill_to_memory + its spawned task on ONE loop so the
    done-callback actually fires (cross-loop tasks never invoke callbacks).
    Returns (job, callback) — callback captured while the task is still
    pending (asyncio clears _callbacks once the task finishes)."""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(mixin.backfill_to_memory(limit=limit))
        job = mod._backfill_jobs[result["job_id"]]
        cb = job.task._callbacks[0][0][0] if job.task._callbacks else None
        try:
            loop.run_until_complete(job.task)
        except BaseException:
            pass
        return job, cb
    finally:
        loop.close()


def test_backfill_error_callback_marks_job_failed():
    """Real handle_error: task fails with an uncaught exception (via a
    monkeypatched _run_backfill) → callback marks the job failed."""
    mixin = _FakeIntegration(integration_id="outlook")
    mixin._run_backfill = AsyncMock(side_effect=RuntimeError("boom"))
    job, _ = _run_on_same_loop(mixin)
    assert job.status == "failed"
    assert job.error == "boom"
    assert job.completed_at is not None


def test_backfill_error_callback_cancelled():
    """REAL handle_error: task cancelled → except CancelledError branch."""
    mixin = _FakeIntegration(integration_id="outlook")
    mixin._run_backfill = AsyncMock(side_effect=asyncio.CancelledError())
    job, _ = _run_on_same_loop(mixin)
    assert job.status == "cancelled"


def test_backfill_error_callback_generic_handler_exception():
    """REAL handle_error where task.exception() itself explodes → generic
    branch (job.error prefixed with 'Handler error:'). The task is kept
    pending (blocking _run_backfill) so the callback is still registered;
    then it is driven with a task whose exception() raises."""
    mixin = _FakeIntegration(integration_id="outlook")

    async def _blocking(*a, **k):
        await asyncio.sleep(3600)

    mixin._run_backfill = _blocking
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(mixin.backfill_to_memory(limit=10))
        job = mod._backfill_jobs[result["job_id"]]
        cb = job.task._callbacks[0][0]
        job.task.cancel()
        try:
            loop.run_until_complete(job.task)
        except BaseException:
            pass

        class _BoomTask:
            def done(self):
                return True

            def exception(self):
                raise RuntimeError("probe")

        # job.task pointing at a still-pending task exercises the
        # cleanup-cancel branch (line 213) inside the exception path.
        class _PendingTask:
            def __init__(self):
                self.cancelled = False

            def done(self):
                return False

            def cancel(self):
                self.cancelled = True

        # 1) exception() RETURNS an exception → 205-213 + cancel() body.
        pending = _PendingTask()
        job.task = pending

        class _FailedTask:
            def done(self):
                return True

            def exception(self):
                return RuntimeError("boom")

        cb(_FailedTask())
        assert pending.cancelled is True

        # 2) exception() RAISES → generic branch 219-222.
        cb(_BoomTask())
        assert job.error == "Handler error: probe"
    finally:
        loop.close()
    assert job.status == "failed"
    assert job.error == "Handler error: probe"


def test_get_job_status_found_and_missing():
    job = BackfillJob("job-x", "outlook")
    mod._backfill_jobs["job-x"] = job
    assert mod.MemoryIntegrationMixin.get_job_status("job-x")["job_id"] == "job-x"
    assert mod.MemoryIntegrationMixin.get_job_status("nope") is None


def test_abstract_fetch_records_body():
    """Directly invoke the abstract method body (a bare pass)."""
    mixin = _FakeIntegration.__new__(_FakeIntegration)
    result = _run(MemoryIntegrationMixin.fetch_records(mixin))
    assert result is None


# ============================================================================
# _run_backfill
# ============================================================================

def test_run_backfill_fetch_exception():
    mixin = _FakeIntegration(integration_id="outlook", fetch_error=RuntimeError("nope"))
    job = BackfillJob("j1", "outlook")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert job.status == "failed"
    assert job.error == "nope"


def test_run_backfill_no_records_completes():
    mixin = _FakeIntegration(integration_id="gmail", records=[])
    job = BackfillJob("j2", "gmail")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert job.status == "completed"
    assert job.progress == 100
    assert job.total_records == 0
    assert job.completed_at is not None


def test_run_backfill_entities_without_lancedb():
    """lancedb None → storage loop skipped entirely, still completes."""
    mixin = _FakeIntegration(integration_id="slack", records=[{"id": "r1"}])
    mixin.entity_extractor.extract = AsyncMock(
        return_value=[{"id": "e1", "text": "some long text here ok"}])
    mixin.lancedb = None
    job = BackfillJob("j3", "slack")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert job.status == "completed"
    assert job.progress == 100


def test_run_backfill_entity_skipped_no_id():
    mixin = _FakeIntegration(integration_id="outlook", records=[{"noid": True}])
    mixin.lancedb = MagicMock()
    mixin.entity_extractor.extract = AsyncMock(
        return_value=[{"text": "some long text here ok"}])
    job = BackfillJob("j4", "outlook")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert job.failed_records == 1
    assert job.processed_records == 0
    assert job.status == "completed"


def test_run_backfill_entity_short_text_skipped():
    mixin = _FakeIntegration(integration_id="outlook", records=[{"id": "r1"}])
    mixin.lancedb = MagicMock()
    mixin.entity_extractor.extract = AsyncMock(
        return_value=[{"id": "e1", "text": "short"}])
    job = BackfillJob("j5", "outlook")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert job.failed_records == 1
    assert job.processed_records == 0
    assert job.status == "completed"


def test_run_backfill_entity_processing_error():
    mixin = _FakeIntegration(integration_id="outlook", records=[{"id": "r1"}])
    mixin.lancedb = MagicMock()
    mixin.entity_extractor.extract = AsyncMock(
        return_value=[{"id": "e1", "text": "some long text here ok"}])
    mixin.embedding_service.generate_embedding = MagicMock(side_effect=RuntimeError("emb"))
    job = BackfillJob("j6", "outlook")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert job.failed_records == 1
    assert job.status == "completed"


def test_run_backfill_add_documents_retry_success():
    mixin = _FakeIntegration(integration_id="outlook", records=[{"id": "r1"}])
    lancedb = MagicMock()
    lancedb.add_documents = AsyncMock(side_effect=[RuntimeError("db down"), None])
    mixin.lancedb = lancedb
    mixin.entity_extractor.extract = AsyncMock(
        return_value=[{"id": "e1", "text": "some long text here ok"}])
    job = BackfillJob("j7", "outlook")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert lancedb.add_documents.await_count == 2
    assert job.processed_records == 1
    assert job.failed_records == 0
    assert job.status == "completed"
    assert job.progress == 100


def test_run_backfill_add_documents_retries_exhausted():
    mixin = _FakeIntegration(integration_id="outlook", records=[{"id": "r1"}])
    lancedb = MagicMock()
    lancedb.add_documents = AsyncMock(side_effect=RuntimeError("still down"))
    mixin.lancedb = lancedb
    mixin.entity_extractor.extract = AsyncMock(
        return_value=[{"id": "e1", "text": "some long text here ok"}])
    job = BackfillJob("j8", "outlook")
    _run(mixin._run_backfill(job, None, None, 500, 50))
    assert lancedb.add_documents.await_count == 3
    assert job.failed_records == 1
    assert job.processed_records == 0
    assert job.status == "completed"


def test_run_backfill_multiple_batches_progress():
    mixin = _FakeIntegration(
        integration_id="outlook",
        records=[{"id": f"r{i}"} for i in range(6)],
    )
    lancedb = MagicMock()
    lancedb.add_documents = AsyncMock()
    mixin.lancedb = lancedb
    mixin.entity_extractor.extract = AsyncMock(
        return_value=[{"id": f"e{i}", "text": "some long text here ok"}
                      for i in range(4)])
    job = BackfillJob("j9", "outlook")
    _run(mixin._run_backfill(job, None, None, 500, 2))
    assert job.processed_records == 12
    assert job.progress == 100
    assert job.status == "completed"


# ============================================================================
# IntegrationBackfillManager
# ============================================================================

def test_trigger_backfill_unsupported():
    result = _run(IntegrationBackfillManager.trigger_backfill("nothing"))
    assert result["success"] is False
    assert "not found or not supported" in result["error"]


def test_trigger_backfill_dynamic_import():
    fake_service = MagicMock()
    fake_service.backfill_to_memory = AsyncMock(return_value={"success": True,
                                                              "job_id": "j1"})
    fake_module = MagicMock()
    fake_module.OutlookIntegration = lambda: fake_service
    with patch("builtins.__import__", return_value=fake_module):
        result = _run(IntegrationBackfillManager.trigger_backfill("outlook"))
    assert result["success"] is True
    fake_service.backfill_to_memory.assert_awaited_once()


def test_trigger_backfill_exception():
    with patch("builtins.__import__", side_effect=ImportError("no module")):
        result = _run(IntegrationBackfillManager.trigger_backfill("outlook"))
    assert result["success"] is False
    assert "no module" in result["error"]


def test_trigger_all_backfills_raising():
    """A trigger_backfill that itself raises → per-integration error entry."""
    with patch.object(IntegrationBackfillManager, "trigger_backfill",
                      side_effect=RuntimeError("scheduler down")):
        result = _run(IntegrationBackfillManager.trigger_all_backfills())
    assert result["success"] is False
    assert result["total_triggered"] == 0
    assert len(result["errors"]) == 8
    assert all("scheduler down" in e for e in result["errors"])


def test_trigger_all_backfills_mixed():
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "integrations.outlook_integration":
            fake_service = MagicMock()
            fake_service.backfill_to_memory = AsyncMock(
                return_value={"success": True, "job_id": "ojob"})
            fake_module = MagicMock()
            fake_module.OutlookIntegration = lambda: fake_service
            return fake_module
        if name == "integrations.gmail_service":
            fake_service = MagicMock()
            fake_service.backfill_to_memory = AsyncMock(
                return_value={"success": False, "error": "gmail exploded"})
            fake_module = MagicMock()
            fake_module.GmailService = lambda: fake_service
            return fake_module
        if name == "integrations.slack_service":
            raise ImportError("slack missing")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        result = _run(IntegrationBackfillManager.trigger_all_backfills(limit_per_integration=10))
    assert result["success"] is True
    assert result["total_triggered"] == 1
    assert result["job_ids"] == ["ojob"]
    assert len(result["errors"]) == 7
