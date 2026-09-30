# -*- coding: utf-8 -*-
"""F09 — a terminal outcome whose message never landed is RECOVERED, repeatably.

The gap this closes
`terminal_delivered` is written before the message. A crash in that window
leaves a row that says the turn finished and a history that says nothing about
it — the stranded acknowledgment. The lease makes such a claim *reclaimable*,
but a lease schedules nothing: expiry alone does not retry anything. So without
this pass the outcome stays stranded until some unrelated turn happens to touch
it.

`recover_missing_terminal_deliveries()` is a pure scan of durable state, which
is what makes it repeatable: a pass that meets an UNEXPIRED lease defers the
row, and a later pass, after expiry, delivers it. It takes no scheduler into
account, so it is callable with the general scheduler disabled.

The canvas mutation is NEVER replayed — only the terminal message is written.
These tests assert that too, by counting audit rows across the recovery.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

import core.async_turn_continuation as atc

_TOKEN = uuid.uuid4().hex[:8]


class _Recorder:
    def __init__(self):
        self.events = []

    async def broadcast_event(self, ch, ev, payload):
        self.events.append((ch, ev, dict(payload or {})))


class _Notifications:
    def __init__(self):
        self.sent = []

    async def send_notification(self, user_id, ntype, payload):
        self.sent.append({"type": ntype, "payload": dict(payload or {})})
        return {"success": True}


def _seed_crashed_after_claim(session_id: str, *, lease_age: float = 0.0):
    """A terminal continuation that claimed delivery and then died before
    persisting the message — the exact stranded state."""
    from core.database import get_db_session
    from core.models import AgentExecution

    cid = f"c-recov-{session_id}-{_TOKEN}"
    with get_db_session() as db:
        db.add(AgentExecution(
            id=cid, status="completed",
            metadata_json={"continuation": {
                "session_id": session_id, "user_id": "u-recov",
                "canvas_id": "cv-recov", "outcome": "cancelled",
                "summary": "superseded by a newer canvas instruction; that "
                           "update's result is reported separately",
                "originating_execution_id": f"e-{session_id}",
                # a claim that is ALREADY set, aged by lease_age seconds
                "terminal_delivered": True,
                "terminal_delivered_at": time.time() - lease_age,
            }}))
    return cid


def _terminal_rows(session_id: str) -> list:
    from core.database import get_db_session
    from core.models import ChatMessage as ChatMessageModel

    with get_db_session() as db:
        return [r for r in db.query(ChatMessageModel).filter(
            ChatMessageModel.conversation_id == session_id).all()
            if r.metadata_json and "continuation" in r.metadata_json
            and r.metadata_json.count(session_id) >= 0
            and '"id"' in r.metadata_json]


def _recov_ids(session_id: str) -> list:
    """The terminal messages belonging to THIS recovery run."""
    rows = _terminal_rows(session_id)
    return [r for r in rows if f"c-recov-{session_id}-{_TOKEN}" in
            (r.metadata_json or "")]


_SID: list = []


async def _pass():
    with patch("core.websockets.get_connection_manager",
               return_value=_Recorder()), \
         patch("core.notification_service.NotificationService",
               return_value=_Notifications()):
        return await atc.recover_missing_terminal_deliveries(
            session_ids=set(_SID))


class TestRecoveryGap:
    @pytest.mark.asyncio
    async def test_restart_before_expiry_defers_then_expiry_delivers_once(self):
        """The exact sequence, end to end.

        claim -> crash before the message -> restart BEFORE expiry -> the pass
        defers -> expiry -> the pass delivers exactly one correctly bound row.
        """
        sid = "s-recov-seq"
        # The recovery scan is GLOBAL by design -- it finds every terminal
        # continuation whose message is missing, across runs. The scratch
        # database outlives a pytest run, so this asserts about ITS OWN
        # continuation rather than about the total, which would be a
        # measurement of what earlier runs left behind.
        _SID.clear(); _SID.append(sid)
        cid = _seed_crashed_after_claim(sid, lease_age=0.0)

        # Restart #1, immediately: the lease has not expired, so this must
        # DEFER. If it delivered here, the lease would be decoration.
        first = await _pass()
        assert not [d for d in first["details"]
                    if d["continuation_id"] == cid and "delivered" in d], (
            f"a pass inside the lease delivered anyway: {first}")
        assert [d for d in first["details"]
                if d["continuation_id"] == cid and "deferred" in d], (
            f"an unexpired claim was not deferred: {first}")
        assert not _recov_ids(sid), "a row was written before the lease expired"

        # Expire the lease, as the passage of time would.
        _age_all(sid)
        second = await _pass()
        assert [d for d in second["details"]
                if d["continuation_id"] == cid and "delivered" in d], (
            f"the expired claim was not recovered: {second}")

        rows = _recov_ids(sid)
        assert len(rows) == 1, f"expected exactly one row, got {len(rows)}"
        meta = json.loads(rows[0].metadata_json)["continuation"]
        assert meta["outcome"] == "cancelled"
        assert meta["canvas_id"] == "cv-recov"
        assert meta["originating_execution_id"] == f"e-{sid}"
        assert rows[0].role == "assistant"
        # Truthful wording, not the stranded acknowledgment.
        assert "still running" not in (rows[0].content or "").lower()
        assert "supersed" in (rows[0].content or "").lower()

    @pytest.mark.asyncio
    async def test_a_later_restart_adds_no_second_row(self):
        """Restart again after the recovery: the outcome must not be delivered
        twice just because the process came back."""
        sid = "s-recov-idem"
        _SID.clear(); _SID.append(sid)
        _seed_crashed_after_claim(sid, lease_age=10000.0)
        await _pass()
        assert len(_recov_ids(sid)) == 1
        again = await _pass()
        assert again["delivered"] == 0, (
            f"a second restart delivered again: {again}")
        assert len(_recov_ids(sid)) == 1, (
            f"a second restart added a row: {len(_recov_ids(sid))}")

    @pytest.mark.asyncio
    async def test_recovery_is_repeatable_without_the_general_scheduler(self):
        """No scheduler may be required. The pass takes no scheduling decision
        into account, so it works with the scheduler explicitly disabled."""
        sid = "s-recov-nosched"
        _SID.clear(); _SID.append(sid)
        _seed_crashed_after_claim(sid, lease_age=10000.0)
        with patch.dict(os.environ, {"ENABLE_SCHEDULER": "false",
                                     "ENABLE_INGESTION_SYNC": "false"}):
            out = await _pass()
        assert out["delivered"] == 1, f"recovery needed the scheduler: {out}"

    @pytest.mark.asyncio
    async def test_recovery_never_replays_the_canvas_mutation(self):
        """Only the message is written. Re-running the edit would be the
        duplicate-mutation bug this area exists to prevent, so the recovery path
        must not touch the canvas at all."""
        from core.database import get_db_session
        from core.models import CanvasAudit

        sid = "s-recov-nomutate"
        _SID.clear(); _SID.append(sid)
        _seed_crashed_after_claim(sid, lease_age=10000.0)
        with get_db_session() as db:
            before = db.query(CanvasAudit).count()
        with patch("core.chat_canvas_editor.apply_canvas_edit") as edit:
            await _pass()
        with get_db_session() as db:
            after = db.query(CanvasAudit).count()
        assert edit.call_count == 0, (
            f"recovery re-entered the canvas editor: {edit.call_args}")
        assert after == before, (
            f"recovery changed the audit trail: {before} -> {after}")
        assert len(_recov_ids(sid)) == 1, "the message was not delivered"


def _age_all(session_id: str) -> None:
    """Age every claim in this session past the lease."""
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        for row in db.query(AgentExecution).all():
            meta = dict(row.metadata_json or {})
            cm = dict(meta.get("continuation") or {})
            if cm.get("session_id") != session_id:
                continue
            cm["terminal_delivered_at"] = time.time() - 100000.0
            meta["continuation"] = cm
            row.metadata_json = meta
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(row, "metadata_json")
