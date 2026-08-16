# -*- coding: utf-8 -*-
"""Coverage wave 96 — nine-module batch (plain pytest + unittest.mock).

Targets:
1. api/device_websocket.py
2. core/memory/memory_consolidation_service.py
3. core/fleet_orchestration/predictive_scaling_service.py
4. core/mcp_service.py
5. core/security/middleware.py
6. core/condition_checkers.py
7. core/debug_collector.py
8. core/container_sandbox.py
9. core/service_factory.py

No network, no LLM, no real DB — every external boundary is mocked.
"""
import asyncio
import itertools
import json
import subprocess
import sys
import time
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

import pytest

from fastapi import WebSocketDisconnect


def run(coro):
    return asyncio.run(coro)


def _q(results):
    """Build a query-style chainable mock whose terminal call returns `results`."""
    chain = mock.MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    chain.count.return_value = results if isinstance(results, int) else len(results)
    chain.all.return_value = results
    chain.first.return_value = results[0] if results else None
    chain.scalar.return_value = results[0] if results else None
    return chain


def _scalar_seq(vals):
    """Query chain whose .scalar() returns cycling successive values."""
    chain = _q([])
    chain.scalar = mock.MagicMock(side_effect=itertools.cycle(vals))
    return chain


def _fixed_db(chain):
    """Fake Session whose query() always returns `chain` regardless of model."""
    db = ModelDb()
    db.query = lambda *a, **k: chain
    return db


class ModelDb:
    """Fake Session routing query(Model) through a mapping."""

    def __init__(self, mapping=None, default=None):
        self.mapping = mapping or {}
        self.default = default if default is not None else []
        self.add = mock.Mock()
        self.add_all = mock.Mock()
        self.commit = mock.Mock()
        self.rollback = mock.Mock()
        self.close = mock.Mock()
        self._exec_result = None

    def query(self, model):
        return self.mapping.get(model, _q(self.default))

    def execute(self, *a, **k):
        return self._exec_result if self._exec_result is not None else _q([])


# =========================================================================== #
# 1. api/device_websocket.py
# =========================================================================== #
import api.device_websocket as dw
from api.device_websocket import (
    DeviceConnectionManager,
    get_device_connection_manager,
    send_device_command,
    get_connected_devices_info,
    is_device_online,
)
from core.models import DeviceNode, User


class FakeWebSocket:
    def __init__(self, incoming=None, disconnect_at_end=False, auto_result=None):
        self.accepted = False
        self.closed = None
        self.sent = []
        self._incoming = list(incoming or [])
        self._disconnect_at_end = disconnect_at_end
        self.fail_send = False
        self.auto_result = auto_result

    async def accept(self):
        self.accepted = True

    async def close(self, code=None, reason=None):
        self.closed = (code, reason)

    async def send_json(self, payload):
        if self.fail_send and payload.get("type") != "connected":
            raise RuntimeError("send failed")
        self.sent.append(payload)
        if payload.get("type") == "command" and self.auto_result is not None:
            reply = dict(self.auto_result)
            reply["command_id"] = payload["command_id"]
            self._incoming.insert(0, reply)

    async def receive_json(self, timeout=None):
        if self._incoming:
            item = self._incoming.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if self._disconnect_at_end:
            raise WebSocketDisconnect(code=1001)
        raise WebSocketDisconnect(code=1000)


def _ep_db(user="user-obj", device="device-obj"):
    db = ModelDb()
    db.mapping = {
        User: _q([user] if user else []),
        DeviceNode: _q([device] if device else []),
    }
    return db


class TestDeviceConnectionManager:
    def test_connect_disconnect_cycle(self):
        mgr = DeviceConnectionManager()
        ws = FakeWebSocket()
        run(mgr.connect(ws, "dev1", "u1", {"capabilities": ["camera"]}))
        assert ws.accepted and ws.sent[0]["type"] == "connected"
        assert mgr.is_device_connected("dev1")
        assert mgr.get_device_info("dev1")["capabilities"] == ["camera"]
        assert mgr.get_user_devices("u1") == ["dev1"]
        assert mgr.get_all_connected_devices()[0]["device_node_id"] == "dev1"

        mgr.disconnect("dev1", "u1")
        assert not mgr.is_device_connected("dev1")
        assert mgr.get_device_info("dev1") is None
        assert mgr.get_user_devices("u1") == []
        # idempotent disconnect
        mgr.disconnect("dev1", "u1")

    def test_get_user_devices_unknown(self):
        mgr = DeviceConnectionManager()
        assert mgr.get_user_devices("nobody") == []

    def test_send_command_not_connected(self):
        mgr = DeviceConnectionManager()
        with pytest.raises(ValueError):
            run(mgr.send_command("nope", "camera_snap", {}))

    def test_send_command_success_and_generated_id(self):
        mgr = DeviceConnectionManager()
        ws = FakeWebSocket(incoming=[
            {"type": "result", "command_id": "fixed-id", "success": True}
        ])
        run(mgr.connect(ws, "dev1", "u1", {}))
        resp = run(mgr.send_command("dev1", "cmd", {}, command_id="fixed-id"))
        assert resp["success"] is True
        assert ws.sent[-1]["type"] == "command"

    def test_send_command_mismatch_id(self):
        mgr = DeviceConnectionManager()
        ws = FakeWebSocket(incoming=[{"command_id": "other"}])
        run(mgr.connect(ws, "dev1", "u1", {}))
        with pytest.raises(ValueError):
            run(mgr.send_command("dev1", "cmd", {}, command_id="expected"))

    def test_send_command_ws_disconnect(self):
        mgr = DeviceConnectionManager()
        ws = FakeWebSocket(incoming=[WebSocketDisconnect(code=1000)])
        run(mgr.connect(ws, "dev1", "u1", {"user_id": "u1"}))
        with pytest.raises(ValueError):
            run(mgr.send_command("dev1", "cmd", {}))
        assert not mgr.is_device_connected("dev1")

    def test_send_command_generic_error(self):
        mgr = DeviceConnectionManager()
        ws = FakeWebSocket(incoming=[RuntimeError("boom")])
        run(mgr.connect(ws, "dev1", "u1", {}))
        with pytest.raises(RuntimeError):
            run(mgr.send_command("dev1", "cmd", {}))

    def test_broadcast(self):
        mgr = DeviceConnectionManager()
        ws_ok = FakeWebSocket()
        ws_bad = FakeWebSocket()
        ws_bad.fail_send = True
        run(mgr.connect(ws_ok, "d1", "u1", {}))
        run(mgr.connect(ws_bad, "d2", "u1", {}))
        run(mgr.broadcast_to_user_devices("u1", {"type": "ping"}))
        assert ws_ok.sent[-1]["type"] == "ping"
        run(mgr.broadcast_to_user_devices("unknown-user", {"type": "ping"}))

    def test_get_device_connection_manager_singleton(self):
        assert get_device_connection_manager() is get_device_connection_manager()


class TestDeviceWebsocketEndpoint:
    def _run(self, monkeypatch, ws, db, token="tok"):
        monkeypatch.setattr(dw, "get_db_session", lambda: _ctx(db))
        monkeypatch.setattr(dw, "decode_token", lambda t: {"sub": "u1"} if t == "tok" else {})
        run(dw.websocket_device_endpoint(ws, token))

    def test_disabled_flag(self, monkeypatch):
        monkeypatch.setattr(dw, "DEVICE_WEBSOCKET_ENABLED", False)
        ws = FakeWebSocket()
        run(dw.websocket_device_endpoint(ws, "tok"))
        assert ws.closed[0] == 1003

    def test_invalid_token(self, monkeypatch):
        db = _ep_db()
        ws = FakeWebSocket()
        self._run(monkeypatch, ws, db, token="bad")
        assert ws.closed[0] == 1008

    def test_user_not_found(self, monkeypatch):
        db = _ep_db(user=None)
        ws = FakeWebSocket()
        self._run(monkeypatch, ws, db)
        assert ws.closed[0] == 1008

    def test_registration_timeout(self, monkeypatch):
        db = _ep_db()
        ws = FakeWebSocket(incoming=[asyncio.TimeoutError()])
        self._run(monkeypatch, ws, db)
        assert ws.closed[0] == 1008

    def test_wrong_first_message(self, monkeypatch):
        db = _ep_db()
        ws = FakeWebSocket(incoming=[{"type": "hello"}])
        self._run(monkeypatch, ws, db)
        assert ws.closed[0] == 1002

    def test_missing_device_node_id(self, monkeypatch):
        db = _ep_db()
        ws = FakeWebSocket(incoming=[{"type": "register"}])
        self._run(monkeypatch, ws, db)
        assert ws.closed[0] == 1002

    def test_existing_device_full_loop(self, monkeypatch):
        db = _ep_db(user=SimpleNamespace(id="u1"), device=SimpleNamespace(status="x"))
        ws = FakeWebSocket(incoming=[
            {"type": "register", "device_node_id": "dev1", "device_info": {"capabilities": ["cam"]}},
            {"type": "result", "command_id": "c1"},
            {"type": "heartbeat"},
            {"type": "error", "error": "cam denied"},
            {"type": "mystery"},
            WebSocketDisconnect(code=1000),
        ])
        self._run(monkeypatch, ws, db)
        types = [m["type"] for m in ws.sent]
        assert "registered" in types and "heartbeat_ack" in types
        assert db.commit.called

    def test_new_device_created(self, monkeypatch):
        db = _ep_db(user=SimpleNamespace(id="u1"), device=None)
        ws = FakeWebSocket(incoming=[
            {"type": "register", "device_node_id": "dev-abcdef12", "device_info": {}},
            WebSocketDisconnect(code=1000),
        ])
        self._run(monkeypatch, ws, db)
        assert db.add.called

    def test_message_loop_timeout_probe(self, monkeypatch):
        db = _ep_db(user=SimpleNamespace(id="u1"), device=SimpleNamespace(status="x"))
        # Timeout -> probe; then TimeoutError again with stale heartbeat -> break
        ws = FakeWebSocket(incoming=[
            {"type": "register", "device_node_id": "dev1", "device_info": {}},
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
        ])
        self._run(monkeypatch, ws, db)
        assert any(m.get("type") == "heartbeat_probe" for m in ws.sent)

    def test_probe_send_failure_breaks(self, monkeypatch):
        db = _ep_db(user=SimpleNamespace(id="u1"), device=SimpleNamespace(status="x"))
        ws = FakeWebSocket(incoming=[
            {"type": "register", "device_node_id": "dev1", "device_info": {}},
            asyncio.TimeoutError(),
        ])
        ws.fail_send = True
        self._run(monkeypatch, ws, db)

    def test_generic_exception_swallowed(self, monkeypatch):
        db = _ep_db(user=SimpleNamespace(id="u1"), device=SimpleNamespace(status="x"))
        ws = FakeWebSocket(incoming=[
            {"type": "register", "device_node_id": "dev1", "device_info": {}},
            ValueError("boom"),
        ])
        self._run(monkeypatch, ws, db)


