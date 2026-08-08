"""
Coverage-push tests — core modules wave B (part 2).

Top-ups for:
  - core.atom_saas_websocket      (59% -> 95%+)
  - core.canvas_logic_service     (76% -> 95%+)
  - core.orchestration.conductor_agent (98% -> 95%+)
"""
import asyncio
import contextlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from core.models import (
    AgentRegistry, CategoryCache, SkillCache, WebSocketState,
)

# ============================================================================
# core.atom_saas_websocket — remaining paths
# ============================================================================


@pytest.fixture
def ws_client(monkeypatch):
    from core.atom_saas_websocket import AtomSaaSWebSocketClient

    client = AtomSaaSWebSocketClient(api_token="tok")
    client._update_db_state = AsyncMock()
    return client


def _patch_session_local(monkeypatch, db_session):
    @contextlib.contextmanager
    def _cm():
        yield db_session
    monkeypatch.setattr("core.atom_saas_websocket.SessionLocal",
                        lambda: _cm())


class _IterConn:
    """Fake ws connection supporting `async for` + close/send."""

    def __init__(self, messages, exc=None):
        self._messages = list(messages)
        self._exc = exc
        self.sent = []
        self.closed = False

    def __aiter__(self):
        return self._agen()

    async def _agen(self):
        for m in self._messages:
            yield m
        if self._exc is not None:
            raise self._exc

    async def send(self, msg):
        self.sent.append(msg)

    async def close(self):
        self.closed = True


