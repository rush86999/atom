# -*- coding: utf-8 -*-
"""
Coverage + bug-hunt tests for core/webhook_ingestion_triggers.py.

The WebhookIngestionQueue coordinates Redis-backed asynchronous processing of
webhook-triggered ingestion jobs with tenant isolation. Existing coverage
(tests/test_r79_gap_webhook_ingestion.py) covers the happy paths and basic
Redis fallback. This file targets the remaining branches:

- Redis-unavailable initialization warning path
- JSON serialization failure on enqueue (returns job_id, drops job)
- process_webhook_job parse-error branch
- quota-check exception path (fail-open) + DB leak safety
- full processing exception path (pipeline raises)
- get_queue_depth / get_pending_jobs / clear_stuck_jobs / dequeue_job
  Redis-error branches
- stuck-job cleanup: missing enqueued_at, malformed JSON, fresh vs old
- ACU estimation edge cases

BUG found (TDD): ``get_pending_jobs(limit=0)`` calls
``lrange(key, 0, limit - 1)`` = ``lrange(key, 0, -1)`` which in Redis returns
the ENTIRE list, so a caller asking for zero jobs receives all of them.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis import RedisError

from core import webhook_ingestion_triggers as triggers
from core.webhook_ingestion_triggers import WebhookIngestionQueue


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def queue():
    """Queue with the redis module patched so __init__ doesn't connect."""
    with patch.object(triggers, "redis"):
        return WebhookIngestionQueue()


@pytest.fixture()
def no_redis_queue():
    with patch.object(triggers, "redis"):
        q = WebhookIngestionQueue()
        q.redis_client = None
        return q


@pytest.fixture()
def redis_queue():
    with patch.object(triggers, "redis"):
        q = WebhookIngestionQueue()
        q.redis_client = MagicMock()
        return q


def _job_dict(job_id="j1", tenant_id="t1", integration_id="slack",
              enqueued_at=None):
    return {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "trigger_type": "webhook",
        "payload": {"text": "hello"},
        "source_connection_id": None,
        "enqueued_at": enqueued_at or datetime.now(timezone.utc).isoformat(),
    }


def _patch_pipeline(usage_allowed=True, process_result=None, process_exc=None):
    """Patch IngestionPipelineService + UsageTrackingService + SessionLocal."""
    pipeline = AsyncMock()
    if process_exc is not None:
        pipeline.process_webhook_payload.side_effect = process_exc
    else:
        pipeline.process_webhook_payload.return_value = process_result or {
            "records_processed": 3,
            "entities_extracted": 1,
            "relationships_extracted": 2,
        }
    pipeline_mock = MagicMock(return_value=pipeline)
    usage = MagicMock()
    usage.check_quota_before_job = AsyncMock(
        return_value={"allowed": usage_allowed, "remaining_quota": 10, "reason": None}
    )
    workspace = MagicMock()
    workspace.id = "ws-1"
    return {
        "pipeline": pipeline,
        "pipeline_patch": patch.object(triggers, "IngestionPipelineService", pipeline_mock),
        "usage_patch": patch.object(triggers, "UsageTrackingService", return_value=usage),
        "usage": usage,
        "session_patch": patch.object(triggers, "SessionLocal"),
        "workspace": workspace,
    }


# ---------------------------------------------------------------------------
# __init__ warning when Redis unavailable
# ---------------------------------------------------------------------------

