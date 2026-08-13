"""
E2E tests for workflow DAG validation (WORK-05).

Tests workflow DAG validation against the REAL engine + API contract:

- The workflow engine (core/workflow_engine.py::WorkflowEngine) linearizes
  node/connection graphs with Kahn's topological sort and raises ValueError
  ("Workflow contains circular dependencies") when a cycle is present.
- The API accepts any WorkflowDefinition at create time; cycle rejection
  happens at execution time (POST /api/v1/workflows/workflows/{id}/execute
  → 500 when the engine detects the cycle).
- NetworkX is the test-side oracle: rebuild the graph from the real API
  response and verify it is a DAG with a topological ordering.

Requirements covered:
- WORK-05: Workflow DAG validation detects cycles and prevents circular dependencies
- WORK-05: Workflow DAG must be acyclic (Directed Acyclic Graph)
- WORK-05: NetworkX used for DAG validation

Run with: pytest backend/tests/e2e_ui/tests/workflows/test_workflow_dag_validation.py -v
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

import networkx as nx

from core.workflow_engine import WorkflowEngine


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


def make_node(node_id: str, title: str, x: float = 100) -> Dict[str, Any]:
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
    return {"id": conn_id, "source": source, "target": target}


def build_workflow_payload(name: str, node_ids: List[str], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "name": name,
        "description": f"E2E DAG workflow {name}",
        "version": "1",
        "nodes": [make_node(nid, f"Step {i + 1}", 100 * (i + 1)) for i, nid in enumerate(node_ids)],
        "connections": connections,
        "triggers": [],
        "enabled": True,
    }


def create_workflow(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
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
    """GET a workflow (the enriched view — carries linearized steps)."""
    response = requests.get(
        f"{WORKFLOWS_API}/{workflow_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Workflow fetch failed: {response.text}"
    return response.json()


def execute_workflow(token: str, workflow_id: str) -> requests.Response:
    """POST the real execute endpoint — returns the raw response (the cycle
    rejection surfaces as an HTTP 500 from the engine's ValueError)."""
    return requests.post(
        f"{WORKFLOWS_API}/{workflow_id}/execute",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )


def unique_name(prefix: str) -> str:
    return f"{prefix} {str(uuid.uuid4())[:8]}"


def assert_engine_rejects_cycle(workflow_payload: Dict[str, Any]) -> None:
    """Drive the REAL engine (core.workflow_engine.py) directly: converting a
    cyclic node graph must raise ValueError mentioning circular dependencies —
    this is the authoritative validation the execute path relies on."""
    engine = WorkflowEngine()
    with pytest.raises(ValueError) as excinfo:
        engine._convert_nodes_to_steps(workflow_payload)
    assert "circular" in str(excinfo.value).lower(), \
        f"Engine error should mention circular dependencies, got: {excinfo.value}"


# ============================================================================
# Tests
# ============================================================================

def test_acyclic_workflow_validation_passes(test_user):
    """Test acyclic workflow validation passes (WORK-05).

    A linear chain (n1 -> n2 -> n3) must create successfully, linearize to
    3 steps in topological order, and execute (execution starts — the API
    returns an execution id).
    """
    token = get_token(test_user)

    name = unique_name("Acyclic WF")
    payload = build_workflow_payload(
        name,
        ["node-a1", "node-a2", "node-a3"],
        [
            make_connection("c1", "node-a1", "node-a2"),
            make_connection("c2", "node-a2", "node-a3"),
        ],
    )

    # Engine-level: acyclic graph converts without error
    engine = WorkflowEngine()
    steps = engine._convert_nodes_to_steps(payload)
    assert len(steps) == 3, f"Expected 3 linearized steps, got {len(steps)}"
    assert [s["id"] for s in steps] == ["node-a1", "node-a2", "node-a3"], \
        f"Topological order wrong: {steps}"

    # API-level: create + execute both succeed (the enriched GET carries the
    # linearized steps — the create response leaves them null)
    created = create_workflow(token, payload)
    created = get_workflow(token, created["id"])
    assert created.get("steps_count") == 3, f"Expected steps_count=3, got {created.get('steps_count')}"

    exec_response = execute_workflow(token, created["id"])
    assert exec_response.status_code == 200, f"Execution should start: {exec_response.text}"
    assert exec_response.json().get("execution_id"), "No execution_id in execute response"


def test_circular_dependency_detected(test_user):
    """Test circular dependency detection (WORK-05).

    A cycle n1 -> n2 -> n3 -> n1 must be rejected by the engine (ValueError)
    AND by the create API (HTTP 400 with a circular-dependency message) —
    cyclic definitions never enter the workflow store.
    """
    token = get_token(test_user)

    name = unique_name("Cyclic WF")
    payload = build_workflow_payload(
        name,
        ["node-c1", "node-c2", "node-c3"],
        [
            make_connection("c1", "node-c1", "node-c2"),
            make_connection("c2", "node-c2", "node-c3"),
            make_connection("c3", "node-c3", "node-c1"),  # Creates cycle
        ],
    )

    # Engine-level rejection (the authoritative validation)
    assert_engine_rejects_cycle(payload)

    # API-level: create rejects the cyclic definition with a 400 + message
    response = requests.post(
        WORKFLOWS_API,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400, \
        f"Expected 400 on cyclic creation, got {response.status_code}: {response.text}"
    assert "circular" in response.text.lower(), \
        f"Error should mention circular dependencies: {response.text}"


def test_self_loop_prevented(test_user):
    """Test self-loop prevention (WORK-05).

    A self-loop (n1 -> n1) is a cycle: the engine must reject it and the
    create API must reject the definition with a 400.
    """
    token = get_token(test_user)

    name = unique_name("Self Loop WF")
    payload = build_workflow_payload(
        name,
        ["node-s1"],
        [make_connection("c1", "node-s1", "node-s1")],  # Self-loop
    )

    assert_engine_rejects_cycle(payload)

    response = requests.post(
        WORKFLOWS_API,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400, \
        f"Expected 400 on self-loop creation, got {response.status_code}: {response.text}"


def test_complex_dag_validation(test_user):
    """Test complex DAG validation (WORK-05).

    Branching DAG: n1 -> n2 -> n4 and n1 -> n3 -> n5. Must linearize to all
    5 nodes (topological order), 4 edges, and execute.
    """
    token = get_token(test_user)

    name = unique_name("Complex DAG WF")
    payload = build_workflow_payload(
        name,
        ["node-x1", "node-x2", "node-x3", "node-x4", "node-x5"],
        [
            make_connection("c1", "node-x1", "node-x2"),
            make_connection("c2", "node-x1", "node-x3"),
            make_connection("c3", "node-x2", "node-x4"),
            make_connection("c4", "node-x3", "node-x5"),
        ],
    )

    # Engine-level: 5 steps, valid topological order
    engine = WorkflowEngine()
    steps = engine._convert_nodes_to_steps(payload)
    assert len(steps) == 5, f"Expected 5 steps, found {len(steps)}"
    assert steps[0]["id"] == "node-x1", f"Root node should linearize first: {steps}"

    # API-level: create succeeds with all 5 nodes + 4 connections; the
    # enriched GET linearizes all 5 steps
    created = create_workflow(token, payload)
    assert len(created.get("nodes", [])) == 5, "Expected 5 nodes in response"
    assert len(created.get("connections", [])) == 4, "Expected 4 connections in response"
    enriched = get_workflow(token, created["id"])
    assert enriched.get("steps_count") == 5, f"Expected steps_count=5, got {enriched.get('steps_count')}"

    exec_response = execute_workflow(token, created["id"])
    assert exec_response.status_code == 200, f"Execution should start: {exec_response.text}"


def test_dag_validation_via_api(test_user):
    """Test DAG validation via API endpoint (WORK-05).

    A cyclic definition POSTed to /api/v1/workflows/workflows must be rejected
    with a 400 whose message names the circular dependency (the engine's
    authoritative cycle detection surfaced by the create endpoint).
    """
    token = get_token(test_user)

    name = unique_name("API Cycle WF")
    payload = build_workflow_payload(
        name,
        ["node-p1", "node-p2", "node-p3"],
        [
            make_connection("c1", "node-p1", "node-p2"),
            make_connection("c2", "node-p2", "node-p3"),
            make_connection("c3", "node-p3", "node-p1"),
        ],
    )

    response = requests.post(
        WORKFLOWS_API,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    # The API refuses to create a cyclic workflow
    assert response.status_code == 400, \
        f"Expected 400 on cyclic creation, got {response.status_code}: {response.text}"

    # Verify error message mentions the cycle
    error_data = response.json()
    error_message = error_data.get("detail", "") or str(error_data)
    assert "circular" in error_message.lower(), \
        f"Error should mention circular dependencies, got: {error_message}"


def test_networkx_dag_verification(test_user):
    """Test NetworkX DAG verification (WORK-05).

    Create a valid DAG via the API, rebuild the graph with NetworkX from the
    REAL API response (nodes + connections), verify:
    - nx.is_directed_acyclic_graph() is True
    - a topological sort covering all 3 nodes exists
    """
    token = get_token(test_user)

    name = unique_name("NetworkX DAG WF")
    payload = build_workflow_payload(
        name,
        ["node-n1", "node-n2", "node-n3"],
        [
            make_connection("c1", "node-n1", "node-n2"),
            make_connection("c2", "node-n2", "node-n3"),
        ],
    )
    created = create_workflow(token, payload)

    # Rebuild the graph from the real response payload
    G = nx.DiGraph()
    for node in created["nodes"]:
        G.add_node(node["id"])
    for conn in created["connections"]:
        G.add_edge(conn["source"], conn["target"])

    # Verify graph is a DAG
    assert nx.is_directed_acyclic_graph(G), "Workflow graph should be a DAG"

    # Verify topological sort possible (covers all 3 nodes)
    try:
        topological_order = list(nx.topological_sort(G))
        assert len(topological_order) == 3, "Topological sort should include all 3 nodes"
        assert topological_order == ["node-n1", "node-n2", "node-n3"], \
            f"Topological order wrong: {topological_order}"
    except nx.NetworkXUnfeasible:
        pytest.fail("Topological sort should be feasible for DAG")

    # Negative control: the same graph WITH a cycle must fail the oracle
    G_cyclic = G.copy()
    G_cyclic.add_edge("node-n3", "node-n1")
    assert not nx.is_directed_acyclic_graph(G_cyclic), \
        "Cyclic graph must fail the NetworkX DAG oracle"
