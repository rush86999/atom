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
                      context=None, method=None, commercial_terms=None,
                      method_status="explicit"):
    payload = {
        "thread_id": "thread-1",
        "agent_id": "agent-1",
        "proposed_lesson": lesson,
        "method": method if method is not None else {
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
        "method_status": method_status,
        "applies_to": ["pricing"],
        "context": context or {},
        "authority_message_id": "m1",
        "authority_excerpt": "Use the attached workbook",
    }
    if commercial_terms is not None:
        payload["commercial_terms"] = commercial_terms
    response = env["client"].post(
        "/api/conversation-learning/candidates",
        json=payload,
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


def test_route_revise_is_revision_bound_and_clears_confirmation(route_env):
    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={
            "thread_id": "thread-1",
            "reviewer": "owner",
            "expected_revision": 1,
        },
    )
    assert confirmed.status_code == 200, confirmed.text

    missing_revision = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={
            "thread_id": "thread-1",
            "proposed_lesson": "Use the corrected rates workbook.",
        },
    )
    assert missing_revision.status_code == 422, missing_revision.text

    revised = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={
            "thread_id": "thread-1",
            "expected_revision": 1,
            "proposed_lesson": "Use the corrected rates workbook.",
        },
    )
    assert revised.status_code == 200, revised.text
    body = revised.json()
    assert body["candidate"]["candidate_id"] == candidate_id
    assert body["candidate"]["revision"] == 2
    assert body["candidate"]["status"] == "review_ready"
    assert body["candidate"]["confirmed_by"] is None
    assert body["candidate"]["confirmed_revision"] is None
    assert body["review"]["proposed_lesson"] == (
        "Use the corrected rates workbook.")
    # Unedited method and scope survive the correction byte-for-byte.
    method = body["review"]["method_and_assumptions"]["method"]
    assert method["operation"] == "multiply_sum"
    assert [item["column"] for item in method["inputs"]] == ["Qty", "Price"]
    assert method["rounding"] == {"places": 2, "stage": "final"}
    assert body["review"]["where_it_applies"]["applies_to"] == ["pricing"]

    stale = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={
            "thread_id": "thread-1",
            "expected_revision": 1,
            "proposed_lesson": "Silent stale overwrite.",
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"] == "candidate_revision_changed"

    current = route_env["client"].get(
        f"/api/conversation-learning/candidates/{candidate_id}",
        params={"thread_id": "thread-1"},
    )
    assert current.status_code == 200, current.text
    assert current.json()["candidate"]["revision"] == 2
    assert current.json()["review"]["proposed_lesson"] == (
        "Use the corrected rates workbook.")

    unconfirmed_promotion = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={
            "thread_id": "thread-1",
            "reviewer": "owner",
            "expected_revision": 2,
            "expected_digest": body["review"]["digest"],
        },
    )
    assert unconfirmed_promotion.status_code == 409, unconfirmed_promotion.text
    assert "candidate_not_confirmed" in unconfirmed_promotion.json()["detail"]

    reconfirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={
            "thread_id": "thread-1",
            "reviewer": "owner",
            "expected_revision": 2,
        },
    )
    assert reconfirmed.status_code == 200, reconfirmed.text
    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={
            "thread_id": "thread-1",
            "reviewer": "owner",
            "expected_revision": 2,
            "expected_digest": reconfirmed.json()["review"]["digest"],
        },
    )
    assert promoted.status_code == 200, promoted.text

    from core.student_learning_service import get_agent_lessons

    lessons = [entry.get("lesson") for entry in get_agent_lessons(
        route_env["db"], "agent-1")]
    assert "Use the corrected rates workbook." in lessons
    assert "Use the confirmed rates workbook." not in lessons


def test_route_correcting_promoted_lesson_retires_old_guidance(route_env):
    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1},
    )
    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1,
              "expected_digest": created["review"]["digest"]},
    )
    assert promoted.status_code == 200, promoted.text

    from core.student_learning_service import get_agent_lessons

    assert [entry.get("lesson") for entry in get_agent_lessons(
        route_env["db"], "agent-1")] == ["Use the confirmed rates workbook."]

    revised = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 1,
              "proposed_lesson": "Use the corrected rates workbook."},
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["candidate"]["status"] == "review_ready"
    # The old lesson is no longer work-time usable while the correction is
    # under review, and the same candidate remains the review handle.
    assert get_agent_lessons(route_env["db"], "agent-1") == []

    applied = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/apply",
        json={"thread_id": "thread-1",
              "rows": [{"Qty": 2, "Price": "7.50"}]},
    )
    assert applied.status_code == 409, applied.text
    assert applied.json()["detail"] == "candidate_review_ready_not_promoted"

    reconfirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 2},
    )
    assert reconfirmed.status_code == 200, reconfirmed.text
    repromoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 2,
              "expected_digest": reconfirmed.json()["review"]["digest"]},
    )
    assert repromoted.status_code == 200, repromoted.text
    assert [entry.get("lesson") for entry in get_agent_lessons(
        route_env["db"], "agent-1")] == ["Use the corrected rates workbook."]