class TestInitNoRedisUrl:
    def test_warns_when_no_redis_url(self, caplog):
        with patch.object(triggers.os, "getenv", return_value=None):
            with patch.object(triggers, "redis"):
                q = WebhookIngestionQueue()
        assert q.redis_client is None
        assert q.queue_key == "ingestion:webhook:jobs"
        assert "Redis unavailable" in caplog.text

    def test_redis_client_created_when_url_present(self):
        with patch.object(triggers.os, "getenv", return_value="redis://localhost:6379"):
            with patch.object(triggers, "redis") as redis_mod:
                redis_mod.from_url.return_value = MagicMock()
                q = WebhookIngestionQueue()
        assert q.redis_client is not None
        redis_mod.from_url.assert_called_once()

    def test_upstash_url_preferred(self):
        with patch.object(triggers.os, "getenv") as getenv:
            def _env(key, default=None):
                return {"UPSTASH_REDIS_URL": "upstash-url",
                        "REDIS_URL": "redis-url"}.get(key, default)
            getenv.side_effect = _env
            with patch.object(triggers, "redis") as redis_mod:
                redis_mod.from_url.return_value = MagicMock()
                WebhookIngestionQueue()
        redis_mod.from_url.assert_called_once_with("upstash-url", decode_responses=True)


# ---------------------------------------------------------------------------
# enqueue_ingestion_job — serialization failure
# ---------------------------------------------------------------------------

class TestEnqueueSerializationFailure:
    async def test_unserializable_payload_returns_id_without_enqueue(self, redis_queue):
        """json.dumps fails -> job_id returned, nothing pushed, nothing processed."""
        redis_queue.redis_client.lpush = MagicMock(return_value=1)
        with patch.object(redis_queue, "process_webhook_job") as process:
            with patch.object(triggers.json, "dumps", side_effect=TypeError("nope")):
                job_id = await redis_queue.enqueue_ingestion_job(
                    tenant_id="t1", integration_id="slack",
                    trigger_type="webhook", payload=object(),
                )
        assert job_id
        redis_queue.redis_client.lpush.assert_not_called()
        process.assert_not_called()

    async def test_serialization_failure_value_error(self, redis_queue):
        with patch.object(triggers.json, "dumps", side_effect=ValueError("bad")):
            with patch.object(redis_queue, "process_webhook_job") as process:
                job_id = await redis_queue.enqueue_ingestion_job(
                    tenant_id="t1", integration_id="slack",
                    trigger_type="webhook", payload={},
                )
        assert job_id
        process.assert_not_called()

    async def test_source_connection_id_propagated(self, no_redis_queue):
        """source_connection_id is carried into process_webhook_job job_data."""
        with patch.object(no_redis_queue, "process_webhook_job") as process:
            await no_redis_queue.enqueue_ingestion_job(
                tenant_id="t1", integration_id="slack", trigger_type="webhook",
                payload={"a": 1}, source_connection_id="conn-99",
            )
        job_data = process.await_args.args[0]
        assert job_data["source_connection_id"] == "conn-99"


# ---------------------------------------------------------------------------
# process_webhook_job — parse error + quota paths
# ---------------------------------------------------------------------------

class TestProcessWebhookJobParseError:
    async def test_missing_job_data_keys_raises(self, queue):
        """job_data missing tenant_id/integration_id still proceeds (defaults)."""
        deps = _patch_pipeline()
        with deps["pipeline_patch"], deps["usage_patch"], deps["session_patch"] as cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = deps["workspace"]
            cm.return_value.__enter__.return_value = session
            # job_data with only job_id — payload defaults to {}
            result = await queue.process_webhook_job({"job_id": "x"})
        assert result["success"] is True

    async def test_job_data_not_a_dict_raises(self, queue):
        """If job_data.get() raises (e.g. a non-dict), the parse-error branch
        logs and re-raises."""
        with pytest.raises(AttributeError):
            await queue.process_webhook_job(None)  # None has no .get


