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

    def test_canvas_read_alone_is_unconfirmed_not_failed(self):
        """Finding 4: a read proves execution occurred — not that it
        failed. Without a recorded failure the state is unconfirmed."""
        from integrations.chat_orchestrator import _fallback_turn_outcome
        out = _fallback_turn_outcome({}, None, {}, CTX, "default",
                                     canvas_was_read=True)
        assert out["state"] == "unconfirmed"

    def test_recorded_operation_failure_is_failed(self):
        from integrations.chat_orchestrator import _fallback_turn_outcome
        session = {"_task_run_id": "run-1"}
        record = {"operations": [{
            "operation_id": "op-1", "execution_id": "exec-9",
            "status": "failed"}]}
        monkey_out = None
        import integrations.chat_orchestrator as com
        orig = com._task_lifecycle_for
        com._task_lifecycle_for = lambda *a, **k: type(
            "TL", (), {"get_task": lambda self, rid: record})()
        try:
            out = com._fallback_turn_outcome(
                session, "exec-9", {}, {}, "default")
        finally:
            com._task_lifecycle_for = orig
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

    def test_stale_carrier_alone_never_validates(self):
        """Finding 2: a session carrier is not a validated answer by
        itself — validation needs THIS turn's values on the operations
        or this turn's delivery record. The route-level partial case is
        pinned in TestPartialAndQueuedThroughThePath (seeded job)."""
        from integrations.chat_orchestrator import _fallback_turn_outcome
        session = {"_pending_file_result": {
                       "execution_id": "exec-p-1",
                       "structured_result": {"rows": [
                           {"item": "No. 622", "value": "2421"}]}},
                   "_last_open_work": {"actions": [
                       {"next_action": "open the No. 622 quote"}]}}
        out = _fallback_turn_outcome(session, "exec-p-1", {}, {}, "default")
        assert out["state"] == "unconfirmed"
        assert out["delivered"] is False

    def test_turn_open_work_snapshot_is_named(self):
        """The turn's own open-work snapshot names the unfinished work —
        recorded obligations, not background work."""
        from integrations.chat_orchestrator import _fallback_turn_outcome
        session = {"_last_open_work": {"actions": [
            {"next_action": "re-read rows 1-5"}]}}
        out = _fallback_turn_outcome(session, None, {}, {}, "default")
        assert any("re-read" in w for w in out["open_work"])
        assert out["state"] in ("unconfirmed", "partial")

    def test_own_continuation_is_queued_foreign_is_not(self, monkeypatch):
        """A continuation bound to THIS turn's execution queues the
        turn; ANOTHER operation's continuation must not certify it
        (owner finding: identity-bound continuations)."""
        import core.async_turn_continuation as atc
        from integrations.chat_orchestrator import _fallback_turn_outcome
        monkeypatch.setattr(atc, "continuation_in_flight",
                            lambda sid: "exec-own-1")
        out = _fallback_turn_outcome(
            {"id": "conv-cont-1"}, "exec-own-1", {}, {}, "default")
        assert out["state"] == "continuation_queued"
        assert out["continuation_id"] == "exec-own-1"
        # a foreign continuation changes nothing
        monkeypatch.setattr(atc, "continuation_in_flight",
                            lambda sid: "exec-other-9")
        out = _fallback_turn_outcome(
            {"id": "conv-cont-1"}, "exec-own-1", {}, {}, "default")
        assert out["state"] != "continuation_queued"


class TestFallbackHonestyGate:
    def test_trial1_shape_is_replaced_with_the_failed_outcome(self):
        from integrations.chat_orchestrator import (
            _fallback_honesty_replacement as gate)
        out = gate(CLAIM, "template", {}, CTX, READ_CTX)
        assert out is not None, "the false completion claim must be replaced"
        assert "couldn't confirm" in out["message"], (
            "finding 4: a read without a recorded failure is unconfirmed, "
            "not failed")
        assert "draft itself was read" in out["message"], (
            "the resolved draft read is established fact")
        assert "processed your request" not in out["message"]
        assert out["outcome"]["state"] == "unconfirmed"

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