class _ctx:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *a):
        return False


class TestDeviceCommandHelpers:
    def _mgr(self, monkeypatch, ws):
        mgr = DeviceConnectionManager()
        monkeypatch.setattr(dw, "_device_connection_manager", mgr)
        return mgr

    def test_not_connected_device_in_db(self, monkeypatch):
        mgr = self._mgr(monkeypatch, None)
        db = _ep_db(device=SimpleNamespace(status="offline"))
        with pytest.raises(ValueError):
            run(send_device_command("devX", "cmd", {}, db))

    def test_not_connected_device_unknown(self, monkeypatch):
        self._mgr(monkeypatch, None)
        db = _ep_db(device=None)
        with pytest.raises(ValueError):
            run(send_device_command("devX", "cmd", {}, db))

    def test_result_success(self, monkeypatch):
        ws = FakeWebSocket(auto_result={"type": "result", "success": True, "data": {"d": 1}})
        mgr = self._mgr(monkeypatch, ws)
        run(mgr.connect(ws, "dev1", "u1", {}))
        res = run(send_device_command("dev1", "cmd", {}, _ep_db()))
        assert res["success"] is True

    def test_result_failure(self, monkeypatch):
        ws = FakeWebSocket(auto_result={"type": "result", "success": False, "error": "e"})
        mgr = self._mgr(monkeypatch, ws)
        run(mgr.connect(ws, "dev1", "u1", {}))
        res = run(send_device_command("dev1", "cmd", {}, _ep_db()))
        assert res["success"] is False and res["error"] == "e"

    def test_error_response(self, monkeypatch):
        ws = FakeWebSocket(auto_result={"type": "error", "error": "bad"})
        mgr = self._mgr(monkeypatch, ws)
        run(mgr.connect(ws, "dev1", "u1", {}))
        res = run(send_device_command("dev1", "cmd", {}, _ep_db()))
        assert res["success"] is False and res["error"] == "bad"

    def test_unexpected_response_type(self, monkeypatch):
        ws = FakeWebSocket(auto_result={"type": "weird"})
        mgr = self._mgr(monkeypatch, ws)
        run(mgr.connect(ws, "dev1", "u1", {}))
        res = run(send_device_command("dev1", "cmd", {}, _ep_db()))
        assert res["success"] is False

    def test_info_helpers(self, monkeypatch):
        mgr = self._mgr(monkeypatch, None)
        mgr.device_info["dev1"] = {"capabilities": ["gps"]}
        mgr.active_connections["dev1"] = FakeWebSocket()
        assert get_connected_devices_info()[0]["device_node_id"] == "dev1"
        assert is_device_online("dev1") is True
        assert is_device_online("dev2") is False


# =========================================================================== #
# 2. core/memory/memory_consolidation_service.py
# =========================================================================== #
import core.memory.memory_consolidation_service as mcs
from core.memory.memory_consolidation_service import (
    MemoryConsolidationService,
    get_consolidation_service,
)
from core.models import Episode
from core.memory.pomdp_memory_framework import MemoryEntry, MemoryStatus


class FakeMemoryManager:
    def __init__(self):
        self._episodic_memory = {}

    def trigger_manage_cycle(self):
        return {"managed": 1}

    def get_memory_statistics(self):
        return {"total": len(self._episodic_memory)}


def _fake_episode(**kw):
    base = dict(
        id="ep-1", agent_id="a1", tenant_id="t1", started_at=datetime.now(timezone.utc),
        task_description="do the thing", maturity_at_time="AUTONOMOUS",
        human_intervention_count=0, total_steps=10, importance_score=0.9,
    )
    base.update(kw)
    return SimpleNamespace(**base)


class _bad_episode:
    """Episode stub whose attribute access raises mid-sync."""

    id = "e-bad"
    agent_id = "a1"
    tenant_id = "t1"
    started_at = None
    maturity_at_time = "AUTONOMOUS"
    human_intervention_count = 0
    total_steps = 5
    importance_score = 0.5

    @property
    def task_description(self):
        raise RuntimeError("broken episode")


def _fake_memory(mid="m1", agent="a1", quality=0.9, created=None, status=None,
                 task_type="WORKFLOW", access=15, observation=True):
    obs = SimpleNamespace(agent_id=agent, task_type=task_type) if observation else None
    return SimpleNamespace(
        id=mid, observation=obs, quality_score=quality,
        created_at=created or datetime.now(),
        status=status or MemoryStatus.CONSOLIDATED,
        access_count=access, learning_value=0.5,
        success_outcome=True, intervention_required=False,
    )


@pytest.fixture()
def mem_svc(monkeypatch):
    monkeypatch.setattr(mcs, "get_lancedb_handler", lambda: mock.MagicMock())
    lifecycle = mock.MagicMock()
    lifecycle.consolidate_similar_episodes = mock.AsyncMock(return_value={"consolidated": 2})
    lifecycle.decay_old_episodes = mock.AsyncMock(return_value={"affected": 3, "expired": 1})
    monkeypatch.setattr(mcs, "EpisodeLifecycleService", lambda db: lifecycle)
    fmm = FakeMemoryManager()
    monkeypatch.setattr(mcs, "get_memory_manager", lambda db, ldb: fmm)
    pomdp = mock.MagicMock()
    pomdp.consolidate_memories = mock.AsyncMock(return_value=7)
    monkeypatch.setattr(mcs, "MemoryConsolidation", lambda mm: pomdp)
    svc = MemoryConsolidationService(ModelDb())
    svc._fake_lifecycle = lifecycle
    svc._fake_pomdp = pomdp
    return svc


class TestMemoryConsolidation:
    def test_sync_without_pomdp(self, mem_svc, monkeypatch):
        monkeypatch.setattr(mcs, "POMDP_AVAILABLE", False)
        assert run(mem_svc.sync_episodes_to_memory("a1")) == {"synced": 0, "skipped": 0, "errors": 0}

    def test_sync_without_manager(self, mem_svc):
        mem_svc.memory_manager = None
        assert run(mem_svc.sync_episodes_to_memory("a1"))["synced"] == 0

    def test_sync_episodes(self, mem_svc):
        db = ModelDb()
        db.mapping = {Episode: _q([
            _fake_episode(id="e1"), _fake_episode(id="e2", human_intervention_count=2),
            _fake_episode(id="e3", maturity_at_time="INTERN", total_steps=None),
            _fake_episode(id="e4", started_at=None),
        ])}
        mem_svc.db = db
        res = run(mem_svc.sync_episodes_to_memory("a1", limit=10))
        assert res["synced"] == 4 and res["errors"] == 0
        assert "e1" in mem_svc.memory_manager._episodic_memory

    def test_sync_episode_error_path(self, mem_svc):
        db = ModelDb()
        db.mapping = {Episode: _q([_bad_episode()])}
        mem_svc.db = db
        res = run(mem_svc.sync_episodes_to_memory("a1"))
        assert res["errors"] == 1

    def test_infer_complexity_and_autonomy(self, mem_svc):
        f = mem_svc._infer_task_complexity
        assert f(_fake_episode(human_intervention_count=0, total_steps=10)) == 4
        assert f(_fake_episode(human_intervention_count=0, total_steps=2)) == 3
        assert f(_fake_episode(human_intervention_count=1)) == 2
        assert f(_fake_episode(human_intervention_count=5)) == 1
        g = mem_svc._infer_autonomy_level
        assert g(_fake_episode(maturity_at_time="STUDENT")) == 1
        assert g(_fake_episode(maturity_at_time="AUTONOMOUS")) == 4
        assert g(_fake_episode(maturity_at_time="WEIRD")) == 1

    def test_consolidation_already_running(self, mem_svc):
        mem_svc._consolidation_in_progress = True
        res = run(mem_svc.run_consolidation_cycle("a1"))
        assert res == {"consolidated": 0, "status": "already_running"}

    def test_consolidation_cycle_agent(self, mem_svc):
        res = run(mem_svc.run_consolidation_cycle("a1"))
        assert res["consolidated"] == 9  # 7 pomdp + 2 episode lifecycle
        assert mem_svc._last_consolidation is not None
        assert mem_svc._consolidation_in_progress is False

    def test_consolidation_cycle_all_agents(self, mem_svc):
        mem_svc.memory_manager._episodic_memory["x"] = _fake_memory(status=MemoryStatus.EXPIRED)
        res = run(mem_svc.run_consolidation_cycle(None))
        assert res["expired"] == 1 and res["consolidated"] == 0

    def test_consolidation_cycle_no_pomdp(self, mem_svc):
        mem_svc.pomdp_consolidation = None
        mem_svc.memory_manager = None
        res = run(mem_svc.run_consolidation_cycle("a1"))
        assert res["consolidated"] == 2

    def test_forgetting_curve_fallback(self, mem_svc, monkeypatch):
        monkeypatch.setattr(mcs, "POMDP_AVAILABLE", False)
        res = run(mem_svc.apply_forgetting_curve("a1"))
        assert res == {"affected": 3, "expired": 1}

    def test_forgetting_curve_decay_and_expire(self, mem_svc):
        old = datetime.now() - timedelta(days=91)
        m1 = _fake_memory("m1", quality=50.0, created=old)
        m2 = _fake_memory("m2", quality=0.5, created=old)
        m3 = _fake_memory("m3", agent="other", created=old)
        m4 = _fake_memory("m4", created=datetime.now())
        mem_svc.memory_manager._episodic_memory.update({"1": m1, "2": m2, "3": m3, "4": m4})
        res = run(mem_svc.apply_forgetting_curve("a1"))
        assert res["affected"] == 2 and res["expired"] == 1
        assert m2.status == MemoryStatus.EXPIRED

    def test_replay_no_pomdp(self, mem_svc):
        mem_svc.memory_manager = None
        assert run(mem_svc.replay_critical_memories("a1")) == []

    def test_replay_critical(self, mem_svc):
        m1 = _fake_memory("aaaaaaaa", quality=0.9, access=20)
        m2 = _fake_memory("bbbbbbbb", quality=0.9, access=1)  # below access threshold
        m3 = _fake_memory("cccccccc", quality=0.9, access=20, status=MemoryStatus.EXPIRED)
        m4 = _fake_memory("dddddddd", agent="other", quality=0.9, access=20)
        mem_svc.memory_manager._episodic_memory = {"1": m1, "2": m2, "3": m3, "4": m4}
        replayed = run(mem_svc.replay_critical_memories("a1", limit=5))
        assert len(replayed) == 1 and replayed[0]["memory_id"] == "aaaaaaaa"

    def test_extract_patterns_no_pomdp(self, mem_svc):
        mem_svc.memory_manager = None
        assert run(mem_svc.extract_patterns("a1")) == []

    def test_extract_patterns(self, mem_svc):
        for i in range(3):
            mem_svc.memory_manager._episodic_memory[str(i)] = _fake_memory(f"m{i}")
        mem_svc.memory_manager._episodic_memory["9"] = _fake_memory("m9", agent="other")
        mem_svc.memory_manager._episodic_memory["8"] = _fake_memory("m8", status=MemoryStatus.PENDING)
        patterns = run(mem_svc.extract_patterns("a1"))
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "WORKFLOW"
        assert patterns[0]["sample_size"] == 3

    def test_extract_patterns_no_observation_task_type(self, mem_svc):
        for i in range(3):
            mem_svc.memory_manager._episodic_memory[str(i)] = _fake_memory(f"m{i}", task_type=None)
        patterns = run(mem_svc.extract_patterns("a1"))
        assert patterns[0]["pattern_type"] == "UNKNOWN"

    def test_status_and_factory(self, mem_svc):
        st = mem_svc.get_consolidation_status()
        assert st["pomdp_available"] is True
        assert st["memory_statistics"]["total"] == 0
        assert get_consolidation_service(ModelDb()) is not None

    def test_pomdp_init_failure(self, monkeypatch):
        monkeypatch.setattr(mcs, "get_lancedb_handler", lambda: mock.MagicMock())
        monkeypatch.setattr(mcs, "EpisodeLifecycleService", lambda db: mock.MagicMock())
        def boom(db, ldb):
            raise RuntimeError("no pomdp")
        monkeypatch.setattr(mcs, "get_memory_manager", boom)
        svc = MemoryConsolidationService(ModelDb())
        assert svc.memory_manager is None
        assert svc.get_consolidation_status()["pomdp_available"] is False


