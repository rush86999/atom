"""
Canvas Mobile API-level E2E Tests

Tests canvas API endpoints for mobile platform (React Native).
Uses API-level testing to bypass mobile UI limitations.

Real canvas API surface (backend/api/canvas_routes.py + tools/canvas_crud_tool.py):
- POST /api/canvas/{canvas_id}/context — create/seed canvas context (the
  HTTP-visible "present" path; the agent present tool writes Canvas+CanvasAudit
  rows + a WS broadcast, the context endpoint persists the state snapshot)
- GET /api/canvas/{canvas_id}/context — context snapshot (canvas_id, canvas_type,
  current_state)
- POST /api/canvas/submit — form submission (writes a CanvasAudit row)
- GET /api/canvas/ — canvas list derived from the CanvasAudit trail

Requirements:
- MOBILE-01: Canvas API works for mobile (React Native) via API-level testing
- CROSS-01: Cross-platform canvas state is consistent (web, mobile, desktop)

Tests:
1. test_mobile_canvas_present_api - Present canvas via mobile API
2. test_mobile_canvas_get_state_api - Get canvas state via mobile API
3. test_mobile_canvas_submit_form_api - Submit form via mobile API
4. test_mobile_canvas_list_api - List canvases via mobile API
5. test_mobile_canvas_cross_platform_consistency - Verify cross-platform consistency
"""

import os
import sys
import uuid
from typing import Dict, Any

import pytest
import requests

# Add backend to path (5 dirnames: tests/e2e_ui/tests/cross-platform → backend)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import CanvasAudit, CanvasContext
from sqlalchemy.orm import Session


BASE_URL = "http://localhost:8001"


# ============================================================================
# Helper Functions
# ============================================================================

def create_mobile_token(user: Any, password: str = "TestPassword123!", base_url: str = BASE_URL) -> str:
    """Create access token for mobile platform via API login.

    The real login endpoint accepts ``username`` (not ``email``) — see
    utils/api_setup.authenticate_user. The user must exist in the DB the
    backend serves (created by the test_user fixture).

    Args:
        user: User ORM instance (must have ``email``)
        password: User password
        base_url: Base URL for API requests

    Returns:
        JWT access token

    Raises:
        AssertionError: If login fails
    """
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "username": user.email,
            "password": password
        }
    )

    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert 'access_token' in data, "No access_token in response"

    return data['access_token']


