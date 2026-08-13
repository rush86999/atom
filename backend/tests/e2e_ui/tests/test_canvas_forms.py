"""
E2E tests for canvas form rendering, validation, and submission.

These tests drive the REAL rendering path — no phantom state injection:
1. A form canvas is created as `Canvas` + `CanvasAudit` rows in the e2e
   database via `tests/canvas_helpers.create_form_canvas()`.
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where
   `pages/canvas/[id].tsx` loads `/api/canvas/{id}` and `CanvasPanel` renders
   the `InteractiveForm` component.
3. Submission posts to the REAL backend endpoint `POST /api/canvas/submit`
   (no mock), which persists a `CanvasAudit` row with action_type="submit".

Covered: title, all field types, required indicators, required/email/
min-max validation, validation summary, real submission with success
message + audit persistence, disabled button during submission.

The governance-blocked submission test is skipped: the backend enforces
governance only when the request carries an `agent_id`, and the frontend
form submit path intentionally does not send one (user-driven submissions
are not agent actions).

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_forms.py -v
"""

import pytest
import uuid
import json
from playwright.sync_api import Page
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Tuple

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import CanvasFormPage, CanvasHostPage
from tests.e2e_ui.tests.canvas_helpers import create_form_canvas
from core.models import User


def open_form_canvas(page: Page, canvas_id: str) -> CanvasFormPage:
    """Navigate to the real /canvas/{id} route and wait for the form."""
    page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    page.wait_for_load_state("networkidle")
    canvas_host = CanvasHostPage(page)
    canvas_host.wait_for_canvas_visible(timeout=10000)
    return CanvasFormPage(page)


# ============================================================================
# Form Rendering Tests
# ============================================================================

def test_form_renders_with_title(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that form displays title correctly."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "full_name",
                "label": "Full Name",
                "type": "text",
                "placeholder": "Enter your full name",
                "required": True,
            }
        ],
        "User Registration Form",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Verify form is loaded
    assert form_page.is_loaded() is True, "Form should be visible"

    # Verify form title displays
    title = form_page.get_title()
    assert "User Registration Form" in title, f"Form title should contain 'User Registration Form', got: {title}"


