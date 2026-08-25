"""
Tests for employee-friendly agent onboarding (api/agent_onboarding_routes.py)
and the guided automation services (core/guided_automation_service.py).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.agent_onboarding_routes import router
from core.guided_automation_service import (
    AutomationSuggestionService,
    GuidedAgentFactory,
)
from core.models import AgentRegistry, AgentExecution


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
def employee_user(db_session: Session):
    import uuid
    user_id = str(uuid.uuid4())
    user = type(
        "User",
        (),
        {
            "id": user_id,
            "email": f"emp-{user_id}@example.com",
            "workspace_id": "default",
            "tenant_id": "default",
            "role": "member",
        },
    )()
    return user


def _llm_mock(content: str) -> MagicMock:
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={"content": content})
    return llm


def _factory_with_llm(llm) -> GuidedAgentFactory:
    return GuidedAgentFactory(llm_service=llm)


class TestGuidedAgentCreation:
    def test_employee_creates_agent_from_goal(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user

        llm = _llm_mock(
            '''{"name": "Invoice Watchdog", "description": "Flags overdue invoices", '''
            '''"category": "Finance", "capabilities": ["monitor_invoices", "send_alert"], '''
            '''"template": "finance_analyst", "configuration": {"system_prompt": "Watch invoices"}}'''
        )
        with patch("api.agent_onboarding_routes.get_guided_agent_factory",
                   return_value=_factory_with_llm(llm)):
            resp = client.post("/api/agents/guided", json={"goal": "watch our invoices and flag overdue ones"})

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == data["agent_id"]).first()
        assert agent is not None
        assert agent.name == "Invoice Watchdog"
        assert agent.status == "student"  # always spoon-fed to start
        assert agent.user_id == employee_user.id
        assert agent.workspace_id == "default"

    def test_falls_back_to_template_without_llm(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user

        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("no llm"))
        with patch("api.agent_onboarding_routes.get_guided_agent_factory",
                   return_value=_factory_with_llm(llm)):
            resp = client.post("/api/agents/guided", json={"goal": "help track our sales leads in the crm"})

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["template"] == "sales_assistant"
        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == data["agent_id"]).first()
        assert agent is not None
        assert agent.status == "student"

    def test_requires_authentication(self, client):
        resp = client.post("/api/agents/guided", json={"goal": "do some stuff for me please"})
        assert resp.status_code == 401

    def test_goal_minimum_length(self, client, employee_user):
        global _current_test_user
        _current_test_user = employee_user
        resp = client.post("/api/agents/guided", json={"goal": "hi"})
        assert resp.status_code == 422


class TestAgentInitiatedCreation:
    def _governance(self, allowed: bool):
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": allowed, "reason": None if allowed else "Agent maturity below threshold"}
        )
        gov.request_approval = MagicMock(return_value="hitl-42")
        return gov

    def test_autonomous_agent_creates_directly(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user

        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("no llm"))
        gov = self._governance(allowed=True)
        with patch("api.agent_onboarding_routes.get_guided_agent_factory",
                   return_value=_factory_with_llm(llm)), \
             patch("api.agent_onboarding_routes.ServiceFactory.get_governance_service", return_value=gov):
            resp = client.post(
                "/api/agents/guided",
                json={"goal": "monitor inventory levels nightly", "acting_agent_id": "agent-auto-1"},
            )

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["created_by"] == "agent"
        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == data["agent_id"]).first()
        assert agent.parent_agent_id == "agent-auto-1"
        gov.request_approval.assert_not_called()

    def test_immature_agent_gets_hitl_not_created(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user

        gov = self._governance(allowed=False)
        with patch("api.agent_onboarding_routes.ServiceFactory.get_governance_service", return_value=gov):
            resp = client.post(
                "/api/agents/guided",
                json={"goal": "delete old records automatically", "acting_agent_id": "agent-student-1"},
            )

        assert resp.status_code == 202, resp.text
        data = resp.json()["data"]
        assert data["status"] == "pending_approval"
        assert data["hitl_action_id"] == "hitl-42"
        gov.request_approval.assert_called_once()
        req_kwargs = gov.request_approval.call_args.kwargs
        assert req_kwargs["agent_id"] == "agent-student-1"
        assert req_kwargs["action_type"] == "create_agent"
        # Nothing was created without approval
        assert db_session.query(AgentRegistry).filter(AgentRegistry.parent_agent_id == "agent-student-1").count() == 0


class TestAutomationSuggestions:
    def test_rule_based_suggestions_from_manual_history(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user

        for _ in range(5):
            db_session.add(AgentExecution(
                agent_id="a1",
                workspace_id="default",
                status="completed",
                triggered_by="manual",
                input_summary="Weekly vendor invoice collection",
            ))
        db_session.commit()

        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("no llm"))
        with patch("api.agent_onboarding_routes.get_automation_suggestion_service",
                   return_value=AutomationSuggestionService(llm_service=llm)):
            resp = client.get("/api/agents/automation-suggestions")

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["history_summary"]["frequent_manual_agent_runs"][0]["count"] == 5
        assert any("Weekly vendor invoice collection" in s["title"] for s in data["suggestions"])

    def test_llm_suggestions_passed_through(self, client, employee_user, db_session):
        global _current_test_user
        _current_test_user = employee_user

        llm = _llm_mock(
            '''[{"title": "Nightly invoice sweep", "description": "Collects vendor invoices", '''
            '''"trigger": "schedule", "steps": ["collect", "notify"], '''
            '''"evidence": "manual runs", "estimated_time_saved_minutes_per_month": 120}]'''
        )
        with patch("api.agent_onboarding_routes.get_automation_suggestion_service",
                   return_value=AutomationSuggestionService(llm_service=llm)):
            resp = client.get("/api/agents/automation-suggestions")

        assert resp.status_code == 200, resp.text
        suggestions = resp.json()["data"]["suggestions"]
        assert suggestions[0]["title"] == "Nightly invoice sweep"


class TestGuidedAgentFactoryUnit:
    @pytest.mark.asyncio
    async def test_llm_constraint_injection(self):
        llm = _llm_mock(
            '''{"name": "X", "description": "d", "category": "General", '''
            '''"capabilities": ["a"], "template": "custom", '''
            '''"configuration": {"system_prompt": "s", "constraints": []}}'''
        )
        factory = GuidedAgentFactory(llm_service=llm)
        blueprint = await factory.design_agent("anything at all")
        assert "require human approval for destructive actions" in blueprint["configuration"]["constraints"]

    @pytest.mark.asyncio
    async def test_generic_fallback_when_no_template_matches(self):
        factory = GuidedAgentFactory(llm_service=_llm_mock("not json at all {{{"))
        blueprint = await factory.design_agent("help with miscellaneous things")
        assert blueprint["template"] == "custom"
        assert blueprint["name"]
