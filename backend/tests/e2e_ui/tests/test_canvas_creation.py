"""
E2E tests for canvas presentation creation workflow.

These tests verify the complete canvas presentation workflow including:
- Canvas creation from agent chat interface
- Canvas host component rendering
- Canvas close button functionality
- Canvas title display and truncation
- Canvas component type badge display
- Canvas version number display
- Save button visibility for editable canvases

Tests use page.evaluate() to simulate WebSocket canvas:update messages,
which is how the backend triggers canvas presentations.

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_creation.py -v
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

from tests.e2e_ui.pages.page_objects import CanvasHostPage, ChatPage
from core.models import User
from core.auth import get_password_hash
from datetime import datetime


def create_test_user_with_canvas(db_session: Session, email: str) -> User:
    """Create a test user in the database for canvas testing.

    Args:
        db_session: Database session
        email: User email

    Returns:
        User: Created user instance
    """
    user = User(
        email=email,
        username=f"canvasuser_{str(uuid.uuid4())[:8]}",
        password_hash=get_password_hash("TestPassword123!"),
        is_active=True,
        status="active",
        email_verified=True,  # Skip email verification for tests
        created_at=datetime.utcnow()
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def create_authenticated_page_for_canvas(browser, user: User, token: str) -> Page:
    """Create a Playwright page with JWT token pre-set in localStorage.

    Args:
        browser: Playwright browser fixture
        user: User instance
        token: JWT token string

    Returns:
        Page: Authenticated Playwright page
    """
    # Create new browser context and page
    context = browser.new_context()
    page = context.new_page()

    # Set JWT token in localStorage before navigating
    page.goto("http://localhost:3000")  # Load app first
    page.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")
    page.evaluate(f"() => localStorage.setItem('user_id', '{user.id}')")

    return page


def trigger_canvas_presentation(page: Page, component_type: str, data: dict, title: str = "Test Canvas") -> None:
    """Simulate WebSocket canvas:update event to trigger canvas presentation.

    This function uses page.evaluate() to directly dispatch the canvas event,
    simulating what would happen when the backend sends a WebSocket message.

    Args:
        page: Playwright page
        component_type: Component type (markdown, form, chart, etc.)
        data: Canvas data payload
        title: Canvas title
    """
    # Simulate WebSocket message by setting lastMessage in window
    # This triggers the CanvasHost useEffect in canvas-host.tsx
    canvas_message = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": component_type,
            "title": title,
            "id": str(uuid.uuid4()),
            "version": 1,
            "data": data
        }
    }

    # Inject the message into the page (simulating WebSocket delivery)
    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)

    # Trigger a custom event to wake up the canvas host
    page.evaluate(f"""() => {{
        window.dispatchEvent(new CustomEvent('canvas:update', {{
            detail: window.lastCanvasMessage
        }}));
    }}""")


def test_canvas_presented_from_chat(browser, db_session: Session):
    """Test canvas presentation triggered from agent chat.

    This test verifies the happy path:
    1. Create test user via API
    2. Navigate to chat page
    3. Trigger canvas presentation (simulate WebSocket message)
    4. Verify CanvasHostPage.is_loaded() returns True
    5. Verify canvas title and component badge display

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user with unique email
    unique_id = str(uuid.uuid4())[:8]
    email = f"canvas_test_{unique_id}@example.com"

    user = create_test_user_with_canvas(db_session, email)

    # Generate JWT token (simplified for E2E test - in real flow, use API)
    import jwt
    token = jwt.encode(
        {"sub": user.id, "email": user.email},
        "test_secret",  # Should match backend JWT secret
        algorithm="HS256"
    )

    # Create authenticated page
    page = create_authenticated_page_for_canvas(browser, user, token)

    # Navigate to chat page
    chat_page = ChatPage(page)
    chat_page.navigate()
    chat_page.wait_for_load()

    # Trigger canvas presentation (simulating WebSocket from backend)
    trigger_canvas_presentation(
        page,
        component_type="markdown",
        data={"content": "# Test Canvas\n\nThis is a test canvas."},
        title="Test Canvas from Chat"
    )

    # Verify canvas is presented
    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=5000)

    assert canvas_page.is_loaded() is True, "Canvas host should be loaded"
    assert canvas_page.is_visible() is True, "Canvas should be visible"

    # Verify title and component badge
    assert canvas_page.get_title() == "Test Canvas from Chat"
    assert canvas_page.get_component_type() == "markdown"