def test_form_field_types(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that all field types render correctly."""
    user, _ = authenticated_user
    fields = [
        {
            "name": "text_field",
            "label": "Text Input",
            "type": "text",
            "placeholder": "Enter text"
        },
        {
            "name": "email_field",
            "label": "Email Input",
            "type": "email",
            "placeholder": "user@example.com",
            "required": True
        },
        {
            "name": "number_field",
            "label": "Number Input",
            "type": "number",
            "validation": {"min": 0, "max": 100}
        },
        {
            "name": "select_field",
            "label": "Select Dropdown",
            "type": "select",
            "options": [
                {"value": "option1", "label": "Option 1"},
                {"value": "option2", "label": "Option 2"}
            ]
        },
        {
            "name": "checkbox_field",
            "label": "Checkbox Field",
            "type": "checkbox"
        }
    ]
    canvas_id = create_form_canvas(db_session, user, fields, "All Field Types")

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Verify all fields render (data-testid="form-field-{name}")
    assert form_page.get_field_count() == 5, "Should have 5 form fields"

    # Verify each field type
    assert form_page.form_input_text.is_visible(), "Text input should be visible"
    assert form_page.form_input_email.is_visible(), "Email input should be visible"
    assert form_page.form_input_number.is_visible(), "Number input should be visible"
    assert form_page.form_select.is_visible(), "Select dropdown should be visible"
    assert form_page.form_checkbox.is_visible(), "Checkbox should be visible"

    # Verify field labels
    assert form_page.get_field_label("text_field") == "Text Input"
    assert form_page.get_field_label("email_field") == "Email Input"
    assert form_page.get_field_label("number_field") == "Number Input"
    assert form_page.get_field_label("select_field") == "Select Dropdown"
    assert form_page.get_field_label("checkbox_field") == "Checkbox Field"


def test_form_required_fields(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that required fields show asterisk indicator."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "required_field1",
                "label": "Required Field 1",
                "type": "text",
                "required": True
            },
            {
                "name": "optional_field",
                "label": "Optional Field",
                "type": "text",
                "required": False
            },
            {
                "name": "required_field2",
                "label": "Required Field 2",
                "type": "email",
                "required": True
            }
        ],
        "Required Fields Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Verify required fields have asterisk
    assert form_page.is_field_required("required_field1") is True, "required_field1 should be marked as required"
    assert form_page.is_field_required("required_field2") is True, "required_field2 should be marked as required"
    assert form_page.is_field_required("optional_field") is False, "optional_field should not be marked as required"


# ============================================================================
# Form Validation Tests
# ============================================================================

def test_form_required_field_validation(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that required fields show validation errors when empty."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "required_name",
                "label": "Name",
                "type": "text",
                "required": True
            },
            {
                "name": "required_email",
                "label": "Email",
                "type": "email",
                "required": True,
                "validation": {"pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$"}
            }
        ],
        "Validation Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Try to submit without filling fields
    form_page.click_submit()

    # Wait a bit for validation to run
    authenticated_page.wait_for_timeout(500)

    # Verify error messages appear
    assert form_page.has_field_error("required_name") is True, "Required name field should show error"
    assert form_page.has_field_error("required_email") is True, "Required email field should show error"

    # Verify error message text
    name_error = form_page.get_field_error("required_name")
    email_error = form_page.get_field_error("required_email")
    assert "required" in name_error.lower() or "name" in name_error.lower(), f"Expected 'required' error, got: {name_error}"
    assert "required" in email_error.lower() or "email" in email_error.lower(), f"Expected 'required' error, got: {email_error}"


def test_form_email_validation(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test email pattern validation."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "email",
                "label": "Email Address",
                "type": "email",
                "required": True,
                "validation": {
                    "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
                    "custom": "Please enter a valid email address"
                }
            }
        ],
        "Email Validation Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Enter invalid email
    form_page.fill_email_field("email", "invalid-email")
    authenticated_page.wait_for_timeout(300)  # Wait for validation

    # Click submit to trigger validation
    form_page.click_submit()
    authenticated_page.wait_for_timeout(500)

    # Verify error appears
    assert form_page.has_field_error("email") is True, "Invalid email should show error"
    error_msg = form_page.get_field_error("email")
    assert "email" in error_msg.lower() or "valid" in error_msg.lower(), f"Expected email validation error, got: {error_msg}"

    # Enter valid email and re-submit — validation is submit-driven, so the
    # error clears after the next submit validates successfully
    form_page.fill_email_field("email", "user@example.com")
    authenticated_page.wait_for_timeout(300)
    form_page.click_submit()
    authenticated_page.wait_for_timeout(500)

    # Verify error clears
    assert form_page.has_field_error("email") is False, "Error should clear for valid email"


def test_form_number_min_max_validation(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test number field min/max validation."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "age",
                "label": "Age",
                "type": "number",
                "required": True,
                "validation": {"min": 18, "max": 100}
            }
        ],
        "Number Validation Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Enter number below min
    form_page.fill_number_field("age", 15)
    authenticated_page.wait_for_timeout(300)
    form_page.click_submit()
    authenticated_page.wait_for_timeout(500)

    # Verify min error
    assert form_page.has_field_error("age") is True, "Below minimum should show error"
    min_error = form_page.get_field_error("age")
    assert "18" in min_error or "least" in min_error.lower(), f"Expected min error, got: {min_error}"

    # Enter number above max
    form_page.fill_number_field("age", 150)
    authenticated_page.wait_for_timeout(300)
    form_page.click_submit()
    authenticated_page.wait_for_timeout(500)

    # Verify max error
    assert form_page.has_field_error("age") is True, "Above maximum should show error"
    max_error = form_page.get_field_error("age")
    assert "100" in max_error or "most" in max_error.lower(), f"Expected max error, got: {max_error}"

    # Enter valid number and re-submit — validation is submit-driven, so the
    # error clears after the next submit validates successfully
    form_page.fill_number_field("age", 25)
    authenticated_page.wait_for_timeout(300)
    form_page.click_submit()
    authenticated_page.wait_for_timeout(500)

    # Verify error clears
    assert form_page.has_field_error("age") is False, "Error should clear for valid number"


def test_form_validation_summary(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that multiple validation errors display simultaneously."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True
            },
            {
                "name": "email",
                "label": "Email",
                "type": "email",
                "required": True,
                "validation": {"pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$"}
            },
            {
                "name": "age",
                "label": "Age",
                "type": "number",
                "required": True,
                "validation": {"min": 18, "max": 100}
            }
        ],
        "Multiple Validation Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Submit empty form
    form_page.click_submit()
    authenticated_page.wait_for_timeout(500)

    # Verify all fields show errors
    assert form_page.has_field_error("name") is True, "Name field should show error"
    assert form_page.has_field_error("email") is True, "Email field should show error"
    assert form_page.has_field_error("age") is True, "Age field should show error"

    # Count error messages
    error_count = 0
    if form_page.has_field_error("name"):
        error_count += 1
    if form_page.has_field_error("email"):
        error_count += 1
    if form_page.has_field_error("age"):
        error_count += 1

    assert error_count == 3, f"Should have 3 validation errors, got {error_count}"


# ============================================================================
# Form Submission Tests
# ============================================================================

def test_form_submit_success(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test successful form submission against the REAL /api/canvas/submit endpoint.

    The backend persists a CanvasAudit row with action_type="submit"; the
    form shows the success message.
    """
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True
            },
            {
                "name": "email",
                "label": "Email",
                "type": "email",
                "required": True,
                "validation": {"pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$"}
            }
        ],
        "Submit Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Fill form with valid data
    form_page.fill_text_field("name", "John Doe")
    form_page.fill_email_field("email", "john@example.com")

    # Submit form (real POST /api/canvas/submit)
    form_page.click_submit()

    # Wait for submission to complete
    form_page.wait_for_submission(timeout=5000)

    # Verify success message displays
    assert form_page.is_success_message_visible() is True, "Success message should be visible"
    success_msg = form_page.get_success_message()
    assert "submitted successfully" in success_msg.lower() or "check" in success_msg.lower(), f"Expected success message, got: {success_msg}"


