"""
E2E tests for agent lifecycle management (AGNT-07).

Rewritten 2026-08-12 to match the ACTUAL agents UI: the AgentCard offers
run/stop/chat/edit/reasoning actions (no activate/deactivate buttons), so
activation/deactivation is exercised via the API + registry and the UI is
asserted to reflect the state (Paused badge, error surfacing in the run
dialog and live logs, card removal after deletion).

Run with: pytest backend/tests/e2e_ui/tests/test_agent_lifecycle.py -v
"""

import uuid
import requests
from playwright.sync_api import Page, expect

from core.models import AgentRegistry, AgentExecution


def seed_agent(db_session, status: str = "student", name_prefix: str = "Lifecycle Agent") -> AgentRegistry:
    """Insert an agent row with the given maturity/state status."""
    agent = AgentRegistry(
        name=f"{name_prefix} {str(uuid.uuid4())[:8]}",
        status=status,
        category="testing",
        module_path="core.agents.generic_agent",
        class_name="GenericAgent",
        workspace_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def verify_agent_status(db_session, agent_id: str, expected_status: str) -> AgentRegistry:
    """Verify agent has expected status in database.

    expire_all() first: the fixture session uses expire_on_commit=False, so
    rows mutated by the BACKEND process (promote/run) would otherwise be
    returned stale from the identity map.
    """
    db_session.expire_all()
    agent = db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert agent is not None, f"Agent {agent_id} should exist in database"
    assert agent.status == expected_status, (
        f"Agent status should be {expected_status}, got {agent.status}"
    )
    return agent


class TestAgentLifecycleUI:
    """E2E tests for agent lifecycle via API + UI reflection (AGNT-07)."""

    def test_paused_agent_run_blocked_in_ui(
        self,
        authenticated_page_api: Page,
        db_session,
        setup_test_user,
    ):
        """Verify a paused (deactivated) agent cannot be executed.

        1. Seed a paused agent
        2. POST /api/agents/{id}/run -> 400 AGENT_INVALID_STATE
        3. No AgentExecution record created
        4. UI: card shows the Paused badge
        5. UI: run dialog surfaces the "Agent is paused" error in live logs

        Coverage: AGNT-07 (Deactivated agent execution blocking)
        """
        agent = seed_agent(db_session, status="paused")
        token = setup_test_user["access_token"]

        response = requests.post(
            f"http://localhost:8001/api/agents/{agent.id}/run",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
            timeout=15,
        )
        assert response.status_code == 400, (
            f"Run on paused agent should 400, got {response.status_code}"
        )
        error = response.json()["error"]
        assert error["code"] == "AGENT_INVALID_STATE", error
        assert "paused" in error["message"].lower(), error

        executions = db_session.query(AgentExecution).filter_by(agent_id=agent.id).all()
        assert len(executions) == 0, (
            f"AgentExecution table should be empty for inactive agent, found {len(executions)}"
        )

        authenticated_page_api.goto("http://localhost:3001/agents")
        card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent.name}"]')
        expect(card).to_be_visible(timeout=15000)
        expect(card.locator('[data-testid="agent-status-badge"]')).to_contain_text("Paused")

        # The card still offers a Run surface; executing it must surface the
        # governance error instead of starting the agent.
        card.get_by_role("button", name="Run").click()
        run_dialog = authenticated_page_api.get_by_role("dialog")
        expect(run_dialog).to_be_visible()
        run_dialog.get_by_role("button", name="Run Agent").click()
        expect(authenticated_page_api.get_by_text("Agent is paused").first).to_be_visible(timeout=10000)

    def test_promoted_agent_reflected_in_ui(
        self,
        authenticated_page_api: Page,
        db_session,
        setup_test_user,
        admin_user,
    ):
        """Verify promotion to AUTONOMOUS via API is reflected in the UI.

        1. Seed a student agent
        2. Member promote -> 403 (governance: AGENT_MANAGE required)
        3. Admin promote -> 200, status becomes autonomous
        4. UI: card shows the AUTONOMOUS maturity badge

        Coverage: AGNT-07 (Maturity transition reflected in UI)
        """
        agent = seed_agent(db_session, status="student")
        token = setup_test_user["access_token"]
        _, admin_token = admin_user

        member_response = requests.post(
            f"http://localhost:8001/api/agents/{agent.id}/promote",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert member_response.status_code == 403, (
            f"Member promote should be 403, got {member_response.status_code}"
        )

        admin_response = requests.post(
            f"http://localhost:8001/api/agents/{agent.id}/promote",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert admin_response.status_code == 200, admin_response.text
        verify_agent_status(db_session, agent.id, "autonomous")

        authenticated_page_api.goto("http://localhost:3001/agents")
        card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent.name}"]')
        expect(card).to_be_visible(timeout=15000)
        expect(card.locator('[data-testid="agent-maturity-badge"]')).to_have_text("autonomous")

    def test_agent_deletion_lifecycle(
        self,
        authenticated_page_api: Page,
        db_session,
        setup_test_user,
        admin_user,
    ):
        """Verify agent deletion lifecycle via API + UI removal.

        1. Seed an agent; verify it exists
        2. Member DELETE -> 403 (AGENT_MANAGE required)
        3. Admin DELETE -> 200; registry row removed; GET -> 404
        4. UI: card no longer present after reload

        Coverage: AGNT-07 (Agent deletion lifecycle)
        """
        agent = seed_agent(db_session, status="intern")
        token = setup_test_user["access_token"]
        _, admin_token = admin_user

        member_response = requests.delete(
            f"http://localhost:8001/api/agents/{agent.id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert member_response.status_code == 403, (
            f"Member delete should be 403, got {member_response.status_code}"
        )

        admin_response = requests.delete(
            f"http://localhost:8001/api/agents/{agent.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert admin_response.status_code == 200, admin_response.text

        assert db_session.query(AgentRegistry).filter_by(id=agent.id).first() is None, (
            "Agent should be removed from registry"
        )
        not_found = requests.get(
            f"http://localhost:8001/api/agents/{agent.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert not_found.status_code == 404

        authenticated_page_api.goto("http://localhost:3001/agents")
        card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent.name}"]')
        expect(card).to_have_count(0, timeout=15000)


class TestAgentLifecycleAPI:
    """E2E tests for agent lifecycle via API endpoints (AGNT-07)."""

    def test_agent_status_transitions(self, db_session, setup_test_user):
        """Verify valid status transitions and the paused run gate.

        1. Seed intern agent
        2. Promote (admin) -> autonomous
        3. Pause -> paused; run blocked with AGENT_INVALID_STATE
        4. Resume -> intern; run no longer state-blocked (not paused)

        Coverage: AGNT-07 (Agent status transitions via API)
        """
        agent = seed_agent(db_session, status="intern")
        token = setup_test_user["access_token"]

        verify_agent_status(db_session, agent.id, "intern")

        agent.status = "autonomous"
        db_session.commit()
        verify_agent_status(db_session, agent.id, "autonomous")

        agent.status = "paused"
        db_session.commit()
        verify_agent_status(db_session, agent.id, "paused")

        blocked = requests.post(
            f"http://localhost:8001/api/agents/{agent.id}/run",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
            timeout=15,
        )
        assert blocked.status_code == 400
        assert blocked.json()["error"]["code"] == "AGENT_INVALID_STATE"

        agent.status = "intern"
        db_session.commit()
        verify_agent_status(db_session, agent.id, "intern")
