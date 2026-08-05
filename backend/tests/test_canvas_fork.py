"""
P5 — Blueprint Security: canvas fork tests.

Forking a canvas must create an independent copy: new id, ``name`` ending in
" (copy)", no shared ``share_token``, ``status`` "active", ``created_by`` set
to the current user, content/style copied, NO audit history (exactly one
"fork" row), NO context/artifacts/recordings/usage/presence/handoffs, and
component configs run through ``strip_credentials``.

TDD: written against intended behaviour — they fail before the implementation
lands.
"""
import uuid
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import (
    AgentCanvasPresence,
    AgentHandoff,
    AgentRegistry,
    Artifact,
    ArtifactComment,
    ArtifactVersion,
    Canvas,
    CanvasAudit,
    CanvasComponent,
    CanvasContext,
    CanvasRecording,
    ComponentInstallation,
    ComponentUsage,
    Tenant,
    User,
    Workspace,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_user(db_session):
    """A valid User row for the current User schema.

    NOTE: the root conftest ``test_user`` fixture passes ``username``/
    ``is_active`` kwargs that are invalid for the current ``core.models.User``
    (which uses ``first_name``/``last_name``/``role``/``status``). This local
    fixture shadows it so the fork tests can create real FK-backed rows.
    """
    user = User(
        id=f"u-{uuid.uuid4()}",
        email=f"p5-{uuid.uuid4()}@example.com",
        hashed_password="hashed_password_here",
        first_name="Test",
        last_name="User",
        role="member",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, "test-token"


@pytest.fixture
def source_canvas(db_session, test_user):
    """A source canvas row plus all supporting rows that a fork must NOT copy."""
    user, token = test_user

    tenant = Tenant(
        id=f"t-{uuid.uuid4()}",
        name="P5 Tenant",
        subdomain=f"p5-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    db_session.flush()

    agent = AgentRegistry(
        id=f"ag-{uuid.uuid4()}",
        name="ForkTestAgent",
        category="testing",
        module_path="test.module",
        class_name="TestClass",
        status="student",
        confidence_score=0.3,
    )
    db_session.add(agent)
    db_session.flush()

    workspace = Workspace(
        id=f"ws-{uuid.uuid4()}",
        tenant_id=tenant.id,
        name="P5 Workspace",
    )
    db_session.add(workspace)
    db_session.flush()

    canvas = Canvas(
        id=f"cv-{uuid.uuid4()}",
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        created_by=str(user.id),
        name="Source Canvas",
        description="source description",
        canvas_type="document",
        content={"body": "hello", "sections": [1, 2]},
        style={"theme": "dark"},
        is_collaborative=True,
        is_public=True,
        share_token=f"src-share-token-{uuid.uuid4().hex[:12]}",
        status="active",
    )
    db_session.add(canvas)
    db_session.flush()

    # The audit trail is the source-of-truth read path; exactly one source row.
    audit = CanvasAudit(
        canvas_id=canvas.id,
        tenant_id=tenant.id,
        action_type="create",
        user_id=str(user.id),
        canvas_type="document",
        details_json={"content": canvas.content, "title": canvas.name},
    )
    db_session.add(audit)
    db_session.flush()

    component = CanvasComponent(
        id=f"comp-{uuid.uuid4()}",
        author_id=str(user.id),
        name="Chart",
        category="chart",
        component_type="html",
        code="<div/>",
    )
    db_session.add(component)
    db_session.flush()

    installation = ComponentInstallation(
        tenant_id=tenant.id,
        canvas_id=canvas.id,
        component_id=component.id,
        config={"api_key": "sk-secret", "title": "Sales", "auth": {"access_token": "tok-secret"}},
        position={"x": 1, "y": 2},
        z_index=3,
    )
    db_session.add(installation)
    db_session.flush()

    ctx = CanvasContext(
        canvas_id=canvas.id,
        tenant_id=tenant.id,
        canvas_type="document",
        user_id=str(user.id),
        current_state={"foo": "bar"},
    )
    db_session.add(ctx)
    db_session.flush()

    artifact = Artifact(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        canvas_id=canvas.id,
        name="Artifact",
        type="markdown",
        content="# hi",
    )
    db_session.add(artifact)
    db_session.flush()
    db_session.add(ArtifactVersion(artifact_id=artifact.id, version=1, content="# hi"))
    db_session.add(ArtifactComment(tenant_id=tenant.id, artifact_id=artifact.id, content="nice"))

    recording = CanvasRecording(
        recording_id=f"rec-{uuid.uuid4()}",
        canvas_id=canvas.id,
        tenant_id=tenant.id,
        user_id=str(user.id),
        agent_id=agent.id,
        status="completed",
    )
    db_session.add(recording)

    db_session.add(ComponentUsage(component_id=component.id, canvas_id=canvas.id))
    db_session.add(AgentCanvasPresence(agent_id=agent.id, canvas_id=canvas.id, tenant_id=tenant.id))
    db_session.add(AgentHandoff(
        from_agent_id=agent.id,
        to_agent_id=agent.id,
        canvas_id=canvas.id,
        tenant_id=tenant.id,
        status="completed",
    ))

    db_session.commit()

    return {
        "canvas": canvas,
        "tenant": tenant,
        "user": user,
        "token": token,
        "component": component,
        "installation": installation,
        "agent": agent,
    }


@pytest.fixture
def fork_client(db_session, source_canvas):
    """A TestClient over the canvas router with auth + DB routed to db_session.

    ``get_current_user`` is overridden to return the source owner, and
    ``core.database.get_db_session`` (used by ``read_canvas`` and the fork
    route) is patched to yield the test ``db_session`` so all fork work sees
    the rows created by ``source_canvas``.
    """
    from api.canvas_routes import router
    from core.auth import get_current_user
    import core.database as db_mod

    user = source_canvas["user"]

    app = FastAPI()
    app.include_router(router)

    def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user

    original_get_db_session = db_mod.get_db_session

    @contextmanager
    def _test_session():
        yield db_session

    db_mod.get_db_session = _test_session
    try:
        client = TestClient(app, raise_server_exceptions=False)
        yield client
    finally:
        db_mod.get_db_session = original_get_db_session
        app.dependency_overrides.clear()


# ============================================================================
# Fork behaviour
# ============================================================================

class TestCanvasFork:
    def test_fork_creates_independent_copy(self, fork_client, db_session, source_canvas):
        source = source_canvas["canvas"]
        user = source_canvas["user"]

        resp = fork_client.post(f"/api/canvas/{source.id}/fork")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        new_id = data["canvas"]["id"]
        assert new_id != source.id

        new_canvas = db_session.query(Canvas).filter(Canvas.id == new_id).first()
        assert new_canvas is not None
        # Copy semantics.
        assert new_canvas.name == source.name + " (copy)"
        assert new_canvas.name.endswith(" (copy)")
        assert new_canvas.description == source.description
        assert new_canvas.canvas_type == source.canvas_type
        assert new_canvas.content == source.content
        assert new_canvas.style == source.style
        assert new_canvas.is_collaborative == source.is_collaborative
        # Reset semantics.
        assert new_canvas.created_by == str(user.id)
        assert new_canvas.share_token is None
        assert new_canvas.status == "active"

    def test_fork_carries_no_audit_history_beyond_fork_row(self, fork_client, db_session, source_canvas):
        source = source_canvas["canvas"]
        resp = fork_client.post(f"/api/canvas/{source.id}/fork")
        assert resp.status_code == 200, resp.text
        new_id = resp.json()["canvas"]["id"]

        audits = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == new_id).all()
        assert len(audits) == 1
        assert audits[0].action_type == "fork"

    def test_fork_carries_no_context_artifacts_or_recordings(self, fork_client, db_session, source_canvas):
        source = source_canvas["canvas"]
        resp = fork_client.post(f"/api/canvas/{source.id}/fork")
        assert resp.status_code == 200, resp.text
        new_id = resp.json()["canvas"]["id"]

        assert db_session.query(CanvasContext).filter(CanvasContext.canvas_id == new_id).count() == 0
        assert db_session.query(Artifact).filter(Artifact.canvas_id == new_id).count() == 0
        assert db_session.query(CanvasRecording).filter(CanvasRecording.canvas_id == new_id).count() == 0
        assert db_session.query(ComponentUsage).filter(ComponentUsage.canvas_id == new_id).count() == 0
        assert db_session.query(AgentCanvasPresence).filter(AgentCanvasPresence.canvas_id == new_id).count() == 0
        assert db_session.query(AgentHandoff).filter(AgentHandoff.canvas_id == new_id).count() == 0

        # No artifact versions/comments can exist without an artifact.
        artifact_ids = [a.id for a in db_session.query(Artifact).filter(Artifact.canvas_id == new_id).all()]
        assert artifact_ids == []

    def test_fork_does_not_modify_source_canvas(self, fork_client, db_session, source_canvas):
        source = source_canvas["canvas"]
        resp = fork_client.post(f"/api/canvas/{source.id}/fork")
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        src = db_session.query(Canvas).filter(Canvas.id == source.id).first()
        assert src.name == "Source Canvas"
        assert src.content == {"body": "hello", "sections": [1, 2]}
        assert src.style == {"theme": "dark"}
        assert src.share_token == source.share_token
        assert src.status == "active"
        # Source audit history untouched (still exactly the one create row).
        assert db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == source.id).count() == 1

    def test_fork_sanitizes_component_config(self, fork_client, db_session, source_canvas):
        source = source_canvas["canvas"]
        resp = fork_client.post(f"/api/canvas/{source.id}/fork")
        assert resp.status_code == 200, resp.text
        new_id = resp.json()["canvas"]["id"]

        installs = db_session.query(ComponentInstallation).filter(
            ComponentInstallation.canvas_id == new_id
        ).all()
        assert len(installs) == 1
        cfg = installs[0].config
        assert cfg is not None
        assert "api_key" not in cfg
        assert "access_token" not in cfg["auth"]
        # Non-secret config preserved.
        assert cfg["title"] == "Sales"
        # Same component reference re-created for the copy.
        assert installs[0].component_id == source_canvas["component"].id

    def test_fork_requires_auth(self, db_session, source_canvas):
        """Unauthenticated fork requests are rejected (401)."""
        from api.canvas_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(f"/api/canvas/{source_canvas['canvas'].id}/fork")
        assert resp.status_code in (401, 403)