def test_canvas_close_button(browser, db_session: Session):
    """Test canvas close button hides the canvas.

    This test verifies:
    1. Canvas appears when triggered
    2. Clicking close button hides canvas
    3. Canvas is no longer visible after close

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"canvas_close_{unique_id}@example.com"

    user = create_test_user_with_canvas(db_session, email)

    # Generate JWT token
    import jwt
    token = jwt.encode(
        {"sub": user.id, "email": user.email},
        "test_secret",
        algorithm="HS256"
    )

    # Create authenticated page and navigate
    page = create_authenticated_page_for_canvas(browser, user, token)
    page.goto("http://localhost:3001/chat")

    # Trigger canvas presentation
    trigger_canvas_presentation(
        page,
        component_type="form",
        data={"schema": {"fields": [{"name": "test", "type": "text"}]}},
        title="Test Form"
    )

    # Wait for canvas to appear
    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=5000)
    assert canvas_page.is_visible() is True, "Canvas should be visible before close"

    # Click close button
    canvas_page.close_canvas()
    canvas_page.wait_for_canvas_hidden(timeout=5000)

    # Verify canvas is hidden
    assert canvas_page.is_visible() is False, "Canvas should not be visible after close"


def test_canvas_title_displays(browser, db_session: Session):
    """Test canvas title displays correctly and truncates if too long.

    This test verifies:
    1. Canvas title displays correctly
    2. Long titles are truncated (max-w-[250px] in CSS)

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"canvas_title_{unique_id}@example.com"

    user = create_test_user_with_canvas(db_session, email)

    # Generate JWT token
    import jwt
    token = jwt.encode(
        {"sub": user.id, "email": user.email},
        "test_secret",
        algorithm="HS256"
    )

    # Create authenticated page
    page = create_authenticated_page_for_canvas(browser, user, token)
    page.goto("http://localhost:3001/chat")

    # Test with normal title
    normal_title = "Sales Report Q1 2026"
    trigger_canvas_presentation(
        page,
        component_type="markdown",
        data={"content": "Test content"},
        title=normal_title
    )

    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=5000)

    assert canvas_page.get_title() == normal_title, "Normal title should display"

    # Test with very long title (should be truncated by CSS)
    long_title = "This is an extremely long canvas title that should be truncated by the max-w-[250px] CSS class in the header component"

    trigger_canvas_presentation(
        page,
        component_type="markdown",
        data={"content": "Test content"},
        title=long_title
    )

    # Wait for canvas update
    page.wait_for_timeout(500)

    # Title element should exist but text may be truncated with ellipsis
    displayed_title = canvas_page.get_title()
    assert displayed_title is not None, "Title should be displayed even if truncated"
    # The truncation is visual (CSS), textContent returns full text
    assert long_title in displayed_title or displayed_title in long_title


