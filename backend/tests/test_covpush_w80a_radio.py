# -*- coding: utf-8 -*-
"""Coverage wave 80A — Agent Radio stack (8 modules to >=95%).

Modules:
- radio_adapter  (fleet thread attachment)
- radio_breaker  (responsibility-breakpoint classifier)
- radio_guard    (attention/cost governance — re-verified, was 100%)
- radio_server   (async in-process relay)
- radio_actions  (Unified-Action-Registry handlers)
- radio_teams    (declarative team YAML loader)
- radio_config   (env knobs — re-verified, was 100%)
- radio_service  (DB source of truth: threads, messages, budget)

Style: mocked deps, zero LLM spend, no network, fake DB sessions.
"""

from __future__ import annotations

import asyncio
import math
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest

from core.agent_radio import radio_adapter, radio_breaker, radio_config, radio_guard
from core.agent_radio import radio_actions, radio_server, radio_service, radio_teams
from core.models import AgentThread, LateralMessage

UTC = timezone.utc


# ===========================================================================
# Fake DB (chainable query fake with per-model first()/all() control)
# ===========================================================================

class RadioFakeQuery:
    """Chainable query fake: filter/order_by/limit/with_for_update are no-ops."""

    def __init__(self, db: "RadioFakeDb", model: Optional[str]) -> None:
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):  # noqa: A002
        return self

    def order_by(self, *args):
        return self

    def group_by(self, *args):
        return self

    def limit(self, *args):
        return self

    def with_for_update(self, *args):
        return self

    def populate_existing(self, *args):
        return self

    def first(self):
        seq = self.db.first_sequences.get(self.model) if self.model else None
        if seq:
            n = self.db._first_calls.get(self.model, 0)
            self.db._first_calls[self.model] = n + 1
            if n < len(seq):
                return seq[n]
            return self.db.first_rows.get(self.model)
        return self.db.first_rows.get(self.model) if self.model else None

    def all(self):
        return self.db.all_rows.get(self.model, []) if self.model else []


class RadioFakeDb:
    """Minimal session fake: per-model rows, add/commit/refresh, sequences."""

    def __init__(
        self,
        first_rows: Optional[Dict[str, Any]] = None,
        all_rows: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.first_rows = first_rows or {}
        self.all_rows = all_rows or {}
        self.first_sequences: Dict[str, List[Any]] = {}
        self._first_calls: Dict[str, int] = {}
        self.added: List[Any] = []
        self.committed = 0
        self.refreshed: List[Any] = []
        self.closed = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, row) -> None:
        if getattr(row, "id", None) is None:
            row.id = f"fake-{uuid.uuid4().hex[:8]}"
        self.added.append(row)

    def commit(self) -> None:
        self.committed += 1

    def refresh(self, row) -> None:
        self.refreshed.append(row)

    def close(self) -> None:
        self.closed += 1

    def query(self, *cols):
        if not cols:
            return RadioFakeQuery(self, None)
        first = cols[0]
        cls = first if isinstance(first, type) else getattr(first, "class_", None)
        name = getattr(cls, "__name__", None) if cls is not None else None
        return RadioFakeQuery(self, name)


