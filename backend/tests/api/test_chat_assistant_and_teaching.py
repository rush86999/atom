"""
Tests for the system Chat Assistant birth state / heal and the mentor
teach endpoint (POST /api/agents/{id}/teach).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.agent_onboarding_routes import router
from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, AgentStatus
from core.student_learning_service import StudentLearningService

_current_test_user = None


@pytest.fixture
def client(db_session: Session):
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    import core.auth as auth_mod
    from core.database import get_db

    def override_get_db():
        yield db_session

    def override_get_current_user():
        if _current_test_user is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Not authenticated")
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth_mod.get_current_user] = override_get_current_user

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def employee_user():
    user_id = str(uuid.uuid4())
    return type("User", (), {
        "id": user_id, "email": f"u-{user_id}@example.com",
        "workspace_id": "default", "tenant_id": "default", "role": "member",
    })()


def _make_student(db_session, category="Finance", status="student"):
    agent = AgentRegistry(
        id=f"learn-{uuid.uuid4().hex[:8]}",
        name="Learner", category=category, description="t",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=status, confidence_score=0.1, configuration={}, capabilities=["send_email"],
        workspace_id="default", tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


class TestChatAssistantBirthState:
    def test_new_chat_assistant_born_intern_with_learning_contract(self, db_session, monkeypatch):
        monkeypatch.setattr(AgentContextResolver, "__init__", lambda self, db: None)
        resolver = AgentContextResolver(db_session)
        resolver.db = db_session

        agent = resolver._get_or_create_system_default()

        assert agent.status == AgentStatus.INTERN.value
        assert agent.confidence_score == 0.6
        config = agent.configuration
        assert config["system_agent"] is True
        assert config["learning"]["teacher_agent_id"] == "atom_main"
        assert set(config["learning"]["pathways"]) == {"teacher", "observation"}
        # level-2 chat actions now pass governance for the fallback surface
        from core.agent_governance_service import AgentGovernanceService
        gov = AgentGovernanceService(db_session, workspace_id=agent.workspace_id, tenant_id=agent.tenant_id)
        assert gov.can_perform_action(agent_id=agent.id, action_type="stream_chat")["allowed"] is True
        # ...but state-changing actions still wait for graduation
        assert gov.can_perform_action(agent_id=agent.id, action_type="send_email")["allowed"] is False

    def test_existing_student_chat_assistant_healed_to_intern(self, db_session, monkeypatch):
        legacy = AgentRegistry(
            id="legacy-chat", name="Chat Assistant", category="system",
            module_path="system", class_name="ChatAssistant",
            status=AgentStatus.STUDENT.value, confidence_score=0.5,
            configuration={}, workspace_id="default", tenant_id="default",
        )
        db_session.add(legacy)
        db_session.commit()

        monkeypatch.setattr(AgentContextResolver, "__init__", lambda self, db: None)
        resolver = AgentContextResolver(db_session)
        resolver.db = db_session

        agent = resolver._get_or_create_system_default()

        assert agent.id == "legacy-chat"
        assert agent.status == AgentStatus.INTERN.value

    def test_graduated_chat_assistant_not_demoted(self, db_session, monkeypatch):
        senior = AgentRegistry(
            id="senior-chat", name="Chat Assistant", category="system",
            module_path="system", class_name="ChatAssistant",
            status=AgentStatus.SUPERVISED.value, confidence_score=0.9,
            configuration={}, workspace_id="default", tenant_id="default",
        )
        db_session.add(senior)
        db_session.commit()

        monkeypatch.setattr(AgentContextResolver, "__init__", lambda self, db: None)
        resolver = AgentContextResolver(db_session)
        resolver.db = db_session

        agent = resolver._get_or_create_system_default()
        assert agent.status == AgentStatus.SUPERVISED.value


class TestTeachEndpoint:
    def test_human_can_teach_any_student(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user
        student = _make_student(db_session)

        resp = client.post(f"/api/agents/{student.id}/teach", json={
            "lesson": "Always verify the vendor before creating an invoice",
            "topic": "invoices",
        })

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "ok"
        assert data["source"] == "teacher"
        db_session.refresh(student)
        entry = student.configuration["learning"]["log"][0]
        assert entry["teacher_agent_id"] == "human_supervisor"

    def test_teaching_missing_agent_404(self, client, employee_user):
        global _current_test_user
        _current_test_user = employee_user
        resp = client.post("/api/agents/nope/teach", json={"lesson": "something useful"})
        assert resp.status_code == 404

    def test_teaching_non_student_returns_skip_not_error(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user
        intern = _make_student(db_session, status="intern")

        resp = client.post(f"/api/agents/{intern.id}/teach", json={"lesson": "something useful"})

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "skipped"
        assert data["agent_status"] == "intern"

    def test_agent_teacher_must_be_qualified_mentor(self, client, employee_user, db_session):
        """Role-specific mentorship: a Finance intern cannot teach a Finance
        student — mentors must be SUPERVISED+ same-category with verified
        episodes (or atom_main for system/Meta students)."""
        global _current_test_user
        _current_test_user = employee_user
        student = _make_student(db_session, category="Finance")

        governance = MagicMock()
        governance.can_perform_action_async = AsyncMock(return_value={"allowed": True})
        # _find_mentor returns None: no qualified same-category senior
        training_svc = MagicMock()
        training_svc._find_mentor.return_value = None
        with patch("api.agent_onboarding_routes.ServiceFactory.get_governance_service", return_value=governance), \
             patch("core.student_training_service.StudentTrainingService", return_value=training_svc):
            resp = client.post(f"/api/agents/{student.id}/teach", json={
                "lesson": "lesson", "acting_agent_id": "agent-finance-intern",
            })

        assert resp.status_code == 403, resp.text
        assert "qualified mentor" in resp.json()["detail"] or "qualified mentor" in str(resp.json())

    def test_qualified_agent_mentor_can_teach(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user
        student = _make_student(db_session, category="Finance")

        governance = MagicMock()
        governance.can_perform_action_async = AsyncMock(return_value={"allowed": True})
        mentor = MagicMock()
        mentor.id = "agent-finance-senior"
        training_svc = MagicMock()
        training_svc._find_mentor.return_value = mentor
        with patch("api.agent_onboarding_routes.ServiceFactory.get_governance_service", return_value=governance), \
             patch("core.student_training_service.StudentTrainingService", return_value=training_svc):
            resp = client.post(f"/api/agents/{student.id}/teach", json={
                "lesson": "verify vendor totals before approval", "acting_agent_id": "agent-finance-senior",
            })

        assert resp.status_code == 200, resp.text
        db_session.refresh(student)
        entry = student.configuration["learning"]["log"][0]
        assert entry["teacher_agent_id"] == "agent-finance-senior"


class TestTeachUpdatesTrainingCircuit:
    def test_teach_files_lesson_into_active_training_session(
        self, client, employee_user, db_session
    ):
        """A lesson taught while the student's training session is ACTIVE
        must land in that session's guidance record (training history shows
        what was taught during the pass) — in addition to the learning
        journal + confidence boost."""
        global _current_test_user
        _current_test_user = employee_user

        from core.models import AgentProposal, ProposalType, ProposalStatus, TrainingSession
        from datetime import datetime, timezone

        student = _make_student(db_session)
        proposal = AgentProposal(
            tenant_id="default", user_id=employee_user.id, agent_id=student.id,
            agent_name=student.name, proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={}, status=ProposalStatus.APPROVED.value,
            title="p", description="d",
        )
        db_session.add(proposal)
        db_session.commit()
        session = TrainingSession(
            tenant_id="default", proposal_id=proposal.id, agent_id=student.id,
            agent_name=student.name, status="in_progress", supervisor_id="sup-1",
            supervisor_guidance={}, started_at=datetime.now(timezone.utc),
        )
        db_session.add(session)
        db_session.commit()

        resp = client.post(f"/api/agents/{student.id}/teach", json={
            "lesson": "Log the recipient before sending", "topic": "email",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ok"

        db_session.refresh(session)
        taught = session.supervisor_guidance["lessons_taught"]
        assert taught[0]["lesson"] == "Log the recipient before sending"
        assert taught[0]["topic"] == "email"
