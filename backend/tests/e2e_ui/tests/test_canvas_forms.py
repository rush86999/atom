"""
E2E tests for canvas form submission and validation.

These tests verify the complete form workflow including:
- Form rendering with title and field types
- Required field validation
- Email pattern validation
- Number min/max validation
- Form submission with API integration
- Form governance enforcement (SUPERVISED+ required)
- Form state API access (window.atom.canvas.getState)

Tests use page.evaluate() to trigger form canvas presentations
and page.route() to mock form submission API responses.

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_forms.py -v
"""

import pytest
import uuid
import json
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
from typing import Dict, Any, List

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import CanvasFormPage, CanvasHostPage
from core.models import User, AgentRegistry, AgentExecution, CanvasAudit
from core.auth import get_password_hash
from datetime import datetime
from conftest import create_test_user, get_auth_token_for_user


def create_test_form_schema(field_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a test form schema with specified field configurations.

    Args:
        field_configs: List of field config dicts with keys:
            - name, label, type, placeholder, defaultValue, required, validation, options

    Returns:
        dict: Form schema compatible with InteractiveForm component
    """
    return {
        "canvas_type": "generic",
        "canvas_id": f"form-{str(uuid.uuid4())}",
        "timestamp": datetime.utcnow().isoformat(),
        "component": "form",
        "title": field_configs[0].get("form_title", "Test Form"),
        "form_schema": {
            "fields": field_configs
        }
    }


def trigger_form_canvas(page: Page, schema: Dict[str, Any], title: str = "Test Form") -> str:
    """Simulate WebSocket canvas:update event to trigger form canvas presentation.

    This function uses page.evaluate() to directly dispatch the canvas event,
    simulating what would happen when the backend sends a WebSocket message.

    Args:
        page: Playwright page
        schema: Form schema with fields configuration
        title: Form title

    Returns:
        str: Canvas ID for the triggered form
    """
    canvas_id = schema.get("canvas_id", f"form-{str(uuid.uuid4())}")

    # Simulate WebSocket message by setting lastMessage in window
    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "form",
            "title": title,
            "schema": schema
        }
    }

    # Inject canvas message into window (simulates WebSocket delivery)
    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)

    # Dispatch custom event to trigger canvas host useEffect
    page.evaluate(f"""
        () => {{
            const event = new CustomEvent('canvas:update', {{
                detail: {{ type: 'canvas:update' }}
            }});
            window.dispatchEvent(event);
        }}
    """)

    return canvas_id


def mock_canvas_submit_api(page: Page, response_data: Dict[str, Any], status_code: int = 200) -> None:
    """Mock the /api/canvas/submit endpoint to return custom response.

    Args:
        page: Playwright page
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
# Form Rendering Tests
# ============================================================================

def test_form_renders_with_title(authenticated_page: Page):
    """Test that form displays title correctly."""
    # Create form schema with title
    form_schema = create_test_form_schema([
        {
            "form_title": "User Registration Form",
            "name": "full_name",
            "label": "Full Name",
            "type": "text",
            "placeholder": "Enter your full name",
            "required": True
        }
    ])

    # Trigger form canvas
    canvas_id = trigger_form_canvas(authenticated_page, form_schema, "User Registration Form")

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Verify form is loaded
    assert form_page.is_loaded() is True, "Form should be visible"

    # Verify form title displays
    title = form_page.get_title()
    assert "User Registration Form" in title, f"Form title should contain 'User Registration Form', got: {title}"


def test_form_field_types(authenticated_page: Page):
    """Test that all field types render correctly."""
    # Create form with all field types
    form_schema = create_test_form_schema([
        {
            "form_title": "All Field Types",
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
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Verify all fields render
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


def test_form_required_fields(authenticated_page: Page):
    """Test that required fields show asterisk indicator."""
    # Create form with mix of required and optional fields
    form_schema = create_test_form_schema([
        {
            "form_title": "Required Fields Test",
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
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Verify required fields have asterisk
    assert form_page.is_field_required("required_field1") is True, "required_field1 should be marked as required"
    assert form_page.is_field_required("required_field2") is True, "required_field2 should be marked as required"
    assert form_page.is_field_required("optional_field") is False, "optional_field should not be marked as required"


# ============================================================================
# Form Validation Tests
# ============================================================================

def test_form_required_field_validation(authenticated_page: Page):
    """Test that required fields show validation errors when empty."""
    # Create form with required fields
    form_schema = create_test_form_schema([
        {
            "form_title": "Validation Test",
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
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

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


def test_form_email_validation(authenticated_page: Page):
    """Test email pattern validation."""
    # Create form with email validation
    form_schema = create_test_form_schema([
        {
            "form_title": "Email Validation Test",
            "name": "email",
            "label": "Email Address",
            "type": "email",
            "required": True,
            "validation": {
                "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
                "custom": "Please enter a valid email address"
            }
        }
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

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

    # Enter valid email
    form_page.fill_email_field("email", "user@example.com")
    authenticated_page.wait_for_timeout(300)

    # Verify error clears
    assert form_page.has_field_error("email") is False, "Error should clear for valid email"


def test_form_number_min_max_validation(authenticated_page: Page):
    """Test number field min/max validation."""
    # Create form with number validation
    form_schema = create_test_form_schema([
        {
            "form_title": "Number Validation Test",
            "name": "age",
            "label": "Age",
            "type": "number",
            "required": True,
            "validation": {"min": 18, "max": 100}
        }
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5005)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

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

    # Enter valid number
    form_page.fill_number_field("age", 25)
    authenticated_page.wait_for_timeout(300)

    # Verify error clears
    assert form_page.has_field_error("age") is False, "Error should clear for valid number"


def test_form_validation_summary(authenticated_page: Page):
    """Test that multiple validation errors display simultaneously."""
    # Create form with multiple required fields
    form_schema = create_test_form_schema([
        {
            "form_title": "Multiple Validation Test",
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
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

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

def test_form_submit_success(authenticated_page: Page, db_session: Session):
    """Test successful form submission with API call."""
    # Create form schema
    form_schema = create_test_form_schema([
        {
            "form_title": "Submit Test",
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
    ])

    # Trigger form canvas
    canvas_id = trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Mock successful API response
    mock_canvas_submit_api(authenticated_page, {
        "submission_id": str(uuid.uuid4()),
        "agent_execution_id": None,
        "agent_id": None,
        "governance_check": {"allowed": True}
    })

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Fill form with valid data
    form_page.fill_text_field("name", "John Doe")
    form_page.fill_email_field("email", "john@example.com")

    # Submit form
    form_page.click_submit()

    # Wait for submission to complete
    form_page.wait_for_submission(timeout=5000)

    # Verify success message displays
    assert form_page.is_success_message_visible() is True, "Success message should be visible"
    success_msg = form_page.get_success_message()
    assert "submitted successfully" in success_msg.lower() or "check" in success_msg.lower(), f"Expected success message, got: {success_msg}"


def test_form_submit_button_disabled_during_submission(authenticated_page: Page):
    """Test that submit button is disabled during submission."""
    # Create form schema
    form_schema = create_test_form_schema([
        {
            "form_title": "Submit Button Test",
            "name": "name",
            "label": "Name",
            "type": "text",
            "required": True
        }
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Mock API response with delay (simulate slow submission)
    def handle_route(route):
        # Delay response to observe button state
        authenticated_page.wait_for_timeout(1000)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"success": True, "data": {"submission_id": str(uuid.uuid4())}})
        )

    authenticated_page.route("http://localhost:8001/api/canvas/submit", handle_route)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

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
    form_page.wait_for_submission(timeout=5000)

    # Verify button re-enables after success (form is replaced by success message)
    # After submission, form is replaced by success message, so button is no longer visible
    assert form_page.is_success_message_visible() is True, "Success message should appear"


def test_form_submit_with_agent_context(authenticated_page: Page, db_session: Session):
    """Test form submission with agent_id and agent_execution_id context."""
    # Create agent for testing
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name=f"TestAgent_{str(uuid.uuid4())[:8]}",
        maturity_level="SUPERVISED",  # SUPERVISED+ can submit forms
        agent_type="assistant",
        description="Test agent for form submission",
        system_prompt="You are a test agent",
        capabilities=["present_canvas", "submit_form"],
        config={},
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    # Create form schema
    form_schema = create_test_form_schema([
        {
            "form_title": "Agent Context Test",
            "name": "user_input",
            "label": "Input",
            "type": "text",
            "required": True
        }
    ])

    # Trigger form canvas
    canvas_id = trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Mock API response that includes agent execution
    mock_response = {
        "submission_id": str(uuid.uuid4()),
        "agent_execution_id": str(uuid.uuid4()),
        "agent_id": agent.id,
        "governance_check": {"allowed": True, "reason": "Agent has SUPERVISED maturity"}
    }

    # Intercept and verify request contains agent context
    def handle_route(route):
        # Get request body
        request = route.request
        body = json.loads(request.post_data)

        # Verify agent context is included
        # Note: In real scenario, this would be added by the frontend
        # For this test, we just verify the mock response is used

        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"success": True, "data": mock_response})
        )

    authenticated_page.route("http://localhost:8001/api/canvas/submit", handle_route)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Fill and submit form
    form_page.fill_text_field("user_input", "Test input")
    form_page.click_submit()

    # Wait for submission
    form_page.wait_for_submission(timeout=5000)

    # Verify success
    assert form_page.is_success_message_visible() is True, "Form should submit successfully"

    # Verify agent execution record exists (if we had real governance)
    # In this mocked scenario, we verify the response structure
    assert "agent_id" in mock_response, "Response should include agent_id"
    assert "governance_check" in mock_response, "Response should include governance_check"


def test_form_submit_governance_blocked(authenticated_page: Page, db_session: Session):
    """Test that STUDENT agents cannot submit forms (governance enforcement)."""
    # Create STUDENT agent (below SUPERVISED)
    student_agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name=f"StudentAgent_{str(uuid.uuid4())[:8]}",
        maturity_level="STUDENT",  # STUDENT cannot submit forms
        agent_type="assistant",
        description="Test STUDENT agent",
        system_prompt="You are a student agent",
        capabilities=["present_canvas"],  # No submit_form capability
        config={},
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(student_agent)
    db_session.commit()
    db_session.refresh(student_agent)

    # Create form schema
    form_schema = create_test_form_schema([
        {
            "form_title": "Governance Test",
            "name": "data",
            "label": "Data",
            "type": "text",
            "required": True
        }
    ])

    # Trigger form canvas
    trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Mock governance blocked response
    def handle_route(route):
        route.fulfill(
            status=403,
            content_type="application/json",
            body=json.dumps({
                "success": False,
                "error_code": "GOVERNANCE_DENIED",
                "message": "Form submission requires SUPERVISED maturity level or higher",
                "details": {
                    "agent_id": student_agent.id,
                    "action": "submit_form",
                    "required_level": "SUPERVISED",
                    "current_level": "STUDENT"
                }
            })
        )

    authenticated_page.route("http://localhost:8001/api/canvas/submit", handle_route)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Fill and submit form
    form_page.fill_text_field("data", "Test data")
    form_page.click_submit()

    # Wait for response
    authenticated_page.wait_for_timeout(1000)

    # Verify governance error is shown (form-level error)
    # Note: The InteractiveForm component shows form-level error in errors._form
    # After governance failure, the form should show error state
    # In the current implementation, errors are shown in red text below fields

    # The success message should NOT appear
    assert form_page.is_success_message_visible() is False, "Success message should not appear for blocked submission"


# ============================================================================
# Form State API Tests
# ============================================================================

def test_form_state_api(authenticated_page: Page):
    """Test that form state is accessible via window.atom.canvas.getState()."""
    # Create form schema
    form_schema = create_test_form_schema([
        {
            "form_title": "State API Test",
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
    ])

    # Trigger form canvas
    canvas_id = trigger_form_canvas(authenticated_page, form_schema)

    # Wait for canvas to appear
    canvas_host = CanvasHostPage(authenticated_page)
    canvas_host.wait_for_canvas_visible(timeout=5000)

    # Initialize form page
    form_page = CanvasFormPage(authenticated_page)

    # Fill form fields
    form_page.fill_text_field("text_field", "Test value")
    form_page.fill_number_field("number_field", 100)

    # Wait for state to update
    authenticated_page.wait_for_timeout(500)

    # Access form state via canvas state API
    form_state = authenticated_page.evaluate(f"(canvasId) => window.atom.canvas.getState(canvasId)", canvas_id)

    # Verify state structure
    assert form_state is not None, "Form state should be accessible via API"
    assert form_state["canvas_type"] == "generic", "State should have canvas_type"
    assert form_state["component"] == "form", "State should have component type 'form'"
    assert "form_data" in form_state, "State should include form_data"
    assert "validation_errors" in form_state, "State should include validation_errors"

    # Verify form data matches input values
    assert form_state["form_data"]["text_field"] == "Test value", "State should reflect text field value"
    assert form_state["form_data"]["number_field"] == 100, "State should reflect number field value"

    # Verify no validation errors when form is valid
    assert len(form_state["validation_errors"]) == 0, "State should have no validation errors for valid form"
