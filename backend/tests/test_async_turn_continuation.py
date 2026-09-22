# -*- coding: utf-8 -*-
"""Durable, idempotent async turn continuation (corrected contract, 2026-09-22).

Grounding: the SEPARATELY demonstrated timeout case (edit-leg bound deaths
with planners of 41.5-60.3s; the turn_budget_exceeded trace) — the original
evidence-validation incident is fixed and verified elsewhere.

These pins cover the six contract points:
1. Idempotency — "write succeeded, response timed out" is detected via the
   canvas audit (same-session advance) and NEVER applies twice.
2. Conflict — an audit advance from another source holds the retry back.
3. Durability — the durable AgentExecution record enforces one-in-flight
   (including across "restarts": a stale running row refuses new forks) and
   the boot pass notifies recovered rows exactly once.
4. Supersede — a new user turn cancels a pending continuation.
5. Distinct outcomes — applied / awaiting_approval (learning-mode draft,
   "ready for review" wording) / already_applied / conflict / failed /
   cancelled; notifications distinguish review from completion.
6. History consistency — the next conversational turn SEES the result
   (in-memory session append), as does reconnect (DB row) and restart
   (hydration shape).
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.async_turn_continuation as atc
import integrations.chat_orchestrator as chat


class _IntegrityError(Exception):
    pass


def _fresh_registry():
    atc._continuations.clear()
    atc._tasks.clear()
    atc._SESSION_IN_FLIGHT.clear()


@pytest.fixture(autouse=True)
def _clean_registry():
    _fresh_registry()
    # Atomic-claim semantics WITHOUT a database: an in-memory PK map with
    # the same insert-refuses-duplicate behavior. Tests that exercise the
    # real claim path override these patches.
    claims: dict = {}

    def fake_claim(cont):
        if cont.session_id in claims:
            raise _IntegrityError("UNIQUE constraint failed")
        claims[cont.session_id] = cont.continuation_id
        return True

    def fake_claimed(sid):
        return claims.get(sid)

    def fake_release(sid):
        claims.pop(sid, None)

    with patch.object(atc, "_claim_session", side_effect=fake_claim), \
         patch.object(atc, "_claimed_id", side_effect=fake_claimed), \
         patch.object(atc, "_release_claim", side_effect=fake_release):
        yield
    for t in list(atc._tasks.values()):
        if not t.done():
            t.cancel()
    _fresh_registry()


async def _wait_terminal(cont, timeout=3.0):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while not cont.outcome and loop.time() < deadline:
        await asyncio.sleep(0.02)
    return cont.outcome


def _runner(outcome, summary="done"):
    async def _r():
        return outcome, summary
    return _r


def _cont(session_id="s1", user_id="u1", canvas_id="cv1", **kw):
    return atc.AsyncTurnContinuation(
        continuation_id="c-" + session_id + "-" + str(
            len(atc._continuations)) + "-" + str(kw.pop("n", 0)),
        user_id=user_id,
        session_id=session_id,
        message="rebuild the draft",
        canvas={"canvas_id": canvas_id, "canvas_type": "email",
                "content": {"body": "x"}},
        execution_id="e1",
        agent_id=None,
        history_snapshot=[],
        **kw,
    )


class TestRegistryAndOutcomes:
    async def test_applied_outcome(self):
        cont = _cont()
        with patch.object(atc, "_create_durable_record"), \
             patch.object(atc, "_finish_durable_record"), \
             patch.object(atc, "_apply_effects", new=AsyncMock()):
            assert atc.start_continuation(cont, _runner("applied", "ok"))
            assert await _wait_terminal(cont) == "applied"

    async def test_failed_when_runner_raises(self):
        cont = _cont()
        async def _boom():
            raise RuntimeError("planner down")
        with patch.object(atc, "_create_durable_record"), \
             patch.object(atc, "_finish_durable_record"), \
             patch.object(atc, "_apply_effects", new=AsyncMock()):
            atc.start_continuation(cont, _boom)
            assert await _wait_terminal(cont) == "failed"

    async def test_one_in_flight_per_session(self):
        cont1, cont2 = _cont("s1"), _cont("s1", n=1)
        with patch.object(atc, "_create_durable_record"), \
             patch.object(atc, "_finish_durable_record"), \
             patch.object(atc, "_apply_effects", new=AsyncMock()):
            assert atc.start_continuation(cont1, _runner("applied")) is True
            assert atc.start_continuation(cont2, _runner("applied")) is False

    async def test_claim_row_refuses_across_restart(self):
        """The CLAIM row is the cross-restart authority: a stale claim
        (the process died before reaping) blocks a new fork even though
        the in-process map is empty."""
        cont = _cont("s9")
        with patch.object(atc, "_create_durable_record"), \
             patch.object(atc, "_claim_session",
                          side_effect=_IntegrityError("held")), \
             patch.object(atc, "_claim_insert_refused", return_value=True), \
             patch.object(atc, "_apply_effects", new=AsyncMock()):
            assert atc.start_continuation(cont, _runner("applied")) is False

    async def test_duplicate_claim_race_refuses_loser(self):
        """Two racing workers: both pass the in-process check, one claim
        INSERT wins, the loser gets the integrity failure and refuses —
        no check-then-act window."""
        calls = {"n": 0}

        def racing_claim(cont):
            calls["n"] += 1
            if calls["n"] > 1:
                raise _IntegrityError("UNIQUE constraint failed")
            return True

        cont1, cont2 = _cont("s-race"), _cont("s-race", n=1)
        with patch.object(atc, "_create_durable_record"), \
             patch.object(atc, "_finish_durable_record"), \
             patch.object(atc, "_claim_session", side_effect=racing_claim), \
             patch.object(atc, "_claim_insert_refused", return_value=True), \
             patch.object(atc, "_apply_effects", new=AsyncMock()):
            # cont1 wins the race via the fixture's fake claim; racing_claim
            # simulates the loser's INSERT hitting the constraint.
            assert atc.start_continuation(cont1, _runner("applied")) is True
            assert atc.start_continuation(cont2, _runner("applied")) is False

    async def test_cancel_during_execution_with_landed_write(self):
        """Cancellation does not undo a completed write: when the operation
        already landed, the outcome is already_applied WITH effects, not
        cancelled."""
        cont = _cont("s-land")
        effects = AsyncMock()

        async def _apply_then_hang():
            # Simulate: write lands (op-id probe True), then cancellation
            # arrives while effects/bookkeeping would still run.
            await asyncio.sleep(30)
            return "applied", "never"

        with patch.object(atc, "_create_durable_record"), \
             patch.object(atc, "_finish_durable_record"), \
             patch.object(atc, "_claim_session"), \
             patch.object(atc, "_operation_landed", return_value=True), \
             patch.object(atc, "_apply_effects", new=effects):
            atc.start_continuation(cont, _apply_then_hang)
            await asyncio.sleep(0.02)
            atc.cancel_continuation("s-land")
            await asyncio.sleep(0.05)
        assert cont.outcome == "already_applied"
        effects.assert_awaited_once()

    async def test_cancel_supersede(self):
        cont = _cont()
        async def _slow():
            await asyncio.sleep(30)
            return "applied", "never"
        with patch.object(atc, "_create_durable_record"), \
             patch.object(atc, "_finish_durable_record"), \
             patch.object(atc, "_apply_effects", new=AsyncMock()):
            atc.start_continuation(cont, _slow)
            await asyncio.sleep(0.02)
            assert atc.cancel_continuation("s1") is True
            assert await _wait_terminal(cont) == "cancelled"


class TestIdempotencyAndConflict:
    def _audit(self, ts, session_id):
        return {"created_at": ts, "session_id": session_id,
                "action_type": "update"}

    async def test_write_succeeded_then_timeout_is_already_applied(self):
        """The timed-out attempt's write landed (audit advanced, attributed
        to the SAME session): the retry must NOT run the edit leg again."""
        orch = MagicMock()
        orch._try_canvas_edit = AsyncMock(return_value={
            "message": "should never run",
            "data": {"canvas_edit": {"updated": True}}})
        cont = _cont("s1")
        cont.snapshot_audit_ts = "2026-09-22T10:00:00"
        with patch.object(atc, "_latest_audit",
                          return_value=self._audit(
                              "2026-09-22T10:05:00", "s1")):
            outcome, summary = await atc.run_canvas_edit_continuation(
                orch, cont)
        assert outcome == "already_applied"
        orch._try_canvas_edit.assert_not_awaited()
        assert "already landed" in summary

    async def test_other_source_advance_is_conflict(self):
        orch = MagicMock()
        orch._try_canvas_edit = AsyncMock(return_value={
            "message": "should never run",
            "data": {"canvas_edit": {"updated": True}}})
        cont = _cont("s1")
        cont.snapshot_audit_ts = "2026-09-22T10:00:00"
        with patch.object(atc, "_latest_audit",
                          return_value=self._audit(
                              "2026-09-22T10:05:00", "other-session")):
            outcome, summary = await atc.run_canvas_edit_continuation(
                orch, cont)
        assert outcome == "conflict"
        orch._try_canvas_edit.assert_not_awaited()
        assert "held back" in summary

    async def test_no_advance_runs_the_retry(self):
        orch = MagicMock()
        orch._try_canvas_edit = AsyncMock(return_value={
            "message": "Canvas updated.",
            "data": {"canvas_edit": {"updated": True}}})
        cont = _cont("s1")
        cont.snapshot_audit_ts = "2026-09-22T10:00:00"
        with patch.object(atc, "_latest_audit",
                          return_value=self._audit(
                              "2026-09-22T10:00:00", "s1")):
            outcome, summary = await atc.run_canvas_edit_continuation(
                orch, cont)
        assert outcome == "applied"
        orch._try_canvas_edit.assert_awaited_once()

    async def test_learning_mode_is_awaiting_approval_not_applied(self):
        orch = MagicMock()
        orch._try_canvas_edit = AsyncMock(return_value={
            "message": "my draft attempt",
            "data": {"canvas_edit": {
                "updated": True, "learning_mode": True}}})
        cont = _cont("s1")
        with patch.object(atc, "_latest_audit", return_value=None):
            outcome, _ = await atc.run_canvas_edit_continuation(orch, cont)
        assert outcome == "awaiting_approval"


class TestEffectsAndContextContinuity:
    async def test_next_turn_sees_result_in_memory(self):
        """Backend context, not just the frontend: the in-memory session
        history gains the continuation turn (single event loop, same
        orchestrator instance that forked)."""
        orch = MagicMock()
        session = {"id": "s1", "history": [
            {"message": "rebuild", "response": {"message": "bg note"},
             "intent": {}, "timestamp": "", "error": False}]}
        orch.conversation_sessions = {"s1": session}
        cont = _cont("s1")
        cont.outcome = "applied"
        cont.summary = "Canvas updated with the eight-line list."
        object.__setattr__(cont, "_orchestrator", orch)
        with patch("core.database.get_db_session",
                   _fake_db(SimpleNamespace(add=lambda r: None))), \
             patch("core.websockets.get_connection_manager",
                   return_value=MagicMock(
                       broadcast_event=AsyncMock())), \
             patch("core.notification_service.NotificationService") as ns:
            ns.return_value = MagicMock(
                send_notification=AsyncMock(return_value={}))
            await atc._apply_effects(cont)
        assert len(session["history"]) == 2
        late = session["history"][-1]
        assert late["error"] is False
        assert "applied" in late["response"]["message"]
        assert "eight-line list" in late["response"]["message"]

    async def test_db_row_shape_for_reconnect_and_restart(self):
        cont = _cont("s1")
        cont.outcome = "awaiting_approval"
        cont.summary = "draft ready"
        added = []
        db = SimpleNamespace(add=added.append)
        with patch("core.database.get_db_session", _fake_db(db)), \
             patch("core.websockets.get_connection_manager",
                   return_value=MagicMock(
                       broadcast_event=AsyncMock())), \
             patch("core.notification_service.NotificationService") as ns:
            ns.return_value = MagicMock(
                send_notification=AsyncMock(return_value={}))
            await atc._apply_effects(cont)
        row = added[0]
        assert row.role == "assistant"
        assert "awaiting_approval" in row.content
        import json as _json
        meta = _json.loads(row.metadata_json)
        assert meta["continuation"]["outcome"] == "awaiting_approval"

    async def test_notification_distinguishes_review_from_completion(self):
        for outcome, expected_type in (
            ("applied", "async_turn_applied"),
            ("awaiting_approval", "async_turn_awaiting_review"),
            ("conflict", "async_turn_conflict"),
            ("failed", "async_turn_failed"),
        ):
            cont = _cont("s1")
            cont.outcome = outcome
            cont.summary = "x"
            with patch("core.database.get_db_session",
                       _fake_db(SimpleNamespace(add=lambda r: None))), \
                 patch("core.websockets.get_connection_manager",
                       return_value=MagicMock(
                           broadcast_event=AsyncMock())), \
                 patch(
                     "core.notification_service.NotificationService") as ns:
                inst = MagicMock()
                inst.send_notification = AsyncMock(return_value={})
                ns.return_value = inst
                await atc._apply_effects(cont)
                got = inst.send_notification.await_args.args[1]
            assert got == expected_type, (outcome, got)


class TestRecoveryPass:
    def test_crashed_unnotified_rows_get_notified_once(self):
        row = SimpleNamespace(
            id="c-x",
            metadata_json={
                "recovery": {"crashed": True},
                "continuation": {
                    "session_id": "s1", "user_id": "u1",
                    "canvas_id": "cv1"},
            },
        )
        with patch("core.database.get_db_session",
                   _fake_db(_QueryDb([row]))), \
             patch(
                 "core.notification_service.NotificationService") as ns:
            ns.return_value = MagicMock(
                send_notification=AsyncMock(return_value={}))
            out = atc.notify_recovered_continuations()
        assert out["recovered_notified"] == 1
        # The notified flag is persisted → the second pass is a no-op.
        row.metadata_json["continuation"]["notified"] = True
        with patch("core.database.get_db_session",
                   _fake_db(_QueryDb([row]))), \
             patch(
                 "core.notification_service.NotificationService") as ns:
            ns.return_value = MagicMock(
                send_notification=AsyncMock(return_value={}))
            out2 = atc.notify_recovered_continuations()
        assert out2["recovered_notified"] == 0


class _QueryDb:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *a):
        return self

    def filter(self, *a):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _fake_db:
    def __init__(self, db):
        self._db = db

    def __call__(self):
        ctx = self

        class _Ctx:
            def __enter__(self):
                return ctx._db

            def __exit__(self, *a):
                return False
        return _Ctx()


@pytest.mark.asyncio
async def test_orchestrator_forks_once_reply_honest_action_skipped(
        monkeypatch):
    monkeypatch.setenv("ATOM_CHAT_REQUEST_DEADLINE_SECONDS", "8")
    monkeypatch.setattr(chat, "_CANVAS_LEG_MAX_SECONDS", 0.5)
    monkeypatch.setattr(chat, "_REPLY_LEG_MIN_SECONDS", 1.0)

    orch = chat.ChatOrchestrator()
    session = {"id": "sess-b1", "history": []}
    canvas = {"canvas_id": "cv1", "canvas_type": "email",
              "content": {"subject": "Draft", "body": "Unchanged"}}

    async def slow_edit(*a, **k):
        await asyncio.sleep(5)
        return None

    forks = []

    def fake_fork(orch_ref, **kwargs):
        forks.append(kwargs)
        return "cont-1"

    async def fake_reply(message, history, routing_overrides=None, **kwargs):
        assert kwargs.get("async_continuation_forked") is True
        return {"content": "finishing in the background", "model": "m",
                "provider": "p"}

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_try_canvas_edit", side_effect=slow_edit),
        patch.object(orch, "_try_canvas_action", new=AsyncMock()) as action,
        patch.object(orch, "_get_qwen_response", side_effect=fake_reply),
        patch("core.chat_tool_planner.plan_tool_use",
              new=AsyncMock(return_value=None)),
        patch("core.chat_tool_planner._provenance_menu",
              new=AsyncMock(return_value="")),
        patch("core.async_turn_continuation.fork_canvas_edit_continuation",
              side_effect=fake_fork),
    ):
        result = await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-b1",
            context={"canvas_id": "cv1"})

    assert len(forks) == 1
    action.assert_not_awaited()
    assert result["message"] == "finishing in the background"


@pytest.mark.asyncio
async def test_new_turn_supersedes_pending_continuation(monkeypatch):
    """The orchestrator cancels a pending continuation at turn entry — the
    new instruction wins."""
    superseded = []

    orch = chat.ChatOrchestrator()
    session = {"id": "sess-b2", "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_get_qwen_response", new=AsyncMock(return_value={
            "content": "ok", "model": "m", "provider": "p"})),
        patch("core.chat_tool_planner.plan_tool_use",
              new=AsyncMock(return_value=None)),
        patch("core.chat_tool_planner._provenance_menu",
              new=AsyncMock(return_value="")),
        patch("core.async_turn_continuation.supersede_pending_continuation",
              side_effect=lambda sid, msg, ctx: superseded.append(
                  (sid, msg)) or True),
    ):
        await orch.process_chat_message(
            "u1", "rebuild the draft with the new quotes", "sess-b2",
            context={"canvas_id": "cv1"})

    assert superseded and superseded[0][0] == "sess-b2", (
        "an edit-shaped turn must attempt to supersede a pending "
        "continuation")


@pytest.mark.asyncio
async def test_non_edit_turns_never_fork(monkeypatch):
    monkeypatch.setenv("ATOM_CHAT_REQUEST_DEADLINE_SECONDS", "8")
    monkeypatch.setattr(chat, "_CANVAS_LEG_MAX_SECONDS", 0.5)
    monkeypatch.setattr(chat, "_REPLY_LEG_MIN_SECONDS", 1.0)

    orch = chat.ChatOrchestrator()
    session = {"id": "sess-b3", "history": []}
    canvas = {"canvas_id": "cv1", "canvas_type": "email",
              "content": {"subject": "Draft", "body": "Unchanged"}}

    async def slow_edit(*a, **k):
        await asyncio.sleep(5)
        return None

    forks = []
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_try_canvas_edit", side_effect=slow_edit),
        patch.object(orch, "_get_qwen_response", new=AsyncMock(return_value={
            "content": "ok", "model": "m", "provider": "p"})),
        patch("core.chat_tool_planner.plan_tool_use",
              new=AsyncMock(return_value=None)),
        patch("core.chat_tool_planner._provenance_menu",
              new=AsyncMock(return_value="")),
        patch("core.async_turn_continuation.fork_canvas_edit_continuation",
              side_effect=lambda *a, **k: forks.append(k)),
    ):
        await orch.process_chat_message(
            "u1", "what does the draft say about pricing", "sess-b3",
            context={"canvas_id": "cv1"})

    assert forks == []


class TestOperationIdIdempotency:
    async def test_landed_operation_is_definitive_already_applied(self):
        """A prior retry of THIS operation already wrote (audit carries the
        operation_id): never re-run, even with no timestamp advance."""
        orch = MagicMock()
        orch._try_canvas_edit = AsyncMock(return_value={
            "message": "never runs",
            "data": {"canvas_edit": {"updated": True}}})
        cont = _cont("s1")
        cont.snapshot_audit_ts = ""  # no timestamp signal at all
        with patch.object(atc, "_operation_landed", return_value=True):
            outcome, summary = await atc.run_canvas_edit_continuation(
                orch, cont)
        assert outcome == "already_applied"
        orch._try_canvas_edit.assert_not_awaited()

    async def test_retry_passes_operation_id_and_revision_token(self):
        """The retry stamps its writes with the operation id and enforces
        the revision token captured at retry start."""
        orch = MagicMock()
        orch._try_canvas_edit = AsyncMock(return_value={
            "message": "ok", "data": {"canvas_edit": {"updated": True}}})
        cont = _cont("s1")
        fake_latest = {"id": "audit-42", "created_at": "2026-09-22T11:00:00",
                       "session_id": "other", "action_type": "update"}
        with patch.object(atc, "_latest_audit", return_value=fake_latest):
            outcome, _ = await atc.run_canvas_edit_continuation(orch, cont)
        assert outcome == "applied"
        kwargs = orch._try_canvas_edit.await_args.kwargs
        assert kwargs["operation_id"] == cont.continuation_id
        assert kwargs["expected_prior_audit_id"] == "audit-42"


class TestAtomicRevisionDoor:
    def _tool(self):
        from tools.canvas_crud_tool import update_canvas_content
        return update_canvas_content

    def _db(self, latest_row):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.return_value = latest_row
        db.query.return_value = q
        return db

    async def test_mismatched_revision_refuses_without_writing(self):
        latest = MagicMock(
            id="audit-NEW", action_type="update",
            details_json={"content": {}, "title": "t"},
            created_at=None, tenant_id="default")
        added = []
        db = self._db(latest)
        db.add = added.append
        with patch("core.database.get_db_session",
                   _fake_db(db)), \
             patch("tools.canvas_crud_tool._verify_canvas_owner",
                   return_value=True):
            result = await self._tool()(
                "u1", "cv1", {"body": "new"}, "email",
                operation_id="op-1",
                expected_prior_audit_id="audit-OLD")
        assert result.get("conflict") is True
        assert result.get("success") is False
        assert added == [], "a refused write must append nothing"

    async def test_matching_revision_writes_with_operation_stamp(self):
        from datetime import datetime as _dt
        latest = MagicMock(
            id="audit-42", action_type="update",
            details_json={"content": {}, "title": "t"},
            created_at=_dt(2026, 9, 22, 12, 0, 0), tenant_id="default")
        added = []
        db = self._db(latest)
        db.add = added.append
        with patch("core.database.get_db_session",
                   _fake_db(db)), \
             patch("tools.canvas_crud_tool._verify_canvas_owner",
                   return_value=True), \
             patch("tools.canvas_crud_tool._broadcast_canvas_update",
                   new=AsyncMock()):
            result = await self._tool()(
                "u1", "cv1", {"body": "new"}, "email",
                operation_id="op-1",
                expected_prior_audit_id="audit-42")
        assert result.get("success") is True
        assert added, "the write must append its audit row"
        details = added[0].details_json
        assert details["operation_id"] == "op-1"


class TestConditionalSupersede:
    def test_status_question_does_not_cancel(self):
        cancelled = []
        with patch.object(atc, "cancel_continuation",
                          side_effect=lambda sid: cancelled.append(sid)
                          or True):
            got = atc.supersede_pending_continuation(
                "s1", "did the background update finish?", {})
        assert got is False
        assert cancelled == []

    def test_new_edit_instruction_cancels(self):
        cancelled = []
        with patch.object(atc, "cancel_continuation",
                          side_effect=lambda sid: cancelled.append(sid)
                          or True):
            got = atc.supersede_pending_continuation(
                "s1", "rebuild the draft with the new quotes",
                {"canvas_id": "cv1"})
        assert got is True
        assert cancelled == ["s1"]


class TestRestartVisibility:
    def test_hydration_includes_continuation_row(self):
        """After a restart the session hydrates from ChatMessage rows — the
        continuation row must survive that path (role/content/metadata
        shape) and not be flagged as an error turn."""
        orch = chat.ChatOrchestrator()
        session = {"id": "s-h", "history": []}
        row = SimpleNamespace(
            role="assistant",
            content="[background continuation — applied of: \"rebuild\"]\n"
                    "Canvas updated.",
            metadata_json='{"continuation": {"outcome": "applied"}}',
            created_at="2026-09-22T12:00:00")
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.order_by.return_value.all.return_value = [row]
        db.query.return_value = q
        with patch("core.database.get_db_session", _fake_db(db)):
            orch._hydrate_session_history("s-h", session)
        assert len(session["history"]) == 1
        turn = session["history"][0]
        assert turn["error"] is False
        assert "applied" in turn["response"]["message"]


class TestRealDatabaseSuccessPath:
    """DB-level demonstration of the SUCCESS contract against the REAL
    audit trail (the live LLM-served run additionally requires provider
    credits — open separately): a stamped write lands, the definitive
    probe detects it, a duplicate execution of the same operation refuses,
    and the atomic revision door refuses a raced write."""

    def _scratch_canvas(self, db, canvas_id=None, user="u-int"):
        import uuid as _uuid
        from core.models import Canvas, CanvasAudit
        from datetime import datetime, timezone as tz

        canvas_id = canvas_id or ("cv-int-" + _uuid.uuid4().hex[:10])
        seed_id = "audit-seed-" + canvas_id
        # Idempotent against the file-backed scratch DB.
        db.query(Canvas).filter(Canvas.id == canvas_id).delete()
        db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id).delete()
        db.query(CanvasAudit).filter(CanvasAudit.id == seed_id).delete()
        self._seed_id = seed_id
        db.add(Canvas(
            id=canvas_id, tenant_id="default", created_by=user,
            name="Quote draft",
            canvas_type="email",
            content={"subject": "s", "body": "old"},
            status="active",
            created_at=datetime.now(tz.utc),
            updated_at=datetime.now(tz.utc),
        ))
        db.add(CanvasAudit(
            id=seed_id, canvas_id=canvas_id, tenant_id="default",
            session_id=None, action_type="update", user_id=user,
            canvas_type="email",
            created_at=datetime(2026, 9, 22, 10, 0, 0),
            details_json={"content": {"subject": "s", "body": "old"},
                          "title": "Quote draft"},
        ))

    def test_stamped_write_probe_and_duplicate_refusal(self):
        import asyncio
        from core.database import get_db_session
        from core.models import CanvasAudit

        canvas_id = "cv-int-1"
        with get_db_session() as db:
            self._scratch_canvas(db, canvas_id)
        self._ids = getattr(self, "_ids", [])

        cont = _cont("s-int", canvas_id=canvas_id)
        seed_id = self._seed_id

        # The retry's write: stamped with the operation id, planned against
        # the seed revision.
        from tools.canvas_crud_tool import update_canvas_content

        async def _scenario():
            result = await update_canvas_content(
                "u-int", canvas_id, {"subject": "s", "body": "REBUILT"},
                "email", operation_id=cont.continuation_id,
                expected_prior_audit_id=seed_id)
            assert result.get("success") is True, result
            # (2) the definitive probe sees it — real query, no mocks.
            assert atc._operation_landed(cont) is True
            # (3) a duplicate execution of the SAME operation refuses
            # before any write (pre-apply gate, definitive layer).
            orch = MagicMock()
            orch._try_canvas_edit = AsyncMock(return_value={
                "message": "never", "data": {"canvas_edit": {
                    "updated": True}}})
            outcome, summary = await atc.run_canvas_edit_continuation(
                orch, cont)
            assert outcome == "already_applied"
            orch._try_canvas_edit.assert_not_awaited()
            # (4) the atomic door: a write planned against the SEED (now
            # stale) revision is refused and appends nothing.
            before = None
            with get_db_session() as db:
                before = db.query(CanvasAudit).filter(
                    CanvasAudit.canvas_id == canvas_id).count()
            raced = await update_canvas_content(
                "u-int", canvas_id, {"body": "RACED"}, "email",
                operation_id="op-other",
                expected_prior_audit_id=seed_id)
            assert raced.get("conflict") is True
            with get_db_session() as db:
                after = db.query(CanvasAudit).filter(
                    CanvasAudit.canvas_id == canvas_id).count()
            assert after == before, "a refused write must append nothing"

        asyncio.run(_scenario())

    def test_unstamped_session_heuristic_still_catches_interactive_write(self):
        import asyncio
        from core.database import get_db_session
        from core.models import CanvasAudit
        from datetime import datetime, timezone as tz

        canvas_id = "cv-int-2"
        with get_db_session() as db:
            self._scratch_canvas(db, canvas_id)
            seed_id = self._seed_id

        cont = _cont("s-int2", canvas_id=canvas_id)
        cont.snapshot_audit_ts = "2026-09-22T10:00:00"

        async def _scenario():
            # The TIMED-OUT INTERACTIVE attempt's write: unstamped (it
            # could not know the operation id) but session-attributed.
            from tools.canvas_crud_tool import update_canvas_content

            result = await update_canvas_content(
                "u-int", canvas_id, {"body": "INTERACTIVE LANDED"},
                "email")
            assert result.get("success") is True
            with get_db_session() as db:
                row = db.query(CanvasAudit).filter(
                    CanvasAudit.canvas_id == canvas_id,
                    CanvasAudit.details_json.contains(
                        "INTERACTIVE LANDED")).first()
                assert row is not None
                row.session_id = cont.session_id  # the attribution
                import json as _j
                row.details_json = _j.dumps(row.details_json)
            orch = MagicMock()
            orch._try_canvas_edit = AsyncMock()
            outcome, _ = await atc.run_canvas_edit_continuation(orch, cont)
            assert outcome == "already_applied"
            orch._try_canvas_edit.assert_not_awaited()

        asyncio.run(_scenario())