def present_canvas_via_mobile_api(token: str, canvas_id: str, canvas_data: dict, base_url: str = BASE_URL) -> dict:
    """Present canvas via mobile API with X-Platform header.

    Real endpoint: POST /api/canvas/{canvas_id}/context — creates the
    canvas context and seeds the initial state (the HTTP-visible present path).

    Args:
        token: JWT access token
        canvas_id: Canvas ID to create context for
        canvas_data: Canvas data (type, chart_type, data, etc.)
        base_url: Base URL for API requests

    Returns:
        API response dict with context_id

    Raises:
        AssertionError: If canvas presentation fails
    """
    response = requests.post(
        f"{base_url}/api/canvas/{canvas_id}/context",
        json={
            "canvas_type": canvas_data["type"],
            "initial_state": canvas_data,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"Canvas present failed: {response.text}"
    data = response.json()
    assert data.get("success") is True, f"Canvas present not successful: {data}"

    return data


def get_canvas_state_via_mobile_api(token: str, canvas_id: str, base_url: str = BASE_URL) -> dict:
    """Get canvas state via mobile API.

    Real endpoint: GET /api/canvas/{canvas_id}/context — the state snapshot
    carries canvas_id / canvas_type / current_state.

    Args:
        token: JWT access token
        canvas_id: Canvas ID to query
        base_url: Base URL for API requests

    Returns:
        Canvas state dict

    Raises:
        AssertionError: If state retrieval fails
    """
    response = requests.get(
        f"{base_url}/api/canvas/{canvas_id}/context",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"Get state failed: {response.text}"
    data = response.json()
    assert data.get("success") is True, f"Get state not successful: {data}"

    return data.get("data") or {}


def submit_canvas_form_via_mobile_api(token: str, canvas_id: str, form_values: dict, base_url: str = BASE_URL) -> dict:
    """Submit canvas form via mobile API.

    Real endpoint: POST /api/canvas/submit — persists a CanvasAudit row.

    Args:
        token: JWT access token
        canvas_id: Canvas ID
        form_values: Form field values
        base_url: Base URL for API requests

    Returns:
        Submission response dict

    Raises:
        AssertionError: If submission fails
    """
    response = requests.post(
        f"{base_url}/api/canvas/submit",
        json={
            "canvas_id": canvas_id,
            "form_data": form_values
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"Form submit failed: {response.text}"
    data = response.json()
    assert data.get("success") is True, f"Form submit not successful: {data}"

    return data


def list_canvases_via_mobile_api(token: str, base_url: str = BASE_URL) -> list:
    """List canvases via mobile API.

    Real endpoint: GET /api/canvas/ — returns canvases derived from the
    CanvasAudit trail (canvas_id / canvas_type / action_type / title).

    Args:
        token: JWT access token
        base_url: Base URL for API requests

    Returns:
        List of canvas dicts

    Raises:
        AssertionError: If list request fails
    """
    response = requests.get(
        f"{base_url}/api/canvas/",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"List canvases failed: {response.text}"
    data = response.json()
    assert data.get("success") is True, f"List canvases not successful: {data}"

    return data.get("canvases") or []


def verify_canvas_schema_compatibility(state: dict) -> bool:
    """Verify canvas state matches expected schema for cross-platform compatibility.

    The real context snapshot carries canvas_id / canvas_type / current_state.

    Args:
        state: Canvas state dict

    Returns:
        True if schema is compatible

    Raises:
        AssertionError: If required keys are missing
    """
    required_keys = ['canvas_id', 'canvas_type', 'current_state']

    for key in required_keys:
        assert key in state, f"Missing required key: {key}"

    return True


def create_test_chart_canvas_data() -> dict:
    """Create test chart canvas data.

    Returns:
        Canvas data dict for line chart
    """
    return {
        "type": "chart",
        "chart_type": "line",
        "data": {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "datasets": [{
                "label": "Sales",
                "data": [10, 20, 30, 40]
            }]
        }
    }


def create_test_form_canvas_data() -> dict:
    """Create test form canvas data.

    Returns:
        Canvas data dict for form
    """
    return {
        "type": "form",
        "title": "User Registration",
        "schema": {
            "fields": [
                {
                    "name": "full_name",
                    "label": "Full Name",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "email",
                    "label": "Email",
                    "type": "email",
                    "required": True
                }
            ]
        }
    }


def create_canvas_audit_row(db_session: Session, user: Any, canvas_id: str, canvas_type: str = "chart") -> None:
    """Create a real Canvas + CanvasAudit row so the audit-derived list/read
    endpoints can serve it (the exact shape tools/canvas_tool._create_canvas_audit
    writes in production)."""
    from core.models import Canvas
    db_session.add(Canvas(
        id=canvas_id,
        tenant_id="default",
        created_by=str(user.id),
        name=canvas_id,
        canvas_type=canvas_type,
        content={},
    ))
    db_session.add(CanvasAudit(
        id=str(uuid.uuid4()),
        tenant_id="default",
        canvas_id=canvas_id,
        user_id=str(user.id),
        action_type="present",
        canvas_type=canvas_type,
        details_json={"title": canvas_id, "content": {}},
    ))
    db_session.commit()


# ============================================================================
# Tests
# ============================================================================

def test_mobile_canvas_present_api(test_user, db_session: Session):
    """Test canvas present API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create test user and get access token
    2. Send POST request to /api/canvas/{id}/context with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify response contains context_id and canvas_id
    5. Verify CanvasContext record created in database
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Present chart canvas
    canvas_id = f"mobile-present-{uuid.uuid4()}"
    canvas_data = create_test_chart_canvas_data()
    response = present_canvas_via_mobile_api(token, canvas_id, canvas_data)

    # Verify response
    data = response.get("data", {})
    assert data.get("canvas_id") == canvas_id, "Canvas_id mismatch in response"

    # Verify CanvasContext record created
    context = db_session.query(CanvasContext).filter(
        CanvasContext.canvas_id == canvas_id
    ).first()

    assert context is not None, "CanvasContext record not created"
    assert context.canvas_type == "chart", f"Expected canvas_type='chart', got '{context.canvas_type}'"


def test_mobile_canvas_get_state_api(test_user):
    """Test canvas get state API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create canvas context via present API
    2. Send GET request to /api/canvas/{canvas_id}/context with X-Platform: mobile
    3. Verify response status: 200
    4. Verify response contains canvas state (canvas_id, canvas_type, current_state)
    5. Verify state structure matches web version (cross-platform consistency)
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Present canvas
    canvas_id = f"mobile-state-{uuid.uuid4()}"
    canvas_data = create_test_chart_canvas_data()
    present_canvas_via_mobile_api(token, canvas_id, canvas_data)

    # Get canvas state
    state = get_canvas_state_via_mobile_api(token, canvas_id)

    # Verify state structure (cross-platform consistency)
    verify_canvas_schema_compatibility(state)

    # Verify state matches what was presented
    assert state['canvas_id'] == canvas_id, "canvas_id mismatch"
    assert state['canvas_type'] == 'chart', f"Unexpected type: {state['canvas_type']}"
    assert state['current_state'].get('type') == 'chart', \
        f"Initial state not seeded: {state['current_state']}"


def test_mobile_canvas_submit_form_api(test_user, db_session: Session):
    """Test canvas form submit API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create form canvas context via present API
    2. Send POST request to /api/canvas/submit with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify submission success message
    5. Verify CanvasAudit record with action="submit"
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Present form canvas
    canvas_id = f"mobile-form-{uuid.uuid4()}"
    canvas_data = create_test_form_canvas_data()
    present_canvas_via_mobile_api(token, canvas_id, canvas_data)

    # Submit form
    form_values = {
        "full_name": "Test User",
        "email": "test@example.com"
    }
    submit_response = submit_canvas_form_via_mobile_api(token, canvas_id, form_values)

    # Verify submission success
    assert submit_response.get("success") is True, "Invalid submit response"
    assert submit_response.get("data", {}).get("submitted") is True, "Submission flag not set"

    # Verify CanvasAudit record created
    audit = db_session.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.action_type == "submit"
    ).first()

    assert audit is not None, "CanvasAudit submit record not created"


def test_mobile_canvas_list_api(test_user, db_session: Session):
    """Test canvas list API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create 3 canvases (context rows + audit rows)
    2. Send GET request to /api/canvas/ with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify response contains array of canvases
    5. Verify each created canvas is listed with its id and type
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Create 3 canvases
    canvas_ids = []
    for i in range(3):
        canvas_id = f"mobile-list-{uuid.uuid4()}"
        present_canvas_via_mobile_api(token, canvas_id, create_test_chart_canvas_data())
        create_canvas_audit_row(db_session, test_user, canvas_id)
        canvas_ids.append(canvas_id)

    # List canvases
    canvases = list_canvases_via_mobile_api(token)

    # Verify list response
    assert isinstance(canvases, list), "Canvases response is not a list"
    listed_ids = {c.get("canvas_id") for c in canvases}
    assert len(canvases) >= 3, f"Expected at least 3 canvases, got {len(canvases)}"
    for canvas_id in canvas_ids:
        assert canvas_id in listed_ids, f"Canvas {canvas_id} not found in list"


def test_mobile_canvas_cross_platform_consistency(test_user):
    """Test canvas state is consistent across mobile and web platforms (CROSS-01).

    Scenario:
    1. Create canvas context via mobile API (X-Platform: mobile)
    2. Get canvas state via mobile API
    3. Get the same state via web API (X-Platform: web — same endpoint)
    4. Verify consistency: mobile_state == web_state (same keys, same values)
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Present canvas via mobile API
    canvas_id = f"mobile-xplat-{uuid.uuid4()}"
    canvas_data = create_test_chart_canvas_data()
    present_canvas_via_mobile_api(token, canvas_id, canvas_data)

    # Get state via mobile API
    mobile_state = get_canvas_state_via_mobile_api(token, canvas_id)

    # Get state via web API (same endpoint, different platform header)
    web_response = requests.get(
        f"{BASE_URL}/api/canvas/{canvas_id}/context",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "web"
        }
    )
    assert web_response.status_code == 200, f"Web state request failed: {web_response.text}"
    web_state = web_response.json().get("data") or {}

    # Verify both states have same structure
    verify_canvas_schema_compatibility(mobile_state)
    verify_canvas_schema_compatibility(web_state)

    # Verify canvas_id matches
    assert mobile_state['canvas_id'] == web_state['canvas_id'], "canvas_id mismatch between mobile and web"

    # Verify type matches
    assert mobile_state['canvas_type'] == web_state['canvas_type'], "type mismatch between mobile and web"

    # Verify state content matches
    assert mobile_state['current_state'] == web_state['current_state'], \
        "current_state mismatch between mobile and web"
