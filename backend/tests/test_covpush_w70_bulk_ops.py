# -*- coding: utf-8 -*-
"""Coverage wave 70 — core/bulk_operations_processor (fully mocked deps, no
network, no real DB). Complements tests/test_bulk_operations_processor.py
(70% baseline) by covering the untested `_process_job` lifecycle and the
integration-specific error branches.

- BulkJob: zero-total progress percentage + setter no-op.
- IntegrationBulkProcessor._process_queue: concurrency-limit sleep loop and
  normal dequeue; _process_job success (multi-batch, estimated completion),
  partial success, all-failed, stop_on_error abort, mid-loop cancel, callback
  failure, unknown-integration, processor exception; _prepare_items
  (mapping transform ±exception, schema validation ±invalid/exception);
  _save_job_results exception path (non-dataclass operation).
- Integration processors: asana create/update/delete/complete success + every
  failure branch (no data, missing ids, unsupported op, per-item exception),
  jira create/update/unsupported/exception, salesforce create/update/
  unsupported/exception, notion/airtable/hubspot/monday success+exception.
- get_performance_stats (empty + populated), get_bulk_processor singleton.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.bulk_operations_processor import (
    BulkJob,
    IntegrationBulkProcessor,
    OperationStatus,
    get_bulk_processor,
)
from core.integration_data_mapper import BulkOperation
import core.bulk_operations_processor as mod


def _op(*, operation_type="create", integration_id="notion", items=None,
        batch_size=100, stop_on_error=False, progress_callback=None):
    return BulkOperation(
        operation_type=operation_type,
        integration_id=integration_id,
        items=items if items is not None else [{"id": 1}, {"id": 2}],
        batch_size=batch_size,
        parallel_processing=True,
        stop_on_error=stop_on_error,
        progress_callback=progress_callback,
    )


def _job(operation, *, status=OperationStatus.PENDING, job_id="bulk_test_1"):
    return BulkJob(
        job_id=job_id,
        operation=operation,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture()
def processor(tmp_path):
    proc = IntegrationBulkProcessor()
    proc._job_results_dir = tmp_path
    return proc


async def _fake_success(items, operation):
    return [{"success": True, "item": item} for item in items]


# ============================================================================
# BulkJob
# ============================================================================

class TestBulkJob:
    def test_progress_zero_when_no_items(self):
        job = _job(_op(items=[]))
        assert job.total_items == 0
        assert job.progress_percentage == 0.0

    def test_progress_setter_is_noop(self):
        job = _job(_op(items=[{"a": 1}]))
        job.processed_items = 1
        job.progress_percentage = 75.0
        assert job.progress_percentage == 100.0  # calculated, not stored


# ============================================================================
# _process_queue
# ============================================================================

class TestProcessQueue:
    async def test_concurrency_limit_waits(self, processor):
        queued = _job(_op(), job_id="bulk_queued_1")
        processor.active_jobs["bulk_queued_1"] = queued
        processor.job_queue = ["bulk_queued_1"]
        for i in range(5):
            running = _job(_op(), status=OperationStatus.RUNNING,
                           job_id=f"bulk_running_{i}")
            processor.active_jobs[f"bulk_running_{i}"] = running

        def _drain(*a, **k):
            processor.job_queue.clear()
            return None

        with patch("asyncio.sleep", new=AsyncMock(side_effect=_drain)):
            with patch("asyncio.create_task") as create_task:
                await processor._process_queue()
        create_task.assert_not_called()

    async def test_dequeues_and_starts_job(self, processor):
        queued = _job(_op(), job_id="bulk_q_2")
        processor.active_jobs["bulk_q_2"] = queued
        processor.job_queue = ["bulk_q_2"]
        with patch("asyncio.create_task") as create_task:
            await processor._process_queue()
        assert processor.job_queue == []
        create_task.assert_called_once()
        assert create_task.call_args.args[0] is not None


# ============================================================================
# _process_job lifecycle
# ============================================================================

class TestProcessJob:
    async def test_success_multi_batch_with_estimate(self, processor):
        op = _op(items=[{"id": 1}, {"id": 2}], batch_size=1)
        processor.integration_processors["notion"] = _fake_success
        job = _job(op)
        await processor._process_job(job)
        assert job.status == OperationStatus.COMPLETED
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.processed_items == 2
        assert job.successful_items == 2
        assert job.estimated_completion is not None
        assert len(job.results) == 2
        assert job.results[0] == {"success": True, "item": {"id": 1}}
        results_file = processor._job_results_dir / f"{job.job_id}_results.json"
        assert results_file.exists()
        payload = json.loads(results_file.read_text())
        assert payload["status"] == "completed"
        assert payload["successful_items"] == 2
        assert payload["progress_percentage"] == 100.0

    async def test_partial_success(self, processor):
        async def fake(items, operation):
            return [{"success": True, "item": items[0]},
                    {"success": False, "error": "nope"}]
        processor.integration_processors["notion"] = fake
        job = _job(_op(items=[{"id": 1}, {"id": 2}]))
        await processor._process_job(job)
        assert job.status == OperationStatus.PARTIAL_SUCCESS
        assert job.successful_items == 1
        assert job.failed_items == 1
        assert job.errors[0]["error"] == "nope"
        assert job.errors[0]["item_index"] == 1

    async def test_all_failed(self, processor):
        async def fake(items, operation):
            return [{"success": False, "error": "bad"}]
        processor.integration_processors["notion"] = fake
        job = _job(_op(items=[{"id": 1}]))
        await processor._process_job(job)
        assert job.status == OperationStatus.FAILED
        assert job.failed_items == 1

    async def test_stop_on_error_aborts(self, processor):
        async def fake(items, operation):
            return [{"success": False, "error": "fatal"}]
        processor.integration_processors["notion"] = fake
        job = _job(_op(items=[{"id": 1}, {"id": 2}], stop_on_error=True))
        await processor._process_job(job)
        assert job.status == OperationStatus.FAILED
        assert job.processed_items == 1

    async def test_cancel_during_processing(self, processor):
        async def fake(items, operation):
            job.status = OperationStatus.CANCELLED
            return [{"success": True, "item": items[0]}]
        processor.integration_processors["notion"] = fake
        job = _job(_op(items=[{"id": 1}, {"id": 2}], batch_size=1))
        await processor._process_job(job)
        assert job.status == OperationStatus.CANCELLED
        assert job.completed_at is not None

    async def test_progress_callback_success_and_failure(self, processor):
        calls = []

        async def callback(job):
            calls.append(job)

        async def failing_callback(job):
            raise RuntimeError("callback blew up")

        processor.integration_processors["notion"] = _fake_success
        job = _job(_op(items=[{"id": 1}], progress_callback=callback))
        await processor._process_job(job)
        assert len(calls) == 1
        job2 = _job(_op(items=[{"id": 1}], progress_callback=failing_callback),
                    job_id="bulk_cb_fail")
        with patch.object(mod.logger, "error") as err:
            await processor._process_job(job2)
        err.assert_called_once()
        assert "Progress callback failed" in str(err.call_args)

    async def test_unknown_integration_fails_job(self, processor):
        job = _job(_op(integration_id="does-not-exist"))
        await processor._process_job(job)
        assert job.status == OperationStatus.FAILED
        assert job.errors[0]["type"] == "job_error"
        assert "No processor found" in job.errors[0]["error"]

    async def test_processor_exception_fails_job(self, processor):
        processor.integration_processors["notion"] = AsyncMock(
            side_effect=RuntimeError("integration down"))
        job = _job(_op(items=[{"id": 1}]))
        await processor._process_job(job)
        assert job.status == OperationStatus.FAILED
        assert "integration down" in job.errors[0]["error"]
        results_file = processor._job_results_dir / f"{job.job_id}_results.json"
        assert results_file.exists()

    async def test_save_results_failure_logged(self, processor):
        # asdict() fails on a non-dataclass operation → save path except
        job = _job(_op(items=[{"id": 1}]))
        job.operation = SimpleNamespace(items=[{"id": 1}])
        job.status = OperationStatus.COMPLETED
        with patch.object(mod.logger, "error") as err:
            await processor._save_job_results(job)
        err.assert_called_once()
        assert "Failed to save job results" in str(err.call_args)


# ============================================================================
# _prepare_items
# ============================================================================

class TestPrepareItems:
    async def test_mapping_transform_applied(self, processor):
        mapper = MagicMock()
        mapper.transform_data.return_value = [{"mapped": True}]
        processor.data_mapper = mapper
        op = _op(items=[{"id": 1}])
        op.mapping_id = "map-1"
        items = await processor._prepare_items(op)
        assert items == [{"mapped": True}]
        mapper.transform_data.assert_called_once_with([{"id": 1}], "map-1")

    async def test_mapping_transform_exception_swallowed(self, processor):
        mapper = MagicMock()
        mapper.transform_data.side_effect = RuntimeError("transform failed")
        processor.data_mapper = mapper
        op = _op(items=[{"id": 1}])
        op.mapping_id = "map-1"
        with patch.object(mod.logger, "error") as err:
            items = await processor._prepare_items(op)
        assert items == [{"id": 1}]
        err.assert_called_once()

    async def test_validation_invalid_warns(self, processor):
        mapper = MagicMock()
        mapper.validate_data.return_value = {"valid": False, "warnings": ["bad field"]}
        processor.data_mapper = mapper
        op = _op(items=[{"id": 1}])
        op.schema_id = "schema-1"
        with patch.object(mod.logger, "warning") as warn:
            items = await processor._prepare_items(op)
        assert items == [{"id": 1}]
        warn.assert_called_once()

    async def test_validation_exception_swallowed(self, processor):
        mapper = MagicMock()
        mapper.validate_data.side_effect = RuntimeError("validation failed")
        processor.data_mapper = mapper
        op = _op(items=[{"id": 1}])
        op.schema_id = "schema-1"
        with patch.object(mod.logger, "error") as err:
            items = await processor._prepare_items(op)
        assert items == [{"id": 1}]
        err.assert_called_once()

    async def test_no_mapping_no_schema(self, processor):
        items = await processor._prepare_items(_op(items=[{"id": 1}]))
        assert items == [{"id": 1}]


# ============================================================================
# Asana processor
# ============================================================================

class TestAsana:
    def _patch_asana(self, *, create=None, update=None, delete=None, complete=None):
        service = MagicMock()
        service.create_task = AsyncMock(return_value=create if create is not None
                                        else {"data": {"gid": "g-1"}})
        service.update_task = AsyncMock(return_value=update if update is not None
                                        else {"data": {"gid": "g-1"}})
        service.delete_task = AsyncMock(return_value=delete if delete is not None
                                        else {"data": {"gid": "g-1"}})
        service.complete_task = AsyncMock(return_value=complete if complete is not None
                                          else {"data": {"gid": "g-1"}})
        return patch("integrations.asana_service.AsanaService", return_value=service)

    async def test_create_success(self, processor):
        with self._patch_asana():
            op = _op(operation_type="create", integration_id="asana",
                     items=[{"name": "T", "notes": "n", "projects": ["p"],
                             "assignee": None, "due_on": "2026-09-01"}])
            op.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["id"] == "g-1"
        assert results[0]["result"]["created"] is True

    async def test_create_no_data(self, processor):
        with self._patch_asana(create={"errors": "API refused"}):
            op = _op(operation_type="create", integration_id="asana",
                     items=[{"name": "T"}])
            op.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert results[0]["error"] == "API refused"

    async def test_update_success_and_missing_id_and_no_data(self, processor):
        with self._patch_asana(update={"data": {"gid": "g-1"}}):
            op = _op(operation_type="update", integration_id="asana",
                     items=[{"task_id": "t1", "updates": {"name": "x"}},
                            {"updates": {"name": "y"}}])
            op.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["updated"] is True
        assert results[1]["success"] is False
        assert "Missing task_id" in results[1]["error"]

        with self._patch_asana(update={"errors": "conflict"}):
            op2 = _op(operation_type="update", integration_id="asana",
                      items=[{"task_id": "t2", "updates": {}}])
            op2.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op2.items, op2)
        assert results[0]["success"] is False
        assert results[0]["error"] == "conflict"

    async def test_delete_success_and_missing_id_and_no_data(self, processor):
        with self._patch_asana(delete={"data": {"gid": "g-1"}}):
            op = _op(operation_type="delete", integration_id="asana",
                     items=[{"task_gid": "t1"}, {"name": "no-id"}])
            op.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["deleted"] is True
        assert results[1]["success"] is False
        assert "Missing task_id" in results[1]["error"]

        with self._patch_asana(delete={"errors": "gone"}):
            op2 = _op(operation_type="delete", integration_id="asana",
                      items=[{"id": "t2"}])
            op2.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op2.items, op2)
        assert results[0]["success"] is False
        assert results[0]["error"] == "gone"

    async def test_complete_success_and_missing_id_and_no_data(self, processor):
        with self._patch_asana(complete={"data": {"gid": "g-1"}}):
            op = _op(operation_type="complete", integration_id="asana",
                     items=[{"task_id": "t1"}, {"name": "no-id"}])
            op.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["completed"] is True
        assert results[1]["success"] is False
        assert "Missing task_id" in results[1]["error"]

        with self._patch_asana(complete={"errors": "nope"}):
            op2 = _op(operation_type="complete", integration_id="asana",
                      items=[{"id": "t2"}])
            op2.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op2.items, op2)
        assert results[0]["success"] is False

    async def test_unsupported_operation(self, processor):
        with self._patch_asana():
            op = _op(operation_type="upsert", integration_id="asana",
                     items=[{"name": "T"}])
            op.metadata = {"access_token": "tok"}
            results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "Unsupported operation" in results[0]["error"]

    async def test_per_item_exception(self, processor):
        service = MagicMock()
        service.create_task = AsyncMock(side_effect=RuntimeError("rate limited"))
        with patch("integrations.asana_service.AsanaService", return_value=service):
            op = _op(operation_type="create", integration_id="asana",
                     items=[{"name": "T"}])
            op.metadata = {"access_token": "tok"}
            with patch.object(mod.logger, "error"):
                results = await processor._process_asana_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "rate limited" in results[0]["error"]


# ============================================================================
# Jira / Salesforce processors
# ============================================================================

class TestJira:
    async def test_create_and_update(self, processor):
        op = _op(operation_type="create", integration_id="jira", items=[{"title": "x"}])
        with patch("asyncio.sleep", new=AsyncMock()):
            results = await processor._process_jira_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["key"].startswith("ATOM-")

        op2 = _op(operation_type="update", integration_id="jira", items=[{"id": 1}])
        with patch("asyncio.sleep", new=AsyncMock()):
            results = await processor._process_jira_bulk(op2.items, op2)
        assert results[0]["result"]["updated"] is True

    async def test_unsupported_operation(self, processor):
        op = _op(operation_type="delete", integration_id="jira", items=[{"id": 1}])
        with patch("asyncio.sleep", new=AsyncMock()):
            results = await processor._process_jira_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "Unsupported operation" in results[0]["error"]

    async def test_exception(self, processor):
        op = _op(operation_type="create", integration_id="jira", items=[{"id": 1}])
        with patch("asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("jira down"))):
            results = await processor._process_jira_bulk(op.items, op)
        assert results[0]["success"] is False
        assert "jira down" in results[0]["error"]


class TestSalesforce:
    async def test_create_and_update(self, processor):
        op = _op(operation_type="create", integration_id="salesforce",
                 items=[{"Name": "x"}])
        with patch("asyncio.sleep", new=AsyncMock()):
            results = await processor._process_salesforce_bulk(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["result"]["id"].startswith("001")

        op2 = _op(operation_type="update", integration_id="salesforce",
                  items=[{"Id": "a1"}])
        with patch("asyncio.sleep", new=AsyncMock()):
            results = await processor._process_salesforce_bulk(op2.items, op2)
        assert results[0]["result"]["success"] is True

    async def test_unsupported_operation(self, processor):
        op = _op(operation_type="delete", integration_id="salesforce", items=[{"Id": "a1"}])
        with patch("asyncio.sleep", new=AsyncMock()):
            results = await processor._process_salesforce_bulk(op.items, op)
        assert results[0]["success"] is False

    async def test_exception(self, processor):
        op = _op(operation_type="create", integration_id="salesforce", items=[{"Id": "a1"}])
        with patch("asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("sf down"))):
            results = await processor._process_salesforce_bulk(op.items, op)
        assert results[0]["success"] is False


# ============================================================================
# Notion / Airtable / HubSpot / Monday processors
# ============================================================================

class TestSimpleProcessors:
    @pytest.mark.parametrize("name", ["notion", "airtable", "hubspot", "monday"])
    async def test_success(self, processor, name):
        method = getattr(processor, f"_process_{name}_bulk")
        op = _op(operation_type="create", integration_id=name, items=[{"id": 1}])
        with patch("asyncio.sleep", new=AsyncMock()):
            results = await method(op.items, op)
        assert results[0]["success"] is True
        assert results[0]["item"] == {"id": 1}

    @pytest.mark.parametrize("name", ["notion", "airtable", "hubspot", "monday"])
    async def test_exception(self, processor, name):
        method = getattr(processor, f"_process_{name}_bulk")
        op = _op(operation_type="create", integration_id=name, items=[{"id": 1}])
        with patch("asyncio.sleep", new=AsyncMock(side_effect=RuntimeError(f"{name} down"))):
            results = await method(op.items, op)
        assert results[0]["success"] is False
        assert f"{name} down" in results[0]["error"]


# ============================================================================
# Performance stats + singleton
# ============================================================================

class TestStatsAndSingleton:
    async def test_performance_stats_no_completed(self, processor):
        running = _job(_op(), status=OperationStatus.RUNNING, job_id="bulk_run_1")
        processor.active_jobs["bulk_run_1"] = running
        stats = processor.get_performance_stats()
        assert stats["completed_jobs"] == 0
        assert stats["running_jobs"] == 1
        assert stats["average_processing_time"] == 0
        assert stats["success_rate"] == 0

    async def test_performance_stats_with_completed(self, processor):
        start = datetime.now(timezone.utc)
        job = _job(_op(items=[{"id": 1}, {"id": 2}]), job_id="bulk_done_1")
        job.status = OperationStatus.COMPLETED
        job.started_at = start
        job.completed_at = start + timedelta(seconds=4)
        job.successful_items = 2
        job.total_items = 2
        processor.active_jobs["bulk_done_1"] = job
        processor.job_queue = ["queued-1"]
        stats = processor.get_performance_stats()
        assert stats["completed_jobs"] == 1
        assert stats["average_processing_time"] == 4.0
        assert stats["total_items_processed"] == 2
        assert stats["success_rate"] == 100.0
        assert stats["queue_length"] == 1

    def test_get_bulk_processor_singleton(self):
        with patch.object(mod, "_bulk_processor", None):
            first = get_bulk_processor()
            second = get_bulk_processor()
            assert first is second
            assert isinstance(first, IntegrationBulkProcessor)
