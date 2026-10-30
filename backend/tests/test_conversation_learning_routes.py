"""Public-route coverage for reference-bound conversation learning."""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.conversation_learning_routes import router
from core.auth import get_current_user
from core.database import get_db
from core.models import (
    AgentRegistry, Base, Canvas, CanvasAudit, DatasetEntry, User,
)


@pytest.fixture()
def route_env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/learning-routes.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    user = User(
        id="user-1", email="member@example.com", hashed_password="x",
        first_name="M", last_name="One", role="member", status="active",
        workspace_id="ws-1", tenant_id="t-1", is_active=True)
    empty_user = User(
        id="user-empty", email="empty@example.com", hashed_password="x",
        first_name="E", last_name="Empty", role="member", status="active",
        workspace_id="ws-empty", tenant_id="t-1", is_active=True)
    viewer = User(
        id="user-viewer", email="viewer@example.com", hashed_password="x",
        first_name="V", last_name="Viewer", role="viewer", status="active",
        workspace_id="ws-1", tenant_id="t-1", is_active=True)
    agent = AgentRegistry(
        id="agent-1", name="Learning Agent", category="sales",
        role="sales_assistant", type="worker", capabilities=[],
        module_path="x", class_name="X", status="supervised",
        confidence_score=0.6, configuration={},
        workspace_id="ws-1", tenant_id="t-1",
    )
    foreign_agent = AgentRegistry(
        id="agent-foreign", name="Foreign Agent", category="sales",
        role="sales_assistant", type="worker", capabilities=[],
        module_path="x", class_name="X", status="supervised",
        confidence_score=0.6, configuration={},
        workspace_id="ws-2", tenant_id="t-1",
    )
    canvas = Canvas(
        id="canvas-1", tenant_id="t-1", workspace_id="ws-1",
        created_by="user-1", name="Thread", canvas_type="email",
    )
    audit = CanvasAudit(
        id="audit-1", canvas_id="canvas-1", tenant_id="t-1",
        user_id="user-1", canvas_type="email", action_type="import_eml",
        details_json={
            "thread_id": "thread-1",
            "messages": [{
                "message_id": "m1",
                "from_email": "owner@example.com",
                "to_emails": ["agent@example.com"],
                "subject": "Rates",
                "body": "Use the attached workbook to price this order.",
                "timestamp": "2026-10-30T10:00:00+00:00",
                "attachments": [{
                    "attachment_id": "a1",
                    "message_id": "m1",
                    "provider": "outlook",
                    "filename": "rates.xlsx",
                    "content_type": "application/vnd.openxmlformats-"
                                    "officedocument.spreadsheetml.sheet",
                    "size": 10,
                    "ingestion": {"status": "indexed"},
                }],
            }],
        },
    )
    dataset = DatasetEntry(
        id="ds-1", workspace_id="ws-1", tenant_id="t-1",
        created_by="user-1", source_kind="file", source="upload",
        external_id="m1:a1", file_name="rates.xlsx",
        content_hash="v1", entity_name="Rates", dataset_name="rates",
        parquet_path=str(tmp_path / "rates.parquet"),
        row_count=2, column_count=3,
        columns_json=["Price", "Quantity", "Region"],
        status="active",
    )
    db.add_all([
        user, empty_user, viewer, agent, foreign_agent,
        canvas, audit, dataset,
    ])
    db.commit()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    try:
        yield {
            "db": db,
            "client": client,
            "user": user,
            "empty_user": empty_user,
            "viewer": viewer,
            "agent": agent,
            "foreign_agent": foreign_agent,
        }
    finally:
        db.close()
        engine.dispose()