def test_route_revise_denies_terminal_foreign_and_viewer(route_env):
    rejected = _create_candidate(route_env, lesson="Rejected rates rule.")
    rejected_id = rejected["candidate"]["candidate_id"]
    response = route_env["client"].post(
        f"/api/conversation-learning/candidates/{rejected_id}/reject",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "reason": "not applicable", "expected_revision": 1},
    )
    assert response.status_code == 200, response.text

    terminal = route_env["client"].post(
        f"/api/conversation-learning/candidates/{rejected_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 1,
              "proposed_lesson": "Revive the rejected rule."},
    )
    assert terminal.status_code == 409, terminal.text
    assert terminal.json()["detail"] == "candidate_rejected"

    foreign = _create_candidate(route_env, lesson="Scoped rates rule.")
    foreign_id = foreign["candidate"]["candidate_id"]
    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["empty_user"])
    hidden = route_env["client"].post(
        f"/api/conversation-learning/candidates/{foreign_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 1,
              "proposed_lesson": "Overwrite another workspace's lesson."},
    )
    assert hidden.status_code == 404, hidden.text

    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["viewer"])
    denied = route_env["client"].post(
        f"/api/conversation-learning/candidates/{foreign_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 1,
              "proposed_lesson": "Viewer overwrite."},
    )
    assert denied.status_code == 403, denied.text

    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["user"])


def test_route_stale_correction_after_peer_commit_is_409(route_env, monkeypatch):
    """Mounted route: read rev1, peer commits rev2, stale POST must lose."""
    from core.conversation_learning import load_candidate, revise_candidate

    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    stale = load_candidate(route_env["db"], "thread-1", candidate_id)
    assert stale is not None and stale.revision == 1

    peer = sessionmaker(
        bind=route_env["db"].get_bind(), expire_on_commit=False)()
    try:
        peer_candidate = load_candidate(peer, "thread-1", candidate_id)
        peer_revised = revise_candidate(
            peer, peer_candidate, proposed_lesson="Peer correction.",
            expected_revision=1)
        assert peer_revised.revision == 2
    finally:
        peer.close()

    import api.conversation_learning_routes as learning_routes

    # Reproduce the real stale-tab interleaving: the route's scoped load
    # already happened before the peer transaction committed.
    monkeypatch.setattr(
        learning_routes, "_load_scoped", lambda *args, **kwargs: stale)
    response = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={
            "thread_id": "thread-1",
            "expected_revision": 1,
            "expected_status": "review_ready",
            "proposed_lesson": "Stale tab overwrite.",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "candidate_revision_changed"

    check = sessionmaker(
        bind=route_env["db"].get_bind(), expire_on_commit=False)()
    try:
        fresh = load_candidate(check, "thread-1", candidate_id)
        assert fresh is not None
        assert fresh.revision == 2
        assert fresh.proposed_lesson == "Peer correction."
    finally:
        check.close()


def test_route_stale_correction_cannot_retire_newer_promotion(
    route_env, monkeypatch,
):
    from core.conversation_learning import load_candidate, promote_candidate

    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1},
    )
    assert confirmed.status_code == 200, confirmed.text
    stale = load_candidate(route_env["db"], "thread-1", candidate_id)
    assert stale is not None and stale.status == "confirmed"

    peer = sessionmaker(
        bind=route_env["db"].get_bind(), expire_on_commit=False)()
    try:
        peer_candidate = load_candidate(peer, "thread-1", candidate_id)
        promoted = promote_candidate(
            peer, peer_candidate, reviewer="owner", expected_revision=1)
        old_entry_id = promoted["lesson_id"]
    finally:
        peer.close()

    import api.conversation_learning_routes as learning_routes

    monkeypatch.setattr(
        learning_routes, "_load_scoped", lambda *args, **kwargs: stale)
    response = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={
            "thread_id": "thread-1",
            "expected_revision": 1,
            "expected_status": "confirmed",
            "proposed_lesson": "Stale correction.",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "candidate_status_changed"

    # The newer promotion is untouched: its lesson is usable and not stale.
    from core.student_learning_service import get_agent_lessons

    check = sessionmaker(
        bind=route_env["db"].get_bind(), expire_on_commit=False)()
    try:
        assert [entry["lesson"] for entry in get_agent_lessons(
            check, "agent-1")] == ["Use the confirmed rates workbook."]
        agent = check.query(AgentRegistry).filter(
            AgentRegistry.id == "agent-1").first()
        entry = next(
            item for item in agent.configuration["learning"]["log"]
            if str(item.get("id")) == str(old_entry_id))
        assert entry.get("stale") is not True
        assert entry["details"]["conversation_learning"].get(
            "revalidation_required") is not True
    finally:
        check.close()


def test_route_resolve_is_revision_bound(route_env):
    from core.conversation_learning import load_candidate, revise_candidate

    created = _create_candidate(
        route_env, context={"region": {"value": "north"}})
    candidate_id = created["candidate"]["candidate_id"]
    dep = created["review"]["unresolved_questions"][0]

    missing = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/resolve",
        json={"thread_id": "thread-1", "dependency_id": dep["dependency_id"],
              "column": "Region"},
    )
    assert missing.status_code == 422, missing.text

    peer = sessionmaker(
        bind=route_env["db"].get_bind(), expire_on_commit=False)()
    try:
        peer_candidate = load_candidate(peer, "thread-1", candidate_id)
        revise_candidate(
            peer, peer_candidate, proposed_lesson="Peer correction.",
            expected_revision=1)
    finally:
        peer.close()

    stale = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/resolve",
        json={"thread_id": "thread-1", "dependency_id": dep["dependency_id"],
              "column": "Region", "expected_revision": 1},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"] == "candidate_revision_changed"

    fresh = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/resolve",
        json={"thread_id": "thread-1", "dependency_id": dep["dependency_id"],
              "column": "Region", "expected_revision": 2},
    )
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["candidate"]["revision"] == 3


