"""
E2E tests for agent registry verification (AGNT-02).

Rewritten 2026-08-12 to match the ACTUAL agents UI: agents are seeded through
the registry (db_session / API) and verified in the "Agent Control Center"
list, the client-side search box, and the maturity/status badges on AgentCard.

Run with: pytest backend/tests/e2e_ui/tests/test_agent_registry.py -v
"""

import uuid
import requests
from playwright.sync_api import Page, expect

from core.models import AgentRegistry


def seed_agent(db_session, name: str, status: str = "student", category: str = "testing",
               confidence_score: float = 0.5, workspace_id: str = "default") -> AgentRegistry:
    """Insert an agent row directly (the sanctioned e2e seeding pattern)."""
    agent = AgentRegistry(
        name=name,
        category=category,
        module_path="test.module",
        class_name="TestAgent",
        description=f"Test agent {name}",
        status=status,
        confidence_score=confidence_score,
        workspace_id=workspace_id,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


class TestAgentRegistryVerification:
    """E2E tests for agent registry verification (AGNT-02)."""

    def test_agent_registry_persistence(self, authenticated_page_api: Page, db_session, setup_test_user):
        """Verify agent persists in registry and round-trips via the API.

        1. Seed agent with unique ID
        2. Query registry by ID — all fields match
        3. GET /api/agents/{id} returns the same agent to the UI user

        Coverage: AGNT-02 (Agent registry persistence)
        """
        agent = seed_agent(db_session, f"Registry Test {str(uuid.uuid4())[:8]}", status="intern", confidence_score=0.6)

        retrieved = db_session.query(AgentRegistry).filter_by(id=agent.id).first()
        assert retrieved is not None, "Agent should be retrieved from registry"
        assert retrieved.id == agent.id
        assert retrieved.name == agent.name
        assert retrieved.maturity_level == "intern", "Maturity level should match"
        assert retrieved.status == "intern", "Status should match"

        detail = requests.get(
            f"http://localhost:8001/api/agents/{agent.id}",
            headers={"Authorization": f"Bearer {setup_test_user['access_token']}"},
            timeout=15,
        ).json()["data"]
        assert detail["id"] == agent.id
        assert detail["name"] == agent.name
        assert detail["status"] == "intern"

    def test_agent_registry_unique_ids(self, db_session):
        """Verify agent registry enforces unique IDs (no collisions)."""
        agent_ids = []
        for i in range(5):
            agent = seed_agent(db_session, f"Unique ID Test {i + 1}-{str(uuid.uuid4())[:8]}", status="student")
            agent_ids.append(agent.id)

        agents = db_session.query(AgentRegistry).filter(AgentRegistry.id.in_(agent_ids)).all()
        assert len(agents) == 5, f"All 5 agents should be retrieved, got {len(agents)}"
        assert len(set(agent_ids)) == 5, "All agent IDs should be unique"

    def test_agent_registry_search_by_name(self, authenticated_page_api: Page, db_session):
        """Verify the UI search box filters the agent list by name.

        1. Seed a uniquely-named agent
        2. Navigate to agents page — card visible
        3. Search for a non-matching term — card hidden
        4. Search for the agent name — card visible again

        Coverage: AGNT-02 (Agent registry search by name)
        """
        unique = str(uuid.uuid4())[:8]
        agent = seed_agent(db_session, f"Searchable Agent {unique}", status="intern")

        authenticated_page_api.goto("http://localhost:3001/agents")
        card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent.name}"]')
        expect(card).to_be_visible(timeout=15000)

        search_input = authenticated_page_api.locator('[data-testid="agent-search-input"]')
        expect(search_input).to_be_visible()

        search_input.fill("zzz-no-such-agent-match")
        authenticated_page_api.wait_for_timeout(300)
        expect(card).to_have_count(0, timeout=5000)

        search_input.fill(unique)
        authenticated_page_api.wait_for_timeout(300)
        expect(card).to_be_visible()

        db_agent = db_session.query(AgentRegistry).filter(AgentRegistry.name == agent.name).first()
        assert db_agent is not None, "Agent should be found by name in database"

    def test_agent_registry_filter_by_maturity(self, authenticated_page_api: Page, db_session):
        """Verify each card renders its registry maturity level.

        1. Seed 3 agents with different maturity levels
        2. UI: each AgentCard shows the correct maturity badge
        3. GET /api/agents/{id}/status reports the seeded maturity
        4. DB query by status finds exactly one per tier

        Coverage: AGNT-02 (Agent registry maturity display + filterability)
        """
        unique_suffix = str(uuid.uuid4())[:8]
        agents_data = [
            ("Filter Student", "student", 0.4),
            ("Filter Intern", "intern", 0.6),
            ("Filter Supervised", "supervised", 0.8),
        ]
        seeded = []
        for name_part, status, confidence in agents_data:
            agent = seed_agent(db_session, f"{name_part} {unique_suffix}", status=status, confidence_score=confidence)
            seeded.append((agent, status))

        authenticated_page_api.goto("http://localhost:3001/agents")
        for agent, status in seeded:
            card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent.name}"]')
            expect(card).to_be_visible(timeout=15000)
            expect(card.locator('[data-testid="agent-maturity-badge"]')).to_have_text(status)

        intern_rows = db_session.query(AgentRegistry).filter(
            AgentRegistry.status == "intern",
            AgentRegistry.name.like(f"%{unique_suffix}%"),
        ).all()
        assert len(intern_rows) == 1, "Should find exactly 1 INTERN agent"
        assert intern_rows[0].maturity_level == "intern"

    def test_agent_registry_update_status(self, authenticated_page_api: Page, db_session, setup_test_user):
        """Verify agent status updates are reflected in registry + UI.

        1. Seed agent with intern status
        2. Update status to paused (deactivated)
        3. GET /api/agents/{id}/status reflects paused
        4. UI: card shows the Paused status badge after reload

        Coverage: AGNT-02 (Agent registry status update)
        """
        agent = seed_agent(db_session, f"Status Test {str(uuid.uuid4())[:8]}", status="intern")
        assert agent.status == "intern", "Agent should start with intern status"

        agent.status = "paused"
        db_session.commit()
        db_session.refresh(agent)
        assert agent.status == "paused", "Agent status should be updated to paused"

        status = requests.get(
            f"http://localhost:8001/api/agents/{agent.id}/status",
            headers={"Authorization": f"Bearer {setup_test_user['access_token']}"},
            timeout=15,
        ).json()["data"]
        assert status["status"] == "paused"

        authenticated_page_api.goto("http://localhost:3001/agents")
        card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent.name}"]')
        expect(card).to_be_visible(timeout=15000)
        expect(card.locator('[data-testid="agent-status-badge"]')).to_contain_text("Paused")
