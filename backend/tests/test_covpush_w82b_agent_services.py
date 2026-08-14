"""Coverage wave 82b — agent-service cores (8 modules).

Targets (statement coverage, standalone >=95% each):
  - core.admin_endpoints.py
  - core.agent_communication.py
  - core.agent_learning_enhanced.py
  - core.agent_promotion_service.py
  - core.agent_request_manager.py
  - core.agent_worker_wrapper.py
  - core.ai_workflow_optimization_endpoints.py
  - core.auto_healing.py

Conventions: mocked deps only, zero LLM spend, no network, no real DB
(fake sessions / chained query mocks). Endpoint tests use TestClient with
app.dependency_overrides. Patches target real module names (no backend.
prefix).

Lines left uncovered (documented in the wave report):
  - ai_workflow_optimization_endpoints 235-236, 357-358, 407-408, 440-441:
    bare `except Exception` handlers whose bodies are pure dict building
    (nothing inside the try can raise) — unreachable.
"""
import asyncio
import importlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.agent_communication as ac
import core.agent_request_manager as arm
import core.ai_workflow_optimization_endpoints as awe
import core.auto_healing as ah
from core.admin_endpoints import get_super_admin
from core.agent_learning_enhanced import AgentLearningEnhanced
from core.agent_promotion_service import AgentPromotionService, PromotionCriteria
from core.agent_request_manager import AgentRequestManager, get_agent_request_manager
from core.agent_worker_wrapper import execute_agent_background
from core.ai_workflow_optimization_endpoints import (
    _calculate_risk_level,
    _execute_optimization_implementation,
    _group_recommendations_by_type,
)
from core.ai_workflow_optimizer import (
    ImpactLevel,
    OptimizationRecommendation,
    OptimizationType,
    WorkflowAnalysis,
    get_ai_workflow_optimizer,
)
from core.models import AgentStatus, UserRole


# ===========================================================================
# core.admin_endpoints
# ===========================================================================


class TestAdminEndpoints:
    async def test_super_admin_role_string_value(self):
        user = MagicMock(role="super_admin")
        assert await get_super_admin(user) is user

    async def test_super_admin_role_enum(self):
        user = MagicMock(role=UserRole.SUPER_ADMIN)
        assert await get_super_admin(user) is user

    async def test_non_super_admin_forbidden(self):
        from fastapi import HTTPException

        for role in ("admin", UserRole.OWNER, UserRole.MEMBER):
            user = MagicMock(role=role)
            with pytest.raises(HTTPException) as exc:
                await get_super_admin(user)
            assert exc.value.status_code == 403


# ===========================================================================
# core.agent_worker_wrapper
# ===========================================================================


class TestAgentWorkerWrapper:
    def test_execute_background_success(self):
        atom_instance = MagicMock()
        atom_instance.execute = AsyncMock(return_value={"status": "done"})
        atom_class = MagicMock(return_value=atom_instance)
        with patch("core.atom_meta_agent.AtomMetaAgent", atom_class):
            result = execute_agent_background({
                "request": "Summarize sales data for the last quarter",
                "context": {"user_id": "u1"},
                "trigger_mode": "data_event",
                "tenant_id": "t-1",
            })
        assert result == {"status": "done"}
        atom_instance.execute.assert_awaited_once()
        atom_class.assert_called_once_with("t-1")

    def test_execute_background_defaults_and_missing_request(self):
        atom_instance = MagicMock()
        atom_instance.execute = AsyncMock(return_value=None)
        with patch("core.atom_meta_agent.AtomMetaAgent", MagicMock(return_value=atom_instance)):
            result = execute_agent_background({"tenant_id": "default"})
        assert result is None
        _, kwargs = atom_instance.execute.await_args
        assert kwargs["request"] is None
        assert kwargs["context"] == {}
        assert kwargs["trigger_mode"].value == "manual"

    def test_execute_background_error_reraises(self):
        atom_class = MagicMock(side_effect=RuntimeError("agent init failed"))
        with patch("core.atom_meta_agent.AtomMetaAgent", atom_class):
            with pytest.raises(RuntimeError, match="agent init failed"):
                execute_agent_background({"request": "x"})

    def test_execute_background_invalid_trigger_mode(self):
        atom_instance = MagicMock()
        atom_instance.execute = AsyncMock(return_value="ok")
        with patch("core.atom_meta_agent.AtomMetaAgent", MagicMock(return_value=atom_instance)):
            with pytest.raises(ValueError):
                execute_agent_background({"request": "x", "trigger_mode": "bogus"})

    def test_execute_background_agent_loop_raises(self):
        atom_instance = MagicMock()
        atom_instance.execute = AsyncMock(side_effect=RuntimeError("exec boom"))
        with patch("core.atom_meta_agent.AtomMetaAgent", MagicMock(return_value=atom_instance)):
            with pytest.raises(RuntimeError, match="exec boom"):
                execute_agent_background({"request": "x"})


# ===========================================================================
# core.auto_healing
# ===========================================================================


class TestCircuitBreaker:
    def test_call_success_closed(self):
        cb = ah.CircuitBreaker()
        assert cb.call(lambda: 42) == 42
        assert cb.state == "CLOSED"

    def test_call_open_within_timeout_raises(self):
        cb = ah.CircuitBreaker(timeout=60)
        cb.state = "OPEN"
        cb.last_failure_time = datetime.now()
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            cb.call(lambda: 1)

    def test_call_open_timeout_elapsed_half_open_reset(self):
        cb = ah.CircuitBreaker(timeout=60)
        cb.state = "OPEN"
        cb.last_failure_time = datetime.now() - timedelta(seconds=120)
        assert cb.call(lambda: "recovered") == "recovered"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_call_failure_records_and_opens(self):
        cb = ah.CircuitBreaker(failure_threshold=2)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.failure_count == 1
        assert cb.state == "CLOSED"
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.failure_count == 2
        assert cb.state == "OPEN"

    def test_call_failure_in_half_open_stays_open_threshold(self):
        cb = ah.CircuitBreaker(failure_threshold=5)
        cb.state = "HALF_OPEN"
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("nope")))
        assert cb.state == "HALF_OPEN"
        assert cb.failure_count == 1

    def test_record_failure_opens_at_threshold(self):
        cb = ah.CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.last_failure_time is not None

    def test_reset(self):
        cb = ah.CircuitBreaker()
        cb.state = "OPEN"
        cb.failure_count = 4
        cb.last_failure_time = datetime.now()
        cb.reset()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None


class TestRetryWithBackoff:
    def test_success_first_try(self):
        @ah.retry_with_backoff(max_retries=3)
        def f():
            return "ok"
        assert f() == "ok"

    def test_retry_then_success(self):
        calls = {"n": 0}

        @ah.retry_with_backoff(max_retries=3, base_delay=0.01)
        def f():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("transient")
            return "ok"

        with patch.object(time, "sleep") as sleep_mock:
            assert f() == "ok"
        assert calls["n"] == 3
        assert sleep_mock.call_count == 2

    def test_max_retries_exhausted_raises_last(self):
        @ah.retry_with_backoff(max_retries=2, base_delay=0.01)
        def f():
            raise ValueError("always")

        with patch.object(time, "sleep") as sleep_mock:
            with pytest.raises(ValueError, match="always"):
                f()
        assert sleep_mock.call_count == 2

    def test_delay_capped_at_max_delay(self):
        @ah.retry_with_backoff(max_retries=1, base_delay=100, max_delay=5, exponential_base=2.0)
        def f():
            raise ValueError("x")

        with patch.object(time, "sleep") as sleep_mock:
            with pytest.raises(ValueError):
                f()
        sleep_mock.assert_called_once_with(5)

    def test_non_matching_exception_propagates(self):
        @ah.retry_with_backoff(max_retries=3, exceptions=(ValueError,))
        def f():
            raise TypeError("not retried")

        with patch.object(time, "sleep") as sleep_mock:
            with pytest.raises(TypeError, match="not retried"):
                f()
        sleep_mock.assert_not_called()


class TestAsyncRetryWithBackoff:
    async def test_success_first_try(self):
        @ah.async_retry_with_backoff(max_retries=3)
        async def f():
            return "ok"
        assert await f() == "ok"

    async def test_retry_then_success(self):
        calls = {"n": 0}

        @ah.async_retry_with_backoff(max_retries=3, base_delay=0.01)
        async def f():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("transient")
            return "ok"

        with patch.object(asyncio, "sleep", new=AsyncMock()) as sleep_mock:
            assert await f() == "ok"
        assert calls["n"] == 3
        assert sleep_mock.await_count == 2

    async def test_max_retries_exhausted_raises_last(self):
        @ah.async_retry_with_backoff(max_retries=2, base_delay=0.01)
        async def f():
            raise ValueError("always")

        with patch.object(asyncio, "sleep", new=AsyncMock()) as sleep_mock:
            with pytest.raises(ValueError, match="always"):
                await f()
        assert sleep_mock.await_count == 2

    async def test_delay_capped(self):
        @ah.async_retry_with_backoff(max_retries=1, base_delay=100, max_delay=5)
        async def f():
            raise ValueError("x")

        with patch.object(asyncio, "sleep", new=AsyncMock()) as sleep_mock:
            with pytest.raises(ValueError):
                await f()
        sleep_mock.assert_awaited_once_with(5)

    async def test_non_matching_exception_propagates(self):
        @ah.async_retry_with_backoff(max_retries=3, exceptions=(ValueError,))
        async def f():
            raise TypeError("not retried")

        with patch.object(asyncio, "sleep", new=AsyncMock()) as sleep_mock:
            with pytest.raises(TypeError, match="not retried"):
                await f()
        sleep_mock.assert_not_awaited()


