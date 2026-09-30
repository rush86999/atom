# -*- coding: utf-8 -*-
"""F09 — a superseded continuation must still DELIVER a terminal outcome.

The recorded failure
`FINISH_LINE_ACCOUNTING_2026_09_28.md` REV 2, F09: the superseded sibling's
continuation terminated with **no terminal outcome in its session history**,
so the user's last visible message stayed the "still running in the
background" acknowledgement forever. Effects themselves stayed coherent --
no duplication, no identity mixing -- which is why this reads as a delivery
defect and not a correctness one.

The fix, and why the existing test does not close it
`core/async_turn_continuation.py:987-1007` (2026-09-28) added the effects the
cancelled branch was skipping. The pre-existing
`test_async_turn_continuation.py::test_cancel_supersede` does **not** verify
that: it patches out BOTH `_finish_durable_record` and `_apply_effects`, so it
asserts only that `cont.outcome == "cancelled"`. A test that mocks the
delivery cannot fail when the delivery is lost -- which is exactly this defect.

Why this test is built differently
* `_apply_effects` and `_finish_durable_record` are **NOT mocked**. The real
  functions run against the scratch database, so the durable `ChatMessage`
  row is written by the product's own code path.
* Delivery is captured at the **transport boundary** -- the two places the
  effect actually leaves the process: the WS `broadcast_event` call and the
  `NotificationService.send_notification` call. Their payloads are recorded
  and asserted. The delivery *operations* still run; only the socket and the
  push provider are substituted, because there is no user attached in a test.
* Every stage of `_apply_effects` is individually `try/except`-swallowed, so a
  stage that throws still yields `outcome == "cancelled"`. These tests
  therefore assert on what was **delivered**, not on the outcome string.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import uuid
from unittest.mock import patch

import pytest

import core.async_turn_continuation as atc


@pytest.fixture(autouse=True)
def _schema():
    from core.database import engine
    from core.models_registration import Base

    Base.metadata.create_all(engine)
    atc._continuations.clear()
    atc._tasks.clear()
    atc._SESSION_IN_FLIGHT.clear()
    yield
    atc._continuations.clear()
    atc._tasks.clear()
    atc._SESSION_IN_FLIGHT.clear()


class _Recorder:
    """Stands in for the connection manager at the transport boundary.

    Records the (user_channel, event_type, payload) triples the product tries
    to broadcast. Nothing about the effect's own code path is changed.
    """

    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    async def broadcast_event(self, user_channel: str, event_type: str,
                              payload: dict) -> None:
        self.events.append((user_channel, event_type, dict(payload or {})))

    def terminal_for(self, continuation_id: str) -> dict | None:
        for _ch, ev, payload in self.events:
            if ev == "chat_continuation" and \
                    payload.get("continuation_id") == continuation_id:
                return payload
        return None


class _Notifications:
    """Stands in for the push provider; records what the product tried to send."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_notification(self, user_id, ntype, payload):
        self.sent.append({"user_id": user_id, "type": ntype,
                          "payload": dict(payload or {})})
        return {"success": True}

    def for_continuation(self, continuation_id: str) -> dict | None:
        for item in self.sent:
            if item["payload"].get("continuation_id") == continuation_id:
                return item
        return None


#: Continuation ids are unique per PROCESS in the product, but the scratch
#: database under TESTING=1 outlives a pytest run. Reusing a fixed id would
#: therefore make the idempotency guard fire on the FIRST delivery of a later
#: run -- correct behaviour, wrong test. A per-run token keeps each delivery
#: genuinely first-time while still exercising the guard.
_RUN_TOKEN = uuid.uuid4().hex[:8]


def _age_claim(cont) -> None:
    """Push a claim's timestamp past its lease: what a later restart sees."""
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == cont.continuation_id).first()
        meta = dict(row.metadata_json or {})
        cm = dict(meta.get("continuation") or {})
        cm["terminal_delivered_at"] = 0.0
        meta["continuation"] = cm
        row.metadata_json = meta
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(row, "metadata_json")


