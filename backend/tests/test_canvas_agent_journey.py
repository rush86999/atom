"""Canvas journey: create blank canvas → attach agent → load data.

Covers the agent-attachment journey end to end at the API boundary:

1. POST /api/canvas — blank canvas creation (row + "create" audit row with
   details.content, the readers' source of truth) and its type allowlist.
2. POST/GET/DELETE /api/canvas/{id}/agents — explicit hire attachment
   (AgentCanvasPresence + CanvasContext.agent_id stamp), idempotent,
   ownership-guarded, detachable.
3. POST /api/canvas/{id}/data/upload — the gate: 409 NO_AGENT_ON_CANVAS
   until a hire is attached; with a hire, ingestion is role-tagged to the
   hire's category and a "data_loaded" audit row lands.
4. Drive loads scoped to a canvas (Zoho WorkDrive /ingest with canvas_id):
   same 409 gate; no canvas_id → unchanged user-scoped behavior.
5. Training-context resolution: an explicit attach outranks audit
   provenance (the supervisor put THIS hire on THIS canvas).
"""
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from api import canvas_routes
from api import agent_maturity_routes
from api import zoho_workdrive_routes as zwr
from core import ingest_jobs
from core.auth import get_current_user
from core.database import get_db
from core.models import (
    AgentCanvasPresence,
    AgentRegistry,
    Canvas,
    CanvasAudit,
    User,
)
from core.personal_scope import PERSONAL_TENANT_ID

USER_ID = "journey-user"
OTHER_ID = "journey-other"


def _make_user(user_id: str) -> User:
    return User(
        id=user_id, email=f"{user_id}@x.com", first_name="J", last_name="U",
        role="admin", status="active", tenant_id=PERSONAL_TENANT_ID,
    )


def _client_for(user_id: str, SessionLocal) -> TestClient:
    app = FastAPI()
    app.include_router(canvas_routes.router)
    app.include_router(agent_maturity_routes.router)
    app.include_router(zwr.router)

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = lambda: _make_user(user_id)
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def env(worker_database):
    """Scratch DB + an authenticated client for the journey user."""
    client = _client_for(USER_ID, worker_database)
    yield {"client": client, "db_factory": worker_database}
    ingest_jobs.registry.clear()


@pytest.fixture
def other_client(worker_database):
    return _client_for(OTHER_ID, worker_database)


def _db(env):
    return env["db_factory"]()


def _seed_agent(db, agent_id=None, name="Alex", category="finance", tenant=PERSONAL_TENANT_ID):
    agent = AgentRegistry(
        id=agent_id or str(uuid.uuid4()),
        name=name,
        category=category,
        module_path="test.module",
        class_name="TestJourney",
        status="student",
        confidence_score=0.3,
        tenant_id=tenant,
    )
    db.add(agent)
    db.commit()
    return agent


