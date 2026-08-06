# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/webhook_ingestion_triggers.py (webhook ingestion
job queue with Redis + sync fallback; zero test references before this file).

TDD targets (RED first):
- ``process_webhook_job`` / ``dequeue_job`` leak ``[FATAL_DEBUG]`` payload
  fragments (job_id/tenant_id/workspace_id prefixes) to stderr — leftover
  debug prints that must not ship in a webhook ingestion path.
- Baseline: enqueue with Redis push, sync fallback when Redis is unavailable,
  quota rejection, workspace-not-found, queue depth/pending/stuck-jobs,
  dequeue, ACU estimation.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import webhook_ingestion_triggers as triggers
from core.webhook_ingestion_triggers import WebhookIngestionQueue


@pytest.fixture()
def queue():
    with patch.object(triggers, "redis") as _:
        return WebhookIngestionQueue()


class TestEstimateAcu:
    def test_base_acu_for_known_integration(self, queue):
        assert queue._estimate_webhook_acu("slack", 0) == pytest.approx(5.0)

    def test_payload_size_scales_acu(self, queue):
        assert queue._estimate_webhook_acu("slack", 1000) == pytest.approx(6.0)

    def test_complexity_multiplier(self, queue):
        assert queue._estimate_webhook_acu("salesforce", 0) == pytest.approx(6.0)

    def test_unknown_integration_default_multiplier(self, queue):
        assert queue._estimate_webhook_acu("unknown_platform", 100) == pytest.approx(5.1)


class TestNoRedisFallback:
    @pytest.fixture()
    def no_redis_queue(self):
        with patch.object(triggers, "redis"):
            q = WebhookIngestionQueue()
            q.redis_client = None
            return q

    async def test_enqueue_processes_synchronously(self, no_redis_queue):
        with patch.object(no_redis_queue, "process_webhook_job") as process:
            process.return_value = {"success": True}
            job_id = await no_redis_queue.enqueue_ingestion_job(
                tenant_id="t1",
                integration_id="slack",
                trigger_type="webhook",
                payload={"text": "hello"},
            )
            assert job_id
            process.assert_awaited_once()

    async def test_get_queue_depth_zero_without_redis(self, no_redis_queue):
        assert await no_redis_queue.get_queue_depth() == 0

    async def test_get_pending_jobs_empty_without_redis(self, no_redis_queue):
        assert await no_redis_queue.get_pending_jobs() == []

    async def test_clear_stuck_jobs_zero_without_redis(self, no_redis_queue):
        assert await no_redis_queue.clear_stuck_jobs() == 0

    async def test_dequeue_none_without_redis(self, no_redis_queue):
        assert await no_redis_queue.dequeue_job() is None