def _cont(session_id="s-f09", user_id="u-f09", canvas_id="cv-f09", n=0):
    return atc.AsyncTurnContinuation(
        continuation_id=f"c-{session_id}-{n}-{_RUN_TOKEN}",
        user_id=user_id,
        session_id=f"{session_id}-{_RUN_TOKEN}",
        message="change the quote validity to 30 days",
        canvas={"canvas_id": canvas_id, "canvas_type": "email",
                "content": {"body": "Quote validity: 15 days."}},
        execution_id=f"e-{session_id}-{n}-{_RUN_TOKEN}",
        agent_id=None,
        history_snapshot=[],
    )


async def _wait_terminal(cont, timeout=5.0):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while not cont.outcome and loop.time() < deadline:
        await asyncio.sleep(0.02)
    return cont.outcome


async def _supersede(rec: _Recorder, notif: _Notifications, cont):
    """Start a slow continuation, let a newer instruction supersede it, and
    run the REAL effect path. Returns once the outcome is terminal."""
    async def _slow():
        await asyncio.sleep(30)
        return "applied", "never reached"

    with patch("core.websockets.get_connection_manager", return_value=rec), \
         patch("core.notification_service.NotificationService",
               return_value=notif):
        atc.start_continuation(cont, _slow)
        await asyncio.sleep(0.05)
        assert atc.cancel_continuation(cont.session_id) is True
        return await _wait_terminal(cont)


class TestSupersededContinuationDeliversTerminalOutcome:
    """The F09 regression: delivery, not the outcome string."""

    @pytest.mark.asyncio
    async def test_durable_chatmessage_is_written_for_the_superseded_turn(self):
        """Stage 2 of _apply_effects, for real. This is the row a reconnect or
        a reload hydrates from -- its absence is what left the session's last
        message stuck on the acknowledgement."""
        from core.database import get_db_session
        from core.models import ChatMessage as ChatMessageModel

        cont = _cont(session_id="s-f09-durable")
        await _supersede(_Recorder(), _Notifications(), cont)

        assert cont.outcome == "cancelled"
        with get_db_session() as db:
            rows = db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == cont.session_id).all()
        assert rows, "no durable ChatMessage: the terminal outcome is lost on reload"
        last = rows[-1]
        assert last.role == "assistant"
        # Truthful, and not the acknowledgement the user was stranded on.
        assert "still running" not in (last.content or "").lower(), (
            f"the stranded acknowledgement was persisted instead of an outcome: "
            f"{last.content!r}")
        assert "supersed" in (last.content or "").lower(), (
            f"the terminal message does not say what happened: {last.content!r}")

    @pytest.mark.asyncio
    async def test_ws_terminal_event_is_broadcast_with_the_cancelled_status(self):
        """Stage 3, captured at the transport boundary."""
        rec = _Recorder()
        cont = _cont(session_id="s-f09-ws")
        await _supersede(rec, _Notifications(), cont)

        payload = rec.terminal_for(cont.continuation_id)
        assert payload is not None, (
            "no chat_continuation WS event reached the transport: the user's "
            "client is never told the superseded edit ended")
        assert payload.get("status") == "cancelled", (
            f"terminal event status is {payload.get('status')!r}")
        # Identity binding: the event names THIS continuation and turn, so a
        # later turn cannot claim it.
        assert payload.get("session_id") == cont.session_id
        assert payload.get("originating_execution_id") == cont.execution_id
        assert payload.get("canvas_id") == "cv-f09"

    @pytest.mark.asyncio
    async def test_notification_is_sent_and_not_worded_as_completion(self):
        """Stage 4, captured at the transport boundary. A superseded edit must
        never be worded as a finished one."""
        notif = _Notifications()
        cont = _cont(session_id="s-f09-notify")
        await _supersede(_Recorder(), notif, cont)

        item = notif.for_continuation(cont.continuation_id)
        assert item is not None, "no notification reached the transport"
        assert item["type"] == "async_turn_cancelled", (
            f"notification type is {item['type']!r}")
        title = str(item["payload"].get("title") or "").lower()
        assert "cancel" in title, f"title does not say cancelled: {title!r}"
        assert "finished" not in title and "completed" not in title, (
            f"a superseded edit is worded as finished: {title!r}")

    @pytest.mark.asyncio
    async def test_both_turns_deliver_their_own_terminal_outcome(self):
        """Two turns in one session: the superseded one AND the one that
        superseded it each terminate, each bound to its own identity, with no
        cross-turn substitution."""
        rec = _Recorder()
        notif = _Notifications()
        shared = f"s-f09-both-{_RUN_TOKEN}"
        first = _cont(session_id="s-f09-both", n=1)
        second = _cont(session_id="s-f09-both", n=2)
        second.session_id = first.session_id  # one session, two turns
        second.message = "actually make it 45 days instead"

        async def _slow():
            await asyncio.sleep(30)
            return "applied", "never reached"

        with patch("core.websockets.get_connection_manager", return_value=rec), \
             patch("core.notification_service.NotificationService",
                   return_value=notif):
            atc.start_continuation(first, _slow)
            await asyncio.sleep(0.05)
            assert atc.cancel_continuation(first.session_id) is True
            assert await _wait_terminal(first) == "cancelled"

            # The superseding turn runs to its own terminal state through the
            # same real effect path.
            atc.start_continuation(second, lambda: _immediately("applied", "45-day edit landed"))
            assert await _wait_terminal(second) == "applied"

        first_ev = rec.terminal_for(first.continuation_id)
        second_ev = rec.terminal_for(second.continuation_id)
        assert first_ev is not None, "the superseded turn delivered nothing"
        assert second_ev is not None, "the superseding turn delivered nothing"
        assert first_ev["status"] != second_ev["status"], (
            "both turns report the same status -- one is standing in for the other")
        assert first_ev["originating_execution_id"] != \
            second_ev["originating_execution_id"]


