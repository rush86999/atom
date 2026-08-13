"""
Form Canvas Validation and Submission E2E Tests.

Tests form canvas validation (required fields, email format) and submission
through the REAL rendering path (no phantom state injection):

1. A form canvas is created as `Canvas` + `CanvasAudit` rows via
   `canvas_helpers.create_form_canvas()` (mirroring
   `tools/canvas_tool.present_form()`), content = {schema: {fields}}.
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where `CanvasPanel`
   renders `InteractiveForm` with the real testids:
   - `form-field-{name}` (inputs/selects/checkboxes)
   - `form-submit-button`
   - `form-success-message` (replaces the form on successful submit)
3. Submission posts to the real `/api/canvas/submit` (backend persists a
   `CanvasAudit` row with action_type="submit").

Error messages render as plain text next to the field (real component), e.g.
"{label} is required" / "Invalid email".

Coverage: CANV-03 (form validation), CANV-08 (form submission)
"""

import json
import uuid
from typing import Tuple

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import CanvasAudit, User
from tests.e2e_ui.tests.canvas_helpers import create_form_canvas, open_canvas


# ============================================================================
# Helper Functions
# ============================================================================

def open_form_canvas(page: Page, canvas_id: str) -> None:
    """Navigate to a form canvas and wait for the InteractiveForm."""
    open_canvas(page, canvas_id, "form")
    page.wait_for_selector('[data-testid="form-submit-button"]', timeout=15000)


def create_test_form_fields() -> list:
    """Create the real InteractiveForm field configs (name/label/type/validation)."""
    return [
        {"name": "name", "type": "text", "label": "Full Name", "required": True,
         "validation": {"min": 2}},
        {"name": "email", "type": "email", "label": "Email Address", "required": True},
        {"name": "message", "type": "text", "label": "Message", "required": False},
    ]


def field(page: Page, name: str):
    return page.locator(f'[data-testid="form-field-{name}"]').first


def submit_button(page: Page):
    return page.locator('[data-testid="form-submit-button"]').first


def mock_canvas_submit_api(page: Page, status_code: int = 400) -> None:
    """Stub /api/canvas/submit to exercise the UI error path (failed POST)."""
    def handle_route(route):
        route.fulfill(
            status=status_code,
            content_type="application/json",
            body=json.dumps({
                "success": status_code == 200,
                "data": {},
                "message": "Form submitted successfully" if status_code == 200 else "Submission failed",
            })
        )

    page.route("http://localhost:8001/api/canvas/submit", handle_route)


# ============================================================================
# Tests
# ============================================================================

def test_required_field_validation(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that required field validation blocks submission with error text.

    Verifies:
    - Form renders all 3 fields with real form-field-{name} testids
    - Submit with empty required fields shows "{label} is required" errors
    - No CanvasAudit submit row is persisted (submission rejected client-side)
    """
    user, _ = authenticated_user
    canvas_id = create_form_canvas(db_session, user, create_test_form_fields(), "Required Field Test")
    open_form_canvas(authenticated_page, canvas_id)

    assert authenticated_page.locator('[data-testid^="form-field-"]').count() == 3, (
        "Expected 3 form fields"
    )

    submit_button(authenticated_page).click()

    # Real error text: "Full Name is required" / "Email Address is required".
    expect(authenticated_page.locator("text=Full Name is required").first).to_be_visible()
    expect(authenticated_page.locator("text=Email Address is required").first).to_be_visible()

    # Failed validation must not reach the backend.
    audit = db_session.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id, CanvasAudit.action_type == "submit"
    ).all()
    assert len(audit) == 0, "No submit audit row should be created for failed validation"


def test_email_format_validation(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that email format validation shows inline errors.

    Verifies:
    - "not-an-email" → "Invalid email" error text
    - Valid email + filled required fields → success message (real POST)
    """
    user, _ = authenticated_user
    fields = [{"name": "email", "type": "email", "label": "Email Address", "required": True}]
    canvas_id = create_form_canvas(db_session, user, fields, "Email Validation Test")
    open_form_canvas(authenticated_page, canvas_id)

    field(authenticated_page, "email").fill("not-an-email")
    submit_button(authenticated_page).click()

    error_text = authenticated_page.locator("text=Invalid email").first
    expect(error_text).to_be_visible()

    # Valid email → submission succeeds against the real backend.
    field(authenticated_page, "email").fill("test@example.com")
    submit_button(authenticated_page).click()

    expect(authenticated_page.locator('[data-testid="form-success-message"]')).to_be_visible(timeout=10000)


def test_successful_form_submission(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that a valid submission posts to /api/canvas/submit and the backend
    persists a CanvasAudit row with action_type="submit".

    Verifies:
    - Success message testid appears after submit
    - CanvasAudit submit row exists with the submitted form_data
    """
    user, _ = authenticated_user
    canvas_id = create_form_canvas(db_session, user, create_test_form_fields(), "Successful Submission Test")
    open_form_canvas(authenticated_page, canvas_id)

    field(authenticated_page, "name").fill("John Doe")
    field(authenticated_page, "email").fill("john@example.com")
    field(authenticated_page, "message").fill("Test message")
    submit_button(authenticated_page).click()

    expect(authenticated_page.locator('[data-testid="form-success-message"]')).to_be_visible(timeout=10000)

    audit = db_session.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id, CanvasAudit.action_type == "submit"
    ).all()
    assert len(audit) >= 1, "CanvasAudit submit row should be persisted"

    details = audit[0].details_json or {}
    form_data = details.get("form_data") or {}
    assert form_data.get("name") == "John Doe", f"Submitted data should be stored: {details}"
    assert form_data.get("email") == "john@example.com", "Submitted email should be stored"


def test_form_submission_with_api_mocking(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that the UI handles a failed POST /api/canvas/submit (400).

    The backend never returns 400 for valid auth, so the failure path is
    exercised with a route stub — the UI error surface (errors._form) is real.
    """
    user, _ = authenticated_user
    canvas_id = create_form_canvas(db_session, user, create_test_form_fields(), "API Mocking Test")
    open_form_canvas(authenticated_page, canvas_id)

    field(authenticated_page, "name").fill("Test User")
    field(authenticated_page, "email").fill("test@example.com")

    mock_canvas_submit_api(authenticated_page, status_code=400)
    submit_button(authenticated_page).click()

    expect(authenticated_page.locator("text=Submission failed. Please try again.").first).to_be_visible(
        timeout=10000
    )
    authenticated_page.unroute("http://localhost:8001/api/canvas/submit")


def test_multi_step_form_validation(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Multi-step forms: InteractiveForm renders a single page of fields — the
    real component has no step indicator / next-step navigation (a "steps" key
    in the schema is ignored; only schema.fields render). Documented skip."""
    pytest.skip(
        "InteractiveForm renders one flat field list; multi-step forms are not "
        "implemented in the real component — see components/canvas/InteractiveForm.tsx."
    )