class TestProcessWebhookJobQuota:
    @pytest.fixture()
    def job_data(self):
        return _job_dict()

    async def test_quota_exception_fails_open(self, queue, job_data):
        """If check_quota_before_job raises, processing continues (fail open)."""
        pipeline = AsyncMock()
        pipeline.process_webhook_payload.return_value = {"records_processed": 1}
        pipeline_mock = MagicMock(return_value=pipeline)
        usage = MagicMock()
        usage.check_quota_before_job = AsyncMock(side_effect=RuntimeError("db down"))
        usage.close = MagicMock()
        workspace = MagicMock()
        workspace.id = "ws-1"
        with patch.object(triggers, "IngestionPipelineService", pipeline_mock), \
             patch.object(triggers, "UsageTrackingService", return_value=usage), \
             patch.object(triggers, "SessionLocal") as cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = workspace
            cm.return_value.__enter__.return_value = session
            result = await queue.process_webhook_job(job_data)
        assert result["success"] is True
        # usage_tracker.close() must still be called even on quota error
        usage.close.assert_called_once()

    async def test_quota_rejected_returns_remaining(self, queue, job_data):
        deps = _patch_pipeline(usage_allowed=False)
        with deps["pipeline_patch"], deps["usage_patch"], deps["session_patch"]:
            result = await queue.process_webhook_job(job_data)
        assert result["success"] is False
        assert result["status"] == "rejected"
        assert result["remaining_quota"] == 10
        assert "estimated_acu" in result

    async def test_usage_tracker_closed_on_success(self, queue, job_data):
        deps = _patch_pipeline()
        with deps["pipeline_patch"], deps["usage_patch"] as up, deps["session_patch"] as cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = deps["workspace"]
            cm.return_value.__enter__.return_value = session
            await queue.process_webhook_job(job_data)
        # The UsageTrackingService instance must be closed to avoid DB leaks
        up.return_value.close.assert_called_once()


# ---------------------------------------------------------------------------
# process_webhook_job — full processing exception
# ---------------------------------------------------------------------------

class TestProcessWebhookJobProcessingError:
    @pytest.fixture()
    def job_data(self):
        return _job_dict()

    async def test_pipeline_exception_returns_failure(self, queue, job_data):
        deps = _patch_pipeline(process_exc=RuntimeError("pipeline crashed"))
        with deps["pipeline_patch"], deps["usage_patch"], deps["session_patch"] as cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = deps["workspace"]
            cm.return_value.__enter__.return_value = session
            result = await queue.process_webhook_job(job_data)
        assert result["success"] is False
        assert "Webhook job processing failed" in result["error"]
        assert result["duration_seconds"] >= 0

    async def test_workspace_not_found(self, queue, job_data):
        deps = _patch_pipeline()
        with deps["pipeline_patch"], deps["usage_patch"], deps["session_patch"] as cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = None
            cm.return_value.__enter__.return_value = session
            result = await queue.process_webhook_job(job_data)
        assert result["success"] is False
        assert result["status"] == "failed"
        assert "Workspace not found" in result["error"]

    async def test_success_includes_pipeline_result_fields(self, queue, job_data):
        deps = _patch_pipeline(process_result={
            "records_processed": 7, "entities_extracted": 3, "relationships_extracted": 5,
        })
        with deps["pipeline_patch"], deps["usage_patch"], deps["session_patch"] as cm:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = deps["workspace"]
            cm.return_value.__enter__.return_value = session
            result = await queue.process_webhook_job(job_data)
        assert result["success"] is True
        assert result["records_processed"] == 7
        assert result["entities_extracted"] == 3
        assert result["duration_seconds"] >= 0


# ---------------------------------------------------------------------------
# get_queue_depth — Redis error path
# ---------------------------------------------------------------------------

class TestGetQueueDepth:
    async def test_returns_llen_value(self, redis_queue):
        redis_queue.redis_client.llen.return_value = 42
        assert await redis_queue.get_queue_depth() == 42

    async def test_redis_error_returns_zero(self, redis_queue):
        redis_queue.redis_client.llen.side_effect = RedisError("down")
        assert await redis_queue.get_queue_depth() == 0

    async def test_no_redis_returns_zero(self, no_redis_queue):
        assert await no_redis_queue.get_queue_depth() == 0


# ---------------------------------------------------------------------------
# get_pending_jobs
# ---------------------------------------------------------------------------

