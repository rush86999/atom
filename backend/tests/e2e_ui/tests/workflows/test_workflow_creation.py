"""
E2E tests for workflow creation and composition (WORK-04).

Tests workflow creation against the REAL workflow API (core/workflow_endpoints.py
mounted at /api/v1/workflows/workflows — node/connection based WorkflowDefinition,
persisted to backend/workflows.json):

- Creating workflow with multiple skills (nodes)
- Skill reordering within workflow (connection-driven topological order)
- Workflow deletion
- Workflow DAG visualization (enriched node/connection/steps response)
- Workflow cloning (independent copy with identical composition)

Requirements covered:
- WORK-04: User can create workflow with multiple skills via UI
- WORK-04: Workflow composition allows skill ordering and connection
- WORK-04: User can visualize workflow DAG before execution

Run with: pytest backend/tests/e2e_ui/tests/workflows/test_workflow_creation.py -v
"""

import pytest
import uuid
import requests
from typing import Dict, Any, List

# Add backend to path for imports (5 dirnames: tests/e2e_ui/tests/workflows → backend)
import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


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
    """Login via the live backend and return a JWT (workflow:manage required —
    the test_user fixture creates workspace_admin users, matching the real
    bootstrap admin role)."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": test_user.email, "password": "TestPassword123!"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


def make_node(node_id: str, title: str, x: float = 100) -> Dict[str, Any]:
    """Build a real WorkflowNode payload (core/workflow_endpoints.py)."""
    return {
        "id": node_id,
        "type": "action",
        "title": title,
        "description": "",
        "position": {"x": x, "y": 100},
        "config": {"service": "default", "action": "default", "parameters": {}},
        "connections": [],
    }


def make_connection(conn_id: str, source: str, target: str) -> Dict[str, Any]:
    """Build a real WorkflowConnection payload."""
    return {"id": conn_id, "source": source, "target": target}


def build_workflow_payload(name: str, node_ids: List[str], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a full WorkflowDefinition payload (name/description/version/nodes/
    connections/triggers/enabled — the real create contract)."""
    return {
        "name": name,
        "description": f"E2E workflow {name}",
        "version": "1",
        "nodes": [make_node(nid, f"Step {i + 1}", 100 * (i + 1)) for i, nid in enumerate(node_ids)],
        "connections": connections,
        "triggers": [],
        "enabled": True,
    }


