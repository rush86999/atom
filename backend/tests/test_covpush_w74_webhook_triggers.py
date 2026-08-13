# -*- coding: utf-8 -*-
"""Coverage wave 74 — core/webhook_ingestion_triggers.py (fully mocked Redis +
SessionLocal, no network, no real DB).

Complements test_r79_gap_webhook_ingestion.py; covers the remaining branches:
- enqueue: JSON serialization failure (returns job id for error tracking)
- process_webhook_job: malformed job re-raise, quota-check failure → fail-open
  continue (logged, job still processed), pipeline exception → error dict with
  duration, workspace-not-found, success dict shape
- get_queue_depth: RedisError → 0
- get_pending_jobs: limit<=0 guard, RedisError → [], per-job parse errors
  skipped
- clear_stuck_jobs: missing enqueued_at skipped, JSON/ValueError skipped,
  RedisError → 0
- dequeue_job: RedisError/JSONDecodeError → None
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis as redis_lib

from core import webhook_ingestion_triggers as triggers
from core.webhook_ingestion_triggers import WebhookIngestionQueue


@pytest.fixture()
def queue():
    """No REDIS_URL env → real redis module imported, client stays None."""
    return WebhookIngestionQueue()


def _job(tenant_id="t1", integration_id="slack", payload=None, enqueued_at=None):
    return {
        "job_id": "job-1",
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "trigger_type": "webhook",
        "payload": payload if payload is not None else {"event": "message"},
        "source_connection_id": "conn-1",
        "enqueued_at": enqueued_at or datetime.now(timezone.utc).isoformat(),
    }


class TestEnqueueSerialization:
    @pytest.mark.asyncio
    async def test_unserializable_payload_returns_job_id(self, queue):
        queue.redis_client = MagicMock()
        job_id = await queue.enqueue_ingestion_job(
            "t1", "slack", "webhook", {"bad": object()}
        )
        assert isinstance(job_id, str)
        queue.redis_client.lpush.assert_not_called()


class TestProcessWebhookJob:
    @pytest.mark.asyncio
    async def test_malformed_job_reraises(self, queue):
        with patch.object(triggers, "UsageTrackingService"):
            with pytest.raises(AttributeError):
                await queue.process_webhook_job(None)  # None.get raises

    @pytest.mark.asyncio
    async def test_quota_check_failure_fails_open(self, queue):
        usage = MagicMock()
        usage.check_quota_before_job = AsyncMock(side_effect=RuntimeError("quota service down"))
        workspace = MagicMock()
        workspace.id = "ws-1"
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.query.return_value.filter.return_value.first.return_value = workspace
        pipeline = AsyncMock()
        pipeline.process_webhook_payload = AsyncMock(return_value={
            "records_processed": 2, "entities_extracted": 3, "relationships_extracted": 1,
        })
        with patch.object(triggers, "UsageTrackingService", return_value=usage), \
             patch.object(triggers, "SessionLocal", return_value=session), \
             patch.object(triggers, "IngestionPipelineService", return_value=pipeline):
            result = await queue.process_webhook_job(_job())

        assert result["success"] is True  # quota failure does NOT reject the job
        assert result["records_processed"] == 2
        assert usage.close.called

    @pytest.mark.asyncio
    async def test_pipeline_exception_returns_error_dict(self, queue):
        usage = MagicMock()
        usage.check_quota_before_job = AsyncMock(return_value={"allowed": True})
        workspace = MagicMock()
        workspace.id = "ws-1"
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.query.return_value.filter.return_value.first.return_value = workspace
        pipeline = AsyncMock()
        pipeline.process_webhook_payload = AsyncMock(side_effect=RuntimeError("pipeline boom"))
        with patch.object(triggers, "UsageTrackingService", return_value=usage), \
             patch.object(triggers, "SessionLocal", return_value=session), \
             patch.object(triggers, "IngestionPipelineService", return_value=pipeline):
            result = await queue.process_webhook_job(_job())

        assert result["success"] is False
        assert result["job_id"] == "job-1"
        assert "pipeline boom" in result["error"]
        assert result["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_workspace_not_found(self, queue):
        usage = MagicMock()
        usage.check_quota_before_job = AsyncMock(return_value={"allowed": True})
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session.query.return_value.filter.return_value.first.return_value = None
        with patch.object(triggers, "UsageTrackingService", return_value=usage), \
             patch.object(triggers, "SessionLocal", return_value=session):
            result = await queue.process_webhook_job(_job())

        assert result["success"] is False
        assert result["status"] == "failed"
        assert "Workspace not found" in result["error"]


class TestQueueDepth:
    @pytest.mark.asyncio
    async def test_redis_error_returns_zero(self, queue):
        client = MagicMock()
        client.llen.side_effect = redis_lib.RedisError("redis down")
        queue.redis_client = client
        assert await queue.get_queue_depth() == 0


class TestPendingJobs:
    @pytest.mark.asyncio
    async def test_limit_zero_returns_empty(self, queue):
        queue.redis_client = MagicMock()
        assert await queue.get_pending_jobs(limit=0) == []
        queue.redis_client.lrange.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_error_returns_empty(self, queue):
        client = MagicMock()
        client.lrange.side_effect = redis_lib.RedisError("redis down")
        queue.redis_client = client
        assert await queue.get_pending_jobs() == []

    @pytest.mark.asyncio
    async def test_parse_errors_skipped(self, queue):
        client = MagicMock()
        client.lrange.return_value = [json.dumps(_job()), "not-json{{", "also-bad"]
        queue.redis_client = client
        jobs = await queue.get_pending_jobs()
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job-1"

    @pytest.mark.asyncio
    async def test_respects_limit(self, queue):
        client = MagicMock()
        entries = [json.dumps(_job()) for _ in range(3)]
        client.lrange.side_effect = lambda key, start, stop: entries[start:stop + 1]
        queue.redis_client = client
        jobs = await queue.get_pending_jobs(limit=2)
        assert len(jobs) == 2
        client.lrange.assert_called_with(queue.queue_key, 0, 1)


class TestClearStuckJobs:
    @pytest.mark.asyncio
    async def test_missing_enqueued_at_skipped(self, queue):
        client = MagicMock()
        stale = _job()
        stale["enqueued_at"] = None
        client.lrange.return_value = [json.dumps(stale)]
        queue.redis_client = client
        assert await queue.clear_stuck_jobs() == 0
        client.lrem.assert_not_called()

    @pytest.mark.asyncio
    async def test_parse_errors_skipped(self, queue):
        client = MagicMock()
        client.lrange.return_value = ["{{bad-json", json.dumps(_job())]
        queue.redis_client = client
        assert await queue.clear_stuck_jobs() == 0
        client.lrem.assert_not_called()

    @pytest.mark.asyncio
    async def test_removes_old_jobs_only(self, queue):
        client = MagicMock()
        old = _job(enqueued_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
        fresh = _job()
        client.lrange.return_value = [json.dumps(fresh), json.dumps(old)]
        queue.redis_client = client
        assert await queue.clear_stuck_jobs(max_age_minutes=60) == 1
        client.lrem.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_error_returns_zero(self, queue):
        client = MagicMock()
        client.lrange.side_effect = redis_lib.RedisError("redis down")
        queue.redis_client = client
        assert await queue.clear_stuck_jobs() == 0


class TestDequeue:
    @pytest.mark.asyncio
    async def test_redis_error_returns_none(self, queue):
        client = MagicMock()
        client.rpop.side_effect = redis_lib.RedisError("redis down")
        queue.redis_client = client
        assert await queue.dequeue_job() is None

    @pytest.mark.asyncio
    async def test_bad_json_returns_none(self, queue):
        client = MagicMock()
        client.rpop.return_value = "not-json{{"
        queue.redis_client = client
        assert await queue.dequeue_job() is None

    @pytest.mark.asyncio
    async def test_returns_job_dict(self, queue):
        client = MagicMock()
        client.rpop.return_value = json.dumps(_job())
        queue.redis_client = client
        job = await queue.dequeue_job()
        assert job["job_id"] == "job-1"
        assert job["tenant_id"] == "t1"
