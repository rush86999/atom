"""Public chat-route settlement for a calculation plus an email obligation."""
from __future__ import annotations

import os
from contextlib import contextmanager
from types import SimpleNamespace

os.environ.setdefault("TESTING", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import get_current_user
from core.database import get_db
from core.finalization import apply_recorded_outcome
from core.models import (
    AgentProposal, Base, Canvas, HITLAction, HITLActionStatus,
)
from integrations import chat_routes as cr


@pytest.fixture()
def route_env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/chat-teaching.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        db = factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    import core.database as database_module

    monkeypatch.setattr(database_module, "get_db_session", get_db_session)

    user = SimpleNamespace(
        id="user-1", workspace_id="ws-1", tenant_id="t-1",
        role="member", is_active=True)
    app = FastAPI()
    app.include_router(cr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: factory()
    monkeypatch.setattr(
        cr, "_finalize_chat_response",
        lambda db, response: apply_recorded_outcome(
            response, response.get("_recorded_outcome")))
    monkeypatch.setattr(
        cr, "_persist_finalized_outcome",
        lambda db, response, session_id: response)
    yield {
        "client": TestClient(app),
        "factory": factory,
        "user": user,
    }
    engine.dispose()


def test_public_chat_compound_request_keeps_email_obligation(route_env):
    from core.conversation_learning import MethodInput, MethodSpec
    from integrations.chat_orchestrator import ChatOrchestrator

    method = MethodSpec(
        intended_outcome="Price the order",
        operation="multiply_sum",
        inputs=[
            MethodInput(concept="quantity", column="Qty", unit="units"),
            MethodInput(concept="unit_price", column="Price", unit="USD"),
        ],
        output_unit="USD",
        transformation="quantity * unit_price",
        rounding={"places": 2, "stage": "final"},
    )
    entry = {
        "id": "lesson-1", "revision": 1,
        "details": {"conversation_learning": {
            "method": method.model_dump(mode="json")}},
    }
    resolution = {
        "needs_context": False,
        "required_context": [],
        "conflicts": [],
        "excluded_lessons": [],
        "consumed_lesson_refs": [{"id": "lesson-1", "revision": 1}],
        "method_status": "applicable",
        "method_lessons": [{
            "entry": entry, "method": method, "specificity": 2,
        }],
    }
    orch = ChatOrchestrator()
    orch.session_manager = None

    async def fake_process(*, user_id, message, session_id=None,
                           context=None, **_kwargs):
        reply = orch._apply_teaching_resolution(
            resolution=resolution,
            message=message,
            session={"id": session_id or "s1"},
            session_id=session_id or "s1",
            user_id=user_id,
            agent_id="agent-1",
            workspace_id="ws-1",
            task_context={"qualification": "licensed"},
            memory_context="TRAINING LESSONS",
        )
        assert reply is not None
        return {
            "success": True,
            "message": reply["content"],
            "session_id": session_id or "s1",
            "intent": "teaching_context",
            "confidence": 0.95,
            "data": {
                "teaching_execution": reply["teaching_execution"],
            },
            "model": reply.get("model"),
            "provider": reply.get("provider"),
            "memory_context": reply.get("memory_context"),
            "outcome": reply["_recorded_outcome"]["state"],
            "_recorded_outcome": reply["_recorded_outcome"],
            "deterministic_delivery": True,
            "requires_confirmation": False,
            "next_steps": [],
            "suggested_actions": [],
            "timestamp": "2026-10-31T00:00:00+00:00",
        }

    async def forbidden_send(*_args, **_kwargs):
        raise AssertionError("an outbound send must not run")

    cr.chat_orchestrator.process_chat_message = fake_process
    cr.chat_orchestrator._execute_send_email = forbidden_send

    response = route_env["client"].post(
        "/api/chat/message",
        json={
            "message": (
                "Qty 2 and Price 7.50; then email the quote to "
                "alice@example.com"),
            "user_id": "user-1",
            "session_id": "s1",
            "agent_id": "agent-1",
            "context": {"task_context": {"qualification": "licensed"}},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "partial", body
    execution = (body.get("metadata") or {}).get("teaching_execution") or {}
    receipt = execution.get("calculation_receipt") or {}
    assert receipt.get("value") == "15.00", receipt
    assert receipt.get("lesson_ref") == {
        "id": "lesson-1", "revision": 1}, receipt
    assert execution.get("covered_obligations") == ["calculation"], execution
    open_texts = [
        item.get("text") for item in execution.get("open_obligations") or []]
    assert any("email" in str(text).lower() for text in open_texts), execution
    approval_id = execution.get("approval_id")
    assert approval_id, execution
    proposal_id = execution.get("proposal_id")
    assert proposal_id, execution
    assert execution.get("draft_canvas_id"), execution

    db = route_env["factory"]()
    try:
        row = db.query(HITLAction).filter(
            HITLAction.id == approval_id).first()
        assert row is not None
        assert row.status == HITLActionStatus.PENDING.value
        assert row.action_type == "chat_request_obligation"
        assert row.params["calculation_receipt"]["value"] == "15.00"
        assert row.params["proposal_id"] == proposal_id
        assert "email" in row.params["obligations"][0]["text"].lower()
        proposal_row = db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id).first()
        assert proposal_row is not None
        assert proposal_row.status == "pending_approval"
        assert proposal_row.proposal_data["to"] == "alice@example.com"
    finally:
        db.close()


def test_compound_email_draft_clarification_and_approval_resume(
        route_env, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    from core.conversation_learning import MethodInput, MethodSpec
    from core.hitl_resume import resume_after_hitl_decision
    from integrations.chat_orchestrator import ChatOrchestrator

    method = MethodSpec(
        intended_outcome="Price the order",
        operation="multiply_sum",
        inputs=[
            MethodInput(concept="quantity", column="Qty", unit="units"),
            MethodInput(concept="unit_price", column="Price", unit="USD"),
        ],
        output_unit="USD",
        transformation="quantity * unit_price",
        rounding={"places": 2, "stage": "final"},
    )
    entry = {
        "id": "lesson-1", "revision": 1,
        "details": {"conversation_learning": {
            "method": method.model_dump(mode="json")}},
    }
    resolution = {
        "needs_context": False, "required_context": [],
        "conflicts": [], "excluded_lessons": [],
        "consumed_lesson_refs": [{"id": "lesson-1", "revision": 1}],
        "method_status": "applicable",
        "method_lessons": [{"entry": entry, "method": method,
                            "specificity": 2}],
    }
    import uuid

    orch = ChatOrchestrator()
    orch.session_manager = None
    session_id = f"email-{uuid.uuid4().hex[:8]}"
    session = {"id": session_id, "history": []}
    first = orch._apply_teaching_resolution(
        resolution=resolution,
        message="Qty 2 and Price 7.50; then email the quote",
        session=session, session_id=session_id, user_id="user-1",
        agent_id="agent-1", workspace_id="ws-1",
        task_context={"qualification": "licensed"},
        memory_context="TRAINING LESSONS",
    )
    assert first is not None
    assert first["_recorded_outcome"]["state"] == "partial"
    assert first["teaching_execution"]["calculation_receipt"]["value"] == "15.00"
    assert first["teaching_execution"]["email_draft"]["recipient_required"] is True
    assert "Who should I email it to" in first["content"]
    draft_id = first["teaching_execution"]["email_draft"]["draft_canvas_id"]
    assert draft_id
    assert session["_pending_teaching_clarification"]["kind"] == "email_draft"

    message, context, state = orch._resume_teaching_clarification(
        session=session, session_id=session_id, user_id="user-1",
        message="alice@example.com",
        context={"task_context": {"qualification": "licensed"}},
        workspace_id="ws-1", agent_id="agent-1",
    )
    assert state["confirmed"] is True
    proposal = context["_teaching_resume"]["email_proposal"]
    assert proposal["recipients"] == ["alice@example.com"]
    assert proposal["proposal_id"]
    assert proposal["approval_id"]

    second = orch._apply_teaching_resolution(
        resolution=resolution,
        message="Qty 2 and Price 7.50; then email the quote",
        session=session, session_id=session_id, user_id="user-1",
        agent_id="agent-1", workspace_id="ws-1",
        task_context=context["task_context"],
        memory_context="TRAINING LESSONS",
    )
    assert second["_recorded_outcome"]["state"] == "partial"
    execution = second["teaching_execution"]
    assert execution["proposal_id"] == proposal["proposal_id"]
    assert execution["approval_id"] == proposal["approval_id"]
    assert "requested approval" in second["content"]
    assert "No email was sent" in second["content"]

    db = route_env["factory"]()
    try:
        canvas = db.query(Canvas).filter(Canvas.id == draft_id).first()
        assert canvas is not None
        assert canvas.content["to"] == "alice@example.com"
        assert "multiply_sum" in canvas.content["body"]
        proposal_row = db.query(AgentProposal).filter(
            AgentProposal.id == proposal["proposal_id"]).first()
        assert proposal_row.status == "pending_approval"
        assert proposal_row.proposal_data["to"] == "alice@example.com"
        assert proposal_row.proposal_data["action_type"] == "send_email"
        hitl = db.query(HITLAction).filter(
            HITLAction.id == proposal["approval_id"]).first()
        assert hitl.status == HITLActionStatus.PENDING.value
        assert hitl.action_type == "chat_request_obligation"
        assert hitl.params["proposal_id"] == proposal["proposal_id"]
        hitl_id = hitl.id
    finally:
        db.close()

    from core.canvas_email_service import EmailCanvasService

    send_mock = AsyncMock(return_value={
        "success": True, "status": "draft_only"})
    monkeypatch.setattr(EmailCanvasService, "send_email", send_mock)
    result = asyncio.run(resume_after_hitl_decision(
        hitl_id, approved=True, reviewer_id="user-1"))
    assert result["handled"] is True
    assert result["resumed"] is True
    assert result["kind"] == "chat_obligation"
    send_mock.assert_awaited_once()
    kwargs = send_mock.await_args.kwargs
    assert kwargs["to_emails"] == ["alice@example.com"]
    assert "multiply_sum" in kwargs["body"]

    db = route_env["factory"]()
    try:
        proposal_row = db.query(AgentProposal).filter(
            AgentProposal.id == proposal["proposal_id"]).first()
        assert proposal_row.status == "executed"
        assert proposal_row.execution_success is True
    finally:
        db.close()

    # Duplicate approval must replay, not send twice.
    replay = asyncio.run(resume_after_hitl_decision(
        hitl_id, approved=True, reviewer_id="user-1"))
    assert replay["handled"] is True
    assert replay["replayed"] is True
    assert replay["status"] == "already_executed"
    assert send_mock.await_count == 1


def _prepare_email_proposal(route_env):
    import asyncio

    from core.conversation_learning import MethodInput, MethodSpec
    from integrations.chat_orchestrator import ChatOrchestrator

    method = MethodSpec(
        intended_outcome="Price the order",
        operation="multiply_sum",
        inputs=[
            MethodInput(concept="quantity", column="Qty", unit="units"),
            MethodInput(concept="unit_price", column="Price", unit="USD"),
        ],
        output_unit="USD",
        transformation="quantity * unit_price",
        rounding={"places": 2, "stage": "final"},
    )
    entry = {
        "id": "lesson-1", "revision": 1,
        "details": {"conversation_learning": {
            "method": method.model_dump(mode="json")}},
    }
    resolution = {
        "needs_context": False, "required_context": [],
        "conflicts": [], "excluded_lessons": [],
        "consumed_lesson_refs": [{"id": "lesson-1", "revision": 1}],
        "method_status": "applicable",
        "method_lessons": [{"entry": entry, "method": method,
                            "specificity": 2}],
    }
    import uuid

    orch = ChatOrchestrator()
    orch.session_manager = None
    session_id = f"email-{uuid.uuid4().hex[:8]}"
    session = {"id": session_id, "history": []}
    orch._apply_teaching_resolution(
        resolution=resolution,
        message="Qty 2 and Price 7.50; then email the quote",
        session=session, session_id=session_id, user_id="user-1",
        agent_id="agent-1", workspace_id="ws-1",
        task_context={"qualification": "licensed"},
        memory_context="TRAINING LESSONS",
    )
    message, context, state = orch._resume_teaching_clarification(
        session=session, session_id=session_id, user_id="user-1",
        message="alice@example.com",
        context={"task_context": {"qualification": "licensed"}},
        workspace_id="ws-1", agent_id="agent-1",
    )
    assert state["confirmed"] is True
    proposal = context["_teaching_resume"]["email_proposal"]
    assert proposal.get("approval_id"), proposal
    return {
        "proposal_id": proposal["proposal_id"],
        "hitl_id": proposal["approval_id"],
        "draft_canvas_id": proposal["draft_canvas_id"],
        "resolution": resolution,
        "session": session,
        "context": context,
        "message": message,
    }


@pytest.mark.parametrize("field,value", [
    ("to", "different-recipient@example.invalid"),
    ("body", "A different body that was never reviewed."),
    ("attachment_hashes", {"a1": "deadbeef"}),
])
def test_chat_obligation_payload_drift_refused(
        route_env, monkeypatch, field, value):
    import asyncio
    from unittest.mock import AsyncMock

    from core.canvas_email_service import EmailCanvasService
    from core.hitl_resume import resume_after_hitl_decision
    from core.models import AgentProposal

    prepared = _prepare_email_proposal(route_env)
    db = route_env["factory"]()
    try:
        proposal = db.query(AgentProposal).filter(
            AgentProposal.id == prepared["proposal_id"]).first()
        data = dict(proposal.proposal_data or {})
        data[field] = value
        proposal.proposal_data = data
        db.commit()
    finally:
        db.close()

    send = AsyncMock(return_value={"success": True, "status": "draft_only"})
    monkeypatch.setattr(EmailCanvasService, "send_email", send)
    result = asyncio.run(resume_after_hitl_decision(
        prepared["hitl_id"], approved=True, reviewer_id="user-1"))
    assert result["handled"] is True
    assert result["resumed"] is False
    assert result["status"] == "payload_changed"
    assert result["fresh_review_required"] is True
    assert send.await_count == 0

    db = route_env["factory"]()
    try:
        proposal = db.query(AgentProposal).filter(
            AgentProposal.id == prepared["proposal_id"]).first()
        assert proposal.status == "pending_approval"
    finally:
        db.close()


def test_chat_obligation_rejection_has_no_transport(route_env, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    from core.canvas_email_service import EmailCanvasService
    from core.hitl_resume import resume_after_hitl_decision
    from core.models import AgentProposal

    prepared = _prepare_email_proposal(route_env)
    send = AsyncMock(return_value={"success": True, "status": "draft_only"})
    monkeypatch.setattr(EmailCanvasService, "send_email", send)
    result = asyncio.run(resume_after_hitl_decision(
        prepared["hitl_id"], approved=False, reviewer_id="user-1",
        guidance="not this one"))
    assert result["handled"] is True
    assert result["resumed"] is False
    assert result["status"] == "rejected"
    assert send.await_count == 0
    db = route_env["factory"]()
    try:
        proposal = db.query(AgentProposal).filter(
            AgentProposal.id == prepared["proposal_id"]).first()
        assert proposal.status == "rejected"
    finally:
        db.close()