def create_workflow(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST the real create endpoint; returns the created workflow dict."""
    response = requests.post(
        WORKFLOWS_API,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Workflow creation failed: {response.text}"
    created = response.json()
    if created.get("id"):
        _CREATED_WORKFLOW_IDS.append(created["id"])
    return created


def get_workflow(token: str, workflow_id: str) -> Dict[str, Any]:
    """GET a workflow by id (404 → None)."""
    response = requests.get(
        f"{WORKFLOWS_API}/{workflow_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code == 404:
        return None
    assert response.status_code == 200, f"Workflow fetch failed: {response.text}"
    return response.json()


def list_workflows(token: str) -> List[Dict[str, Any]]:
    """GET the workflow list (the real endpoint the frontend calls)."""
    response = requests.get(
        WORKFLOWS_API,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Workflow list failed: {response.text}"
    return response.json()


def delete_workflow(token: str, workflow_id: str) -> None:
    """DELETE a workflow by id."""
    response = requests.delete(
        f"{WORKFLOWS_API}/{workflow_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Workflow deletion failed: {response.text}"


def unique_name(prefix: str) -> str:
    return f"{prefix} {str(uuid.uuid4())[:8]}"


# ============================================================================
# Tests
# ============================================================================

def test_create_workflow_with_multiple_skills(test_user):
    """Test creating workflow with multiple skills (WORK-04).

    Real contract: node-based WorkflowDefinition with a linear chain of
    connections; the API responds with the workflow (id) and the enriched
    list must contain it.
    """
    token = get_token(test_user)

    # Two-node chain: n1 -> n2
    name = unique_name("Multi Skill WF")
    payload = build_workflow_payload(
        name,
        ["node-a", "node-b"],
        [make_connection("c1", "node-a", "node-b")],
    )
    created = create_workflow(token, payload)

    # Verify response carries the workflow with its composition
    assert created.get("id"), "No workflow id in create response"
    assert created.get("name") == name, "Workflow name mismatch"
    node_ids = {n["id"] for n in created.get("nodes", [])}
    assert node_ids == {"node-a", "node-b"}, f"Unexpected nodes: {node_ids}"

    # Verify workflow listed by the real list endpoint
    workflows = list_workflows(token)
    listed = [w for w in workflows if w.get("name") == name]
    assert listed, f"Workflow '{name}' not found in list"


def test_workflow_skill_reordering(test_user):
    """Test reordering skills within workflow (WORK-04).

    Reordering is expressed through the connection DAG: the engine's
    topological linearization (core/workflow_engine.py::_convert_nodes_to_steps)
    must reflect the declared order — reversing the connections reverses the
    linearized steps.
    """
    token = get_token(test_user)

    # Nodes a, b, c connected a -> b -> c
    name = unique_name("Reorder WF")
    payload = build_workflow_payload(
        name,
        ["node-r1", "node-r2", "node-r3"],
        [
            make_connection("c1", "node-r1", "node-r2"),
            make_connection("c2", "node-r2", "node-r3"),
        ],
    )
    created = create_workflow(token, payload)

    # The enriched GET response carries the linearized `steps` (topological
    # order — the create response leaves them null)
    created = get_workflow(token, created["id"])
    steps = created.get("steps") or []
    assert len(steps) == 3, f"Expected 3 linearized steps, got {len(steps)}"
    step_ids = [s.get("id") for s in steps]
    assert step_ids == ["node-r1", "node-r2", "node-r3"], \
        f"Topological order wrong: {step_ids}"

    # Reverse order: r3 -> r2 -> r1 must linearize in reverse
    name2 = unique_name("Reorder WF Rev")
    payload2 = build_workflow_payload(
        name2,
        ["node-r1", "node-r2", "node-r3"],
        [
            make_connection("c1", "node-r3", "node-r2"),
            make_connection("c2", "node-r2", "node-r1"),
        ],
    )
    created2 = create_workflow(token, payload2)
    created2 = get_workflow(token, created2["id"])
    steps2 = created2.get("steps") or []
    step_ids2 = [s.get("id") for s in steps2]
    assert step_ids2 == ["node-r3", "node-r2", "node-r1"], \
        f"Reversed topological order wrong: {step_ids2}"


def test_workflow_deletion(test_user):
    """Test deleting workflow (WORK-04).

    Create via the real API, delete via the real API, verify the workflow
    is gone (404 on fetch).
    """
    token = get_token(test_user)

    name = unique_name("Deletion WF")
    payload = build_workflow_payload(name, ["node-d1", "node-d2"], [])
    created = create_workflow(token, payload)
    workflow_id = created["id"]

    # Verify present
    assert get_workflow(token, workflow_id) is not None, "Workflow not created"

    # Delete and verify gone
    delete_workflow(token, workflow_id)
    assert get_workflow(token, workflow_id) is None, \
        "Workflow should be deleted (404 on fetch)"


def test_workflow_visualization(test_user):
    """Test workflow DAG visualization (WORK-04).

    The real "visualization" contract: the enriched workflow response carries
    the full DAG — nodes (one per skill), connections (edges), and linearized
    steps (topological order).
    """
    token = get_token(test_user)

    # 3-node chain: n1 -> n2 -> n3
    name = unique_name("Visualization WF")
    payload = build_workflow_payload(
        name,
        ["node-v1", "node-v2", "node-v3"],
        [
            make_connection("c1", "node-v1", "node-v2"),
            make_connection("c2", "node-v2", "node-v3"),
        ],
    )
    created = create_workflow(token, payload)

    # Nodes visible (one per skill)
    nodes = created.get("nodes", [])
    assert len(nodes) == 3, f"Expected 3 DAG nodes, found {len(nodes)}"

    # Edges visible (connections between skills)
    connections = created.get("connections", [])
    assert len(connections) == 2, f"Expected 2 DAG edges, found {len(connections)}"

    # Linearized steps present with names (enriched GET view)
    created = get_workflow(token, created["id"])
    steps = created.get("steps") or []
    assert created.get("steps_count") == 3, f"Expected steps_count=3, got {created.get('steps_count')}"
    step_names = [s.get("name") for s in steps]
    assert step_names == ["Step 1", "Step 2", "Step 3"], \
        f"Node labels wrong: {step_names}"


def test_workflow_clone(test_user):
    """Test cloning workflow (WORK-04).

    The real API has no dedicated clone endpoint — cloning is creating a new
    workflow (fresh id) with the same node/connection composition. Verify the
    copy is independent (new id) with identical composition.
    """
    token = get_token(test_user)

    # Original
    original_name = unique_name("Original WF")
    payload = build_workflow_payload(
        original_name,
        ["node-c1", "node-c2", "node-c3"],
        [
            make_connection("c1", "node-c1", "node-c2"),
            make_connection("c2", "node-c2", "node-c3"),
        ],
    )
    original = create_workflow(token, payload)
    original_id = original["id"]

    # Clone: same composition, new id, "(Copy)" name
    clone_payload = build_workflow_payload(
        f"{original_name} (Copy)",
        [n["id"] for n in original["nodes"]],
        [dict(c) for c in original["connections"]],
    )
    clone = create_workflow(token, clone_payload)
    clone_id = clone["id"]

    assert clone_id != original_id, "Clone must have an independent id"

    # Fetch both and compare composition
    fetched_original = get_workflow(token, original_id)
    fetched_clone = get_workflow(token, clone_id)

    assert fetched_original is not None and fetched_clone is not None

    original_nodes = {n["id"] for n in fetched_original["nodes"]}
    clone_nodes = {n["id"] for n in fetched_clone["nodes"]}
    assert clone_nodes == original_nodes, \
        f"Clone nodes {clone_nodes} != original nodes {original_nodes}"

    original_conns = {(c["source"], c["target"]) for c in fetched_original["connections"]}
    clone_conns = {(c["source"], c["target"]) for c in fetched_clone["connections"]}
    assert clone_conns == original_conns, \
        f"Clone connections {clone_conns} != original connections {original_conns}"