class TestRedisPath:
    @pytest.fixture()
    def redis_queue(self):
        with patch.object(triggers, "redis"):
            q = WebhookIngestionQueue()
            q.redis_client = MagicMock()
            return q

    async def test_enqueue_pushes_to_redis(self, redis_queue):
        redis_queue.redis_client.lpush.return_value = 1
        redis_queue.redis_client.llen.return_value = 1
        with patch.object(redis_queue, "process_webhook_job") as process:
            job_id = await redis_queue.enqueue_ingestion_job(
                tenant_id="t1", integration_id="slack", trigger_type="webhook", payload={}
            )
        assert job_id
        redis_queue.redis_client.lpush.assert_called_once()
        assert json.loads(redis_queue.redis_client.lpush.call_args.args[1])["job_id"] == job_id

    async def test_enqueue_falls_back_sync_on_redis_error(self, redis_queue):
        from redis import RedisError

        redis_queue.redis_client.lpush.side_effect = RedisError("down")
        with patch.object(redis_queue, "process_webhook_job") as process:
            process.return_value = {"success": True}
            await redis_queue.enqueue_ingestion_job(
                tenant_id="t1", integration_id="slack", trigger_type="webhook", payload={}
            )
            process.assert_awaited_once()

    async def test_get_queue_depth_uses_llen(self, redis_queue):
        redis_queue.redis_client.llen.return_value = 7
        assert await redis_queue.get_queue_depth() == 7

    async def test_get_pending_jobs_parses_queue(self, redis_queue):
        job = {
            "job_id": "j1",
            "tenant_id": "t1",
            "integration_id": "slack",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        redis_queue.redis_client.lrange.return_value = [json.dumps(job), "{broken json"]
        jobs = await redis_queue.get_pending_jobs(limit=10)
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "j1"

    async def test_clear_stuck_jobs_removes_old(self, redis_queue):
        old = {
            "job_id": "old",
            "enqueued_at": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
        }
        fresh = {
            "job_id": "fresh",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        redis_queue.redis_client.lrange.return_value = [json.dumps(old), json.dumps(fresh)]
        cleared = await redis_queue.clear_stuck_jobs(max_age_minutes=60)
        assert cleared == 1
        redis_queue.redis_client.lrem.assert_called_once()

    async def test_dequeue_job_roundtrip(self, redis_queue):
        job = {"job_id": "j1", "tenant_id": "t1"}
        redis_queue.redis_client.rpop.return_value = json.dumps(job)
        assert await redis_queue.dequeue_job() == job

    async def test_dequeue_job_empty_queue(self, redis_queue):
        redis_queue.redis_client.rpop.return_value = None
        assert await redis_queue.dequeue_job() is None


class TestProcessWebhookJob:
    @pytest.fixture()
    def job_data(self):
        return {
            "job_id": "job-123",
            "tenant_id": "tenant-abc",
            "integration_id": "slack",
            "trigger_type": "webhook",
            "payload": {"text": "hello"},
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }

    def _patch_deps(self, usage_allowed=True):
        pipeline = AsyncMock()
        pipeline.process_webhook_payload.return_value = {"records_processed": 3}
        pipeline_mock = MagicMock(return_value=pipeline)
        usage = MagicMock()
        usage.check_quota_before_job = AsyncMock(
            return_value={"allowed": usage_allowed, "remaining_quota": 10, "reason": None}
        )
        workspace = MagicMock()
        workspace.id = "ws-1"
        return {
            "pipeline": pipeline,
            "pipeline_mock": patch.object(triggers, "IngestionPipelineService", pipeline_mock),
            "usage_mock": patch.object(triggers, "UsageTrackingService", return_value=usage),
            "session_mock": patch.object(triggers, "SessionLocal"),
            "workspace": workspace,
        }

    async def test_process_webhook_job_success(self, queue, job_data):
        deps = self._patch_deps()
        with deps["pipeline_mock"], deps["usage_mock"], deps["session_mock"] as session_cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = deps["workspace"]
            session_cm.return_value.__enter__.return_value = session
            result = await queue.process_webhook_job(job_data)

        assert result["success"] is True
        assert result["records_processed"] == 3
        deps["pipeline"].process_webhook_payload.assert_awaited_once()

    async def test_process_webhook_job_quota_rejected(self, queue, job_data):
        deps = self._patch_deps(usage_allowed=False)
        with deps["pipeline_mock"], deps["usage_mock"], deps["session_mock"]:
            result = await queue.process_webhook_job(job_data)
        assert result["success"] is False
        assert result["status"] == "rejected"

    async def test_process_webhook_job_workspace_missing(self, queue, job_data):
        deps = self._patch_deps()
        with deps["pipeline_mock"], deps["usage_mock"], deps["session_mock"] as session_cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = None
            session_cm.return_value.__enter__.return_value = session
            result = await queue.process_webhook_job(job_data)
        assert result["success"] is False
        assert "Workspace not found" in result["error"]

    async def test_no_fatal_debug_stderr_output(self, queue, job_data, capsys):
        """RED: [FATAL_DEBUG] prints leaked job/tenant fragments to stderr."""
        deps = self._patch_deps()
        with deps["pipeline_mock"], deps["usage_mock"], deps["session_mock"] as session_cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = deps["workspace"]
            session_cm.return_value.__enter__.return_value = session
            await queue.process_webhook_job(job_data)

        captured = capsys.readouterr()
        assert "[FATAL_DEBUG]" not in captured.err
        assert "job-123" not in captured.err
        assert "tenant-abc" not in captured.err

    async def test_dequeue_job_no_debug_print(self, queue, capsys):
        redis_queue = queue
        redis_queue.redis_client = MagicMock()
        redis_queue.redis_client.rpop.return_value = None
        await redis_queue.dequeue_job()
        captured = capsys.readouterr()
        assert "[FATAL_DEBUG]" not in captured.err