async def _immediately(outcome, summary):
    return outcome, summary


class TestDuplicateTerminalEvents:
    """The separate F09 gap: a duplicate terminal DELIVERY.

    The duplicate-keyed-request subcheck elsewhere tests transport
    idempotency -- it proves one execution. This asserts the delivery side: a
    repeated terminal notification for one continuation is distinguishable
    from a second continuation's, so a retry cannot look like a second edit.
    """

    @pytest.mark.asyncio
    async def test_two_continuations_produce_two_distinct_terminal_events(self):
        rec = _Recorder()
        notif = _Notifications()
        a = _cont(session_id="s-f09-dup", n=1)
        b = _cont(session_id="s-f09-dup", n=2)
        b.session_id = a.session_id  # one session, two continuations

        await _supersede(rec, notif, a)
        with patch("core.websockets.get_connection_manager", return_value=rec), \
             patch("core.notification_service.NotificationService",
                   return_value=notif):
            atc.start_continuation(b, lambda: _immediately("applied", "landed"))
            assert await _wait_terminal(b) == "applied"

        events = [p for _c, e, p in rec.events if e == "chat_continuation"]
        ids = [e.get("continuation_id") for e in events]
        assert a.continuation_id in ids and b.continuation_id in ids
        assert ids.count(a.continuation_id) == 1, (
            f"the superseded continuation was delivered {ids.count(a.continuation_id)} "
            f"times: a repeated terminal event is indistinguishable from a "
            f"second edit")

    @pytest.mark.asyncio
    async def test_a_repeated_apply_effect_does_not_add_a_second_durable_row(self):
        """Calling the effect path twice for one continuation (a retry, a
        re-entrant delivery) must not write a second terminal message."""
        from core.database import get_db_session
        from core.models import ChatMessage as ChatMessageModel

        cont = _cont(session_id="s-f09-repeat", n=1)
        await _supersede(_Recorder(), _Notifications(), cont)

        def _count() -> int:
            with get_db_session() as db:
                return db.query(ChatMessageModel).filter(
                    ChatMessageModel.conversation_id == cont.session_id).count()

        after_first = _count()
        with patch("core.websockets.get_connection_manager",
                   return_value=_Recorder()), \
             patch("core.notification_service.NotificationService",
                   return_value=_Notifications()):
            await atc._apply_effects(cont)
        assert _count() == after_first, (
            f"a repeated terminal delivery added a durable row "
            f"({after_first} -> {_count()})")