class TestAutoHealingEngine:
    def test_get_circuit_breaker_creates_and_caches(self):
        engine = ah.AutoHealingEngine()
        cb = engine.get_circuit_breaker("salesforce")
        assert isinstance(cb, ah.CircuitBreaker)
        assert engine.get_circuit_breaker("salesforce") is cb
        assert engine.get_circuit_breaker("slack") is not cb

    def test_get_service_status(self):
        engine = ah.AutoHealingEngine()
        assert engine.get_service_status() == {}
        cb = engine.get_circuit_breaker("svc")
        for _ in range(5):
            cb.record_failure()
        status = engine.get_service_status()
        assert status["svc"]["state"] == "OPEN"
        assert status["svc"]["failure_count"] == 5
        assert status["svc"]["last_failure"] is not None
        cb.reset()
        status = engine.get_service_status()
        assert status["svc"]["last_failure"] is None

    def test_global_engine_instance(self):
        assert isinstance(ah.auto_healing_engine, ah.AutoHealingEngine)


# ===========================================================================
# core.agent_communication
# ===========================================================================


class _FakePubSub:
    """Redis pubsub stand-in whose listen() is a finite async generator."""

    def __init__(self, messages, final_error=None):
        self.messages = list(messages)
        self.final_error = final_error
        self.closed = False
        self.psubscribed = []

    async def psubscribe(self, pattern):
        self.psubscribed.append(pattern)

    def listen(self):
        return self._agen()

    async def _agen(self):
        for m in self.messages:
            yield m
        if self.final_error is not None:
            raise self.final_error
        raise asyncio.CancelledError

    async def close(self):
        self.closed = True