# =========================================================================== #
# 3. core/fleet_orchestration/predictive_scaling_service.py
# =========================================================================== #
import core.fleet_orchestration.predictive_scaling_service as pss
from core.fleet_orchestration.predictive_scaling_service import (
    PredictiveScalingService,
    get_predictive_scaling_service,
)
from core.models import FleetPerformanceMetric, DelegationChain


def _metrics(values, hours_step=0.5):
    now = datetime.now(timezone.utc)
    out = []
    n = len(values)
    for i, v in enumerate(values):
        out.append(SimpleNamespace(
            window_start=now - timedelta(hours=(n - i) * hours_step),
            metric_value=v,
        ))
    return out


@pytest.fixture()
def scaling(monkeypatch):
    monkeypatch.setattr(pss, "PerformanceMetricsService", mock.MagicMock())
    prop = mock.MagicMock()
    prop.create_expansion_proposal = mock.AsyncMock(
        return_value=SimpleNamespace(id="prop-1"))
    monkeypatch.setattr(pss, "ScalingProposalService", lambda db=None: prop)
    svc = PredictiveScalingService(db=ModelDb())
    svc._fake_proposal = prop
    return svc


class TestPredictiveScaling:
    def test_analyze_trend_insufficient(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([1, 2, 3]))}
        res = scaling.analyze_trend("c1", "success_rate")
        assert res["direction"] == "unknown" and "error" in res

    def test_analyze_trend_directions(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([100 - i for i in range(20)]))}
        dec = scaling.analyze_trend("c1", "success_rate")
        assert dec["direction"] == "decreasing"
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([100 + i for i in range(20)]))}
        inc = scaling.analyze_trend("c1", "success_rate")
        assert inc["direction"] == "increasing"
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([100] * 20))}
        st = scaling.analyze_trend("c1", "success_rate")
        assert st["direction"] == "stable"

    def test_predict_breach_error(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([1]))}
        res = scaling.predict_threshold_breach("c1", "success_rate", 85.0)
        assert res["will_breach"] is False and res["confidence"] == "unknown"

    def test_predict_already_breached_below(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([80 - i for i in range(20)]))}
        res = scaling.predict_threshold_breach("c1", "success_rate", 85.0, "below")
        assert res["will_breach"] and res["hours_until_breach"] == 0

    def test_predict_no_breach_below(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([95 + i * 0.1 for i in range(20)]))}
        res = scaling.predict_threshold_breach("c1", "success_rate", 85.0, "below")
        assert res["will_breach"] is False and "stable or increasing" in res["message"]

    def test_predict_already_breached_above(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([600 + i for i in range(20)]))}
        res = scaling.predict_threshold_breach("c1", "avg_latency", 500, "above")
        assert res["will_breach"] and res["hours_until_breach"] == 0

    def test_predict_no_breach_above(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([400 - i for i in range(20)]))}
        res = scaling.predict_threshold_breach("c1", "avg_latency", 500, "above")
        assert res["will_breach"] is False

    def test_predict_breach_confidence_levels(self, scaling):
        # Clean downward trend -> high r_squared, breach predicted
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([95 - i for i in range(20)]))}
        res = scaling.predict_threshold_breach("c1", "success_rate", 85.0, "below")
        assert res["will_breach"] is True and res["hours_until_breach"] is not None
        # Noisy data -> confidence degrades relative to the clean fit
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics(
            [95, 70, 90, 60, 88, 65, 92, 62, 89, 64, 91, 66, 90, 63, 92, 61, 88, 67, 93, 60]))}
        res2 = scaling.predict_threshold_breach("c1", "success_rate", 85.0, "below")
        assert res2["confidence"] in ("low", "medium", "high")

    def test_linear_regression_edge_cases(self, scaling):
        assert scaling._linear_regression([], []) == (0.0, 0.0, 0.0)
        assert scaling._linear_regression([1.0], [5.0]) == (0.0, 5.0, 0.0)
        # denominator zero: identical x values
        assert scaling._linear_regression([2.0, 2.0], [1.0, 3.0])[1] == 2.0

    def test_proposal_chain_missing(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([1]))}
        res = run(scaling.generate_proactive_proposal("nope"))
        assert res["proposal_needed"] is False

    def test_proposal_no_reasons(self, scaling):
        scaling.db.mapping = {
            FleetPerformanceMetric: _q(_metrics([95 + i * 0.05 for i in range(20)])),
            DelegationChain: _q([SimpleNamespace(id="c1")]),
        }
        res = run(scaling.generate_proactive_proposal("c1"))
        assert res["proposal_needed"] is False
        assert res["reason"].startswith("No performance")

    def test_proposal_urgent(self, scaling):
        scaling.db.mapping = {
            FleetPerformanceMetric: _q(_metrics([95 - 2 * i for i in range(20)])),
            DelegationChain: _q([SimpleNamespace(id="c1")]),
        }
        res = run(scaling.generate_proactive_proposal("c1"))
        assert res["proposal_needed"] is True
        assert res["urgency"] >= 2

    def test_proposal_moderate_and_mild(self, scaling):
        # Slow decline -> breach beyond 12h but within 24h
        values = [95 - 0.4 * i for i in range(20)]
        scaling.db.mapping = {
            FleetPerformanceMetric: _q(_metrics(values, hours_step=1.0)),
            DelegationChain: _q([SimpleNamespace(id="c1")]),
        }
        res = run(scaling.generate_proactive_proposal("c1"))
        # Depending on fit, either no proposal or a moderate one — both valid.
        assert "reason" in res

    def test_seasonal_insufficient(self, scaling):
        scaling.db.mapping = {FleetPerformanceMetric: _q(_metrics([1] * 10))}
        res = scaling.detect_seasonal_pattern("c1", "success_rate")
        assert res["pattern_detected"] is False and "error" in res

    def test_seasonal_pattern(self, scaling):
        now = datetime.now(timezone.utc)
        base = (now - timedelta(days=8)).replace(hour=0, minute=0, second=0, microsecond=0)
        pts = []
        for d in range(7):
            for h in range(24):
                # Strong hour-of-day variation: peak at hour 12
                val = 100 if h == 12 else (10 if h in (0, 1, 2) else 50)
                pts.append(SimpleNamespace(
                    window_start=base + timedelta(days=d, hours=h), metric_value=val))
        scaling.db.mapping = {FleetPerformanceMetric: _q(pts)}
        res = scaling.detect_seasonal_pattern("c1", "success_rate")
        assert res["pattern_detected"] is True
        assert 12 in res["peak_hours"]

    def test_get_fleet_size(self, scaling):
        chain_q = mock.MagicMock()
        chain_q.filter.return_value.count.return_value = 4
        scaling.db.mapping = {"chainlink": chain_q}
        # _get_fleet_size imports ChainLink from core.models inside function
        from core.models import ChainLink
        scaling.db.mapping = {ChainLink: chain_q}
        assert scaling._get_fleet_size("c1") == 4

    def test_factory(self, scaling):
        svc = get_predictive_scaling_service(db=ModelDb())
        assert svc is not None


# =========================================================================== #
# 4. core/mcp_service.py
# =========================================================================== #
import core.mcp_service as mcp_mod
from core.mcp_service import MCPService, MCPTool, _is_error_result
from core.mcp_client import MCPClientError


@pytest.fixture()
def svc(monkeypatch):
    MCPService._instance = None
    s = MCPService()
    s.tool_registry = mock.MagicMock()
    s.tool_registry.get.return_value = None
    s.tool_registry.export_all.return_value = []
    yield s
    MCPService._instance = None


def _legacy(monkeypatch, tools=None, conns=None):
    import integrations.mcp_service as im
    legacy = mock.MagicMock()
    legacy.get_server_tools = mock.AsyncMock(return_value=tools or [])
    legacy.get_active_connections = mock.AsyncMock(return_value=conns or [])
    legacy.execute_tool = mock.AsyncMock(return_value="legacy-result")
    monkeypatch.setattr(im, "mcp_service", legacy)
    return legacy


def _patch_coding(monkeypatch, cas):
    """Install a fake core.coding_agent_service module (real one is optional)."""
    mod = types.ModuleType("core.coding_agent_service")
    mod.coding_agent_service = cas
    monkeypatch.setitem(sys.modules, "core.coding_agent_service", mod)
    return mod


class TestMCPToolModel:
    def test_is_error_result(self):
        assert _is_error_result({"error": "x"}) is True
        assert _is_error_result("Error: bad") is True
        assert _is_error_result({"ok": 1}) is False
        assert _is_error_result("fine") is False


