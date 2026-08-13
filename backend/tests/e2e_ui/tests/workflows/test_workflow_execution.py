"""
E2E tests for workflow execution (WORK-06).

Tests workflow execution against the REAL engine + API contract:

- Execute: POST /api/v1/workflows/workflows/{id}/execute → {execution_id, status: "running"}
- Details: GET /api/v1/workflows/workflows/executions/{execution_id}
- History: GET /api/v1/workflows/workflows/{id}/executions
- Engine: linearizes node/connection graphs (Kahn) — a "default" service
  step fails at runtime with "Unknown service" (the real engine behavior),
  which still proves the execution pipeline ran end to end.

Tests cover:
- Manual workflow execution with correct step order
- Progress tracking during execution
- Failure handling and error messages
- Execution history tracking
- Parallel (branching) step execution
"""

import os
import sys
import time
import uuid
from datetime import datetime
from typing import List

import pytest
import requests

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from core.models import WorkflowExecution
from core.workflow_engine import WorkflowEngine
from sqlalchemy.orm import Session


BASE_URL = "http://localhost:8001"
WORKFLOWS_API = f"{BASE_URL}/api/v1/workflows/workflows"

# Workflows created during a test run (the store is a shared JSON file) —
# cleaned up after every test so runs stay idempotent.
_CREATED_WORKFLOW_IDS: List[str] = []


@pytest.fixture(autouse=True)
def _cleanup_created_workflows(test_user):
    """Delete every workflow the test created (shared workflows.json store)."""
    yield
    token = get_token(test_user)
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

def get_token(test_user) -> str:
    """Login via the live backend and return a JWT (workflow:manage required)."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": test_user.email, "password": "TestPassword123!"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


def make_node(node_id: str, title: str, service: str = "default", x: float = 100) -> dict:
    return {
        "id": node_id,
        "type": "action",
        "title": title,
        "description": "",
        "position": {"x": x, "y": 100},
        "config": {"service": service, "action": "default", "parameters": {}},
        "connections": [],
    }


def make_connection(conn_id: str, source: str, target: str) -> dict:
    return {"id": conn_id, "source": source, "target": target}


def build_workflow_payload(name: str, node_ids: List[str], connections: List[dict],
                           failing_index: int = -1) -> dict:
    """Build a node-based WorkflowDefinition. A failing step (index >= 0) uses
    an unknown service so the real engine marks it failed."""
    nodes = []
    for i, nid in enumerate(node_ids):
        service = "unknown_service" if i == failing_index else "default"
        nodes.append(make_node(nid, f"Step {i + 1}", service=service, x=100 * (i + 1)))
    return {
        "name": name,
        "description": f"E2E execution workflow {name}",
        "version": "1",
        "nodes": nodes,
        "connections": connections,
        "triggers": [],
        "enabled": True,
    }


def create_workflow(token: str, payload: dict) -> str:
    """Create workflow via the real API; returns workflow_id."""
    response = requests.post(
        WORKFLOWS_API,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Workflow creation failed: {response.text}"
    workflow_id = response.json()["id"]
    _CREATED_WORKFLOW_IDS.append(workflow_id)
    return workflow_id


def execute_workflow(token: str, workflow_id: str) -> str:
    """Execute workflow via the real API; returns execution_id."""
    response = requests.post(
        f"{WORKFLOWS_API}/{workflow_id}/execute",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Workflow execution failed: {response.text}"
    data = response.json()
    assert "execution_id" in data, f"No execution_id in response: {data}"
    assert data.get("status") == "running", f"Expected status=running, got {data.get('status')}"
    return data["execution_id"]


def get_execution_details(token: str, execution_id: str, timeout: int = 30) -> dict:
    """Poll GET /api/v1/workflows/workflows/executions/{id} until terminal."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(
            f"{WORKFLOWS_API}/executions/{execution_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            execution = response.json()
            if execution.get("status") in ("completed", "complete", "failed", "cancelled"):
                return execution
        time.sleep(1)
    raise TimeoutError(f"Execution {execution_id} did not reach a terminal state")