class TestGetPendingJobs:
    async def test_parses_jobs(self, redis_queue):
        job = _job_dict(job_id="j1")
        redis_queue.redis_client.lrange.return_value = [json.dumps(job)]
        result = await redis_queue.get_pending_jobs(limit=10)
        assert len(result) == 1
        assert result[0]["job_id"] == "j1"
        assert result[0]["integration_id"] == "slack"

    async def test_skips_malformed_json(self, redis_queue):
        good = _job_dict(job_id="good")
        redis_queue.redis_client.lrange.return_value = [json.dumps(good), "{broken"]
        result = await redis_queue.get_pending_jobs()
        assert len(result) == 1
        assert result[0]["job_id"] == "good"

    async def test_redis_error_returns_empty(self, redis_queue):
        redis_queue.redis_client.lrange.side_effect = RedisError("down")
        assert await redis_queue.get_pending_jobs() == []

    async def test_no_redis_returns_empty(self, no_redis_queue):
        assert await no_redis_queue.get_pending_jobs() == []

    async def test_limit_passed_to_lrange(self, redis_queue):
        redis_queue.redis_client.lrange.return_value = []
        await redis_queue.get_pending_jobs(limit=50)
        redis_queue.redis_client.lrange.assert_called_once_with(
            "ingestion:webhook:jobs", 0, 49
        )


# ---------------------------------------------------------------------------
# BUG: get_pending_jobs(limit=0) returns ALL jobs
# ---------------------------------------------------------------------------

class TestGetPendingJobsLimitZeroBug:
    async def test_limit_zero_returns_no_jobs(self, redis_queue):
        """BUG: get_pending_jobs(limit=0) computes ``lrange(key, 0, 0 - 1)``
        = ``lrange(key, 0, -1)`` which in Redis returns the ENTIRE list. A
        caller asking for zero pending jobs therefore receives every queued
        job instead of an empty list.

        Setup: queue contains 3 jobs. Expectation after fix: limit=0 -> [].
        Before fix: returns all 3.
        """
        jobs = [json.dumps(_job_dict(job_id=f"j{i}")) for i in range(3)]
        redis_queue.redis_client.lrange.return_value = jobs
        result = await redis_queue.get_pending_jobs(limit=0)
        assert result == [], (
            f"limit=0 must return no jobs, got {len(result)}"
        )


# ---------------------------------------------------------------------------
# clear_stuck_jobs
# ---------------------------------------------------------------------------

class TestClearStuckJobs:
    async def test_removes_old_jobs(self, redis_queue):
        old = _job_dict(job_id="old",
                        enqueued_at=(datetime.now(timezone.utc) - timedelta(hours=5)).isoformat())
        fresh = _job_dict(job_id="fresh")
        redis_queue.redis_client.lrange.return_value = [json.dumps(old), json.dumps(fresh)]
        cleared = await redis_queue.clear_stuck_jobs(max_age_minutes=60)
        assert cleared == 1
        redis_queue.redis_client.lrem.assert_called_once()

    async def test_no_redis_returns_zero(self, no_redis_queue):
        assert await no_redis_queue.clear_stuck_jobs() == 0

    async def test_redis_error_returns_zero(self, redis_queue):
        redis_queue.redis_client.lrange.side_effect = RedisError("down")
        assert await redis_queue.clear_stuck_jobs() == 0

    async def test_skips_missing_enqueued_at(self, redis_queue):
        """Job with no enqueued_at is skipped (not cleared, not crashed)."""
        job = {"job_id": "nots", "tenant_id": "t1", "integration_id": "slack"}
        redis_queue.redis_client.lrange.return_value = [json.dumps(job)]
        cleared = await redis_queue.clear_stuck_jobs()
        assert cleared == 0
        redis_queue.redis_client.lrem.assert_not_called()

    async def test_skips_malformed_json(self, redis_queue):
        redis_queue.redis_client.lrange.return_value = ["{broken"]
        cleared = await redis_queue.clear_stuck_jobs()
        assert cleared == 0

    async def test_skips_unparseable_timestamp(self, redis_queue):
        job = _job_dict(job_id="bad", enqueued_at="not-a-timestamp")
        redis_queue.redis_client.lrange.return_value = [json.dumps(job)]
        cleared = await redis_queue.clear_stuck_jobs()
        assert cleared == 0

    async def test_fresh_jobs_not_removed(self, redis_queue):
        fresh = _job_dict(job_id="fresh")
        redis_queue.redis_client.lrange.return_value = [json.dumps(fresh)]
        cleared = await redis_queue.clear_stuck_jobs(max_age_minutes=60)
        assert cleared == 0
        redis_queue.redis_client.lrem.assert_not_called()

    async def test_clears_all_when_all_old(self, redis_queue):
        old1 = _job_dict(job_id="o1", enqueued_at=(datetime.now(timezone.utc) - timedelta(hours=10)).isoformat())
        old2 = _job_dict(job_id="o2", enqueued_at=(datetime.now(timezone.utc) - timedelta(hours=20)).isoformat())
        redis_queue.redis_client.lrange.return_value = [json.dumps(old1), json.dumps(old2)]
        cleared = await redis_queue.clear_stuck_jobs(max_age_minutes=60)
        assert cleared == 2
        assert redis_queue.redis_client.lrem.call_count == 2