def test_route_stale_confirm_promote_reject_after_peer_commit_lose(
    route_env, monkeypatch,
):
    """All candidate mutations read the peer's latest revision under guard."""
    from core.conversation_learning import load_candidate, revise_candidate
    from core.models import ConversationEvent

    created = _create_candidate(route_env)
    candidate_id = created["candidate"]["candidate_id"]
    stale = load_candidate(route_env["db"], "thread-1", candidate_id)
    assert stale is not None and stale.revision == 1

    peer = sessionmaker(
        bind=route_env["db"].get_bind(), expire_on_commit=False)()
    try:
        peer_candidate = load_candidate(peer, "thread-1", candidate_id)
        revise_candidate(
            peer, peer_candidate, proposed_lesson="Peer correction.",
            expected_revision=1)
    finally:
        peer.close()

    import api.conversation_learning_routes as learning_routes

    monkeypatch.setattr(
        learning_routes, "_load_scoped", lambda *args, **kwargs: stale)
    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1},
    )
    assert confirmed.status_code == 409, confirmed.text
    assert confirmed.json()["detail"] == "candidate_revision_changed"

    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1, "expected_digest": stale.digest},
    )
    assert promoted.status_code == 409, promoted.text
    assert promoted.json()["detail"] == "candidate_revision_changed"

    rejected = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/reject",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "reason": "stale rejection", "expected_revision": 1},
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"] == "candidate_revision_changed"

    check = sessionmaker(
        bind=route_env["db"].get_bind(), expire_on_commit=False)()
    try:
        fresh = load_candidate(check, "thread-1", candidate_id)
        assert fresh is not None
        assert fresh.revision == 2
        assert fresh.status == "review_ready"
        assert fresh.proposed_lesson == "Peer correction."
        kinds = [
            row.kind for row in check.query(ConversationEvent).filter(
                ConversationEvent.conversation_id == "thread-1").all()
        ]
        assert kinds.count("learning_candidate_revised") == 1
        assert "learning_candidate_confirmed" not in kinds
        assert "learning_candidate_promoted" not in kinds
        assert "learning_candidate_rejected" not in kinds
    finally:
        check.close()


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


def _route_commercial_terms():
    return {
        "currency": {"value": "usd"},
        "freight": {"value": "12.50", "currency": "usd"},
        "tax_rate": {"value": "0.20"},
        "tax_amount": {"value": "2.50", "currency": "usd"},
        "tax_basis": {"value": "exempt"},
    }


def _route_expected_terms():
    return {
        "currency": {"value": "USD"},
        "freight": {"value": "12.50", "currency": "USD"},
        "tax_rate": {"value": "0.20"},
        "tax_amount": {"value": "2.50", "currency": "USD"},
        "tax_basis": {"value": "exempt"},
    }


