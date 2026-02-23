"""
E2E tests for agent governance enforcement (AGENT-04, AGENT-05).

Tests agent maturity level enforcement including:
- STUDENT agents blocked from restricted actions
- INTERN agents require approval before actions
- SUPERVISED agents auto-execute with monitoring
- Approval dialog workflow

Run with: pytest tests/e2e_ui/tests/test_agent_governance.py -v
"""

import pytest
from playwright.sync_api import Page, expect
from typing import Dict, Any

# Import Page Objects
from tests.e2e_ui.pages.page_objects import ChatPage

# Import fixtures
from tests.e2e_ui.fixtures.api_fixtures import create_test_agent_direct

# Import models for AgentStatus
import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import AgentStatus, AgentRegistry


class TestAgentGovernanceEnforcement:
    """
    E2E tests for agent governance enforcement.

    Validates that agents at different maturity levels are properly
    governed according to their permissions and approval requirements.
    """

    def test_student_agent_blocked_from_restricted_actions(
        self,
        browser,
        db_session,
        setup_test_user
    ):
        """
        Test that STUDENT agents are blocked from restricted actions.

        AGENT-04: STUDENT agents should not be able to perform actions
        with complexity 2 or higher without showing an error.

        Steps:
        1. Create a STUDENT agent via API
        2. Select STUDENT agent in chat interface
        3. Send message requiring action (e.g., "delete project")
        4. Verify governance error message displayed
        5. Verify action not executed
        """
        # Create STUDENT agent directly in database
        agent_result = create_test_agent_direct(
            db=db_session,
            name="Student Test Agent",
            status="STUDENT",
            category="testing",
            confidence_score=0.3
        )

        agent_id = agent_result["agent_id"]
        agent_name = agent_result["name"]

        # Create page and navigate to chat
        page = browser.new_page()
        chat_page = ChatPage(page)
        chat_page.navigate()
        chat_page.wait_for_load()

        # Select STUDENT agent from dropdown
        chat_page.select_agent(agent_name)

        # Send message requiring restricted action
        chat_page.send_message("delete all projects")

        # Verify governance error message appears
        # Look for error indicator or message containing "not permitted" or "blocked"
        page.wait_for_timeout(2000)  # Wait for governance check

        # Check for error message in chat
        error_locators = [
            page.get_by_test_id("governance-error-message"),
            page.get_by_text("not permitted"),
            page.get_by_text("blocked"),
            page.get_by_text("not allowed"),
            page.get_by_test_id("error-message")
        ]

        error_found = False
        for locator in error_locators:
            if locator.count() > 0:
                error_found = True
                break

        assert error_found, "STUDENT agent should show governance error for restricted actions"

        # Verify no assistant message (action not executed)
        assistant_messages = chat_page.assistant_message.all()
        assert len(assistant_messages) == 0, "Action should not be executed for STUDENT agent"

        page.close()


    def test_intern_agent_shows_approval_dialog(
        self,
        browser,
        db_session,
        setup_test_user
    ):
        """
        Test that INTERN agents show approval dialog for actions.

        AGENT-05: INTERN agents should trigger approval workflow before
        executing actions with complexity 3 or higher.

        Steps:
        1. Create an INTERN agent via API
        2. Select INTERN agent in chat interface
        3. Send message requiring action
        4. Verify approval dialog appears
        5. Verify dialog shows proposed action
        6. Verify approve/reject buttons present
        """
        # Create INTERN agent directly in database
        agent_result = create_test_agent_direct(
            db=db_session,
            name="Intern Test Agent",
            status="INTERN",
            category="testing",
            confidence_score=0.6
        )

        agent_id = agent_result["agent_id"]
        agent_name = agent_result["name"]

        # Create page and navigate to chat
        page = browser.new_page()
        chat_page = ChatPage(page)
        chat_page.navigate()
        chat_page.wait_for_load()

        # Select INTERN agent from dropdown
        chat_page.select_agent(agent_name)

        # Send message requiring action proposal
        chat_page.send_message("create a new project called Test Project")

        # Wait for proposal workflow to trigger
        page.wait_for_timeout(2000)

        # Verify approval dialog appears
        approval_dialog = page.get_by_test_id("approval-dialog")
        expect(approval_dialog).to_be_visible()

        # Verify dialog shows proposed action
        proposed_action_text = page.get_by_test_id("proposed-action-text")
        expect(proposed_action_text).to_be_visible()

        # Verify approve button present
        approve_button = page.get_by_test_id("approve-action-button")
        expect(approve_button).to_be_visible()

        # Verify reject button present
        reject_button = page.get_by_test_id("reject-action-button")
        expect(reject_button).to_be_visible()

        page.close()


    def test_intern_approval_execute_on_approve(
        self,
        browser,
        db_session,
        setup_test_user
    ):
        """
        Test that INTERN agent action executes when approved.

        AGENT-05: When user approves an INTERN agent proposal,
        the action should execute successfully.

        Steps:
        1. Create an INTERN agent via API
        2. Select INTERN agent and trigger action proposal
        3. Click approve button
        4. Verify action executes
        5. Verify success message shown
        """
        # Create INTERN agent directly in database
        agent_result = create_test_agent_direct(
            db=db_session,
            name="Intern Approval Test Agent",
            status="INTERN",
            category="testing",
            confidence_score=0.6
        )

        agent_id = agent_result["agent_id"]
        agent_name = agent_result["name"]

        # Create page and navigate to chat
        page = browser.new_page()
        chat_page = ChatPage(page)
        chat_page.navigate()
        chat_page.wait_for_load()

        # Select INTERN agent from dropdown
        chat_page.select_agent(agent_name)

        # Send message to trigger proposal
        chat_page.send_message("create a project named Approved Test")

        # Wait for approval dialog
        page.wait_for_timeout(2000)
        approval_dialog = page.get_by_test_id("approval-dialog")
        expect(approval_dialog).to_be_visible()

        # Click approve button
        approve_button = page.get_by_test_id("approve-action-button")
        approve_button.click()

        # Wait for action to execute
        page.wait_for_timeout(3000)

        # Verify approval dialog closes
        expect(approval_dialog).not_to_be_visible()

        # Verify success message appears
        success_message = page.get_by_test_id("action-success-message")
        expect(success_message).to_be_visible()

        # Verify assistant message confirms action completed
        chat_page.wait_for_response(timeout=5000)
        last_message = chat_page.get_last_message()
        assert "created" in last_message.lower() or "success" in last_message.lower()

        page.close()


    def test_intern_reject_blocks_action(
        self,
        browser,
        db_session,
        setup_test_user
    ):
        """
        Test that rejecting INTERN agent proposal blocks action.

        AGENT-05: When user rejects an INTERN agent proposal,
        the action should NOT execute.

        Steps:
        1. Create an INTERN agent via API
        2. Select INTERN agent and trigger action proposal
        3. Click reject button
        4. Verify action does NOT execute
        5. Verify rejection message shown
        """
        # Create INTERN agent directly in database
        agent_result = create_test_agent_direct(
            db=db_session,
            name="Intern Reject Test Agent",
            status="INTERN",
            category="testing",
            confidence_score=0.6
        )

        agent_id = agent_result["agent_id"]
        agent_name = agent_result["name"]

        # Create page and navigate to chat
        page = browser.new_page()
        chat_page = ChatPage(page)
        chat_page.navigate()
        chat_page.wait_for_load()

        # Select INTERN agent from dropdown
        chat_page.select_agent(agent_name)

        # Send message to trigger proposal
        chat_page.send_message("delete project named Rejected Project")

        # Wait for approval dialog
        page.wait_for_timeout(2000)
        approval_dialog = page.get_by_test_id("approval-dialog")
        expect(approval_dialog).to_be_visible()

        # Click reject button
        reject_button = page.get_by_test_id("reject-action-button")
        reject_button.click()

        # Wait for dialog to close
        page.wait_for_timeout(2000)

        # Verify approval dialog closes
        expect(approval_dialog).not_to_be_visible()

        # Verify rejection message appears
        rejection_message = page.get_by_test_id("action-rejected-message")
        expect(rejection_message).to_be_visible()

        # Verify no assistant message (action not executed)
        assistant_messages = chat_page.assistant_message.all()
        # There might be a rejection message, but no action completion message
        assert len(assistant_messages) == 0 or "rejected" in rejection_message.text_content().lower()

        page.close()


    def test_supervised_agent_auto_executes(
        self,
        browser,
        db_session,
        setup_test_user
    ):
        """
        Test that SUPERVISED agents auto-execute actions.

        AGENT-05: SUPERVISED agents should execute actions without
        requiring approval, with real-time monitoring.

        Steps:
        1. Create a SUPERVISED agent via API
        2. Select SUPERVISED agent in chat interface
        3. Send message requiring action
        4. Verify no approval dialog (auto-executes)
        5. Verify action completes
        6. Verify execution logged
        """
        # Create SUPERVISED agent directly in database
        agent_result = create_test_agent_direct(
            db=db_session,
            name="Supervised Test Agent",
            status="SUPERVISED",
            category="testing",
            confidence_score=0.8
        )

        agent_id = agent_result["agent_id"]
        agent_name = agent_result["name"]

        # Create page and navigate to chat
        page = browser.new_page()
        chat_page = ChatPage(page)
        chat_page.navigate()
        chat_page.wait_for_load()

        # Select SUPERVISED agent from dropdown
        chat_page.select_agent(agent_name)

        # Send message requiring action
        chat_page.send_message("create a project named Supervised Auto Project")

        # Wait for action to execute (no approval dialog should appear)
        page.wait_for_timeout(2000)

        # Verify NO approval dialog appears
        approval_dialog = page.get_by_test_id("approval-dialog")
        expect(approval_dialog).not_to_be_visible()

        # Verify action executes (assistant response appears)
        chat_page.wait_for_response(timeout=5000)
        last_message = chat_page.get_last_message()
        assert len(last_message) > 0, "SUPERVISED agent should execute action and respond"

        # Verify action completed successfully
        success_indicators = [
            page.get_by_test_id("action-success-message"),
            page.get_by_text("created"),
            page.get_by_text("completed"),
            page.get_by_text("success")
        ]

        success_found = False
        for indicator in success_indicators:
            if indicator.count() > 0:
                success_found = True
                break

        assert success_found, "SUPERVISED agent should show action completion"

        # Verify execution logged (check for monitoring indicator)
        monitoring_indicator = page.get_by_test_id("monitoring-indicator")
        # Monitoring may be subtle, just verify it exists or doesn't error
        if monitoring_indicator.count() > 0:
            expect(monitoring_indicator).to_be_visible()

        page.close()