def _create_candidate(env, *, lesson="Use the confirmed rates workbook.",
                      context=None, method=None):
    response = env["client"].post(
        "/api/conversation-learning/candidates",
        json={
            "thread_id": "thread-1",
            "agent_id": "agent-1",
            "proposed_lesson": lesson,
            "method": method or {
                "intended_outcome": "Price the order",
                "operation": "multiply_sum",
                "inputs": [
                    {"concept": "quantity", "column": "Qty", "unit": "units"},
                    {"concept": "unit_price", "column": "Price",
                     "unit": "USD"},
                ],
                "output_unit": "USD",
                "transformation": "quantity * unit_price",
                "rounding": {"places": 2, "stage": "final"},
            },
            "method_status": "explicit",
            "applies_to": ["pricing"],
            "context": context or {},
            "authority_message_id": "m1",
            "authority_excerpt": "Use the attached workbook",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_workspace_sees_no_threads_or_evidence(route_env):
    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["empty_user"])
    threads = route_env["client"].get(
        "/api/conversation-learning/threads")
    assert threads.status_code == 200, threads.text
    assert threads.json()["threads"] == []

    evidence = route_env["client"].post(
        "/api/conversation-learning/evidence",
        json={"thread_id": "thread-1"},
    )
    assert evidence.status_code == 200, evidence.text
    body = evidence.json()
    assert body["messages"] == []
    assert body["resources"] == []
    assert body["coverage"]["source_access"] == "access_denied"

    direct = route_env["client"].get(
        "/api/conversation-learning/threads/thread-1/evidence")
    assert direct.status_code == 200, direct.text
    assert direct.json()["messages"] == []
    assert direct.json()["resources"] == []

    candidates = route_env["client"].get(
        "/api/conversation-learning/threads/thread-1/candidates")
    assert candidates.status_code == 200, candidates.text
    assert candidates.json()["candidates"] == []


def test_foreign_employee_cannot_be_targeted(route_env):
    response = route_env["client"].post(
        "/api/conversation-learning/candidates",
        json={
            "thread_id": "thread-1",
            "agent_id": "agent-foreign",
            "proposed_lesson": "Teach the foreign employee.",
            "method_status": "unresolved",
            "applies_to": ["pricing"],
        },
    )
    assert response.status_code == 404, response.text

    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    route_env["agent"].workspace_id = "ws-2"
    route_env["db"].commit()
    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={
            "thread_id": "thread-1",
            "reviewer": "forged-owner",
            "expected_revision": 1,
        },
    )
    assert confirmed.status_code == 404, confirmed.text


def test_viewer_cannot_create_or_promote(route_env):
    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["viewer"])
    response = route_env["client"].post(
        "/api/conversation-learning/candidates",
        json={
            "thread_id": "thread-1",
            "agent_id": "agent-1",
            "proposed_lesson": "Viewer lesson.",
            "method_status": "unresolved",
            "applies_to": ["pricing"],
        },
    )
    assert response.status_code == 403, response.text


def test_reviewer_identity_comes_from_authentication(route_env):
    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={
            "thread_id": "thread-1",
            "reviewer": "forged-owner",
            "expected_revision": 1,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["candidate"]["confirmed_by"] == (
        "member@example.com")


def test_source_change_blocks_work_time_reuse_without_manual_revalidation(
        route_env):
    from core.student_learning_service import get_agent_lessons

    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "forged-owner",
              "expected_revision": 1})
    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "forged-owner",
              "expected_revision": 1})
    assert promoted.status_code == 200, promoted.text
    lesson_id = promoted.json()["lesson_id"]
    assert any(entry.get("id") == lesson_id
               for entry in get_agent_lessons(route_env["db"], "agent-1"))

    dataset = route_env["db"].query(DatasetEntry).filter(
        DatasetEntry.id == "ds-1").first()
    dataset.content_hash = "v2"
    route_env["db"].commit()
    assert not any(entry.get("id") == lesson_id
                   for entry in get_agent_lessons(route_env["db"], "agent-1"))

    fetched = route_env["client"].get(
        f"/api/conversation-learning/candidates/{candidate_id}",
        params={"thread_id": "thread-1"})
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["candidate"]["status"] == "invalidated"
    applied = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/apply",
        json={"thread_id": "thread-1", "rows": [{"Qty": 1, "Price": "10"}]})
    assert applied.status_code == 409, applied.text

    agent_row = route_env["db"].query(AgentRegistry).filter(
        AgentRegistry.id == "agent-1").first()
    raw = next(entry for entry in agent_row.configuration["learning"]["log"]
               if entry.get("id") == lesson_id)
    assert raw["stale"] is True