def test_route_commercial_terms_review_promote_and_revision_patch(route_env):
    from core.student_learning_service import get_agent_lessons

    created = _create_candidate(
        route_env, lesson="Apply the reviewed freight and tax terms.",
        method={}, method_status="unresolved",
        context={"customer": "Customer-A"},
        commercial_terms=_route_commercial_terms())
    assert created["review_ready"] is True, created
    candidate = created["candidate"]
    candidate_id = candidate["candidate_id"]
    expected = _route_expected_terms()
    assert candidate["method_status"] == "not_applicable"
    assert candidate["commercial_terms"] == expected
    assert created["review"]["commercial_terms"] == expected

    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1},
    )
    assert confirmed.status_code == 200, confirmed.text
    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1,
              "expected_digest": confirmed.json()["review"]["digest"]},
    )
    assert promoted.status_code == 200, promoted.text
    details = promoted.json()["entry"]["details"]["conversation_learning"]
    assert details["commercial_terms"] == expected
    assert details["reviewed_by"] == "member@example.com"
    lesson_id = promoted.json()["lesson_id"]
    visible = get_agent_lessons(
        route_env["db"], "agent-1", include_context_bound=True)
    assert [entry["id"] for entry in visible] == [lesson_id]

    # Omitting commercial_terms preserves the reviewed mapping.
    preserved = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 1,
              "proposed_lesson": "Apply the reviewed terms exactly."},
    )
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["candidate"]["commercial_terms"] == expected
    assert get_agent_lessons(
        route_env["db"], "agent-1", include_context_bound=True) == []

    # An explicit empty mapping clears it.
    cleared = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 2,
              "commercial_terms": {}},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["candidate"]["commercial_terms"] == {}
    assert cleared.json()["review"]["commercial_terms"] == {}


def test_route_commercial_terms_require_reviewed_context(route_env):
    created = _create_candidate(
        route_env, lesson="Apply unscoped terms.",
        method={}, method_status="unresolved", context={},
        commercial_terms=_route_commercial_terms())
    assert created["review_ready"] is False, created
    assert any(
        dep["kind"] == "commercial_terms"
        for dep in created["blocking"]
    )
    candidate_id = created["candidate"]["candidate_id"]
    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 1},
    )
    assert confirmed.status_code == 409, confirmed.text
    assert confirmed.json()["detail"] == "candidate_not_review_ready"


def test_route_rejects_invalid_commercial_terms_without_writing(route_env):
    invalid = route_env["client"].post(
        "/api/conversation-learning/candidates",
        json={
            "thread_id": "thread-1",
            "agent_id": "agent-1",
            "proposed_lesson": "Apply invalid terms.",
            "method_status": "not_applicable",
            "applies_to": ["pricing"],
            "context": {"customer": "Customer-A"},
            "commercial_terms": {
                "freight": {"value": "10", "formula": "a+b"},
            },
            "authority_message_id": "m1",
            "authority_excerpt": "Use the attached workbook",
        },
    )
    assert invalid.status_code == 400, invalid.text
    assert "commercial_term_field_unsupported" in invalid.json()["detail"]

    created = _create_candidate(
        route_env, lesson="Apply valid terms.", method={},
        method_status="unresolved", context={"customer": "Customer-A"},
        commercial_terms=_route_commercial_terms())
    candidate_id = created["candidate"]["candidate_id"]
    invalid_revision = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 1,
              "commercial_terms": {"duty": {"value": "1"}}},
    )
    assert invalid_revision.status_code == 400, invalid_revision.text
    current = route_env["client"].get(
        f"/api/conversation-learning/candidates/{candidate_id}",
        params={"thread_id": "thread-1"},
    )
    assert current.status_code == 200, current.text
    assert current.json()["candidate"]["revision"] == 1
    assert current.json()["candidate"]["commercial_terms"] == (
        _route_expected_terms())


def _history_url(candidate_id: str) -> str:
    return f"/api/conversation-learning/candidates/{candidate_id}/history"


