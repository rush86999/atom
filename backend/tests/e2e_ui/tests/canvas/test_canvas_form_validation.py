"""
Form Canvas Validation and Submission E2E Tests.

Tests form canvas validation (required fields, email format), submission with
loading states, and CanvasAudit record creation.

Coverage: CANV-03 (form validation), CANV-08 (form submission)
"""

import json
import uuid
from datetime import datetime
import pytest
from playwright.sync_api import Page
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import CanvasAudit


# ============================================================================
# Helper Functions
# ============================================================================

def trigger_form_canvas(page: Page, schema: dict, title: str = "Test Form") -> str:
    """Simulate WebSocket canvas:update event for form canvas.

    Args:
        page: Playwright page object
        schema: Form schema dict
        title: Form title

    Returns:
        canvas_id: Generated canvas ID
    """
    canvas_id = schema.get("canvas_id", f"form-{str(uuid.uuid4())[:8]}")

    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "form",
            "title": title,
            "schema": schema
        }
    }

    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)
    page.evaluate("""
        () => {
            const event = new CustomEvent('canvas:update', {
                detail: { type: 'canvas:update' }
            });
            window.dispatchEvent(event);
        }
    """)

    return canvas_id


def create_test_form_schema() -> dict:
    """Create test form schema with various field types.

    Returns:
        Form schema dictionary
    """
    return {
        "canvas_id": f"form-{str(uuid.uuid4())[:8]}",
        "fields": [
            {
                "name": "name",
                "type": "text",
                "label": "Full Name",
                "required": True,
                "validation": {"min_length": 2}
            },
            {
                "name": "email",
                "type": "email",
                "label": "Email Address",
                "required": True,
                "validation": {"format": "email"}
            },
            {
                "name": "message",
                "type": "textarea",
                "label": "Message",
                "required": False
            }
        ]
    }


def mock_canvas_submit_api(page: Page, response_data: dict, status_code: int = 200) -> None:
    """Mock the /api/canvas/submit endpoint.

    Args:
        page: Playwright page object
        response_data: Response data to return
        status_code: HTTP status code
    """
    def handle_route(route):
        route.fulfill(
            status=status_code,
            content_type="application/json",
            body=json.dumps({
                "success": status_code == 200,
                "data": response_data,
                "message": "Form submitted successfully" if status_code == 200 else "Submission failed"
            })
        )

    page.route("http://localhost:8001/api/canvas/submit", handle_route)


# ============================================================================
# Tests
# ============================================================================

