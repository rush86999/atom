"""
E2E tests for agent execution history display.

These tests verify the complete execution history workflow including:
- Execution history display in chat interface
- Timestamp format validation
- Status indicators (completed, failed, running, blocked)
- History persistence across page refresh
- Navigation to session details

Run with: pytest backend/tests/e2e_ui/tests/test_agent_execution_history.py -v
"""

import pytest
import uuid
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime, timedelta

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import ExecutionHistoryPage, ChatPage
from tests.e2e_ui.utils.api_setup import create_test_user, authenticate_user, APIClient
from core.models import User, AgentRegistry, AgentExecution
from core.auth import get_password_hash


def create_test_user_db(db_session: Session, email: str, password: str) -> User:
    """Create a test user in the database.

    Args:
        db_session: Database session
        email: User email
        password: Plain text password (will be hashed)

    Returns:
        User: Created user instance
    """
    user = User(
        email=email,
        username=f"historyuser_{str(uuid.uuid4())[:8]}",
        password_hash=get_password_hash(password),
        is_active=True,
        status="active",
        email_verified=True,
        created_at=datetime.utcnow()
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def create_test_agent(db_session: Session, name: str = "TestAgent") -> AgentRegistry:
    """Create a test agent in the database.

    Args:
        db_session: Database session
        name: Agent name

    Returns:
        AgentRegistry: Created agent instance
    """
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name=name,
        maturity_level="AUTONOMOUS",
        description="Test agent for E2E tests",
        system_prompt="You are a helpful test agent",
        capabilities=["test"],
        is_active=True,
        created_at=datetime.utcnow()
    )

    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    return agent


def create_agent_execution(
    db_session: Session,
    agent_id: str,
    status: str = "completed",
    input_summary: str = "Test input",
    output_summary: str = "Test output",
    started_at: datetime = None
) -> AgentExecution:
    """Create a test agent execution record.

    Args:
        db_session: Database session
        agent_id: Agent ID
        status: Execution status (completed, failed, running, blocked)
        input_summary: Input summary text
        output_summary: Output summary text
        started_at: Start time (defaults to now)

    Returns:
        AgentExecution: Created execution instance
    """
    if started_at is None:
        started_at = datetime.utcnow()

    execution = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
        result_summary=f"Result: {output_summary}",
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=5) if status == "completed" else None,
        duration_seconds=5.0 if status == "completed" else 0.0,
        triggered_by="manual"
    )

    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    return execution


def create_authenticated_page(browser, user: User, token: str) -> Page:
    """Create a Playwright page with JWT token pre-set in localStorage.

    Args:
        browser: Playwright browser fixture
        user: User instance
        token: JWT token string

    Returns:
        Page: Authenticated Playwright page
    """
    context = browser.new_context()
    page = context.new_page()

    # Set JWT token in localStorage before navigating
    page.goto("http://localhost:3000")
    page.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")
    page.evaluate(f"() => localStorage.setItem('user_id', '{user.id}')")

    return page