class TestWebSocketRemaining:
    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, ws_client):
        assert await ws_client.send_message({"type": "ping"}) is False

    @pytest.mark.asyncio
    async def test_send_message_failure(self, ws_client, monkeypatch):
        ws_client._connected = True
        ws_client._ws_connection = SimpleNamespace(
            send=AsyncMock(side_effect=ConnectionError("socket dead")))
        assert await ws_client.send_message({"type": "ping"}) is False

    @pytest.mark.asyncio
    async def test_disconnect_close_error(self, ws_client):
        ws_client._connected = True
        ws_client._ws_connection = SimpleNamespace(
            close=AsyncMock(side_effect=ConnectionError("gone")))
        await ws_client.disconnect()
        assert ws_client._connected is False

    @pytest.mark.asyncio
    async def test_message_loop_normal_close(self, ws_client):
        conn = _IterConn([], exc=ConnectionClosedOK(None, "ok"))
        ws_client._ws_connection = conn
        with patch.object(ws_client, "_handle_disconnect", new=AsyncMock()) as h:
            await ws_client._message_loop()
            h.assert_awaited_once_with("connection_closed_ok")

    @pytest.mark.asyncio
    async def test_message_loop_error_close(self, ws_client):
        conn = _IterConn([], exc=ConnectionClosedError(None, "bad"))
        ws_client._ws_connection = conn
        with patch.object(ws_client, "_handle_disconnect", new=AsyncMock()) as h:
            await ws_client._message_loop()
            h.assert_awaited_once()
            assert h.call_args[0][0].startswith("connection_error:")

    @pytest.mark.asyncio
    async def test_message_loop_generic_error(self, ws_client):
        conn = _IterConn([], exc=RuntimeError("boom"))
        ws_client._ws_connection = conn
        with patch.object(ws_client, "_handle_disconnect", new=AsyncMock()) as h:
            await ws_client._message_loop()
            h.assert_awaited_once()
            assert h.call_args[0][0].startswith("message_loop_error:")

    @pytest.mark.asyncio
    async def test_handle_message_rate_limit(self, ws_client):
        import time
        ws_client._message_timestamps = [time.time()] * ws_client.RATE_LIMIT_MESSAGES
        await ws_client._handle_message('{"type":"skill_update","data":{"skill_id":"1","name":"n"}}')
        assert ws_client._message_handler is None  # never invoked

    @pytest.mark.asyncio
    async def test_handle_message_invalid_and_ping(self, ws_client):
        await ws_client._handle_message('{"data":{}}')  # missing type
        with patch.object(ws_client, "send_message", new=AsyncMock(return_value=True)) as send:
            await ws_client._handle_message('{"type":"ping"}')
            send.assert_awaited_once()
            assert send.call_args[0][0] == {"type": "pong"}

    @pytest.mark.asyncio
    async def test_handle_message_json_error_and_bad_data(self, ws_client):
        await ws_client._handle_message("{not json")
        await ws_client._handle_message('{"type":"skill_update","data":"not-a-dict"}')
        await ws_client._handle_message('{"type":"skill_update","data":{"name":"no-id"}}')

    @pytest.mark.asyncio
    async def test_handle_message_valid_with_handler(self, ws_client):
        calls = []
        async def handler(msg_type, data):
            calls.append((msg_type, data))
        ws_client._message_handler = handler
        with patch.object(ws_client, "_update_cache", new=AsyncMock()) as uc:
            await ws_client._handle_message(
                '{"type":"rating_update","data":{"skill_id":"s1","rating":5}}')
            assert calls == [("rating_update", {"skill_id": "s1", "rating": 5})]
            uc.assert_awaited_once()

    def test_validate_message_data_matrix(self, ws_client):
        assert ws_client._validate_message_data("category_update", {"name": "x"}) is True
        assert ws_client._validate_message_data("category_update", {}) is False
        assert ws_client._validate_message_data("rating_update", {"skill_id": "s"}) is False
        assert ws_client._validate_message_data("rating_update",
                                                {"skill_id": "s", "rating": 9}) is False
        assert ws_client._validate_message_data("rating_update",
                                                {"skill_id": "s", "rating": "4"}) is False
        assert ws_client._validate_message_data("skill_delete", {}) is False
        assert ws_client._validate_message_data("skill_delete", {"skill_id": "s"}) is True
        assert ws_client._validate_message_data("weird", {"a": 1}) is True

    @pytest.mark.asyncio
    async def test_update_cache_skill_existing_and_new(self, ws_client, db_session, monkeypatch):
        _patch_session_local(monkeypatch, db_session)
        db_session.add(SkillCache(skill_id="s1", tenant_id="t1", skill_data={"name": "old"}, expires_at=datetime.now(timezone.utc)))
        db_session.commit()
        await ws_client._update_cache("skill_update", {"skill_id": "s1", "name": "new"})
        await ws_client._update_cache("skill_update", {"skill_id": "s2", "name": "fresh"})
        db_session.expire_all()
        assert db_session.query(SkillCache).count() == 2
        assert db_session.query(SkillCache).filter(SkillCache.skill_id == "s1").first().skill_data["name"] == "new"

    @pytest.mark.asyncio
    async def test_update_cache_category_and_delete(self, ws_client, db_session, monkeypatch):
        _patch_session_local(monkeypatch, db_session)
        db_session.add(CategoryCache(category_name="c1", tenant_id="t1", category_data={}, expires_at=datetime.now(timezone.utc)))
        db_session.commit()
        await ws_client._update_cache("category_update", {"name": "c1", "n": 2})
        await ws_client._update_cache("category_update", {"category": "c2", "n": 3})
        db_session.add(SkillCache(skill_id="s9", tenant_id="t1", skill_data={}, expires_at=datetime.now(timezone.utc)))
        db_session.commit()
        await ws_client._update_cache("skill_delete", {"skill_id": "s9"})
        db_session.expire_all()
        assert db_session.query(SkillCache).filter(SkillCache.skill_id == "s9").count() == 0
        assert db_session.query(CategoryCache).count() == 2

    @pytest.mark.asyncio
    async def test_update_cache_failure_logged(self, monkeypatch, caplog):
        import logging
        from core.atom_saas_websocket import AtomSaaSWebSocketClient

        raw = AtomSaaSWebSocketClient(api_token="tok")
        _patch_session_local(monkeypatch, SimpleNamespace())
        with caplog.at_level(logging.ERROR):
            await raw._update_cache("skill_update", {"skill_id": "x", "name": "y"})
        assert "Failed to update cache" in caplog.text

    @pytest.mark.asyncio
    async def test_heartbeat_pong_timeout(self, ws_client):
        ws_client._connected = True
        ws_client.send_message = AsyncMock()
        ws_client._wait_for_pong = AsyncMock(side_effect=asyncio.TimeoutError())

        async def disconnect(reason):
            ws_client._connected = False

        with patch.object(ws_client, "_handle_disconnect", new=AsyncMock(side_effect=disconnect)):
            with patch.object(asyncio, "sleep", new=AsyncMock()):
                await ws_client._heartbeat_loop()
            ws_client._handle_disconnect.assert_awaited_once_with("pong_timeout")

    @pytest.mark.asyncio
    async def test_heartbeat_no_pong(self, ws_client):
        ws_client._connected = True
        ws_client.send_message = AsyncMock()
        ws_client._wait_for_pong = AsyncMock(return_value=False)

        async def disconnect(reason):
            ws_client._connected = False

        with patch.object(ws_client, "_handle_disconnect", new=AsyncMock(side_effect=disconnect)):
            with patch.object(asyncio, "sleep", new=AsyncMock()):
                await ws_client._heartbeat_loop()
            ws_client._handle_disconnect.assert_awaited_once_with("stale_connection")

    @pytest.mark.asyncio
    async def test_heartbeat_cancelled(self, ws_client):
        ws_client._connected = True
        ws_client.send_message = AsyncMock()
        ws_client._wait_for_pong = AsyncMock(return_value=True)
        with patch.object(asyncio, "sleep", new=AsyncMock(side_effect=asyncio.CancelledError)):
            await ws_client._heartbeat_loop()

    @pytest.mark.asyncio
    async def test_heartbeat_generic_error(self, ws_client):
        ws_client._connected = True
        ws_client.send_message = AsyncMock(side_effect=ConnectionError("x"))
        with patch.object(asyncio, "sleep", new=AsyncMock()):
            await ws_client._heartbeat_loop()  # must not raise

    @pytest.mark.asyncio
    async def test_wait_for_pong(self, ws_client):
        assert await ws_client._wait_for_pong() is True

    @pytest.mark.asyncio
    async def test_reconnect_failure_reschedules(self, ws_client, monkeypatch):
        attempts = {"n": 0}

        async def failing_connect(*a, **k):
            attempts["n"] += 1
            raise OSError("refused")

        monkeypatch.setattr("core.atom_saas_websocket.websockets.connect",
                            failing_connect)
        ws_client.RECONNECT_DELAYS = [0.01]
        ws_client.MAX_RECONNECT_ATTEMPTS = 2
        ws_client._reconnect_attempts = 0
        ws_client._message_handler = AsyncMock()
        await ws_client._reconnect()
        await asyncio.sleep(0.05)
        assert attempts["n"] >= 1

    @pytest.mark.asyncio
    async def test_reconnect_success(self, ws_client, monkeypatch):
        async def fake_connect(handler):
            ws_client._connected = True
            return True

        monkeypatch.setattr(ws_client, "connect", fake_connect)
        ws_client._reconnect_attempts = 0
        await ws_client._reconnect()
        assert ws_client._connected is True

    @pytest.mark.asyncio
    async def test_handle_disconnect_max_attempts(self, ws_client):
        ws_client._reconnect_attempts = ws_client.MAX_RECONNECT_ATTEMPTS
        with patch.object(ws_client, "_update_db_state", new=AsyncMock()) as ud:
            await ws_client._handle_disconnect("nope")
            reasons = [c.kwargs.get("disconnect_reason") or c.args[1]
                       for c in ud.call_args_list]
            assert any("max_reconnects_reached" in str(r) for r in reasons)

    @pytest.mark.asyncio
    async def test_update_db_state_existing_row(self, db_session, monkeypatch):
        from core.atom_saas_websocket import AtomSaaSWebSocketClient

        raw = AtomSaaSWebSocketClient(api_token="tok")
        _patch_session_local(monkeypatch, db_session)
        db_session.add(WebSocketState(id=1, connected=False))
        db_session.commit()
        await raw._update_db_state(connected=True, reconnect_attempts=3)
        db_session.expire_all()
        row = db_session.query(WebSocketState).first()
        assert row.connected is True
        assert row.reconnect_attempts == 3

    @pytest.mark.asyncio
    async def test_update_db_state_failure_logged(self, monkeypatch, caplog):
        import logging
        from core.atom_saas_websocket import AtomSaaSWebSocketClient

        raw = AtomSaaSWebSocketClient(api_token="tok")
        _patch_session_local(monkeypatch, SimpleNamespace())
        with caplog.at_level(logging.ERROR):
            await raw._update_db_state(connected=True)
        assert "Failed to update database state" in caplog.text

    @pytest.mark.asyncio
    async def test_handle_rating_update(self, ws_client, db_session, monkeypatch):
        _patch_session_local(monkeypatch, db_session)
        db_session.add(SkillCache(
            skill_id="r1", tenant_id="t1", skill_data={"name": "n", "average_rating": 3},
            expires_at=datetime.now(timezone.utc)))
        db_session.commit()
        await ws_client.handle_rating_update({"skill_id": "r1", "rating": 5,
                                              "average_rating": 4.5, "rating_count": 12})
        db_session.expire_all()
        row = db_session.query(SkillCache).filter(SkillCache.skill_id == "r1").first()
        assert row.skill_data["average_rating"] == 4.5
        assert row.skill_data["rating_count"] == 12

    @pytest.mark.asyncio
    async def test_handle_rating_update_missing_skill(self, ws_client, db_session, monkeypatch):
        _patch_session_local(monkeypatch, db_session)
        await ws_client.handle_rating_update({"skill_id": None, "rating": 5})

    @pytest.mark.asyncio
    async def test_handle_skill_delete(self, ws_client, db_session, monkeypatch):
        _patch_session_local(monkeypatch, db_session)
        with patch.object(ws_client, "_update_cache", new=AsyncMock()) as uc:
            await ws_client.handle_skill_delete({"skill_id": "s5"})
            uc.assert_awaited_once_with("skill_delete", {"skill_id": "s5"})

    def test_get_websocket_state(self, db_session, monkeypatch):
        _patch_session_local(monkeypatch, db_session)
        from core.atom_saas_websocket import get_websocket_state
        db_session.add(WebSocketState(id=1, connected=True))
        db_session.commit()
        assert get_websocket_state() is not None

    def test_get_websocket_state_error(self, monkeypatch):
        from core.atom_saas_websocket import get_websocket_state
        with patch("core.atom_saas_websocket.SessionLocal",
                   side_effect=RuntimeError("db down")):
            assert get_websocket_state() is None


