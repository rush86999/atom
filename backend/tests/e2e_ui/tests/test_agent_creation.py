"""
E2E tests for agent creation workflow (AGNT-01).

Rewritten 2026-08-12 to match the ACTUAL agents UI ("Agent Control Center"):
the create-agent modal was removed, so agents are created via the real API
endpoint (POST /api/agents/custom, requires AGENT_MANAGE) and VERIFIED in the
UI (AgentCard with name/status/maturity badges).

Run with: pytest backend/tests/e2e_ui/tests/test_agent_creation.py -v
"""

import uuid
import requests
from playwright.sync_api import Page, expect

from core.models import AgentRegistry


def create_agent_via_api(token: str, name: str, category: str = "testing", description: str = None) -> dict:
    """POST the real agent-create endpoint (AGENT_MANAGE required).

    Returns the parsed JSON body. Raises for HTTP errors.
    """
    base_url = "http://localhost:8001"
    payload = {"name": name, "category": category}
    if description is not None:
        payload["description"] = description
    response = requests.post(
        f"{base_url}/api/agents/custom",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


class TestAgentCreation:
    """E2E tests for agent creation (API-first, verified in the UI)."""

    def test_create_agent_via_api_and_verify_in_ui(
        self,
        authenticated_page_api: Page,
        db_session,
        setup_test_user,
        admin_user,
    ):
        """Verify agent creation via the real API and UI listing.

        1. POST /api/agents/custom (admin token) -> 201 with agent_id
        2. Verify registry row: status=student (STUDENT default), enabled
        3. GET /api/agents/{id} round-trips name/category
        4. UI: AgentCard appears with name, STUDENT maturity badge, Idle status
        5. UI: Run button present (agent is runnable surface)

        Coverage: AGNT-01 (Agent creation via API + UI verification)
        """
        _, admin_token = admin_user
        agent_name = f"E2E Created Agent {str(uuid.uuid4())[:8]}"

        response = create_agent_via_api(
            admin_token, agent_name, category="productivity", description="Created by e2e"
        )
        data = response.get("data", response)
        agent_id = data["agent_id"]
        assert agent_id, "Create response must include agent_id"

        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        assert agent is not None, f"Agent {agent_name} should be in registry"
        assert agent.name == agent_name
        assert agent.status == "student", "New agents should start at STUDENT maturity"
        assert agent.enabled is True, "New agents should be enabled"

        detail = requests.get(
            f"http://localhost:8001/api/agents/{agent_id}",
            headers={"Authorization": f"Bearer {setup_test_user['access_token']}"},
            timeout=15,
        ).json()["data"]
        assert detail["name"] == agent_name
        assert detail["category"] == "productivity"

        authenticated_page_api.goto("http://localhost:3001/agents")
        card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent_name}"]')
        expect(card).to_be_visible(timeout=15000)
        expect(card.locator('[data-testid="agent-maturity-badge"]')).to_have_text("student")
        expect(card.locator('[data-testid="agent-status-badge"]')).to_have_text("Idle")
        expect(card.get_by_role("button", name="Run")).to_be_visible()

    def test_create_agent_with_validation_errors(self, db_session, setup_test_user, admin_user):
        """Verify validation errors prevent creating agents with invalid data.

        1. POST /api/agents/custom with empty name -> 422
        2. POST with whitespace-only name -> 422
        3. POST with empty category -> 422
        4. Verify no registry row created for the rejected payloads

        Coverage: AGNT-01 (Agent creation validation)
        """
        _, admin_token = admin_user
        base_url = "http://localhost:8001"
        headers = {"Authorization": f"Bearer {admin_token}"}

        invalid_payloads = [
            {"name": "", "category": "testing"},
            {"name": "   ", "category": "testing"},
            {"name": f"Valid Name {str(uuid.uuid4())[:8]}", "category": ""},
            {"name": "  ", "category": "  "},
        ]
        for payload in invalid_payloads:
            response = requests.post(f"{base_url}/api/agents/custom", headers=headers, json=payload, timeout=15)
            assert response.status_code == 422, (
                f"Create with {payload!r} should 422, got {response.status_code}"
            )

        row = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "   "
        ).first()
        assert row is None, "Whitespace-only name must not create a registry row"

    def test_create_agent_requires_manage_permission(self, db_session, setup_test_user):
        """Verify agent creation is governance-gated (AGENT_MANAGE required).

        A regular (member) user must be rejected with 403 — creation is an
        agent-management action, not available to every authenticated user.

        Coverage: AGNT-01 (Creation permission enforcement)
        """
        token = setup_test_user["access_token"]
        response = requests.post(
            "http://localhost:8001/api/agents/custom",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": f"Member Agent {str(uuid.uuid4())[:8]}", "category": "testing"},
            timeout=15,
        )
        assert response.status_code == 403, (
            f"Member create should be 403, got {response.status_code}"
        )

    def test_agent_maturity_level_default(self, db_session, admin_user):
        """Verify new agents default to STUDENT maturity level.

        1. Create agent via API (no maturity selection possible)
        2. Verify DB status == student
        3. Verify GET /api/agents/{id}/status reports student
        4. Verify the governance rules document STUDENT as max-complexity-1
           (read-only tier — creation default cannot perform restricted actions)

        Coverage: AGNT-01 (Agent default maturity level)
        """
        _, admin_token = admin_user
        agent_name = f"Student Agent {str(uuid.uuid4())[:8]}"
        response = create_agent_via_api(admin_token, agent_name, category="productivity")
        agent_id = response["data"]["agent_id"]

        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        assert agent is not None
        assert agent.status == "student", "New agents should default to STUDENT maturity"

        status = requests.get(
            f"http://localhost:8001/api/agents/{agent_id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        ).json()["data"]
        assert status["status"] == "student"

        rules = requests.get(
            "http://localhost:8001/api/agent-governance/rules",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        ).json()["maturity_levels"]
        assert rules["student"]["max_complexity"] == 1, (
            "STUDENT tier must be read-only (complexity 1) per governance rules"
        )

    def test_multiple_agents_can_be_created(self, authenticated_page_api: Page, db_session, admin_user):
        """Verify multiple agents can be created and all appear in the UI.

        1. Create 3 agents via API with unique names
        2. Verify all 3 in registry with unique IDs
        3. UI: all 3 AgentCards visible

        Coverage: AGNT-01 (Multiple agent creation)
        """
        _, admin_token = admin_user
        agent_names = []
        agent_ids = []
        for i in range(3):
            agent_name = f"Multi Agent {i + 1}-{str(uuid.uuid4())[:8]}"
            response = create_agent_via_api(admin_token, agent_name, description=f"Test agent {i + 1}")
            agent_ids.append(response["data"]["agent_id"])
            agent_names.append(agent_name)

        assert len(set(agent_ids)) == 3, "All agent IDs should be unique"
        rows = db_session.query(AgentRegistry).filter(AgentRegistry.id.in_(agent_ids)).all()
        assert len(rows) == 3, "All 3 agents should be in registry"
        assert {a.id for a in rows} == set(agent_ids)

        authenticated_page_api.goto("http://localhost:3001/agents")
        for agent_name in agent_names:
            card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent_name}"]')
            expect(card).to_be_visible(timeout=15000)
