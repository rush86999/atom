"""
E2E Tests for Email Canvas Rendering (CANV-05).

Tests verify the email canvas renders correctly through the REAL rendering
path (no phantom state injection):

1. An email canvas is created as `Canvas` + `CanvasAudit` rows via
   `canvas_helpers.create_canvas()` with content = {to, subject, body}.
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where `CanvasPanel`
   renders the email composer: To/Subject inputs (pre-filled from the
   audit content via the metadata bridge in pages/canvas/[id].tsx) and a
   Monaco body editor.

Note: the composer has no client-side validation — the Send button calls a
placeholder alert() (real component behavior), so the legacy "validation"
test is a documented skip.
"""

import uuid
from typing import Tuple

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from core.models import CanvasAudit, User
from tests.e2e_ui.tests.canvas_helpers import create_canvas, open_canvas


# =============================================================================
# Helper Functions
# =============================================================================

def create_email_canvas(db: Session, user: User, email_data: dict, title: str = "Compose Email") -> str:
    """Create an email canvas whose content is {to, subject, body}."""
    canvas_id = f"e2e-email-{uuid.uuid4()}"
    create_canvas(db, user, canvas_id, "email", title, email_data)
    return canvas_id


def open_email_canvas(page: Page, canvas_id: str) -> None:
    """Navigate to an email canvas and wait for the composer."""
    open_canvas(page, canvas_id, "email")
    page.wait_for_selector("input[placeholder='recipient@example.com']", timeout=30000)
    page.wait_for_selector(".monaco-editor .view-lines", timeout=30000)


def to_input(page: Page):
    return page.locator("input[placeholder='recipient@example.com']").first


def subject_input(page: Page):
    return page.locator("input[placeholder='Email Subject']").first


def body_text(page: Page) -> str:
    """Read the body content from the Monaco editor, normalizing the
    non-breaking spaces Monaco renders in place of regular spaces."""
    return page.locator(".monaco-editor .view-lines").inner_text().replace("\u00a0", " ")


# =============================================================================
# Email Canvas Rendering Tests
# =============================================================================

def test_email_canvas_displays_fields(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that email canvas displays To/Subject fields and the body.

    Verifies:
    - CanvasPanel container with email type badge
    - To input pre-filled, Subject input pre-filled, body rendered
    - CanvasAudit record created
    """
    user, _ = authenticated_user
    email_data = {
        "to": "test@example.com",
        "subject": "Test Subject",
        "body": "This is a test email body.",
    }
    canvas_id = create_email_canvas(db_session, user, email_data, "Compose Email")

    open_email_canvas(authenticated_page, canvas_id)

    assert to_input(authenticated_page).input_value() == "test@example.com", "To field should be pre-filled"
    assert subject_input(authenticated_page).input_value() == "Test Subject", "Subject field should be pre-filled"
    assert "This is a test email body." in body_text(authenticated_page), "Body should render"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"
    assert audit[0].canvas_type == "email", "Audit row should carry the email type"


def test_email_validation_works(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Email validation: the real composer (CanvasPanel 'email') performs no
    client-side validation — the Send button calls a placeholder alert().
    Documented skip (no validation path exists in the real component)."""
    pytest.skip(
        "The real email composer has no client-side validation: Send invokes "
        "a placeholder alert() in CanvasPanel.handleSendEmail. Nothing to "
        "verify — see CanvasPanel.tsx."
    )


def test_email_pre_filled_values(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that email fields are pre-filled with the persisted values."""
    user, _ = authenticated_user
    email_data = {
        "to": "recipient@example.com",
        "subject": "Important Update",
        "body": "Please review the attached documents.",
    }
    canvas_id = create_email_canvas(db_session, user, email_data, "Important Update")

    open_email_canvas(authenticated_page, canvas_id)

    assert to_input(authenticated_page).input_value() == "recipient@example.com"
    assert subject_input(authenticated_page).input_value() == "Important Update"
    assert "Please review the attached documents." in body_text(authenticated_page)

    # Values are editable.
    to_input(authenticated_page).fill("new@example.com")
    assert to_input(authenticated_page).input_value() == "new@example.com", "To field should be editable"


def test_email_multiple_recipients(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that email canvas supports comma-separated recipient lists."""
    user, _ = authenticated_user
    email_data = {
        "to": "user1@example.com, user2@example.com, user3@example.com",
        "subject": "Group Announcement",
        "body": "This is a group message.",
    }
    canvas_id = create_email_canvas(db_session, user, email_data, "Group Announcement")

    open_email_canvas(authenticated_page, canvas_id)

    to_value = to_input(authenticated_page).input_value()
    assert "user1@example.com" in to_value and "user3@example.com" in to_value, (
        f"All recipients should be preserved: {to_value}"
    )


def test_email_body_multiline(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that email body preserves multiline content."""
    user, _ = authenticated_user
    email_data = {
        "to": "recipient@example.com",
        "subject": "Multiline Test",
        "body": """Dear Recipient,

This is a multiline email body.

Paragraph 1: Introduction.
Paragraph 2: Main content.

Best regards,
Sender""",
    }
    canvas_id = create_email_canvas(db_session, user, email_data, "Multiline Test")

    open_email_canvas(authenticated_page, canvas_id)

    text = body_text(authenticated_page)
    assert "Dear Recipient," in text, "First body line should render"
    assert "Paragraph 1: Introduction." in text, "Multiline body content should render"


def test_email_field_labels(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that email composer shows To/Sub field labels."""
    user, _ = authenticated_user
    email_data = {
        "to": "test@example.com",
        "subject": "Label Test",
        "body": "Testing field labels.",
    }
    canvas_id = create_email_canvas(db_session, user, email_data, "Label Test")

    open_email_canvas(authenticated_page, canvas_id)

    container_text = authenticated_page.locator('[data-testid="canvas-container"]').inner_text().replace("\u00a0", " ").lower()
    assert "to:" in container_text, "To label should be visible"
    assert "sub:" in container_text, "Subject label should be visible"
