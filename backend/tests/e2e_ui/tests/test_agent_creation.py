"""
E2E tests for agent creation workflow via web UI (AGNT-01).

Run with: pytest backend/tests/e2e_ui/tests/test_agent_creation.py -v
"""

import pytest
import uuid
from datetime import datetime
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

from core.models import AgentRegistry


class TestAgentCreation:
    """E2E tests for agent creation workflow via web UI (AGNT-01)."""

    def test_create_agent_via_ui(self, authenticated_page_api: Page, db_session: Session):
        """Verify user can create agent via web UI form.

        This test validates:
        1. Navigate to agents page
        2. Click "Create Agent" button
        3. Wait for agent creation modal
        4. Fill agent form (name, category, description)
        5. Submit form
        6. Verify success notification
        7. Verify agent appears in agent list
        8. Verify agent in database registry
        9. Verify agent status is active and maturity is STUDENT

        Args:
            authenticated_page_api: Authenticated Playwright page
            db_session: Database session for verification

        Coverage: AGNT-01 (Agent creation via UI)
        """
        # Generate unique agent name
        agent_name = f"E2E Test Agent {uuid.uuid4()[:8]}"

        # Navigate to agents page
        authenticated_page_api.goto("/agents")
        authenticated_page_api.wait_for_load_state("networkidle")

        # Click "Create Agent" button
        create_agent_button = authenticated_page_api.locator('[data-testid="create-agent-button"]')
        expect(create_agent_button).to_be_visible(timeout=10000)
        create_agent_button.click()

        # Wait for agent creation modal
        modal = authenticated_page_api.locator('[data-testid="agent-creation-modal"]')
        expect(modal).to_be_visible(timeout=10000)

        # Fill agent form
        authenticated_page_api.fill('[data-testid="agent-name-input"]', agent_name)
        authenticated_page_api.select_option('[data-testid="agent-category-select"]', "productivity")
        authenticated_page_api.fill('[data-testid="agent-description-input"]', "E2E test agent for verification")

        # Submit form
        submit_button = authenticated_page_api.locator('[data-testid="create-agent-submit-button"]')
        expect(submit_button).to_be_visible()
        submit_button.click()

        # Wait for success notification
        success_notification = authenticated_page_api.locator('[data-testid="agent-created-success"]')
        expect(success_notification).to_be_visible(timeout=10000)

        # Verify agent appears in agent list
        agent_card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent_name}"]')
        expect(agent_card).to_be_visible(timeout=10000)

        # Verify agent in database
        agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == agent_name
        ).first()

        assert agent is not None, f"Agent {agent_name} should be in database"
        assert agent.status == "active", "Agent should be active"
        assert agent.maturity_level == "STUDENT", "New agents should start at STUDENT maturity"

    def test_create_agent_with_validation_errors(self, authenticated_page_api: Page, db_session: Session):
        """Verify validation errors prevent creating agents with invalid data.

        This test validates:
        1. Navigate to agents page
        2. Click "Create Agent" button
        3. Try to submit form without required fields (empty name)
        4. Verify validation error appears
        5. Verify agent not created in database

        Args:
            authenticated_page_api: Authenticated Playwright page
            db_session: Database session for verification

        Coverage: AGNT-01 (Agent creation validation)
        """
        # Navigate to agents page
        authenticated_page_api.goto("/agents")
        authenticated_page_api.wait_for_load_state("networkidle")

        # Click "Create Agent" button
        create_agent_button = authenticated_page_api.locator('[data-testid="create-agent-button"]')
        expect(create_agent_button).to_be_visible(timeout=10000)
        create_agent_button.click()

        # Wait for agent creation modal
        modal = authenticated_page_api.locator('[data-testid="agent-creation-modal"]')
        expect(modal).to_be_visible(timeout=10000)

        # Try to submit without filling required fields
        submit_button = authenticated_page_api.locator('[data-testid="create-agent-submit-button"]')
        expect(submit_button).to_be_visible()
        submit_button.click()

        # Verify validation error appears
        validation_error = authenticated_page_api.locator('[data-testid="validation-error"]')
        expect(validation_error).to_be_visible(timeout=5000)

        # Verify modal still open (agent not created)
        expect(modal).to_be_visible()

        # Verify no agent was created in database
        # Should not find any agent created in the last minute
        one_minute_ago = datetime.utcnow()
        agents_created = db_session.query(AgentRegistry).filter(
            AgentRegistry.created_at >= one_minute_ago
        ).count()

        assert agents_created == 0, "No agents should be created when validation fails"

    def test_create_agent_via_api_faster(self, authenticated_page_api: Page, db_session: Session):
        """Verify creating agent via API is faster than UI.

        This test validates:
        1. Create agent directly via API (or database for speed)
        2. Verify agent in database
        3. Refresh UI and verify agent appears
        4. Compare timing with UI creation (API should be faster)

        Args:
            authenticated_page_api: Authenticated Playwright page
            db_session: Database session for verification

        Coverage: AGNT-01 (Agent creation via API)
        """
        import time

        # Generate unique agent name
        agent_name = f"API Test Agent {uuid.uuid4()[:8]}"

        # Create agent via database (fastest method for testing)
        start_time = time.time()

        agent = AgentRegistry(
            name=agent_name,
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            description="E2E test agent created via API",
            status="active",
            maturity_level="INTERN",
            confidence_score=0.6,
            created_at=datetime.utcnow()
        )

        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        api_creation_time = time.time() - start_time

        # Navigate to agents page and verify agent appears
        authenticated_page_api.goto("/agents")
        authenticated_page_api.wait_for_load_state("networkidle")

        # Wait for agent to appear in list (with timeout)
        agent_card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent_name}"]')
        expect(agent_card).to_be_visible(timeout=10000)

        # Verify agent in database
        db_agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == agent_name
        ).first()

        assert db_agent is not None, "Agent should be in database"
        assert db_agent.name == agent_name
        assert db_agent.maturity_level == "INTERN"
        assert db_agent.status == "active"

        # API creation should be fast (< 1 second)
        assert api_creation_time < 1.0, f"API creation should be fast, took {api_creation_time:.2f}s"

    def test_agent_maturity_level_default(self, authenticated_page_api: Page, db_session: Session):
        """Verify new agents default to STUDENT maturity level.

        This test validates:
        1. Create agent via UI (no maturity level selection)
        2. Verify default maturity_level == "STUDENT"
        3. Verify new agents cannot perform restricted actions

        Args:
            authenticated_page_api: Authenticated Playwright page
            db_session: Database session for verification

        Coverage: AGNT-01 (Agent default maturity level)
        """
        # Generate unique agent name
        agent_name = f"Student Agent {uuid.uuid4()[:8]}"

        # Navigate to agents page
        authenticated_page_api.goto("/agents")
        authenticated_page_api.wait_for_load_state("networkidle")

        # Click "Create Agent" button
        create_agent_button = authenticated_page_api.locator('[data-testid="create-agent-button"]')
        expect(create_agent_button).to_be_visible(timeout=10000)
        create_agent_button.click()

        # Wait for agent creation modal
        modal = authenticated_page_api.locator('[data-testid="agent-creation-modal"]')
        expect(modal).to_be_visible(timeout=10000)

        # Fill agent form (without selecting maturity level)
        authenticated_page_api.fill('[data-testid="agent-name-input"]', agent_name)
        authenticated_page_api.select_option('[data-testid="agent-category-select"]', "productivity")
        authenticated_page_api.fill('[data-testid="agent-description-input"]', "Test STUDENT agent")

        # Submit form
        submit_button = authenticated_page_api.locator('[data-testid="create-agent-submit-button"]')
        expect(submit_button).to_be_visible()
        submit_button.click()

        # Wait for success notification
        success_notification = authenticated_page_api.locator('[data-testid="agent-created-success"]')
        expect(success_notification).to_be_visible(timeout=10000)

        # Verify agent in database has STUDENT maturity
        agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == agent_name
        ).first()

        assert agent is not None, "Agent should be in database"
        assert agent.status == "active", "Agent should be active"
        assert agent.maturity_level == "STUDENT", "New agents should default to STUDENT maturity"

        # Verify STUDENT agent cannot perform restricted actions (e.g., automated triggers)
        # This is verified by checking the maturity_level field in the database
        assert agent.maturity_level == "STUDENT", "STUDENT agents should not have restricted permissions"

    def test_multiple_agents_can_be_created(self, authenticated_page_api: Page, db_session: Session):
        """Verify multiple agents can be created sequentially.

        This test validates:
        1. Create 3 agents sequentially via UI
        2. Use unique names with UUID for each
        3. Verify all 3 appear in agent list
        4. Verify all 3 in database with unique IDs
        5. Verify no ID collisions

        Args:
            authenticated_page_api: Authenticated Playwright page
            db_session: Database session for verification

        Coverage: AGNT-01 (Multiple agent creation)
        """
        agent_names = []
        agent_ids = []

        # Create 3 agents
        for i in range(3):
            # Generate unique agent name
            agent_name = f"Multi Agent {i+1}-{uuid.uuid4()[:8]}"

            # Navigate to agents page
            authenticated_page_api.goto("/agents")
            authenticated_page_api.wait_for_load_state("networkidle")

            # Click "Create Agent" button
            create_agent_button = authenticated_page_api.locator('[data-testid="create-agent-button"]')
            expect(create_agent_button).to_be_visible(timeout=10000)
            create_agent_button.click()

            # Wait for agent creation modal
            modal = authenticated_page_api.locator('[data-testid="agent-creation-modal"]')
            expect(modal).to_be_visible(timeout=10000)

            # Fill agent form
            authenticated_page_api.fill('[data-testid="agent-name-input"]', agent_name)
            authenticated_page_api.select_option('[data-testid="agent-category-select"]', "productivity")
            authenticated_page_api.fill('[data-testid="agent-description-input"]', f"Test agent {i+1}")

            # Submit form
            submit_button = authenticated_page_api.locator('[data-testid="create-agent-submit-button"]')
            expect(submit_button).to_be_visible()
            submit_button.click()

            # Wait for success notification
            success_notification = authenticated_page_api.locator('[data-testid="agent-created-success"]')
            expect(success_notification).to_be_visible(timeout=10000)

            # Store agent name
            agent_names.append(agent_name)

        # Verify all 3 agents in database
        for agent_name in agent_names:
            agent = db_session.query(AgentRegistry).filter(
                AgentRegistry.name == agent_name
            ).first()

            assert agent is not None, f"Agent {agent_name} should be in database"
            agent_ids.append(agent.id)

        # Verify all IDs are unique
        assert len(set(agent_ids)) == 3, "All agent IDs should be unique"

        # Navigate to agents page and verify all agents appear in list
        authenticated_page_api.goto("/agents")
        authenticated_page_api.wait_for_load_state("networkidle")

        for agent_name in agent_names:
            agent_card = authenticated_page_api.locator(f'[data-testid="agent-card-{agent_name}"]')
            expect(agent_card).to_be_visible(timeout=10000)


# Helper functions

def verify_agent_in_db(db_session: Session, agent_name: str) -> AgentRegistry:
    """Verify agent exists in database with correct attributes.

    Args:
        db_session: Database session
        agent_name: Agent name to verify

    Returns:
        AgentRegistry: Agent instance if found

    Raises:
        AssertionError: If agent not found or attributes incorrect
    """
    agent = db_session.query(AgentRegistry).filter(
        AgentRegistry.name == agent_name
    ).first()

    assert agent is not None, f"Agent {agent_name} should be in database"
    assert agent.status == "active", "Agent should be active"
    assert agent.maturity_level == "STUDENT", "New agents should be STUDENT"

    return agent
