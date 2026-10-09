# -*- coding: utf-8 -*-
"""The legacy fallback false-success (measurement trial C1, session
3038c208): the modern lane collapsed (planning + replan timeouts under
pool distress) with the draft retrieved but ZERO dispositions
delivered — and "I've processed your request across all connected
platforms." shipped with success=true.

Owner work order 2026-10-09 (rev 2): the repair is OUTCOME handling,
not message rewriting. Three layers are pinned here:

1. the gate + outcome resolver (real functions): the claim is replaced
   for canvas AND standalone requests; the outcome comes from durable
   records (task carriers, delivered findings, pending continuations) —
   never from sentence text or dict non-emptiness alone;
2. the PRODUCTION PATH (rev 2 work order): the real orchestrator runs
   with the planner kill-switch + a failed reply leg, the real route
   persists, and the REAL history handler reads back — text, machine
   status, and persisted metadata agree;
3. the coordinated legacy envelope agrees with the outcome too.

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
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from core.models_registration import Base
from core import database as _database_module
from integrations import chat_routes as cr

CANVAS_ID = "2233f463-6fad-443a-959d-e6088e1bb784"
CTX = {"canvas_id": CANVAS_ID}
READ_CTX = {"canvas_id": CANVAS_ID,
            "content": {"subject": "Quote", "rows": []}}

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


class TestFallbackOutcomeResolver:
    """The record-driven outcome mapping (owner work order table)."""

    def test_canvas_read_nothing_delivered_is_failed(self):
        from integrations.chat_orchestrator import _fallback_turn_outcome
        out = _fallback_turn_outcome({}, None, {}, CTX, "default",
                                     canvas_was_read=True)
        assert out["state"] == "failed"

    def test_standalone_no_records_is_unconfirmed_never_processed(self):
        from integrations.chat_orchestrator import _fallback_turn_outcome
        out = _fallback_turn_outcome({}, None, {}, {}, "default")
        assert out["state"] == "unconfirmed"

    def test_feature_failures_are_not_delivery(self):
        from integrations.chat_orchestrator import _fallback_turn_outcome
        out = _fallback_turn_outcome(
            {}, None,
            {"tasks": {"success": False, "error_code": "timeout"},
             "analytics": {"success": True, "message": "done"}}, {},
            "default")
        # a success FLAG with no structured data is not delivery —
        # dictionary non-emptiness alone proves nothing
        assert out["state"] != "completed"
        assert out["delivered"] is False

    def test_feature_payloads_never_assert_delivery(self):
        """Even structured feature payloads do not count as delivery:
        the legacy handlers return stub data ("AI Analytics logic
        here", empty results) — durable carriers only."""
        from integrations.chat_orchestrator import _fallback_turn_outcome
        out = _fallback_turn_outcome(
            {}, None, {"search": {"success": True,
                                  "data": {"results": [1, 2]}}},
            {}, "default")
        assert out["delivered"] is False
        assert out["state"] == "unconfirmed"

    def test_findings_plus_remaining_work_is_partial(self):
        from integrations.chat_orchestrator import _fallback_turn_outcome
        session = {"_pending_file_result": {"structured_result": {"rows": []}},
                   "_last_open_work": {"actions": [
                       {"next_action": "open the No. 622 quote"}]}}
        out = _fallback_turn_outcome(session, None, {}, {}, "default")
        assert out["state"] == "partial"
        assert any("No. 622" in w for w in out["open_work"])

    def test_recorded_obligations_are_named(self):
        """A pending-file task is a RECORDED obligation — it names the
        unfinished work (it resumes next turn; it is not background
        work — only a genuine in-flight continuation is)."""
        from integrations.chat_orchestrator import _fallback_turn_outcome
        session = {"_pending_file_task": {"objective": "re-read rows 1-5",
                                          "requested_targets": ["381"]}}
        out = _fallback_turn_outcome(session, None, {}, {}, "default")
        assert any("re-read" in w for w in out["open_work"])

    def test_genuine_in_flight_continuation_is_queued(self, monkeypatch):
        from core.async_turn_continuation import continuation_in_flight
        monkeypatch.setattr(continuation_in_flight.__class__ if False
                            else continuation_in_flight,
                            "__wrapped__", continuation_in_flight,
                            raising=False)
        import core.async_turn_continuation as atc
        monkeypatch.setattr(atc, "continuation_in_flight",
                            lambda sid: True)
        from integrations.chat_orchestrator import _fallback_turn_outcome
        out = _fallback_turn_outcome(
            {"id": "conv-cont-1"}, None, {}, {}, "default")
        assert out["state"] == "continuation_queued"


class TestFallbackHonestyGate:
    def test_trial1_shape_is_replaced_with_the_failed_outcome(self):
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        out = gate(CLAIM, "template", {}, CTX, READ_CTX)
        assert out is not None, "the false completion claim must be replaced"
        assert "couldn't complete" in out["message"]
        assert "draft itself was read" in out["message"], (
            "the resolved draft read is established fact")
        assert "retry" in out["message"]
        assert "processed your request" not in out["message"]
        assert out["outcome"]["state"] == "failed"

    def test_standalone_claim_is_replaced_too(self):
        """Work order rev 2: the canvas-only exception is GONE — a
        standalone request earns the same honest outcome."""
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        out = gate(CLAIM, "template", {}, {}, None)
        assert out is not None, "standalone claim must be replaced"
        assert "processed your request" not in out["message"]
        assert out["outcome"]["state"] == "unconfirmed"

    def test_genuine_shapes_stand(self):
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        assert gate(SUCCESS_REPLY, "template", {}, CTX, READ_CTX) is None
        assert gate(CLAIM, "calc-lane", {}, CTX, READ_CTX) is None
        assert gate(CLAIM, "deepseek", {}, CTX, READ_CTX) is None
        assert gate(None, "template", {}, CTX, READ_CTX) is None


def _mk_app_and_db(monkeypatch):
    """The PRODUCTION fixture: real router, real persistence, real
    history handler — all on one scratch DB."""
    from contextlib import contextmanager
    from integrations import chat_routes as cr
    from core.models import User as UserModel

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        s = factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(_database_module, "get_db_session", get_db_session)
    cr.chat_orchestrator.conversation_sessions.clear()

    with get_db_session() as s:
        s.add(UserModel(id="user_1", email="u1@example.com",
                        first_name="U", last_name="One", role="user",
                        tenant_id="t1", status="active"))
        s.commit()

    app = FastAPI()
    app.include_router(cr.router)
    return app, factory, get_db_session


def _seam_failure(monkeypatch, reply=None):
    """Inject failure at the EXISTING planner/reply seam of the
    orchestrator instance THE ROUTE owns (chat_routes builds its own
    ChatOrchestrator — patching the module singleton misses it)."""
    from integrations import chat_routes as cr

    orch = cr.chat_orchestrator

    async def fake_reply(*a, **k):
        return reply
    monkeypatch.setattr(orch, "_get_qwen_response", fake_reply)

    from integrations.chat_orchestrator import ChatIntent

    async def fixed_intent(message, session):
        # DATA_ANALYSIS has no branch in the legacy generator — the
        # fallthrough completion claim fires (the C1 shape).
        return {"primary_intent": ChatIntent.DATA_ANALYSIS,
                "confidence": 0.9}
    monkeypatch.setattr(orch, "_analyze_intent", fixed_intent)

    class _DeadLLM:
        async def generate_completion(self, *a, **k):
            raise RuntimeError("injected: no provider in this test")

        async def __call__(self, *a, **k):
            raise RuntimeError("injected: no provider in this test")
    monkeypatch.setattr(orch, "llm_service", _DeadLLM(), raising=False)
    monkeypatch.setenv("ATOM_DISABLE_TOOL_PLANNER", "1")


def _db_override(factory):
    from core.database import get_db

    def _override():
        s = factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()
    return _override


def _route_call(factory, message, context, session_id=None):
    """Drive the PRODUCTION chat route (real orchestrator + real
    persistence + real envelope), then the REAL history handler."""
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from integrations import chat_routes as cr

    user = SimpleNamespace(id="user_1", tenant_id="t1")
    http_response = SimpleNamespace(headers={})
    http_request = SimpleNamespace(headers={})
    resp = asyncio.run(cr.send_chat_message(
        request=cr.ChatMessageRequest(
            message=message, user_id="user_1", session_id=session_id,
            context=context),
        http_request=http_request,
        http_response=http_response,
        current_user=user,
        db=factory(),
    ))
    return resp, user


class TestProductionPath:
    def test_canvas_failure_envelope_and_history_agree(self, monkeypatch):
        """Work order case 1: canvas-attached request fails without
        dispositions — the envelope carries success=False + the failure
        classification, the persisted row + the REAL history handler
        read back the same truthful text."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        from core.models import Canvas, CanvasAudit
        with factory() as sc:
            sc.add(Canvas(id=CANVAS_ID, tenant_id="t1",
                          created_by="user_1", name="Quote draft",
                          canvas_type="email",
                          content={"body": "quote rows"}))
            # the audit trail IS the source of truth for the reader
            sc.add(CanvasAudit(
                canvas_id=CANVAS_ID, tenant_id="t1",
                action_type="fork", user_id="user_1",
                details_json={"content": {"body": "quote rows"}}))
            sc.commit()

        resp, user = _route_call(
            factory,
            "Check rows 1 to 5 of the current quote draft against our "
            "taught sources.",
            {"canvas_id": CANVAS_ID})
        assert resp.success is False
        assert resp.error_code == "turn_failed_no_result"
        assert resp.outcome == "failed"
        assert "processed your request" not in resp.message
        assert "couldn't complete" in resp.message

        # the REAL history handler (production read path)
        history = asyncio.run(
            cr.get_chat_history(session_id=resp.session_id,
                                user_id="user_1", current_user=user))
        asst = [m for m in history.messages if m["role"] == "assistant"]
        assert asst, "the assistant row must exist"
        assert "processed your request" not in (asst[-1]["response"]["message"])
        assert "couldn't complete" in asst[-1]["response"]["message"]

    def test_standalone_failure_same_treatment(self, monkeypatch):
        """Work order case 2: a standalone request reaches the same
        empty fallback and gets the same honest outcome (no canvas
        exception)."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)

        resp, user = _route_call(
            factory,
            "Pull together the five-row comparison for me.", {})
        assert resp.success is False
        assert resp.error_code in ("turn_failed_no_result",
                                   "outcome_unconfirmed")
        assert "processed your request" not in resp.message

    def test_calculate_delivery_survives_narration_failure(
            self, monkeypatch):
        """Work order case 6: engine-backed calculation delivery rides
        out the narration failure — the pending-input question ships
        (calc-lane), the gate stands down, success stays true."""
        app, factory, get_db_session = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)

        # stage the durable continuation under the id the turn will
        # use: an open pending-input question
        conv = "conv-calc-1"
        from core.pricing_calculation import _record_pending_calc_inputs
        _record_pending_calc_inputs(
            conv, "default", "Service estimate",
            ["hours", "materials"], {"rate": "150"},
            "ROUNDUP(hours * rate + materials, 0)", "v-test",
            canvas_id=None, user_bound={})

        resp, user = _route_call(
            factory,
            "Estimate a service job using our taught rates.",
            {"workspace_id": "default"}, session_id=conv)
        assert resp.success is True, (
            "the calc lane's pending question is a real delivery")
        assert "still need" in resp.message and "hours" in resp.message
        assert "The calculation did not run yet" in resp.message, (
            "the reply must not claim a computation happened")
        assert resp.model == "calc-lane"
        assert "processed your request" not in resp.message

    def test_genuine_success_remains_successful(self, monkeypatch):
        """Work order case 7: genuine success stays successful, the
        gate stands down, and the REAL history handler serves it."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch, reply={
            "content": SUCCESS_REPLY, "model": "deepseek",
            "provider": "deepseek"})

        resp, user = _route_call(
            factory,
            "Check rows 1 to 5 of the current quote draft.",
            {"canvas_id": CANVAS_ID})
        assert resp.success is True
        assert "$2,902" in resp.message
        assert resp.error_code is None

        history = asyncio.run(
            cr.get_chat_history(session_id=resp.session_id,
                                user_id="user_1", current_user=user))
        asst = [m for m in history.messages if m["role"] == "assistant"]
        assert asst and "$2,902" in asst[-1]["response"]["message"]


class TestCoordinatedEnvelope:
    def test_claim_over_nothing_is_failure(self):
        """Work order: the coordinated legacy envelope agrees with the
        outcome — the claim over zero delivered work is a failure, not
        a success."""
        from integrations.chat_orchestrator import chat_orchestrator
        from integrations.chat_orchestrator import ChatIntent

        intent = {"primary_intent": ChatIntent.DATA_ANALYSIS,
                  "confidence": 0.9}
        resp = chat_orchestrator._generate_coordinated_response(
            "do the thing", intent, {}, {"id": "s-coord-1"})
        assert resp["success"] is False
        assert "processed your request" not in resp["message"]
        assert resp["outcome"] in ("failed", "unconfirmed")
        assert resp["error_code"] is not None

    def test_non_claim_message_keeps_established_envelope(self):
        from integrations.chat_orchestrator import chat_orchestrator
        from integrations.chat_orchestrator import ChatIntent, FeatureType

        intent = {"primary_intent": ChatIntent.DATA_ANALYSIS,
                  "confidence": 0.9}
        responses = {FeatureType.AGENT: {
            "success": True, "message": SUCCESS_REPLY,
            "data": {"results": [1, 2]}}}
        resp = chat_orchestrator._generate_coordinated_response(
            "do the thing", intent, responses, {"id": "s-coord-2"})
        assert resp["success"] is True
        assert resp["outcome"] is None

    def test_in_flight_continuation_keeps_success_named(self, monkeypatch):
        """The durable-continuation row of the owner's table: an
        acknowledgement naming the unfinished work — the established
        success semantics for queued work, with the outcome explicit."""
        import core.async_turn_continuation as atc
        monkeypatch.setattr(atc, "continuation_in_flight",
                            lambda sid: True)
        from integrations.chat_orchestrator import chat_orchestrator
        from integrations.chat_orchestrator import ChatIntent

        intent = {"primary_intent": ChatIntent.DATA_ANALYSIS,
                  "confidence": 0.9}
        resp = chat_orchestrator._generate_coordinated_response(
            "do the thing", intent, {}, {"id": "s-coord-3"})
        assert resp["success"] is True
        assert resp["outcome"] == "continuation_queued"
        assert "queued" in resp["message"].lower()