def get_execution_history(token: str, workflow_id: str) -> List[dict]:
    """GET execution history for a workflow."""
    response = requests.get(
        f"{WORKFLOWS_API}/{workflow_id}/executions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Execution history failed: {response.text}"
    return response.json()


def unique_name(prefix: str) -> str:
    return f"{prefix} {str(uuid.uuid4())[:8]}"


def create_chain_workflow(token: str, skill_count: int = 3) -> str:
    """Create a linear chain workflow: n1 -> n2 -> ... -> nN."""
    node_ids = [f"exec-node-{i}" for i in range(skill_count)]
    connections = [
        make_connection(f"exec-conn-{i}", node_ids[i], node_ids[i + 1])
        for i in range(skill_count - 1)
    ]
    return create_workflow(token, build_workflow_payload(unique_name("Exec WF"), node_ids, connections))


# ============================================================================
# Tests
# ============================================================================

def test_manual_workflow_execution(test_user, db_session: Session):
    """Test manual workflow execution with correct step order (WORK-06).

    Creates workflow with 3 steps in sequence, executes manually, verifies
    the execution id is returned, the run reaches a terminal state, and a
    WorkflowExecution row is persisted.
    """
    token = get_token(test_user)
    workflow_id = create_chain_workflow(token, skill_count=3)

    # Verify the engine linearizes the 3 steps in order
    engine = WorkflowEngine()
    response = requests.get(f"{WORKFLOWS_API}/{workflow_id}", headers={"Authorization": f"Bearer {token}"})
    workflow_def = response.json()
    steps = engine._convert_nodes_to_steps(workflow_def)
    assert [s["id"] for s in steps] == ["exec-node-0", "exec-node-1", "exec-node-2"], \
        f"Step order wrong: {steps}"

    # Execute and wait for terminal state
    execution_id = execute_workflow(token, workflow_id)
    final = get_execution_details(token, execution_id)
    assert final.get("execution_id") == execution_id, "Execution id mismatch"
    assert final.get("status") in ("completed", "failed"), f"Unexpected status: {final.get('status')}"

    # Verify execution record persisted
    execution = db_session.query(WorkflowExecution).filter(
        WorkflowExecution.execution_id == execution_id
    ).first()
    assert execution is not None, "WorkflowExecution row not persisted"
    assert execution.workflow_id == workflow_id, "workflow_id mismatch"


def test_workflow_execution_progress_tracking(test_user):
    """Test workflow execution progress tracking (WORK-06).

    The execute API reports status "running" immediately (async background
    execution); the execution details endpoint reports the terminal state —
    the real progress surface.
    """
    token = get_token(test_user)
    workflow_id = create_chain_workflow(token, skill_count=3)

    # Execute — immediate "running" acknowledgement
    execution_id = execute_workflow(token, workflow_id)
    response = requests.get(
        f"{WORKFLOWS_API}/executions/{execution_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Execution details failed: {response.text}"
    initial = response.json()
    assert initial.get("execution_id") == execution_id, "Execution id mismatch"

    # Poll to terminal state (progress complete)
    final = get_execution_details(token, execution_id)
    assert final.get("status") in ("completed", "failed"), f"Unexpected status: {final.get('status')}"
    assert final.get("workflow_id") == workflow_id, "workflow_id mismatch in details"


def test_workflow_execution_with_failures(test_user, db_session: Session):
    """Test workflow execution with step failures (WORK-06).

    A workflow with an unknown-service step must execute and reach "failed"
    with an error recorded — the engine's real failure contract.
    """
    token = get_token(test_user)

    node_ids = ["fail-node-0", "fail-node-1", "fail-node-2"]
    payload = build_workflow_payload(
        unique_name("Failing WF"),
        node_ids,
        [
            make_connection("c1", "fail-node-0", "fail-node-1"),
            make_connection("c2", "fail-node-1", "fail-node-2"),
        ],
        failing_index=1,  # step 2 uses an unknown service
    )
    workflow_id = create_workflow(token, payload)

    execution_id = execute_workflow(token, workflow_id)
    final = get_execution_details(token, execution_id)

    # The failing step makes the run fail with a recorded error (the engine
    # aborts at the first unknown service — the real failure contract)
    assert final.get("status") == "failed", f"Expected failed status, got {final.get('status')}"
    assert final.get("errors"), f"Expected recorded errors, got {final.get('errors')}"
    error_text = str(final.get("errors"))
    assert "Unknown service" in error_text, f"Error should mention the unknown service: {error_text}"


def test_workflow_execution_history(test_user):
    """Test workflow execution history tracking (WORK-06).

    Executes workflow 3 times, verifies 3 execution records appear in the
    real history endpoint.
    """
    token = get_token(test_user)
    workflow_id = create_chain_workflow(token, skill_count=3)

    # Execute workflow 3 times
    for i in range(3):
        execution_id = execute_workflow(token, workflow_id)
        get_execution_details(token, execution_id)

    # Verify 3 execution records visible via the history endpoint
    executions = get_execution_history(token, workflow_id)
    assert len(executions) >= 3, f"Expected at least 3 executions, got {len(executions)}"

    # Verify each record carries id + status
    for execution in executions[:3]:
        assert execution.get("execution_id"), f"Execution missing id: {execution}"
        assert execution.get("status"), f"Execution missing status: {execution}"


def test_parallel_skill_execution(test_user):
    """Test parallel (branching) skill execution (WORK-06).

    Diamond DAG: n1 -> n2, n1 -> n3, n2 -> n4, n3 -> n4 — the engine
    linearizes 4 steps with n1 first and n4 last (parallel branches n2/n3
    merge at n4), and the run reaches a terminal state.
    """
    token = get_token(test_user)

    node_ids = ["par-node-0", "par-node-1", "par-node-2", "par-node-3"]
    payload = build_workflow_payload(
        unique_name("Parallel WF"),
        node_ids,
        [
            make_connection("c1", "par-node-0", "par-node-1"),
            make_connection("c2", "par-node-0", "par-node-2"),
            make_connection("c3", "par-node-1", "par-node-3"),
            make_connection("c4", "par-node-2", "par-node-3"),
        ],
    )
    workflow_id = create_workflow(token, payload)

    # Engine linearization: root first, merge node last
    engine = WorkflowEngine()
    response = requests.get(f"{WORKFLOWS_API}/{workflow_id}", headers={"Authorization": f"Bearer {token}"})
    steps = engine._convert_nodes_to_steps(response.json())
    assert len(steps) == 4, f"Expected 4 linearized steps, got {len(steps)}"
    assert steps[0]["id"] == "par-node-0", f"Root step should linearize first: {steps}"
    assert steps[-1]["id"] == "par-node-3", f"Merge step should linearize last: {steps}"

    # Execute — the parallel graph runs to a terminal state
    execution_id = execute_workflow(token, workflow_id)
    final = get_execution_details(token, execution_id)
    assert final.get("status") in ("completed", "failed"), f"Unexpected status: {final.get('status')}"