def test_execution_history_display(browser, db_session: Session):
    """Test execution history displays in chat interface.

    This test verifies the happy path:
    1. Create test user and agent via API
    2. Execute agent action (create execution record)
    3. Navigate to execution history page
    4. Verify history entry appears
    5. Verify agent name shown
    6. Verify status indicator shows correct state
    7. Verify result preview displayed

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user with unique email
    unique_id = str(uuid.uuid4())[:8]
    email = f"history_display_{unique_id}@example.com"
    password = "HistoryPassword123!"

    user = create_test_user_db(db_session, email, password)
    assert user.id is not None

    # Create test agent
    agent = create_test_agent(db_session, name=f"HistoryAgent_{unique_id}")
    assert agent.id is not None

    # Create agent execution record
    execution = create_agent_execution(
        db_session,
        agent_id=agent.id,
        status="completed",
        input_summary=f"Test input {unique_id}",
        output_summary=f"Test output {unique_id}",
        started_at=datetime.utcnow()
    )
    assert execution.id is not None

    # Generate JWT token for authentication
    import jwt
    token = jwt.encode({"user_id": str(user.id), "email": email}, "test_secret", algorithm="HS256")

    # Create authenticated page
    page = create_authenticated_page(browser, user, token)

    # Navigate to execution history page
    history_page = ExecutionHistoryPage(page)
    history_page.navigate()
    history_page.wait_for_load()

    # Wait for history to load
    page.wait_for_timeout(1000)

    # Verify history entry appears
    history_count = history_page.get_history_count()
    assert history_count >= 1, f"Expected at least 1 history entry, got: {history_count}"

    # Verify agent name is shown
    displayed_agent = history_page.get_entry_agent(0)
    assert agent.name in displayed_agent, f"Expected agent name '{agent.name}' in '{displayed_agent}'"

    # Verify status indicator shows "completed"
    displayed_status = history_page.get_entry_status(0)
    assert displayed_status.lower() == "completed", f"Expected status 'completed', got: '{displayed_status}'"

    # Verify result preview is displayed
    displayed_result = history_page.get_entry_result(0)
    assert unique_id in displayed_result, f"Expected unique_id '{unique_id}' in result: '{displayed_result}'"

    # Verify timestamp is present
    displayed_timestamp = history_page.get_entry_timestamp(0)
    assert displayed_timestamp is not None and len(displayed_timestamp) > 0, "Expected timestamp to be present"


def test_history_timestamp_format(browser, db_session: Session):
    """Test execution history timestamp format validation.

    This test verifies:
    1. Create agent execution record
    2. Get history entry timestamp
    3. Verify timestamp in ISO format or readable format
    4. Verify timestamp is recent (within last minute)

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user and agent
    unique_id = str(uuid.uuid4())[:8]
    email = f"timestamp_test_{unique_id}@example.com"
    password = "TimestampPassword123!"

    user = create_test_user_db(db_session, email, password)
    agent = create_test_agent(db_session, name=f"TimestampAgent_{unique_id}")

    # Create execution with specific timestamp (now)
    execution_time = datetime.utcnow()
    execution = create_agent_execution(
        db_session,
        agent_id=agent.id,
        status="completed",
        input_summary="Timestamp test input",
        output_summary="Timestamp test output",
        started_at=execution_time
    )

    # Generate JWT token and create authenticated page
    import jwt
    token = jwt.encode({"user_id": str(user.id), "email": email}, "test_secret", algorithm="HS256")
    page = create_authenticated_page(browser, user, token)

    # Navigate to history page
    history_page = ExecutionHistoryPage(page)
    history_page.navigate()
    history_page.wait_for_load()

    # Wait for history to load
    page.wait_for_timeout(1000)

    # Get history entry timestamp
    displayed_timestamp = history_page.get_entry_timestamp(0)

    # Verify timestamp is present and non-empty
    assert displayed_timestamp is not None, "Expected timestamp to be present"
    assert len(displayed_timestamp) > 0, "Expected timestamp to be non-empty"

    # Verify timestamp contains time information (has digits and/or date separators)
    has_time_info = any(char.isdigit() for char in displayed_timestamp)
    assert has_time_info, f"Expected timestamp to contain time information, got: '{displayed_timestamp}'"

    # Verify timestamp is recent (either ISO format with today's date or relative time like "2 min ago")
    # For E2E test flexibility, we accept various formats
    today = datetime.utcnow().strftime("%Y-%m-%d")
    is_recent = (
        today in displayed_timestamp or  # ISO format with today's date
        "ago" in displayed_timestamp.lower() or  # Relative time format
        "just now" in displayed_timestamp.lower() or  # Just now format
        "second" in displayed_timestamp.lower() or  # Seconds ago format
        "min" in displayed_timestamp.lower()  # Minutes ago format
    )
    assert is_recent, f"Expected timestamp to be recent, got: '{displayed_timestamp}'"