class TestMCPRegister:
    def test_register_tool_new_and_duplicate(self, svc):
        t1 = MCPTool(name="t", description="d", server_id="s1")
        svc.register_tool(t1)
        svc.register_tool(MCPTool(name="t", description="d2", server_id="s1"))
        assert len(svc.tools_cache["s1"]) == 1
        assert svc.tools_cache["s1"][0].description == "d2"

    def test_get_server_tools_cached_and_legacy(self, svc, monkeypatch):
        svc.register_tool(MCPTool(name="t", description="d", server_id="s1"))
        tools = run(svc.get_server_tools("s1"))
        assert tools[0]["name"] == "t"
        legacy = _legacy(monkeypatch, tools=[{"name": "lt"}])
        assert (run(svc.get_server_tools("s2"))) == [{"name": "lt"}]
        assert legacy.get_server_tools.called

    def test_get_active_connections_bridge(self, svc, monkeypatch):
        legacy = _legacy(monkeypatch, conns=[{"id": "x"}])
        assert run(svc.get_active_connections()) == [{"id": "x"}]

    def test_register_server_legacy_local_tools(self, svc, monkeypatch):
        _legacy(monkeypatch, tools=[{"name": "lt", "description": "d", "parameters": {}}])
        run(svc.register_server("local-tools", {}))
        names = [t.name for t in svc.tools_cache["local-tools"]]
        assert "read_codebase" in names and "run_local_terminal" in names

    def test_register_server_local_tools_with_registry(self, svc, monkeypatch):
        _legacy(monkeypatch)
        svc.tool_registry.export_all.return_value = [
            {"name": "reg_tool", "description": "rd", "parameters": {}}]
        run(svc.register_server("local-tools", {}))
        names = [t.name for t in svc.tools_cache["local-tools"]]
        assert "reg_tool" in names

    def test_register_server_brightdata(self, svc, monkeypatch):
        _legacy(monkeypatch)
        run(svc.register_server("brightdata", {}))
        names = [t.name for t in svc.tools_cache["brightdata"]]
        assert "brightdata_search" in names and "brightdata_navigate" in names

    def test_refresh_tools_no_config(self, svc):
        run(svc.refresh_tools("unknown-server"))
        assert "unknown-server" not in svc.tools_cache

    def test_refresh_tools_external_success(self, svc, monkeypatch):
        client_cls = mock.MagicMock()
        client = client_cls.return_value
        client.initialize = mock.AsyncMock()
        client.list_tools = mock.AsyncMock(return_value=[
            {"name": "ext1", "description": "d", "inputSchema": {"type": "object"}}])
        monkeypatch.setattr(mcp_mod, "MCPClient", client_cls)
        run(svc.register_server("my-server", {"transport": "http"}))
        assert svc.tools_cache["my-server"][0].name == "ext1"
        assert "my-server" in svc.external_clients

    def test_refresh_tools_external_mcp_error(self, svc, monkeypatch):
        client_cls = mock.MagicMock()
        client_cls.return_value.initialize = mock.AsyncMock(
            side_effect=MCPClientError("handshake failed"))
        monkeypatch.setattr(mcp_mod, "MCPClient", client_cls)
        run(svc.register_server("bad-server", {"transport": "stdio"}))

    def test_refresh_tools_external_generic_error(self, svc, monkeypatch):
        client_cls = mock.MagicMock()
        client_cls.return_value.initialize = mock.AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(mcp_mod, "MCPClient", client_cls)
        run(svc.register_server("bad-server2", {"transport": "http"}))

    def test_get_available_tools_with_cache(self, svc):
        svc.register_tool(MCPTool(name="t", description="d", server_id="s1"))
        tools = run(svc.get_available_tools())
        assert tools[0].name == "t"

    def test_get_available_tools_empty_initializes_defaults(self, svc, monkeypatch):
        _legacy(monkeypatch)
        refreshed = []
        async def fake_refresh(sid):
            refreshed.append(sid)
        monkeypatch.setattr(svc, "refresh_tools", fake_refresh)
        tools = run(svc.get_available_tools())
        assert refreshed == ["google-search", "local-tools", "brightdata"]

    def test_call_external_tool_not_connected(self, svc):
        with pytest.raises(MCPClientError):
            run(svc.call_external_tool("none", "t", {}))

    def test_call_external_tool(self, svc):
        client = mock.MagicMock()
        client.call_tool = mock.AsyncMock(return_value="ext-res")
        svc.external_clients["s"] = client
        assert run(svc.call_external_tool("s", "t", {})) == "ext-res"