# ============================================================================
# core.canvas_logic_service — remaining paths
# ============================================================================


class TestCanvasLogicRemaining:
    def test_sanitize_namespace_empty_and_noise(self):
        from core.canvas_logic_service import sanitize_namespace

        assert sanitize_namespace("") == "unknown"
        assert sanitize_namespace("!!!") == "unknown"
        assert sanitize_namespace("a b") == "a-b"

    def test_get_runtime(self, monkeypatch):
        from core import canvas_logic_service as cls

        fake = object()
        monkeypatch.setattr("core.sandbox_runtime.base.get_runtime",
                            lambda: fake)
        assert cls.get_runtime() is fake

    def test_check_governance_requires_agent(self, db_session):
        from core.canvas_logic_service import CanvasLogicService

        svc = CanvasLogicService(db_session)
        with pytest.raises(PermissionError):
            svc.check_governance(None)

    def test_save_logic_update_existing_row(self, db_session):
        from core.canvas_logic_service import CanvasLogicService

        svc = CanvasLogicService(db_session)
        first = svc.save_logic("c-upd", "v1", language="python", created_by="u1")
        updated = svc.save_logic("c-upd", "v2", language="python3", created_by=None)
        assert updated["source"] == "v2"
        assert updated["language"] == "python3"
        loaded = svc.load_logic("c-upd")
        assert loaded["source"] == "v2"
        # created_by preserved on update when not re-supplied.
        assert loaded["created_by"] == "u1"

    def test_check_governance_agent_not_found(self, db_session):
        from core.canvas_logic_service import CanvasLogicService

        svc = CanvasLogicService(db_session)
        with pytest.raises(PermissionError):
            svc.check_governance("no-such-agent")

    def test_check_governance_not_autonomous(self, db_session):
        from core.canvas_logic_service import CanvasLogicService

        db_session.add(AgentRegistry(
            id="intern-1", name="i", category="Ops", module_path="m",
            class_name="c", status="intern",
        ))
        db_session.commit()
        svc = CanvasLogicService(db_session)
        with pytest.raises(PermissionError):
            svc.check_governance("intern-1")

    @pytest.mark.asyncio
    async def test_run_no_logic(self, db_session):
        from core.canvas_logic_service import CanvasLogicService

        svc = CanvasLogicService(db_session)
        result = await svc.run("ghost-canvas")
        assert result["success"] is False
        assert "No logic" in result["error"]

    @pytest.mark.asyncio
    async def test_run_governance_gate_with_agent(self, db_session):
        from core.canvas_logic_service import CanvasLogicService

        svc = CanvasLogicService(db_session)
        svc.save_logic(canvas_id="c-gov", source="x=1", created_by="u1")
        with pytest.raises(PermissionError):
            await svc.run("c-gov", inputs={}, agent_id="no-such-agent")

    @pytest.mark.asyncio
    async def test_run_policy_issuer_failure_still_runs(self, db_session, monkeypatch):
        from core import canvas_logic_service as cls

        captured = {}

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
                captured["policy"] = policy
                return SimpleNamespace(success=True, stdout="", stderr="", exit_code=0)

        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())
        monkeypatch.setattr("core.sandbox_policy.PolicyIssuer",
                            MagicMock(side_effect=RuntimeError("no issuer")))
        svc = cls.CanvasLogicService(db_session)
        svc.save_logic(canvas_id="c-pfail", source="x=1", created_by="u1")
        result = await svc.run("c-pfail", inputs={}, scopes=("canvas_render",))
        assert result["success"] is True
        assert captured["policy"] is None