def test_promotion_blocks_after_source_change(route_env):
    from core.student_learning_service import get_agent_lessons

    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "forged-owner",
              "expected_revision": 1})
    dataset = route_env["db"].query(DatasetEntry).filter(
        DatasetEntry.id == "ds-1").first()
    dataset.content_hash = "v2"
    route_env["db"].commit()
    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "forged-owner",
              "expected_revision": 1})
    assert promoted.status_code == 409, promoted.text
    assert get_agent_lessons(route_env["db"], "agent-1") == []




def _promote_context_candidate(env, *, context, lesson, method=None):
    created = _create_candidate(
        env, lesson=lesson, context=context, method=method)
    candidate_id = created["candidate"]["candidate_id"]
    confirmed = env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "forged-owner",
              "expected_revision": 1})
    assert confirmed.status_code == 200, confirmed.text
    promoted = env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "forged-owner",
              "expected_revision": 1})
    assert promoted.status_code == 200, promoted.text
    return candidate_id, promoted.json()


def test_apply_context_matching_wrong_missing(route_env):
    context = {"customer": "Customer-A", "qualification": "licensed"}
    candidate_id, promoted = _promote_context_candidate(
        route_env, context=context,
        lesson="Use the Customer-A licensed pricing method.")
    lesson_id = promoted["lesson_id"]

    matching = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/apply",
        json={"thread_id": "thread-1", "context": context,
              "rows": [{"Qty": 2, "Price": "7.50",
                        "Status": "approved", "Region": "south"}]})
    assert matching.status_code == 200, matching.text
    assert matching.json()["result"]["value"] == "15"

    wrong = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/apply",
        json={"thread_id": "thread-1",
              "context": {"customer": "Customer-B",
                          "qualification": "unlicensed"},
              "rows": [{"Qty": 1, "Price": "10"}]})
    assert wrong.status_code == 409, wrong.text
    assert wrong.json()["detail"]["reason"] == "teaching_context_mismatch"

    missing = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/apply",
        json={"thread_id": "thread-1",
              "context": {"customer": "Customer-A"},
              "rows": [{"Qty": 1, "Price": "10"}]})
    assert missing.status_code == 409, missing.text
    detail = missing.json()["detail"]
    assert detail["reason"] == "teaching_context_required"
    assert "qualification" in detail["applicability"]["missing"]

    fetched = route_env["client"].get(
        f"/api/conversation-learning/candidates/{candidate_id}",
        params={"thread_id": "thread-1"})
    assert fetched.json()["candidate"]["status"] == "promoted"
    assert fetched.json()["candidate"]["promoted_entry_id"] == lesson_id
    agent = route_env["db"].query(AgentRegistry).filter(
        AgentRegistry.id == "agent-1").first()
    assert len(agent.configuration["learning"]["log"]) == 1


def test_apply_conflicting_applicable_teaching(route_env):
    context = {"customer": "Customer-A", "qualification": "licensed"}
    first_id, _ = _promote_context_candidate(
        route_env, context=context,
        lesson="Use the Customer-A licensed sum method.",
        method={
            "intended_outcome": "Sum the order",
            "operation": "sum",
            "inputs": [{"concept": "amount", "column": "Price",
                        "unit": "USD"}],
            "output_unit": "USD",
            "transformation": "sum of Price",
            "rounding": {"places": 2, "stage": "final"},
        })
    _promote_context_candidate(
        route_env, context=context,
        lesson="Use the Customer-A licensed multiply method.",
        method={
            "intended_outcome": "Price the order",
            "operation": "multiply_sum",
            "inputs": [
                {"concept": "quantity", "column": "Qty", "unit": "units"},
                {"concept": "unit_price", "column": "Price", "unit": "USD"},
            ],
            "output_unit": "USD",
            "transformation": "quantity * unit_price",
            "rounding": {"places": 2, "stage": "final"},
        })
    applied = route_env["client"].post(
        f"/api/conversation-learning/candidates/{first_id}/apply",
        json={"thread_id": "thread-1", "context": context,
              "rows": [{"Qty": 2, "Price": "7.50"}]})
    assert applied.status_code == 409, applied.text
    assert applied.json()["detail"]["error"] == "teaching_context_conflict"


