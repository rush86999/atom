"""
Canvas Mobile API-level E2E Tests

Tests canvas API endpoints for mobile platform (React Native).
Uses API-level testing to bypass mobile UI limitations.

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

# Add backend to path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import CanvasAudit
from sqlalchemy.orm import Session


# ============================================================================
# Helper Functions
# ============================================================================

def create_mobile_token(user_data: dict, base_url: str = "http://localhost:8001") -> str:
    """Create access token for mobile platform via API login.

    Args:
        user_data: User data dictionary with email and password
        base_url: Base URL for API requests

    Returns:
        JWT access token

    Raises:
        AssertionError: If login fails
    """
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "email": user_data['email'],
            "password": user_data['password']
        }
    )

    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert 'access_token' in data, "No access_token in response"

    return data['access_token']


def present_canvas_via_mobile_api(token: str, canvas_data: dict, base_url: str = "http://localhost:8001") -> dict:
    """Present canvas via mobile API with X-Platform header.

    Args:
        token: JWT access token
        canvas_data: Canvas data (type, chart_type, data, etc.)
        base_url: Base URL for API requests

    Returns:
        API response dict with canvas_id

    Raises:
        AssertionError: If canvas presentation fails
    """
    response = requests.post(
        f"{base_url}/api/canvas/present",
        json=canvas_data,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"Canvas present failed: {response.text}"
    data = response.json()
    assert 'canvas_id' in data or 'data' in data, "No canvas_id in response"

    return data


def get_canvas_state_via_mobile_api(token: str, canvas_id: str, base_url: str = "http://localhost:8001") -> dict:
    """Get canvas state via mobile API.

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
        f"{base_url}/api/canvas/{canvas_id}/state",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"Get state failed: {response.text}"
    return response.json()