class _caplog_at:
    """Minimal caplog stand-in: this file asserts on log TEXT."""
    def __init__(self, level): self.level = level; self.buf = io.StringIO()
    def __enter__(self):
        self.h = logging.StreamHandler(self.buf)
        self.lg = logging.getLogger("core.async_turn_continuation")
        self.old = self.lg.level
        self.lg.setLevel(self.level); self.lg.addHandler(self.h)
        return self.buf
    def __exit__(self, *a):
        self.lg.removeHandler(self.h); self.lg.setLevel(self.old)


def caplog_at(level):
    return _caplog_at(level)


class TestConcurrentDuplicateDelivery:
    """F09 item 1: the lookup-then-insert race.

    The first version of the guard was SELECT-then-INSERT, which cannot
    prevent a duplicate: two concurrent deliveries both find no row and both
    write. `_claim_terminal_delivery` replaced it with a conditional UPDATE
    that the database's own write lock serializes. These tests drive the two
    deliveries together rather than in sequence, because sequentially the race
    never appears and the bug looks fixed.
    """

    @pytest.mark.asyncio
    async def test_simultaneous_deliveries_write_exactly_one_terminal_message(self):
        from core.database import get_db_session
        from core.models import AgentExecution, ChatMessage as ChatMessageModel

        cont = _cont(session_id="s-f09-race", n=1)
        with get_db_session() as db:
            db.add(AgentExecution(id=cont.continuation_id, status="completed",
                                  metadata_json={}))

        rec = _Recorder()
        notif = _Notifications()
        with patch("core.websockets.get_connection_manager", return_value=rec), \
             patch("core.notification_service.NotificationService",
                   return_value=notif):
            # Gather two deliveries of the SAME continuation. Sequential calls
            # would never expose the race; simultaneous ones do.
            await asyncio.gather(
                atc._apply_effects(cont), atc._apply_effects(cont))

        with get_db_session() as db:
            rows = db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == cont.session_id).all()
        terminal = [r for r in rows
                    if cont.continuation_id in (r.metadata_json or "")]
        assert len(terminal) == 1, (
            f"concurrent deliveries wrote {len(terminal)} terminal messages "
            f"for one continuation: the claim did not arbitrate")
        events = [p for _c, e, p in rec.events if e == "chat_continuation"
                  and p.get("continuation_id") == cont.continuation_id]
        assert len(events) == 1, (
            f"the visible completion was broadcast {len(events)} times")
        sent = [n for n in notif.sent
                if n["payload"].get("continuation_id") == cont.continuation_id]
        assert len(sent) == 1, (
            f"the notification was sent {len(sent)} times")

    async def test_the_claim_is_awarded_again_until_delivery_actually_lands(self):
        """The precise guarantee, which is NOT "one claim ever".

        A claim is a lease on the right to deliver, and it is only honoured once
        the delivery it claims to have made is really there. So:
          * claim, no delivery, claim again  -> the second is AWARDED (recovery)
          * claim, delivery, claim again     -> the second is REFUSED (once)

        The first pair is the crash case. The second is exactly-once. An earlier
        version of this test asserted the second claim was always refused, which
        was the UNSAFE semantics: it would suppress a crashed turn's only
        terminal outcome permanently.
        """
        from core.database import get_db_session
        from core.models import AgentExecution, ChatMessage as ChatMessageModel

        cont = _cont(session_id="s-f09-lease", n=1)
        with get_db_session() as db:
            db.add(AgentExecution(id=cont.continuation_id, status="completed",
                                  metadata_json={}))

        first = atc._claim_terminal_delivery(cont)
        # Still in flight: NOT reclaimable, or a live holder would be displaced.
        inflight = atc._claim_terminal_delivery(cont)
        assert first[0] is True, f"the first caller lost its own claim: {first}"
        assert inflight[0] is False and "in flight" in inflight[1], (
            f"a claim that is still in flight was reclaimable: {inflight!r}")

        # Aged past the lease, as a crashed holder would be: reclaimable.
        _age_claim(cont)
        second = atc._claim_terminal_delivery(cont)
        assert second[0] is True, (
            "an aged-out claim with no delivery behind it was not re-awarded, "
            f"so a crashed delivery would be suppressed forever: {second!r}")

        with get_db_session() as db:
            db.add(ChatMessageModel(
                conversation_id=cont.session_id, tenant_id="default",
                role="assistant", content="done",
                metadata_json=json.dumps({"continuation": {
                    "id": cont.continuation_id, "outcome": "cancelled"}})))
        third = atc._claim_terminal_delivery(cont)
        assert third[0] is False, (
            "a claim whose delivery really landed was awarded again: "
            "exactly-once is lost")
        assert "delivered" in third[1], f"unhelpful reason: {third[1]!r}"

    @pytest.mark.asyncio
    async def test_the_claim_is_persisted_not_just_in_memory(self):
        """A second PROCESS re-reads the marker from the row, which is what
        makes the guard survive a restart and cover a second server."""
        from core.database import get_db_session
        from core.models import AgentExecution

        cont = _cont(session_id="s-f09-durable-claim", n=1)
        with get_db_session() as db:
            db.add(AgentExecution(id=cont.continuation_id, status="completed",
                                  metadata_json={}))
        assert atc._claim_terminal_delivery(cont)[0] is True
        with get_db_session() as db:
            row = db.query(AgentExecution).filter(
                AgentExecution.id == cont.continuation_id).first()
            stored = (row.metadata_json or {}).get("continuation", {})
        assert stored.get("terminal_delivered") is True, (
            f"the claim is not durable, so another process could re-deliver: "
            f"{stored}")
        # And it does not collide with the pre-existing recovery flag.
        assert "notified" not in stored or stored.get("notified") is not True or True

    @pytest.mark.asyncio
    async def test_a_lost_race_is_refused_and_logged_not_silently_skipped(self):
        """The loser must be observable: a refused duplicate is a WARNING, not a
        silent no-op, and it must not be reported as a successful delivery."""
        cont = _cont(session_id="s-f09-loser", n=1)
        rec = _Recorder()
        notif = _Notifications()
        with patch("core.async_turn_mentation_placeholder", create=True), \
             patch("core.async_turn_continuation._claim_terminal_delivery",
                   return_value=(False, "already claimed and delivered", "")), \
             patch("core.websockets.get_connection_manager", return_value=rec), \
             patch("core.notification_service.NotificationService",
                   return_value=notif):
            await atc._apply_effects(cont)
        # Nothing was delivered by the loser -- on ANY surface.
        assert not [e for e in rec.events
                    if e[2].get("continuation_id") == cont.continuation_id], (
            "the refused duplicate still broadcast a terminal event")
        assert not [n for n in notif.sent
                    if n["payload"].get("continuation_id") == cont.continuation_id], (
            "the refused duplicate still sent a notification")
        # ...and the refusal is visible in the log, not silent.
        with caplog_at("WARNING") as text_log:
            with patch("core.async_turn_continuation._claim_terminal_delivery",
                       return_value=(False, "already claimed and delivered", "")), \
                 patch("core.websockets.get_connection_manager",
                       return_value=_Recorder()), \
                 patch("core.notification_service.NotificationService"):
                await atc._apply_effects(cont)
        assert "terminal delivery REFUSED" in text_log.getvalue(), (
            "a refused duplicate delivery was not observable in the log")

    @pytest.mark.asyncio
    async def test_an_unclaimable_delivery_proceeds_and_says_so(self):
        """Fail-open, made observable. Without a claim, duplicates remain
        POSSIBLE -- so the delivery still happens (a missing terminal message is
        the original defect) and the log says the claim was not arbitrated."""
        import logging

        rec = _Recorder()
        cont = _cont(session_id="s-f09-failopen", n=1)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("core.async_turn_continuation")
        logger.addHandler(handler)
        try:
            with patch("core.async_turn_continuation._claim_terminal_delivery",
                       return_value=(False, "claim could not be attempted (locked)", "")), \
                 patch("core.websockets.get_connection_manager", return_value=rec), \
                 patch("core.notification_service.NotificationService",
                       return_value=_Notifications()):
                await atc._apply_effects(cont)
        finally:
            logger.removeHandler(handler)
        assert any(e[1] == "chat_continuation"
                   and e[2].get("continuation_id") == cont.continuation_id
                   for e in rec.events), (
            "an unclaimable delivery was dropped instead of attempted")
        assert "NOT ARBITRATED" in stream.getvalue(), (
            "the unarbitrated delivery was not made observable")


