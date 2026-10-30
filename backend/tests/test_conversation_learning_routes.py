"""Public-route coverage for reference-bound conversation learning."""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace

from api.conversation_learning_routes import router
from core.auth import get_current_user
from core.database import get_db
from core.models import (
    AgentRegistry, Base, Canvas, CanvasAudit, DatasetEntry,
)


@pytest.fixture()
def route_env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/learning-routes.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    user = SimpleNamespace(
        id="user-1", workspace_id="ws-1", tenant_id="t-1",
        email="owner@example.com", role="team_lead")
    agent = AgentRegistry(
        id="agent-1", name="Learning Agent", category="sales",
        role="sales_assistant", type="worker", capabilities=[],
        module_path="x", class_name="X", status="supervised",
        confidence_score=0.6, configuration={},
        workspace_id="ws-1", tenant_id="t-1",
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
    db.add_all([agent, canvas, audit, dataset])
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
            "agent": agent,
        }
    finally:
        db.close()
        engine.dispose()


def _create_candidate(env, *, lesson="Use the confirmed rates workbook."):
    response = env["client"].post(
        "/api/conversation-learning/candidates",
        json={
            "thread_id": "thread-1",
            "agent_id": "agent-1",
            "proposed_lesson": lesson,
            "method": {
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
            "authority_message_id": "m1",
            "authority_excerpt": "Use the attached workbook",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


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
    foreign_user = SimpleNamespace(
        id="user-2", workspace_id="ws-2", tenant_id="t-2")
    route_env["client"].app.dependency_overrides[get_current_user] = (
        lambda: foreign_user)
    response = route_env["client"].get(
        f"/api/conversation-learning/candidates/{candidate_id}",
        params={"thread_id": "thread-1"},
    )
    assert response.status_code == 404, response.text
