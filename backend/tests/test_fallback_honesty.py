# -*- coding: utf-8 -*-
"""The legacy fallback false-success (measurement trial C1, session
3038c208): the modern lane collapsed (planning + replan timeouts under
pool distress) with the draft retrieved but ZERO dispositions
delivered — and "I've processed your request across all connected
platforms." shipped with success=true.

These pins hold the repair at its three layers:
1. the gate decision (pure): the trial-1 shape is replaced; genuine
   content, calc-lane delivery, contextless turns, delivered features,
   and non-template models all stand;
2. the timeout/replan failure persists and reads back byte-identical
   through the production history path;
3. a genuine successful response persists and reads back intact (and
   the gate leaves it alone).

Scratch DB only. Never the live DB. No model calls.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Base, ChatMessage as ChatMessageModel

CANVAS_ID = "2233f463-6fad-443a-959d-e6088e1bb784"
CTX = {"canvas_id": CANVAS_ID}
READ_CTX = {"canvas_id": CANVAS_ID,
            "content": {"subject": "Quote", "rows": []}}

# The captured trial-1 shape: the exact fallthrough claim, template
# leg, nothing delivered, canvas-attached work turn.
CLAIM = "I've processed your request across all connected platforms."

SUCCESS_REPLY = (
    "Row 1 — No. 381 $2,902 confirmed (Sep 18 Chandrakant email); "
    "row 2 — U-22 delivery CONFLICT flagged (In Stock vs 3-4 months); "
    "row 3 — $1,609 confirmed; rows 4-5 not confirmed, decisions open. "
    "Nothing changed, nothing sent.")


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


class TestFallbackHonestyGate:
    def test_trial1_shape_is_replaced_with_the_failed_outcome(self):
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        out = gate(CLAIM, "template", {}, CTX, READ_CTX)
        assert out is not None, "the false completion claim must be replaced"
        assert "couldn't complete" in out
        assert "nothing is underway" in out, (
            "must not imply background work")
        assert "draft itself was read" in out, (
            "the resolved draft read is established fact")
        assert "retry" in out
        assert "processed your request" not in out

    def test_unread_draft_omits_the_read_sentence(self):
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        out = gate(CLAIM, "template", {}, CTX, {"canvas_id": CANVAS_ID})
        assert out is not None and "draft itself was read" not in out
        assert "retry" in out

    def test_genuine_shapes_stand(self):
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        assert gate(SUCCESS_REPLY, "template", {}, CTX, READ_CTX) is None
        assert gate(CLAIM, "calc-lane", {}, CTX, READ_CTX) is None
        assert gate(CLAIM, "template", {}, None, None) is None
        assert gate(CLAIM, "template", {"k": "v"}, CTX, READ_CTX) is None
        assert gate(CLAIM, "deepseek", {}, CTX, READ_CTX) is None
        assert gate(None, "template", {}, CTX, READ_CTX) is None

    def test_gate_is_pure_no_writes(self):
        """The gate rewrites text only: no canvas mutation, no ledger
        write, no status claim — it returns a string or None."""
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        out = gate(CLAIM, "template", {}, CTX, READ_CTX)
        assert isinstance(out, str)
        for verb in ("updated", "applied", "sent", "saved"):
            assert verb not in out.lower()


def _write_turn(factory, conv, user_text, assistant_text,
                execution_id, model="template"):
    import datetime
    from contextlib import contextmanager

    @contextmanager
    def _s():
        s = factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    with _s() as db:
        db.add(ChatMessageModel(
            conversation_id=conv, tenant_id="t", role="user",
            content=user_text,
            created_at=datetime.datetime.now(datetime.timezone.utc)))
        db.add(ChatMessageModel(
            conversation_id=conv, tenant_id="t", role="assistant",
            content=assistant_text,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            metadata_json=json.dumps(
                {"execution_id": execution_id, "model": model,
                 "provider": model})))


def _read_history(factory, conv):
    """The production history read: ChatMessage rows for the
    conversation, hydrated in order (the get_chat_history row path)."""
    from contextlib import contextmanager

    @contextmanager
    def _s():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    with _s() as db:
        rows = (
            db.query(ChatMessageModel)
            .filter(ChatMessageModel.conversation_id == conv)
            .order_by(ChatMessageModel.created_at.asc(),
                      ChatMessageModel.role.desc())
            .all()
        )
        out = []
        for row in rows:
            try:
                meta = json.loads(row.metadata_json or "{}")
            except Exception:
                meta = {}
            out.append({
                "role": row.role,
                "text": row.content,
                "execution_id": meta.get("execution_id"),
                "model": meta.get("model"),
            })
        return out


class TestFailureAndSuccessThroughHistory:
    def test_failed_outcome_persists_and_reads_back_verbatim(self, db):
        """Timeout/replan failure: the honest replacement persists and
        the history path serves it byte-identical — reload preserves
        the truthful terminal."""
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        honest = gate(CLAIM, "template", {}, CTX, READ_CTX)
        assert honest
        _write_turn(db, "conv-fail-1", "Check rows 1 to 5 ...", honest,
                    "exec-fail-1")
        history = _read_history(db, "conv-fail-1")
        assert [h["role"] for h in history] == ["user", "assistant"]
        assert history[1]["text"] == honest
        assert history[1]["execution_id"] == "exec-fail-1"
        assert "processed your request" not in history[1]["text"]

    def test_genuine_success_persists_and_reads_back_verbatim(self, db):
        """A genuine successful response is untouched by the gate and
        survives the same persistence + history path intact."""
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        assert gate(SUCCESS_REPLY, "template", {}, CTX, READ_CTX) is None
        _write_turn(db, "conv-ok-1", "Check rows 1 to 5 ...",
                    SUCCESS_REPLY, "exec-ok-1")
        history = _read_history(db, "conv-ok-1")
        assert history[1]["text"] == SUCCESS_REPLY
        assert "$2,902" in history[1]["text"]