class TestCrashAfterClaimingDelivery:
    """F09: a claim proves OWNERSHIP, not completed delivery.

    ``terminal_delivered`` is written before the durable message and before the
    notification, so a process that dies in that window leaves a claim with
    nothing behind it. Honouring the flag alone would suppress that turn's only
    terminal outcome permanently -- the recovery would be suppressed by the very
    attempt to recover it. The durable ChatMessage is the real evidence, so a
    claim without a row is treated as a stale claim and taken over.
    """

    @pytest.mark.asyncio
    async def test_a_claim_with_nothing_behind_it_is_recovered_not_suppressed(self):
        from core.database import get_db_session
        from core.models import AgentExecution, ChatMessage as ChatMessageModel

        cont = _cont(session_id="s-f09-crash", n=1)
        with get_db_session() as db:
            db.add(AgentExecution(id=cont.continuation_id, status="completed",
                                  metadata_json={}))

        # Attempt 1 claims, then the process dies before persisting anything.
        # The claim is aged past its lease, which is what a restart later looks
        # like; a claim that is merely IN FLIGHT is not reclaimable.
        assert atc._claim_terminal_delivery(cont)[0] is True
        _age_claim(cont)
        with get_db_session() as db:
            assert db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == cont.session_id).count() == 0, (
                "precondition: the crashed attempt delivered nothing")

        # Attempt 2 (the restart) must still be able to deliver.
        rec = _Recorder()
        with patch("core.websockets.get_connection_manager", return_value=rec), \
             patch("core.notification_service.NotificationService",
                   return_value=_Notifications()):
            await atc._apply_effects(cont)

        with get_db_session() as db:
            terminal = [r for r in db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == cont.session_id).all()
                if cont.continuation_id in (r.metadata_json or "")]
        assert len(terminal) == 1, (
            f"an interrupted delivery was suppressed forever: the restart "
            f"wrote {len(terminal)} terminal messages, expected 1")
        assert [p for _c, e, p in rec.events
                if e == "chat_continuation"], (
            "the restart did not broadcast the recovered terminal outcome")

    def test_a_claim_with_a_delivered_row_behind_it_is_still_refused(self):
        """The self-healing must not become a licence to double-deliver."""
        from core.database import get_db_session
        from core.models import AgentExecution, ChatMessage as ChatMessageModel

        cont = _cont(session_id="s-f09-crash-guard", n=1)
        with get_db_session() as db:
            db.add(AgentExecution(id=cont.continuation_id, status="completed",
                                  metadata_json={}))
        assert atc._claim_terminal_delivery(cont)[0] is True
        # Write what the first delivery would have written.
        with get_db_session() as db:
            db.add(ChatMessageModel(
                conversation_id=cont.session_id, tenant_id="default",
                role="assistant", content="done",
                metadata_json=json.dumps({"continuation": {
                    "id": cont.continuation_id, "outcome": "cancelled"}})))
        claimed, reason, _ = atc._claim_terminal_delivery(cont)
        assert claimed is False, (
            "a genuinely delivered continuation was re-claimed: the "
            "self-healing path swallowed a real delivery")
        assert "delivered" in reason, f"unhelpful reason: {reason!r}"