def test_route_correction_reason_and_history_survive_confirm_promote(
        route_env):
    import json

    created = _create_candidate(route_env, lesson="Use the first workbook.")
    candidate_id = created["candidate"]["candidate_id"]

    revised = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={
            "thread_id": "thread-1",
            "expected_revision": 1,
            "proposed_lesson": "Use the corrected workbook.",
            "reason": "First workbook was superseded.",
        },
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["candidate"]["revision"] == 2

    history = route_env["client"].get(
        _history_url(candidate_id), params={"thread_id": "thread-1"})
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["read_only"] is True
    assert body["signatures"]["present"] is False
    newest = body["events"][0]
    assert newest["kind"] == "learning_candidate_revised"
    # The actor is the authenticated caller, not the body's changed_by field.
    assert newest["actor"] == "member@example.com"
    assert newest["reason"] == "First workbook was superseded."
    assert newest["before"]["proposed_lesson"] == "Use the first workbook."
    assert newest["after"]["proposed_lesson"] == "Use the corrected workbook."
    assert newest["recorded_at"]
    # The raw source message body is never dumped through history.
    serialized = json.dumps(body)
    assert "Use the attached workbook to price this order." not in serialized

    bounded = route_env["client"].get(
        _history_url(candidate_id),
        params={"thread_id": "thread-1", "limit": 1})
    assert bounded.status_code == 200, bounded.text
    assert bounded.json()["coverage"]["returned"] == 1
    assert bounded.json()["coverage"]["has_more"] is True
    assert bounded.json()["coverage"]["history_complete"] is False

    # Reading history did not mutate the candidate: the normal review path
    # still confirms and promotes the same revision.
    current = route_env["client"].get(
        f"/api/conversation-learning/candidates/{candidate_id}",
        params={"thread_id": "thread-1"})
    assert current.status_code == 200, current.text
    assert current.json()["candidate"]["revision"] == 2

    confirmed = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/confirm",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 2},
    )
    assert confirmed.status_code == 200, confirmed.text
    promoted = route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/promote",
        json={"thread_id": "thread-1", "reviewer": "owner",
              "expected_revision": 2,
              "expected_digest": confirmed.json()["review"]["digest"]},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["candidate"]["status"] == "promoted"

    after = route_env["client"].get(
        _history_url(candidate_id), params={"thread_id": "thread-1"})
    assert after.status_code == 200, after.text
    after_body = after.json()
    assert [event["kind"] for event in after_body["events"]] == [
        "learning_candidate_promoted",
        "learning_candidate_confirmed",
        "learning_candidate_revised",
        "learning_candidate_created",
    ]
    # Earlier rows are untouched by later decisions (append-only).
    revised_row = next(
        event for event in after_body["events"]
        if event["kind"] == "learning_candidate_revised")
    assert revised_row["event_id"] == newest["event_id"]
    assert revised_row["reason"] == newest["reason"]
    assert revised_row["status"] == "review_ready"


def test_route_history_negatives_use_current_scope_and_authority(route_env):
    created = _create_candidate(route_env, lesson="Scoped history lesson.")
    candidate_id = created["candidate"]["candidate_id"]
    route_env["client"].post(
        f"/api/conversation-learning/candidates/{candidate_id}/revise",
        json={"thread_id": "thread-1", "expected_revision": 1,
              "proposed_lesson": "Scoped corrected lesson.",
              "reason": "scope run"},
    )

    missing_thread = route_env["client"].get(
        _history_url(candidate_id), params={"thread_id": "thread-missing"})
    assert missing_thread.status_code == 404, missing_thread.text

    missing_candidate = route_env["client"].get(
        _history_url("lc-missing"), params={"thread_id": "thread-1"})
    assert missing_candidate.status_code == 404, missing_candidate.text

    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["empty_user"])
    foreign_workspace = route_env["client"].get(
        _history_url(candidate_id), params={"thread_id": "thread-1"})
    assert foreign_workspace.status_code == 404, foreign_workspace.text

    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["viewer"])
    denied_role = route_env["client"].get(
        _history_url(candidate_id), params={"thread_id": "thread-1"})
    assert denied_role.status_code == 403, denied_role.text

    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: route_env["user"])
    route_env["user"].is_active = False
    route_env["db"].commit()
    try:
        deactivated = route_env["client"].get(
            _history_url(candidate_id), params={"thread_id": "thread-1"})
        assert deactivated.status_code == 403, deactivated.text
    finally:
        route_env["user"].is_active = True
        route_env["db"].commit()

    restored = route_env["client"].get(
        _history_url(candidate_id), params={"thread_id": "thread-1"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["coverage"]["total_events"] == 2

    # No credentials at all: the route's normal dependency refuses (401).
    route_env["client"].app.dependency_overrides.pop(get_current_user)
    try:
        unauthenticated = route_env["client"].get(
            _history_url(candidate_id), params={"thread_id": "thread-1"})
        assert unauthenticated.status_code == 401, unauthenticated.text
    finally:
        route_env["client"].app.dependency_overrides[get_current_user] = (
            lambda: route_env["user"])