class RadioThread:
    """Plain stand-in for AgentThread (no SQLAlchemy machinery)."""

    def __init__(
        self,
        id: str = "th-1",
        name: str = "thread",
        status: str = "open",
        created_by: str = "agent-a",
        members: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.status = status
        self.created_by_agent_id = created_by
        self.member_agent_ids = members or ["agent-a", "agent-b"]
        self.metadata_json = metadata
        self.created_at = created_at or datetime.now(UTC)
        self.thread_id = id


class RadioMessage:
    """Plain stand-in for LateralMessage."""

    def __init__(
        self,
        id: str = "m-1",
        thread_id: str = "th-1",
        from_agent_id: str = "agent-a",
        to_agent_id: Optional[str] = None,
        content: str = "hello",
        mentions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        delivered: bool = False,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.id = id
        self.thread_id = thread_id
        self.from_agent_id = from_agent_id
        self.to_agent_id = to_agent_id
        self.content = content
        self.mentions = mentions or []
        self.metadata_json = metadata
        self.delivered = delivered
        self.created_at = created_at


def patch_db(monkeypatch, db: RadioFakeDb) -> None:
    monkeypatch.setattr("core.database.get_db_session", lambda: db)


# ===========================================================================
# radio_breaker — responsibility-breakpoint classifier
# ===========================================================================

class TestClassifyBreakpoints:
    def test_empty_task(self):
        verdict = radio_breaker.classify_responsibility_breakpoints("")
        assert verdict.triggered is False
        assert verdict.reasons == ["empty task"]
        assert verdict.score == 0

    def test_whitespace_task(self):
        verdict = radio_breaker.classify_responsibility_breakpoints("   ")
        assert verdict.triggered is False
        assert verdict.score == 0

    def test_none_task(self):
        verdict = radio_breaker.classify_responsibility_breakpoints(None)
        assert verdict.reasons == ["empty task"]

    @pytest.mark.parametrize(
        "task",
        [
            "just one-file change",
            "write some boilerplate",
            "rename a variable",
            "add a comment here",
            "fix typo in doc",
            "small change to css",
        ],
    )
    def test_bounded_patterns_never_trigger(self, task):
        verdict = radio_breaker.classify_responsibility_breakpoints(task)
        assert verdict.triggered is False
        assert verdict.reasons == ["bounded local work"]

    def test_bounded_overrides_breakpoint_keywords(self):
        # "legacy" is a breakpoint keyword, but bounded wins (checked first)
        verdict = radio_breaker.classify_responsibility_breakpoints("fix typo in legacy code")
        assert verdict.triggered is False
        assert verdict.reasons == ["bounded local work"]

    @pytest.mark.parametrize(
        ("task", "pattern"),
        [
            ("this is legacy code", "legacy"),
            ("totally unfamiliar stack", "unfamiliar"),
            ("a data migration", "migration"),
            ("multi module refactor is needed", "multi[- ]module"),
            ("a cross service call", "cross[- ]service"),
            ("production incident", "incident"),
            ("root cause analysis", "root[- ]cause"),
            ("do a security audit", "security (audit|review|analysis)"),
            ("security review please", "security (audit|review|analysis)"),
            ("security analysis", "security (audit|review|analysis)"),
            ("refactor the payment flow", "refactor"),
            ("write an integration test", "integration"),
            ("api integration work", "api integration"),
            ("coordination between teams", "coordinat"),
            ("dependency upgrade", "dependenc"),
        ],
    )
    def test_breakpoint_patterns_detected(self, task, pattern):
        verdict = radio_breaker.classify_responsibility_breakpoints(task)
        assert pattern in verdict.reasons

    def test_single_signal_not_enough(self):
        verdict = radio_breaker.classify_responsibility_breakpoints("just some legacy code")
        assert verdict.triggered is False
        assert verdict.reasons == ["legacy"]
        assert verdict.score == 1

    def test_two_signals_trigger(self):
        verdict = radio_breaker.classify_responsibility_breakpoints("legacy migration")
        assert verdict.triggered is True
        assert verdict.reasons == ["legacy", "migration"]
        assert verdict.score == 2

    def test_three_signals_score(self):
        verdict = radio_breaker.classify_responsibility_breakpoints(
            "legacy incident migration"
        )
        assert verdict.triggered is True
        assert verdict.score == 3

    def test_api_integration_deduped_with_integration(self):
        verdict = radio_breaker.classify_responsibility_breakpoints("api integration")
        assert "api integration" in verdict.reasons
        assert "integration" not in verdict.reasons
        assert verdict.score == 1

    def test_compact_keyword_variants(self):
        # multi-module / cross-service hyphenated forms
        assert radio_breaker.classify_responsibility_breakpoints(
            "multi-module build"
        ).reasons == ["multi[- ]module"]
        assert radio_breaker.classify_responsibility_breakpoints(
            "cross-service tracing"
        ).reasons == ["cross[- ]service"]
        assert radio_breaker.classify_responsibility_breakpoints(
            "root-cause writeup"
        ).reasons == ["root[- ]cause"]


class TestShouldAttachThread:
    def test_gate_disabled_returns_false(self, monkeypatch):
        monkeypatch.setattr(radio_config, "breakpoint_gate_enabled", lambda: False)
        verdict = radio_breaker.should_attach_thread("legacy migration")
        assert verdict.triggered is False
        assert verdict.reasons == ["gate disabled"]

    def test_gate_enabled_delegates_to_classifier(self, monkeypatch):
        monkeypatch.setattr(radio_config, "breakpoint_gate_enabled", lambda: True)
        verdict = radio_breaker.should_attach_thread("legacy migration")
        assert verdict.triggered is True

    def test_gate_enabled_bounded_task(self, monkeypatch):
        monkeypatch.setattr(radio_config, "breakpoint_gate_enabled", lambda: True)
        verdict = radio_breaker.should_attach_thread("fix typo in readme")
        assert verdict.triggered is False

    def test_verdict_dataclass_defaults(self):
        v = radio_breaker.BreakpointVerdict(triggered=False)
        assert v.reasons == []
        assert v.score == 0


# ===========================================================================
# radio_adapter — fleet thread attachment
# ===========================================================================

class TestAttachThreadForChain:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: False)
        db = RadioFakeDb()
        assert (
            radio_adapter.attach_thread_for_chain(
                db, chain_id="c1", task_description="legacy migration", team_agent_ids=["b"]
            )
            is None
        )

    def test_no_breakpoint_returns_none(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        assert (
            radio_adapter.attach_thread_for_chain(
                db, chain_id="c1", task_description="fix typo", team_agent_ids=["b"]
            )
            is None
        )

    def test_creates_thread_without_execution(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        thread = RadioThread(id="th-abc12345")
        created: Dict[str, Any] = {}

        def fake_create_thread(
            dbs,
            *,
            name,
            created_by_agent_id,
            member_agent_ids,
            chain_id=None,
            tenant_id=None,
            metadata_json=None,
        ):
            created.update(
                {
                    "name": name,
                    "created_by": created_by_agent_id,
                    "members": member_agent_ids,
                    "chain_id": chain_id,
                    "tenant_id": tenant_id,
                    "metadata": metadata_json,
                }
            )
            return thread

        monkeypatch.setattr(radio_adapter.radio_service, "create_thread", fake_create_thread)
        result = radio_adapter.attach_thread_for_chain(
            db,
            chain_id="chain-1234567890",
            task_description="legacy migration",
            team_agent_ids=["agent-b", "agent-c"],
        )
        assert result is thread
        assert created["name"] == "fleet-chain-12"
        assert created["members"] == ["agent-b", "agent-c"]
        assert created["chain_id"] == "chain-1234567890"
        assert created["metadata"]["scope"] == "fleet"
        assert created["metadata"]["breakpoint_reasons"] == ["legacy", "migration"]

    def test_execution_id_attaches_thread(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        thread = RadioThread(id="th-xyz")
        execution = type("AgentExecution", (), {"thread_id": None})()
        db.first_rows["AgentExecution"] = execution
        monkeypatch.setattr(
            radio_adapter.radio_service,
            "create_thread",
            lambda *a, **k: thread,
        )
        result = radio_adapter.attach_thread_for_chain(
            db,
            chain_id="c1",
            task_description="legacy migration",
            team_agent_ids=["b"],
            execution_id="exec-1",
        )
        assert result is thread
        assert execution.thread_id == "th-xyz"
        assert db.committed >= 1

    def test_execution_not_found_skips_attach(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()  # no AgentExecution row
        thread = RadioThread(id="th-xyz")
        monkeypatch.setattr(
            radio_adapter.radio_service,
            "create_thread",
            lambda *a, **k: thread,
        )
        result = radio_adapter.attach_thread_for_chain(
            db,
            chain_id="c1",
            task_description="legacy migration",
            team_agent_ids=["b"],
            execution_id="missing",
        )
        assert result is thread
        assert db.committed == 0

    def test_creator_default_and_tenant_passthrough(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        thread = RadioThread(id="th-1")
        seen: Dict[str, Any] = {}

        def fake_create_thread(
            dbs,
            *,
            name,
            created_by_agent_id,
            member_agent_ids,
            chain_id=None,
            tenant_id=None,
            metadata_json=None,
        ):
            seen.update(created_by=created_by_agent_id, tenant_id=tenant_id)
            return thread

        monkeypatch.setattr(radio_adapter.radio_service, "create_thread", fake_create_thread)
        radio_adapter.attach_thread_for_chain(
            db,
            chain_id="c1",
            task_description="legacy migration",
            team_agent_ids=["b"],
            tenant_id="t-9",
        )
        assert seen["created_by"] == "atom_main"
        assert seen["tenant_id"] == "t-9"


class TestExecutionThreadId:
    def test_returns_thread_id_when_found(self, monkeypatch):
        db = RadioFakeDb()
        execution = type("AgentExecution", (), {"thread_id": "th-42"})()
        db.first_rows["AgentExecution"] = execution
        patch_db(monkeypatch, db)
        assert radio_adapter.execution_thread_id("exec-1") == "th-42"
        assert db.closed == 0

    def test_returns_none_when_missing(self, monkeypatch):
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        assert radio_adapter.execution_thread_id("exec-1") is None

    def test_returns_none_on_db_error(self, monkeypatch):
        def broken():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken)
        assert radio_adapter.execution_thread_id("exec-1") is None


# ===========================================================================
# radio_server — async relay
# ===========================================================================

class TestRadioServerSingleton:
    def test_get_returns_singleton(self):
        radio_server.reset_radio_server()
        a = radio_server.get_radio_server()
        b = radio_server.get_radio_server()
        assert a is b

    def test_reset_creates_new_instance(self):
        radio_server.reset_radio_server()
        a = radio_server.get_radio_server()
        radio_server.reset_radio_server()
        b = radio_server.get_radio_server()
        assert a is not b


class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_wakes_registered_listener(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        q, ev = server._register_listener("th-1", "agent-a")
        msg = RadioMessage(id="m-9", mentions=["agent-a", "ghost"])
        await server.publish(msg)
        assert not q.empty()
        assert q.get_nowait() == "m-9"
        assert ev.is_set()

    @pytest.mark.asyncio
    async def test_publish_unmentioned_agent_not_woken(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        q, ev = server._register_listener("th-1", "agent-b")
        await server.publish(RadioMessage(id="m-1", mentions=["agent-a"]))
        assert q.empty()
        assert not ev.is_set()

    @pytest.mark.asyncio
    async def test_publish_empty_mentions(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        await server.publish(RadioMessage(id="m-1", mentions=[]))

    @pytest.mark.asyncio
    async def test_publish_never_raises(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()

        class Boom:
            thread_id = "th-1"

            @property
            def mentions(self):
                raise RuntimeError("boom")

        await server.publish(Boom())  # swallowed


class TestRegisterListener:
    def test_creates_queue_and_event(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        q, ev = server._register_listener("th-1", "agent-a")
        assert isinstance(q, asyncio.Queue)
        assert isinstance(ev, asyncio.Event)

    def test_reuse_existing_queue_and_event(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        q1, ev1 = server._register_listener("th-1", "agent-a")
        q2, ev2 = server._register_listener("th-1", "agent-a")
        assert q1 is q2
        assert ev1 is ev2


class TestWaitForMention:
    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        result = await server.wait_for_mention("th-1", "agent-a", timeout=0.02)
        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_capped_by_config(self, monkeypatch):
        monkeypatch.setattr(radio_config, "wait_timeout_seconds", lambda: 0.02)
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        assert await server.wait_for_mention("th-1", "agent-a") is None

    @pytest.mark.asyncio
    async def test_explicit_timeout_honored(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        assert await server.wait_for_mention("th-1", "agent-a", timeout=0.01) is None

    @pytest.mark.asyncio
    async def test_returns_pending_db_message_immediately(self, monkeypatch):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        msg = RadioMessage(id="m-1", mentions=["agent-a"])
        db = RadioFakeDb()
        pending = [msg]
        monkeypatch.setattr(radio_service, "get_pending_mentions", lambda dbs, t, a, limit=1: pending)
        read = []
        monkeypatch.setattr(radio_service, "mark_read", lambda dbs, m, a: read.append(m.id))
        result = await server.wait_for_mention("th-1", "agent-a", timeout=0.1, db=db)
        assert result is msg
        assert read == ["m-1"]

    @pytest.mark.asyncio
    async def test_drains_queued_token_then_checks_db(self, monkeypatch):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        msg = RadioMessage(id="m-2", mentions=["agent-a"])
        db = RadioFakeDb()
        calls: List[List[Any]] = [[], [msg]]

        def side_effect(dbs, t, a, limit=1):
            return calls.pop(0)

        monkeypatch.setattr(radio_service, "get_pending_mentions", side_effect)
        read = []
        monkeypatch.setattr(radio_service, "mark_read", lambda dbs, m, a: read.append(m.id))
        q, ev = server._register_listener("th-1", "agent-a")
        q.put_nowait("stale-token")
        result = await server.wait_for_mention("th-1", "agent-a", timeout=0.1, db=db)
        assert result is msg
        assert q.empty()
        assert read == ["m-2"]

    @pytest.mark.asyncio
    async def test_event_set_returns_db_message(self, monkeypatch):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        msg = RadioMessage(id="m-3", mentions=["agent-a"])
        db = RadioFakeDb()
        calls: List[List[Any]] = [[], [msg]]

        def side_effect(dbs, t, a, limit=1):
            return calls.pop(0)

        monkeypatch.setattr(radio_service, "get_pending_mentions", side_effect)
        read = []
        monkeypatch.setattr(radio_service, "mark_read", lambda dbs, m, a: read.append(m.id))
        q, ev = server._register_listener("th-1", "agent-a")
        task = asyncio.create_task(
            server.wait_for_mention("th-1", "agent-a", timeout=1.0, db=db)
        )
        await asyncio.sleep(0.05)
        ev.set()
        result = await task
        assert result is msg
        assert read == ["m-3"]

    @pytest.mark.asyncio
    async def test_event_set_without_db_returns_none(self):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        q, ev = server._register_listener("th-1", "agent-a")
        task = asyncio.create_task(
            server.wait_for_mention("th-1", "agent-a", timeout=1.0)
        )
        await asyncio.sleep(0.05)
        ev.set()
        assert await task is None

    @pytest.mark.asyncio
    async def test_db_error_returns_none(self, monkeypatch):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        db = RadioFakeDb()

        def boom(dbs, t, a, limit=1):
            raise RuntimeError("db down")

        monkeypatch.setattr(radio_service, "get_pending_mentions", boom)
        assert await server.wait_for_mention("th-1", "agent-a", timeout=0.05, db=db) is None

    @pytest.mark.asyncio
    async def test_get_nowait_exception_swallowed(self, monkeypatch):
        radio_server.reset_radio_server()
        server = radio_server.get_radio_server()
        q, ev = server._register_listener("th-1", "agent-a")

        class BoomQueue(asyncio.Queue):
            def get_nowait(self):
                raise RuntimeError("boom")

        boom_q = BoomQueue()
        boom_q.put_nowait("token")
        server._queues["th-1"]["agent-a"] = boom_q
        monkeypatch.setattr(radio_service, "get_pending_mentions", lambda dbs, t, a, limit=1: [])
        assert await server.wait_for_mention("th-1", "agent-a", timeout=0.02, db=RadioFakeDb()) is None


# ===========================================================================
# radio_actions — registry handlers
# ===========================================================================

class _StubServer:
    """Stand-in relay: controlled publish / wait_for_mention."""

    def __init__(self, wait_result=None, wait_exc=None) -> None:
        self.wait_result = wait_result
        self.wait_exc = wait_exc
        self.published: List[Any] = []
        self.wait_args: List[Dict[str, Any]] = []

    async def publish(self, message) -> None:
        self.published.append(message)

    async def wait_for_mention(self, thread_id, agent_id, timeout=None, db=None):
        self.wait_args.append(
            {"thread_id": thread_id, "agent_id": agent_id, "timeout": timeout}
        )
        if self.wait_exc is not None:
            raise self.wait_exc
        return self.wait_result


class TestActionHelpers:
    def test_context_tier_defaults_to_student(self):
        assert radio_actions._context_tier({}) == "student"
        assert radio_actions._context_tier(None) == "student"

    def test_context_tier_normalized(self):
        assert radio_actions._context_tier({"tier": "INTERN"}) == "intern"
        assert radio_actions._context_tier({"tier": "Autonomous"}) == "autonomous"

    def test_require_tier_ok(self):
        assert radio_actions._require_tier({"tier": "intern"}, "intern") is None
        assert radio_actions._require_tier({"tier": "autonomous"}, "student") is None

    def test_require_tier_denied(self):
        err = radio_actions._require_tier({"tier": "student"}, "intern")
        assert err == "Requires INTERN+ maturity tier"

    def test_require_tier_unknown_tier_denied(self):
        assert radio_actions._require_tier({"tier": "admin"}, "intern") is not None

    def test_require_tier_missing_tier_denied(self):
        assert radio_actions._require_tier({}, "student") is None  # student == student

    def test_context_agent_id(self):
        assert radio_actions._context_agent_id({"agent_id": "a1"}) == "a1"
        assert radio_actions._context_agent_id({}) is None

    def test_disabled_note(self):
        note = radio_actions._disabled_note()
        assert note["success"] is False
        assert note["error"] == "radio_disabled"
        assert "ATOM_RADIO_ENABLED" in note["message"]


class TestRadioCreateThread:
    @pytest.mark.asyncio
    async def test_disabled(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: False)
        result = await radio_actions.radio_create_thread({}, {})
        assert result["success"] is False
        assert result["error"] == "radio_disabled"

    @pytest.mark.asyncio
    async def test_tier_denied(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_create_thread(
            {}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["success"] is False
        assert "INTERN" in result["error"]

    @pytest.mark.asyncio
    async def test_no_agent_id(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_create_thread(
            {"name": "x", "member_agent_ids": ["b"]}, {"tier": "intern"}
        )
        assert result["success"] is False
        assert "agent_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_name_required(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_create_thread(
            {"name": "   ", "member_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["success"] is False
        assert result["error"] == "name is required"

    @pytest.mark.asyncio
    async def test_members_required(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_create_thread(
            {"name": "x", "member_agent_ids": []},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["success"] is False
        assert "member_agent_ids" in result["error"]

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_create_thread(
            {
                "name": "squad",
                "member_agent_ids": ["agent-b", ""],
                "scope_hint": "fleet",
            },
            {"agent_id": "agent-a", "tier": "autonomous", "tenant_id": "t-1"},
        )
        assert result["success"] is True
        assert result["thread_id"]
        assert result["name"] == "squad"
        assert "agent-b" in result["member_agent_ids"]
        thread = db.added[0]
        assert thread.created_by_agent_id == "agent-a"
        assert thread.metadata_json["scope"] == "fleet"
        assert thread.tenant_id == "t-1"
        assert thread.member_agent_ids[0] == "agent-a"

    @pytest.mark.asyncio
    async def test_radio_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise radio_service.RadioError("nope")

        monkeypatch.setattr(radio_service, "create_thread", boom)
        result = await radio_actions.radio_create_thread(
            {"name": "x", "member_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["success"] is False
        assert result["error"] == "radio_error"

    @pytest.mark.asyncio
    async def test_internal_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(radio_service, "create_thread", boom)
        result = await radio_actions.radio_create_thread(
            {"name": "x", "member_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["success"] is False
        assert result["error"] == "internal_error"


class TestRadioSendMessage:
    @pytest.mark.asyncio
    async def test_disabled(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: False)
        result = await radio_actions.radio_send_message({}, {})
        assert result["error"] == "radio_disabled"

    @pytest.mark.asyncio
    async def test_tier_denied(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_send_message(
            {}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_no_agent_id(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_send_message(
            {"thread_id": "t1", "content": "hi"}, {"tier": "intern"}
        )
        assert "agent_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_thread_id_required(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_send_message(
            {"content": "hi"}, {"agent_id": "a1", "tier": "intern"}
        )
        assert result["error"] == "thread_id is required"

    @pytest.mark.asyncio
    async def test_success_plain(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        stub = _StubServer()
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        thread = RadioThread(id="th-1")
        db = RadioFakeDb(first_rows={"AgentThread": thread})
        db.first_sequences["AgentThread"] = [thread, thread]
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_send_message(
            {
                "thread_id": "th-1",
                "content": "please review",
                "mention_agent_ids": ["agent-b", ""],
            },
            {"agent_id": "agent-a", "tier": "intern"},
        )
        assert result["success"] is True
        assert result["message_id"]
        assert result["mentions"] == ["agent-b"]
        assert len(stub.published) == 1
        assert stub.published[0].content == "please review"
        msg = db.added[0]
        assert msg.metadata_json == {"read_by": []}

    @pytest.mark.asyncio
    async def test_success_to_agent_and_requires_response(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        stub = _StubServer()
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        thread = RadioThread(id="th-1")
        db = RadioFakeDb(first_rows={"AgentThread": thread})
        db.first_sequences["AgentThread"] = [thread, thread]
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_send_message(
            {
                "thread_id": "th-1",
                "content": "urgent",
                "to_agent_id": "agent-b",
                "requires_response": True,
            },
            {"agent_id": "agent-a", "tier": "intern"},
        )
        assert result["success"] is True
        msg = db.added[0]
        assert msg.metadata_json == {
            "is_response": False,
            "priority": "high",
            "read_by": [],
        }
        assert msg.to_agent_id == "agent-b"

    @pytest.mark.asyncio
    async def test_policy_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise radio_service.RadioPolicyError("no broadcast")

        monkeypatch.setattr(radio_service, "send_message", boom)
        result = await radio_actions.radio_send_message(
            {"thread_id": "t1", "content": "hi", "mention_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["error"] == "policy_error"

    @pytest.mark.asyncio
    async def test_access_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise radio_service.RadioAccessError("not a member")

        monkeypatch.setattr(radio_service, "send_message", boom)
        result = await radio_actions.radio_send_message(
            {"thread_id": "t1", "content": "hi", "mention_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["error"] == "access_error"

    @pytest.mark.asyncio
    async def test_budget_exceeded(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise radio_service.RadioBudgetExceeded("no budget")

        monkeypatch.setattr(radio_service, "send_message", boom)
        result = await radio_actions.radio_send_message(
            {"thread_id": "t1", "content": "hi", "mention_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["error"] == "budget_exceeded"

    @pytest.mark.asyncio
    async def test_radio_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise radio_service.RadioError("generic")

        monkeypatch.setattr(radio_service, "send_message", boom)
        result = await radio_actions.radio_send_message(
            {"thread_id": "t1", "content": "hi", "mention_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["error"] == "radio_error"

    @pytest.mark.asyncio
    async def test_internal_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(radio_service, "send_message", boom)
        result = await radio_actions.radio_send_message(
            {"thread_id": "t1", "content": "hi", "mention_agent_ids": ["b"]},
            {"agent_id": "a1", "tier": "intern"},
        )
        assert result["error"] == "internal_error"


class TestRadioWaitForMention:
    @pytest.mark.asyncio
    async def test_disabled(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: False)
        result = await radio_actions.radio_wait_for_mention({}, {})
        assert result["error"] == "radio_disabled"

    @pytest.mark.asyncio
    async def test_no_tier_passes_student_floor(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        # Missing tier fails closed to 'student' == the STUDENT+ floor, so the
        # tier gate cannot deny here (reached only by empty/unknown tiers)
        result = await radio_actions.radio_wait_for_mention({}, {"agent_id": "a1"})
        assert result["success"] is False
        assert result["error"] == "thread_id is required"

    @pytest.mark.asyncio
    async def test_no_agent_id(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_wait_for_mention(
            {"thread_id": "t1"}, {"tier": "student"}
        )
        assert "agent_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_thread_id_required(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_wait_for_mention(
            {}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["error"] == "thread_id is required"

    @pytest.mark.asyncio
    async def test_timed_out(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        stub = _StubServer(wait_result=None)
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_wait_for_mention(
            {"thread_id": "t1", "timeout": 1}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["success"] is True
        assert result["timed_out"] is True
        assert stub.wait_args[0]["timeout"] == 1

    @pytest.mark.asyncio
    async def test_timeout_none_passed_through(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        stub = _StubServer(wait_result=None)
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        await radio_actions.radio_wait_for_mention(
            {"thread_id": "t1"}, {"agent_id": "a1", "tier": "student"}
        )
        assert stub.wait_args[0]["timeout"] is None

    @pytest.mark.asyncio
    async def test_invalid_timeout_falls_back_to_none(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        stub = _StubServer(wait_result=None)
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        await radio_actions.radio_wait_for_mention(
            {"thread_id": "t1", "timeout": "abc"}, {"agent_id": "a1", "tier": "student"}
        )
        assert stub.wait_args[0]["timeout"] is None

    @pytest.mark.asyncio
    async def test_message_received(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        msg = RadioMessage(
            id="m-1",
            from_agent_id="agent-b",
            content="can you verify?",
            mentions=["agent-a"],
            created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        )
        stub = _StubServer(wait_result=msg)
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_wait_for_mention(
            {"thread_id": "t1", "timeout": 5}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["success"] is True
        assert result["timed_out"] is False
        assert result["message_id"] == "m-1"
        assert result["from_agent_id"] == "agent-b"
        assert result["content"] == "can you verify?"
        assert result["created_at"] == "2026-08-01T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_message_without_created_at(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        msg = RadioMessage(id="m-2", mentions=["agent-a"], created_at=None)
        stub = _StubServer(wait_result=msg)
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_wait_for_mention(
            {"thread_id": "t1"}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["created_at"] is None

    @pytest.mark.asyncio
    async def test_wait_raises_returns_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        stub = _StubServer(wait_exc=RuntimeError("boom"))
        monkeypatch.setattr(radio_server, "get_radio_server", lambda: stub)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_wait_for_mention(
            {"thread_id": "t1"}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["success"] is False
        assert result["error"] == "internal_error"


class TestRadioReadInbox:
    @pytest.mark.asyncio
    async def test_disabled(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: False)
        result = await radio_actions.radio_read_inbox({}, {})
        assert result["error"] == "radio_disabled"

    @pytest.mark.asyncio
    async def test_no_tier_passes_student_floor(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        # Missing tier fails closed to 'student' == the STUDENT+ floor; the
        # tier gate cannot deny, so the read proceeds (empty inbox)
        result = await radio_actions.radio_read_inbox({}, {"agent_id": "a1"})
        assert result["success"] is True
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_no_agent_id(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        result = await radio_actions.radio_read_inbox({}, {"tier": "student"})
        assert "agent_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_snapshot_with_thread_id(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        thread = RadioThread(id="th-1", metadata={"used_budget_usd": 0.05})
        msg = RadioMessage(id="m-1", mentions=["agent-a"])
        db = RadioFakeDb(
            first_rows={"AgentThread": thread},
            all_rows={"LateralMessage": [msg]},
        )
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_read_inbox(
            {"thread_id": "th-1"}, {"agent_id": "agent-a", "tier": "student"}
        )
        assert result["success"] is True
        assert result["found"] is True
        assert result["name"] == "thread"
        assert result["unread_mentions"] == 1
        assert result["messages"][0]["id"] == "m-1"

    @pytest.mark.asyncio
    async def test_inbox_without_thread_id(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        msg = RadioMessage(
            id="m-1", thread_id="th-1", from_agent_id="agent-b", content="ping", mentions=["agent-a"]
        )
        db = RadioFakeDb(
            first_rows={"AgentThread": thread},
            all_rows={"AgentThread": [thread], "LateralMessage": [msg]},
        )
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_read_inbox(
            {}, {"agent_id": "agent-a", "tier": "student"}
        )
        assert result["success"] is True
        assert result["found"] is True
        assert "@agent-b" in result["inbox"]

    @pytest.mark.asyncio
    async def test_inbox_empty(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)
        result = await radio_actions.radio_read_inbox(
            {}, {"agent_id": "agent-a", "tier": "student"}
        )
        assert result["success"] is True
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_read_error(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()
        patch_db(monkeypatch, db)

        def boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(radio_service, "get_thread_snapshot", boom)
        result = await radio_actions.radio_read_inbox(
            {"thread_id": "th-1"}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["success"] is False
        assert result["error"] == "internal_error"


class TestRegisterAll:
    def test_register_all_actions_exist(self):
        radio_actions.register_all()
        from core.action_registry import action_registry

        for name in (
            "radio.create_thread",
            "radio.send_message",
            "radio.wait_for_mention",
            "radio.read_inbox",
        ):
            assert action_registry.get_action(name) is not None


# ===========================================================================
# radio_teams — declarative team loader
# ===========================================================================

class TestTeamModels:
    def test_role_keys(self):
        team = radio_teams.TeamConfig(
            name="t",
            roles=[
                radio_teams.TeamRole(key="planner", name="Planner"),
                radio_teams.TeamRole(key="reviewer", name="Reviewer"),
            ],
        )
        assert team.role_keys() == ["planner", "reviewer"]
        assert team.reviewer().key == "reviewer"

    def test_reviewer_absent(self):
        team = radio_teams.TeamConfig(name="t", roles=[radio_teams.TeamRole(key="dev", name="Dev")])
        assert team.reviewer() is None

    def test_empty_team(self):
        team = radio_teams.TeamConfig(name="t")
        assert team.role_keys() == []
        assert team.reviewer() is None

    def test_role_defaults(self):
        role = radio_teams.TeamRole(key="k", name="N")
        assert role.responsibility == ""
        assert role.prompt == ""
        assert role.mentions == []


class TestValidate:
    def test_not_a_dict(self):
        assert radio_teams._validate(None) is None
        assert radio_teams._validate("nope") is None
        assert radio_teams._validate([]) is None

    def test_missing_team_key(self):
        assert radio_teams._validate({"other": 1}) is None

    def test_team_not_mapping(self):
        assert radio_teams._validate({"team": "str"}) is None

    def test_missing_name(self):
        assert radio_teams._validate({"team": {"roles": []}}) is None

    def test_role_missing_key_or_name_skipped(self):
        parsed = {
            "team": {
                "name": "x",
                "roles": [
                    {"name": "NoKey"},
                    {"key": "noName"},
                    {"key": "dev", "name": "Dev"},
                ],
            }
        }
        team = radio_teams._validate(parsed)
        assert team is not None
        assert team.role_keys() == ["dev"]

    def test_no_valid_roles(self):
        assert radio_teams._validate({"team": {"name": "x", "roles": [{"key": "k"}]}}) is None
        assert radio_teams._validate({"team": {"name": "x", "roles": []}}) is None

    def test_valid_config_strips_and_defaults(self):
        parsed = {
            "team": {
                "name": "team-x",
                "description": "  desc  ",
                "roles": [
                    {
                        "key": "planner",
                        "name": "Planner",
                        "responsibility": "  plan things  ",
                        "prompt": "  prompt text  ",
                        "mentions": [{"role": "reviewer", "when": "x"}],
                    }
                ],
                "defaults": {"inbox_cap": 5},
            }
        }
        team = radio_teams._validate(parsed)
        assert team.name == "team-x"
        assert team.description == "desc"
        assert team.roles[0].responsibility == "plan things"
        assert team.roles[0].prompt == "prompt text"
        assert team.roles[0].mentions == [{"role": "reviewer", "when": "x"}]
        assert team.defaults == {"inbox_cap": 5}

    def test_roles_none_means_no_roles(self):
        parsed = {"team": {"name": "x", "roles": None, "defaults": None}}
        assert radio_teams._validate(parsed) is None

    def test_defaults_none_becomes_empty(self):
        parsed = {
            "team": {"name": "x", "roles": [{"key": "dev", "name": "Dev"}], "defaults": None}
        }
        team = radio_teams._validate(parsed)
        assert team is not None
        assert team.defaults == {}


class TestTryImportYaml:
    def test_yaml_available(self):
        assert radio_teams._try_import_yaml() is not None

    def test_yaml_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "yaml", None)
        assert radio_teams._try_import_yaml() is None


class TestLoadTeam:
    def test_yaml_unavailable_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "yaml", None)
        assert radio_teams.load_team("coding_team", teams_dir=tmp_path) is None

    def test_no_config_for_team(self, tmp_path):
        assert radio_teams.load_team("missing", teams_dir=tmp_path) is None

    def test_loads_yaml_file(self, tmp_path):
        (tmp_path / "alpha.yaml").write_text(
            "team:\n  name: alpha\n  roles:\n    - key: dev\n      name: Dev\n",
            encoding="utf-8",
        )
        team = radio_teams.load_team("alpha", teams_dir=tmp_path)
        assert team is not None
        assert team.name == "alpha"
        assert team.role_keys() == ["dev"]

    def test_falls_back_to_yml(self, tmp_path):
        (tmp_path / "beta.yml").write_text(
            "team:\n  name: beta\n  roles:\n    - key: qa\n      name: QA\n",
            encoding="utf-8",
        )
        team = radio_teams.load_team("beta", teams_dir=tmp_path)
        assert team.name == "beta"

    def test_yaml_preferred_over_yml(self, tmp_path):
        (tmp_path / "gamma.yaml").write_text(
            "team:\n  name: gamma-yaml\n  roles:\n    - key: a\n      name: A\n",
            encoding="utf-8",
        )
        (tmp_path / "gamma.yml").write_text(
            "team:\n  name: gamma-yml\n  roles:\n    - key: b\n      name: B\n",
            encoding="utf-8",
        )
        assert radio_teams.load_team("gamma", teams_dir=tmp_path).name == "gamma-yaml"

    def test_invalid_yaml_returns_none(self, tmp_path):
        (tmp_path / "bad.yaml").write_text("team: [unclosed", encoding="utf-8")
        assert radio_teams.load_team("bad", teams_dir=tmp_path) is None

    def test_invalid_structure_returns_none(self, tmp_path):
        (tmp_path / "weird.yaml").write_text("foo: bar\n", encoding="utf-8")
        assert radio_teams.load_team("weird", teams_dir=tmp_path) is None

    def test_loads_repo_coding_team(self):
        team = radio_teams.load_team("coding_team")
        assert team is not None
        assert team.name == "coding-team"
        assert "planner" in team.role_keys()
        assert "reviewer" in team.role_keys()
        assert team.reviewer().key == "reviewer"
        assert team.defaults.get("inbox_cap") == 10


class TestListTeamNames:
    def test_missing_dir(self, tmp_path):
        assert radio_teams.list_team_names(teams_dir=tmp_path / "nope") == []

    def test_lists_yaml_and_yml_sorted(self, tmp_path):
        (tmp_path / "b.yaml").write_text("team:\n  name: b\n", encoding="utf-8")
        (tmp_path / "a.yml").write_text("team:\n  name: a\n", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        assert radio_teams.list_team_names(teams_dir=tmp_path) == ["a", "b"]


class TestFalsificationPrompt:
    def test_block_content(self):
        block = radio_teams.falsification_prompt_block()
        assert "[FALSIFICATION PASS]" in block
        assert "prove this WRONG" in block


# ===========================================================================
# radio_service — DB source of truth
# ===========================================================================

class TestCreateThread:
    def test_creator_prepended_and_dedup(self):
        db = RadioFakeDb()
        thread = radio_service.create_thread(
            db,
            name="squad",
            created_by_agent_id="agent-a",
            member_agent_ids=["agent-b", "agent-b", "agent-c"],
            chain_id="c1",
            tenant_id="t1",
        )
        assert thread.member_agent_ids == ["agent-a", "agent-b", "agent-c"]
        assert thread.chain_id == "c1"
        assert thread.tenant_id == "t1"
        assert thread.status == "open"
        assert thread.metadata_json == {"used_budget_usd": 0.0}
        assert thread in db.added
        assert db.committed == 1
        assert thread in db.refreshed

    def test_creator_already_member_order_preserved(self):
        db = RadioFakeDb()
        thread = radio_service.create_thread(
            db,
            name="squad",
            created_by_agent_id="agent-a",
            member_agent_ids=["agent-c", "agent-a", "agent-b"],
        )
        assert thread.member_agent_ids == ["agent-c", "agent-a", "agent-b"]

    def test_metadata_default_preserved(self):
        db = RadioFakeDb()
        thread = radio_service.create_thread(
            db,
            name="squad",
            created_by_agent_id="agent-a",
            member_agent_ids=["agent-b"],
            metadata_json={"used_budget_usd": 1.5, "scope": "fleet"},
        )
        assert thread.metadata_json == {"used_budget_usd": 1.5, "scope": "fleet"}

    def test_empty_members(self):
        db = RadioFakeDb()
        thread = radio_service.create_thread(
            db, name="solo", created_by_agent_id="agent-a", member_agent_ids=[]
        )
        assert thread.member_agent_ids == ["agent-a"]


class TestIsMember:
    def test_empty_agent_false(self):
        assert radio_service.is_member(RadioThread(), "") is False

    def test_roster_member(self):
        assert radio_service.is_member(RadioThread(members=["agent-a"]), "agent-a") is True

    def test_non_member_false(self):
        assert radio_service.is_member(RadioThread(members=["agent-b"]), "agent-z") is False

    def test_creator_counts_even_if_not_in_roster(self):
        thread = RadioThread(members=["agent-b"], created_by="agent-c")
        assert radio_service.is_member(thread, "agent-c") is True


class TestThreadBudgetUsed:
    def test_float_metadata(self):
        thread = RadioThread(metadata={"used_budget_usd": 0.5})
        assert radio_service.thread_budget_used_usd(thread) == 0.5

    def test_int_metadata(self):
        thread = RadioThread(metadata={"used_budget_usd": 1})
        assert radio_service.thread_budget_used_usd(thread) == 1.0

    def test_numeric_string_metadata(self):
        thread = RadioThread(metadata={"used_budget_usd": "0.25"})
        assert radio_service.thread_budget_used_usd(thread) == 0.25

    def test_missing_key_defaults_zero(self):
        assert radio_service.thread_budget_used_usd(RadioThread()) == 0.0
        assert radio_service.thread_budget_used_usd(RadioThread(metadata=None)) == 0.0

    def test_corrupt_string_raises(self):
        thread = RadioThread(metadata={"used_budget_usd": "garbage"})
        with pytest.raises(radio_service.RadioBudgetCorrupted):
            radio_service.thread_budget_used_usd(thread)

    def test_corrupt_dict_raises(self):
        thread = RadioThread(metadata={"used_budget_usd": {"x": 1}})
        with pytest.raises(radio_service.RadioBudgetCorrupted):
            radio_service.thread_budget_used_usd(thread)

    def test_nan_raises(self):
        thread = RadioThread(metadata={"used_budget_usd": float("nan")})
        with pytest.raises(radio_service.RadioBudgetCorrupted):
            radio_service.thread_budget_used_usd(thread)

    def test_inf_raises(self):
        thread = RadioThread(metadata={"used_budget_usd": float("inf")})
        with pytest.raises(radio_service.RadioBudgetCorrupted):
            radio_service.thread_budget_used_usd(thread)

    def test_negative_raises(self):
        thread = RadioThread(metadata={"used_budget_usd": -1.0})
        with pytest.raises(radio_service.RadioBudgetCorrupted):
            radio_service.thread_budget_used_usd(thread)


class TestSendMessage:
    _GONE = object()  # sentinel: locked re-check returns None

    def _db(self, thread, locked_thread=None):
        db = RadioFakeDb(first_rows={"AgentThread": thread})
        if locked_thread is self._GONE:
            locked = None
        else:
            locked = locked_thread or thread
        db.first_sequences["AgentThread"] = [thread, locked]
        return db

    def test_no_mentions_raises_policy(self):
        db = RadioFakeDb()
        with pytest.raises(radio_service.RadioPolicyError):
            radio_service.send_message(db, thread_id="t1", from_agent_id="a", content="hi")

    def test_to_agent_self_not_counted(self):
        db = RadioFakeDb()
        with pytest.raises(radio_service.RadioPolicyError):
            radio_service.send_message(
                db,
                thread_id="t1",
                from_agent_id="agent-a",
                content="hi",
                mention_agent_ids=["agent-a"],
                to_agent_id="agent-a",
            )

    def test_to_agent_counts_as_mention(self):
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        db = self._db(thread)
        msg = radio_service.send_message(
            db,
            thread_id="th-1",
            from_agent_id="agent-a",
            content="hi",
            to_agent_id="agent-b",
        )
        assert msg.mentions == ["agent-b"]

    def test_mention_dedup_with_to_agent(self):
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        db = self._db(thread)
        msg = radio_service.send_message(
            db,
            thread_id="th-1",
            from_agent_id="agent-a",
            content="hi",
            mention_agent_ids=["agent-b", "agent-b"],
            to_agent_id="agent-b",
        )
        assert msg.mentions == ["agent-b"]

    def test_thread_missing_raises_access(self):
        db = RadioFakeDb()
        with pytest.raises(radio_service.RadioAccessError):
            radio_service.send_message(
                db,
                thread_id="gone",
                from_agent_id="a",
                content="hi",
                mention_agent_ids=["b"],
            )

    def test_thread_closed_raises_access(self):
        thread = RadioThread(id="th-1", status="closed")
        db = self._db(thread)
        with pytest.raises(radio_service.RadioAccessError):
            radio_service.send_message(
                db,
                thread_id="th-1",
                from_agent_id="agent-a",
                content="hi",
                mention_agent_ids=["agent-b"],
            )

    def test_non_member_raises_access(self):
        thread = RadioThread(id="th-1", members=["agent-b"], created_by="agent-c")
        db = self._db(thread)
        with pytest.raises(radio_service.RadioAccessError):
            radio_service.send_message(
                db,
                thread_id="th-1",
                from_agent_id="agent-z",
                content="hi",
                mention_agent_ids=["agent-b"],
            )

    def test_locked_recheck_thread_gone(self):
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        db = self._db(thread, locked_thread=self._GONE)
        with pytest.raises(radio_service.RadioAccessError):
            radio_service.send_message(
                db,
                thread_id="th-1",
                from_agent_id="agent-a",
                content="hi",
                mention_agent_ids=["agent-b"],
            )

    def test_locked_recheck_non_member(self):
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        interloper = RadioThread(id="th-1", members=["agent-x"], created_by="agent-y")
        db = self._db(thread, locked_thread=interloper)
        with pytest.raises(radio_service.RadioAccessError):
            radio_service.send_message(
                db,
                thread_id="th-1",
                from_agent_id="agent-a",
                content="hi",
                mention_agent_ids=["agent-b"],
            )

    def test_corrupted_budget_fails_closed(self):
        thread = RadioThread(
            id="th-1",
            members=["agent-a", "agent-b"],
            metadata={"used_budget_usd": "corrupt"},
        )
        db = self._db(thread)
        with pytest.raises(radio_service.RadioBudgetExceeded) as exc:
            radio_service.send_message(
                db,
                thread_id="th-1",
                from_agent_id="agent-a",
                content="hi",
                mention_agent_ids=["agent-b"],
            )
        assert "corrupted" in str(exc.value)

    def test_budget_exhausted(self, monkeypatch):
        monkeypatch.setattr(radio_config, "team_budget_usd", lambda: 0.20)
        thread = RadioThread(
            id="th-1",
            members=["agent-a", "agent-b"],
            metadata={"used_budget_usd": 0.20},
        )
        db = self._db(thread)
        with pytest.raises(radio_service.RadioBudgetExceeded):
            radio_service.send_message(
                db,
                thread_id="th-1",
                from_agent_id="agent-a",
                content="hi",
                mention_agent_ids=["agent-b"],
                cost_usd=0.01,
            )

    def test_success_with_cost_updates_budget(self, monkeypatch):
        monkeypatch.setattr(radio_config, "team_budget_usd", lambda: 0.20)
        thread = RadioThread(
            id="th-1",
            members=["agent-a", "agent-b"],
            metadata={"used_budget_usd": 0.05},
        )
        db = self._db(thread)
        msg = radio_service.send_message(
            db,
            thread_id="th-1",
            from_agent_id="agent-a",
            content="hi there",
            mention_agent_ids=["agent-b"],
            cost_usd=0.01,
            metadata_json={"is_response": False},
        )
        assert msg.delivered is False
        assert msg.metadata_json == {"is_response": False, "read_by": []}
        assert msg.thread_id == "th-1"
        assert thread.metadata_json["used_budget_usd"] == 0.06
        assert db.committed >= 1
        assert msg in db.refreshed
        assert msg in db.added

    def test_success_zero_cost_no_budget_update(self):
        thread = RadioThread(
            id="th-1",
            members=["agent-a", "agent-b"],
            metadata={"used_budget_usd": 0.05},
        )
        db = self._db(thread)
        radio_service.send_message(
            db,
            thread_id="th-1",
            from_agent_id="agent-a",
            content="free",
            mention_agent_ids=["agent-b"],
        )
        assert thread.metadata_json == {"used_budget_usd": 0.05}

    def test_negative_cost_clamped(self):
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        db = self._db(thread)
        msg = radio_service.send_message(
            db,
            thread_id="th-1",
            from_agent_id="agent-a",
            content="hi",
            mention_agent_ids=["agent-b"],
            cost_usd=-5.0,
        )
        assert msg is not None
        # cost clamped to 0 -> no budget metadata written
        assert thread.metadata_json is None

    def test_non_finite_cost_treated_zero(self):
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        db = self._db(thread)
        for bad in (float("nan"), float("inf"), "abc"):
            radio_service.send_message(
                db,
                thread_id="th-1",
                from_agent_id="agent-a",
                content="hi",
                mention_agent_ids=["agent-b"],
                cost_usd=bad,
            )
        assert thread.metadata_json is None

    def test_at_budget_exactly_allowed(self, monkeypatch):
        monkeypatch.setattr(radio_config, "team_budget_usd", lambda: 0.20)
        thread = RadioThread(
            id="th-1",
            members=["agent-a", "agent-b"],
            metadata={"used_budget_usd": 0.19},
        )
        db = self._db(thread)
        radio_service.send_message(
            db,
            thread_id="th-1",
            from_agent_id="agent-a",
            content="hi",
            mention_agent_ids=["agent-b"],
            cost_usd=0.01,
        )
        assert thread.metadata_json["used_budget_usd"] == 0.2


class TestGetThread:
    def test_found(self):
        thread = RadioThread(id="th-1")
        db = RadioFakeDb(first_rows={"AgentThread": thread})
        assert radio_service.get_thread(db, "th-1") is thread

    def test_missing(self):
        db = RadioFakeDb()
        assert radio_service.get_thread(db, "th-1") is None


class TestMarkRead:
    def test_already_read_noop(self):
        msg = RadioMessage(metadata={"read_by": ["agent-b"]})
        db = RadioFakeDb()
        radio_service.mark_read(db, msg, "agent-b")
        assert msg.metadata_json == {"read_by": ["agent-b"]}
        assert db.committed == 0

    def test_first_read_appends(self):
        msg = RadioMessage(metadata={})
        db = RadioFakeDb()
        radio_service.mark_read(db, msg, "agent-b")
        assert msg.metadata_json == {"read_by": ["agent-b"]}
        assert db.committed == 1

    def test_read_by_two_readers(self):
        msg = RadioMessage(metadata={"read_by": ["agent-b"]})
        db = RadioFakeDb()
        radio_service.mark_read(db, msg, "agent-c")
        assert msg.metadata_json["read_by"] == ["agent-b", "agent-c"]

    def test_all_mentioned_read_marks_delivered(self):
        msg = RadioMessage(mentions=["agent-b", "agent-c"], metadata={})
        db = RadioFakeDb()
        radio_service.mark_read(db, msg, "agent-b")
        assert msg.delivered is False
        radio_service.mark_read(db, msg, "agent-c")
        assert msg.delivered is True

    def test_message_without_metadata(self):
        msg = RadioMessage(metadata=None, mentions=[])
        db = RadioFakeDb()
        radio_service.mark_read(db, msg, "agent-b")
        assert msg.metadata_json == {"read_by": ["agent-b"]}


class TestGetPendingMentions:
    def test_no_agent_returns_empty(self):
        assert radio_service.get_pending_mentions(RadioFakeDb(), "th-1", "") == []

    def test_filters_mentions_and_read(self):
        fresh = datetime.now(UTC)
        msgs = [
            RadioMessage(id="m1", mentions=["agent-b"], created_at=fresh),  # pending
            RadioMessage(id="m2", mentions=["agent-b"], metadata={"read_by": ["agent-b"]}, created_at=fresh),
            RadioMessage(id="m3", mentions=["agent-c"], created_at=fresh),
            RadioMessage(id="m4", mentions=["agent-b", "agent-c"], created_at=fresh),  # pending
        ]
        db = RadioFakeDb(all_rows={"LateralMessage": msgs})
        pending = radio_service.get_pending_mentions(db, "th-1", "agent-b")
        assert [m.id for m in pending] == ["m1", "m4"]

    def test_limit_applied(self):
        fresh = datetime.now(UTC)
        msgs = [
            RadioMessage(id=f"m{i}", mentions=["agent-b"], created_at=fresh)
            for i in range(3)
        ]
        db = RadioFakeDb(all_rows={"LateralMessage": msgs})
        pending = radio_service.get_pending_mentions(db, "th-1", "agent-b", limit=2)
        assert len(pending) == 2

    def test_limit_none_returns_all(self):
        fresh = datetime.now(UTC)
        msgs = [
            RadioMessage(id=f"m{i}", mentions=["agent-b"], created_at=fresh)
            for i in range(3)
        ]
        db = RadioFakeDb(all_rows={"LateralMessage": msgs})
        assert len(radio_service.get_pending_mentions(db, "th-1", "agent-b")) == 3


class TestGetThreadSnapshot:
    def test_thread_missing(self):
        db = RadioFakeDb()
        snap = radio_service.get_thread_snapshot(db, "th-1", "agent-a")
        assert snap == {"thread_id": "th-1", "found": False, "messages": []}

    def test_full_snapshot(self):
        thread = RadioThread(
            id="th-1",
            name="squad",
            members=["agent-a", "agent-b"],
            metadata={"used_budget_usd": 0.5},
        )
        msgs = [
            RadioMessage(
                id="m1",
                from_agent_id="agent-b",
                content="ping",
                mentions=["agent-a"],
                created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
            ),
            RadioMessage(id="m2", mentions=["agent-a"], metadata={"read_by": ["agent-a"]}),
            RadioMessage(id="m3", mentions=[], created_at=None),
        ]
        db = RadioFakeDb(
            first_rows={"AgentThread": thread},
            all_rows={"LateralMessage": msgs},
        )
        snap = radio_service.get_thread_snapshot(db, "th-1", "agent-a", limit=3)
        assert snap["found"] is True
        assert snap["name"] == "squad"
        assert snap["status"] == "open"
        assert snap["member_agent_ids"] == ["agent-a", "agent-b"]
        assert snap["unread_mentions"] == 1
        assert snap["budget_used_usd"] == 0.5
        # newest-first fetch is reversed back to oldest-first: [m1, m2, m3]
        assert snap["messages"][0]["created_at"] is None  # m3 (no timestamp)
        assert snap["messages"][2]["created_at"] == "2026-08-01T12:00:00+00:00"  # m1

    def test_corrupted_budget_returns_none(self):
        thread = RadioThread(
            id="th-1", metadata={"used_budget_usd": "corrupt"}, members=["agent-a"]
        )
        db = RadioFakeDb(
            first_rows={"AgentThread": thread},
            all_rows={"LateralMessage": []},
        )
        snap = radio_service.get_thread_snapshot(db, "th-1", "agent-a")
        assert snap["budget_used_usd"] is None

    def test_message_without_mentions_not_unread(self):
        thread = RadioThread(id="th-1", members=["agent-a"])
        msg = RadioMessage(id="m1", mentions=None)
        db = RadioFakeDb(
            first_rows={"AgentThread": thread},
            all_rows={"LateralMessage": [msg]},
        )
        snap = radio_service.get_thread_snapshot(db, "th-1", "agent-a")
        assert snap["unread_mentions"] == 0
        assert snap["messages"][0]["mentions"] == []


class TestCloseThread:
    def test_missing_returns_none(self):
        db = RadioFakeDb()
        assert radio_service.close_thread(db, "th-1") is None

    def test_closes_thread(self):
        thread = RadioThread(id="th-1")
        db = RadioFakeDb(first_rows={"AgentThread": thread})
        result = radio_service.close_thread(db, "th-1")
        assert result is thread
        assert thread.status == "closed"
        assert db.committed >= 1
        assert thread in db.refreshed


class TestInboxDrainText:
    def test_disabled_returns_empty(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: False)
        assert radio_service.inbox_drain_text("agent-a") == ""

    def test_no_agent_returns_empty(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        assert radio_service.inbox_drain_text("") == ""
        assert radio_service.inbox_drain_text(None) == ""

    def test_db_error_returns_empty(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)

        def broken():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken)
        assert radio_service.inbox_drain_text("agent-a") == ""

    def test_no_thread_found_returns_empty(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        db = RadioFakeDb()  # no threads
        patch_db(monkeypatch, db)
        assert radio_service.inbox_drain_text("agent-a") == ""

    def test_thread_not_agent_member_returns_empty(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        other = RadioThread(id="th-x", members=["agent-z"])
        db = RadioFakeDb(all_rows={"AgentThread": [other]})
        patch_db(monkeypatch, db)
        assert radio_service.inbox_drain_text("agent-a") == ""

    def test_no_pending_returns_empty(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        db = RadioFakeDb(
            all_rows={"AgentThread": [thread], "LateralMessage": []}
        )
        patch_db(monkeypatch, db)
        assert radio_service.inbox_drain_text("agent-a") == ""

    def test_returns_formatted_inbox_and_marks_read(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        msg = RadioMessage(
            id="m1",
            thread_id="th-1",
            from_agent_id="agent-b",
            content="x" * 500,
            mentions=["agent-a"],
        )
        db = RadioFakeDb(
            all_rows={"AgentThread": [thread], "LateralMessage": [msg]}
        )
        patch_db(monkeypatch, db)
        text = radio_service.inbox_drain_text("agent-a")
        assert "[RADIO INBOX] 1 new mention(s) on thread th-1:" in text
        assert f"- @agent-b: {'x' * 400}" in text
        assert "Respond via radio.send_message" in text
        assert text.endswith("\n")
        assert "agent-a" in msg.metadata_json["read_by"]
        assert db.committed >= 1

    def test_explicit_thread_id_used(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        thread = RadioThread(id="th-2", members=["agent-a"])
        msg = RadioMessage(
            id="m1", thread_id="th-2", from_agent_id="agent-b", content="hi", mentions=["agent-a"]
        )
        db = RadioFakeDb(
            all_rows={"AgentThread": [thread], "LateralMessage": [msg]}
        )
        patch_db(monkeypatch, db)
        text = radio_service.inbox_drain_text("agent-a", thread_id="th-2", max_items=2)
        assert "[RADIO INBOX] 1 new mention(s) on thread th-2:" in text

    def test_cap_via_inbox_config(self, monkeypatch):
        monkeypatch.setattr(radio_config, "radio_enabled", lambda: True)
        thread = RadioThread(id="th-1", members=["agent-a", "agent-b"])
        msgs = [
            RadioMessage(id=f"m{i}", from_agent_id="agent-b", content="hi", mentions=["agent-a"])
            for i in range(3)
        ]
        db = RadioFakeDb(all_rows={"AgentThread": [thread], "LateralMessage": msgs})
        patch_db(monkeypatch, db)
        text = radio_service.inbox_drain_text("agent-a", thread_id="th-1")
        assert "3 new mention(s)" in text


# ===========================================================================
# radio_config — re-verification (was 100% via wave-9 suite; keep standalone)
# ===========================================================================

class TestRadioConfigReverify:
    def test_env_bool_unset_default(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_TEST_BOOL", raising=False)
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", True) is True
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", False) is False

    @pytest.mark.parametrize("raw", ["1", "true", "yes", "on", "TRUE", " ON "])
    def test_env_bool_truthy(self, monkeypatch, raw):
        monkeypatch.setenv("ATOM_RADIO_TEST_BOOL", raw)
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", False) is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "anything", ""])
    def test_env_bool_falsy(self, monkeypatch, raw):
        monkeypatch.setenv("ATOM_RADIO_TEST_BOOL", raw)
        assert radio_config._env_bool("ATOM_RADIO_TEST_BOOL", True) is False

    def test_master_switch(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_ENABLED", raising=False)
        assert radio_config.radio_enabled() is True
        monkeypatch.setenv("ATOM_RADIO_ENABLED", "false")
        assert radio_config.radio_enabled() is False

    def test_knob_defaults(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_INBOX_CAP", raising=False)
        monkeypatch.delenv("ATOM_RADIO_BACKLOG_TTL_MIN", raising=False)
        monkeypatch.delenv("ATOM_RADIO_TEAM_BUDGET_USD", raising=False)
        monkeypatch.delenv("ATOM_RADIO_WAIT_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("ATOM_RADIO_BREAKPOINT_GATE", raising=False)
        assert radio_config.inbox_cap() == 10
        assert radio_config.backlog_ttl_minutes() == 30
        assert radio_config.team_budget_usd() == 0.20
        assert radio_config.wait_timeout_seconds() == 30
        assert radio_config.breakpoint_gate_enabled() is True

    def test_knob_overrides(self, monkeypatch):
        monkeypatch.setenv("ATOM_RADIO_INBOX_CAP", "5")
        monkeypatch.setenv("ATOM_RADIO_BACKLOG_TTL_MIN", "7")
        monkeypatch.setenv("ATOM_RADIO_TEAM_BUDGET_USD", "1.5")
        monkeypatch.setenv("ATOM_RADIO_WAIT_TIMEOUT_SECONDS", "3")
        monkeypatch.setenv("ATOM_RADIO_BREAKPOINT_GATE", "off")
        assert radio_config.inbox_cap() == 5
        assert radio_config.backlog_ttl_minutes() == 7
        assert radio_config.team_budget_usd() == 1.5
        assert radio_config.wait_timeout_seconds() == 3
        assert radio_config.breakpoint_gate_enabled() is False

    def test_env_str(self, monkeypatch):
        monkeypatch.delenv("ATOM_RADIO_TEST_STR", raising=False)
        assert radio_config._env_str("ATOM_RADIO_TEST_STR") is None
        monkeypatch.setenv("ATOM_RADIO_TEST_STR", "  v  ")
        assert radio_config._env_str("ATOM_RADIO_TEST_STR") == "v"

    def test_thread_override_chain_id(self):
        assert radio_config.thread_override_chain_id("th-1") is None

    def test_constant(self):
        assert radio_config.ATOM_RADIO_ENABLED == "ATOM_RADIO_ENABLED"


# ===========================================================================
# radio_guard — re-verification (was 100% via wave-9 suite; keep standalone)
# ===========================================================================

class TestRadioGuardReverify:
    def _thread(self, **kw):
        kwargs = dict(members=["agent-a", "agent-b"], created_by="agent-a")
        kwargs.update(kw)
        return RadioThread(**kwargs)

    def _msg(self, mentions, content="hello", metadata=None):
        return RadioMessage(mentions=mentions, content=content, metadata=metadata)

    def test_policy_allowed_mention_and_to(self):
        assert radio_guard.check_send_policy(self._thread(), "agent-a", ["agent-b"], None, "hi") is None
        assert radio_guard.check_send_policy(self._thread(), "agent-a", None, "agent-b", "hi") is None
        assert (
            radio_guard.check_send_policy(self._thread(), "agent-a", ["agent-b"], "agent-b", "hi")
            is None
        )

    def test_policy_no_recipients(self):
        msg = radio_guard.check_send_policy(self._thread(), "agent-a", [], None, "hi")
        assert "mention" in msg

    def test_policy_self_mention_only(self):
        assert radio_guard.check_send_policy(self._thread(), "agent-a", ["agent-a"], None, "hi") is not None

    def test_policy_empty_content(self):
        assert radio_guard.check_send_policy(self._thread(), "agent-a", ["agent-b"], None, "   ") is not None

    def test_policy_oversized_content(self):
        msg = radio_guard.check_send_policy(self._thread(), "agent-a", ["agent-b"], None, "x" * 8001)
        assert "8000" in msg

    def test_policy_closed_or_none_thread(self):
        assert radio_guard.check_send_policy(self._thread(status="closed"), "agent-a", ["agent-b"], None, "hi") is not None
        assert radio_guard.check_send_policy(None, "agent-a", ["agent-b"], None, "hi") is not None

    def test_policy_non_member(self):
        t = self._thread(members=["agent-b"], created_by="agent-z")
        assert radio_guard.check_send_policy(t, "agent-a", ["agent-b"], None, "hi") is not None
        t2 = self._thread(members=["agent-b"], created_by="agent-a")
        assert radio_guard.check_send_policy(t2, "agent-a", ["agent-b"], None, "hi") is None

    def test_budget_allows(self):
        assert radio_guard.budget_allows_send(None, 0.1) is False
        assert radio_guard.budget_allows_send(self._thread(metadata={"used_budget_usd": 0.1}), 0.05) is True
        assert radio_guard.budget_allows_send(self._thread(metadata={"used_budget_usd": 0.1}), 0.1) is True
        assert radio_guard.budget_allows_send(self._thread(metadata={"used_budget_usd": 0.1}), 0.11) is False
        assert radio_guard.budget_allows_send(self._thread(metadata={"used_budget_usd": 0.19}), -5.0) is True
        assert radio_guard.budget_allows_send(self._thread(metadata={"used_budget_usd": "bad"}), 0.05) is True
        assert radio_guard.budget_allows_send(self._thread(metadata={"used_budget_usd": {"x": 1}}), 0.05) is True

    def test_inbox_pending(self, monkeypatch):
        msgs = [
            self._msg(["agent-b"]),
            self._msg(["agent-b"], metadata={"read_by": ["agent-b"]}),
            self._msg(["agent-c"]),
            self._msg(["agent-b", "agent-c"]),
        ]
        pending = radio_guard.inbox_pending_messages(msgs, "agent-b")
        assert len(pending) == 2
        assert radio_guard.inbox_pending_messages([], "agent-b") == []
        monkeypatch.setenv("ATOM_RADIO_INBOX_CAP", "1")
        assert len(radio_guard.inbox_pending_messages(msgs, "agent-b")) == 1

    def test_interrupt_worth_it(self):
        assert radio_guard.interrupt_worth_it(self._msg(["agent-c"]), "agent-b") is False
        assert radio_guard.interrupt_worth_it(self._msg(["agent-b"], content="   "), "agent-b") is False
        assert radio_guard.interrupt_worth_it(self._msg(["agent-b"], metadata={"priority": "high"}), "agent-b") is True
        assert radio_guard.interrupt_worth_it(self._msg(["agent-b"], metadata={"priority": "urgent"}), "agent-b") is True
        assert radio_guard.interrupt_worth_it(self._msg(["agent-b"], metadata={"is_response": True}), "agent-b") is True
        assert radio_guard.interrupt_worth_it(self._msg(["agent-b"]), "agent-b") is False
