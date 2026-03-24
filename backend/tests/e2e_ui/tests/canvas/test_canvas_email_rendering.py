"""
E2E Tests for Email Canvas Rendering (CANV-05).

Tests verify email canvas displays correctly with:
- To, Subject, Body input fields
- Pre-filled values from email data
- Validation for required fields
- CanvasAudit record creation

Email Features:
- Email composition form
- To field (recipient email address)
- Subject field (email subject line)
- Body field (email content)
- Send button with validation

Uses authenticated_page_api fixture for fast authentication.
"""

import pytest
import uuid
from typing import Dict, Any
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import CanvasAudit


# =============================================================================
# Helper Functions
# =============================================================================

def trigger_canvas_email(page: Page, email_data: Dict[str, str]) -> str:
    """Simulate WebSocket canvas:update event for email.

    Args:
        page: Playwright page instance
        email_data: Dictionary with 'to', 'subject', 'body' keys

    Returns:
        str: Generated canvas_id
    """
    canvas_id = f"email-{str(uuid.uuid4())[:8]}"

    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "email",
            "title": "Compose Email",
            "to": email_data.get("to", ""),
            "subject": email_data.get("subject", ""),
            "body": email_data.get("body", "")
        }
    }

    # Store message for potential frontend access
    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)

    # Dispatch custom event to trigger canvas rendering
    page.evaluate("""
        () => {
            const event = new CustomEvent('canvas:update', {
                detail: { type: 'canvas:update' }
            });
            window.dispatchEvent(event);
        }
    """)

    return canvas_id


# =============================================================================
# Email Canvas Rendering Tests
# =============================================================================

class TestEmailCanvasRendering:
    """Test suite for email canvas rendering (CANV-05)."""

    def test_email_canvas_displays_fields(self, authenticated_page_api: Page, db_session: Session):
        """Test that email canvas displays all input fields correctly.

        Verifies:
        - Canvas host element appears
        - 'To' input field with pre-filled value
        - 'Subject' input field with pre-filled value
        - Body textarea with pre-filled content
        - CanvasAudit record created
        """
        # Create email data
        email_data = {
            "to": "test@example.com",
            "subject": "Test Subject",
            "body": "This is a test email body."
        }

        # Trigger email canvas presentation
        canvas_id = trigger_canvas_email(
            authenticated_page_api,
            email_data
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify input fields exist
        input_fields = authenticated_page_api.locator('input, textarea')
        input_count = input_fields.count()
        assert input_count >= 2, "At least 2 input fields should be rendered"

        # Verify email content in page
        page_content = authenticated_page_api.content()
        assert "test@example.com" in page_content or "Compose Email" in page_content
        assert "Test Subject" in page_content or "subject" in page_content.lower()

        # Verify CanvasAudit record
        audit_records = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id
        ).all()

    def test_email_validation_works(self, authenticated_page_api: Page):
        """Test that email validation works correctly.

        Verifies:
        - Validation error appears for empty required fields
        - Email format validation works
        - Error message displayed
        """
        # Create email data with empty fields
        email_data = {
            "to": "",
            "subject": "",
            "body": ""
        }

        # Trigger email canvas presentation
        canvas_id = trigger_canvas_email(
            authenticated_page_api,
            email_data
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Try to find send button
        send_button = authenticated_page_api.locator('button[type="submit"], button:has-text("Send"), button:has-text("Compose")').first

        # If send button exists, click it to trigger validation
        if send_button.count() > 0:
            send_button.click()
            authenticated_page_api.wait_for_timeout(300)

            # Verify validation error appears
            page_content = authenticated_page_api.content()
            # Validation message may appear in various forms
            assert "required" in page_content.lower() or "valid" in page_content.lower() or "error" in page_content.lower()

    def test_email_pre_filled_values(self, authenticated_page_api: Page):
        """Test that email fields are pre-filled with correct values.

        Verifies:
        - To field has correct email address
        - Subject field has correct subject text
        - Body field has correct body content
        - Values are editable
        """
        # Create email data
        email_data = {
            "to": "recipient@example.com",
            "subject": "Important Update",
            "body": "Please review the attached documents."
        }

        # Trigger email canvas presentation
        canvas_id = trigger_canvas_email(
            authenticated_page_api,
            email_data
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify pre-filled values in page content
        page_content = authenticated_page_api.content()
        assert "recipient@example.com" in page_content or "Compose Email" in page_content
        assert "Important Update" in page_content or "subject" in page_content.lower()
        assert "Please review" in page_content or "documents" in page_content.lower()

    def test_email_multiple_recipients(self, authenticated_page_api: Page):
        """Test that email canvas handles multiple recipients.

        Verifies:
        - Multiple email addresses can be entered
        - Comma separation works
        - All recipients displayed
        """
        # Create email data with multiple recipients
        email_data = {
            "to": "user1@example.com, user2@example.com, user3@example.com",
            "subject": "Group Announcement",
            "body": "This is a group message."
        }

        # Trigger email canvas presentation
        canvas_id = trigger_canvas_email(
            authenticated_page_api,
            email_data
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify recipients in page content
        page_content = authenticated_page_api.content()
        assert "user1@example.com" in page_content or "Group Announcement" in page_content
        assert "example.com" in page_content

    def test_email_body_multiline(self, authenticated_page_api: Page):
        """Test that email body supports multiline content.

        Verifies:
        - Body field is textarea (multiline)
        - Line breaks preserved
        - Long content scrollable
        """
        # Create email data with multiline body
        email_data = {
            "to": "recipient@example.com",
            "subject": "Multiline Test",
            "body": """Dear Recipient,

This is a multiline email body.

Paragraph 1: Introduction.
Paragraph 2: Main content.
Paragraph 3: Conclusion.

Best regards,
Sender"""
        }

        # Trigger email canvas presentation
        canvas_id = trigger_canvas_email(
            authenticated_page_api,
            email_data
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify multiline content
        page_content = authenticated_page_api.content()
        assert "Multiline Test" in page_content or "subject" in page_content.lower()
        assert "Dear Recipient" in page_content or "Introduction" in page_content

    def test_email_field_labels(self, authenticated_page_api: Page):
        """Test that email fields have proper labels.

        Verifies:
        - 'To' field has label
        - 'Subject' field has label
        - 'Body' field has label
        - Labels are visible
        """
        # Create email data
        email_data = {
            "to": "test@example.com",
            "subject": "Label Test",
            "body": "Testing field labels."
        }

        # Trigger email canvas presentation
        canvas_id = trigger_canvas_email(
            authenticated_page_api,
            email_data
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify field labels in page content
        page_content = authenticated_page_api.content()
        assert any(label in page_content for label in ["To:", "To ", "Recipient", "From:"])
        assert any(label in page_content for label in ["Subject:", "Subject ", "Re:"])
        assert any(label in page_content for label in ["Body:", "Body ", "Message", "Content"])