def test_form_submit_button_disabled_during_submission(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that submit button is disabled during submission."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True
            }
        ],
        "Submit Button Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Delay the real submit endpoint so the in-flight state is observable
    def handle_route(route):
        authenticated_page.wait_for_timeout(1000)
        route.continue_()

    authenticated_page.route("**/api/canvas/submit", handle_route)

    # Fill form
    form_page.fill_text_field("name", "John Doe")

    # Verify button is enabled before submit
    assert form_page.is_submit_enabled() is True, "Submit button should be enabled initially"

    # Click submit
    form_page.click_submit()

    # Immediately check button state (should be disabled and show "Submitting...")
    assert form_page.is_submitting() is True, "Button should show 'Submitting...'"
    assert form_page.is_submit_enabled() is False, "Button should be disabled during submission"

    # Wait for submission to complete
    form_page.wait_for_submission(timeout=10000)

    # Verify success message appears (form is replaced by success message)
    assert form_page.is_success_message_visible() is True, "Success message should appear"


def test_form_submit_with_agent_context(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test form submission persists an audit trail with form data.

    The real POST /api/canvas/submit writes a CanvasAudit row with
    action_type="submit" and the submitted form_data — verify via the
    backend's history endpoint (real API, not a mock).
    """
    user, token = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "user_input",
                "label": "Input",
                "type": "text",
                "required": True
            }
        ],
        "Agent Context Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Fill and submit form
    form_page.fill_text_field("user_input", "Test input")
    form_page.click_submit()

    # Wait for submission
    form_page.wait_for_submission(timeout=5000)

    # Verify success
    assert form_page.is_success_message_visible() is True, "Form should submit successfully"

    # Verify the submit audit row exists via the real backend history endpoint
    import requests
    resp = requests.get(
        f"http://localhost:8001/api/canvas/{canvas_id}/history",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert resp.status_code == 200, f"History endpoint failed: {resp.status_code}"
    history = resp.json().get("history", [])
    submit_rows = [h for h in history if h.get("action_type") == "submit"]
    assert len(submit_rows) >= 1, "Submit audit row should exist after form submission"
    details = submit_rows[0].get("details") or {}
    assert details.get("form_data", {}).get("user_input") == "Test input", \
        "Submitted form data should be persisted in the audit trail"


def test_form_submit_governance_blocked(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Governance-blocked form submission (STUDENT agents).

    Skipped: the backend enforces governance on /api/canvas/submit ONLY when
    the request carries an `agent_id`; the InteractiveForm submit path is
    user-driven and never sends one (there is no agent context in the canvas
    detail route). Driving this test would require an agent-driven form
    presentation (LLM/WebSocket flow) or an agent_id-carrying submit path
    that the frontend does not implement — neither is available without an
    LLM key.
    """
    pytest.skip(
        "Backend governance on /api/canvas/submit only applies to agent_id-carrying "
        "requests; the InteractiveForm path is user-driven and sends no agent_id. "
        "Requires an agent-driven (LLM) form presentation to exercise."
    )


# ============================================================================
# Form State API Tests
# ============================================================================

def test_form_state_api(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that form state is accessible via window.atom.canvas.getState().

    InteractiveForm registers its state (FormCanvasState) with
    window.atom.canvas on mount — the real AI-accessibility contract.
    """
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {
                "name": "text_field",
                "label": "Text Field",
                "type": "text",
                "required": True
            },
            {
                "name": "number_field",
                "label": "Number Field",
                "type": "number",
                "defaultValue": 42
            }
        ],
        "State API Test",
    )

    form_page = open_form_canvas(authenticated_page, canvas_id)

    # Fill form fields
    form_page.fill_text_field("text_field", "Test value")
    form_page.fill_number_field("number_field", 100)

    # Wait for state to update
    authenticated_page.wait_for_timeout(500)

    # Access form state via canvas state API (registered by InteractiveForm)
    form_state = authenticated_page.evaluate(
        "(canvasId) => window.atom.canvas.getState(canvasId)", canvas_id
    )

    # Verify state structure
    assert form_state is not None, "Form state should be accessible via API"
    assert form_state["canvas_type"] == "generic", "State should have canvas_type"
    assert form_state["component"] == "form", "State should have component type 'form'"
    assert "form_data" in form_state, "State should include form_data"
    assert "validation_errors" in form_state, "State should include validation_errors"

    # Verify form data matches input values. Number fields keep the raw input
    # string in state until a submit coerces them (component behavior).
    assert form_state["form_data"]["text_field"] == "Test value", "State should reflect text field value"
    assert str(form_state["form_data"]["number_field"]) == "100", "State should reflect number field value"

    # Verify no validation errors when form is valid
    assert len(form_state["validation_errors"]) == 0, "State should have no validation errors for valid form"
