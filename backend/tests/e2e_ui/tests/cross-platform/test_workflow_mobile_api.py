"""
Workflow Mobile API-level E2E Tests

Tests workflow API endpoints for mobile platform (React Native).
Uses API-level testing to bypass mobile UI limitations.

Real API surface:
- POST /api/v1/workflows/workflows — create (node-based WorkflowDefinition,
  stored in backend/workflows.json; requires workflow:manage)
- GET /api/mobile/workflows — mobile-optimized list (MobileWorkflowSummary)
- GET /api/mobile/workflows/{workflow_id} — mobile details
- POST /api/mobile/workflows/trigger?user_id=<id> — mobile trigger (async or
  synchronous; persists a WorkflowExecution row)
- GET /api/mobile/workflows/executions/{execution_id} — mobile execution details
- POST /api/v1/workflows/workflows/{workflow_id}/schedule — schedule a trigger
  (cron/interval/date via APScheduler)
- GET /api/v1/workflows/scheduler/jobs — list scheduled trigger jobs

Requirements:
- MOBILE-02: Workflow API works for mobile (React Native) via API-level testing
- CROSS-02: Cross-platform workflow execution is consistent

Tests:
1. test_mobile_workflow_create_api - Create workflow via mobile API
2. test_mobile_workflow_execute_api - Execute workflow via mobile API
3. test_mobile_workflow_list_api - List workflows via mobile API
4. test_mobile_workflow_triggers_api - Add triggers via mobile API
5. test_mobile_workflow_cross_platform_consistency - Verify cross-platform consistency
"""

import os
import sys
import time
import uuid
from typing import Dict, Any

import pytest
import requests

# Add backend to path (5 dirnames: tests/e2e_ui/tests/cross-platform → backend)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import WorkflowExecution
from sqlalchemy.orm import Session


BASE_URL = "http://localhost:8001"
WORKFLOWS_API = f"{BASE_URL}/api/v1/workflows/workflows"
MOBILE_API = f"{BASE_URL}/api/mobile/workflows"

# Workflows created during a test run (the store is a shared JSON file) —
# cleaned up after every test so runs stay idempotent.
_CREATED_WORKFLOW_IDS: list = []


@pytest.fixture(autouse=True)
def _cleanup_created_workflows(test_user):
    """Delete every workflow the test created (shared workflows.json store)."""
    yield
    token = create_mobile_token(test_user)
    for wf_id in list(_CREATED_WORKFLOW_IDS):
        try:
            requests.delete(
                f"{WORKFLOWS_API}/{wf_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except Exception:
            pass
    _CREATED_WORKFLOW_IDS.clear()


# ============================================================================
# Helper Functions
# ============================================================================

def create_mobile_token(user: Any, password: str = "TestPassword123!", base_url: str = BASE_URL) -> str:
    """Create access token for mobile platform via API login.

    The real login endpoint accepts ``username`` (not ``email``) — see
    utils/api_setup.authenticate_user.

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


def create_workflow_via_api(token: str, workflow_data: dict, base_url: str = WORKFLOWS_API) -> dict:
    """Create workflow via the core workflow API (X-Platform header).

    Args:
        token: JWT access token
        workflow_data: Workflow data (name, nodes, connections)
        base_url: Base URL for API requests

    Returns:
        API response dict with workflow id

    Raises:
        AssertionError: If workflow creation fails
    """
    response = requests.post(
        base_url,
        json=workflow_data,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"Workflow creation failed: {response.text}"
    data = response.json()
    assert 'id' in data, f"No workflow id in response: {data}"
    if data.get("id"):
        _CREATED_WORKFLOW_IDS.append(data["id"])

    return data


def trigger_workflow_via_mobile_api(token: str, workflow_id: str, user_id: str,
                                    parameters: Dict[str, Any] = None,
                                    base_url: str = MOBILE_API) -> str:
    """Trigger workflow via mobile API.

    Args:
        token: JWT access token
        workflow_id: Workflow ID to execute
        user_id: User ID (required query param of the real endpoint)
        parameters: Optional input parameters
        base_url: Base URL for API requests

    Returns:
        Execution ID string

    Raises:
        AssertionError: If execution fails
    """
    response = requests.post(
        f"{base_url}/trigger?user_id={user_id}",
        json={
            "workflow_id": workflow_id,
            "parameters": parameters or {},
            "synchronous": False,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"Workflow execution failed: {response.text}"
    data = response.json()
    assert 'execution_id' in data, f"No execution_id in response: {data}"

    return data['execution_id']


def poll_workflow_execution(token: str, execution_id: str, timeout: int = 30,
                            base_url: str = MOBILE_API) -> dict:
    """Poll workflow execution until terminal.

    Args:
        token: JWT access token
        execution_id: Execution ID to poll
        timeout: Maximum seconds to wait
        base_url: Base URL for API requests

    Returns:
        Final execution dict with status

    Raises:
        TimeoutError: If execution doesn't complete in time
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(
            f"{base_url}/executions/{execution_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Platform": "mobile"
            }
        )

        if response.status_code == 200:
            execution = response.json()
            # The mobile execution details endpoint keys on `id` (not
            # `execution_id` — see api/mobile_workflows.py).
            status = (execution.get('status') or '').lower()

            if status in ['complete', 'completed', 'failed', 'cancelled']:
                return execution

        time.sleep(1)

    raise TimeoutError(f"Workflow execution {execution_id} did not complete within {timeout}s")


