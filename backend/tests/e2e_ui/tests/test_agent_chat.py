"""
E2E tests for agent chat message sending functionality.

These tests verify the complete chat message workflow including:
- Sending chat messages through the interface
- Message display in chat history
- Empty message handling
- Long message truncation/scrolling
- Message persistence after page refresh

Run with: pytest backend/tests/e2e_ui/tests/test_agent_chat.py -v
"""

import pytest
import uuid
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
from typing import Tuple

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import ChatPage
from tests.e2e_ui.utils.api_setup import APIClient, authenticate_user
from core.models import User
from core.auth import get_password_hash
from datetime import datetime


def create_test_user(db_session: Session, email: str, password: str) -> User:
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
        hashed_password=get_password_hash(password),
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def create_authenticated_page(browser, user: User, password: str) -> Page:
    """Create a Playwright page with a real JWT token pre-set.

    The token is minted by the LIVE backend via the login API (the backend's
    JWT secret is auto-generated at boot, so tokens forged in this process are
    rejected). The auth_token COOKIE is required too — the frontend middleware
    (middleware.ts) redirects to /login when only localStorage is set.

    Args:
        browser: Playwright browser fixture
        user: User instance
        password: Plain-text password used to log in via the API

    Returns:
        Page: Authenticated Playwright page
    """
    # Login through the live backend so the token is signed with its secret.
    api = APIClient(base_url=os.getenv("E2E_API_URL", "http://localhost:8001"))
    auth_resp = authenticate_user(api, email=user.email, password=password)
    token = auth_resp["access_token"]

    # Create new browser context and page
    context = browser.new_context()
    page = context.new_page()

    # Pre-seed the auth_token cookie so the frontend middleware passes.
    context.add_cookies([
        {"name": "auth_token", "value": token, "url": "http://localhost:3001"},
    ])

    # Set JWT token in localStorage before navigating
    page.goto("http://localhost:3001")  # Load app first
    page.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")
    page.evaluate(f"() => localStorage.setItem('user_id', '{user.id}')")

    return page


def test_send_chat_message(browser, db_session: Session):
    """Test sending a chat message and verifying it appears in history.

    This test verifies the happy path:
    1. Create test user via API
    2. Authenticate via the live backend login endpoint
    3. Navigate to chat page using ChatPage
    4. Type message "Hello agent" in chat input
    5. Click send button
    6. Verify message appears in chat history
    7. Verify input clears after send

    Note: on a stack without a valid LLM provider key the assistant cannot
    reply, so the user-message assertions are the ground truth here; the
    assistant-response assertion only applies when a response actually
    arrives.
    """
    # Setup: Create test user with unique email
    unique_id = str(uuid.uuid4())[:8]
    email = f"chat_test_{unique_id}@example.com"
    password = "ChatPassword123!"

    user = create_test_user(db_session, email, password)
    assert user.id is not None

    # Create authenticated page (real token via backend login API)
    page = create_authenticated_page(browser, user, password)

    # Navigate to chat page
    chat_page = ChatPage(page)
    chat_page.navigate()

    # Wait for page to load
    page.wait_for_timeout(500)

    # Type and send message
    test_message = f"Hello agent {unique_id}"
    chat_page.send_message(test_message)

    # Wait for the user message to render (optimistic append — no LLM needed)
    page.wait_for_timeout(1000)

    # Verify the user message appears in the message list
    user_messages = chat_page.user_message.all()
    user_texts = [m.text_content() for m in user_messages]
    assert any(test_message in t for t in user_texts), \
        f"Expected '{test_message}' in a user message, got: {user_texts}"

    # Verify message count increased
    message_count = chat_page.get_message_count()
    assert message_count >= 1, f"Expected at least 1 message, got: {message_count}"

    # Verify input field cleared after send
    input_value = chat_page.chat_input.input_value()
    assert input_value == "" or input_value.isspace(), f"Expected empty input after send, got: '{input_value}'"


