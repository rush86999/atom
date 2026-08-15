# -*- coding: utf-8 -*-
"""W87B-B — coverage push for core.historical_sync_service (part 2 of the
w87b wave; part 1 = test_covpush_w87b_utils_a.py). Standalone >=95% required.

Measured before-% (existing carrier suites) -> after-% (this file alone):

 10. core/historical_sync_service.py  (344 stmts)  99% -> 100%

Style: mocked deps, zero LLM spend, zero network, in-memory SQLite for the
ORM-backed service (established carrier-suite convention). No real DB.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

import core.historical_sync_service as hss

from core.models import HistoricalSyncJob
# 10. historical_sync_service
# ============================================================================


@pytest.fixture(scope="module")
def hss_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from core.models_registration import Base
    from core.models import HistoricalSyncJob

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng, tables=[HistoricalSyncJob.__table__])
    yield eng
    eng.dispose()


@pytest.fixture
def hss_db(hss_engine):
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=hss_engine)
    session = Session()
    yield session
    session.query(HistoricalSyncJob).delete()
    session.commit()
    session.close()


def hss_make_job(db, **overrides):
    from core.models import HistoricalSyncJob

    data = dict(
        tenant_id="tenant-1",
        integration_id="salesforce",
        source_connection_id="conn-1",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 4, 1, tzinfo=timezone.utc),
        status="pending",
        scope="personal",
        chunk_size=100,
    )
    data.update(overrides)
    job = HistoricalSyncJob(id=str(uuid.uuid4()), **data)
    db.add(job)
    db.commit()
    return job


def hss_make_service(db, **kwargs):
    svc = hss.HistoricalSyncService(tenant_id="tenant-1", db=db, **kwargs)
    svc._ingestion_pipeline = Mock()
    return svc


def hss_config():
    return SimpleNamespace(
        integration_id="salesforce",
        entity_types=["contacts"],
        sync_last_n_days=30,
        max_records_per_sync=100,
        include_metadata=True,
        sync_mode="incremental",
        discovery_frequency_hours=168,
    )


class TestHssModuleHelpers:
    def test_get_memory_threshold(self):
        assert hss._get_memory_threshold(2048) == 1638

    def test_get_memory_usage_with_psutil(self, monkeypatch):
        proc = Mock()
        proc.memory_info.return_value = SimpleNamespace(rss=500 * 1024 * 1024)
        fake_psutil = Mock()
        fake_psutil.Process.return_value = proc
        monkeypatch.setitem(__import__("sys").modules, "psutil", fake_psutil)
        assert hss._get_memory_usage() == 500

    def test_get_memory_usage_without_psutil(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "psutil", None)
        assert hss._get_memory_usage() == 0

    async def test_log_job_event_appends_and_caps(self, hss_db):
        job = hss_make_job(hss_db)
        for i in range(12):
            hss._log_job_event(hss_db, job.id, "tenant-1", f"evt-{i}")
        hss_db.refresh(job)
        assert len(job.checkpoint_data["events"]) == 10
        assert job.checkpoint_data["events"][-1].endswith("evt-11")

    async def test_log_job_event_missing_job(self, hss_db):
        hss._log_job_event(hss_db, "missing", "tenant-1", "x")
        assert hss_db.query(HistoricalSyncJob).count() == 0

    async def test_log_job_event_exception_swallowed(self):
        bad_db = Mock()
        hss._log_job_event(bad_db, "j", "t", "x")
        assert bad_db.query.called


class TestLLMExtractWithHandler:
    async def test_success_plain_json(self):
        llm = AsyncMock()
        llm.generate.return_value = '{"entities": [{"name": "Acme", "type": "org", "canonical_type": "organization", "confidence": 0.9}], "relationships": [{"from": "A", "to": "B", "type": "owns"}]}'
        entities, rels = await hss._llm_extract_with_handler(llm, "text", "doc1", "src", "ws", "tenant")
        assert len(entities) == 1
        assert entities[0].name == "Acme"
        assert entities[0].properties["canonical_type"] == "organization"
        assert entities[0].properties["confidence"] == 0.9
        assert len(rels) == 1
        assert rels[0].from_entity == "A"
        llm.generate.assert_called()

    async def test_success_fenced_json(self):
        llm = AsyncMock()
        llm.generate.return_value = '```json\n{"entities": [{"name": "A", "type": "t"}]}\n```'
        entities, _ = await hss._llm_extract_with_handler(llm, "text", "d", "s", "w", "t")
        assert entities[0].name == "A"

    async def test_success_fenced_plain(self):
        llm = AsyncMock()
        llm.generate.return_value = '```\n{"entities": [{"name": "A", "type": "t"}]}\n```'
        entities, _ = await hss._llm_extract_with_handler(llm, "text", "d", "s", "w", "t")
        assert entities[0].name == "A"

    async def test_extra_metadata_and_system_override(self):
        llm = AsyncMock()
        llm.generate.return_value = '{"entities": [{"name": "A", "type": "t"}], "relationships": [{"from": "A", "to": "B", "type": "x"}]}'
        entities, rels = await hss._llm_extract_with_handler(
            llm, "text", "d", "s", "w", "t",
            system_instruction_override="custom",
            extra_metadata={"channel": "email"},
        )
        assert entities[0].properties["channel"] == "email"
        assert rels[0].properties["channel"] == "email"

    async def test_empty_response(self):
        llm = AsyncMock()
        llm.generate.side_effect = ["", '{"entities": [{"name": "A", "type": "t"}]}']
        entities, _ = await hss._llm_extract_with_handler(llm, "text", "d", "s", "w", "t")
        assert entities[0].name == "A"

    async def test_json_decode_retry_then_success(self):
        llm = AsyncMock()
        llm.generate.side_effect = ["not json", '{"entities": [{"name": "A", "type": "t"}]}']
        entities, _ = await hss._llm_extract_with_handler(llm, "text", "d", "s", "w", "t")
        assert entities[0].name == "A"

    async def test_all_models_fail_returns_empty(self):
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("llm down")
        entities, rels = await hss._llm_extract_with_handler(llm, "text", "d", "s", "w", "t")
        assert entities == []
        assert rels == []

    async def test_non_numeric_confidence_does_not_kill_chunk(self):
        llm = AsyncMock()
        llm.generate.return_value = '{"entities": [{"name": "A", "type": "t", "confidence": "high"}]}'
        entities, _ = await hss._llm_extract_with_handler(llm, "text", "d", "s", "w", "t")
        assert entities[0].properties["confidence"] == 0.0

    async def test_entity_without_canonical_type(self):
        llm = AsyncMock()
        llm.generate.return_value = '{"entities": [{"name": "A", "type": "t"}], "relationships": []}'
        entities, rels = await hss._llm_extract_with_handler(llm, "text", "d", "s", "w", "t")
        assert "canonical_type" not in entities[0].properties
        assert rels == []

    async def test_text_truncated_to_6000_chars(self):
        llm = AsyncMock()
        llm.generate.return_value = '{"entities": []}'
        long_text = "x" * 9000
        await hss._llm_extract_with_handler(llm, long_text, "d", "s", "w", "t")
        prompt_arg = llm.generate.call_args.kwargs["prompt"]
        assert "x" * 6000 in prompt_arg
        assert "x" * 6001 not in prompt_arg


class TestServiceProperties:
    async def test_db_property_creates_internal_session(self, hss_db, monkeypatch):
        svc = hss.HistoricalSyncService(tenant_id="t")
        monkeypatch.setattr(hss, "SessionLocal", lambda: hss_db)
        assert svc.db is hss_db
        assert svc._internal_session is True

    async def test_db_property_returns_existing(self, hss_db):
        svc = hss.HistoricalSyncService(tenant_id="t", db=hss_db)
        assert svc.db is hss_db
        assert svc._internal_session is False

    async def test_workspace_id_falls_back_to_tenant(self, hss_db):
        svc = hss.HistoricalSyncService(tenant_id="t", db=hss_db)
        assert svc.workspace_id == "t"

    async def test_workspace_id_uses_provided(self, hss_db):
        svc = hss.HistoricalSyncService(tenant_id="t", db=hss_db, workspace_id="ws")
        assert svc.workspace_id == "ws"

    async def test_ingestion_pipeline_lazy(self, hss_db, monkeypatch):
        monkeypatch.setattr(hss, "IngestionPipelineService", Mock(return_value="pipe"))
        svc = hss.HistoricalSyncService(tenant_id="t", db=hss_db)
        assert svc.ingestion_pipeline == "pipe"
        assert svc.ingestion_pipeline == "pipe"

    async def test_integration_registry_lazy(self, hss_db, monkeypatch):
        monkeypatch.setattr(hss, "IntegrationRegistry", Mock(return_value="reg"))
        svc = hss.HistoricalSyncService(tenant_id="t", db=hss_db)
        assert svc.integration_registry == "reg"
        assert svc.integration_registry == "reg"


class TestStartHistoricalSync:
    async def test_default_end_date_and_enqueue(self, hss_db):
        svc = hss_make_service(hss_db)
        queue = AsyncMock()
        queue.enqueue = AsyncMock()
        with patch("core.historical_sync_service.SyncJobQueue", return_value=queue):
            job_id = await svc.start_historical_sync(
                "salesforce", "conn-1", datetime(2024, 1, 1, tzinfo=timezone.utc)
            )
        job = hss_db.query(HistoricalSyncJob).filter_by(id=job_id).first()
        assert job.end_date == datetime(2024, 1, 1) + timedelta(days=90)
        queue.enqueue.assert_awaited_once()

    async def test_explicit_end_date(self, hss_db):
        svc = hss_make_service(hss_db)
        end = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with patch("core.historical_sync_service.SyncJobQueue") as qcls:
            qcls.return_value.enqueue = AsyncMock()
            job_id = await svc.start_historical_sync(
                "salesforce", "conn-1", datetime(2024, 1, 1, tzinfo=timezone.utc), end_date=end
            )
        job = hss_db.query(HistoricalSyncJob).filter_by(id=job_id).first()
        assert job.end_date == datetime(2024, 6, 1)

    async def test_enqueue_failure_keeps_job_pending(self, hss_db):
        svc = hss_make_service(hss_db)
        queue = Mock()
        queue.enqueue = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("core.historical_sync_service.SyncJobQueue", return_value=queue):
            job_id = await svc.start_historical_sync("salesforce", "conn-1", datetime(2024, 1, 1))
        job = hss_db.query(HistoricalSyncJob).filter_by(id=job_id).first()
        assert job.status == "pending"


class TestHeartbeatAndMemory:
    async def test_heartbeat_loop_cancel_stops_thread(self, hss_db, monkeypatch):
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=hss_db.bind)
        monkeypatch.setattr(hss, "SessionLocal", Session)
        svc = hss.HistoricalSyncService(tenant_id="t")
        task = asyncio.create_task(svc._heartbeat_loop("job-1"))
        await asyncio.sleep(0.15)
        task.cancel()
        await task
        assert svc._hb_stop is not None
        assert svc._hb_stop.is_set()

    async def test_heartbeat_thread_db_error_is_swallowed(self, monkeypatch):
        def _raise():
            raise RuntimeError("no db")

        monkeypatch.setattr(hss, "SessionLocal", _raise)
        svc = hss.HistoricalSyncService(tenant_id="t")
        task = asyncio.create_task(svc._heartbeat_loop("job-2"))
        await asyncio.sleep(0.15)
        task.cancel()
        await task
        assert svc._hb_stop.is_set()

    async def test_heartbeat_thread_crash_logged(self, monkeypatch):
        def _raise():
            raise RuntimeError("no db")

        real_wait = threading.Event.wait

        def _crashy_wait(self, timeout=None):
            if timeout is not None:
                raise RuntimeError("wait crash")
            return real_wait(self, timeout)

        monkeypatch.setattr(hss, "SessionLocal", _raise)
        monkeypatch.setattr(threading.Event, "wait", _crashy_wait)
        svc = hss.HistoricalSyncService(tenant_id="t")
        task = asyncio.create_task(svc._heartbeat_loop("job-3"))
        await asyncio.sleep(0.15)
        task.cancel()
        await task
        assert svc._hb_stop.is_set()

    async def test_memory_check_normal(self, monkeypatch):
        monkeypatch.setattr(hss, "_get_memory_usage", lambda: 100)
        monkeypatch.setattr(hss, "_get_memory_threshold", lambda: 1000)
        svc = hss_make_service(hss_db)
        assert await svc._check_memory_and_gc("job-1") is True

    async def test_memory_check_high_triggers_gc(self, hss_db, monkeypatch):
        monkeypatch.setattr(hss, "_get_memory_usage", lambda: 1000)
        monkeypatch.setattr(hss, "_get_memory_threshold", lambda: 100)
        monkeypatch.setattr(hss.gc, "collect", Mock())
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        svc = hss_make_service(hss_db)
        assert await svc._check_memory_and_gc("job-1") is False
        hss.gc.collect.assert_called_once()

    async def test_memory_check_exception_is_non_fatal(self, hss_db, monkeypatch):
        def _raise():
            raise RuntimeError("oom probe failed")

        monkeypatch.setattr(hss, "_get_memory_usage", _raise)
        svc = hss_make_service(hss_db)
        assert await svc._check_memory_and_gc("job-1") is True


class TestExtractChunkAndIngest:
    async def _patch_env(self, monkeypatch, hss_db):
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=hss_db.bind)
        monkeypatch.setattr(hss, "SessionLocal", Session)
        engine = Mock()
        engine.ingest_structured_data = Mock()
        monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", Mock(return_value=engine))
        monkeypatch.setattr("core.llm_service.LLMService", Mock())
        return engine

    async def test_extracts_and_ingests(self, monkeypatch, hss_db):
        engine = await self._patch_env(monkeypatch, hss_db)
        from core.graphrag_engine import Entity, Relationship

        entities = [Entity(id="e1", name="A", entity_type="t", description="", properties={})]
        rels = [Relationship(id="r1", from_entity="A", to_entity="B", rel_type="x", description="", properties={})]
        monkeypatch.setattr(
            hss, "_llm_extract_with_handler",
            AsyncMock(return_value=(entities, rels)),
        )
        svc = hss_make_service(hss_db)
        ent_count, rel_count = await svc._extract_chunk_and_ingest("job-1", 0, [("d1", "text one", "src")], "ws")
        assert ent_count == 1
        assert rel_count == 1
        engine.ingest_structured_data.assert_called_once()

    async def test_empty_extraction_skips_ingestion(self, monkeypatch, hss_db):
        engine = await self._patch_env(monkeypatch, hss_db)
        monkeypatch.setattr(hss, "_llm_extract_with_handler", AsyncMock(return_value=([], [])))
        svc = hss_make_service(hss_db)
        ent_count, rel_count = await svc._extract_chunk_and_ingest("job-1", 0, [("d1", "text one", "src")], "ws")
        assert (ent_count, rel_count) == (0, 0)
        engine.ingest_structured_data.assert_not_called()

    async def test_llm_failure_yields_none_result(self, monkeypatch, hss_db):
        engine = await self._patch_env(monkeypatch, hss_db)
        monkeypatch.setattr(
            hss, "_llm_extract_with_handler",
            AsyncMock(side_effect=RuntimeError("llm down")),
        )
        svc = hss_make_service(hss_db)
        ent_count, rel_count = await svc._extract_chunk_and_ingest("job-1", 0, [("d1", "text one", "src")], "ws")
        assert (ent_count, rel_count) == (0, 0)
        engine.ingest_structured_data.assert_not_called()

    async def test_partial_results_only_valid_ingested(self, monkeypatch, hss_db):
        engine = await self._patch_env(monkeypatch, hss_db)
        from core.graphrag_engine import Entity

        entities = [Entity(id="e1", name="A", entity_type="t", description="", properties={})]
        monkeypatch.setattr(
            hss, "_llm_extract_with_handler",
            AsyncMock(return_value=(entities, [])),
        )
        svc = hss_make_service(hss_db)
        ent_count, rel_count = await svc._extract_chunk_and_ingest("job-1", 0, [("d1", "text one", "src"), ("d2", "text two", "src")], "ws")
        assert ent_count == 2
        assert rel_count == 0

    async def test_inner_llm_retry_succeeds_on_second_attempt(self, monkeypatch, hss_db):
        engine = await self._patch_env(monkeypatch, hss_db)
        from core.graphrag_engine import Entity

        entities = [Entity(id="e1", name="A", entity_type="t", description="", properties={})]
        side = [RuntimeError("transient"), (entities, [])]
        async def _flaky(*a, **k):
            err = side.pop(0)
            if isinstance(err, Exception):
                raise err
            return err

        monkeypatch.setattr(hss, "_llm_extract_with_handler", _flaky)
        svc = hss_make_service(hss_db)
        ent_count, _ = await svc._extract_chunk_and_ingest("job-1", 0, [("d1", "text one", "src")], "ws")
        assert ent_count == 1
        engine.ingest_structured_data.assert_called_once()

    async def test_inner_llm_retry_exhausted(self, monkeypatch, hss_db):
        await self._patch_env(monkeypatch, hss_db)
        monkeypatch.setattr(
            hss, "_llm_extract_with_handler",
            AsyncMock(side_effect=RuntimeError("always down")),
        )
        svc = hss_make_service(hss_db)
        ent_count, rel_count = await svc._extract_chunk_and_ingest("job-1", 0, [("d1", "text one", "src")], "ws")
        assert (ent_count, rel_count) == (0, 0)

    async def test_task_result_exception_is_swallowed(self, monkeypatch, hss_db):
        await self._patch_env(monkeypatch, hss_db)
        from core.graphrag_engine import Entity

        entities = [Entity(id="e1", name="A", entity_type="t", description="", properties={})]
        done_results = [{"doc_id": "d1", "entities": entities, "relationships": []}]

        class FakeTask:
            def __init__(self, result):
                self._result = result

            def result(self):
                raise RuntimeError("result lost")

        real_wait = hss.asyncio.wait

        async def _fake_wait(tasks, timeout=None, return_when=None):
            return {FakeTask(None)}, set()

        monkeypatch.setattr(hss.asyncio, "wait", _fake_wait)
        monkeypatch.setattr(hss, "_llm_extract_with_handler", AsyncMock(return_value=(entities, [])))
        svc = hss_make_service(hss_db)
        ent_count, rel_count = await svc._extract_chunk_and_ingest("job-1", 0, [("d1", "text one", "src")], "ws")
        assert (ent_count, rel_count) == (0, 0)
        monkeypatch.setattr(hss.asyncio, "wait", real_wait)

    async def test_pending_tasks_are_cancelled(self, monkeypatch, hss_db):
        await self._patch_env(monkeypatch, hss_db)
        from core.graphrag_engine import Entity

        entities = [Entity(id="e1", name="A", entity_type="t", description="", properties={})]
        monkeypatch.setattr(hss, "_llm_extract_with_handler", AsyncMock(return_value=(entities, [])))
        real_wait = hss.asyncio.wait

        async def _fake_wait(tasks, timeout=None, return_when=None):
            await real_wait(tasks, timeout=600.0)
            return {tasks[0]}, {tasks[1]}

        monkeypatch.setattr(hss.asyncio, "wait", _fake_wait)
        svc = hss_make_service(hss_db)
        ent_count, _ = await svc._extract_chunk_and_ingest(
            "job-1", 0, [("d1", "text one", "src"), ("d2", "text two", "src")], "ws"
        )
        assert ent_count == 1
        monkeypatch.setattr(hss.asyncio, "wait", real_wait)


class TestProcessSyncJob:
    @pytest.fixture
    def patch_loop(self, hss_db, monkeypatch):
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=hss_db.bind)
        monkeypatch.setattr(hss, "SessionLocal", Session)

    async def test_success_flow(self, hss_db, patch_loop):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        records = [
            {"id": "r1", "name": "Record One", "text": "This is a long text for extraction here"},
            {"id": "r2", "name": "Record Two", "text": "This is another long text for extraction"},
        ]
        svc.ingestion_pipeline.sync_configs = {"salesforce": hss_config()}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=records)
        svc.ingestion_pipeline._record_to_text = Mock(side_effect=lambda r, i: r.get("text", ""))
        svc._extract_chunk_and_ingest = AsyncMock(return_value=(2, 1))
        svc._heartbeat_loop = AsyncMock()
        with patch("core.schema_discovery_service.SchemaDiscoveryService") as sdcls:
            sdcls.return_value.discover_schemas_from_entities = AsyncMock()
            await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "completed"
        assert job.records_processed == 2
        assert job.completed_chunks == 1
        assert job.entities_extracted == 2
        assert job.relationships_extracted == 1
        assert job.last_error is None
        sdcls.return_value.discover_schemas_from_entities.assert_awaited_once()

    async def test_job_not_found(self, hss_db, patch_loop):
        svc = hss_make_service(hss_db)
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job("missing-job")
        svc._heartbeat_loop.assert_not_called()

    async def test_terminal_state_skips(self, hss_db, patch_loop):
        for status in ["completed", "failed"]:
            job = hss_make_job(hss_db, status=status)
            svc = hss_make_service(hss_db)
            svc._heartbeat_loop = AsyncMock()
            await svc._process_sync_job(job.id)
            svc._heartbeat_loop.assert_not_called()

    async def test_paused_job_stops_and_not_completed(self, hss_db):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()

        orig_session_cls = hss_db.__class__

        class PauseSession(orig_session_cls):
            def refresh(self, instance):
                super().refresh(instance)
                if getattr(instance, "status", None) == "running":
                    instance.status = "paused"
                    self.commit()

        from sqlalchemy.orm import sessionmaker

        with patch("core.historical_sync_service.SessionLocal", lambda: PauseSession(bind=hss_db.bind)):
            await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "paused"

    async def test_cancelled_job_stops(self, hss_db):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()

        orig_session_cls = hss_db.__class__

        class CancelSession(orig_session_cls):
            def refresh(self, instance):
                super().refresh(instance)
                if getattr(instance, "status", None) == "running":
                    instance.status = "cancelled"
                    self.commit()

        with patch("core.historical_sync_service.SessionLocal", lambda: CancelSession(bind=hss_db.bind)):
            await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "cancelled"

    async def test_fetch_failure_marks_failed(self, hss_db, patch_loop):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(side_effect=RuntimeError("api down"))
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "failed"
        assert "Fetch failed for salesforce" in job.last_error
        assert job.error_count == 1

    async def test_empty_records_completes(self, hss_db, patch_loop):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "completed"
        assert job.records_processed == 0

    async def test_short_text_records_skipped(self, hss_db, patch_loop):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {"salesforce": hss_config()}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[{"id": "r1", "text": "short"}])
        svc.ingestion_pipeline._record_to_text = Mock(side_effect=lambda r, i: r.get("text", ""))
        svc._extract_chunk_and_ingest = AsyncMock(return_value=(0, 0))
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "completed"
        svc._extract_chunk_and_ingest.assert_not_called()

    async def test_default_config_fallback(self, hss_db, patch_loop):
        job = hss_make_job(hss_db, integration_id="hubspot")
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "completed"

    async def test_minimal_config_fallback(self, hss_db, patch_loop):
        job = hss_make_job(hss_db, integration_id="unknown-integration")
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "completed"

    async def test_schema_discovery_failure_does_not_break(self, hss_db, patch_loop):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        with patch("core.schema_discovery_service.SchemaDiscoveryService") as sdcls:
            sdcls.return_value.discover_schemas_from_entities = AsyncMock(
                side_effect=RuntimeError("discovery boom")
            )
            await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "completed"

    async def test_background_tasks_are_awaited(self, hss_db, patch_loop, monkeypatch):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        done_task = asyncio.create_task(asyncio.sleep(0))
        monkeypatch.setattr(hss, "_background_tasks", [done_task])
        await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "completed"

    async def test_mark_failed_commit_error_logged(self, hss_db, monkeypatch):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(side_effect=RuntimeError("api down"))
        svc._heartbeat_loop = AsyncMock()

        orig_session_cls = hss_db.__class__
        counter = {"n": 0}

        class FailCommitSession(orig_session_cls):
            def commit(self):
                super().commit()
                counter["n"] += 1
                if counter["n"] >= 2:
                    raise RuntimeError("commit died")

        monkeypatch.setattr(hss, "SessionLocal", lambda: FailCommitSession(bind=hss_db.bind))
        await svc._process_sync_job(job.id)
        hss_db.refresh(job)
        assert job.status == "failed"


class TestSyncLifecycle:
    async def test_get_progress_found(self, hss_db):
        job = hss_make_job(hss_db)
        job.records_processed = 10
        job.entities_extracted = 3
        job.relationships_extracted = 2
        job.completed_chunks = 1
        job.started_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        job.completed_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
        job.last_error = None
        job.status = "completed"
        hss_db.commit()
        svc = hss_make_service(hss_db)
        result = await svc.get_sync_progress(job.id)
        assert result["status"] == "completed"
        assert result["records_processed"] == 10
        assert result["started_at"].startswith("2024-01-01")
        assert result["completed_at"].startswith("2024-01-02")
        assert result["last_error"] is None

    async def test_get_progress_not_found(self, hss_db):
        svc = hss_make_service(hss_db)
        result = await svc.get_sync_progress("missing")
        assert result["error"] == "Job not found"

    async def test_cancel_sync_found(self, hss_db):
        job = hss_make_job(hss_db)
        svc = hss_make_service(hss_db)
        assert await svc.cancel_sync(job.id) is True
        hss_db.refresh(job)
        assert job.status == "cancelled"

    async def test_cancel_sync_not_found(self, hss_db):
        svc = hss_make_service(hss_db)
        assert await svc.cancel_sync("missing") is False

    async def test_pause_sync_running(self, hss_db):
        job = hss_make_job(hss_db, status="running")
        svc = hss_make_service(hss_db)
        assert await svc.pause_sync(job.id) is True
        hss_db.refresh(job)
        assert job.status == "paused"

    async def test_pause_sync_pending(self, hss_db):
        job = hss_make_job(hss_db, status="pending")
        svc = hss_make_service(hss_db)
        assert await svc.pause_sync(job.id) is True
        hss_db.refresh(job)
        assert job.status == "paused"

    async def test_pause_sync_wrong_status(self, hss_db):
        job = hss_make_job(hss_db, status="completed")
        svc = hss_make_service(hss_db)
        assert await svc.pause_sync(job.id) is False

    async def test_pause_sync_not_found(self, hss_db):
        svc = hss_make_service(hss_db)
        assert await svc.pause_sync("missing") is False

    async def test_resume_sync_success(self, hss_db):
        job = hss_make_job(hss_db, status="paused")
        svc = hss_make_service(hss_db)
        queue = Mock()
        queue.enqueue = AsyncMock()
        with patch("core.historical_sync_service.SyncJobQueue", return_value=queue):
            assert await svc.resume_sync(job.id) is True
        hss_db.refresh(job)
        assert job.status == "pending"
        queue.enqueue.assert_awaited_once()

    async def test_resume_sync_enqueue_failure(self, hss_db):
        job = hss_make_job(hss_db, status="failed")
        svc = hss_make_service(hss_db)
        queue = Mock()
        queue.enqueue = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("core.historical_sync_service.SyncJobQueue", return_value=queue):
            assert await svc.resume_sync(job.id) is False

    async def test_resume_sync_not_found(self, hss_db):
        svc = hss_make_service(hss_db)
        assert await svc.resume_sync("missing") is False