def _fixed_execution(monkeypatch, exec_id="e-turn"):
    """Bind the turn's execution identity so tests can seed operations
    the identity-bound resolver attributes to THIS execution. Also
    creates the AgentExecution row (status success) — the M1 finalizer
    reads it, and an unknown record is delivered as unverified
    (success=false) by design."""
    from datetime import datetime, timezone
    from integrations import chat_routes as cr
    from core.models import AgentExecution

    def _fixed(session_id, agent_id, message, **k):
        try:
            with _db_session_ctx() as db:
                db.add(AgentExecution(
                    id=exec_id, status="success",
                    started_at=datetime.now(timezone.utc),
                    result_summary="test execution",
                    metadata_json={"session_id": session_id}))
                db.commit()
        except Exception:
            pass
        return exec_id

    def _db_session_ctx():
        from core.database import get_db_session
        return get_db_session()
    monkeypatch.setattr(cr.chat_orchestrator, "_start_chat_execution",
                        _fixed)


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
        """Work order case 1 (rev 3): a canvas-attached request whose
        outcome is unverified carries success=False + outcome
        unconfirmed (a read proves execution occurred, not failure) —
        the persisted row + the REAL history handler read back the same
        truthful text."""
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
        assert resp.error_code == "outcome_unconfirmed"
        assert resp.outcome == "unconfirmed"
        assert "processed your request" not in resp.message
        assert "couldn't confirm" in resp.message

        # the REAL history handler (production read path)
        history = asyncio.run(
            cr.get_chat_history(session_id=resp.session_id,
                                user_id="user_1", current_user=user))
        asst = [m for m in history.messages if m["role"] == "assistant"]
        assert asst, "the assistant row must exist"
        assert "processed your request" not in (asst[-1]["response"]["message"])
        assert "couldn't confirm" in asst[-1]["response"]["message"]

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
        # the reply leg SUCCEEDS (a genuine model answer); the planner is
        # disabled but the LLM service is NOT poisoned — an in-turn
        # helper failure must not relabel a delivered answer
        # (provider-failure wording is a different case, covered above).
        orch = cr.chat_orchestrator

        async def good_reply(*a, **k):
            return {"content": SUCCESS_REPLY, "model": "deepseek",
                    "provider": "deepseek"}
        monkeypatch.setattr(orch, "_get_qwen_response", good_reply)
        monkeypatch.setenv("ATOM_DISABLE_TOOL_PLANNER", "1")
        _fixed_execution(monkeypatch, "e-turn")
        conv = "conv-genuine-1"
        cr.chat_orchestrator._get_or_create_session("user_1", conv)
        # the execution-bound evidence carrier: this turn's findings
        cr.chat_orchestrator.conversation_sessions[conv][
            "_pending_file_result"] = {
                "execution_id": "e-turn",
                "structured_result": {"rows": [
                    {"item": "No. 381", "value": "2902"}]}}

        resp, user = _route_call(
            factory,
            "Check rows 1 to 5 of the current quote draft.",
            {"canvas_id": CANVAS_ID}, session_id=conv)
        assert resp.success is True
        assert "$2,902" in resp.message
        assert resp.error_code is None

        history = asyncio.run(
            cr.get_chat_history(session_id=resp.session_id,
                                user_id="user_1", current_user=user))
        asst = [m for m in history.messages if m["role"] == "assistant"]
        assert asst and "$2,902" in asst[-1]["response"]["message"]


    def test_model_authored_failure_gets_aligned_envelope(self, monkeypatch):
        """Owner work order 2026-10-09: alignment is driven by the
        RECORDED outcome, not by the claim sentence.

        Live evidence (browser check, 21:53): a model-authored "I couldn't
        complete the check — the live lookup ... failed this turn" was
        PERSISTED with success=true and no outcome, because the gate only
        ever looked for the exact template claim. The execution was
        recorded success (a reply was produced) while the work behind it
        had failed.

        Here the same shape: a model-authored, already-truthful failure
        over a canvas read with nothing delivered must ship
        success=false + the recorded outcome, and the PERSISTED metadata
        and the REAL history handler must agree. The model's own truthful
        wording is preserved verbatim — alignment governs status, not
        text.
        """
        app, factory, _ = _mk_app_and_db(monkeypatch)
        model_reply = ("I couldn't complete the check — the live lookup "
                       "against our taught sources failed this turn "
                       "(timed out or errored), so I have no per-row "
                       "verdict for you.")
        _seam_failure(monkeypatch, reply={
            "content": model_reply, "model": "deepseek",
            "provider": "deepseek"})
        from core.models import Canvas, CanvasAudit
        with factory() as sc:
            sc.add(Canvas(id=CANVAS_ID, tenant_id="t1",
                          created_by="user_1", name="Quote draft",
                          canvas_type="email",
                          content={"body": "quote rows"}))
            sc.add(CanvasAudit(
                canvas_id=CANVAS_ID, tenant_id="t1", action_type="fork",
                user_id="user_1",
                details_json={"content": {"body": "quote rows"}}))
            sc.commit()

        resp, user = _route_call(
            factory,
            "Check rows 1 to 5 of the current quote draft against our "
            "taught sources.",
            {"canvas_id": CANVAS_ID})

        # the envelope now agrees with the recorded outcome
        assert resp.success is False, (
            "a recorded failure must not ship a success envelope")
        assert resp.error_code in ("turn_failed_no_result",
                                   "outcome_unconfirmed")
        assert resp.outcome in ("failed", "unconfirmed")
        # the model's truthful wording stands — alignment is not rewriting
        assert "couldn't complete the check" in resp.message

        # the PERSISTED metadata agrees (the live defect was here)
        import json as _json
        from sqlalchemy import text as _sql_text
        with factory() as sc:
            found = sc.execute(_sql_text(
                "SELECT metadata_json FROM chat_messages WHERE "
                "conversation_id=:s AND role='assistant'"),
                {"s": resp.session_id}).fetchall()
        assert found, "the assistant row must be persisted"
        meta = _json.loads(found[-1][0])
        assert meta.get("success") is False, (
            "persisted success must match the finalized envelope")
        assert meta.get("outcome") == resp.outcome

        history = asyncio.run(
            cr.get_chat_history(session_id=resp.session_id,
                                user_id="user_1", current_user=user))
        asst = [m for m in history.messages if m["role"] == "assistant"]
        assert asst and "couldn't complete the check" in (
            asst[-1]["response"]["message"])

    def test_conversational_turn_keeps_established_envelope(self, monkeypatch):
        """The mapping applies to WORK turns. A conversational turn
        attempted nothing, so it has no outcome to verify and must not be
        downgraded to unconfirmed/success=false — this is the regression
        guard for generalizing the gate."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch, reply={
            "content": "Hello — what can I help you with?",
            "model": "deepseek", "provider": "deepseek"})

        resp, user = _route_call(factory, "hello there", {})
        assert resp.success is True
        assert resp.outcome is None
        assert resp.error_code is None


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
                            lambda sid: "exec-coord-1")
        from integrations.chat_orchestrator import chat_orchestrator
        from integrations.chat_orchestrator import ChatIntent

        intent = {"primary_intent": ChatIntent.DATA_ANALYSIS,
                  "confidence": 0.9}
        resp = chat_orchestrator._generate_coordinated_response(
            "do the thing", intent, {},
            {"id": "s-coord-3", "_last_execution_id": "exec-coord-1"})
        assert resp["success"] is True
        assert resp["outcome"] == "continuation_queued"
        assert "running in the background" in resp["message"].lower()


class TestPartialAndQueuedThroughThePath:
    """Work-order cases 4-5 through the REAL route: seeded durable
    state (production lifecycle records, genuine continuation
    registry) plus seam failure — the gate classifies from records,
    the envelope aligns, history serves it back."""

    def _seed_job(self, factory, conv):
        # Same (tenant, workspace) scope the turn resolves under
        # (user_1/tenant t1, workspace default) — otherwise the
        # seeded record is invisible to the gate.
        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.task_lifecycle import (
            TaskLifecycle, begin_retrieval_turn, finish_retrieval_turn,
            record_read_outcome)
        tl = TaskLifecycle(
            GoalRunService(workspace_id="default", tenant_id="t1",
                           session_factory=factory),
            GoalService(workspace_id="default", tenant_id="t1",
                        session_factory=factory))
        run_id, op = begin_retrieval_turn(
            tl, {"id": conv}, conv, "verify pricing", "e-turn",
            items=["M-1"], requested_fields=["price"])
        finish_retrieval_turn(
            tl, run_id, op, {}, "e-turn", True,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy", "failure_stage": None,
                       "findings": [{
                           "field": "price", "column": "List",
                           "raw": "100", "parsed": {"value": 100.0},
                           "source": "W.xlsx!S!row1"}],
                       "items": {"M-1": "matched"}})
        record_read_outcome(
            tl, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "M-2", "kind": "verification",
                "question": "M-2 is carried by W.xlsx — not yet read",
                "evidence": "test seed",
                "next_action": "read W.xlsx for M-2"}])
        return tl

    def test_partial_names_remaining_work(self, monkeypatch):
        import asyncio

        from integrations import chat_routes as cr

        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch)
        self._seed_job(factory, "conv-partial-1")
        resp, user = _route_call(
            factory,
            "Check rows 1 to 5 of the current quote draft.",
            {"canvas_id": CANVAS_ID}, session_id="conv-partial-1")
        assert resp.success is True, (
            "partial delivery is not a failure")
        assert "still open" in resp.message.lower(), resp.message
        assert "read W.xlsx for M-2" in resp.message
        assert resp.error_code is None
        history = asyncio.run(
            cr.get_chat_history(session_id=resp.session_id,
                                user_id="user_1", current_user=user))
        asst = [m for m in history.messages if m["role"] == "assistant"]
        assert asst and "still open" in asst[-1]["response"]["message"].lower()

    def test_queued_names_the_continuation(self, monkeypatch):
        """A genuine in-flight continuation (the real registry, cleaned
        up after): acknowledgement naming the unfinished work, success
        stays true — background work is never reported as failed."""
        import asyncio

        import core.async_turn_continuation as atc
        from integrations import chat_routes as cr

        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "cont-path-1")
        atc._SESSION_IN_FLIGHT["conv-queued-1"] = "cont-path-1"
        try:
            resp, user = _route_call(
                factory,
                "Check rows 1 to 5 of the current quote draft.",
                {"canvas_id": CANVAS_ID}, session_id="conv-queued-1")
        finally:
            atc._SESSION_IN_FLIGHT.pop("conv-queued-1", None)
        assert resp.success is True
        assert "running in the background" in resp.message.lower()
        assert "keep going" in resp.message.lower(), (
            "finding 5: a genuine continuation continues on its own — "
            "the reply must not tell the owner to re-send")
        assert "cont-path-1" in resp.message
        history = asyncio.run(
            cr.get_chat_history(session_id=resp.session_id,
                                user_id="user_1", current_user=user))
        asst = [m for m in history.messages if m["role"] == "assistant"]
        assert asst and "cont-path-1" in asst[-1]["response"]["message"]


# ---------------------------------------------------------------------------
# Identity-bound outcome resolution — owner review 2026-10-09.
# Each regression drives the REAL route (planner kill-switch + injected
# reply-leg failure) through real persistence and the real history handler,
# over real task-lifecycle records seeded per case.
# ---------------------------------------------------------------------------
class TestIdentityBoundOutcomes:
    """The resolver may only infer from evidence bound to THIS turn."""

    def _route(self, factory, message, session_id, ctx=None):
        resp, _user = _route_call(
            factory, message,
            ctx or {"canvas_id": CANVAS_ID}, session_id=session_id)
        return resp

    def _job(self, factory, conv, *, execution_id, outcome, findings,
             questions=None):
        """Seed a real task record whose ONE operation is bound to
        ``execution_id`` (this turn's identity) with the given recorded
        outcome/findings. Returns nothing — the record is durable on the
        scratch DB, which is what the resolver reads."""
        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.task_lifecycle import (
            TaskLifecycle, begin_retrieval_turn, finish_retrieval_turn,
            record_read_outcome)
        tl = TaskLifecycle(
            GoalRunService(workspace_id="default", tenant_id="t1",
                           session_factory=factory),
            GoalService(workspace_id="default", tenant_id="t1",
                        session_factory=factory))
        run_id, op = begin_retrieval_turn(
            tl, {"id": conv}, conv, "verify pricing", execution_id,
            items=["M-1"], requested_fields=["price"])
        execution = {"invoked": True, "outcome": outcome,
                     "served_basis": "saved_copy" if findings else "none",
                     "failure_stage": None,
                     "findings": findings,
                     "items": {"M-1": "matched"} if findings else {}}
        finish_retrieval_turn(
            tl, run_id, op, {}, execution_id, bool(findings),
            execution=execution)
        if questions:
            record_read_outcome(
                tl, run_id, op, structured_result=None, freshness=None,
                execution=None, extra_questions=questions)
        return tl

    def test_earlier_findings_do_not_certify_a_failed_turn(
            self, monkeypatch):
        """Finding 1: an earlier successful operation must not certify a
        later failed turn. The successful op belongs to a DIFFERENT
        execution id."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "exec-now-1")
        # earlier turn: succeeded on exec-earlier-9
        self._job(factory, "conv-earlier-1", execution_id="exec-earlier-9",
                  outcome="read_succeeded",
                  findings=[{"field": "price", "raw": "100",
                             "parsed": {"value": 100.0},
                             "source": "W.xlsx!row1"}])
        # THIS turn: retrieval dispatched and failed, no values
        self._job(factory, "conv-now-1", execution_id="exec-now-1",
                  outcome="read_failed", findings=None)

        resp = self._route(
            factory, "Give me the current price for M-1.", "conv-now-1")
        assert resp.outcome == "failed", (
            "this turn's recorded failure must decide — an earlier "
            "operation's findings belong to another execution")
        assert resp.success is False

    def test_discovery_only_receipt_is_not_delivery(self, monkeypatch):
        """Finding 2: a dispatched read that returned prose but no
        structured values obtained evidence, not an answer. It is not a
        failure (the executor returned), and it is not delivery."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "exec-disc-1")
        self._job(factory, "conv-disc-1", execution_id="exec-disc-1",
                  outcome="read_returned_no_receipt", findings=None)

        resp = self._route(
            factory, "Read M-1 out of the price list.", "conv-disc-1")
        assert resp.outcome != "completed", (
            "a discovery receipt without requested values is not an"
            " answer")
        assert resp.success is False, (
            "no validated result and no recorded failure — the outcome "
            "is unverified, never success")

    def test_findings_with_owner_decision_is_partial(self, monkeypatch):
        """Finding 3: owner decisions are unresolved requested work — the
        turn delivered values but cannot report a final answer."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "exec-own-1")
        self._job(
            factory, "conv-own-1", execution_id="exec-own-1",
            outcome="read_succeeded",
            findings=[{"field": "price", "raw": "100",
                       "parsed": {"value": 100.0},
                       "source": "W.xlsx!row1"}],
            questions=[{
                "item": "M-1", "kind": "business_decision",
                "question": "Two rows match M-1 — which one applies?",
                "evidence": "test seed"}])

        resp = self._route(
            factory, "Quote M-1 from the price list.", "conv-own-1")
        assert resp.outcome == "partial", (
            "delivered values with an unanswered owner decision")
        assert resp.success is True

    def test_findings_with_exhausted_read_is_partial(self, monkeypatch):
        """Finding 3: an exhausted obligation is still unfinished
        requested work, never silently dropped."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "exec-exh-1")
        self._job(
            factory, "conv-exh-1", execution_id="exec-exh-1",
            outcome="read_succeeded",
            findings=[{"field": "price", "raw": "100",
                       "parsed": {"value": 100.0},
                       "source": "W.xlsx!row1"}],
            questions=[{
                "item": "M-2", "kind": "verification",
                "question": "M-2 is carried elsewhere — keep trying",
                "evidence": "test seed", "attempts": 99,
                "next_action": "re-read M-2"}])

        resp = self._route(
            factory, "Check rows 1 to 5.", "conv-exh-1")
        assert resp.outcome == "partial", (
            "an exhausted obligation is unfinished requested work")
        assert resp.success is True

    def test_successful_grounded_read_completes(self, monkeypatch):
        """Finding 2-4: this turn's own successful read with values and
        no open obligations is a validated completion."""
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "exec-ok-1")
        self._job(
            factory, "conv-ok-1", execution_id="exec-ok-1",
            outcome="read_succeeded",
            findings=[{"field": "price", "raw": "100",
                       "parsed": {"value": 100.0},
                       "source": "W.xlsx!row1"}])

        resp = self._route(
            factory, "What is the list price for M-1?", "conv-ok-1")
        assert resp.outcome == "completed", (
            "this turn's own validated result with no open obligations")
        assert resp.success is True

    @pytest.mark.xfail(reason=(
        "DESIGN GAP shared with tests/test_outcome_resolution.py: "
        "an authorized no-op has no structured values, and current "
        "delivery validation requires values — needs an explicit "
        "no-op validated signal (owner table: requested-work-"
        "completed)."), strict=True)
    def test_authorized_instruction_already_satisfied(self, monkeypatch):
        """An authorized instruction that is already satisfied is a
        genuine no-op: it must not be manufactured into a failure.

        Two things are pinned:
          (a) the finalization helper preserves a no-op-shaped delivery
              (an authorized stop with nothing left to do reports its
              own truthful completion, not a manufactured failure);
          (b) through the REAL route, a turn with NO durable work task
              resolves no outcome at all, so the established envelope
              stands.
        """
        from core.finalization import apply_recorded_outcome
        # (a) a no-op delivery is preserved: success stays as drafted
        noop = apply_recorded_outcome(
            {"success": True, "message": "Nothing to send — it already "
                                         "went out.",
             "data": {"noop": True, "noop_reason": "already_satisfied"}},
            {"state": "unconfirmed", "work_turn": True})
        assert noop["success"] is True, (
            "an authorized no-op is a genuine completion, not a failure")

        # (b) no durable task -> no outcome -> established semantics
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "exec-noop-1")
        resp = self._route(factory, "Thanks, that's all.", "conv-noop-1")
        # A conversational close has no work task, so nothing is
        # manufactured. (If it resolves an outcome it must not be a
        # failure the records do not support.)
        assert resp.outcome is None or resp.success is True, (
            "no durable work task — the outcome resolver must not "
            "invent one")

    def test_completed_calculation_survives_narration_failure(
            self, monkeypatch):
        """A delivered engine result is never negated by an outcome
        resolved from an incomplete evidence set.

        The turn's own record is what decides delivery: a
        deterministic calculation result (or an authorized instruction
        already satisfied) reaching the reply is a genuine delivery, and
        ``apply_recorded_outcome`` must preserve it even though the
        resolver could not corroborate it from operations. Pinned at the
        finalization helper, which is the boundary that owns this rule.
        """
        from core.finalization import apply_recorded_outcome

        # a resolved-but-uncorroborated outcome over a DELIVERED
        # deterministic result: the delivery wins
        payload = {
            "success": True,
            "message": "Service estimate: $1,260 (engine-computed).",
            "deterministic_delivery": True,
            "data": {"calculation": {"value": 1260}},
            "execution_id": "exec-calc-1",
        }
        out = apply_recorded_outcome(
            payload, {"state": "unconfirmed", "work_turn": True,
                      "open_work": [], "delivered": False})
        assert out["success"] is True, (
            "a delivered engine result is never negated by an outcome "
            "resolved from an incomplete evidence set")
        assert out.get("deterministic_delivery") is True

        # and the same guard on the data-carried marker
        out2 = apply_recorded_outcome(
            {"success": True, "message": "m",
             "data": {"deterministic_delivery": True}},
            {"state": "failed", "work_turn": True})
        assert out2["success"] is True

    def test_foreign_continuation_does_not_certify_this_turn(
            self, monkeypatch):
        """Finding 1: a continuation running for ANOTHER operation must
        not turn this turn into queued."""
        import core.async_turn_continuation as atc
        app, factory, _ = _mk_app_and_db(monkeypatch)
        _seam_failure(monkeypatch)
        _fixed_execution(monkeypatch, "exec-mine-1")
        atc._SESSION_IN_FLIGHT["conv-foreign-1"] = "exec-theirs-9"
        try:
            resp = self._route(
                factory, "Read M-1 from the price list.", "conv-foreign-1")
        finally:
            atc._SESSION_IN_FLIGHT.pop("conv-foreign-1", None)
        assert resp.outcome != "continuation_queued", (
            "a foreign continuation certifies nothing about this turn")
