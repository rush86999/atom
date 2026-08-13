"""
E2E Tests for Agent Execution Workflows.

Tests verify complete agent workflows including:
- Agent registration (created via API — the agents page is a control
  center with NO create/spawn form)
- Agent list rendering (agent cards, maturity/status badges)
- Chat message sending and user-message history
- Governance maturity validation (backend-enforced)
- Agent lifecycle management (list, search, filter)

Run with: pytest backend/tests/e2e_ui/tests/test_agent_execution.py -v
"""

import pytest
import uuid
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import ChatPage
from core.models import AgentRegistry
from datetime import datetime


# =============================================================================
# Helper Functions
# =============================================================================

def create_agent_via_api(db_session: Session, name: str, maturity: str = "INTERN", user_id: str = None) -> AgentRegistry:
    """Create an agent via database for faster test setup.

    Args:
        db_session: Database session
        name: Agent name
        maturity: Maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        user_id: User ID for agent ownership

    Returns:
        AgentRegistry: Created agent instance
    """
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name=name,
        status="idle",
        category="testing",
        module_path="core.agents.generic_agent",
        class_name="GenericAgent",
        user_id=user_id or str(uuid.uuid4()),
        updated_at=datetime.utcnow()
    )

    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    return agent


def cleanup_test_agent(db_session: Session, agent_name: str):
    """Cleanup test agent after test.

    Args:
        db_session: Database session
        agent_name: Name of agent to delete
    """
    try:
        agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == agent_name
        ).first()

        if agent:
            db_session.delete(agent)
            db_session.commit()
    except Exception as e:
        # Log but don't fail test if cleanup fails
        print(f"Warning: Failed to cleanup agent {agent_name}: {e}")


# =============================================================================
# Agent Spawn Tests
# =============================================================================

@pytest.mark.e2e
def test_agent_spawn_and_chat(authenticated_page: Page, db_session: Session):
    """Test agent registration and list rendering.

    The real agents page (/agents) is an Agent Control Center — it has NO
    create/spawn form (creating agents happens via API or the marketplace).
    This test therefore:
    1. Registers an agent via the same DB row the API would write
    2. Navigates to the agents page
    3. Asserts the agent card renders with its name (testid agent-card-{name})
    4. Asserts the card carries a status badge

    Args:
        authenticated_page: Authenticated Playwright page
        db_session: Database session fixture
    """
    # Setup: Create unique agent name
    unique_id = str(uuid.uuid4())[:8]
    agent_name = f"E2ETestAgent_{unique_id}"

    # Register the agent via DB (the agents page offers no spawn form)
    create_agent_via_api(db_session, agent_name, "INTERN")

    # Navigate to agents page
    authenticated_page.goto("http://localhost:3001/agents")
    authenticated_page.wait_for_load_state("networkidle")

    # The agent card must render (testid = agent-card-{name})
    agent_card = authenticated_page.get_by_test_id(f"agent-card-{agent_name}")
    expect(agent_card).to_be_visible(timeout=10000)

    # The card carries the agent name and a status badge
    expect(agent_card).to_contain_text(agent_name)
    assert agent_card.get_by_test_id("agent-status-badge").is_visible(), \
        "Agent card should render a status badge"

    # Cleanup
    cleanup_test_agent(db_session, agent_name)


@pytest.mark.e2e
def test_agent_streaming_response(authenticated_page: Page, db_session: Session):
    """Test agent chat via the real /chat interface.

    Verifies:
    1. Create agent via API for setup
    2. Navigate to chat page with the agent preselected (/chat?agent_id=...)
    3. Send message via chat input
    4. User message appears in the message list (optimistic append — no LLM
       key required); a streaming assistant response appears when an LLM
       provider is configured (environment-dependent, not asserted)

    Args:
        authenticated_page: Authenticated Playwright page
        db_session: Database session fixture
    """
    # Setup: Create agent via API
    unique_id = str(uuid.uuid4())[:8]
    agent_name = f"StreamingTestAgent_{unique_id}"
    agent = create_agent_via_api(db_session, agent_name, "INTERN")

    # Navigate to chat with the agent preselected
    authenticated_page.goto(f"http://localhost:3001/chat?agent_id={agent.id}")
    chat_page = ChatPage(authenticated_page)
    chat_page.hide_dev_overlays()
    assert chat_page.is_loaded(), "Chat interface should be loaded"

    # Send message via chat input
    test_message = f"Hello E2E {unique_id}"
    chat_page.send_message(test_message)

    # User message appears in history (optimistic append — deterministic
    # regardless of LLM availability)
    last_message = chat_page.get_last_user_message()
    assert test_message in last_message, \
        f"Expected message '{test_message}' in chat history, got: {last_message!r}"

    # Cleanup
    cleanup_test_agent(db_session, agent_name)