# ---------------------------------------------------------------------------
# dequeue_job
# ---------------------------------------------------------------------------

class TestDequeueJob:
    async def test_returns_parsed_job(self, redis_queue):
        job = _job_dict(job_id="j1")
        redis_queue.redis_client.rpop.return_value = json.dumps(job)
        result = await redis_queue.dequeue_job()
        assert result["job_id"] == "j1"

    async def test_empty_queue_returns_none(self, redis_queue):
        redis_queue.redis_client.rpop.return_value = None
        assert await redis_queue.dequeue_job() is None

    async def test_no_redis_returns_none(self, no_redis_queue):
        assert await no_redis_queue.dequeue_job() is None

    async def test_redis_error_returns_none(self, redis_queue):
        redis_queue.redis_client.rpop.side_effect = RedisError("down")
        assert await redis_queue.dequeue_job() is None

    async def test_malformed_json_returns_none(self, redis_queue):
        redis_queue.redis_client.rpop.return_value = "{broken"
        assert await redis_queue.dequeue_job() is None


# ---------------------------------------------------------------------------
# _estimate_webhook_acu
# ---------------------------------------------------------------------------

class TestEstimateAcu:
    def test_base_acu_slack(self, queue):
        assert queue._estimate_webhook_acu("slack", 0) == pytest.approx(5.0)

    def test_payload_scales(self, queue):
        # 5 + 1000*0.001 = 6.0
        assert queue._estimate_webhook_acu("slack", 1000) == pytest.approx(6.0)

    def test_salesforce_multiplier(self, queue):
        assert queue._estimate_webhook_acu("salesforce", 0) == pytest.approx(6.0)

    def test_gmail_lower_multiplier(self, queue):
        assert queue._estimate_webhook_acu("gmail", 0) == pytest.approx(4.0)

    def test_unknown_integration_default_multiplier(self, queue):
        assert queue._estimate_webhook_acu("unknown", 100) == pytest.approx(5.1)

    def test_zero_payload_size(self, queue):
        assert queue._estimate_webhook_acu("hubspot", 0) == pytest.approx(5.5)

    @pytest.mark.parametrize("integration,expected_mult", [
        ("slack", 1.0), ("salesforce", 1.2), ("hubspot", 1.1), ("zoho_crm", 1.1),
        ("zoho_desk", 1.1), ("zoho_books", 1.0), ("gmail", 0.8), ("notion", 1.0),
        ("asana", 1.1), ("trello", 1.0), ("jira", 1.2), ("github", 0.9),
        ("gitlab", 1.0), ("pipedrive", 1.1), ("mailchimp", 1.0), ("stripe", 0.9),
        ("shopify", 1.1),
    ])
    def test_all_multipliers(self, queue, integration, expected_mult):
        assert queue._estimate_webhook_acu(integration, 0) == pytest.approx(5.0 * expected_mult)