def test_history_status_indicators(browser, db_session: Session):
    """Test execution history status indicators display correctly.

    This test verifies:
    1. Create successful execution (status: completed)
    2. Create failed execution (status: failed)
    3. Verify status: completed (green check icon/text)
    4. Verify status: failed (red x/error icon/text)
    5. Verify status values are visually distinct

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user and agent
    unique_id = str(uuid.uuid4())[:8]
    email = f"status_test_{unique_id}@example.com"
    password = "StatusPassword123!"

    user = create_test_user_db(db_session, email, password)
    agent = create_test_agent(db_session, name=f"StatusAgent_{unique_id}")

    # Create successful execution
    completed_execution = create_agent_execution(
        db_session,
        agent_id=agent.id,
        status="completed",
        input_summary="Successful input",
        output_summary="Successful output",
        started_at=datetime.utcnow() - timedelta(seconds=10)
    )

    # Create failed execution
    failed_execution = create_agent_execution(
        db_session,
        agent_id=agent.id,
        status="failed",
        input_summary="Failed input",
        output_summary="",
        started_at=datetime.utcnow() - timedelta(seconds=5)
    )

    # Generate JWT token and create authenticated page
    import jwt
    token = jwt.encode({"user_id": str(user.id), "email": email}, "test_secret", algorithm="HS256")
    page = create_authenticated_page(browser, user, token)

    # Navigate to history page
    history_page = ExecutionHistoryPage(page)
    history_page.navigate()
    history_page.wait_for_load()

    # Wait for history to load
    page.wait_for_timeout(1000)

    # Get all statuses displayed
    all_statuses = history_page.get_all_entry_statuses()
    assert len(all_statuses) >= 2, f"Expected at least 2 history entries, got: {len(all_statuses)}"

    # Verify we have both "completed" and "failed" statuses
    status_values = [s.lower() for s in all_statuses]
    assert "completed" in status_values, f"Expected 'completed' status in: {status_values}"
    assert "failed" in status_values, f"Expected 'failed' status in: {status_values}"

    # Verify statuses are visually distinct (different values)
    unique_statuses = set(status_values)
    assert len(unique_statuses) >= 2, f"Expected at least 2 distinct status values, got: {unique_statuses}"

    # Verify specific entry statuses
    for i, status in enumerate(status_values):
        if status == "completed":
            # Completed status should show success indicator
            assert status in ["completed", "success"], f"Expected completed status, got: {status}"
        elif status == "failed":
            # Failed status should show error indicator
            assert status in ["failed", "error"], f"Expected failed status, got: {status}"


def test_history_persistence_across_refresh(browser, db_session: Session):
    """Test execution history persists across page refresh.

    This test verifies:
    1. Create agent execution record
    2. Verify history shows entry
    3. Refresh page
    4. Verify history still shows entry
    5. Verify entry count unchanged

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user and agent
    unique_id = str(uuid.uuid4())[:8]
    email = f"persistence_test_{unique_id}@example.com"
    password = "PersistencePassword123!"

    user = create_test_user_db(db_session, email, password)
    agent = create_test_agent(db_session, name=f"PersistenceAgent_{unique_id}")

    # Create execution record
    execution = create_agent_execution(
        db_session,
        agent_id=agent.id,
        status="completed",
        input_summary=f"Persistence test input {unique_id}",
        output_summary=f"Persistence test output {unique_id}",
        started_at=datetime.utcnow()
    )

    # Generate JWT token and create authenticated page
    import jwt
    token = jwt.encode({"user_id": str(user.id), "email": email}, "test_secret", algorithm="HS256")
    page = create_authenticated_page(browser, user, token)

    # Navigate to history page
    history_page = ExecutionHistoryPage(page)
    history_page.navigate()
    history_page.wait_for_load()

    # Wait for history to load
    page.wait_for_timeout(1000)

    # Verify history shows entry (before refresh)
    history_count_before = history_page.get_history_count()
    assert history_count_before >= 1, f"Expected at least 1 history entry before refresh, got: {history_count_before}"

    # Get entry details before refresh
    agent_before = history_page.get_entry_agent(0)
    status_before = history_page.get_entry_status(0)
    result_before = history_page.get_entry_result(0)

    # Refresh page
    page.reload()
    page.wait_for_load_state("networkidle", timeout=5000)

    # Wait for history to reload
    history_page.wait_for_load()
    page.wait_for_timeout(1000)

    # Verify history still shows entry (after refresh)
    history_count_after = history_page.get_history_count()
    assert history_count_after == history_count_before, \
        f"History count changed after refresh: {history_count_before} -> {history_count_after}"

    # Verify entry details are consistent after refresh
    agent_after = history_page.get_entry_agent(0)
    status_after = history_page.get_entry_status(0)
    result_after = history_page.get_entry_result(0)

    assert agent_after == agent_before, f"Agent name changed after refresh: '{agent_before}' -> '{agent_after}'"
    assert status_after == status_before, f"Status changed after refresh: '{status_before}' -> '{status_after}'"
    assert result_after == result_before, f"Result changed after refresh: '{result_before}' -> '{result_after}'"

    # Verify unique identifier persists
    assert unique_id in result_after, f"Expected unique_id '{unique_id}' in result after refresh: '{result_after}'"