class TestFormCanvasValidation:
    """Test form canvas validation behavior (CANV-03)."""

    def test_required_field_validation(self, authenticated_page_api: Page, db_session: Session):
        """Test required field validation shows errors.

        Verify form rejects submission without required fields and displays error messages.
        """
        # Create form schema with required fields
        schema = create_test_form_schema()
        canvas_id = trigger_form_canvas(authenticated_page_api, schema, "Required Field Test")

        # Wait for form to render
        authenticated_page_api.wait_for_selector('[data-testid^="canvas-form-field-"]', timeout=5000)

        # Verify form rendered with 3 fields
        field_count = authenticated_page_api.locator('[data-testid^="canvas-form-field-"]').count()
        assert field_count == 3, f"Expected 3 form fields, got {field_count}"

        # Submit form without filling required fields
        submit_button = authenticated_page_api.locator('[data-testid="canvas-form-submit"]')
        if submit_button.count() > 0:
            submit_button.click()

        # Verify validation errors appear
        authenticated_page_api.wait_for_selector('[data-testid^="canvas-form-error-"]', timeout=3000)
        error_count = authenticated_page_api.locator('[data-testid^="canvas-form-error-"]').count()
        assert error_count >= 2, f"Expected at least 2 validation errors, got {error_count}"

        # Verify error messages contain "required" or "field is required"
        error_texts = [
            authenticated_page_api.locator('[data-testid^="canvas-form-error-"]').nth(i).text_content()
            for i in range(error_count)
        ]
        error_text_combined = " ".join(error_texts).lower()
        assert "required" in error_text_combined or "field is required" in error_text_combined, \
            f"Error messages should mention 'required': {error_texts}"

        # Verify CanvasAudit NOT created (submission rejected)
        audit_records = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.action == "submit"
        ).all()
        assert len(audit_records) == 0, "CanvasAudit should not be created for failed validation"

    def test_email_format_validation(self, authenticated_page_api: Page):
        """Test email format validation.

        Verify form validates email format and shows inline errors.
        """
        # Create form with email field
        schema = {
            "canvas_id": f"form-{str(uuid.uuid4())[:8]}",
            "fields": [
                {
                    "name": "email",
                    "type": "email",
                    "label": "Email Address",
                    "required": True,
                    "validation": {"format": "email"}
                }
            ]
        }
        canvas_id = trigger_form_canvas(authenticated_page_api, schema, "Email Validation Test")

        # Wait for form to render
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-field-email"]', timeout=5000)

        # Fill email with invalid format
        email_field = authenticated_page_api.locator('[data-testid="canvas-form-field-email"]')
        email_field.fill("not-an-email")

        # Trigger validation (blur or submit attempt)
        submit_button = authenticated_page_api.locator('[data-testid="canvas-form-submit"]')
        if submit_button.count() > 0:
            submit_button.click()

        # Verify email field shows inline error
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-error-email"]', timeout=3000)
        error_element = authenticated_page_api.locator('[data-testid="canvas-form-error-email"]')
        assert error_element.is_visible(), "Email error should be visible"

        # Verify error message about invalid email format
        error_text = error_element.text_content().lower()
        assert any(keyword in error_text for keyword in ["invalid", "email", "format"]), \
            f"Error should mention invalid email format: {error_text}"

        # Fill with valid email
        email_field.fill("test@example.com")

        # Verify error disappears (may require re-triggering validation)
        if error_element.is_visible():
            authenticated_page_api.wait_for_selector('[data-testid="canvas-form-error-email"]', state="hidden", timeout=2000)

    def test_successful_form_submission(self, authenticated_page_api: Page, db_session: Session):
        """Test successful form submission with loading states.

        Verify form submits successfully, shows loading state, displays success message,
        and creates CanvasAudit record.
        """
        # Create form schema
        schema = create_test_form_schema()
        canvas_id = trigger_form_canvas(authenticated_page_api, schema, "Successful Submission Test")

        # Wait for form to render
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-field-name"]', timeout=5000)

        # Fill all fields
        authenticated_page_api.locator('[data-testid="canvas-form-field-name"]').fill("John Doe")
        authenticated_page_api.locator('[data-testid="canvas-form-field-email"]').fill("john@example.com")
        authenticated_page_api.locator('[data-testid="canvas-form-field-message"]').fill("Test message")

        # Mock successful submit response
        mock_canvas_submit_api(authenticated_page_api, {"submission_id": str(uuid.uuid4())}, 200)

        # Submit form
        submit_button = authenticated_page_api.locator('[data-testid="canvas-form-submit"]')
        submit_button.click()

        # Verify loading indicator appears
        loading_indicator = authenticated_page_api.locator('[data-testid="canvas-form-submitting"]')
        if loading_indicator.count() > 0:
            assert loading_indicator.is_visible(), "Loading indicator should be visible during submission"

        # Wait for submission response
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-success"]', timeout=5000)

        # Verify success message appears
        success_element = authenticated_page_api.locator('[data-testid="canvas-form-success"]')
        assert success_element.is_visible(), "Success message should be visible"

        # Verify CanvasAudit record created in database
        audit_records = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.action == "submit"
        ).all()
        assert len(audit_records) > 0, "CanvasAudit record should be created for successful submission"

        # Verify submission data stored in metadata
        audit_record = audit_records[0]
        assert audit_record.audit_metadata is not None, "Audit metadata should exist"
        assert "submission" in str(audit_record.audit_metadata).lower() or "form" in str(audit_record.audit_metadata).lower(), \
            "Metadata should contain submission data"

    def test_form_submission_with_api_mocking(self, authenticated_page_api: Page):
        """Test form submission with mocked API response.

        Verify UI handles different API responses correctly (success/error).
        """
        # Create form schema
        schema = create_test_form_schema()
        canvas_id = trigger_form_canvas(authenticated_page_api, schema, "API Mocking Test")

        # Wait for form to render
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-field-name"]', timeout=5000)

        # Fill form fields
        authenticated_page_api.locator('[data-testid="canvas-form-field-name"]').fill("Test User")
        authenticated_page_api.locator('[data-testid="canvas-form-field-email"]').fill("test@example.com")

        # Mock error response
        mock_canvas_submit_api(authenticated_page_api, {"error": "Validation failed"}, 400)

        # Submit form
        submit_button = authenticated_page_api.locator('[data-testid="canvas-form-submit"]')
        submit_button.click()

        # Verify error message appears
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-error"]', timeout=5000)
        error_element = authenticated_page_api.locator('[data-testid="canvas-form-error"]')
        assert error_element.is_visible(), "Error message should be visible for failed submission"

        # Clean up mock
        authenticated_page_api.unroute("http://localhost:8001/api/canvas/submit")

    def test_multi_step_form_validation(self, authenticated_page_api: Page):
        """Test multi-step form validation.

        Verify form prevents step navigation without completing required fields.
        """
        # Create multi-step form
        schema = {
            "canvas_id": f"form-{str(uuid.uuid4())[:8]}",
            "steps": [
                {
                    "step_id": "personal_info",
                    "title": "Personal Information",
                    "fields": [
                        {
                            "name": "first_name",
                            "type": "text",
                            "label": "First Name",
                            "required": True
                        },
                        {
                            "name": "last_name",
                            "type": "text",
                            "label": "Last Name",
                            "required": True
                        }
                    ]
                },
                {
                    "step_id": "address",
                    "title": "Address",
                    "fields": [
                        {
                            "name": "street",
                            "type": "text",
                            "label": "Street Address",
                            "required": True
                        }
                    ]
                }
            ]
        }
        canvas_id = trigger_form_canvas(authenticated_page_api, schema, "Multi-Step Form Test")

        # Wait for form to render
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-step-indicator"]', timeout=5000)

        # Verify step indicator visible
        step_indicator = authenticated_page_api.locator('[data-testid="canvas-form-step-indicator"]')
        assert step_indicator.is_visible(), "Step indicator should be visible for multi-step form"

        # Try to proceed to step 2 without filling step 1
        next_button = authenticated_page_api.locator('[data-testid="canvas-form-next-step"]')
        if next_button.count() > 0:
            initial_step_text = authenticated_page_api.locator('[data-testid="canvas-form-current-step"]').text_content()

            next_button.click()

            # Verify validation prevents step change (step indicator unchanged)
            current_step_text = authenticated_page_api.locator('[data-testid="canvas-form-current-step"]').text_content()
            assert initial_step_text == current_step_text, "Step should not change without completing required fields"

        # Fill step 1 fields
        authenticated_page_api.locator('[data-testid="canvas-form-field-first_name"]').fill("John")
        authenticated_page_api.locator('[data-testid="canvas-form-field-last_name"]').fill("Doe")

        # Proceed to step 2
        if next_button.count() > 0:
            next_button.click()

            # Verify step 2 fields visible
            authenticated_page_api.wait_for_selector('[data-testid="canvas-form-field-street"]', timeout=3000)
            street_field = authenticated_page_api.locator('[data-testid="canvas-form-field-street"]')
            assert street_field.is_visible(), "Step 2 fields should be visible after completing step 1"