def test_message_appears_in_history(browser, db_session: Session):
    """Test sending multiple messages and verifying all appear in history.

    This test verifies:
    1. Create test user
    2. Send multiple messages (3 messages)
    3. Verify all messages appear in history
    4. Verify message count matches

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"chat_history_{unique_id}@example.com"
    password = "ChatPassword123!"

    user = create_test_user(db_session, email, password)

    # Create authenticated page (real token via backend login API)
    page = create_authenticated_page(browser, user, password)

    # Navigate to chat page
    chat_page = ChatPage(page)
    chat_page.navigate()
    page.wait_for_timeout(500)

    # Send multiple messages
    messages = [
        f"First message {unique_id}",
        f"Second message {unique_id}",
        f"Third message {unique_id}"
    ]

    for msg in messages:
        chat_page.send_message(msg)
        page.wait_for_timeout(500)  # Wait between messages

    # Verify all messages appear in history (user bubbles render optimistically)
    all_messages = chat_page.get_all_messages()
    
    # Filter for our test messages (may include existing messages)
    our_messages = [m for m in all_messages if unique_id in m]
    
    assert len(our_messages) == 3, f"Expected 3 messages with unique_id, got: {len(our_messages)}"

    # Verify message count
    message_count = chat_page.get_message_count()
    assert message_count >= 3, f"Expected at least 3 messages, got: {message_count}"


def test_empty_message_not_sent(browser, db_session: Session):
    """Test that clicking send without typing doesn't send a message.

    This test verifies:
    1. Navigate to chat page
    2. Click send without typing
    3. Verify send button disabled or no message sent
    4. Verify message count unchanged

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"chat_empty_{unique_id}@example.com"
    password = "ChatPassword123!"

    user = create_test_user(db_session, email, password)

    # Create authenticated page (real token via backend login API)
    page = create_authenticated_page(browser, user, password)

    # Navigate to chat page
    chat_page = ChatPage(page)
    chat_page.navigate()
    page.wait_for_timeout(500)

    # Get initial message count
    initial_count = chat_page.get_message_count()

    # Try to send empty message (just whitespace)
    chat_page.send_message("   ")
    page.wait_for_timeout(500)

    # Verify message count unchanged
    final_count = chat_page.get_message_count()
    assert initial_count == final_count, f"Message count changed: {initial_count} -> {final_count}"


def test_long_message_truncates_or_scrolls(browser, db_session: Session):
    """Test that long messages display properly and input clears after send.

    This test verifies:
    1. Send long message (500+ chars)
    2. Verify message displays properly
    3. Verify input field clears after send

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"chat_long_{unique_id}@example.com"
    password = "ChatPassword123!"

    user = create_test_user(db_session, email, password)

    # Create authenticated page (real token via backend login API)
    page = create_authenticated_page(browser, user, password)

    # Navigate to chat page
    chat_page = ChatPage(page)
    chat_page.navigate()
    page.wait_for_timeout(500)

    # Create long message (500+ characters)
    long_message = f"This is a very long message from test {unique_id}. " * 25  # ~600 characters

    # Send long message
    chat_page.send_message(long_message)
    page.wait_for_timeout(1000)

    # Verify the user message appears in history (at least partially)
    user_messages = chat_page.user_message.all()
    user_texts = [m.text_content() for m in user_messages]
    assert any(unique_id in t for t in user_texts), \
        f"Expected unique_id '{unique_id}' in a user message, got: {user_texts}"

    # Verify input field cleared (check if input value is empty)
    input_value = chat_page.chat_input.input_value()
    assert input_value == "" or input_value.isspace(), f"Expected empty input after send, got: '{input_value}'"


def test_message_persistence_after_refresh(browser, db_session: Session):
    """Test that messages persist after page refresh.

    This test verifies:
    1. Send message
    2. Refresh page
    3. Verify message still in history
    4. Verify session_id persists

    Note: on a keyless stack the backend persists the user message to the
    session before the (missing) LLM call, and the frontend restores the last
    session id from localStorage on reload, so the user message survives the
    refresh even without an assistant reply.
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"chat_persist_{unique_id}@example.com"
    password = "ChatPassword123!"

    user = create_test_user(db_session, email, password)

    # Create authenticated page (real token via backend login API)
    page = create_authenticated_page(browser, user, password)

    # Navigate to chat page
    chat_page = ChatPage(page)
    chat_page.navigate()
    page.wait_for_timeout(500)

    # Send message
    test_message = f"Persistent message {unique_id}"
    chat_page.send_message(test_message)
    page.wait_for_timeout(1000)

    # Verify message sent
    message_count_before = chat_page.get_message_count()
    assert message_count_before >= 1, "Message not sent before refresh"

    # Refresh page
    page.reload()
    page.wait_for_timeout(1500)

    # Re-initialize ChatPage after refresh
    chat_page_after = ChatPage(page)

    # Verify message still in history
    all_messages = chat_page_after.get_all_messages()
    our_messages = [m for m in all_messages if unique_id in m]
    
    assert len(our_messages) >= 1, f"Expected at least 1 persistent message with unique_id, got: {len(our_messages)}"

    # Verify session persisted by checking message count
    message_count_after = chat_page_after.get_message_count()
    assert message_count_after >= message_count_before, f"Message count decreased after refresh: {message_count_before} -> {message_count_after}"