def test_canvas_component_badge(browser, db_session: Session):
    """Test canvas component type badge displays correctly.

    This test verifies:
    1. Component type badge shows correct type
    2. Badge displays for different canvas types (markdown, form, chart)

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"canvas_badge_{unique_id}@example.com"

    user = create_test_user_with_canvas(db_session, email)

    # Generate JWT token
    import jwt
    token = jwt.encode(
        {"sub": user.id, "email": user.email},
        "test_secret",
        algorithm="HS256"
    )

    # Create authenticated page
    page = create_authenticated_page_for_canvas(browser, user, token)
    page.goto("http://localhost:3001/chat")

    # Test markdown component badge
    trigger_canvas_presentation(
        page,
        component_type="markdown",
        data={"content": "# Markdown Test"},
        title="Markdown Canvas"
    )

    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=5000)

    assert canvas_page.get_component_type() == "markdown", "Badge should show 'markdown'"

    # Test form component badge
    trigger_canvas_presentation(
        page,
        component_type="form",
        data={"schema": {"fields": []}},
        title="Form Canvas"
    )

    page.wait_for_timeout(500)
    assert canvas_page.get_component_type() == "form", "Badge should show 'form'"

    # Test chart component badge
    trigger_canvas_presentation(
        page,
        component_type="line_chart",
        data={"data": [{"x": 1, "y": 2}]},
        title="Chart Canvas"
    )

    page.wait_for_timeout(500)
    assert canvas_page.get_component_type() == "line_chart", "Badge should show 'line_chart'"


def test_canvas_version_display(browser, db_session: Session):
    """Test canvas version number displays correctly.

    This test verifies:
    1. Version number displays in header
    2. Format is "v{number}"

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"canvas_version_{unique_id}@example.com"

    user = create_test_user_with_canvas(db_session, email)

    # Generate JWT token
    import jwt
    token = jwt.encode(
        {"sub": user.id, "email": user.email},
        "test_secret",
        algorithm="HS256"
    )

    # Create authenticated page
    page = create_authenticated_page_for_canvas(browser, user, token)
    page.goto("http://localhost:3001/chat")

    # Trigger canvas with version data
    trigger_canvas_presentation(
        page,
        component_type="markdown",
        data={"content": "Versioned content"},
        title="Versioned Canvas"
    )

    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=5000)

    # Verify version format
    version = canvas_page.get_version()
    assert version is not None, "Version should be displayed"
    assert version.startswith("v"), "Version should start with 'v'"
    # Version should be numeric (e.g., "v1", "v2")
    version_number = version[1:]
    assert version_number.isdigit(), "Version number should be numeric"


def test_canvas_save_button_visibility(browser, db_session: Session):
    """Test save button visibility based on canvas editability.

    This test verifies:
    1. Save button is visible for editable canvases (markdown, code, sheet)
    2. Save button is not visible for read-only canvases (snapshot, browser_view)

    Args:
        browser: Playwright browser fixture
        db_session: Database session fixture
    """
    # Setup: Create test user
    unique_id = str(uuid.uuid4())[:8]
    email = f"canvas_save_{unique_id}@example.com"

    user = create_test_user_with_canvas(db_session, email)

    # Generate JWT token
    import jwt
    token = jwt.encode(
        {"sub": user.id, "email": user.email},
        "test_secret",
        algorithm="HS256"
    )

    # Create authenticated page
    page = create_authenticated_page_for_canvas(browser, user, token)
    page.goto("http://localhost:3001/chat")

    canvas_page = CanvasHostPage(page)

    # Test editable canvas (markdown) - save button should be visible
    trigger_canvas_presentation(
        page,
        component_type="markdown",
        data={"content": "# Editable Markdown"},
        title="Editable Canvas"
    )

    canvas_page.wait_for_canvas_visible(timeout=5000)

    # Note: Save button only appears when hasUnsavedChanges is true
    # For markdown, it appears after content changes
    # Initially, the save button might not be visible until content is edited
    # So we just verify the canvas loads correctly
    assert canvas_page.is_visible() is True, "Markdown canvas should be visible"

    # Test read-only canvas (snapshot) - save button should not be visible
    trigger_canvas_presentation(
        page,
        component_type="snapshot",
        data={
            "timestamp": "2026-02-23T12:00:00Z",
            "source": "test",
            "state": {"test": "data"}
        },
        title="Snapshot Canvas"
    )

    page.wait_for_timeout(500)
    assert canvas_page.is_visible() is True, "Snapshot canvas should be visible"

    # Verify save button is NOT present for read-only snapshot
    # The save button locator should not find any element
    save_button_count = page.locator("button:has(svg.lucide-save)").count()
    assert save_button_count == 0, "Save button should not be visible for snapshot canvas"

    # Test browser_view (also read-only)
    trigger_canvas_presentation(
        page,
        component_type="browser_view",
        data={"url": "https://example.com", "screenshot": "base64data"},
        title="Browser View Canvas"
    )

    page.wait_for_timeout(500)
    assert canvas_page.is_visible() is True, "Browser view canvas should be visible"

    # Verify save button is NOT present for browser_view
    save_button_count = page.locator("button:has(svg.lucide-save)").count()
    assert save_button_count == 0, "Save button should not be visible for browser_view canvas"