class TestMCPExecuteTool:
    def _ctx(self):
        return {"agent_id": None, "tenant_id": "t1", "user_id": "u1"}

    def test_coding_tool(self, svc, monkeypatch):
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(return_value="file-content")
        _patch_coding(monkeypatch, cas)
        res = run(svc.execute_tool("read_codebase", {"file_path": "x"}, self._ctx()))
        assert res == "file-content"
        cas.read_codebase.assert_called_once()

    def test_coding_tool_typeerror(self, svc, monkeypatch):
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(side_effect=TypeError("sync/async mismatch"))
        _patch_coding(monkeypatch, cas)
        res = run(svc.execute_tool("read_codebase", {"file_path": "x"}, self._ctx()))
        assert "type error" in res["error"]

    def test_satellite_tool(self, svc, monkeypatch):
        sat = mock.MagicMock()
        sat.execute_local_tool = mock.AsyncMock(return_value="sat-res")
        monkeypatch.setattr("core.satellite_service.satellite_service", sat)
        res = run(svc.execute_tool("run_local_terminal", {"command": "ls"}, self._ctx()))
        assert res == "sat-res"

    def test_registry_tool(self, svc, monkeypatch):
        meta = mock.MagicMock()
        meta.function = mock.AsyncMock(return_value="reg-res")
        meta.cacheable = False
        svc.tool_registry.get.return_value = meta
        res = run(svc.execute_tool("my_reg_tool", {"x": 1}, self._ctx()))
        assert res == "reg-res"

    def test_legacy_fallback_with_registry(self, svc, monkeypatch):
        _legacy(monkeypatch)
        res = run(svc.execute_tool("some_unknown_tool", {}, self._ctx()))
        assert res == "legacy-result"

    def test_legacy_fallback_no_registry(self, svc, monkeypatch):
        svc.tool_registry = None
        _legacy(monkeypatch)
        res = run(svc.execute_tool("some_unknown_tool", {}, self._ctx()))
        assert res == "legacy-result"

    def test_tool_execution_generic_error(self, svc, monkeypatch):
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(side_effect=RuntimeError("boom"))
        _patch_coding(monkeypatch, cas)
        res = run(svc.execute_tool("read_codebase", {}, self._ctx()))
        assert res["status"] == "error"

    def test_string_truncation(self, svc, monkeypatch):
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(return_value="x" * 50000)
        _patch_coding(monkeypatch, cas)
        res = run(svc.execute_tool("read_codebase", {}, self._ctx()))
        assert len(res) < 33200 and "truncated" in res

    def test_dict_field_truncation(self, svc, monkeypatch):
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(return_value={"out": "y" * 50000})
        _patch_coding(monkeypatch, cas)
        res = run(svc.execute_tool("read_codebase", {}, self._ctx()))
        assert "truncated" in res["out"]

    def test_governance_block(self, svc, monkeypatch):
        govmod = mock.MagicMock()
        gov_service = govmod.AgentGovernanceService.return_value
        gov_service.enforce_action.return_value = {
            "proceed": False, "reason": "not allowed", "status": "blocked",
            "action_required": "approval"}
        monkeypatch.setattr("core.agent_governance_service.AgentGovernanceService",
                            govmod.AgentGovernanceService)
        sess = mock.MagicMock()
        sess.__enter__ = lambda s: mock.MagicMock()
        sess.__exit__ = lambda s, *a: False
        monkeypatch.setattr("core.database.SessionLocal", lambda: sess)
        res = run(svc.execute_tool("read_codebase", {},
                                   {"agent_id": "a1", "tenant_id": "t1"}))
        assert res["error"].startswith("Governance Block")

    def test_governance_failure(self, svc, monkeypatch):
        govmod = mock.MagicMock()
        govmod.AgentGovernanceService.return_value.enforce_action.side_effect = RuntimeError("db down")
        monkeypatch.setattr("core.agent_governance_service.AgentGovernanceService",
                            govmod.AgentGovernanceService)
        sess = mock.MagicMock()
        sess.__enter__ = lambda s: mock.MagicMock()
        sess.__exit__ = lambda s, *a: False
        monkeypatch.setattr("core.database.SessionLocal", lambda: sess)
        res = run(svc.execute_tool("read_codebase", {},
                                   {"agent_id": "a1", "tenant_id": "t1"}))
        assert res["error"] == "Security check failed."

    def test_governance_skip_without_agent(self, svc, monkeypatch):
        # critical tool with no agent_id -> no governance import attempted
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(return_value="ok")
        _patch_coding(monkeypatch, cas)
        res = run(svc.execute_tool("read_codebase", {}, {}))
        assert res == "ok"

    def test_sandbox_blocked_enforced(self, svc, monkeypatch):
        monkeypatch.setattr(mcp_mod, "_sandbox_enabled", lambda: True)
        decision = SimpleNamespace(
            requires_review=True, enforced=True, decision="denied",
            violation_detail="bad path", phase="A", violation_type="fs")
        monkeypatch.setattr(mcp_mod, "_sandbox_check", lambda **kw: decision)
        res = run(svc.execute_tool("read_codebase", {}, {}))
        assert res["status"] == "sandbox_blocked"

    def test_sandbox_shadow_review(self, svc, monkeypatch):
        monkeypatch.setattr(mcp_mod, "_sandbox_enabled", lambda: True)
        decision = SimpleNamespace(
            requires_review=True, enforced=False, decision="review",
            violation_detail="x", phase="A", violation_type="fs")
        monkeypatch.setattr(mcp_mod, "_sandbox_check", lambda **kw: decision)
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(return_value="ok")
        _patch_coding(monkeypatch, cas)
        res = run(svc.execute_tool("read_codebase", {}, {}))
        assert res == "ok"

    def test_sandbox_enabled_allowed(self, svc, monkeypatch):
        monkeypatch.setattr(mcp_mod, "_sandbox_enabled", lambda: True)
        decision = SimpleNamespace(requires_review=False, enforced=False)
        monkeypatch.setattr(mcp_mod, "_sandbox_check", lambda **kw: decision)
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(return_value="ok")
        _patch_coding(monkeypatch, cas)
        assert run(svc.execute_tool("read_codebase", {}, {})) == "ok"

    def test_sandbox_helpers_fail_open(self, monkeypatch):
        import core.sandbox_config as sc
        monkeypatch.setattr(sc, "is_sandbox_enabled", lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert mcp_mod._sandbox_enabled() is False

    def test_sandbox_check_no_run_context(self):
        assert mcp_mod._sandbox_check("tool", {}, {}) is None
        assert mcp_mod._sandbox_check("tool", {}, {"run_id": "r"}) is None  # no tier
        assert mcp_mod._sandbox_check("tool", {}, {"run_id": "r", "tier": "x"}) is not None

    def test_tool_cache_hit(self, svc, monkeypatch):
        import core.hallucination_config as hc
        monkeypatch.setattr(hc, "is_tool_cache_enabled", lambda: True)
        monkeypatch.setattr(hc, "get_tool_cache_ttl", lambda: 60)
        svc.tool_registry.get.return_value = None
        calls = []
        async def fake_read(*a, **k):
            calls.append("read")
            return "fresh"
        _patch_coding(monkeypatch, mock.MagicMock(read_codebase=fake_read))
        r1 = run(svc.execute_tool("read_codebase", {"file_path": "x"}, {"tenant_id": "t1"}))
        r2 = run(svc.execute_tool("read_codebase", {"file_path": "x"}, {"tenant_id": "t1"}))
        assert r1 == "fresh" and r2 == "fresh"
        assert len(calls) == 1  # second call served from cache

    def test_tool_cache_not_cached_errors(self, svc, monkeypatch):
        import core.hallucination_config as hc
        monkeypatch.setattr(hc, "is_tool_cache_enabled", lambda: True)
        monkeypatch.setattr(hc, "get_tool_cache_ttl", lambda: 60)
        import integrations.mcp_service as im
        legacy = mock.MagicMock()
        legacy.execute_tool = mock.AsyncMock(return_value={"error": "bad"})
        monkeypatch.setattr(im, "mcp_service", legacy)
        run(svc.execute_tool("get_all_tools", {}, {"tenant_id": "t"}))
        assert svc._tool_cache == {}

    def test_tool_cache_disabled_ttl(self, svc, monkeypatch):
        import core.hallucination_config as hc
        monkeypatch.setattr(hc, "get_tool_cache_ttl", lambda: 0)
        svc._tool_cache_put("k", "v")
        assert "k" not in svc._tool_cache

    def test_tool_cache_expiry_and_eviction(self, svc):
        svc._tool_cache["old"] = (time.monotonic() - 100, "x")
        assert svc._tool_cache_get("old") is None
        assert "old" not in svc._tool_cache
        # Bounded eviction
        import core.hallucination_config as hc_real
        with mock.patch.object(hc_real, "get_tool_cache_ttl", lambda: 60):
            for i in range(mcp_mod._MAX_TOOL_CACHE_ENTRIES + 5):
                svc._tool_cache_put(f"k{i}", i)
        assert len(svc._tool_cache) <= mcp_mod._MAX_TOOL_CACHE_ENTRIES

    def test_tool_cache_key_stability(self, svc):
        k1 = svc._tool_cache_key("t", {"a": 1, "b": 2}, {"tenant_id": "x"})
        k2 = svc._tool_cache_key("t", {"b": 2, "a": 1}, {"tenant_id": "x"})
        k3 = svc._tool_cache_key("t", {"a": 1, "b": 2}, {"tenant_id": "y"})
        assert k1 == k2 and k1 != k3

    def test_call_tool_alias(self, svc, monkeypatch):
        cas = mock.MagicMock()
        cas.read_codebase = mock.AsyncMock(return_value="ok")
        _patch_coding(monkeypatch, cas)
        assert run(svc.call_tool("read_codebase", {}, {})) == "ok"

    def test_tool_is_cacheable(self, svc):
        svc.tool_registry = None
        assert svc._tool_is_cacheable("read_codebase") is True
        assert svc._tool_is_cacheable("write_code_file") is False
        svc.tool_registry = mock.MagicMock()
        meta = mock.MagicMock(cacheable=True)
        svc.tool_registry.get.return_value = meta
        assert svc._tool_is_cacheable("anything") is True


# =========================================================================== #
# 5. core/security/middleware.py
# =========================================================================== #
import core.security.middleware as secmw
from core.security.middleware import (
    InputValidationMiddleware,
    SecurityHeadersMiddleware,
    CSRFProtectionMiddleware,
    RateLimitMiddleware,
    ExternalAPIRateLimitMiddleware,
    log_tenant_enumeration_attempt,
    validate_email,
    sanitize_input,
    generate_api_key,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app(mw_cls, **kw):
    app = FastAPI()
    app.add_middleware(mw_cls, **kw)

    @app.get("/hello")
    def hello():
        return {"ok": True}

    @app.get("/api/hello")
    def api_hello():
        return {"ok": True}

    @app.post("/hello")
    def hello_post():
        return {"ok": True}

    @app.post("/api/skills/import")
    def skill_import():
        return {"ok": True}

    @app.post("/api/external/v1/ping")
    def ext_ping():
        return {"ok": True}

    return app


class TestInputValidationMiddleware:
    def test_clean_get(self):
        client = TestClient(_build_app(InputValidationMiddleware))
        assert client.get("/hello", params={"q": "ok"}).status_code == 200

    def test_malicious_query(self):
        client = TestClient(_build_app(InputValidationMiddleware))
        r = client.get("/hello", params={"q": "javascript:alert(1)"})
        assert r.status_code == 400

    def test_malicious_body(self):
        client = TestClient(_build_app(InputValidationMiddleware))
        r = client.post("/hello", json={"x": "<script>alert(1)</script>"})
        assert r.status_code == 400

    def test_entity_encoded_body(self):
        client = TestClient(_build_app(InputValidationMiddleware))
        r = client.post("/hello", content=b'{"x": "jav&#x61;script:alert(1)"}',
                        headers={"content-type": "application/json"})
        assert r.status_code == 400

    def test_clean_body(self):
        client = TestClient(_build_app(InputValidationMiddleware))
        assert client.post("/hello", json={"x": "fine"}).status_code == 200

    def test_skip_path(self):
        client = TestClient(_build_app(InputValidationMiddleware))
        assert client.post("/api/skills/import", content=b"def execute(inputs): pass",
                           headers={"content-type": "text/plain"}).status_code == 200

    def test_body_too_large(self):
        app = _build_app(InputValidationMiddleware)
        app.user_middleware.clear()
        app.add_middleware(InputValidationMiddleware)
        # Build with tiny cap
        mw = InputValidationMiddleware(app, )
        mw.max_body_bytes = 10
        client = TestClient(mw)
        r = client.post("/hello", content=b"x" * 100)
        assert r.status_code == 413

    def test_materialized_body_too_large(self):
        app = _build_app(InputValidationMiddleware)
        mw = InputValidationMiddleware(app)
        mw.max_body_bytes = 5
        client = TestClient(mw)
        r = client.post("/hello", content=b"x" * 50)
        assert r.status_code == 413

    def test_scan_failure_fails_closed(self, monkeypatch):
        app = _build_app(InputValidationMiddleware)
        mw = InputValidationMiddleware(app)
        async def boom(request):
            raise RuntimeError("scan broke")
        monkeypatch.setattr(mw, "_read_body_with_limit", boom)
        client = TestClient(mw)
        assert client.post("/hello", content=b"{}").status_code == 400

    def test_contains_malicious_content(self):
        mw = InputValidationMiddleware(_build_app(InputValidationMiddleware))
        for bad in ["<script>x</script>", "onerror=", "union select", "drop table",
                    "expression(", "vbscript:", "behavior:", "binding:", "eval("]:
            assert mw._contains_malicious_content(bad) is True
        assert mw._contains_malicious_content("totally fine") is False


class TestSecurityHeadersMiddleware:
    def test_api_headers(self):
        client = TestClient(_build_app(SecurityHeadersMiddleware))
        r = client.get("/api/hello")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" not in r.headers

    def test_html_headers(self):
        client = TestClient(_build_app(SecurityHeadersMiddleware))
        r = client.get("/hello")
        # path /hello does not start with /api/ -> full header set
        assert "Strict-Transport-Security" in r.headers
        assert "unsafe-eval" not in r.headers["Content-Security-Policy"]


class TestCSRFMiddleware:
    def _client(self):
        return TestClient(_build_app(CSRFProtectionMiddleware))

    def test_safe_methods_pass(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("PYTEST_VERSION", raising=False)
        assert self._client().get("/hello").status_code == 200

    def test_exempt_paths(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("PYTEST_VERSION", raising=False)
        app = FastAPI()
        app.add_middleware(CSRFProtectionMiddleware)

        @app.post("/api/auth/login")
        def login():
            return {"ok": True}
        assert TestClient(app).post("/api/auth/login").status_code == 200

    def test_missing_token_403(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("PYTEST_VERSION", raising=False)
        assert self._client().post("/hello").status_code == 403

    def test_invalid_token_403(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("PYTEST_VERSION", raising=False)
        r = self._client().post("/hello", headers={"X-CSRF-Token": "junk"})
        assert r.status_code == 403

    def test_bearer_passes(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("PYTEST_VERSION", raising=False)
        r = self._client().post("/hello", headers={"Authorization": "Bearer abc"})
        assert r.status_code == 200

    def test_test_secret_bypass(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
        monkeypatch.setenv("E2E_TEST_SECRET", "sec")
        r = self._client().post("/hello", headers={"x-test-secret": "sec"})
        assert r.status_code == 200

    def test_generate_and_validate_token(self, monkeypatch):
        mw = CSRFProtectionMiddleware(_build_app(CSRFProtectionMiddleware))
        mw.cache = mock.MagicMock()
        mw.cache.get.return_value = {"session_id": "s"}
        token = mw.generate_csrf_token("s1")
        assert mw._validate_csrf_token(token) is True
        mw.cache.get.return_value = None
        assert mw._validate_csrf_token(token) is False


class TestRateLimitMiddleware:
    def _client(self):
        return TestClient(_build_app(RateLimitMiddleware, requests_per_minute=100))

    def test_exempt_path(self):
        assert self._client().post("/api/webhooks/x").status_code in (200, 404)

    def test_health_exempt(self):
        assert self._client().get("/health").status_code in (200, 404)

    def test_normal_request_with_cache_disabled(self, monkeypatch):
        c = self._client()
        monkeypatch.setattr(secmw.cache, "enabled", False)
        r = c.get("/hello")
        assert r.status_code == 200

    def test_test_secret_bypass(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
        r = self._client().get("/hello", headers={"x-test-secret": "any"})
        assert r.status_code == 200

    def test_tenant_limits_local_cache_hit(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw._local_limit_cache["t9"] = {"limits": (5, 6), "expiry": time.time() + 100}
        assert mw._get_tenant_limits_sync("t9") == (5, 6)

    def test_tenant_limits_local_expired(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw._local_limit_cache["t8"] = {"limits": (5, 6), "expiry": time.time() - 10}
        mw.cache = mock.MagicMock()
        mw.cache.get.return_value = None
        assert mw._get_tenant_limits_sync(None) == (1000, 100000)

    def test_tenant_limits_redis_hit(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.get.return_value = {"limits": {"requests_per_minute": 42, "requests_per_day": 420}}
        assert mw._get_tenant_limits_sync("t7") == (42, 420)

    def test_tenant_limits_redis_error_then_system(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.get.side_effect = RuntimeError("redis down")
        assert mw._get_tenant_limits_sync("system") == (1000, 100000)

    def test_tenant_limits_db_fallback(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.get.return_value = None
        tenant = SimpleNamespace(plan_type="pro")
        sess = ModelDb()
        from core.models import Tenant
        sess.mapping = {Tenant: _q([tenant])}
        mw_db = SimpleNamespace(SessionLocal=lambda: _ctx(sess))
        with mock.patch.object(secmw, "SessionLocal", lambda: sess):
            limits = mw._get_tenant_limits_sync("real-tenant")
        assert limits[0] > 0

    def test_tenant_limits_db_fallback_importerror(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.get.return_value = None
        tenant = SimpleNamespace(plan_type="pro")
        sess = ModelDb()
        from core.models import Tenant
        sess.mapping = {Tenant: _q([tenant])}
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "core.quota_manager":
                raise ImportError("nope")
            return real_import(name, *a, **k)
        with mock.patch.object(secmw, "SessionLocal", lambda: sess), \
             mock.patch("builtins.__import__", side_effect=fake_import):
            limits = mw._get_tenant_limits_sync("real-tenant")
        assert limits == (100, 5000)

    def test_tenant_limits_db_no_tenant(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.get.return_value = None
        sess = ModelDb()
        from core.models import Tenant
        sess.mapping = {Tenant: _q([])}
        with mock.patch.object(secmw, "SessionLocal", lambda: sess):
            assert mw._get_tenant_limits_sync("ghost") == (100, 100000)

    def test_check_rate_limit_cache_disabled(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.enabled = False
        assert mw._check_rate_limit_sync("id", "ip", 10, 100) == (False, {})

    def test_check_rate_limit_minute_block(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.enabled = True
        mw.cache.client = mock.MagicMock()
        mw._local_requests["id"] = {
            "minute": int(time.time()) // 60, "day": time.strftime("%Y-%m-%d"),
            "min_count": 99, "day_count": 100, "last_sync": int(time.time())}
        blocked, result = mw._check_rate_limit_sync("id", "ip", 10, 1000)
        assert blocked is True and result.status_code == 429

    def test_check_rate_limit_day_block(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.enabled = True
        mw.cache.client = mock.MagicMock()
        mw._local_requests["id2"] = {
            "minute": int(time.time()) // 60, "day": time.strftime("%Y-%m-%d"),
            "min_count": 1, "day_count": 999, "last_sync": 0}
        blocked, result = mw._check_rate_limit_sync("id2", "ip", 100, 10)
        assert blocked is True and result.status_code == 429

    def test_check_rate_limit_allows_and_syncs(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.enabled = True
        mw.cache.client = mock.MagicMock()
        mw._local_requests["id3"] = {
            "minute": (int(time.time()) // 60) - 5, "day": "2000-01-01",
            "min_count": 50, "day_count": 50, "last_sync": 0}
        blocked, headers = mw._check_rate_limit_sync("id3", "ip", 100, 1000)
        assert blocked is False and "X-RateLimit-Limit" in headers
        assert mw.cache.client.pipeline.called

    def test_check_rate_limit_exception_fails_open(self):
        mw = RateLimitMiddleware(_build_app(RateLimitMiddleware), requests_per_minute=100)
        mw.cache = mock.MagicMock()
        mw.cache.enabled = True
        mw.cache.client.pipeline.side_effect = RuntimeError("x")
        mw._local_requests["idx"] = {
            "minute": int(time.time()) // 60, "day": time.strftime("%Y-%m-%d"),
            "min_count": 5, "day_count": 5, "last_sync": 0}
        assert mw._check_rate_limit_sync("idx", "ip", 100, 1000) == (False, {})


class TestExternalAPIRateLimitMiddleware:
    def _client(self):
        return TestClient(_build_app(ExternalAPIRateLimitMiddleware, requests_per_minute=100))

    def test_non_external_path(self):
        assert self._client().get("/hello").status_code == 200

    def test_missing_key_401(self):
        assert self._client().post("/api/external/v1/ping").status_code == 401

    def test_with_key_ok(self):
        r = self._client().post("/api/external/v1/ping", headers={"X-External-API-Key": "k"})
        assert r.status_code == 200

    def test_over_limit_429(self):
        client = self._client()
        mw_app = client.app
        ext = None
        for m in mw_app.user_middleware:
            if m.cls is ExternalAPIRateLimitMiddleware:
                ext = m
        assert ext is not None
        # Simulate a near-limit local state, then exceed via request
        app = _build_app(ExternalAPIRateLimitMiddleware, requests_per_minute=1)
        client2 = TestClient(app)
        # find middleware instance by issuing one request then mutating
        r1 = client2.post("/api/external/v1/ping", headers={"X-External-API-Key": "k"})
        assert r1.status_code == 200
        # second request exceeds limit of 1
        r2 = client2.post("/api/external/v1/ping", headers={"X-External-API-Key": "k"})
        assert r2.status_code == 429

    def test_stale_entry_eviction(self):
        app = _build_app(ExternalAPIRateLimitMiddleware)
        mw = ExternalAPIRateLimitMiddleware(app)
        old_minute = (int(time.time()) // 60) - 10
        for i in range(10005):
            mw._local_requests[f"key{i}"] = {"minute": old_minute, "count": 1, "last_sync": 0}
        client = TestClient(mw)
        r = client.post("/api/external/v1/ping", headers={"X-External-API-Key": "fresh"})
        assert r.status_code == 200
        assert len(mw._local_requests) < 100

    def test_redis_sync(self, monkeypatch):
        app = _build_app(ExternalAPIRateLimitMiddleware)
        mw = ExternalAPIRateLimitMiddleware(app)
        mw.cache = mock.MagicMock()
        mw.cache.enabled = True
        mw.cache.client = mock.MagicMock()
        client = TestClient(mw)
        for _ in range(6):
            r = client.post("/api/external/v1/ping", headers={"X-External-API-Key": "kk"})
        assert r.status_code == 200
        assert mw.cache.client.incrby.called


class TestMiddlewareUtilities:
    def test_log_tenant_enumeration(self):
        req = mock.MagicMock()
        req.url.path = "/x"
        req.method = "GET"
        req.client.host = "1.2.3.4"
        log_tenant_enumeration_attempt(req, "verylongtenantid")
        log_tenant_enumeration_attempt(req, "short")
        req2 = mock.MagicMock()
        req2.client = None
        log_tenant_enumeration_attempt(req2, "x")

    def test_log_tenant_enumeration_outer_failure(self):
        req = mock.MagicMock()
        req.url = mock.PropertyMock(side_effect=RuntimeError("x"))
        log_tenant_enumeration_attempt(req, "x")

    def test_validate_email(self):
        assert validate_email("a@b.com") is True
        assert validate_email("bad") is False

    def test_sanitize_input(self):
        assert sanitize_input("") == ""
        assert sanitize_input("<b>x</b>") == "x"
        assert sanitize_input('a"b<c>') == "ab"

    def test_generate_api_key(self):
        assert len(generate_api_key()) > 20


# =========================================================================== #
# 6. core/condition_checkers.py
# =========================================================================== #
from core.condition_checkers import (
    ConditionCheckers,
    ConditionCheckerFactory,
    CONDITION_TYPE_INBOX_VOLUME,
    CONDITION_TYPE_TASK_BACKLOG,
    CONDITION_TYPE_API_METRICS,
    CONDITION_TYPE_DATABASE_QUERY,
    CONDITION_TYPE_COMPOSITE,
)
from core.models import AgentExecution, TeamMessage, ConditionMonitor


def _monitor(ctype, threshold=None, **kw):
    mon = SimpleNamespace(
        condition_type=ctype,
        threshold_config=threshold or {},
        composite_logic=kw.get("logic", "AND"),
        composite_conditions=kw.get("conditions"),
        user_id="u1", name="mon", agent_id="a1", agent_name="A",
    )
    return mon


class TestConditionCheckers:
    def test_inbox_volume_triggered(self):
        db = _fixed_db(_scalar_seq([120]))
        ck = ConditionCheckers(db)
        res = ck.check_condition(_monitor(CONDITION_TYPE_INBOX_VOLUME, {"operator": ">", "value": 100}))
        assert res["triggered"] is True and res["value"] == 120

    def test_inbox_volume_not_triggered(self):
        db = ModelDb()
        db.mapping = {TeamMessage: _q([5])}
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_INBOX_VOLUME, {"operator": ">", "value": 100}))
        assert res["triggered"] is False

    def test_task_backlog(self):
        db = _fixed_db(_scalar_seq([60]))
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_TASK_BACKLOG, {"operator": ">", "value": 50}))
        assert res["triggered"] is True

    def test_unknown_type(self):
        res = ConditionCheckers(ModelDb()).check_condition(_monitor("bogus"))
        assert res["triggered"] is False and "Unknown type" in res["metric_name"]

    def test_api_metrics_error_rate(self):
        db = _fixed_db(_scalar_seq([100, 10]))  # total then failed
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_API_METRICS,
                     {"metric": "error_rate", "operator": ">", "value": 0.05, "window": "1h"}))
        assert abs(res["value"] - 0.1) < 1e-9

    def test_api_metrics_error_rate_zero_total(self):
        db = _fixed_db(_scalar_seq([0, 0]))
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_API_METRICS, {"metric": "error_rate"}))
        assert res["value"] == 0.0

    def test_api_metrics_numeric_and_bad_window(self):
        db = _fixed_db(_scalar_seq([10, 1]))
        for window in (5, "15m", "2h", "not-a-number", None):
            res = ConditionCheckers(db).check_condition(
                _monitor(CONDITION_TYPE_API_METRICS, {"metric": "error_rate", "window": window}))
            assert "error rate" in res["metric_name"]

    def test_api_metrics_response_time_p95(self):
        now = datetime.now(timezone.utc)
        execs = [
            SimpleNamespace(started_at=now, completed_at=now + timedelta(seconds=2)),
            SimpleNamespace(started_at=now, completed_at=now + timedelta(seconds=4)),
            SimpleNamespace(started_at=now, completed_at=None),
        ]
        db = ModelDb()
        db.mapping = {AgentExecution: _q(execs)}
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_API_METRICS, {"metric": "response_time_p95", "operator": ">", "value": 1}))
        assert res["value"] == 3.0 and res["triggered"] is True

    def test_api_metrics_response_time_no_execs(self):
        db = ModelDb()
        db.mapping = {AgentExecution: _q([])}
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_API_METRICS, {"metric": "response_time_p95"}))
        assert res["value"] == 0.0

    def test_api_metrics_request_count(self):
        db = _fixed_db(_scalar_seq([42, 0]))
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_API_METRICS, {"metric": "request_count", "operator": ">", "value": 10}))
        assert res["value"] == 42 and res["triggered"] is True

    def test_api_metrics_unknown_metric(self):
        db = _fixed_db(_scalar_seq([1, 1]))
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_API_METRICS, {"metric": "bogus_metric"}))
        assert res["value"] == 0 and "Unknown metric" in res["metric_name"]

    def test_database_query(self):
        db = ModelDb()
        db._exec_result = _q([55])
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_DATABASE_QUERY,
                     {"query": "SELECT 55", "operator": ">", "value": 10}))
        assert res["triggered"] is True and res["value"] == 55

    def test_database_query_none_result(self):
        db = ModelDb()
        db._exec_result = _q([None])
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_DATABASE_QUERY, {"query": "SELECT NULL"}))
        assert res["value"] == 0

    def test_database_query_error(self):
        db = ModelDb()

        def boom(*a, **k):
            raise RuntimeError("sql error")
        db.execute = boom
        res = ConditionCheckers(db).check_condition(
            _monitor(CONDITION_TYPE_DATABASE_QUERY, {"query": "BAD"}))
        assert res["triggered"] is False and "Query error" in res["details"]

    def test_composite_empty(self):
        res = ConditionCheckers(ModelDb()).check_condition(
            _monitor(CONDITION_TYPE_COMPOSITE, conditions=[]))
        assert res["triggered"] is False

    def test_composite_and_or(self):
        db = _fixed_db(_scalar_seq([200, 5]))
        ck = ConditionCheckers(db)
        cond = [{"condition_type": "inbox_volume",
                 "threshold_config": {"operator": ">", "value": 100}},
                {"condition_type": "inbox_volume",
                 "threshold_config": {"operator": ">", "value": 100}}]
        res_and = ck.check_condition(_monitor(CONDITION_TYPE_COMPOSITE, conditions=cond, logic="AND"))
        assert res_and["triggered"] is False
        res_or = ck.check_condition(_monitor(CONDITION_TYPE_COMPOSITE, conditions=cond, logic="OR"))
        assert res_or["triggered"] is True
        assert len(res_or["sub_conditions"]) == 2

    def test_compare_operators(self):
        ck = ConditionCheckers(ModelDb())
        cmp_ = ck._compare_values
        assert cmp_(5, ">", 4) is True
        assert cmp_(5, ">=", 5) is True
        assert cmp_(4, "<", 5) is True
        assert cmp_(5, "<=", 5) is True
        assert cmp_(5, "==", 5) is True
        assert cmp_(5, "=", 5) is True
        assert cmp_(5, "!=", 4) is True
        assert cmp_(5, "~", 4) is False  # unknown operator
        assert cmp_(None, ">", 4) is False  # comparison error

    def test_factory(self):
        ck = ConditionCheckerFactory.create_checker("inbox_volume", ModelDb())
        assert isinstance(ck, ConditionCheckers)


# =========================================================================== #
# 7. core/debug_collector.py
# =========================================================================== #
import core.debug_collector as dcmod
from core.debug_collector import (
    DebugCollector,
    get_debug_collector,
    init_debug_collector,
)
from redis.exceptions import RedisError


@pytest.fixture(autouse=True)
def _reset_collector():
    dcmod._collector_instance = None
    yield
    dcmod._collector_instance = None


class TestDebugCollector:
    def test_start_stop(self):
        async def body():
            c = DebugCollector()
            c.start()
            assert c.get_buffer_stats()["running"] is True
            c.start()  # already running -> warning path
            c.stop()
            c.stop()  # idempotent
            await asyncio.sleep(0)
            assert c.get_buffer_stats()["running"] is False
        run(body())

    def test_collect_event_no_redis(self):
        async def body():
            c = DebugCollector()
            ev = await c.collect_event("log", "agent", "a1", "corr", level="INFO",
                                       message="m", data={"x": 1})
            assert ev.event_type == "log"
            assert c.get_buffer_stats()["event_buffer_size"] == 1
        run(body())

    def test_collect_event_disabled(self, monkeypatch):
        async def body():
            monkeypatch.setattr(dcmod, "DEBUG_SYSTEM_ENABLED", False)
            c = DebugCollector()
            assert await c.collect_event("log", "agent", "a", "c") is None
        run(body())

    def test_collect_event_with_redis(self):
        async def body():
            r = mock.MagicMock()
            c = DebugCollector(redis_client=r)
            await c.collect_event("log", "agent", "a", "c")
            assert r.publish.called
            r.publish.side_effect = RedisError("down")
            ev = await c.collect_event("log", "agent", "a", "c")
            assert ev is not None  # error is logged, event still returned
        run(body())

    def test_collect_event_exception(self, monkeypatch):
        async def body():
            c = DebugCollector()
            with mock.patch.object(dcmod, "DebugEvent", side_effect=RuntimeError("x")):
                assert await c.collect_event("log", "agent", "a", "c") is None
        run(body())

    def test_collect_state_snapshot(self):
        async def body():
            r = mock.MagicMock()
            c = DebugCollector(redis_client=r)
            snap = await c.collect_state_snapshot("agent", "a1", "op1", {"s": 1},
                                                  checkpoint_name="cp", diff_from_previous={"d": 1})
            assert snap.component_type == "agent"
            assert r.publish.called
            r.publish.side_effect = RedisError("down")
            snap2 = await c.collect_state_snapshot("agent", "a1", "op1", {})
            assert snap2 is not None
            # no client
            c2 = DebugCollector()
            await c2._publish_snapshot(snap2)
        run(body())

    def test_collect_state_snapshot_disabled(self, monkeypatch):
        async def body():
            monkeypatch.setattr(dcmod, "DEBUG_SYSTEM_ENABLED", False)
            c = DebugCollector()
            assert await c.collect_state_snapshot("a", "b", "c", {}) is None
        run(body())

    def test_collect_state_snapshot_exception(self, monkeypatch):
        async def body():
            c = DebugCollector()
            with mock.patch.object(dcmod, "DebugStateSnapshot", side_effect=RuntimeError("x")):
                assert await c.collect_state_snapshot("a", "b", "c", {}) is None
        run(body())

    def test_collect_batch_events(self):
        async def body():
            c = DebugCollector()
            events = [
                {"event_type": "log", "component_type": "agent", "component_id": "a",
                 "correlation_id": "c"},
                {"bad_kwarg": True},
            ]
            out = await c.collect_batch_events(events)
            assert out[0] is not None and out[1] is None
        run(body())

    def test_collect_batch_disabled(self, monkeypatch):
        async def body():
            monkeypatch.setattr(dcmod, "DEBUG_SYSTEM_ENABLED", False)
            assert await DebugCollector().collect_batch_events([{}]) == []
        run(body())

    def test_flush_batches(self):
        async def body():
            db = ModelDb()
            c = DebugCollector(db_session=db)
            await c.collect_event("log", "agent", "a", "c")
            await c.collect_state_snapshot("agent", "a", "o", {})
            await c._flush_batches()
            assert db.add_all.call_count == 2
            assert db.commit.call_count == 2
            assert c.get_buffer_stats()["event_buffer_size"] == 0
        run(body())

    def test_flush_batches_error(self):
        async def body():
            db = ModelDb()
            db.commit.side_effect = RuntimeError("db down")
            c = DebugCollector(db_session=db)
            await c.collect_event("log", "agent", "a", "c")
            await c._flush_batches()
            assert db.rollback.called
        run(body())

    def test_flush_no_session(self):
        async def body():
            c = DebugCollector()
            await c.collect_event("log", "agent", "a", "c")
            await c._flush_batches()  # no db -> buffers cleared, no error
        run(body())

    def test_correlated_operation(self):
        async def body():
            c = DebugCollector()
            async with c.correlated_operation(component_type="agent") as corr:
                assert isinstance(corr, str)
            async with c.correlated_operation(correlation_id="fixed") as corr:
                assert corr == "fixed"
        run(body())

    def test_global_collector(self):
        async def body():
            assert get_debug_collector() is None
            c = init_debug_collector()
            assert get_debug_collector() is c
            assert init_debug_collector() is c
            c.stop()
            await asyncio.sleep(0)
        run(body())


# =========================================================================== #
# 8. core/container_sandbox.py
# =========================================================================== #
import core.container_sandbox as cs
from core.container_sandbox import ContainerSandbox


class FakeProc:
    def __init__(self, returncode=0, stdout=b"out", stderr=b""):
        self.returncode = returncode
        self.communicate = mock.AsyncMock(return_value=(stdout, stderr))
        self.kill = mock.Mock()
        self.wait = mock.AsyncMock()


class TestContainerSandbox:
    def test_docker_available_cached(self, monkeypatch):
        sb = ContainerSandbox()
        monkeypatch.setattr(cs.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
        assert sb.docker_available is True
        # second call served from cache even if subprocess now fails
        monkeypatch.setattr(cs.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
        assert sb.docker_available is True

    def test_docker_unavailable(self, monkeypatch):
        sb = ContainerSandbox()
        monkeypatch.setattr(cs.subprocess, "run",
                            lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired(cmd="docker", timeout=5)))
        assert sb.docker_available is False

    def test_docker_success(self, monkeypatch):
        sb = ContainerSandbox()
        monkeypatch.setattr(ContainerSandbox, "docker_available", property(lambda self: True))
        proc = FakeProc(0, b"hello", b"")
        async def fake_exec(*a, **k):
            return proc
        monkeypatch.setattr(cs.asyncio, "create_subprocess_exec", fake_exec)
        res = run(sb.execute_raw_python("t1", "print('hi')", {"a": 1}, timeout=5))
        assert res["status"] == "success" and res["environment"] == "docker"
        assert "hello" in res["output"]

    def test_docker_failure(self, monkeypatch):
        sb = ContainerSandbox()
        monkeypatch.setattr(ContainerSandbox, "docker_available", property(lambda self: True))
        proc = FakeProc(1, b"", b"boom")
        monkeypatch.setattr(cs.asyncio, "create_subprocess_exec",
                            lambda *a, **k: _async_ret(proc))
        res = run(sb.execute_raw_python("t1", "x"))
        assert res["status"] == "failed" and "boom" in res["output"]

    def test_docker_timeout(self, monkeypatch):
        sb = ContainerSandbox(timeout=1)
        monkeypatch.setattr(ContainerSandbox, "docker_available", property(lambda self: True))
        proc = FakeProc(0)

        async def fake_wait_for(coro, timeout=None):
            coro.close()
            raise asyncio.TimeoutError()
        monkeypatch.setattr(cs.asyncio, "create_subprocess_exec", lambda *a, **k: _async_ret(proc))
        monkeypatch.setattr(cs.asyncio, "wait_for", fake_wait_for)
        killed = {}
        async def fake_kill(cid_path):
            killed["path"] = cid_path
        monkeypatch.setattr(sb, "_kill_docker_container", fake_kill)
        res = run(sb.execute_raw_python("t1", "x", timeout=2))
        assert res["status"] == "failed" and "timed out" in res["output"]
        assert "path" in killed

    def test_kill_docker_container_paths(self, monkeypatch, tmp_path):
        sb = ContainerSandbox()
        # missing cid file
        run(sb._kill_docker_container(str(tmp_path / "none.cid")))
        # empty cid
        empty = tmp_path / "empty.cid"
        empty.write_text("   ")
        run(sb._kill_docker_container(str(empty)))
        # real cid
        cid = tmp_path / "real.cid"
        cid.write_text("abc123\n")
        killer = FakeProc(0)
        monkeypatch.setattr(cs.asyncio, "create_subprocess_exec", lambda *a, **k: _async_ret(killer))
        run(sb._kill_docker_container(str(cid)))
        # exception path
        async def boom(*a, **k):
            raise RuntimeError("x")
        monkeypatch.setattr(cs.asyncio, "create_subprocess_exec", boom)
        run(sb._kill_docker_container(str(cid)))

    def test_subprocess_success(self, monkeypatch):
        sb = ContainerSandbox()
        monkeypatch.setattr(ContainerSandbox, "docker_available", property(lambda self: False))
        proc = FakeProc(0, b"42", b"")
        monkeypatch.setattr(cs.asyncio, "create_subprocess_exec", lambda *a, **k: _async_ret(proc))
        res = run(sb.execute_raw_python("t1", "print(6*7)", timeout=5))
        assert res["status"] == "success" and res["environment"] == "subprocess"

    def test_subprocess_failure_and_timeout(self, monkeypatch):
        sb = ContainerSandbox()
        monkeypatch.setattr(ContainerSandbox, "docker_available", property(lambda self: False))
        proc = FakeProc(1, b"", b"err")
        monkeypatch.setattr(cs.asyncio, "create_subprocess_exec", lambda *a, **k: _async_ret(proc))
        res = run(sb.execute_raw_python("t1", "x"))
        assert res["status"] == "failed" and res["output"] == "err"

        async def fake_wait_for(coro, timeout=None):
            coro.close()
            raise asyncio.TimeoutError()
        monkeypatch.setattr(cs.asyncio, "wait_for", fake_wait_for)
        res2 = run(sb.execute_raw_python("t1", "x", timeout=1))
        assert res2["status"] == "failed" and "timed out" in res2["output"]

    def test_resource_limit_preexec(self):
        fn = ContainerSandbox._resource_limit_preexec()
        assert callable(fn)
        fn()  # apply best-effort limits (no-op on failure)

    def test_build_execution_wrapper(self):
        wrapper = ContainerSandbox._build_execution_wrapper("print('x')", {"a": "'''inject'''"})
        assert "'''inject'''" not in wrapper
        assert "print('x')" in wrapper
        import base64
        # round-trip params
        start = wrapper.index("_b64.b64decode('") + len("_b64.b64decode('")
        end = wrapper.index("')", start)
        params = json.loads(base64.b64decode(wrapper[start:end]).decode())
        assert params == {"a": "'''inject'''"}


async def _async_ret(value):
    return value


# =========================================================================== #
# 9. core/service_factory.py
# =========================================================================== #
import core.service_factory as csf
from core.service_factory import ServiceFactory, GovernanceServiceFactory


@pytest.fixture(autouse=True)
def _clean_thread_local():
    ServiceFactory.clear_thread_local()
    GovernanceServiceFactory._instances.clear()
    yield
    ServiceFactory.clear_thread_local()
    GovernanceServiceFactory._instances.clear()


@pytest.fixture()
def fake_classes(monkeypatch):
    """Patch every constructible class in the service_factory namespace."""
    made = {}
    def mk(name):
        def ctor(*a, **k):
            inst = mock.MagicMock(name=name)
            made.setdefault(name, []).append((a, k))
            return inst
        return ctor
    top_level = [
        "AgentGovernanceService", "AgentContextResolver", "GovernanceCache",
        "CanvasContextService", "CanvasRecordingService", "CanvasPresentationSummaryService",
        "ActivityPublisher", "WorldModelService", "KnowledgeExtractor", "GraphRAGEngine",
        "LLMService", "SocialPostGenerator", "QueenAgent", "SkillCreationAgent",
        "KingAgent", "AutoresearchAgent", "GroupReflectionService", "GoalEngine",
        "AtomMetaAgent", "IntegrationCatalogService", "IntegrationRegistry",
        "BudgetEnforcementService", "PGPolicySearchService", "DoclingDocumentProcessor",
        "MessagingActionDispatcher", "UniversalCommunicationBridge", "EpisodeService",
        "HybridDataIngestionService", "ZohoAdapter", "HubSpotAdapter", "NotionAdapter",
        "AirtableAdapter", "JiraAdapter",
    ]
    for name in top_level:
        monkeypatch.setattr(csf, name, mk(name))
    # lazy imports
    monkeypatch.setattr("core.activity_publisher.get_activity_publisher", mk("ActivityPublisherFn"))
    monkeypatch.setattr("core.autonomous_guardrails.AutonomousGuardrailService", mk("Guardrails"))
    monkeypatch.setattr("core.memory.memory_consolidation_service.MemoryConsolidationService", mk("MemConsolidation"))
    monkeypatch.setattr("core.push_notifications.PushNotificationService", mk("Push"))
    monkeypatch.setattr("core.workflow_analytics_engine.WorkflowAnalyticsEngine", mk("WAE"))
    import core.database
    monkeypatch.setattr(core.database, "SessionLocal", mock.MagicMock())
    return made


class TestServiceFactory:
    def test_governance_and_resolver(self, fake_classes):
        db = mock.MagicMock()
        g1 = ServiceFactory.get_governance_service(db)
        g2 = ServiceFactory.get_governance_service(db)
        assert g1 is g2
        r1 = ServiceFactory.get_context_resolver(db)
        assert ServiceFactory.get_context_resolver(db) is r1

    def test_governance_cache_singleton(self, fake_classes):
        assert ServiceFactory.get_governance_cache() is ServiceFactory.get_governance_cache()

    def test_canvas_and_episode_services(self, fake_classes):
        db = mock.MagicMock()
        assert ServiceFactory.get_canvas_context_service(db, "t") is ServiceFactory.get_canvas_context_service(db, "t")
        assert ServiceFactory.get_canvas_recording_service(db, "t") is ServiceFactory.get_canvas_recording_service(db, "t")
        assert ServiceFactory.get_canvas_summary_service(db, "t") is ServiceFactory.get_canvas_summary_service(db, "t")
        assert ServiceFactory.get_episode_service(db) is ServiceFactory.get_episode_service(db)
        assert ServiceFactory.get_activity_publisher() is ServiceFactory.get_activity_publisher()

    def test_knowledge_graphrag_llm_social(self, fake_classes):
        assert ServiceFactory.get_knowledge_extractor() is ServiceFactory.get_knowledge_extractor()
        assert ServiceFactory.get_graphrag_engine() is ServiceFactory.get_graphrag_engine()
        l1 = ServiceFactory.get_llm_service()
        assert ServiceFactory.get_llm_service() is l1
        assert ServiceFactory.get_social_post_generator() is ServiceFactory.get_social_post_generator()

    def test_agents(self, fake_classes):
        db = mock.MagicMock()
        assert ServiceFactory.get_queen_agent(db) is ServiceFactory.get_queen_agent(db)
        assert ServiceFactory.get_atom_meta_agent() is ServiceFactory.get_atom_meta_agent()
        assert ServiceFactory.get_skill_creation_agent(db) is ServiceFactory.get_skill_creation_agent(db)
        assert ServiceFactory.get_king_agent() is ServiceFactory.get_king_agent()
        assert ServiceFactory.get_autoresearch_agent(db) is ServiceFactory.get_autoresearch_agent(db)

    def test_world_model_goal_group_reflection(self, fake_classes):
        db = mock.MagicMock()
        assert ServiceFactory.get_world_model_service() is ServiceFactory.get_world_model_service()
        assert ServiceFactory.get_goal_engine() is ServiceFactory.get_goal_engine()
        assert ServiceFactory.get_group_reflection_service(db) is ServiceFactory.get_group_reflection_service(db)

    def test_lazy_factories(self, fake_classes):
        db = mock.MagicMock()
        assert ServiceFactory.get_guardrails_service(db) is ServiceFactory.get_guardrails_service(db)
        assert ServiceFactory.get_memory_consolidation_service() is ServiceFactory.get_memory_consolidation_service()
        assert ServiceFactory.get_push_notification_service(db) is ServiceFactory.get_push_notification_service(db)
        assert ServiceFactory.get_workflow_analytics_engine(db) is ServiceFactory.get_workflow_analytics_engine(db)

    def test_adapters_and_integration_services(self, fake_classes):
        db = mock.MagicMock()
        for getter, args in [
            (ServiceFactory.get_zoho_adapter, (db,)),
            (ServiceFactory.get_hubspot_adapter, (db,)),
            (ServiceFactory.get_notion_adapter, (db,)),
            (ServiceFactory.get_airtable_adapter, (db,)),
            (ServiceFactory.get_jira_adapter, (db,)),
            (ServiceFactory.get_hybrid_ingestion_service, (db,)),
            (ServiceFactory.get_integration_catalog, (db,)),
            (ServiceFactory.get_budget_enforcement, (db,)),
            (ServiceFactory.get_policy_search, (db,)),
            (ServiceFactory.get_docling_processor, ()),
            (ServiceFactory.get_messaging_dispatcher, (db,)),
            (ServiceFactory.get_communication_bridge, (db,)),
        ]:
            assert getter(*args) is getter(*args)

    def test_clear_thread_local(self, fake_classes):
        db = mock.MagicMock()
        ServiceFactory.get_governance_service(db)
        ServiceFactory.get_context_resolver(db)
        ServiceFactory.get_canvas_context_service(db, "t")
        ServiceFactory.get_canvas_recording_service(db, "t")
        ServiceFactory.get_canvas_summary_service(db, "t")
        ServiceFactory.get_episode_service(db)
        ServiceFactory.get_activity_publisher()
        ServiceFactory.get_social_post_generator()
        ServiceFactory.get_queen_agent(db)
        ServiceFactory.get_atom_meta_agent()
        ServiceFactory.get_zoho_adapter(db)
        ServiceFactory.get_hubspot_adapter(db)
        ServiceFactory.get_notion_adapter(db)
        ServiceFactory.get_airtable_adapter(db)
        ServiceFactory.get_jira_adapter(db)
        ServiceFactory.get_hybrid_ingestion_service(db)
        ServiceFactory.get_integration_catalog(db)
        ServiceFactory.get_budget_enforcement(db)
        ServiceFactory.get_policy_search(db)
        ServiceFactory.get_docling_processor()
        ServiceFactory.get_messaging_dispatcher(db)
        ServiceFactory.get_communication_bridge(db)
        ServiceFactory.clear_thread_local()
        # After clear, fresh instances are constructed
        assert ServiceFactory.get_governance_service(db) is not None

    def test_legacy_governance_factory(self, fake_classes):
        db = mock.MagicMock()
        g = GovernanceServiceFactory.create(db)
        assert GovernanceServiceFactory.create(db) is g
        GovernanceServiceFactory.clear_all()
        assert GovernanceServiceFactory.create(db) is not g

    def test_convenience_functions(self, fake_classes):
        db = mock.MagicMock()
        assert csf.get_governance_service(db) is ServiceFactory.get_governance_service(db)
        assert csf.get_context_resolver(db) is ServiceFactory.get_context_resolver(db)
        assert csf.get_governance_cache() is ServiceFactory.get_governance_cache()
        assert csf.get_episode_service(db) is ServiceFactory.get_episode_service(db)
        assert csf.get_knowledge_extractor() is ServiceFactory.get_knowledge_extractor()
        assert csf.get_graphrag_engine() is ServiceFactory.get_graphrag_engine()
        assert csf.get_llm_service() is ServiceFactory.get_llm_service()
        assert csf.get_social_post_generator() is ServiceFactory.get_social_post_generator()
        assert csf.get_queen_agent(db) is ServiceFactory.get_queen_agent(db)
        assert csf.get_atom_meta_agent() is ServiceFactory.get_atom_meta_agent()
        assert csf.get_guardrails_service(db) is ServiceFactory.get_guardrails_service(db)
        assert csf.get_memory_consolidation_service() is ServiceFactory.get_memory_consolidation_service()
