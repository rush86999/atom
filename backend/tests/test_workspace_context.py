"""
P8 — Workspace-Scoped Curated Context tests (Cloudflare G8).

Covers:
- workspace A skills are NOT injected for a workspace B agent (two workspaces,
  one skill each; an agent in B gets only B's skills)
- curated context appears in prompt assembly (Workspace.metadata_json
  ["curated_context"] is injected into the generic_agent system prompt)
- skill_retrieval_service filters by workspace_id (assigned skill returned,
  unassigned not; None keeps all-skills behavior)
- admin-only guard on the context routes (non-admin gets 403/401)
- workspace_id migration guard (_table_exists/_column_exists + batch_alter_table)

TDD: these tests are written against the intended behaviour and fail before the
implementation lands.
"""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Fixtures / helpers
# ============================================================================

def _make_workspace(db_session, ws_id, name, curated=None):
    from core.models import Workspace

    meta = {}
    if curated is not None:
        meta["curated_context"] = curated
    ws = Workspace(id=ws_id, name=name, metadata_json=meta)
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)
    return ws


def _make_skill(db_session, skill_id, name):
    from core.models import Skill

    skill = Skill(
        id=skill_id,
        name=name,
        description=f"{name} does things",
        type="api",
        is_approved=True,
        is_public=True,
    )
    db_session.add(skill)
    db_session.flush()
    return skill


def _make_community_execution(db_session, exec_id, skill_id, skill_name):
    from core.models import SkillExecution

    ex = SkillExecution(
        id=exec_id,
        agent_id="system",
        tenant_id="system",
        workspace_id="default",
        skill_id=skill_id,
        status="Active",
        skill_source="community",
        input_params={"skill_name": skill_name, "skill_type": "api"},
        security_scan_result={"risk_level": "LOW"},
    )
    db_session.add(ex)
    db_session.flush()
    return ex


def _assign_skill(db_session, workspace_id, skill_id):
    from core.models import workspace_skills

    db_session.execute(
        workspace_skills.insert().values(
            workspace_id=workspace_id, skill_id=skill_id
        )
    )
    db_session.commit()


def _make_agent_model(db_session, agent_id, ws_id):
    from core.models import AgentRegistry

    model = AgentRegistry(
        id=agent_id,
        name=f"Agent {agent_id}",
        type="assistant",
        module_path="agents.assistant",
        class_name="AssistantAgent",
        category="general",
        status="student",
        tenant_id="system",
        workspace_id=ws_id,
        configuration={
            "system_prompt": "You are a helpful assistant.",
            "tools": "*",
        },
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)
    return model


def _patch_db_session(monkeypatch, db_session):
    """Point core.database.get_db_session at the test session."""

    @contextmanager
    def _ctx():
        yield db_session

    monkeypatch.setattr("core.database.get_db_session", lambda: _ctx())


def _make_agent(agent_model, ws_id):
    """Construct a GenericAgent with heavy deps mocked (pattern from
    tests/test_generic_agent.py)."""
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        from core.generic_agent import GenericAgent

        agent = GenericAgent(agent_model=agent_model, workspace_id=ws_id)
    agent.mcp = MagicMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    return agent


def _capture_agent(agent, captured):
    from core.react_models import ReActStep

    async def fake_generate_structured(**kwargs):
        captured["system_instruction"] = kwargs.get("system_instruction", "")
        captured["prompt"] = kwargs.get("prompt", "")
        return ReActStep(thought="t", final_answer="ok")

    agent.llm.generate_structured = fake_generate_structured