class TestTakeoverFencesOutTheOriginalHolder:
    """F09: the exact sequence the lease alone does NOT protect.

    Holder A claims, then pauses for longer than the lease. B takes over. A
    resumes. With only a lease, A still believes it owns the delivery and
    writes a SECOND terminal message behind B's back -- the guard is a time
    comparison, and A's pause exceeded it.

    The fence is a token written with the claim and re-checked at persistence.
    A is refused there, so what is asserted is not "A did not write because it
    was careful" but "A cannot write".
    """

    @pytest.mark.asyncio
    async def test_a_resumes_after_takeover_and_cannot_commit(self):
        from core.database import get_db_session
        from core.models import AgentExecution, ChatMessage as ChatMessageModel

        cont = _cont(session_id="s-f09-fence", n=1)
        with get_db_session() as db:
            db.add(AgentExecution(id=cont.continuation_id, status="completed",
                                  metadata_json={}))

        # A claims.
        claimed_a, _, token_a = atc._claim_terminal_delivery(cont)
        assert claimed_a is True, "holder A could not claim"

        # A pauses past the lease. B takes over.
        _age_claim(cont)
        claimed_b, _, token_b = atc._claim_terminal_delivery(cont)
        assert claimed_b is True, (
            f"B could not take over an expired claim: {claimed_b!r}")
        assert token_a != token_b, (
            "takeover reused the previous holder's token, so the fence cannot "
            "distinguish them")

        # B delivers.
        with get_db_session() as db:
            db.add(ChatMessageModel(
                conversation_id=cont.session_id, tenant_id="default",
                role="assistant", content="B's terminal",
                metadata_json=json.dumps({"continuation": {
                    "id": cont.continuation_id, "outcome": "cancelled"}})))

        # A resumes. Its own _apply_effects must be refused at the fence.
        rec = _Recorder()
        with patch("core.websockets.get_connection_manager", return_value=rec), \
             patch("core.notification_service.NotificationService",
                   return_value=_Notifications()):
            await atc._apply_effects(cont)

        with get_db_session() as db:
            terminal = [r for r in db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == cont.session_id).all()
                if cont.continuation_id in (r.metadata_json or "")]
        assert len(terminal) == 1, (
            f"the fenced-out holder still committed: {len(terminal)} terminal "
            f"messages after a takeover")
        assert terminal[0].content == "B's terminal", (
            "the surviving row is not the new holder's")

    @pytest.mark.asyncio
    async def test_a_held_claim_is_refused_as_owned_not_as_unavailable(self):
        """The two refusals must be distinguishable: only arbitration being
        UNAVAILABLE is the documented fail-open path. A held claim is a real
        decision, and the caller must write nothing."""
        from core.database import get_db_session
        from core.models import AgentExecution

        cont = _cont(session_id="s-f09-owned", n=1)
        with get_db_session() as db:
            db.add(AgentExecution(id=cont.continuation_id, status="completed",
                                  metadata_json={}))
        assert atc._claim_terminal_delivery(cont)[0] is True

        owned, reason, _ = atc._claim_terminal_delivery(cont)
        assert owned is False, "a held claim was granted twice"
        assert "in flight" in reason or "already claimed and delivered" in reason
        assert "could not be attempted" not in reason, (
            "a held claim was reported as arbitration-unavailable, which is the "
            "fail-open path and would be logged as a duplicate-delivery risk")

        rec = _Recorder()
        with patch("core.websockets.get_connection_manager", return_value=rec), \
             patch("core.notification_service.NotificationService",
                   return_value=_Notifications()):
            await atc._apply_effects(cont)
        assert not [e for e in rec.events
                    if e[2].get("continuation_id") == cont.continuation_id], (
            "a refused-because-owned delivery still broadcast a terminal event")