class TestAgentEventBus:
    def test_init_defaults_without_redis_url(self):
        with patch.dict(os.environ, {}, clear=True):
            bus = ac.AgentEventBus()
        assert bus._redis_url is None
        assert bus._redis_enabled is False
        assert bus._subscribers == {}
        assert "global" in bus._topics

    def test_init_with_redis_url(self):
        with patch.dict(os.environ, {}, clear=True):
            bus = ac.AgentEventBus(redis_url="redis://localhost:6379")
        assert bus._redis_url == "redis://localhost:6379"
        assert bus._redis_enabled is True and ac.REDIS_AVAILABLE is True

    async def test_subscribe_new_and_existing_agent_default_topics(self):
        bus = ac.AgentEventBus()
        ws1, ws2 = MagicMock(), MagicMock()
        await bus.subscribe("a1", ws1)
        assert bus._subscribers["a1"] == {ws1}
        assert bus._topics["global"] == {"a1"}
        await bus.subscribe("a1", ws2)
        assert bus._subscribers["a1"] == {ws1, ws2}

    async def test_subscribe_custom_topics_creates_topic(self):
        bus = ac.AgentEventBus()
        await bus.subscribe("a1", MagicMock(), topics=["category:sales", "alerts"])
        assert bus._topics["category:sales"] == {"a1"}
        assert bus._topics["alerts"] == {"a1"}
        assert bus._topics["global"] == set()

    async def test_unsubscribe_last_connection_cleans_topics(self):
        bus = ac.AgentEventBus()
        ws = MagicMock()
        await bus.subscribe("a1", ws, topics=["global", "alerts"])
        await bus.unsubscribe("a1", ws)
        assert "a1" not in bus._subscribers
        assert "a1" not in bus._topics["global"]
        assert "a1" not in bus._topics["alerts"]

    async def test_unsubscribe_keeps_other_connections(self):
        bus = ac.AgentEventBus()
        ws1, ws2 = MagicMock(), MagicMock()
        await bus.subscribe("a1", ws1)
        await bus.subscribe("a1", ws2)
        await bus.unsubscribe("a1", ws1)
        assert bus._subscribers["a1"] == {ws2}

    async def test_unsubscribe_unknown_agent(self):
        bus = ac.AgentEventBus()
        await bus.unsubscribe("ghost", MagicMock())

    async def test_publish_default_topic(self):
        bus = ac.AgentEventBus()
        ws = MagicMock()
        ws.send_json = AsyncMock()
        await bus.subscribe("a1", ws)
        await bus.publish({"type": "status_update"})
        ws.send_json.assert_awaited_once_with({"type": "status_update"})

    async def test_publish_multi_topic_dedup(self):
        bus = ac.AgentEventBus()
        ws = MagicMock()
        ws.send_json = AsyncMock()
        await bus.subscribe("a1", ws, topics=["global", "alerts"])
        await bus.publish({"type": "alert"}, ["global", "alerts"])
        assert ws.send_json.await_count == 1

    async def test_publish_ignores_unknown_topic(self):
        bus = ac.AgentEventBus()
        ws = MagicMock()
        ws.send_json = AsyncMock()
        await bus.subscribe("a1", ws)
        await bus.publish({"type": "x"}, ["nonexistent"])
        ws.send_json.assert_not_awaited()

    async def test_publish_dead_connection_unsubscribed(self):
        bus = ac.AgentEventBus()
        ws = MagicMock()
        ws.send_json = AsyncMock(side_effect=ConnectionError("socket closed"))
        await bus.subscribe("a1", ws)
        await bus.publish({"type": "x"})
        assert "a1" not in bus._subscribers

    async def test_publish_via_redis(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        fake_redis = AsyncMock()
        with patch.object(ac.redis, "from_url", new=AsyncMock(return_value=fake_redis)):
            await bus.publish({"type": "x"}, ["global"])
        fake_redis.publish.assert_awaited_once_with("agent_events:global", json.dumps({"topics": ["global"], "event": {"type": "x"}}))

    async def test_publish_redis_failure_falls_back_to_memory(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        bus._redis = AsyncMock()
        bus._redis.publish.side_effect = Exception("redis down")
        ws = MagicMock()
        ws.send_json = AsyncMock()
        await bus.subscribe("a1", ws)
        await bus.publish({"type": "x"}, ["global"])
        ws.send_json.assert_awaited_once()

    async def test_ensure_redis_success(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        fake_redis = AsyncMock()
        fake_redis.pubsub.return_value = AsyncMock()
        with patch.object(ac.redis, "from_url", new=AsyncMock(return_value=fake_redis)):
            await bus._ensure_redis()
        assert bus._redis is fake_redis
        assert bus._pubsub is not None

    async def test_ensure_redis_failure_disables_redis(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        with patch.object(ac.redis, "from_url", new=AsyncMock(side_effect=Exception("no conn"))):
            await bus._ensure_redis()
        assert bus._redis_enabled is False

    async def test_broadcast_post_alert(self):
        bus = ac.AgentEventBus()
        with patch.object(bus, "publish", new=AsyncMock()) as publish:
            await bus.broadcast_post({"sender_id": "a1", "post_type": "alert", "data": 1})
        publish.assert_awaited_once()
        assert publish.await_args.args[1] == ["global", "agent:a1", "alerts"]

    async def test_broadcast_post_question_with_category(self):
        bus = ac.AgentEventBus()
        with patch.object(bus, "publish", new=AsyncMock()) as publish:
            await bus.broadcast_post({
                "sender_id": "a1", "post_type": "question", "sender_category": "marketing",
            })
        assert publish.await_args.args[1] == ["global", "agent:a1", "category:marketing"]

    async def test_broadcast_post_question_without_category(self):
        bus = ac.AgentEventBus()
        with patch.object(bus, "publish", new=AsyncMock()) as publish:
            await bus.broadcast_post({"sender_id": "a1", "post_type": "question"})
        assert publish.await_args.args[1] == ["global", "agent:a1"]

    async def test_broadcast_post_plain(self):
        bus = ac.AgentEventBus()
        with patch.object(bus, "publish", new=AsyncMock()) as publish:
            await bus.broadcast_post({"sender_id": "a1"})
        assert publish.await_args.args[1] == ["global", "agent:a1"]

    async def test_subscribe_to_redis_not_enabled(self):
        bus = ac.AgentEventBus()
        await bus.subscribe_to_redis()
        assert bus._redis_listener_task is None

    async def test_subscribe_to_redis_pubsub_missing(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        bus._redis = AsyncMock()
        bus._pubsub = None
        await bus.subscribe_to_redis()
        assert bus._redis_listener_task is None

    async def _drain_listener(self, bus, rounds=25):
        for _ in range(rounds):
            await asyncio.sleep(0)

    async def test_redis_listener_broadcasts_and_cancels(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        bus._redis = AsyncMock()
        msg = json.dumps({"event": {"type": "agent_post", "data": "hi"}, "topics": ["global"]})
        bus._pubsub = _FakePubSub([
            {"type": "subscribe"},  # non-pmessage: skipped
            {"type": "pmessage", "pattern": "agent_events:*", "channel": "agent_events:global", "data": msg},
        ])
        ws = MagicMock()
        ws.send_json = AsyncMock()
        await bus.subscribe("a1", ws)
        await bus.subscribe_to_redis()
        assert bus._pubsub.psubscribed == ["agent_events:*"]
        task = bus._redis_listener_task
        await self._drain_listener(bus)
        ws.send_json.assert_awaited_with({"type": "agent_post", "data": "hi"})
        await task  # listener consumes the CancelledError from the generator
        assert task.done()

    async def test_redis_listener_send_failure_unsubscribes(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        bus._redis = AsyncMock()
        dead_msg = json.dumps({"event": {"type": "x"}, "topics": ["global"]})
        alive_msg = json.dumps({"event": {"type": "alive"}, "topics": ["global"]})
        bus._pubsub = _FakePubSub([
            {"type": "pmessage", "data": dead_msg},
            {"type": "pmessage", "data": alive_msg},
        ])
        dead_ws = MagicMock()
        dead_ws.send_json = AsyncMock(side_effect=ConnectionError("boom"))
        alive_ws = MagicMock()
        alive_ws.send_json = AsyncMock()
        await bus.subscribe("a1", dead_ws)
        await bus.subscribe("a2", alive_ws)
        await bus.subscribe_to_redis()
        task = bus._redis_listener_task
        await self._drain_listener(bus)
        assert "a1" not in bus._subscribers
        assert "a2" in bus._subscribers
        # The dead connection must not abort processing of later messages.
        alive_ws.send_json.assert_awaited_with({"type": "alive"})
        await task
        assert task.done()

    async def test_redis_listener_invalid_json_logs_and_continues(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        bus._redis = AsyncMock()
        bus._pubsub = _FakePubSub([
            {"type": "pmessage", "data": "{not json"},
            {"type": "pmessage", "data": json.dumps({"event": {"type": "ok"}, "topics": ["global"]})},
        ])
        ws = MagicMock()
        ws.send_json = AsyncMock()
        await bus.subscribe("a1", ws)
        await bus.subscribe_to_redis()
        task = bus._redis_listener_task
        await self._drain_listener(bus)
        ws.send_json.assert_awaited_with({"type": "ok"})
        await task
        assert task.done()

    async def test_redis_listener_generic_error_ends_task(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        bus._redis = AsyncMock()
        bus._pubsub = _FakePubSub(
            [{"type": "pmessage", "data": json.dumps({"event": {"type": "x"}, "topics": ["global"]})}],
            final_error=RuntimeError("listener exploded"),
        )
        ws = MagicMock()
        ws.send_json = AsyncMock()
        await bus.subscribe("a1", ws)
        await bus.subscribe_to_redis()
        task = bus._redis_listener_task
        await self._drain_listener(bus)
        assert not task.cancelled()
        await task  # completes normally (error consumed by listener)

    async def test_close_redis_with_resources(self):
        bus = ac.AgentEventBus(redis_url="redis://x")
        bus._redis_enabled = True
        bus._redis_listener_task = asyncio.create_task(asyncio.sleep(0))
        pubsub = _FakePubSub([])
        redis_mock = AsyncMock()
        bus._pubsub = pubsub
        bus._redis = redis_mock
        await bus.close_redis()
        assert pubsub.closed is True
        redis_mock.close.assert_awaited_once()

    async def test_close_redis_empty(self):
        bus = ac.AgentEventBus()
        await bus.close_redis()

    def test_redis_unavailable_fallback(self):
        """Reload the module with redis shadowed to exercise the ImportError branch."""
        with patch.dict(sys.modules, {"redis": None}):
            mod = importlib.reload(ac)
            assert mod.REDIS_AVAILABLE is False
            assert mod.AgentEventBus(redis_url="redis://x")._redis_enabled is False
        del sys.modules["redis"]
        mod = importlib.reload(ac)
        assert mod.REDIS_AVAILABLE is True


# ===========================================================================
# core.agent_request_manager
# ===========================================================================


def _chain(first_result=None, all_result=None):
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = first_result
    q.all.return_value = all_result
    return q


@pytest.fixture
def arm_db():
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.query = Mock()
    return db


class TestAgentRequestManager:
    def test_get_manager_helper(self, arm_db):
        mgr = get_agent_request_manager(arm_db)
        assert isinstance(mgr, AgentRequestManager)
        assert mgr.db is arm_db

    async def test_create_permission_request_success(self, arm_db):
        agent = Mock()
        agent.name = "Sales Agent"
        arm_db.query.side_effect = [_chain(first_result=agent)]
        with patch.object(arm.ws_manager, "broadcast", new_callable=AsyncMock) as mb:
            mgr = AgentRequestManager(arm_db)
            rid = await mgr.create_permission_request(
                user_id="u1", agent_id="a1", title="Read access",
                permission="read:data", context={"op": "x"}, urgency="high",
            )
        assert isinstance(rid, str) and rid
        mb.assert_awaited_once()
        channel, payload = mb.await_args.args
        assert channel == "user:u1"
        assert payload["type"] == "agent:request"
        data = payload["data"]
        assert data["request_type"] == "permission"
        assert data["governance"]["requires_signature"] is False
        assert data["suggested_option"] == 1
        assert data["agent_name"] == "Sales Agent"

    async def test_create_permission_request_blocking_requires_signature(self, arm_db):
        arm_db.query.side_effect = [_chain(first_result=None)]
        with patch.object(arm.ws_manager, "broadcast", new_callable=AsyncMock) as mb:
            mgr = AgentRequestManager(arm_db)
            rid = await mgr.create_permission_request(
                user_id="u1", agent_id="missing", title="T", permission="p",
                context={}, urgency="blocking", expires_in=120,
            )
        assert rid
        _, payload = mb.await_args.args
        assert payload["data"]["agent_name"] == "Agent"
        assert payload["data"]["governance"]["requires_signature"] is True

    async def test_create_permission_request_unknown_urgency_default_timeout(self, arm_db):
        arm_db.query.side_effect = [_chain(first_result=None)]
        with patch.object(arm.ws_manager, "broadcast", new_callable=AsyncMock):
            mgr = AgentRequestManager(arm_db)
            await mgr.create_permission_request(
                user_id="u1", agent_id="a1", title="T", permission="p",
                context={}, urgency="weird",
            )
        assert arm_db.add.call_count == 2
        assert arm_db.commit.call_count == 2

    async def test_create_permission_request_disabled(self, arm_db):
        with patch.object(arm, "AGENT_REQUESTS_ENABLED", False), \
             patch.object(arm.ws_manager, "broadcast", new_callable=AsyncMock) as mb:
            mgr = AgentRequestManager(arm_db)
            rid = await mgr.create_permission_request("u1", "a1", "T", "p", {})
        assert rid
        mb.assert_not_awaited()
        arm_db.add.assert_not_called()

    async def test_create_permission_request_exception_returns_uuid(self, arm_db):
        arm_db.query.side_effect = RuntimeError("db down")
        with patch.object(arm.ws_manager, "broadcast", new_callable=AsyncMock):
            mgr = AgentRequestManager(arm_db)
            rid = await mgr.create_permission_request("u1", "a1", "T", "p", {})
        assert rid

    async def test_create_decision_request_success(self, arm_db):
        agent = Mock()
        agent.name = "Analyst"
        arm_db.query.side_effect = [_chain(first_result=agent)]
        with patch.object(arm.ws_manager, "broadcast", new_callable=AsyncMock) as mb:
            mgr = AgentRequestManager(arm_db)
            rid = await mgr.create_decision_request(
                user_id="u1", agent_id="a1", title="Pick a vendor",
                explanation="Need input", options=[{"label": "A"}],
                context={}, urgency="low", suggested_option=1, expires_in=300,
            )
        assert rid
        _, payload = mb.await_args.args
        data = payload["data"]
        assert data["request_type"] == "decision"
        assert data["suggested_option"] == 1
        assert data["governance"]["requires_signature"] is False
        assert data["agent_name"] == "Analyst"

    async def test_create_decision_request_disabled(self, arm_db):
        with patch.object(arm, "AGENT_REQUESTS_ENABLED", False):
            mgr = AgentRequestManager(arm_db)
            rid = await mgr.create_decision_request("u1", "a1", "T", "E", [{}], {})
        assert rid

    async def test_create_decision_request_exception(self, arm_db):
        arm_db.query.side_effect = RuntimeError("db down")
        mgr = AgentRequestManager(arm_db)
        rid = await mgr.create_decision_request("u1", "a1", "T", "E", [{}], {})
        assert rid

    async def test_wait_for_response_not_found(self, arm_db):
        mgr = AgentRequestManager(arm_db)
        assert await mgr.wait_for_response("nope") is None

    async def test_wait_for_response_aware_expiry_returns_response(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        log.user_response = {"action": "approve"}
        resp_log = MagicMock(user_response={"action": "approve"})
        arm_db.query.side_effect = [_chain(first_result=log), _chain(first_result=resp_log)]
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r1"] = asyncio.Event()
        mgr._pending_requests["r1"].set()
        result = await mgr.wait_for_response("r1")
        assert result == {"action": "approve"}
        assert "r1" not in mgr._pending_requests

    async def test_wait_for_response_naive_expiry(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now() + timedelta(seconds=60)
        arm_db.query.side_effect = [_chain(first_result=log), _chain(first_result=None)]
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r2"] = asyncio.Event()
        mgr._pending_requests["r2"].set()
        assert await mgr.wait_for_response("r2") is None

    async def test_wait_for_response_no_log_default_timeout(self, arm_db):
        arm_db.query.side_effect = [_chain(first_result=None), _chain(first_result=None)]
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r3"] = asyncio.Event()
        mgr._pending_requests["r3"].set()
        assert await mgr.wait_for_response("r3") is None

    async def test_wait_for_response_timeout_revokes(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        arm_db.query.side_effect = [_chain(first_result=log), _chain(first_result=log)]
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r4"] = asyncio.Event()
        result = await mgr.wait_for_response("r4")
        assert result is None
        assert log.revoked is True

    async def test_wait_for_response_timeout_no_log(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        arm_db.query.side_effect = [_chain(first_result=log), _chain(first_result=None)]
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r5"] = asyncio.Event()
        assert await mgr.wait_for_response("r5") is None

    async def test_wait_for_response_exception(self, arm_db):
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r6"] = asyncio.Event()
        with patch.object(asyncio, "wait_for", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await mgr.wait_for_response("r6") is None

    async def test_handle_response_disabled(self, arm_db):
        with patch.object(arm, "AGENT_REQUESTS_ENABLED", False):
            mgr = AgentRequestManager(arm_db)
            await mgr.handle_response("u1", "r1", {})
        arm_db.query.assert_not_called()

    async def test_handle_response_not_found(self, arm_db):
        arm_db.query.side_effect = [_chain(first_result=None)]
        mgr = AgentRequestManager(arm_db)
        await mgr.handle_response("u1", "r1", {})
        arm_db.commit.assert_not_called()

    async def test_handle_response_expired_naive(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now() - timedelta(seconds=10)
        arm_db.query.side_effect = [_chain(first_result=log)]
        mgr = AgentRequestManager(arm_db)
        await mgr.handle_response("u1", "r1", {})
        arm_db.commit.assert_not_called()

    async def test_handle_response_expired_aware(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        arm_db.query.side_effect = [_chain(first_result=log)]
        mgr = AgentRequestManager(arm_db)
        await mgr.handle_response("u1", "r1", {})
        arm_db.commit.assert_not_called()

    async def test_handle_response_success_with_naive_created_at(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        log.created_at = datetime.now() - timedelta(seconds=5)
        log.agent_id = "a1"
        arm_db.query.side_effect = [_chain(first_result=log)]
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r1"] = asyncio.Event()
        await mgr.handle_response("u1", "r1", {"action": "approve"})
        assert log.user_response == {"action": "approve"}
        assert log.response_time_seconds is not None
        assert mgr._pending_requests["r1"].is_set()
        assert arm_db.commit.call_count == 2

    async def test_handle_response_success_no_created_at(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        log.created_at = None
        log.agent_id = "a1"
        arm_db.query.side_effect = [_chain(first_result=log)]
        mgr = AgentRequestManager(arm_db)
        await mgr.handle_response("u1", "r1", {"action": "deny"})
        assert log.response_time_seconds is None

    async def test_handle_response_exception(self, arm_db):
        log = MagicMock()
        log.expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        log.created_at = datetime.now(timezone.utc)
        arm_db.query.side_effect = [_chain(first_result=log)]
        arm_db.commit.side_effect = RuntimeError("commit fail")
        mgr = AgentRequestManager(arm_db)
        await mgr.handle_response("u1", "r1", {})  # must not raise

    async def test_revoke_request_found(self, arm_db):
        log = MagicMock()
        arm_db.query.side_effect = [_chain(first_result=log)]
        mgr = AgentRequestManager(arm_db)
        mgr._pending_requests["r1"] = asyncio.Event()
        await mgr.revoke_request("r1")
        assert log.revoked is True
        assert mgr._pending_requests["r1"].is_set()

    async def test_revoke_request_not_found(self, arm_db):
        arm_db.query.side_effect = [_chain(first_result=None)]
        mgr = AgentRequestManager(arm_db)
        await mgr.revoke_request("r1")
        arm_db.commit.assert_not_called()

    async def test_revoke_request_exception(self, arm_db):
        arm_db.query.side_effect = RuntimeError("db down")
        mgr = AgentRequestManager(arm_db)
        await mgr.revoke_request("r1")

    async def test_create_audit_success(self, arm_db):
        mgr = AgentRequestManager(arm_db)
        await mgr._create_audit(agent_id="a1", user_id="u1", request_id="r1", action="test", metadata={"k": "v"})
        assert arm_db.add.call_count == 1
        assert arm_db.commit.call_count == 1

    async def test_create_audit_failure_rolls_back(self, arm_db):
        arm_db.commit.side_effect = RuntimeError("boom")
        mgr = AgentRequestManager(arm_db)
        await mgr._create_audit(agent_id="a1", user_id="u1", request_id="r1", action="test")
        arm_db.rollback.assert_called_once()

    async def test_create_permission_request_audit_failure_still_returns_id(self, arm_db):
        arm_db.query.side_effect = [_chain(first_result=None)]
        with patch.object(arm.ws_manager, "broadcast", new_callable=AsyncMock):
            arm_db.commit.side_effect = [None, RuntimeError("audit boom")]
            mgr = AgentRequestManager(arm_db)
            rid = await mgr.create_permission_request("u1", "a1", "T", "p", {})
        assert rid


# ===========================================================================
# core.agent_promotion_service
# ===========================================================================


def _agent(status, confidence=0.5, name="Agent", agent_id="a1"):
    a = MagicMock()
    a.id = agent_id
    a.name = name
    a.status = status
    a.confidence_score = confidence
    return a


class TestAgentPromotionService:
    def _svc(self, db, feedback_summary=None, exec_agents=None):
        service = AgentPromotionService(db)
        if feedback_summary is not None:
            service.feedback_analytics.get_agent_feedback_summary = Mock(return_value=feedback_summary)
        if exec_agents is not None:
            pass
        return service

    def test_get_promotion_suggestions_sorted_and_limited(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = [
            _agent(AgentStatus.INTERN.value), _agent(AgentStatus.SUPERVISED.value, agent_id="a2"),
            _agent(AgentStatus.INTERN.value, agent_id="a3"),
        ]
        svc = AgentPromotionService(db)
        ready1 = {"ready_for_promotion": True, "readiness_score": 0.9}
        ready2 = {"ready_for_promotion": True, "readiness_score": 0.8}
        not_ready = {"ready_for_promotion": False, "readiness_score": 0.5}
        with patch.object(svc, "_evaluate_agent_for_promotion", side_effect=[ready1, not_ready, ready2]):
            suggestions = svc.get_promotion_suggestions()
        assert suggestions == [ready1, ready2]

    def test_get_promotion_suggestions_limit(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = [
            _agent(AgentStatus.INTERN.value, agent_id="a1"),
            _agent(AgentStatus.SUPERVISED.value, agent_id="a2"),
        ]
        svc = AgentPromotionService(db)
        with patch.object(svc, "_evaluate_agent_for_promotion", side_effect=[
            {"ready_for_promotion": True, "readiness_score": 0.9},
            {"ready_for_promotion": True, "readiness_score": 0.8},
        ]):
            suggestions = svc.get_promotion_suggestions(limit=1)
        assert len(suggestions) == 1
        assert suggestions[0]["readiness_score"] == 0.9

    def test_is_agent_ready_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = AgentPromotionService(db)
        result = svc.is_agent_ready_for_promotion("missing")
        assert result == {"ready": False, "reason": "Agent not found"}

    def test_is_agent_ready_intern_auto_detects_supervised(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(AgentStatus.INTERN.value)
        svc = AgentPromotionService(db)
        with patch.object(svc, "_evaluate_agent_for_promotion", return_value={"ready_for_promotion": True, "x": 1}) as ev:
            result = svc.is_agent_ready_for_promotion("a1")
        ev.assert_called_once()
        assert ev.call_args.args[1] == "SUPERVISED"
        assert result["ready"] is True
        assert result["x"] == 1

    def test_is_agent_ready_supervised_auto_detects_autonomous(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(AgentStatus.SUPERVISED.value)
        svc = AgentPromotionService(db)
        with patch.object(svc, "_evaluate_agent_for_promotion", return_value={"ready_for_promotion": False}) as ev:
            result = svc.is_agent_ready_for_promotion("a1")
        assert ev.call_args.args[1] == "AUTONOMOUS"
        assert result["ready"] is False

    def test_is_agent_ready_already_autonomous(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(AgentStatus.AUTONOMOUS.value)
        svc = AgentPromotionService(db)
        result = svc.is_agent_ready_for_promotion("a1")
        assert result["ready"] is False
        assert "already" in result["reason"]

    def test_is_agent_ready_explicit_target(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(AgentStatus.INTERN.value)
        svc = AgentPromotionService(db)
        with patch.object(svc, "_evaluate_agent_for_promotion", return_value={"ready_for_promotion": True}) as ev:
            result = svc.is_agent_ready_for_promotion("a1", target_status="AUTONOMOUS")
        assert ev.call_args.args[1] == "AUTONOMOUS"
        assert result["ready"] is True

    def test_evaluate_already_at_level(self):
        db = Mock()
        svc = AgentPromotionService(db)
        result = svc._evaluate_agent_for_promotion(_agent(AgentStatus.AUTONOMOUS.value))
        assert result["ready_for_promotion"] is False
        assert result["target_status"] is None

    def test_evaluate_no_feedback_data(self):
        db = Mock()
        svc = AgentPromotionService(db)
        svc.feedback_analytics.get_agent_feedback_summary = Mock(side_effect=ValueError("no feedback"))
        result = svc._evaluate_agent_for_promotion(_agent(AgentStatus.INTERN.value))
        assert result["ready_for_promotion"] is False
        assert result["reason"] == "No feedback data available"
        assert result["criteria_failed"]["feedback_count"] == "Insufficient feedback data"

    def test_evaluate_all_criteria_met_supervised(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(status="completed"), MagicMock(status="completed"),
        ]
        svc = self._svc(db, feedback_summary={
            "total_feedback": 12, "positive_count": 12, "average_rating": 4.6,
            "feedback_types": {"correction": 0},
        })
        result = svc._evaluate_agent_for_promotion(
            _agent(AgentStatus.INTERN.value, confidence=0.9), "SUPERVISED")
        assert result["ready_for_promotion"] is True
        assert result["readiness_score"] == 1.0
        assert set(result["criteria_met"]) == {
            "feedback_count", "positive_ratio", "average_rating",
            "correction_count", "confidence_score", "execution_success_rate",
        }

    def test_evaluate_all_criteria_failed(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = [MagicMock(status="failed")] * 4
        svc = self._svc(db, feedback_summary={
            "total_feedback": 2, "positive_count": 0, "average_rating": 1.0,
            "feedback_types": {"correction": 10},
        })
        result = svc._evaluate_agent_for_promotion(
            _agent(AgentStatus.INTERN.value, confidence=0.1), "SUPERVISED")
        assert result["ready_for_promotion"] is False
        assert set(result["criteria_failed"]) == {
            "feedback_count", "positive_ratio", "average_rating",
            "correction_count", "confidence_score", "execution_success_rate",
        }
        assert result["readiness_score"] == 0.0

    def test_evaluate_avg_none_and_no_executions(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = self._svc(db, feedback_summary={
            "total_feedback": 10, "positive_count": 6, "average_rating": None,
            "feedback_types": {"correction": 3},
        })
        result = svc._evaluate_agent_for_promotion(
            _agent(AgentStatus.INTERN.value, confidence=0.8), "SUPERVISED")
        assert "average_rating" not in result["criteria_met"]
        assert "average_rating" not in result["criteria_failed"]
        assert "execution_success_rate" not in result["criteria_met"]
        # 3 of 6 criteria met (feedback, corrections, confidence); avg+executions
        # still count toward the denominator.
        assert result["readiness_score"] == pytest.approx(0.5)

    def test_evaluate_zero_total_feedback_zero_ratio(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = self._svc(db, feedback_summary={
            "total_feedback": 0, "positive_count": 0, "average_rating": None,
            "feedback_types": {},
        })
        result = svc._evaluate_agent_for_promotion(
            _agent(AgentStatus.INTERN.value, confidence=0.9), "SUPERVISED")
        assert "positive_ratio" in result["criteria_failed"]
        assert "correction_count" in result["criteria_met"]

    def test_evaluate_autonomous_thresholds_met(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = [MagicMock(status="completed")] * 10
        svc = self._svc(db, feedback_summary={
            "total_feedback": 10, "positive_count": 10, "average_rating": 4.9,
            "feedback_types": {"correction": 0},
        })
        result = svc._evaluate_agent_for_promotion(
            _agent(AgentStatus.SUPERVISED.value, confidence=0.95), "AUTONOMOUS")
        assert result["ready_for_promotion"] is True
        assert result["readiness_score"] == 1.0

    def test_evaluate_supervised_auto_detects_autonomous(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = self._svc(db, feedback_summary={
            "total_feedback": 10, "positive_count": 10, "average_rating": 4.9,
            "feedback_types": {"correction": 0},
        })
        result = svc._evaluate_agent_for_promotion(_agent(AgentStatus.SUPERVISED.value, confidence=0.95))
        assert result["target_status"] == "AUTONOMOUS"
        assert result["ready_for_promotion"] is True

    def test_evaluate_execution_success_rate_fails(self):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(status="completed"), MagicMock(status="failed"),
        ]
        svc = self._svc(db, feedback_summary={
            "total_feedback": 12, "positive_count": 12, "average_rating": 4.6,
            "feedback_types": {"correction": 0},
        })
        result = svc._evaluate_agent_for_promotion(
            _agent(AgentStatus.INTERN.value, confidence=0.9), "SUPERVISED")
        assert "execution_success_rate" in result["criteria_failed"]
        # 5 of 6 criteria met still crosses the 0.8 readiness bar.
        assert result["ready_for_promotion"] is True
        assert result["readiness_score"] == pytest.approx(5 / 6)

    def test_get_promotion_path_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = AgentPromotionService(db)
        assert svc.get_promotion_path("missing") == {"error": "Agent not found"}

    def test_get_promotion_path_student_full_path(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(
            AgentStatus.STUDENT.value, confidence=0.6, name="Newbie")
        svc = AgentPromotionService(db)
        eval_sup = {"readiness_score": 0.7, "ready_for_promotion": False, "criteria_met": {"a": 1}, "criteria_failed": {"b": 2}}
        eval_auto = {"readiness_score": 0.9, "ready_for_promotion": True, "criteria_met": {"c": 3}, "criteria_failed": {}}
        with patch.object(svc, "_evaluate_agent_for_promotion", side_effect=[eval_sup, eval_auto]) as ev:
            result = svc.get_promotion_path("a1")
        assert ev.call_count == 2
        path = result["promotion_path"]
        assert len(path) == 3
        assert path[0]["from"] == "STUDENT" and path[0]["to"] == "INTERN"
        assert path[1]["from"] == "INTERN" and path[1]["to"] == "SUPERVISED"
        assert path[2]["from"] == "SUPERVISED" and path[2]["to"] == "AUTONOMOUS"
        assert path[1]["current_progress"] == "70%"
        assert path[2]["ready"] is True

    def test_get_promotion_path_intern(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(AgentStatus.INTERN.value)
        svc = AgentPromotionService(db)
        with patch.object(svc, "_evaluate_agent_for_promotion", return_value={
            "readiness_score": 0.8, "ready_for_promotion": True, "criteria_met": {}, "criteria_failed": {},
        }) as ev:
            result = svc.get_promotion_path("a1")
        # INTERN qualifies for both the INTERN->SUPERVISED and SUPERVISED->AUTONOMOUS legs.
        assert ev.call_count == 2
        assert [p["to"] for p in result["promotion_path"]] == ["SUPERVISED", "AUTONOMOUS"]

    def test_get_promotion_path_supervised(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(AgentStatus.SUPERVISED.value)
        svc = AgentPromotionService(db)
        with patch.object(svc, "_evaluate_agent_for_promotion", return_value={
            "readiness_score": 0.5, "ready_for_promotion": False, "criteria_met": {}, "criteria_failed": {},
        }) as ev:
            result = svc.get_promotion_path("a1")
        assert ev.call_count == 1
        assert ev.call_args.args[1] == "AUTONOMOUS"
        assert [p["to"] for p in result["promotion_path"]] == ["AUTONOMOUS"]

    def test_get_promotion_path_autonomous_no_path(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = _agent(AgentStatus.AUTONOMOUS.value)
        svc = AgentPromotionService(db)
        result = svc.get_promotion_path("a1")
        assert result["promotion_path"] == []

    def test_criteria_constants(self):
        assert PromotionCriteria.MIN_FEEDBACK_COUNT == 10
        assert PromotionCriteria.MIN_DAYS_AT_LEVEL == {"INTERN": 7, "SUPERVISED": 14}


# ===========================================================================
# core.ai_workflow_optimization_endpoints
# ===========================================================================


def _rec(rid="r1", opt_type=OptimizationType.PERFORMANCE, impact=ImpactLevel.HIGH, effort="medium"):
    return OptimizationRecommendation(
        id=rid, type=opt_type, title=f"Title {rid}", description="desc",
        impact_level=impact, estimated_improvement={"execution_time": 40},
        implementation_effort=effort, steps=["s1"], prerequisites=["p1"],
        risks=["r1"], confidence_score=85.0,
    )


def _analysis(recs=None, failure_points=None, bottlenecks=None, timestamp=None):
    return WorkflowAnalysis(
        workflow_id="wf-1", workflow_name="Onboarding", total_nodes=3, total_edges=2,
        integrations_used=["salesforce"], complexity_score=40.0, estimated_execution_time=12.0,
        failure_points=list(failure_points or []),
        bottlenecks=list(bottlenecks or []),
        optimization_opportunities=list(recs or []),
        analysis_timestamp=timestamp or datetime.now(timezone.utc),
    )


@pytest.fixture
def optimizer():
    return MagicMock()


@pytest.fixture
def client(optimizer):
    app = FastAPI()
    app.include_router(awe.router)
    app.dependency_overrides[awe.get_ai_workflow_optimizer] = lambda: optimizer
    return TestClient(app)


class TestWorkflowAnalyze:
    def test_analyze_success(self, client, optimizer):
        optimizer.analyze_workflow = AsyncMock(return_value=_analysis(
            recs=[_rec(f"r{i}") for i in range(7)],
            failure_points=[{"issues": ["no error handling"], "risk_level": "high"}],
        ))
        resp = client.post("/api/v1/workflows/analyze", json={
            "workflow_data": {"id": "wf-1", "nodes": [], "edges": []},
            "performance_metrics": {"success_rate": 0.9},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["analysis"]["workflow_id"] == "wf-1"
        assert body["analysis"]["metrics"]["total_nodes"] == 3
        assert body["analysis"]["risk_assessment"]["risk_level"] == "high"
        assert body["analysis"]["optimization_opportunities"] == 7
        assert len(body["analysis"]["top_recommendations"]) == 5
        assert body["analysis"]["top_recommendations"][0]["type"] == "performance"
        assert body["analysis"]["top_recommendations"][0]["impact_level"] == "high"

    def test_analyze_no_recommendations(self, client, optimizer):
        optimizer.analyze_workflow = AsyncMock(return_value=_analysis())
        resp = client.post("/api/v1/workflows/analyze", json={"workflow_data": {}})
        assert resp.status_code == 200
        assert resp.json()["analysis"]["top_recommendations"] == []

    def test_analyze_error_returns_500(self, client, optimizer):
        optimizer.analyze_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/v1/workflows/analyze", json={"workflow_data": {}})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestOptimizationPlan:
    def test_plan_success(self, client, optimizer):
        optimizer.optimize_workflow_plan = AsyncMock(return_value={
            "optimization_plan": {"goals": ["performance"], "phases": []},
            "workflow_analysis": {
                "workflow_id": "wf-1", "workflow_name": "Onboarding",
                "complexity_score": 40.0, "failure_points": [{"x": 1}],
                "optimization_opportunities": [_rec(opt_type=OptimizationType.COST, impact=ImpactLevel.MEDIUM)],
            },
            "generated_at": "2026-08-14T00:00:00+00:00",
        })
        resp = client.post("/api/v1/workflows/optimization-plan", json={
            "workflow_data": {"id": "wf-1"},
            "optimization_goals": ["performance", "COST"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["workflow_summary"]["id"] == "wf-1"
        assert body["workflow_summary"]["current_issues"] == 1
        assert body["recommendations_by_type"]["cost"][0]["id"] == "r1"

    def test_plan_invalid_goal_400(self, client):
        resp = client.post("/api/v1/workflows/optimization-plan", json={
            "workflow_data": {}, "optimization_goals": ["not-a-goal"],
        })
        assert resp.status_code == 400
        assert "not-a-goal" in resp.json()["detail"]

    def test_plan_optimizer_error_500(self, client, optimizer):
        optimizer.optimize_workflow_plan = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/v1/workflows/optimization-plan", json={
            "workflow_data": {}, "optimization_goals": ["performance"],
        })
        assert resp.status_code == 500

    def test_plan_empty_goals(self, client, optimizer):
        optimizer.optimize_workflow_plan = AsyncMock(return_value={
            "optimization_plan": {}, "workflow_analysis": {
                "workflow_id": "w", "workflow_name": "n", "complexity_score": 1,
                "failure_points": [],
            }, "generated_at": "x",
        })
        resp = client.post("/api/v1/workflows/optimization-plan", json={
            "workflow_data": {}, "optimization_goals": [],
        })
        assert resp.status_code == 200


class TestWorkflowMonitor:
    def test_monitor_healthy(self, client, optimizer):
        optimizer.monitor_workflow_performance = AsyncMock(return_value={
            "health_score": 85, "urgent_recommendations": [], "identified_issues": [],
        })
        resp = client.post("/api/v1/workflows/wf-1/monitor", json={
            "workflow_id": "other", "metrics": {"success_rate": 0.95},
            "time_window_hours": 24,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["health_status"]["status"] == "healthy"
        assert body["monitoring_result"]["health_score"] == 85

    def test_monitor_warning(self, client, optimizer):
        optimizer.monitor_workflow_performance = AsyncMock(return_value={
            "health_score": 70, "urgent_recommendations": [], "identified_issues": [{"i": 1}],
        })
        resp = client.post("/api/v1/workflows/wf-1/monitor", json={
            "workflow_id": "wf-1", "metrics": {}, "time_window_hours": 24,
        })
        assert resp.json()["health_status"]["status"] == "warning"
        assert resp.json()["health_status"]["issues_detected"] == 1

    def test_monitor_critical(self, client, optimizer):
        optimizer.monitor_workflow_performance = AsyncMock(return_value={
            "health_score": 40, "urgent_recommendations": [{"r": 1}], "identified_issues": [],
        })
        resp = client.post("/api/v1/workflows/wf-1/monitor", json={
            "workflow_id": "wf-1", "metrics": {},
        })
        assert resp.json()["health_status"]["status"] == "critical"
        assert resp.json()["health_status"]["urgent_actions_needed"] == 1

    def test_monitor_error_500(self, client, optimizer):
        optimizer.monitor_workflow_performance = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/v1/workflows/wf-1/monitor", json={
            "workflow_id": "wf-1", "metrics": {},
        })
        assert resp.status_code == 500


class TestWorkflowRecommendations:
    def test_recommendations_no_filters(self, client):
        resp = client.get("/api/v1/workflows/wf-1/recommendations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["workflow_id"] == "wf-1"
        assert body["total_recommendations"] == 2
        assert body["filters_applied"] == {"type": None, "impact": None}

    def test_recommendations_type_filter(self, client):
        resp = client.get("/api/v1/workflows/wf-1/recommendations", params={"type_filter": "cost"})
        assert resp.status_code == 200
        body = resp.json()
        assert [r["id"] for r in body["recommendations"]] == ["ai_cost_optimization"]
        assert body["filters_applied"]["type"] == "cost"

    def test_recommendations_impact_filter(self, client):
        resp = client.get("/api/v1/workflows/wf-1/recommendations", params={"impact_filter": "high"})
        body = resp.json()
        assert [r["id"] for r in body["recommendations"]] == ["parallel_processing"]

    def test_recommendations_both_filters_no_match(self, client):
        resp = client.get(
            "/api/v1/workflows/wf-1/recommendations",
            params={"type_filter": "reliability", "impact_filter": "critical"},
        )
        assert resp.json()["recommendations"] == []


class TestOptimizationTypes:
    def test_optimization_types(self, client):
        resp = client.get("/api/v1/workflows/optimization-types")
        assert resp.status_code == 200
        types = resp.json()["optimization_types"]
        assert set(types) == {"performance", "cost", "reliability", "efficiency", "security", "scalability"}
        assert "focus_areas" in types["performance"]


class TestBatchAnalysis:
    def test_batch_too_many_400(self, client):
        resp = client.post("/api/v1/workflows/batch-analysis", json=[{} for _ in range(51)])
        assert resp.status_code == 400

    def test_batch_success_with_summary(self, client, optimizer):
        optimizer.analyze_workflow = AsyncMock(return_value=_analysis(
            recs=[_rec(), _rec("r2", opt_type=OptimizationType.COST, impact=ImpactLevel.MEDIUM)],
            failure_points=[{"issues": ["no error handling"]}, {"issues": ["no error handling"]}],
            bottlenecks=[{"type": "sequential_depth"}],
        ))
        resp = client.post("/api/v1/workflows/batch-analysis", json=[{"id": "wf-1"}, {"id": "wf-2"}])
        assert resp.status_code == 200
        body = resp.json()["batch_analysis"]
        assert body["summary"]["total_workflows"] == 2
        assert body["summary"]["total_recommendations"] == 4
        assert body["summary"]["common_issues"] == {"no error handling": 4}
        assert body["summary"]["optimization_priorities"] == {"performance": 2, "cost": 2}
        assert len(body["workflow_results"]) == 2
        assert body["workflow_results"][0]["top_priority"] == "performance"

    def test_batch_empty_list(self, client):
        resp = client.post("/api/v1/workflows/batch-analysis", json=[])
        assert resp.status_code == 200
        body = resp.json()["batch_analysis"]
        assert body["summary"]["total_workflows"] == 0
        assert body["workflow_results"] == []

    def test_batch_partial_failure(self, client, optimizer):
        optimizer.analyze_workflow = AsyncMock(side_effect=[_analysis(), RuntimeError("boom")])
        resp = client.post("/api/v1/workflows/batch-analysis", json=[{"id": "wf-1"}, {"id": "wf-2"}])
        assert resp.status_code == 200
        results = resp.json()["batch_analysis"]["workflow_results"]
        assert results[0]["workflow_id"] == "wf-1"
        assert results[1]["workflow_id"] == "wf-2"
        assert results[1]["error"] == "boom"

    def test_batch_no_recommendations_no_priority(self, client, optimizer):
        optimizer.analyze_workflow = AsyncMock(return_value=_analysis())
        resp = client.post("/api/v1/workflows/batch-analysis", json=[{"id": "wf-1"}])
        results = resp.json()["batch_analysis"]["workflow_results"]
        assert results[0]["top_priority"] is None


class TestOptimizationInsights:
    def test_insights(self, client):
        resp = client.get("/api/v1/workflows/optimization-insights", params={"time_range": "30d"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["time_range"] == "30d"
        assert body["insights"]["roi_analysis"]["total_automated_processes"] == 156

    def test_insights_default_range(self, client):
        resp = client.get("/api/v1/workflows/optimization-insights")
        assert resp.json()["time_range"] == "7d"


class TestImplementOptimization:
    def test_implement_success_runs_background(self, client, optimizer):
        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock, \
             patch("core.database.SessionLocal") as session_factory:
            resp = client.post(
                "/api/v1/workflows/wf-1/implement-optimization",
                json={"optimization_id": "parallel_processing"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["job_id"].startswith("opt_job_wf-1_parallel_processing_")
        assert body["status"] == "initiated"
        assert sleep_mock.await_count == 6
        assert session_factory.return_value.close.call_count == 1

    async def test_execute_optimization_implementation_error(self):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("no db")), \
             patch("asyncio.sleep", new=AsyncMock()):
            await _execute_optimization_implementation("job1", "wf-1", "opt-1")
        # must not raise; error logged

    async def test_implement_optimization_defensive_except(self):
        """Direct-call trigger for the bare except: FastAPI always injects a
        BackgroundTasks, so None can only occur on a malformed direct call."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await awe.implement_optimization(
                "wf-1", "opt-1", background_tasks=None, optimizer=Mock())
        assert exc.value.status_code == 500

    async def test_batch_analyze_defensive_except(self):
        """Direct-call trigger for the outer bare except: a non-iterable body
        fails len() before the per-workflow inner try runs."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await awe.batch_analyze_workflows(workflows=5, optimizer=Mock())
        assert exc.value.status_code == 500


class TestHelperFunctions:
    def test_risk_level_high_critical(self):
        analysis = _analysis(failure_points=[{"risk_level": "high", "issues": []}])
        assert _calculate_risk_level(analysis) == "high"

    def test_risk_level_high_many_issues(self):
        analysis = _analysis(
            failure_points=[{"risk_level": "low", "issues": []}] * 3,
            bottlenecks=[{"b": 1}] * 3,
        )
        assert _calculate_risk_level(analysis) == "high"

    def test_risk_level_medium(self):
        analysis = _analysis(failure_points=[{"risk_level": "low", "issues": []}] * 3)
        assert _calculate_risk_level(analysis) == "medium"

    def test_risk_level_low(self):
        analysis = _analysis(failure_points=[{"risk_level": "low", "issues": []}])
        assert _calculate_risk_level(analysis) == "low"

    def test_risk_level_empty(self):
        assert _calculate_risk_level(_analysis()) == "low"

    def test_group_recommendations_by_type(self):
        recs = [
            _rec("a", opt_type=OptimizationType.PERFORMANCE, impact=ImpactLevel.HIGH),
            _rec("b", opt_type=OptimizationType.PERFORMANCE, impact=ImpactLevel.MEDIUM),
            _rec("c", opt_type=OptimizationType.COST, impact=ImpactLevel.LOW),
        ]
        grouped = _group_recommendations_by_type(recs)
        assert sorted(grouped) == ["cost", "performance"]
        assert len(grouped["performance"]) == 2
        assert grouped["cost"][0]["id"] == "c"
        assert grouped["performance"][0]["impact_level"] == ImpactLevel.HIGH.value

    def test_group_recommendations_empty(self):
        assert _group_recommendations_by_type([]) == {}


# ===========================================================================
# core.agent_learning_enhanced
# ===========================================================================


def make_learning(db=None, world_model=None, continuous=None):
    with patch("core.agent_learning_enhanced.WorldModelService", return_value=world_model or Mock()) as wm, \
         patch("core.agent_learning_enhanced.ContinuousLearningService", return_value=continuous or Mock()) as cl:
        learning = AgentLearningEnhanced(db or Mock())
    return learning, wm, cl


def make_feedback(**overrides):
    fb = MagicMock()
    fb.thumbs_up_down = None
    fb.rating = None
    fb.feedback_type = None
    fb.agent_id = "a1"
    fb.agent_execution_id = None
    fb.input_context = "ctx"
    fb.user_correction = "corr"
    fb.ai_reasoning = "reason"
    fb.created_at = datetime.now()
    for k, v in overrides.items():
        setattr(fb, k, v)
    return fb


class TestAdjustConfidence:
    def test_thumbs_up_rating5(self):
        learning, _, _ = make_learning()
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(thumbs_up_down=True, rating=5), 0.5) == pytest.approx(0.65)

    def test_thumbs_down_rating1_correction(self):
        learning, _, _ = make_learning()
        assert learning.adjust_confidence_with_feedback(
            "a1", make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction"), 0.5) == pytest.approx(0.32)

    def test_no_thumbs_rating4(self):
        learning, _, _ = make_learning()
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(rating=4), 0.5) == pytest.approx(0.55)

    def test_rating3_rating2(self):
        learning, _, _ = make_learning()
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(rating=3), 0.5) == 0.5
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(rating=2), 0.5) == pytest.approx(0.45)

    def test_unknown_rating_ignored(self):
        learning, _, _ = make_learning()
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(rating=7), 0.5) == 0.5

    def test_clamp_upper_and_lower(self):
        learning, _, _ = make_learning()
        assert learning.adjust_confidence_with_feedback("a1", make_feedback(thumbs_up_down=True, rating=5), 0.99) == 1.0
        assert learning.adjust_confidence_with_feedback(
            "a1", make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction"), 0.01) == 0.0


class TestGetLearningSignals:
    def _db(self, feedback_list, learning_record=None):
        db = Mock()
        fb_q = Mock()
        fb_q.filter.return_value = fb_q
        fb_q.all.return_value = feedback_list
        lr_q = Mock()
        lr_q.filter.return_value = lr_q
        lr_q.first.return_value = learning_record
        db.query.side_effect = [fb_q, lr_q]
        return db

    def test_no_feedback_no_record(self):
        learning, _, _ = make_learning(db=self._db([]))
        result = learning.get_learning_signals("a1")
        assert result["total_feedback"] == 0
        assert result["learning_signals"] == []

    def test_no_feedback_aggregate_record(self):
        record = MagicMock(total_feedback=20, positive_feedback=15, parameters_json={"lr": 0.1})
        learning, _, _ = make_learning(db=self._db([], learning_record=record))
        result = learning.get_learning_signals("a1")
        assert result["total_feedback"] == 20
        assert result["positive_ratio"] == 0.75
        assert result["parameters"] == {"lr": 0.1}
        assert result["learning_signals"][0]["type"] == "info"

    def test_no_feedback_aggregate_zero_total(self):
        record = MagicMock(total_feedback=0, positive_feedback=0, parameters_json=None)
        learning, _, _ = make_learning(db=self._db([], learning_record=record))
        result = learning.get_learning_signals("a1")
        assert result["positive_ratio"] == 0
        assert result["parameters"] == {}

    def test_high_positive_ratio_strength_signals(self):
        fb = [
            make_feedback(thumbs_up_down=True),
            make_feedback(thumbs_up_down=True, rating=5),
            make_feedback(thumbs_up_down=False, rating=5, feedback_type="correction"),
            make_feedback(thumbs_up_down=True),
        ]
        record = MagicMock(total_feedback=100, positive_feedback=90, parameters_json={})
        learning, _, _ = make_learning(db=self._db(fb, learning_record=record))
        result = learning.get_learning_signals("a1")
        assert result["total_feedback_in_period"] == 4
        assert result["positive_ratio_in_period"] == 1.0
        assert result["correction_count_in_period"] == 1
        types = [s["type"] for s in result["learning_signals"]]
        assert "strength" in types
        assert [s["type"] for s in result["improvement_suggestions"]] == ["training"]
        assert result["aggregate_data"]["aggregate_total"] == 100
        assert result["aggregate_data"]["aggregate_success_rate"] == 0.9

    def test_low_positive_ratio_weakness_and_warnings(self):
        fb = [
            make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction"),
            make_feedback(thumbs_up_down=False, rating=2, feedback_type="correction"),
            make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction"),
            make_feedback(thumbs_up_down=False, rating=2, feedback_type="correction"),
            make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction"),
        ]
        record = MagicMock(total_feedback=50, positive_feedback=10, parameters_json={})
        learning, _, _ = make_learning(db=self._db(fb, learning_record=record))
        result = learning.get_learning_signals("a1")
        assert result["positive_ratio_in_period"] == 0.0
        assert result["correction_count_in_period"] == 5
        types = [s["type"] for s in result["learning_signals"]]
        assert "weakness" in types
        assert "pattern" in types
        assert "warning" in types
        suggestions = [s["type"] for s in result["improvement_suggestions"]]
        assert suggestions == ["training", "supervision"]

    def test_middle_ratio_no_extreme_signals(self):
        fb = [make_feedback(thumbs_up_down=True), make_feedback(thumbs_up_down=False)]
        learning, _, _ = make_learning(db=self._db(fb))
        result = learning.get_learning_signals("a1")
        assert result["positive_ratio_in_period"] == 0.5
        assert result["learning_signals"] == []
        assert [s["type"] for s in result["improvement_suggestions"]] == ["supervision"]

    def test_ratings_empty_no_rating_signal(self):
        fb = [
            make_feedback(thumbs_up_down=True),
            make_feedback(thumbs_up_down=False),
            make_feedback(thumbs_up_down=True),
        ]
        learning, _, _ = make_learning(db=self._db(fb))
        result = learning.get_learning_signals("a1")
        assert result["positive_ratio_in_period"] == pytest.approx(2 / 3)
        # Mid-range ratio + no ratings + no corrections -> no signals at all.
        assert result["learning_signals"] == []
        assert result["improvement_suggestions"] == []


class TestRecordFeedbackWorldModel:
    def _db(self, execution=None):
        db = Mock()
        ex_q = Mock()
        ex_q.filter.return_value = ex_q
        ex_q.first.return_value = execution
        db.query.return_value = ex_q
        return db

    async def test_record_success_positive(self):
        wm = Mock()
        wm.record_experience = AsyncMock(return_value=True)
        db = self._db(execution=MagicMock())
        learning, _, _ = make_learning(db=db, world_model=wm)
        ok = await learning.record_feedback_in_world_model(
            make_feedback(thumbs_up_down=True, rating=5, agent_execution_id="ex1", feedback_type="positive"))
        assert ok is True
        wm.record_experience.assert_awaited_once()
        exp = wm.record_experience.await_args.args[0]
        assert exp.outcome == "Success"
        assert exp.feedback_score == pytest.approx(1.0)
        assert exp.artifacts == ["ex1"]
        assert exp.input_summary == "ctx"

    async def test_record_failure_negative(self):
        wm = Mock()
        wm.record_experience = AsyncMock(return_value=True)
        learning, _, _ = make_learning(world_model=wm)
        await learning.record_feedback_in_world_model(
            make_feedback(thumbs_up_down=False, rating=1))
        exp = wm.record_experience.await_args.args[0]
        assert exp.outcome == "Failure"
        assert exp.feedback_score == pytest.approx(-1.0)

    async def test_record_mixed_and_no_execution(self):
        wm = Mock()
        wm.record_experience = AsyncMock(return_value=True)
        db = self._db(execution=None)
        learning, _, _ = make_learning(db=db, world_model=wm)
        await learning.record_feedback_in_world_model(make_feedback(rating=3))
        exp = wm.record_experience.await_args.args[0]
        assert exp.outcome == "Mixed"
        assert exp.feedback_score == 0.0
        assert exp.artifacts == []

    async def test_record_world_model_failure_returns_false(self):
        wm = Mock()
        wm.record_experience = AsyncMock(return_value=False)
        learning, _, _ = make_learning(world_model=wm)
        assert await learning.record_feedback_in_world_model(
            make_feedback(thumbs_up_down=True)) is False

    async def test_record_exception_returns_false(self):
        wm = Mock()
        wm.record_experience = AsyncMock(side_effect=RuntimeError("lancedb down"))
        learning, _, _ = make_learning(world_model=wm)
        assert await learning.record_feedback_in_world_model(
            make_feedback(thumbs_up_down=True)) is False

    async def test_record_no_thumbs_rating_only_score(self):
        wm = Mock()
        wm.record_experience = AsyncMock(return_value=True)
        learning, _, _ = make_learning(world_model=wm)
        await learning.record_feedback_in_world_model(make_feedback(rating=2))
        exp = wm.record_experience.await_args.args[0]
        assert exp.feedback_score == pytest.approx(-0.5)
        assert exp.outcome == "Failure"


class TestBatchUpdateConfidence:
    def _db(self, agent=None, feedback=None):
        db = Mock()
        a_q = Mock()
        a_q.filter.return_value = a_q
        a_q.first.return_value = agent
        f_q = Mock()
        f_q.filter.return_value = f_q
        f_q.all.return_value = feedback
        db.query.side_effect = [a_q, f_q]
        return db

    def test_agent_not_found(self):
        learning, _, _ = make_learning(db=self._db(agent=None))
        assert learning.batch_update_confidence_from_feedback("a1") is None

    def test_no_feedback_returns_current(self):
        agent = MagicMock(confidence_score=0.6)
        learning, _, _ = make_learning(db=self._db(agent=agent, feedback=[]))
        assert learning.batch_update_confidence_from_feedback("a1") == 0.6

    def test_aggregate_adjustment(self):
        agent = MagicMock(confidence_score=0.5)
        old = datetime.now() - timedelta(days=30)
        fb = [
            make_feedback(thumbs_up_down=True, rating=5, created_at=datetime.now()),
            make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction", created_at=old),
            make_feedback(rating=3, created_at=datetime.now()),
        ]
        learning, _, _ = make_learning(db=self._db(agent=agent, feedback=fb))
        new = learning.batch_update_confidence_from_feedback("a1", days=30)
        assert new is not None
        assert 0.0 <= new <= 1.0
        assert new > 0.5

    def test_negative_clamp(self):
        agent = MagicMock(confidence_score=0.01)
        fb = [
            make_feedback(thumbs_up_down=False, rating=1, feedback_type="correction",
                          created_at=datetime.now()),
        ]
        learning, _, _ = make_learning(db=self._db(agent=agent, feedback=fb))
        assert learning.batch_update_confidence_from_feedback("a1") == 0.0


class TestRecordUserCorrection:
    def _db(self, agent=None):
        db = Mock()
        a_q = Mock()
        a_q.filter.return_value = a_q
        a_q.first.return_value = agent
        db.query.return_value = a_q
        return db

    async def test_record_correction_success(self):
        agent = MagicMock(confidence_score=0.7)
        db = self._db(agent=agent)
        continuous = Mock()
        learning, _, _ = make_learning(db=db, continuous=continuous)
        exp_id = await learning.record_user_correction(
            agent_id="a1", tenant_id="t1",
            original_action={"action_type": "send_email", "parameters": {"to": "a"}},
            corrected_action={"action_type": "send_email", "parameters": {"to": "b"}},
            context="user fixed recipient",
        )
        assert exp_id
        assert agent.confidence_score == pytest.approx(0.65)
        db.commit.assert_called_once()
        continuous.update_from_feedback.assert_called_once()

    async def test_record_correction_action_type_change(self):
        db = self._db(agent=None)
        learning, _, _ = make_learning(db=db)
        await learning.record_user_correction(
            agent_id="a1", tenant_id="t1",
            original_action={"action_type": "send_email"},
            corrected_action={"action_type": "send_slack"},
        )
        db.commit.assert_called_once()

    async def test_record_correction_continuous_learning_fails(self):
        agent = MagicMock(confidence_score=0.7)
        db = self._db(agent=agent)
        continuous = Mock()
        continuous.update_from_feedback.side_effect = RuntimeError("cl down")
        learning, _, _ = make_learning(db=db, continuous=continuous)
        exp_id = await learning.record_user_correction(
            agent_id="a1", tenant_id="t1",
            original_action={"action_type": "a"}, corrected_action={"action_type": "a"},
        )
        assert exp_id

    async def test_record_correction_exception_rolls_back(self):
        db = self._db(agent=None)
        db.add.side_effect = RuntimeError("db boom")
        learning, _, _ = make_learning(db=db)
        with pytest.raises(RuntimeError):
            await learning.record_user_correction(
                agent_id="a1", tenant_id="t1",
                original_action={}, corrected_action={},
            )
        db.rollback.assert_called_once()

    def test_classify_correction(self):
        learning, _, _ = make_learning()
        assert learning._classify_correction("not-dict", {}) == "other_correction"
        assert learning._classify_correction({}, "not-dict") == "other_correction"
        assert learning._classify_correction(
            {"action_type": "a"}, {"action_type": "b"}) == "action_type_change"
        assert learning._classify_correction(
            {"action_type": "a", "parameters": {"x": 1}},
            {"action_type": "a", "parameters": {"x": 2}}) == "parameter_adjustment"
        assert learning._classify_correction(
            {"action_type": "a"}, {"action_type": "a"}) == "other_correction"


class TestRecordRejection:
    def _db(self, agent=None):
        db = Mock()
        a_q = Mock()
        a_q.filter.return_value = a_q
        a_q.first.return_value = agent
        db.query.return_value = a_q
        return db

    async def test_record_rejection_success(self):
        agent = MagicMock(confidence_score=0.5)
        db = self._db(agent=agent)
        continuous = Mock()
        learning, _, _ = make_learning(db=db, continuous=continuous)
        exp_id = await learning.record_rejection(
            agent_id="a1", tenant_id="t1", action_type="create_invoice",
            action_data={"amount": 100}, reason="wrong amount",
        )
        assert exp_id
        assert agent.confidence_score == pytest.approx(0.4)
        db.commit.assert_called_once()
        continuous.update_from_feedback.assert_called_once()

    async def test_record_rejection_no_agent(self):
        db = self._db(agent=None)
        learning, _, _ = make_learning(db=db)
        await learning.record_rejection(
            agent_id="a1", tenant_id="t1", action_type="x", action_data={})
        db.commit.assert_called_once()

    async def test_record_rejection_continuous_learning_fails(self):
        db = self._db(agent=None)
        continuous = Mock()
        continuous.update_from_feedback.side_effect = RuntimeError("cl down")
        learning, _, _ = make_learning(db=db, continuous=continuous)
        assert await learning.record_rejection(
            agent_id="a1", tenant_id="t1", action_type="x", action_data={})

    async def test_record_rejection_exception_rolls_back(self):
        db = self._db(agent=None)
        db.add.side_effect = RuntimeError("db boom")
        learning, _, _ = make_learning(db=db)
        with pytest.raises(RuntimeError):
            await learning.record_rejection("a1", "t1", "x", {})
        db.rollback.assert_called_once()


class TestAnalyzeFailurePatterns:
    def _db(self, experiences):
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = experiences
        db.query.return_value = q
        return db

    def _exp(self, correction_type=None, rejection_type=None, task_type="t"):
        e = MagicMock()
        e.task_type = task_type
        learnings = {}
        if correction_type:
            learnings["correction_type"] = correction_type
        if rejection_type:
            learnings["rejection_type"] = rejection_type
        e.learnings = learnings
        return e

    async def test_patterns_detected(self):
        db = self._db([
            self._exp(correction_type="action_type_change", task_type="send_email"),
            self._exp(correction_type="action_type_change", task_type="send_email"),
            self._exp(rejection_type="explicit_rejection", task_type="create_invoice"),
            self._exp(rejection_type="explicit_rejection", task_type="create_invoice"),
            self._exp(rejection_type="explicit_rejection", task_type="create_invoice"),
            self._exp(task_type="unknown"),
        ])
        learning, _, _ = make_learning(db=db)
        patterns = await learning.analyze_failure_patterns("a1", "t1", min_occurrences=2)
        assert {p["type"] for p in patterns} == {"action_type_change", "explicit_rejection"}
        action = next(p for p in patterns if p["type"] == "action_type_change")
        assert action["count"] == 2
        assert action["examples"] == ["send_email", "send_email"]

    async def test_unknown_type_below_threshold(self):
        db = self._db([self._exp(task_type="x"), self._exp(task_type="y")])
        learning, _, _ = make_learning(db=db)
        assert await learning.analyze_failure_patterns("a1", "t1", min_occurrences=3) == []

    async def test_no_failures(self):
        learning, _, _ = make_learning(db=self._db([]))
        assert await learning.analyze_failure_patterns("a1", "t1") == []

    async def test_exception_returns_empty(self):
        db = Mock()
        db.query.side_effect = RuntimeError("db boom")
        learning, _, _ = make_learning(db=db)
        assert await learning.analyze_failure_patterns("a1", "t1") == []