# ---------------------------------------------------------------------------
# enqueue — Redis path queue_depth logging
# ---------------------------------------------------------------------------

class TestEnqueueRedisPath:
    async def test_logs_queue_depth_after_push(self, redis_queue, caplog):
        redis_queue.redis_client.lpush.return_value = 1
        redis_queue.redis_client.llen.return_value = 5
        with patch.object(redis_queue, "process_webhook_job") as process:
            job_id = await redis_queue.enqueue_ingestion_job(
                tenant_id="t1", integration_id="slack",
                trigger_type="webhook", payload={"x": 1},
            )
        assert job_id
        redis_queue.redis_client.lpush.assert_called_once()
        # The pushed JSON contains the job_id
        pushed = redis_queue.redis_client.lpush.call_args.args[1]
        assert json.loads(pushed)["job_id"] == job_id
        process.assert_not_called()


# ---------------------------------------------------------------------------
# run_worker_loop — the production consumer for the Redis queue.
#
# BUG found (fix verified): with Redis configured, enqueue_ingestion_job only
# LPUSHes to ingestion:webhook:jobs and dequeue_job had NO production caller —
# pushed jobs sat in Redis forever (the synchronous fallback only runs when
# Redis is unavailable).
# ---------------------------------------------------------------------------

class TestWorkerLoop:
    async def test_no_redis_returns_without_looping(self, no_redis_queue):
        # Must return promptly, not hang: with no Redis, enqueues already
        # process inline, so there is nothing to drain.
        await asyncio.wait_for(no_redis_queue.run_worker_loop(), timeout=1)

    async def _run_worker_briefly(self, queue, **kwargs):
        # Tick in real milliseconds (not sleep(0)) so the worker's parked
        # poll_interval sleeps actually elapse between iterations.
        task = asyncio.create_task(queue.run_worker_loop(**kwargs))
        try:
            for _ in range(500):
                await asyncio.sleep(0.002)
                yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_drains_queued_jobs(self, redis_queue):
        job = _job_dict(job_id="j1")
        redis_queue.redis_client.rpop = MagicMock(
            side_effect=[json.dumps(job), json.dumps(job), None]
        )
        processed = AsyncMock()
        with patch.object(redis_queue, "process_webhook_job", processed):
            async for _ in self._run_worker_briefly(
                redis_queue, poll_interval_seconds=0.01
            ):
                if processed.await_count >= 2:
                    break
        assert processed.await_count == 2

    async def test_failed_job_does_not_kill_worker(self, redis_queue):
        job_a, job_b = _job_dict(job_id="ja"), _job_dict(job_id="jb")
        redis_queue.redis_client.rpop = MagicMock(
            side_effect=[json.dumps(job_a), json.dumps(job_b), None]
        )
        processed = AsyncMock(side_effect=[RuntimeError("boom"), {"success": True}])
        with patch.object(redis_queue, "process_webhook_job", processed):
            async for _ in self._run_worker_briefly(
                redis_queue, poll_interval_seconds=0.01
            ):
                if processed.await_count >= 2:
                    break
        assert processed.await_count == 2

    async def test_parks_when_queue_empty(self, redis_queue):
        redis_queue.redis_client.rpop = MagicMock(return_value=None)
        processed = AsyncMock()
        with patch.object(redis_queue, "process_webhook_job", processed):
            async for _ in self._run_worker_briefly(
                redis_queue, poll_interval_seconds=60
            ):
                pass  # a few loop ticks without a single rpop side effect
        processed.assert_not_awaited()
        assert redis_queue.redis_client.rpop.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