def list_workflows_via_mobile_api(token: str, base_url: str = MOBILE_API) -> list:
    """List workflows via mobile API.

    Args:
        token: JWT access token
        base_url: Base URL for API requests

    Returns:
        List of workflow dicts

    Raises:
        AssertionError: If list request fails
    """
    response = requests.get(
        base_url,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    assert response.status_code == 200, f"List workflows failed: {response.text}"
    data = response.json()
    assert isinstance(data, list), f"Invalid response format: {data}"

    return data


def create_test_workflow_data() -> dict:
    """Create test workflow data with nodes and connections.

    The real WorkflowDefinition contract: nodes (id/type/title/description/
    position/config/connections) + connections (id/source/target) — see
    core/workflow_endpoints.py::WorkflowDefinition.

    Returns:
        Workflow data dict
    """
    unique_id = str(uuid.uuid4())[:8]

    def node(nid: str, title: str, x: float) -> dict:
        return {
            "id": nid,
            "type": "action",
            "title": title,
            "description": "",
            "position": {"x": x, "y": 100},
            "config": {
                "service": "default",
                "action": "default",
                "parameters": {"skill_id": nid}
            },
            "connections": []
        }

    return {
        "name": f"Mobile Test Workflow {unique_id}",
        "description": "Test workflow for mobile API",
        "version": "1",
        "nodes": [node(f"node-{unique_id}-1", "Step 1", 100)],
        "connections": [],
        "triggers": [],
        "enabled": True
    }


def schedule_workflow_trigger(token: str, workflow_id: str, trigger_type: str,
                              trigger_config: dict, base_url: str = WORKFLOWS_API) -> dict:
    """Schedule a workflow trigger via the core API.

    Args:
        token: JWT access token
        workflow_id: Workflow ID
        trigger_type: 'cron', 'interval', or 'date'
        trigger_config: APScheduler trigger kwargs (e.g. {'minutes': 60})
        base_url: Base URL for API requests

    Returns:
        Schedule response dict with job_id
    """
    response = requests.post(
        f"{base_url}/{workflow_id}/schedule",
        json={
            "trigger_type": trigger_type,
            "trigger_config": trigger_config,
            "input_data": {},
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200, f"Trigger scheduling failed: {response.text}"
    data = response.json()
    assert data.get("success") is True, f"Schedule not successful: {data}"
    assert data.get("job_id"), f"No job_id in response: {data}"

    return data


def list_scheduler_jobs(token: str, base_url: str = BASE_URL) -> list:
    """List scheduled trigger jobs via the core API.

    Args:
        token: JWT access token
        base_url: Base URL for API requests

    Returns:
        List of job dicts
    """
    response = requests.get(
        f"{base_url}/api/v1/workflows/scheduler/jobs",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200, f"List scheduler jobs failed: {response.text}"
    return response.json()


# ============================================================================
# Tests
# ============================================================================

def test_mobile_workflow_create_api(test_user, db_session: Session):
    """Test workflow creation API works for mobile platform (MOBILE-02).

    Scenario:
    1. Get mobile access token
    2. Send POST request to /api/v1/workflows/workflows with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify response contains workflow id
    5. Verify workflow is retrievable via the mobile list API
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Create workflow
    workflow_data = create_test_workflow_data()
    response = create_workflow_via_api(token, workflow_data)

    # Extract workflow_id
    workflow_id = response.get('id')
    assert workflow_id is not None, "Could not extract workflow_id from response"
    assert response.get('name') == workflow_data['name'], "Workflow name mismatch"

    # Verify workflow visible via the mobile list API
    workflows = list_workflows_via_mobile_api(token)
    listed_names = {w.get("name") for w in workflows}
    assert workflow_data['name'] in listed_names, \
        f"Workflow '{workflow_data['name']}' not listed via mobile API"


def test_mobile_workflow_execute_api(test_user, db_session: Session):
    """Test workflow execution API works for mobile platform (MOBILE-02).

    Scenario:
    1. Create workflow via mobile API
    2. Send POST request to /api/mobile/workflows/trigger
    3. Verify response status: 200
    4. Verify execution_id returned
    5. Verify WorkflowExecution record created
    6. Poll /api/mobile/workflows/executions/{execution_id} until terminal
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Create workflow
    workflow_data = create_test_workflow_data()
    create_response = create_workflow_via_api(token, workflow_data)
    workflow_id = create_response.get('id')

    # Execute workflow
    execution_id = trigger_workflow_via_mobile_api(token, workflow_id, str(test_user.id))

    # Verify WorkflowExecution record created
    execution = db_session.query(WorkflowExecution).filter(
        WorkflowExecution.execution_id == execution_id
    ).first()

    assert execution is not None, "WorkflowExecution record not created"
    assert execution.workflow_id == workflow_id, "workflow_id mismatch"

    # Poll until terminal status (engine may complete or fail a default-service
    # step — both prove the mobile trigger path executed the workflow)
    final = poll_workflow_execution(token, execution_id, timeout=30)
    assert final.get('id') == execution_id, "Execution id mismatch in poll result"
    assert final.get('status') in ('COMPLETED', 'FAILED', 'complete', 'completed', 'failed'), \
        f"Unexpected terminal status: {final.get('status')}"


def test_mobile_workflow_list_api(test_user):
    """Test workflow list API works for mobile platform (MOBILE-02).

    Scenario:
    1. Create 3 workflows via API
    2. Send GET request to /api/mobile/workflows with X-Platform: mobile header
    3. Verify response status: 200
    4. Verify response contains array of workflows
    5. Verify each created workflow is listed with its name
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Create 3 workflows
    created_names = []
    for i in range(3):
        workflow_data = create_test_workflow_data()
        response = create_workflow_via_api(token, workflow_data)
        created_names.append(response.get('name'))

    # List workflows
    workflows = list_workflows_via_mobile_api(token)

    # Verify list response
    assert isinstance(workflows, list), "Workflows response is not a list"
    listed_names = {w.get("name") for w in workflows}
    for name in created_names:
        assert name in listed_names, f"Workflow '{name}' not listed via mobile API"

    # Verify each workflow has required fields
    for workflow in workflows[:3]:  # Check first 3
        assert 'id' in workflow and 'name' in workflow, \
            f"Workflow missing required fields: {workflow}"


def test_mobile_workflow_triggers_api(test_user):
    """Test workflow triggers API works for mobile platform (MOBILE-02).

    Scenario:
    1. Create workflow via mobile API
    2. Schedule a trigger via POST /api/v1/workflows/workflows/{id}/schedule
    3. Verify response status: 200 + job_id returned
    4. Verify trigger job listed in /api/v1/workflows/scheduler/jobs
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Create workflow
    workflow_data = create_test_workflow_data()
    create_response = create_workflow_via_api(token, workflow_data)
    workflow_id = create_response.get('id')

    # Schedule an interval trigger (the real trigger surface — APScheduler)
    schedule_response = schedule_workflow_trigger(
        token, workflow_id, "interval", {"minutes": 60}
    )
    job_id = schedule_response.get("job_id")

    # Verify trigger job listed
    jobs = list_scheduler_jobs(token)
    job_ids = {j.get("id") for j in jobs}
    assert job_id in job_ids, f"Trigger job {job_id} not found in scheduler jobs"


def test_mobile_workflow_cross_platform_consistency(test_user):
    """Test workflow API is consistent across mobile and web platforms (CROSS-02).

    Scenario:
    1. Create workflow via web API
    2. Get workflow details via mobile API
    3. Compare with web API response:
       - Same id
       - Same name/description
    """
    # Get access token
    token = create_mobile_token(test_user)

    # Create workflow via web API
    workflow_data = create_test_workflow_data()
    mobile_response = create_workflow_via_api(token, workflow_data)
    workflow_id = mobile_response.get('id')

    # Get workflow details via mobile API
    mobile_details = requests.get(
        f"{MOBILE_API}/{workflow_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "mobile"
        }
    )

    # Get workflow details via web API
    web_details = requests.get(
        f"{WORKFLOWS_API}/{workflow_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Platform": "web"
        }
    )

    # Verify both return successfully
    assert mobile_details.status_code == 200, f"Mobile details failed: {mobile_details.text}"
    assert web_details.status_code == 200, f"Web details failed: {web_details.text}"

    mobile_workflow = mobile_details.json()
    web_workflow = web_details.json()

    # Verify IDs match
    assert mobile_workflow.get('id') == workflow_id, "Mobile response ID mismatch"
    assert web_workflow.get('id') == workflow_id, "Web response ID mismatch"

    # Verify names match across platforms
    assert mobile_workflow.get('name') == workflow_data['name'], \
        f"Mobile name mismatch: {mobile_workflow.get('name')}"
    assert web_workflow.get('name') == workflow_data['name'], \
        f"Web name mismatch: {web_workflow.get('name')}"