def test_context_survives_route_restart(route_env):
    context = {"customer": "Customer-A", "qualification": "licensed"}
    candidate_id, _ = _promote_context_candidate(
        route_env, context=context,
        lesson="Use the restart-safe Customer-A method.")
    bind = route_env["db"].get_bind()
    route_env["db"].close()
    factory = sessionmaker(bind=bind, expire_on_commit=False)
    db2 = factory()
    try:
        route_env["client"].app.dependency_overrides[get_db] = lambda: db2
        wrong = route_env["client"].post(
            f"/api/conversation-learning/candidates/{candidate_id}/apply",
            json={"thread_id": "thread-1",
                  "context": {"customer": "Customer-B",
                              "qualification": "unlicensed"},
                  "rows": [{"Qty": 1, "Price": "10"}]})
        assert wrong.status_code == 409, wrong.text
        matching = route_env["client"].post(
            f"/api/conversation-learning/candidates/{candidate_id}/apply",
            json={"thread_id": "thread-1", "context": context,
                  "rows": [{"Qty": 1, "Price": "10"}]})
        assert matching.status_code == 200, matching.text
        assert matching.json()["result"]["value"] == "10"
    finally:
        db2.close()


def test_route_lists_local_email_threads(route_env):
    response = route_env["client"].get(
        "/api/conversation-learning/threads")
    assert response.status_code == 200, response.text
    threads = response.json()["threads"]
    assert threads[0]["thread_id"] == "thread-1"
    assert threads[0]["subject"] == "Rates"
    assert threads[0]["message_count"] == 1


def test_route_evidence_resolves_attachment(route_env):
    response = route_env["client"].post(
        "/api/conversation-learning/evidence",
        json={"thread_id": "thread-1"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["coverage"]["messages_known"] is True
    assert body["coverage"]["max_reference_depth"] == 1
    assert body["coverage"]["depth_reached"] == 0
    edge = next(item for item in body["references"]
                if item["relation"] == "attachment")
    assert edge["resolution_status"] == "resolved"
    assert edge["target_binding"]["resource_id"] == "ds-1"
    assert edge["target_binding"]["source_version"] == "v1"


def test_route_candidate_review_confirm_promote(route_env):
    created = _create_candidate(route_env)
    assert created["review_ready"] is True, created
    candidate = created["candidate"]
    candidate_id = candidate["candidate_id"]
    assert candidate["revision"] == 1

    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={
            "thread_id": "thread-1",
            "reviewer": "owner",
            "expected_revision": 1,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["candidate"]["status"] == "confirmed"

    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={
            "thread_id": "thread-1",
            "reviewer": "owner",
            "expected_revision": 1,
            "expected_digest": confirmed.json()["review"]["digest"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    body = promoted.json()
    assert body["lesson_id"]
    assert body["candidate"]["status"] == "promoted"

    from core.student_learning_service import get_agent_lessons

    lessons = get_agent_lessons(route_env["db"], "agent-1")
    assert any(entry.get("lesson") ==
               "Use the confirmed rates workbook." for entry in lessons)

    applied = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/apply",
        json={"thread_id": "thread-1",
              "rows": [{"Qty": 2, "Price": "7.50",
                        "Status": "approved", "Region": "south"}]})
    assert applied.status_code == 200, applied.text
    assert applied.json()["result"]["value"] == "15"


def test_route_rejects_unreviewed_candidate(route_env):
    created = _create_candidate(route_env, lesson="Use the unreviewed rule.")
    candidate_id = created["candidate"]["candidate_id"]
    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={
            "thread_id": "thread-1",
            "reviewer": "owner",
            "expected_revision": 1,
        },
    )
    assert promoted.status_code == 409, promoted.text
    assert "candidate_not_confirmed" in promoted.json()["detail"]


def test_route_scope_hides_foreign_candidate(route_env):
    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["empty_user"])
    response = route_env["client"].get(
        f"/api/conversation-learning/candidates/{candidate_id}",
        params={"thread_id": "thread-1"},
    )
    assert response.status_code == 404, response.text