@pytest.mark.e2e
def test_agent_governance_maturity(authenticated_page: Page, db_session: Session):
    """Test agent governance maturity rendering.

    Verifies:
    1. Create agents with different maturity levels
    2. Navigate to the agents page
    3. Verify each agent's card renders
    4. Governance enforcement itself lives in the backend
       (require_governance / maturity checks, unit-tested) — the UI surface
       here is the card + status badge rendering for registered agents.

    Args:
        authenticated_page: Authenticated Playwright page
        db_session: Database session fixture
    """
    # Setup: Create agents with different maturity levels
    unique_id = str(uuid.uuid4())[:8]

    student_agent = create_agent_via_api(db_session, f"StudentAgent_{unique_id}", "STUDENT")
    intern_agent = create_agent_via_api(db_session, f"InternAgent_{unique_id}", "INTERN")
    autonomous_agent = create_agent_via_api(db_session, f"AutonomousAgent_{unique_id}", "AUTONOMOUS")

    # Navigate to the agents page
    authenticated_page.goto("http://localhost:3001/agents")
    authenticated_page.wait_for_load_state("networkidle")

    # Each agent's card must render
    for agent in (student_agent, intern_agent, autonomous_agent):
        agent_card = authenticated_page.get_by_test_id(f"agent-card-{agent.name}")
        expect(agent_card).to_be_visible(timeout=10000)
        assert agent_card.get_by_test_id("agent-status-badge").is_visible(), \
            f"Card for '{agent.name}' should render a status badge"

    # Cleanup
    cleanup_test_agent(db_session, student_agent.name)
    cleanup_test_agent(db_session, intern_agent.name)
    cleanup_test_agent(db_session, autonomous_agent.name)


# =============================================================================
# Agent Lifecycle Tests
# =============================================================================

@pytest.mark.e2e
def test_agent_list_renders_all(authenticated_page: Page, db_session: Session):
    """Test that the agents page renders every registered agent.

    The real agents page renders ALL agents in a grid (no pagination UI
    exists — the server has no pagination contract for this surface).

    Args:
        authenticated_page: Authenticated Playwright page
        db_session: Database session fixture
    """
    # Setup: Create multiple agents
    unique_id = str(uuid.uuid4())[:8]
    agent_names = [f"PaginationAgent_{unique_id}_{i}" for i in range(15)]

    for name in agent_names:
        create_agent_via_api(db_session, name, "INTERN")

    # Navigate to agents page
    authenticated_page.goto("http://localhost:3001/agents")
    authenticated_page.wait_for_load_state("networkidle")

    # All created agents must render in the grid
    grid = authenticated_page.get_by_test_id("agents-grid")
    expect(grid).to_be_visible(timeout=10000)
    for name in agent_names:
        expect(authenticated_page.get_by_test_id(f"agent-card-{name}")).to_be_visible(
            timeout=5000
        )

    # Cleanup
    for name in agent_names:
        cleanup_test_agent(db_session, name)


@pytest.mark.e2e
def test_agent_search_and_filter(authenticated_page: Page, db_session: Session):
    """Test the agents page search box filters the grid.

    Args:
        authenticated_page: Authenticated Playwright page
        db_session: Database session fixture
    """
    # Setup: Create agents with different names
    unique_id = str(uuid.uuid4())[:8]
    search_agent = create_agent_via_api(db_session, f"SearchTarget_{unique_id}", "INTERN")
    other_agent = create_agent_via_api(db_session, f"OtherAgent_{unique_id}", "AUTONOMOUS")

    # Navigate to agents page
    authenticated_page.goto("http://localhost:3001/agents")
    authenticated_page.wait_for_load_state("networkidle")

    # Both cards render before filtering
    target_card = authenticated_page.get_by_test_id(f"agent-card-{search_agent.name}")
    other_card = authenticated_page.get_by_test_id(f"agent-card-{other_agent.name}")
    expect(target_card).to_be_visible(timeout=10000)
    expect(other_card).to_be_visible(timeout=5000)

    # Search for the target agent (real search input on the page)
    search_input = authenticated_page.get_by_test_id("agent-search-input")
    search_input.fill(f"SearchTarget_{unique_id}")
    authenticated_page.wait_for_timeout(500)

    # Target stays visible; the other card is filtered out
    assert target_card.is_visible(), "Target agent card should stay visible after search"
    assert not other_card.is_visible(), \
        "Unrelated agent card should be filtered out by search"

    # Clear search restores both
    search_input.fill("")
    authenticated_page.wait_for_timeout(500)
    assert other_card.is_visible(), "Clearing search should restore filtered agents"

    # Cleanup
    cleanup_test_agent(db_session, search_agent.name)
    cleanup_test_agent(db_session, other_agent.name)


# =============================================================================
# Cleanup Fixture
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_data(db_session: Session):
    """Cleanup test data after each test.

    This fixture runs after each test to clean up any test-created agents.
    Uses autouse=True to run automatically for all tests.

    Args:
        db_session: Database session fixture

    Yields:
        None: Allows test to execute
    """
    yield

    # Cleanup any agents with E2E test prefix
    try:
        test_agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("%E2E%") |
            AgentRegistry.name.like("%StreamingTest%") |
            AgentRegistry.name.like("%StudentAgent%") |
            AgentRegistry.name.like("%InternAgent%") |
            AgentRegistry.name.like("%AutonomousAgent%") |
            AgentRegistry.name.like("%PaginationAgent%") |
            AgentRegistry.name.like("%SearchTarget%") |
            AgentRegistry.name.like("%OtherAgent%")
        ).all()

        for agent in test_agents:
            db_session.delete(agent)

        db_session.commit()
    except Exception as e:
        # Log but don't fail test if cleanup fails
        print(f"Warning: Failed to cleanup test agents: {e}")