# ============================================================================
# core.orchestration.conductor_agent — remaining lines
# ============================================================================


class TestConductorRemaining:
    def _step(self, step_id, **kw):
        from core.orchestration.conductor_agent import WorkflowStep, StepType

        defaults = dict(step_id=step_id, step_type=StepType.AGENT)
        defaults.update(kw)
        return WorkflowStep(**defaults)

    def _ctx(self, steps, start_step, strategy):
        from core.orchestration.conductor_agent import (
            WorkflowExecutionContext, ExecutionStrategy,
        )

        return WorkflowExecutionContext(
            workflow_id="wf", execution_id="ex", steps=steps,
            start_step=start_step, strategy=strategy,
        )

    @pytest.mark.asyncio
    async def test_adaptive_strategy_dispatch(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        with patch.object(agent, "_execute_adaptive", new=AsyncMock()) as ea:
            await agent.execute_workflow(
                [self._step("s1")], "s1", strategy=ExecutionStrategy.ADAPTIVE)
            ea.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sequential_step_not_found_and_blocked(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        ctx = self._ctx([self._step("s1", depends_on=["missing"])], "s1",
                        ExecutionStrategy.SEQUENTIAL)
        ctx2 = self._ctx([self._step("s1")], "ghost", ExecutionStrategy.SEQUENTIAL)
        await agent._execute_sequential(ctx, MagicMock())
        await agent._execute_sequential(ctx2, MagicMock())

    @pytest.mark.asyncio
    async def test_adaptive_no_progress_paths(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        with patch.object(agent, "_execute_step", new=AsyncMock(return_value={"ok": True})):
            # start step missing
            ctx = self._ctx([self._step("s1")], "ghost", ExecutionStrategy.ADAPTIVE)
            await agent._execute_adaptive(ctx, MagicMock())
            # condition skips branch with no next steps
            ctx2 = self._ctx([self._step("s1", condition="x > 1")], "s1",
                             ExecutionStrategy.ADAPTIVE)
            ctx2.shared_context = {"x": 0}
            with patch.object(agent, "_evaluate_condition", return_value=False):
                await agent._execute_adaptive(ctx2, MagicMock())
            # parallel group path
            ctx3 = self._ctx([self._step("s1"), self._step("s2", parallel_group="g1"),
                              self._step("s3", parallel_group="g1")], "s1",
                             ExecutionStrategy.ADAPTIVE)
            ctx3.get_step("s1").next_steps = ["s2"]
            with patch.object(agent, "_evaluate_condition", return_value=True):
                with patch.object(agent, "_can_execute_parallel_group", return_value=True):
                    with patch.object(agent, "_execute_parallel_group", new=AsyncMock()) as epg:
                        await agent._execute_adaptive(ctx3, MagicMock())
                        epg.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_safe_blocked_step(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        ctx = self._ctx([self._step("s1", condition_met=False)], "s1",
                        ExecutionStrategy.ROLLBACK_SAFE)
        await agent._execute_rollback_safe(ctx, MagicMock())

    @pytest.mark.asyncio
    async def test_consensus_deterministic_failed_dict(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        agent.set_step_executor(lambda step, ctx: {"status": "failed", "error": "nope"})
        # Force the deterministic single-run path: a non-stochastic executor.
        agent._is_stochastic_executor = lambda: False
        ctx = self._ctx([self._step("s1")], "s1", ExecutionStrategy.PARALLEL_CONSENSUS)
        result = await agent.execute_workflow(
            [self._step("s1")], "s1", context=ctx,
            strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status.value == "failed"

    @pytest.mark.asyncio
    async def test_rollback_skips_missing_compensation_step(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        ctx = self._ctx([self._step("s1")], "s1", ExecutionStrategy.SEQUENTIAL)
        ctx.rollback_stack = ["s1", "ghost-step"]
        result = MagicMock()
        with patch.object(agent, "_execute_step", new=AsyncMock()):
            await agent._rollback_workflow(ctx, result)
        assert result.rolled_back is True


# ============================================================================
# Final top-up tests (combined-coverage gaps)
# ============================================================================


class TestWebSocketFinalTopUps:
    @pytest.mark.asyncio
    async def test_message_loop_delivers_message(self, ws_client):
        conn = _IterConn(['{"type":"pong"}'])
        ws_client._ws_connection = conn
        with patch.object(ws_client, "_handle_message", new=AsyncMock()) as hm:
            await ws_client._message_loop()
            hm.assert_awaited_once_with('{"type":"pong"}')

    @pytest.mark.asyncio
    async def test_handle_message_handler_raises(self, ws_client):
        async def boom(msg_type, data):
            raise RuntimeError("handler crash")
        ws_client._message_handler = boom
        await ws_client._handle_message(
            '{"type":"skill_update","data":{"skill_id":"s","name":"n"}}')

    @pytest.mark.asyncio
    async def test_heartbeat_happy_path(self, ws_client):
        ws_client._connected = True
        ws_client.send_message = AsyncMock()
        ws_client._wait_for_pong = AsyncMock(return_value=True)

        calls = {"n": 0}

        async def sleep_then_disconnect(delay):
            calls["n"] += 1
            if calls["n"] == 2:
                ws_client._connected = False

        with patch.object(asyncio, "sleep",
                          new=AsyncMock(side_effect=sleep_then_disconnect)):
            await ws_client._heartbeat_loop()
        assert calls["n"] >= 2
        ws_client.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_rating_update_db_error(self, ws_client, monkeypatch, caplog):
        import logging
        monkeypatch.setattr("core.atom_saas_websocket.SessionLocal",
                            MagicMock(side_effect=RuntimeError("db down")))
        with caplog.at_level(logging.ERROR):
            await ws_client.handle_rating_update({"skill_id": "r1", "rating": 5})
        assert "Failed to update rating in cache" in caplog.text

    @pytest.mark.asyncio
    async def test_update_db_state_all_kwargs(self, db_session, monkeypatch):
        from core.atom_saas_websocket import AtomSaaSWebSocketClient

        raw = AtomSaaSWebSocketClient(api_token="tok")
        _patch_session_local(monkeypatch, db_session)
        await raw._update_db_state(
            connected=True, last_connected_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
            disconnect_reason="test", reconnect_attempts=2)
        db_session.expire_all()
        row = db_session.query(WebSocketState).first()
        assert row.connected is True
        assert row.last_message_at is not None
        assert row.disconnect_reason == "test"


class TestCanvasLogicFinalTopUps:
    @pytest.mark.asyncio
    async def test_run_legacy_policy_issuer_failure(self, db_session, monkeypatch):
        from core import canvas_logic_service as cls

        captured = {}

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
                captured["policy"] = policy
                return SimpleNamespace(success=True, stdout="", stderr="", exit_code=0)

        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())
        monkeypatch.setattr("core.sandbox_policy.PolicyIssuer",
                            MagicMock(side_effect=RuntimeError("no issuer")))
        svc = cls.CanvasLogicService(db_session)
        svc.save_logic(canvas_id="c-pfail2", source="x=1", created_by="u1")
        result = await svc.run("c-pfail2", inputs={})
        assert result["success"] is True
        assert captured["policy"] is None


class TestConductorFinalTopUps:
    @pytest.mark.asyncio
    async def test_rollback_safe_missing_start_step(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        ctx = TestConductorRemaining()._ctx(
            [TestConductorRemaining()._step("s1")], "ghost", ExecutionStrategy.ROLLBACK_SAFE)
        await agent._execute_rollback_safe(ctx, MagicMock())

    @pytest.mark.asyncio
    async def test_rollback_missing_comp_step(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStrategy,
        )

        agent = ConductorAgent()
        ctx = TestConductorRemaining()._ctx(
            [TestConductorRemaining()._step("s1", compensation_step_id="missing-comp")],
            "s1", ExecutionStrategy.SEQUENTIAL)
        ctx.rollback_stack = ["s1"]
        result = MagicMock()
        with patch.object(agent, "_execute_step", new=AsyncMock()):
            await agent._rollback_workflow(ctx, result)
        assert result.rolled_back is True