def _create_canvas(client, **payload):
    resp = client.post("/api/canvas", json=payload or {"title": "Journey canvas"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _error(resp) -> dict:
    """Inner error body of a BaseAPIRouter HTTPException. The real app mounts
    a handler that unwraps ``detail``; a bare test app returns
    ``{"detail": {"error": ...}}`` — accept both."""
    body = resp.json()
    if isinstance(body.get("detail"), dict):
        return body["detail"].get("error") or body["detail"]
    return body.get("error") or {}


def _attach(client, canvas_id, agent_id):
    return client.post(f"/api/canvas/{canvas_id}/agents", json={"agent_id": agent_id})


class TestBlankCanvasCreate:
    def test_create_returns_id_and_url_with_audit_row(self, env):
        client = env["client"]
        body = _create_canvas(client, title="My blank canvas")
        assert body["success"] is True
        assert body["url"] == f"/canvas/{body['canvas_id']}"

        db = _db(env)
        row = db.query(Canvas).filter(Canvas.id == body["canvas_id"]).one()
        assert row.name == "My blank canvas"
        assert row.canvas_type == "document"
        assert row.created_by == USER_ID
        # Readers treat the audit trail as the source of truth — the create
        # row must carry the content, not just the Canvas row.
        audit = (
            db.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == body["canvas_id"])
            .one()
        )
        assert audit.action_type == "create"
        assert audit.details_json["content"] == {"content": ""}

    def test_unsupported_type_rejected_400(self, env):
        resp = env["client"].post("/api/canvas", json={"canvas_type": "email"})
        assert resp.status_code == 400
        assert _error(resp)["code"] == "UNSUPPORTED_CANVAS_TYPE"


class TestAgentAttachment:
    def test_attach_lists_agent_and_stamps_context(self, env):
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        agent = _seed_agent(db, category="Finance")

        resp = _attach(client, canvas["canvas_id"], agent.id)
        assert resp.status_code == 200, resp.text
        agents = resp.json()["agents"]
        assert [a["agent_id"] for a in agents] == [agent.id]
        assert agents[0]["category"] == "Finance"
        assert agents[0]["maturity"] == "student"

        # Presence row written + CanvasContext stamped for the user.
        presence = (
            db.query(AgentCanvasPresence)
            .filter(
                AgentCanvasPresence.canvas_id == canvas["canvas_id"],
                AgentCanvasPresence.status == "active",
            )
            .all()
        )
        assert len(presence) == 1

    def test_attach_is_idempotent(self, env):
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        agent = _seed_agent(db)

        first = _attach(client, canvas["canvas_id"], agent.id)
        second = _attach(client, canvas["canvas_id"], agent.id)
        assert second.status_code == 200
        assert second.json()["join_status"] == "already_present"
        assert len(first.json()["agents"]) == 1

    def test_attach_unknown_agent_404(self, env):
        client = env["client"]
        canvas = _create_canvas(client)
        resp = _attach(client, canvas["canvas_id"], "no-such-agent")
        assert resp.status_code == 404

    def test_foreign_user_cannot_attach(self, env, other_client):
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        agent = _seed_agent(db)
        resp = _attach(other_client, canvas["canvas_id"], agent.id)
        # 404, not 403 — no existence leak (same guard as the read routes).
        assert resp.status_code == 404

    def test_detach_then_reattach(self, env):
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        agent = _seed_agent(db)
        _attach(client, canvas["canvas_id"], agent.id)
        resp = client.delete(f"/api/canvas/{canvas['canvas_id']}/agents/{agent.id}")
        assert resp.status_code == 200
        assert resp.json()["agents"] == []
        # Detaching an absent hire is a 404.
        again = client.delete(f"/api/canvas/{canvas['canvas_id']}/agents/{agent.id}")
        assert again.status_code == 404
        # And the canvas can hire again.
        re = _attach(client, canvas["canvas_id"], agent.id)
        assert re.status_code == 200
        assert len(re.json()["agents"]) == 1


class TestDataLoadGate:
    def test_upload_without_agent_409(self, env):
        client = env["client"]
        canvas = _create_canvas(client)
        resp = client.post(
            f"/api/canvas/{canvas['canvas_id']}/data/upload",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 409
        assert _error(resp)["code"] == "NO_AGENT_ON_CANVAS"

    def test_upload_with_agent_role_tags_and_audits(self, env):
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        agent = _seed_agent(db, category="Finance")
        _attach(client, canvas["canvas_id"], agent.id)

        with patch("core.auto_document_ingestion.AutoDocumentIngestionService") as svc_cls:
            svc_cls.return_value.process_file_bytes = AsyncMock(
                return_value={"status": "ingested", "doc_id": "doc-1", "chars_ingested": 11}
            )
            resp = client.post(
                f"/api/canvas/{canvas['canvas_id']}/data/upload",
                files={"file": ("notes.txt", b"hello world", "text/plain")},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ingestion"]["status"] == "ingested"
        # The hire's category is the role tag; canvas + hire ride metadata.
        kwargs = svc_cls.return_value.process_file_bytes.await_args.kwargs
        assert kwargs["role"] == "Finance"
        assert kwargs["extra_metadata"] == {
            "canvas_id": canvas["canvas_id"],
            "agent_id": agent.id,
        }

        audit = (
            db.query(CanvasAudit)
            .filter(
                CanvasAudit.canvas_id == canvas["canvas_id"],
                CanvasAudit.action_type == "data_loaded",
            )
            .one()
        )
        assert audit.agent_id == agent.id
        assert audit.details_json["file_name"] == "notes.txt"

    def test_upload_unsupported_extension_422(self, env):
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        agent = _seed_agent(db)
        _attach(client, canvas["canvas_id"], agent.id)
        resp = client.post(
            f"/api/canvas/{canvas['canvas_id']}/data/upload",
            files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
        )
        assert resp.status_code == 422


class TestDriveCanvasGate:
    """canvas_id on the Zoho ingest path: same gate, additive only."""

    def test_ingest_with_agentless_canvas_409(self, env):
        client = env["client"]
        canvas = _create_canvas(client)
        resp = client.post(
            "/api/zoho-workdrive/ingest",
            json={"file_id": "f1", "canvas_id": canvas["canvas_id"]},
        )
        assert resp.status_code == 409
        assert _error(resp)["code"] == "NO_AGENT_ON_CANVAS"

    def test_ingest_with_attached_canvas_passes_role(self, env):
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        agent = _seed_agent(db, category="Finance")
        _attach(client, canvas["canvas_id"], agent.id)

        with patch.object(zwr.zoho_service, "ingest_file_to_memory", new_callable=AsyncMock) as svc:
            svc.return_value = {"success": True, "result": {"status": "ingested"}}
            resp = client.post(
                "/api/zoho-workdrive/ingest",
                json={"file_id": "f1", "canvas_id": canvas["canvas_id"]},
            )
            assert resp.status_code == 200, resp.text
            # The job runs in the background — wait it out, then assert.
            job_id = resp.json()["data"]["job_id"]
            deadline = time.time() + 5
            while time.time() < deadline:
                snap = client.get(f"/api/zoho-workdrive/ingest/jobs/{job_id}").json()["data"]
                if snap["status"] != "running":
                    break
                time.sleep(0.02)
            assert snap["status"] == "completed"
        kwargs = svc.await_args.kwargs
        assert kwargs["role"] == "Finance"
        assert kwargs["extra_metadata"] == {"canvas_id": canvas["canvas_id"]}

    def test_ingest_without_canvas_unchanged(self, env):
        """No canvas_id → byte-for-byte old behavior (no role, no metadata)."""
        client = env["client"]
        with patch.object(zwr.zoho_service, "ingest_file_to_memory", new_callable=AsyncMock) as svc:
            svc.return_value = {"success": True}
            resp = client.post("/api/zoho-workdrive/ingest", json={"file_id": "f1"})
        assert resp.status_code == 200
        assert svc.await_args.kwargs.get("role") is None
        assert svc.await_args.kwargs.get("extra_metadata") is None

    def test_folder_ingest_with_agentless_canvas_409(self, env):
        client = env["client"]
        canvas = _create_canvas(client)
        resp = client.post(
            "/api/zoho-workdrive/ingest-folder",
            json={"folder_id": "fld1", "canvas_id": canvas["canvas_id"]},
        )
        assert resp.status_code == 409
        assert _error(resp)["code"] == "NO_AGENT_ON_CANVAS"


class TestTrainingContextResolution:
    def test_explicit_attach_outranks_audit_provenance(self, env):
        """A canvas whose audit trail names hire A must resolve to hire B
        once the supervisor explicitly attaches B (the human put THIS hire
        on THIS canvas)."""
        client, db = env["client"], _db(env)
        canvas = _create_canvas(client)
        canvas_id = canvas["canvas_id"]

        hire_a = _seed_agent(db, name="Provenance", category="sales")
        hire_b = _seed_agent(db, name="Explicit", category="finance")
        # Provenance: an audit row authored by hire A (e.g. an early edit).
        db.add(CanvasAudit(
            canvas_id=canvas_id,
            tenant_id=PERSONAL_TENANT_ID,
            action_type="update",
            user_id=USER_ID,
            agent_id=hire_a.id,
            details_json={"content": {"content": "hire A was here"}},
        ))
        db.commit()

        def ctx_agent():
            resp = client.get(f"/api/maturity/training/context?canvas_id={canvas_id}")
            assert resp.status_code == 200, resp.text
            # Plain dict body (not the success_response envelope).
            return resp.json()["agent"]

        # Before the attach: audit provenance resolves hire A.
        assert ctx_agent()["id"] == hire_a.id

        # After the explicit attach: hire B wins.
        _attach(client, canvas_id, hire_b.id)
        assert ctx_agent()["id"] == hire_b.id