def _make_user(db_session, uid, role):
    from core.models import User, UserStatus

    user = User(
        id=uid,
        email=f"{uid}@example.com",
        hashed_password="hashed_password",
        first_name="F",
        last_name="L",
        role=role,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_context_app(db_session, current_user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.workspace_context_routes import router
    from core.auth import get_current_user
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    async def override_get_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


# ============================================================================
# 1. skill_retrieval_service filters by workspace_id
# ============================================================================

class TestSkillRetrievalWorkspaceFilter:
    def test_assigned_skill_returned_unassigned_not(self, db_session):
        from core.skill_retrieval_service import SkillRetrievalService

        ws_a = _make_workspace(db_session, "ws-ret-a", "Workspace A")
        ws_b = _make_workspace(db_session, "ws-ret-b", "Workspace B")

        skill_a = _make_skill(db_session, "sk-ret-a", "invoice_parser")
        skill_b = _make_skill(db_session, "sk-ret-b", "email_writer")

        _make_community_execution(db_session, "exec-ret-a", skill_a.id, "invoice_parser")
        _make_community_execution(db_session, "exec-ret-b", skill_b.id, "email_writer")

        _assign_skill(db_session, ws_a.id, skill_a.id)

        svc = SkillRetrievalService()
        block = svc.retrieve_top_skills(
            db_session, "t", ws_a.id, "parse invoice line items", limit=5
        )
        assert "invoice_parser" in block
        assert "email_writer" not in block

        # Workspace B has no assignments -> empty block for a matching request.
        block_b = svc.retrieve_top_skills(
            db_session, "t", ws_b.id, "parse invoice line items", limit=5
        )
        assert block_b == ""

    def test_none_workspace_keeps_all_skills(self, db_session):
        from core.skill_retrieval_service import SkillRetrievalService

        ws_a = _make_workspace(db_session, "ws-ret-none-a", "A")
        skill_a = _make_skill(db_session, "sk-ret-none-a", "invoice_parser")
        skill_b = _make_skill(db_session, "sk-ret-none-b", "email_writer")
        _make_community_execution(db_session, "exec-ret-none-a", skill_a.id, "invoice_parser")
        _make_community_execution(db_session, "exec-ret-none-b", skill_b.id, "email_writer")
        _assign_skill(db_session, ws_a.id, skill_a.id)

        svc = SkillRetrievalService()
        block = svc.retrieve_top_skills(
            db_session, "t", None, "invoice email finance", limit=5
        )
        assert "invoice_parser" in block
        assert "email_writer" in block


# ============================================================================
# 2. Workspace skill isolation across agents (generic_agent prompt assembly)
# ============================================================================

class TestWorkspaceSkillIsolation:
    @pytest.mark.asyncio
    async def test_workspace_a_skills_not_injected_for_workspace_b_agent(
        self, db_session, monkeypatch
    ):
        ws_a = _make_workspace(db_session, "ws-isol-a", "Workspace A")
        ws_b = _make_workspace(db_session, "ws-isol-b", "Workspace B")

        skill_a = _make_skill(db_session, "sk-isol-a", "invoice_parser")
        skill_b = _make_skill(db_session, "sk-isol-b", "email_writer")

        _make_community_execution(db_session, "exec-isol-a", skill_a.id, "invoice_parser")
        _make_community_execution(db_session, "exec-isol-b", skill_b.id, "email_writer")

        _assign_skill(db_session, ws_a.id, skill_a.id)
        _assign_skill(db_session, ws_b.id, skill_b.id)

        _patch_db_session(monkeypatch, db_session)

        # Agent in workspace A -> only A's skill.
        agent_model_a = _make_agent_model(db_session, "agent-isol-a", ws_a.id)
        agent_a = _make_agent(agent_model_a, ws_a.id)
        captured_a = {}
        _capture_agent(agent_a, captured_a)
        await agent_a._react_step("parse invoice line items", {}, "tool: x", "")

        assert "invoice_parser" in captured_a["system_instruction"]
        assert "email_writer" not in captured_a["system_instruction"]

        # Agent in workspace B -> only B's skill.
        agent_model_b = _make_agent_model(db_session, "agent-isol-b", ws_b.id)
        agent_b = _make_agent(agent_model_b, ws_b.id)
        captured_b = {}
        _capture_agent(agent_b, captured_b)
        await agent_b._react_step("draft email reply", {}, "tool: x", "")

        assert "email_writer" in captured_b["system_instruction"]
        assert "invoice_parser" not in captured_b["system_instruction"]


# ============================================================================
# 3. Curated context appears in prompt assembly
# ============================================================================

class TestCuratedContextInjection:
    @pytest.mark.asyncio
    async def test_curated_context_appears_in_system_prompt(
        self, db_session, monkeypatch
    ):
        ws = _make_workspace(
            db_session,
            "ws-cc",
            "CC Workspace",
            curated=[
                "Acme Corp is our top client; invoices are net-30.",
                "All purchase orders require PO approval.",
            ],
        )
        _patch_db_session(monkeypatch, db_session)

        agent_model = _make_agent_model(db_session, "agent-cc", ws.id)
        agent = _make_agent(agent_model, ws.id)
        captured = {}
        _capture_agent(agent, captured)

        await agent._react_step("handle invoice", {}, "tool: x", "")

        assert "net-30" in captured["system_instruction"]
        assert "PO approval" in captured["system_instruction"]

    @pytest.mark.asyncio
    async def test_no_curated_context_when_none_set(self, db_session, monkeypatch):
        ws = _make_workspace(db_session, "ws-cc-none", "No CC")
        _patch_db_session(monkeypatch, db_session)

        agent_model = _make_agent_model(db_session, "agent-cc-none", ws.id)
        agent = _make_agent(agent_model, ws.id)
        captured = {}
        _capture_agent(agent, captured)

        await agent._react_step("hello there", {}, "tool: x", "")

        assert "CURATED CONTEXT" not in captured["system_instruction"]


# ============================================================================
# 4. Admin-only guard on the context routes
# ============================================================================

class TestContextRoutesAdminGuard:
    def test_non_admin_forbidden(self, db_session):
        from core.models import UserRole

        ws = _make_workspace(db_session, "ws-guard", "Guard Workspace")
        member = _make_user(db_session, "member-guard", UserRole.MEMBER.value)
        client = _make_context_app(db_session, member)

        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert resp.status_code in (401, 403)

        resp = client.put(
            f"/api/workspaces/{ws.id}/context",
            json={"curated_context": ["sneaky"]},
        )
        assert resp.status_code in (401, 403)

        resp = client.post(f"/api/workspaces/{ws.id}/skills/sk-any")
        assert resp.status_code in (401, 403)

        resp = client.delete(f"/api/workspaces/{ws.id}/skills/sk-any")
        assert resp.status_code in (401, 403)

    def test_admin_get_and_put_context(self, db_session):
        from core.models import UserRole

        ws = _make_workspace(
            db_session,
            "ws-admin",
            "Admin Workspace",
            curated=["original blob"],
        )
        skill_a = _make_skill(db_session, "sk-admin-a", "invoice_parser")
        _assign_skill(db_session, ws.id, skill_a.id)

        admin = _make_user(db_session, "admin-ctx", UserRole.SUPER_ADMIN.value)
        client = _make_context_app(db_session, admin)

        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "original blob" in body["data"]["curated_context"]
        assert "invoice_parser" in body["data"]["skill_names"]

        resp = client.put(
            f"/api/workspaces/{ws.id}/context",
            json={"curated_context": ["updated blob"]},
        )
        assert resp.status_code == 200
        db_session.refresh(ws)
        assert ws.metadata_json["curated_context"] == ["updated blob"]

    def test_admin_assign_and_unassign_skill(self, db_session):
        from core.models import UserRole

        ws = _make_workspace(db_session, "ws-admin-skills", "Skills Workspace")
        skill_a = _make_skill(db_session, "sk-admin-b", "invoice_parser")

        admin = _make_user(db_session, "admin-skills", UserRole.SUPER_ADMIN.value)
        client = _make_context_app(db_session, admin)

        resp = client.post(f"/api/workspaces/{ws.id}/skills/{skill_a.id}")
        assert resp.status_code == 200

        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert "invoice_parser" in resp.json()["data"]["skill_names"]

        resp = client.delete(f"/api/workspaces/{ws.id}/skills/{skill_a.id}")
        assert resp.status_code == 200

        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert "invoice_parser" not in resp.json()["data"]["skill_names"]

    def test_missing_workspace_returns_404(self, db_session):
        from core.models import UserRole

        admin = _make_user(db_session, "admin-404", UserRole.SUPER_ADMIN.value)
        client = _make_context_app(db_session, admin)

        resp = client.get("/api/workspaces/does-not-exist/context")
        assert resp.status_code == 404


# ============================================================================
# 5. workspace_id migration guard (inspect source)
# ============================================================================

class TestMigrationGuards:
    def test_migration_uses_guarded_helpers(self):
        mig = (
            Path(__file__).resolve().parent.parent
            / "alembic"
            / "versions"
            / "20260805_add_workspace_scoping.py"
        )
        assert mig.exists(), f"Migration file not found: {mig}"
        source = mig.read_text()

        assert "_table_exists" in source
        assert "_column_exists" in source
        assert "op.batch_alter_table" in source
        assert "20260805_integration_token_credential_metadata" in source  # down_revision
        assert "workspace_skills" in source
        assert "knowledge_documents" in source
        assert "agent_episodes" in source