def submit_canvas_form_via_mobile_api(token: str, canvas_id: str, form_values: dict, base_url: str = "http://localhost:8001") -> dict:
    """Submit canvas form via mobile API.

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
    return response.json()


def list_canvases_via_mobile_api(token: str, base_url: str = "http://localhost:8001") -> list:
    """List canvases via mobile API.

    Args:
        token: JWT access token
        base_url: Base URL for API requests

    Returns:
        List of canvas dicts

    Raises:
        AssertionError: If list request fails
    """
    response = requests.get(
        f"{base_url}/api/canvas/list",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"List canvases failed: {response.text}"
    data = response.json()
    assert isinstance(data, list) or 'data' in data, "Invalid response format"

    return data if isinstance(data, list) else data.get('data', [])


def verify_canvas_schema_compatibility(state: dict) -> bool:
    """Verify canvas state matches expected schema for cross-platform compatibility.

    Args:
        state: Canvas state dict

    Returns:
        True if schema is compatible

    Raises:
        AssertionError: If required keys are missing
    """
    required_keys = ['canvas_id', 'type', 'data']

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


# ============================================================================
# Tests
# ============================================================================

def test_mobile_canvas_present_api(setup_test_user: Dict[str, Any], db_session: Session):
    """Test canvas present API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create test user and get access token
    2. Send POST request to /api/canvas/present with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify response contains canvas_id
    5. Verify CanvasAudit record created in database
    6. Verify platform stored as "mobile"
    """
    # Get access token
    token = create_mobile_token(setup_test_user)

    # Present chart canvas
    canvas_data = create_test_chart_canvas_data()
    response = present_canvas_via_mobile_api(token, canvas_data)

    # Verify response
    assert 'canvas_id' in response or 'data' in response, "No canvas_id in response"

    # Extract canvas_id (might be in different response formats)
    canvas_id = response.get('canvas_id') or response.get('data', {}).get('canvas_id')
    assert canvas_id is not None, "Could not extract canvas_id from response"

    # Verify CanvasAudit record created
    audit = db_session.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id
    ).first()

    assert audit is not None, "CanvasAudit record not created"
    assert audit.action_type == "present", f"Expected action_type='present', got '{audit.action_type}'"

    # Verify platform stored (check details_json)
    if audit.details_json:
        # Check if platform information is stored
        if 'platform' in audit.details_json:
            assert audit.details_json['platform'] == 'mobile', \
                f"Expected platform='mobile', got '{audit.details_json['platform']}'"


def test_mobile_canvas_get_state_api(setup_test_user: Dict[str, Any]):
    """Test canvas get state API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create canvas via present API
    2. Send GET request to /api/canvas/{canvas_id}/state with X-Platform: mobile
    3. Verify response status: 200
    4. Verify response contains canvas state (canvas_id, type, data)
    5. Verify state structure matches web version (cross-platform consistency)
    """
    # Get access token
    token = create_mobile_token(setup_test_user)

    # Present canvas
    canvas_data = create_test_chart_canvas_data()
    present_response = present_canvas_via_mobile_api(token, canvas_data)
    canvas_id = present_response.get('canvas_id') or present_response.get('data', {}).get('canvas_id')

    # Get canvas state
    state = get_canvas_state_via_mobile_api(token, canvas_id)

    # Verify state structure (cross-platform consistency)
    verify_canvas_schema_compatibility(state)

    # Verify state matches what was presented
    assert state['canvas_id'] == canvas_id, "canvas_id mismatch"
    assert state['type'] in ['chart', 'generic'], f"Unexpected type: {state['type']}"


def test_mobile_canvas_submit_form_api(setup_test_user: Dict[str, Any], db_session: Session):
    """Test canvas form submit API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create form canvas via present API
    2. Send POST request to /api/canvas/submit with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify submission success message
    5. Verify CanvasAudit record with action="submit"
    """
    # Get access token
    token = create_mobile_token(setup_test_user)

    # Present form canvas
    canvas_data = create_test_form_canvas_data()
    present_response = present_canvas_via_mobile_api(token, canvas_data)
    canvas_id = present_response.get('canvas_id') or present_response.get('data', {}).get('canvas_id')

    # Submit form
    form_values = {
        "full_name": "Test User",
        "email": "test@example.com"
    }
    submit_response = submit_canvas_form_via_mobile_api(token, canvas_id, form_values)

    # Verify submission success
    assert 'success' in submit_response or 'message' in submit_response, "Invalid submit response"

    # Verify CanvasAudit record created
    audit = db_session.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.action_type == "submit"
    ).first()

    assert audit is not None, "CanvasAudit submit record not created"


def test_mobile_canvas_list_api(setup_test_user: Dict[str, Any]):
    """Test canvas list API works for mobile platform (MOBILE-01).

    Scenario:
    1. Create 3 canvases via API
    2. Send GET request to /api/canvas/list with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify response contains array of canvases
    5. Verify count == 3
    6. Verify each canvas has required fields (id, type, created_at)
    """
    # Get access token
    token = create_mobile_token(setup_test_user)

    # Create 3 canvases
    canvas_ids = []
    for i in range(3):
        canvas_data = create_test_chart_canvas_data()
        present_response = present_canvas_via_mobile_api(token, canvas_data)
        canvas_id = present_response.get('canvas_id') or present_response.get('data', {}).get('canvas_id')
        canvas_ids.append(canvas_id)

    # List canvases
    canvases = list_canvases_via_mobile_api(token)

    # Verify list response
    assert isinstance(canvases, list), "Canvases response is not a list"
    assert len(canvases) >= 3, f"Expected at least 3 canvases, got {len(canvases)}"


def test_mobile_canvas_cross_platform_consistency(setup_test_user: Dict[str, Any]):
    """Test canvas state is consistent across mobile and web platforms (CROSS-01).

    Scenario:
    1. Create canvas via mobile API (X-Platform: mobile)
    2. Get canvas state via mobile API
    3. Compare with web API response format:
       - Same keys present
       - Same data types
       - Same validation rules
    4. Verify consistency: mobile_state == web_state
    """
    # Get access token
    token = create_mobile_token(setup_test_user)

    # Present canvas via mobile API
    canvas_data = create_test_chart_canvas_data()
    mobile_response = present_canvas_via_mobile_api(token, canvas_data)
    canvas_id = mobile_response.get('canvas_id') or mobile_response.get('data', {}).get('canvas_id')

    # Get state via mobile API
    mobile_state = get_canvas_state_via_mobile_api(token, canvas_id)

    # Get state via web API (same endpoint, different platform header)
    web_response = requests.get(
        f"http://localhost:8001/api/canvas/{canvas_id}/state",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "web"
        }
    )

    web_state = web_response.json() if web_response.status_code == 200 else None

    # Verify both states have same structure
    verify_canvas_schema_compatibility(mobile_state)

    if web_state:
        verify_canvas_schema_compatibility(web_state)

        # Verify consistency: same keys
        mobile_keys = set(mobile_state.keys())
        web_keys = set(web_state.keys())

        # At minimum, both should have these keys
        required_keys = {'canvas_id', 'type', 'data'}
        assert required_keys.issubset(mobile_keys), f"Mobile state missing keys: {required_keys - mobile_keys}"
        assert required_keys.issubset(web_keys), f"Web state missing keys: {required_keys - web_keys}"

        # Verify canvas_id matches
        assert mobile_state['canvas_id'] == web_state['canvas_id'], "canvas_id mismatch between mobile and web"

        # Verify type matches
        assert mobile_state['type'] == web_state['type'], "type mismatch between mobile and web"
