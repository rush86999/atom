"""
Coverage-push tests for core.historical_sync_service (target >=80%).

Also fixes two REAL bugs found during test authoring:
1. start_historical_sync() rejects use_worker_queue=... kwarg sent by
   api/routes/webhooks/webhook_bridge.py -> TypeError, fallback sync never runs.
2. _llm_extract_with_handler() crashes with ValueError when the LLM returns a
   non-numeric confidence (e.g. "high") -> the whole chunk's extraction is lost.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.historical_sync_service import (
    HistoricalSyncService,
    _get_memory_threshold,
    _get_memory_usage,
    _llm_extract_with_handler,
    _log_job_event,
)
from core.models import HistoricalSyncJob

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.models_registration import Base

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.query(HistoricalSyncJob).delete()
    session.commit()
    session.close()


def make_job(db, **overrides):
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


def make_service(db, **kwargs):
    svc = HistoricalSyncService(tenant_id="tenant-1", db=db, **kwargs)
    svc._ingestion_pipeline = Mock()
    return svc


# ============================ module helpers ============================


class TestModuleHelpers:
    def test_get_memory_threshold(self):
        assert _get_memory_threshold(2048) == 1638
        assert _get_memory_threshold(100) == 80

    def test_get_memory_usage_with_psutil(self):
        with patch("psutil.Process") as p:
            p.return_value.memory_info.return_value.rss = 200 * 1024 * 1024
            assert _get_memory_usage() == 200

    def test_get_memory_usage_without_psutil(self):
        with patch.dict("sys.modules", {"psutil": None}):
            with patch("builtins.__import__", side_effect=ImportError("no psutil")):
                assert _get_memory_usage() == 0

    async def test_log_job_event_appends_and_caps(self, db_session):
        job = make_job(db_session)
        for i in range(12):
            _log_job_event(db_session, job.id, "tenant-1", f"event-{i}")
        db_session.refresh(job)
        assert len(job.checkpoint_data["events"]) == 10
        assert job.checkpoint_data["events"][-1].endswith("event-11")
        assert not job.checkpoint_data["events"][0].endswith("event-0")

    async def test_log_job_event_missing_job(self, db_session):
        _log_job_event(db_session, "nope", "tenant-1", "event")  # no raise

    async def test_log_job_event_exception_swallowed(self, engine):
        Session = sessionmaker(bind=engine)
        db = Session()
        job = make_job(db)
        db.commit = Mock(side_effect=RuntimeError("boom"))
        _log_job_event(db, job.id, "tenant-1", "event")  # no raise
        db.close()


# ============================ _llm_extract_with_handler ============================


class TestLLMExtractWithHandler:
    async def _run(self, llm, **kw):
        defaults = dict(
            text="Some text about Acme Corp",
            doc_id="doc-1",
            source="salesforce",
            workspace_id="ws-1",
            tenant_id="tenant-1",
        )
        defaults.update(kw)
        return await _llm_extract_with_handler(llm, **defaults)

    async def test_success_plain_json(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=(
            '{"entities": [{"name": "Acme", "type": "org", "description": "d", "confidence": 0.9}], '
            '"relationships": [{"from": "Acme", "to": "Bob", "type": "works_at", "description": "r"}]}'
        ))
        entities, rels = await self._run(llm)
        assert len(entities) == 1
        assert entities[0].name == "Acme"
        assert entities[0].properties["source"] == "salesforce"
        assert entities[0].properties["doc_id"] == "doc-1"
        assert entities[0].properties["confidence"] == 0.9
        assert len(rels) == 1
        assert rels[0].from_entity == "Acme"
        assert rels[0].rel_type == "works_at"

    async def test_success_fenced_json(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value='```json\n{"entities": [{"name": "X", "type": "t"}], "relationships": []}\n```')
        entities, rels = await self._run(llm)
        assert entities[0].name == "X"
        assert rels == []

    async def test_success_fenced_plain(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value='```\n{"entities": [{"name": "Y", "type": "t"}]}\n```')
        entities, _ = await self._run(llm)
        assert entities[0].name == "Y"

    async def test_canonical_type_and_extra_metadata(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=(
            '{"entities": [{"name": "Acme", "type": "org", "canonical_type": "organization", "confidence": 1.0}]}'
        ))
        entities, _ = await self._run(llm, extra_metadata={"folder": "f1"})
        assert entities[0].properties["canonical_type"] == "organization"
        assert entities[0].properties["folder"] == "f1"

    async def test_empty_response(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value="   ")
        entities, rels = await self._run(llm)
        assert entities == []
        assert rels == []

    async def test_json_decode_retry_then_success(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(
            side_effect=["not json at all", '{"entities": [{"name": "Z", "type": "t"}]}']
        )
        entities, _ = await self._run(llm)
        assert entities[0].name == "Z"
        assert llm.generate.await_count == 2

    async def test_all_models_raise(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("api down"))
        entities, rels = await self._run(llm)
        assert entities == [] and rels == []

    async def test_non_numeric_confidence_does_not_kill_chunk(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=(
            '{"entities": [{"name": "Acme", "type": "org", "confidence": "high"}]}'
        ))
        entities, _ = await self._run(llm)
        assert len(entities) == 1
        assert entities[0].name == "Acme"
        assert entities[0].properties["confidence"] == 0.0


# ============================ service properties ============================


class TestServiceProperties:
    async def test_db_property_creates_internal_session(self, engine):
        Session = sessionmaker(bind=engine)
        with patch("core.historical_sync_service.SessionLocal", Session):
            svc = HistoricalSyncService(tenant_id="t-1")
            assert svc.db is not None
            assert svc._internal_session is True

    async def test_workspace_id_falls_back_to_tenant(self, db_session):
        svc = make_service(db_session)
        assert svc.workspace_id == "tenant-1"

    async def test_ingestion_pipeline_lazy(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.IngestionPipelineService") as cls:
            svc._ingestion_pipeline = None
            pipe = svc.ingestion_pipeline
            assert pipe is cls.return_value
            assert svc.ingestion_pipeline is pipe

    async def test_integration_registry_lazy(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.IntegrationRegistry") as cls:
            reg = svc.integration_registry
            assert reg is cls.return_value
            assert svc.integration_registry is reg


# ============================ start_historical_sync ============================


class TestStartHistoricalSync:
    async def test_default_end_date_and_enqueue(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SyncJobQueue") as qcls:
            qcls.return_value.enqueue = AsyncMock()
            job_id = await svc.start_historical_sync(
                "salesforce", "conn-1", datetime(2024, 1, 1, tzinfo=timezone.utc)
            )
        job = db_session.query(HistoricalSyncJob).filter_by(id=job_id).first()
        assert job is not None
        assert job.end_date == datetime(2024, 3, 31)
        qcls.return_value.enqueue.assert_awaited_once()

    async def test_enqueue_failure_keeps_job_pending(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SyncJobQueue") as qcls:
            qcls.return_value.enqueue = AsyncMock(side_effect=RuntimeError("redis down"))
            job_id = await svc.start_historical_sync(
                "salesforce", "conn-1",
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 2, 1, tzinfo=timezone.utc),
            )
        job = db_session.query(HistoricalSyncJob).filter_by(id=job_id).first()
        assert job.status == "pending"

    async def test_accepts_use_worker_queue_kwarg(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SyncJobQueue") as qcls:
            qcls.return_value.enqueue = AsyncMock()
            job_id = await svc.start_historical_sync(
                "salesforce", "conn-1",
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                use_worker_queue=True,
            )
        assert job_id
        qcls.return_value.enqueue.assert_awaited_once()


# ============================ heartbeat / memory ============================


class TestHeartbeatAndMemory:
    async def _start_and_cancel(self, svc, hb_db):
        with patch("core.historical_sync_service.SessionLocal", return_value=hb_db):
            task = asyncio.create_task(svc._heartbeat_loop("job-1"))
            await asyncio.sleep(0.15)
            task.cancel()
            await task  # coroutine swallows CancelledError and returns

    async def test_heartbeat_loop_cancel_stops_thread(self, db_session):
        svc = make_service(db_session)
        hb_db = Mock()
        hb_db.query.return_value.filter.return_value.update.return_value = None
        await self._start_and_cancel(svc, hb_db)
        assert svc._hb_stop.is_set()

    async def test_heartbeat_thread_db_error_is_swallowed(self, db_session):
        svc = make_service(db_session)
        hb_db = Mock()
        hb_db.commit.side_effect = RuntimeError("db gone")
        await self._start_and_cancel(svc, hb_db)
        assert svc._hb_stop.is_set()

    async def test_memory_check_normal(self):
        svc = make_service(Mock())
        with patch("core.historical_sync_service._get_memory_usage", return_value=100), patch(
            "core.historical_sync_service._get_memory_threshold", return_value=1638
        ):
            assert await svc._check_memory_and_gc("job-1") is True

    async def test_memory_check_high_triggers_gc(self):
        svc = make_service(Mock())
        with patch("core.historical_sync_service._get_memory_usage", return_value=5000), patch(
            "core.historical_sync_service._get_memory_threshold", return_value=1638
        ), patch("core.historical_sync_service.gc") as gc_mock:
            assert await svc._check_memory_and_gc("job-1") is False
            gc_mock.collect.assert_called_once()

    async def test_memory_check_exception_is_non_fatal(self):
        svc = make_service(Mock())
        with patch("core.historical_sync_service._get_memory_usage", side_effect=RuntimeError("boom")):
            assert await svc._check_memory_and_gc("job-1") is True


# ============================ _extract_chunk_and_ingest ============================


class TestExtractChunkAndIngest:
    async def test_extracts_and_ingests(self, db_session):
        svc = make_service(db_session)
        shared_db = Mock()
        with patch("core.historical_sync_service.SessionLocal", return_value=shared_db), patch(
            "core.graphrag_engine.GraphRAGEngine"
        ) as gcls, patch("core.llm_service.LLMService") as lcls:
            llm = AsyncMock()
            llm.generate = AsyncMock(return_value=(
                '{"entities": [{"name": "Acme", "type": "org"}], '
                '"relationships": [{"from": "A", "to": "B", "type": "r"}]}'
            ))
            lcls.return_value = llm
            ents, rels = await svc._extract_chunk_and_ingest(
                "job-1", 0,
                [("d1", "long text here for record", "salesforce"),
                 ("d2", "another long text record", "salesforce")],
                "ws-1", "salesforce",
            )
        assert ents == 2
        assert rels == 2
        assert gcls.return_value.ingestion_pipeline_batch.call_count == 2
        gcls.return_value.close.assert_called_once()
        shared_db.close.assert_called_once()

    async def test_empty_extraction_skips_ingestion(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SessionLocal", return_value=Mock()), patch(
            "core.graphrag_engine.GraphRAGEngine"
        ) as gcls, patch("core.llm_service.LLMService") as lcls:
            llm = AsyncMock()
            llm.generate = AsyncMock(return_value='{"entities": [], "relationships": []}')
            lcls.return_value = llm
            ents, rels = await svc._extract_chunk_and_ingest(
                "job-1", 0, [("d1", "long text record", "salesforce")], "ws-1"
            )
        assert (ents, rels) == (0, 0)
        gcls.return_value.ingestion_pipeline_batch.assert_not_called()

    async def test_llm_failure_yields_none_result(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SessionLocal", return_value=Mock()), patch(
            "core.graphrag_engine.GraphRAGEngine"
        ) as gcls, patch("core.llm_service.LLMService") as lcls:
            llm = AsyncMock()
            llm.generate = AsyncMock(side_effect=RuntimeError("down"))
            lcls.return_value = llm
            ents, rels = await svc._extract_chunk_and_ingest(
                "job-1", 0, [("d1", "long text record", "salesforce")], "ws-1"
            )
        assert (ents, rels) == (0, 0)
        gcls.return_value.ingestion_pipeline_batch.assert_not_called()

    async def test_partial_results_only_valid_ingested(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SessionLocal", return_value=Mock()), patch(
            "core.graphrag_engine.GraphRAGEngine"
        ) as gcls, patch("core.llm_service.LLMService") as lcls:
            llm = AsyncMock()
            llm.generate = AsyncMock(side_effect=[
                '{"entities": [{"name": "Only", "type": "t"}], "relationships": []}',
                RuntimeError("down"),
            ])
            lcls.return_value = llm
            ents, rels = await svc._extract_chunk_and_ingest(
                "job-1", 0,
                [("d1", "long text record", "salesforce"),
                 ("d2", "another long text record", "salesforce")],
                "ws-1",
            )
        assert ents == 1 and rels == 0

    async def test_inner_llm_retry_succeeds_on_second_attempt(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SessionLocal", return_value=Mock()), patch(
            "core.graphrag_engine.GraphRAGEngine"
        ) as gcls, patch("core.llm_service.LLMService") as lcls:
            lcls.return_value = Mock()
            calls = {"n": 0}

            async def flaky(llm_service, txt, doc_id, src, workspace_id, tenant_id):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("transient")
                return [Mock(name="E", properties={})], []

            with patch("core.historical_sync_service._llm_extract_with_handler", side_effect=flaky):
                ents, rels = await svc._extract_chunk_and_ingest(
                    "job-1", 0, [("d1", "long text record", "salesforce")], "ws-1"
                )
        assert ents == 1 and rels == 0
        assert calls["n"] == 2
        gcls.return_value.ingestion_pipeline_batch.assert_called_once()

    async def test_inner_llm_retry_exhausted(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SessionLocal", return_value=Mock()), patch(
            "core.graphrag_engine.GraphRAGEngine"
        ) as gcls, patch("core.llm_service.LLMService") as lcls:
            lcls.return_value = Mock()

            async def always_fails(llm_service, txt, doc_id, src, workspace_id, tenant_id):
                raise RuntimeError("always")

            with patch(
                "core.historical_sync_service._llm_extract_with_handler",
                side_effect=always_fails,
            ):
                ents, rels = await svc._extract_chunk_and_ingest(
                    "job-1", 0, [("d1", "long text record", "salesforce")], "ws-1"
                )
        assert (ents, rels) == (0, 0)
        gcls.return_value.ingestion_pipeline_batch.assert_not_called()

    async def test_task_result_exception_is_swallowed(self, db_session):
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SessionLocal", return_value=Mock()), patch(
            "core.graphrag_engine.GraphRAGEngine"
        ) as gcls, patch("core.llm_service.LLMService") as lcls:
            lcls.return_value = Mock()

            async def raise_result(llm_service, txt, doc_id, src, workspace_id, tenant_id):
                raise RuntimeError("boom")

            with patch(
                "core.historical_sync_service._llm_extract_with_handler",
                side_effect=raise_result,
            ):
                ents, rels = await svc._extract_chunk_and_ingest(
                    "job-1", 0, [("d1", "long text record", "salesforce")], "ws-1"
                )
        assert (ents, rels) == (0, 0)
        gcls.return_value.ingestion_pipeline_batch.assert_not_called()


# ============================ _process_sync_job ============================


class TestProcessSyncJob:
    @pytest.fixture
    def patch_loop(self, db_session):
        Session = sessionmaker(bind=db_session.bind)
        with patch("core.historical_sync_service.SessionLocal", Session):
            yield

    async def test_success_flow(self, db_session, patch_loop):
        job = make_job(db_session)
        svc = make_service(db_session)
        records = [
            {"id": "r1", "name": "Record One", "text": "This is a long text for extraction here"},
            {"id": "r2", "name": "Record Two", "text": "This is another long text for extraction"},
        ]
        svc.ingestion_pipeline.sync_configs = {"salesforce": Mock()}
        svc.ingestion_pipeline.sync_configs["salesforce"].integration_id = "salesforce"
        svc.ingestion_pipeline.sync_configs["salesforce"].entity_types = ["contacts"]
        svc.ingestion_pipeline.sync_configs["salesforce"].sync_last_n_days = 30
        svc.ingestion_pipeline.sync_configs["salesforce"].max_records_per_sync = 100
        svc.ingestion_pipeline.sync_configs["salesforce"].include_metadata = True
        svc.ingestion_pipeline.sync_configs["salesforce"].sync_mode = "incremental"
        svc.ingestion_pipeline.sync_configs["salesforce"].discovery_frequency_hours = 168
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=records)
        svc.ingestion_pipeline._record_to_text = Mock(side_effect=lambda r, i: r.get("text", ""))
        svc._extract_chunk_and_ingest = AsyncMock(return_value=(2, 1))
        svc._heartbeat_loop = AsyncMock()
        with patch("core.schema_discovery_service.SchemaDiscoveryService") as sdcls:
            sdcls.return_value.discover_schemas_from_entities = AsyncMock()
            await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "completed"
        assert job.records_processed == 2
        assert job.completed_chunks == 1
        assert job.entities_extracted == 2
        assert job.relationships_extracted == 1
        assert job.last_error is None
        sdcls.return_value.discover_schemas_from_entities.assert_awaited_once()

    async def test_job_not_found(self, db_session, patch_loop):
        svc = make_service(db_session)
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job("missing-job")
        svc._heartbeat_loop.assert_not_called()

    async def test_terminal_state_skips(self, db_session, patch_loop):
        job = make_job(db_session, status="completed")
        svc = make_service(db_session)
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        svc._heartbeat_loop.assert_not_called()

    async def test_fetch_failure_marks_failed(self, db_session, patch_loop):
        job = make_job(db_session)
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(side_effect=RuntimeError("api down"))
        svc._heartbeat_loop = AsyncMock()
        with patch("core.schema_discovery_service.SchemaDiscoveryService") as sdcls:
            sdcls.return_value.discover_schemas_from_entities = AsyncMock()
            await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "failed"
        assert "Fetch failed for salesforce" in job.last_error
        assert job.error_count == 1

    async def test_empty_records_completes(self, db_session, patch_loop):
        job = make_job(db_session)
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "completed"
        assert job.records_processed == 0

    async def test_default_config_fallback(self, db_session, patch_loop):
        job = make_job(db_session, integration_id="hubspot")
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "completed"

    async def test_minimal_config_fallback(self, db_session, patch_loop):
        job = make_job(db_session, integration_id="unknown-integration")
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "completed"

    async def test_short_texts_skip_extraction(self, db_session, patch_loop):
        job = make_job(db_session)
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(
            return_value=[{"id": "r1", "text": "tiny"}]
        )
        svc.ingestion_pipeline._record_to_text = Mock(return_value="tiny")
        svc._extract_chunk_and_ingest = AsyncMock()
        svc._heartbeat_loop = AsyncMock()
        await svc._process_sync_job(job.id)
        svc._extract_chunk_and_ingest.assert_not_called()
        db_session.refresh(job)
        assert job.status == "completed"
        assert job.records_processed == 1

    async def test_paused_job_stops_and_not_completed(self, db_session):
        job = make_job(db_session)
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()

        orig_session_cls = db_session.__class__

        class PauseSession(orig_session_cls):
            def refresh(self, instance):
                super().refresh(instance)
                if getattr(instance, "status", None) == "running":
                    instance.status = "paused"
                    self.commit()

        Session = sessionmaker(bind=db_session.bind)
        with patch("core.historical_sync_service.SessionLocal", lambda: PauseSession(bind=db_session.bind)):
            await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "paused"

    async def test_schema_discovery_failure_does_not_break(self, db_session, patch_loop):
        job = make_job(db_session)
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        with patch("core.schema_discovery_service.SchemaDiscoveryService") as sdcls:
            sdcls.return_value.discover_schemas_from_entities = AsyncMock(side_effect=RuntimeError("boom"))
            await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "completed"

    async def test_background_tasks_awaited(self, db_session, patch_loop):
        job = make_job(db_session)
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])
        svc._heartbeat_loop = AsyncMock()
        done = []

        async def fake_task():
            done.append(True)

        with patch("core.historical_sync_service._background_tasks", [fake_task()]):
            await svc._process_sync_job(job.id)
        assert done == [True]
        db_session.refresh(job)
        assert job.status == "completed"

    async def test_heartbeat_task_cancelled_cleanly(self, db_session, patch_loop):
        job = make_job(db_session)
        svc = make_service(db_session)
        svc.ingestion_pipeline.sync_configs = {}
        svc.ingestion_pipeline._fetch_integration_data = AsyncMock(return_value=[])

        async def long_heartbeat(job_id):
            await asyncio.sleep(3600)

        svc._heartbeat_loop = long_heartbeat
        await svc._process_sync_job(job.id)
        db_session.refresh(job)
        assert job.status == "completed"


# ============================ progress / cancel / pause / resume ============================


class TestJobControls:
    async def test_get_sync_progress_found(self, db_session):
        job = make_job(db_session, status="running", records_processed=5, completed_chunks=1,
                       entities_extracted=3, relationships_extracted=2,
                       started_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        svc = make_service(db_session)
        progress = await svc.get_sync_progress(job.id)
        assert progress["status"] == "running"
        assert progress["records_processed"] == 5
        assert progress["completed_chunks"] == 1
        assert progress["started_at"] is not None
        assert progress["last_error"] is None

    async def test_get_sync_progress_missing(self, db_session):
        svc = make_service(db_session)
        progress = await svc.get_sync_progress("nope")
        assert progress["error"] == "Job not found"

    async def test_cancel_sync(self, db_session):
        job = make_job(db_session)
        svc = make_service(db_session)
        assert await svc.cancel_sync(job.id) is True
        db_session.refresh(job)
        assert job.status == "cancelled"
        assert job.completed_at is not None

    async def test_cancel_sync_missing(self, db_session):
        svc = make_service(db_session)
        assert await svc.cancel_sync("nope") is False

    async def test_pause_sync(self, db_session):
        job = make_job(db_session, status="running")
        svc = make_service(db_session)
        assert await svc.pause_sync(job.id) is True
        db_session.refresh(job)
        assert job.status == "paused"

    async def test_pause_sync_wrong_status(self, db_session):
        job = make_job(db_session, status="completed")
        svc = make_service(db_session)
        assert await svc.pause_sync(job.id) is False

    async def test_pause_sync_missing(self, db_session):
        svc = make_service(db_session)
        assert await svc.pause_sync("nope") is False

    async def test_resume_sync_enqueues(self, db_session):
        job = make_job(db_session, status="failed")
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SyncJobQueue") as qcls:
            qcls.return_value.enqueue = AsyncMock()
            assert await svc.resume_sync(job.id) is True
        db_session.refresh(job)
        assert job.status == "pending"
        qcls.return_value.enqueue.assert_awaited_once()

    async def test_resume_sync_enqueue_failure(self, db_session):
        job = make_job(db_session, status="paused")
        svc = make_service(db_session)
        with patch("core.historical_sync_service.SyncJobQueue") as qcls:
            qcls.return_value.enqueue = AsyncMock(side_effect=RuntimeError("redis down"))
            assert await svc.resume_sync(job.id) is False
        db_session.refresh(job)
        assert job.status == "pending"

    async def test_resume_sync_missing(self, db_session):
        svc = make_service(db_session)
        assert await svc.resume_sync("nope") is False
