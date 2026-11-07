"""Recording-review public scope — same-tenant review vs foreign refusal.

The recording-review family persists a ``CanvasRecordingReview`` (the durable
review/decision record) rather than a HITL row. This probe drives the real
public routes and real service against a scratch DB:

* the owner can create the review for their own recording;
* the persisted review carries the recording's tenant, not the caller default;
* a same-tenant workspace admin can list/read the exact recording and decide
  it with a second review that keeps the recording's durable tenant;
* a foreign tenant/workspace admin cannot create, list, read, auto-review or
  read metrics for it (404, no row/effect).

No external effect leaf is used; the only side effects are the real review,
agent-confidence and audit rows.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.recording_review_routes import router
from core.auth import get_current_user
from core.database import get_db
from core.models import (
    AgentRegistry,
    Canvas,
    CanvasAudit,
    CanvasRecording,
    CanvasRecordingReview,
    Tenant,
    User,
    Workspace,
)
from core.models_registration import Base
from core.recording_review_service import RecordingReviewService


@pytest.fixture
def review_world(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/recording-review-scope.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    suffix = uuid.uuid4().hex[:8]
    tenant_a = f"tenant-a-{suffix}"
    tenant_b = f"tenant-b-{suffix}"
    workspace_a = f"workspace-a-{suffix}"
    workspace_b = f"workspace-b-{suffix}"
    owner_a = f"owner-a-{suffix}"
    admin_a = f"admin-a-{suffix}"
    admin_b = f"admin-b-{suffix}"
    agent_a = f"agent-a-{suffix}"
    canvas_a = f"canvas-a-{suffix}"
    recording_a = f"rec-a-{suffix}"

    with Session() as db:
        db.add(Tenant(id=tenant_a, name="A", subdomain=f"a{suffix}"))
        db.add(Tenant(id=tenant_b, name="B", subdomain=f"b{suffix}"))
        db.add(Workspace(id=workspace_a, name="A", tenant_id=tenant_a))
        db.add(Workspace(id=workspace_b, name="B", tenant_id=tenant_b))
        db.add(User(
            id=owner_a, email=f"{owner_a}@example.invalid",
            first_name="Owner", last_name="A", role="member",
            status="active", is_active=True,
            tenant_id=tenant_a, workspace_id=workspace_a,
        ))
        db.add(User(
            id=admin_a, email=f"{admin_a}@example.invalid",
            first_name="Admin", last_name="A", role="workspace_admin",
            status="active", is_active=True,
            tenant_id=tenant_a, workspace_id=workspace_a,
        ))
        db.add(User(
            id=admin_b, email=f"{admin_b}@example.invalid",
            first_name="Admin", last_name="B", role="workspace_admin",
            status="active", is_active=True,
            tenant_id=tenant_b, workspace_id=workspace_b,
        ))
        db.add(AgentRegistry(
            id=agent_a, name="Agent A", category="test",
            module_path="tests.recording", class_name="RecordingAgent",
            status="student", tenant_id=tenant_a, workspace_id=workspace_a,
        ))
        db.add(Canvas(
            id=canvas_a, tenant_id=tenant_a, workspace_id=workspace_a,
            created_by=owner_a, name="Recorded canvas",
        ))
        db.add(CanvasRecording(
            id=str(uuid.uuid4()), recording_id=recording_a,
            tenant_id=tenant_a, user_id=owner_a, agent_id=agent_a,
            canvas_id=canvas_a, status="completed",
            events=[{"event_type": "operation_complete"},
                    {"event_type": "operation_complete"}],
        ))
        db.commit()
        owner = db.query(User).filter(User.id == owner_a).first()
        admin_same = db.query(User).filter(User.id == admin_a).first()
        admin_foreign = db.query(User).filter(User.id == admin_b).first()

    def db_dependency():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = db_dependency
    state = {"user": owner}
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    with TestClient(app, raise_server_exceptions=False) as client:
        yield {
            "client": client, "state": state, "Session": Session,
            "tenant_a": tenant_a, "tenant_b": tenant_b,
            "workspace_a": workspace_a, "workspace_b": workspace_b,
            "owner": owner, "admin_same": admin_same,
            "admin_foreign": admin_foreign,
            "agent_a": agent_a, "canvas_a": canvas_a,
            "recording_a": recording_a,
        }
    engine.dispose()


def _create_review(client, recording_id):
    return client.post("/api/canvas/recording/review", json={
        "recording_id": recording_id,
        "review_status": "approved",
        "overall_rating": 5,
        "feedback": "looks good",
    })


def test_same_tenant_review_is_visible_and_foreign_scope_is_refused(review_world):
    world = review_world
    client = world["client"]
    state = world["state"]
    recording_id = world["recording_a"]

    # Owner creates the exact review. The local learning sink is a leaf;
    # review/audit/confidence rows remain real.
    with patch.object(
            RecordingReviewService, "_update_world_model", new=AsyncMock()):
        created = _create_review(client, recording_id)
    assert created.status_code == 200, created.text
    review_id = created.json()["review_id"]

    with world["Session"]() as db:
        review = db.query(CanvasRecordingReview).filter(
            CanvasRecordingReview.id == review_id).first()
        assert review is not None
        assert review.tenant_id == world["tenant_a"], (
            "review must carry the recording's tenant, not the caller default")
        audit = db.query(CanvasAudit).filter(
            CanvasAudit.tenant_id == world["tenant_a"]).first()
        assert audit is not None, "review audit must carry the real tenant"

    # A same-tenant workspace admin can see the exact review and queue, and
    # can decide it: the new decision stays in the recording's durable scope.
    state["user"] = world["admin_same"]
    listing = client.get(
        f"/api/canvas/recording/review/recording/{recording_id}")
    assert listing.status_code == 200, listing.text
    assert review_id in {row["review_id"] for row in listing.json()}
    detail = client.get(f"/api/canvas/recording/review/{review_id}")
    assert detail.status_code == 200, detail.text
    metrics = client.get(
        f"/api/canvas/recording/review/agent/{world['agent_a']}/metrics")
    assert metrics.status_code == 200, metrics.text

    with patch.object(
            RecordingReviewService, "_update_world_model", new=AsyncMock()):
        admin_decision = _create_review(client, recording_id)
    assert admin_decision.status_code == 200, admin_decision.text
    admin_review_id = admin_decision.json()["review_id"]
    assert admin_review_id != review_id

    with world["Session"]() as db:
        admin_review = db.query(CanvasRecordingReview).filter(
            CanvasRecordingReview.id == admin_review_id).first()
        assert admin_review is not None
        assert admin_review.tenant_id == world["tenant_a"]
        assert admin_review.reviewed_by == world["admin_same"].id

    listing = client.get(
        f"/api/canvas/recording/review/recording/{recording_id}")
    assert listing.status_code == 200, listing.text
    assert {review_id, admin_review_id} <= {
        row["review_id"] for row in listing.json()}

    # A foreign tenant/workspace admin cannot create, list, read, auto-review
    # or read metrics for the same recording.
    state["user"] = world["admin_foreign"]
    foreign_create = _create_review(client, recording_id)
    assert foreign_create.status_code == 404, foreign_create.text
    assert client.get(
        f"/api/canvas/recording/review/recording/{recording_id}"
    ).status_code == 404
    assert client.get(
        f"/api/canvas/recording/review/{review_id}"
    ).status_code == 404
    assert client.post(
        f"/api/canvas/recording/review/recording/{recording_id}/auto-review"
    ).status_code == 404
    assert client.get(
        f"/api/canvas/recording/review/agent/{world['agent_a']}/metrics"
    ).status_code == 404

    with world["Session"]() as db:
        assert db.query(CanvasRecordingReview).filter(
            CanvasRecordingReview.recording_id == recording_id).count() == 2
