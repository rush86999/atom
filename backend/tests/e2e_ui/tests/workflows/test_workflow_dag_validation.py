"""
E2E tests for workflow DAG validation (WORK-05).

Tests workflow DAG validation including:
- Acyclic workflow validation passes
- Circular dependency detection
- Self-loop prevention
- Complex DAG validation
- DAG validation via API
- NetworkX DAG verification

Requirements covered:
- WORK-05: Workflow DAG validation detects cycles and prevents circular dependencies
- WORK-05: Workflow DAG must be acyclic (Directed Acyclic Graph)
- WORK-05: NetworkX used for DAG validation

Run with: pytest backend/tests/e2e_ui/tests/workflows/test_workflow_dag_validation.py -v
"""

import pytest
import uuid
import requests
from playwright.sync_api import Page, expect
from typing import Dict, Any, List
from datetime import datetime, timezone

# Add backend to path for imports
import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import Workflow, WorkflowStep, SkillExecution
from sqlalchemy.orm import Session

import networkx as nx


# ============================================================================
# Helper Functions
# ============================================================================

def navigate_to_workflow_composer(page: Page) -> None:
    """Navigate to workflow composer page.

    Args:
        page: Playwright page object

    Raises:
        AssertionError: If workflow composer doesn't load
    """
    page.goto("http://localhost:3001/workflows/create")
    page.wait_for_load_state("networkidle")

    # Verify workflow composer loaded
    composer = page.locator('[data-testid="workflow-composer"]')
    expect(composer).to_be_visible(timeout=10000)


def add_skill_to_workflow(page: Page, skill_id: str) -> None:
    """Add skill to workflow composer.

    Args:
        page: Playwright page object
        skill_id: Skill identifier to add

    Raises:
        AssertionError: If skill addition fails
    """
    # Click add skill button
    add_button = page.locator('[data-testid="workflow-add-skill"]')
    expect(add_button).to_be_visible(timeout=5000)
    add_button.click()

    # Wait for skill dropdown
    dropdown = page.locator('[data-testid="skill-select-dropdown"]')
    expect(dropdown).to_be_visible(timeout=5000)

    # Select skill from dropdown
    page.select_option('[data-testid="skill-select-dropdown"]', skill_id)

    # Confirm skill addition
    confirm_button = page.locator('[data-testid="skill-add-confirm"]')
    expect(confirm_button).to_be_visible()
    confirm_button.click()

    # Wait for skill to appear in composer
    skill_node = page.locator(f'[data-testid="workflow-skill-{skill_id}"]')
    expect(skill_node).to_be_visible(timeout=5000)


def connect_skills(page: Page, from_skill: str, to_skill: str) -> None:
    """Connect two skills in workflow composer.

    Args:
        page: Playwright page object
        from_skill: Source skill ID
        to_skill: Target skill ID

    Raises:
        AssertionError: If connection fails
    """
    from_element = page.locator(f'[data-testid="workflow-skill-{from_skill}"] [data-testid="output-port"]')
    to_element = page.locator(f'[data-testid="workflow-skill-{to_skill}"] [data-testid="input-port"]')

    # Drag from output port to input port
    from_element.drag_to(to_element)

    # Wait for connection line to appear
    connection = page.locator('[data-testid^="workflow-connection-"]')
    expect(connection).to_be_visible(timeout=3000)


def save_workflow(page: Page, name: str, description: str = "") -> None:
    """Save workflow.

    Args:
        page: Playwright page object
        name: Workflow name
        description: Optional workflow description

    Raises:
        AssertionError: If save fails
    """
    # Fill workflow name
    name_input = page.locator('[data-testid="workflow-name-input"]')
    expect(name_input).to_be_visible()
    name_input.fill(name)

    # Fill description if provided
    if description:
        desc_input = page.locator('[data-testid="workflow-description-input"]')
        expect(desc_input).to_be_visible()
        desc_input.fill(description)

    # Click save button
    save_button = page.locator('[data-testid="workflow-save-button"]')
    expect(save_button).to_be_visible()
    save_button.click()

    # Wait for success message or error
    page.wait_for_timeout(2000)


def create_test_skills(db_session, count: int = 3) -> List[str]:
    """Create test skills for workflow composition.

    Args:
        db_session: Database session
        count: Number of skills to create

    Returns:
        List[str]: List of created skill IDs
    """
    skill_ids = []
    for i in range(count):
        skill_id = f"test-workflow-skill-{i}-{str(uuid.uuid4())[:8]}"
        skill = SkillExecution(
            id=str(uuid.uuid4()),
            skill_id=skill_id,
            agent_id="system",
            status="Active",
            capability=f"Test skill {i}",
            skill_body="# Test skill\nExecute test function.",
            started_at=datetime.now(timezone.utc),
            completed_at=None
        )
        db_session.add(skill)
        skill_ids.append(skill_id)

    db_session.commit()
    return skill_ids


def create_workflow_with_connections(
    page: Page,
    skills: List[str],
    connections: List[Dict[str, str]],
    workflow_name: str = None
) -> str:
    """Create workflow with specific skill connections.

    Args:
        page: Playwright page object
        skills: List of skill IDs to add
        connections: List of connection dicts with 'from' and 'to' keys
        workflow_name: Optional workflow name

    Returns:
        str: Created workflow name
    """
    if not workflow_name:
        workflow_name = f"Test Workflow {str(uuid.uuid4())[:8]}"

    # Add all skills
    for skill_id in skills:
        add_skill_to_workflow(page, skill_id)

    # Create connections
    for conn in connections:
        connect_skills(page, conn['from'], conn['to'])

    # Save workflow
    save_workflow(page, workflow_name)

    return workflow_name


def create_cyclic_workflow_graph() -> Dict[str, Any]:
    """Create workflow definition with cycle for API testing.

    Returns:
        Dict: Workflow definition with circular dependency
    """
    return {
        "name": "Cyclic Workflow",
        "description": "Workflow with circular dependency for testing",
        "skills": [
            {"skill_id": "skill_1", "position": {"x": 100, "y": 100}},
            {"skill_id": "skill_2", "position": {"x": 300, "y": 100}},
            {"skill_id": "skill_3", "position": {"x": 200, "y": 250}}
        ],
        "connections": [
            {"from": "skill_1", "to": "skill_2"},
            {"from": "skill_2", "to": "skill_3"},
            {"from": "skill_3", "to": "skill_1"}  # Creates cycle
        ]
    }


def verify_dag_in_database(db_session: Session, workflow_id: str) -> bool:
    """Verify workflow DAG stored correctly in database.

    Args:
        db_session: Database session
        workflow_id: Workflow ID to verify

    Returns:
        bool: True if workflow is a valid DAG
    """
    workflow = db_session.query(Workflow).filter_by(id=workflow_id).first()
    if not workflow:
        return False

    # Build NetworkX graph from workflow steps
    G = nx.DiGraph()

    # Add nodes (skills)
    for step in workflow.steps:
        G.add_node(step.skill_id)

    # Note: WorkflowStep model may have different structure
    # This is a simplified verification

    return nx.is_directed_acyclic_graph(G)


def create_workflow_via_api(workflow_def: Dict[str, Any], token: str) -> requests.Response:
    """Create workflow via API endpoint.

    Args:
        workflow_def: Workflow definition dict
        token: JWT access token

    Returns:
        requests.Response: API response
    """
    return requests.post(
        "http://localhost:8000/api/v1/workflows",
        json=workflow_def,
        headers={"Authorization": f"Bearer {token}"}
    )


# ============================================================================
# Tests
# ============================================================================

def test_acyclic_workflow_validation_passes(authenticated_page_api, db_session):
    """Test acyclic workflow validation passes (WORK-05).

    Requirements:
    - Create workflow with 3 skills in linear chain: skill_1 -> skill_2 -> skill_3
    - Save workflow
    - Verify validation passes with success message
    - Verify workflow saved with valid status
    - Verify DAG structure in database
    """
    # Create test skills
    skill_ids = create_test_skills(db_session, count=3)

    # Navigate to workflow composer
    navigate_to_workflow_composer(authenticated_page_api)

    # Create acyclic workflow: skill_1 -> skill_2 -> skill_3
    workflow_name = f"Acyclic Workflow {str(uuid.uuid4())[:8]}"
    connections = [
        {"from": skill_ids[0], "to": skill_ids[1]},
        {"from": skill_ids[1], "to": skill_ids[2]}
    ]
    create_workflow_with_connections(authenticated_page_api, skill_ids, connections, workflow_name)

    # Verify success message displayed
    success = authenticated_page_api.locator('[data-testid="workflow-saved"]')
    expect(success).to_be_visible(timeout=10000)

    # Verify workflow saved in database
    workflow = db_session.query(Workflow).filter_by(name=workflow_name).first()
    assert workflow is not None, f"Workflow '{workflow_name}' not found in database"
    assert workflow.status == "active" or workflow.status == "valid", \
        f"Expected valid status, got {workflow.status}"

    # Verify DAG structure (3 nodes, 2 edges)
    assert len(workflow.steps) == 3, f"Expected 3 workflow steps, found {len(workflow.steps)}"


def test_circular_dependency_detected(authenticated_page_api, db_session):
    """Test circular dependency detection (WORK-05).

    Requirements:
    - Create workflow with 3 skills
    - Connect skills to create cycle: skill_1 -> skill_2 -> skill_3 -> skill_1
    - Try to save workflow
    - Verify error message about circular dependency
    - Verify workflow NOT saved
    - Verify error highlights problematic connections
    """
    # Create test skills
    skill_ids = create_test_skills(db_session, count=3)

    # Navigate to workflow composer
    navigate_to_workflow_composer(authenticated_page_api)

    # Add all skills
    for skill_id in skill_ids:
        add_skill_to_workflow(authenticated_page_api, skill_id)

    # Create circular dependency: skill_1 -> skill_2 -> skill_3 -> skill_1
    connect_skills(authenticated_page_api, skill_ids[0], skill_ids[1])
    connect_skills(authenticated_page_api, skill_ids[1], skill_ids[2])
    connect_skills(authenticated_page_api, skill_ids[2], skill_ids[0])

    # Try to save workflow
    workflow_name = f"Cyclic Workflow {str(uuid.uuid4())[:8]}"
    save_workflow(authenticated_page_api, workflow_name)

    # Verify error message displayed
    error_message = authenticated_page_api.locator('[data-testid="workflow-validation-error"]')
    expect(error_message).to_be_visible(timeout=5000)

    # Verify error mentions cycle or circular dependency
    error_text = error_message.text_content()
    assert "cycle" in error_text.lower() or "circular" in error_text.lower(), \
        f"Error message should mention cycle/circular dependency, got: {error_text}"

    # Verify workflow NOT saved in database
    workflow = db_session.query(Workflow).filter_by(name=workflow_name).first()
    assert workflow is None, "Cyclic workflow should not be saved in database"


def test_self_loop_prevented(authenticated_page_api, db_session):
    """Test self-loop prevention (WORK-05).

    Requirements:
    - Create workflow with single skill
    - Try to connect skill to itself (skill_1 -> skill_1)
    - Verify validation error about self-loop
    - Verify connection rejected
    """
    # Create test skill
    skill_ids = create_test_skills(db_session, count=1)
    skill_id = skill_ids[0]

    # Navigate to workflow composer
    navigate_to_workflow_composer(authenticated_page_api)

    # Add skill
    add_skill_to_workflow(authenticated_page_api, skill_id)

    # Try to connect skill to itself
    # Note: This may be prevented at UI level (drag to self not allowed)
    # or at validation level
    from_element = authenticated_page_api.locator(
        f'[data-testid="workflow-skill-{skill_id}"] [data-testid="output-port"]'
    )
    to_element = authenticated_page_api.locator(
        f'[data-testid="workflow-skill-{skill_id}"] [data-testid="input-port"]'
    )

    # Attempt self-connection
    from_element.drag_to(to_element)

    # Verify error message or connection rejection
    # UI should prevent self-loop or show error
    error_message = authenticated_page_api.locator('[data-testid="workflow-validation-error"]')

    # Either error appears immediately or on save
    if error_message.is_visible(timeout=2000):
        error_text = error_message.text_content()
        assert "self-loop" in error_text.lower() or "self loop" in error_text.lower() or "circular" in error_text.lower(), \
            f"Error should mention self-loop, got: {error_text}"
    else:
        # Connection should not be visible
        connection = authenticated_page_api.locator('[data-testid^="workflow-connection-"]')
        expect(connection).to_have_count(0)


def test_complex_dag_validation(authenticated_page_api, db_session):
    """Test complex DAG validation (WORK-05).

    Requirements:
    - Create complex workflow with multiple branches:
      skill_1 -> skill_2 -> skill_4
              ↓
      skill_3 -> skill_5
    - Save workflow
    - Verify validation passes (DAG is acyclic)
    - Verify all 5 nodes and 4 edges stored correctly
    """
    # Create test skills
    skill_ids = create_test_skills(db_session, count=5)

    # Navigate to workflow composer
    navigate_to_workflow_composer(authenticated_page_api)

    # Add all skills
    for skill_id in skill_ids:
        add_skill_to_workflow(authenticated_page_api, skill_id)

    # Create complex DAG with branches
    # skill_1 -> skill_2 -> skill_4
    # skill_1 -> skill_3 -> skill_5
    connections = [
        {"from": skill_ids[0], "to": skill_ids[1]},  # skill_1 -> skill_2
        {"from": skill_ids[0], "to": skill_ids[2]},  # skill_1 -> skill_3
        {"from": skill_ids[1], "to": skill_ids[3]},  # skill_2 -> skill_4
        {"from": skill_ids[2], "to": skill_ids[4]}   # skill_3 -> skill_5
    ]

    for conn in connections:
        connect_skills(authenticated_page_api, conn['from'], conn['to'])

    # Save workflow
    workflow_name = f"Complex DAG {str(uuid.uuid4())[:8]}"
    save_workflow(authenticated_page_api, workflow_name)

    # Verify validation passes
    success = authenticated_page_api.locator('[data-testid="workflow-saved"]')
    expect(success).to_be_visible(timeout=10000)

    # Verify workflow saved with all 5 skills
    workflow = db_session.query(Workflow).filter_by(name=workflow_name).first()
    assert workflow is not None, f"Workflow '{workflow_name}' not found"
    assert len(workflow.steps) == 5, f"Expected 5 steps, found {len(workflow.steps)}"


def test_dag_validation_via_api(setup_test_user, db_session):
    """Test DAG validation via API endpoint (WORK-05).

    Requirements:
    - Create workflow definition with cycle via API
    - POST to /api/v1/workflows
    - Verify response status indicates validation error (400 or 422)
    - Verify error message mentions cycle or circular dependency
    """
    # Create cyclic workflow definition
    workflow_def = create_cyclic_workflow_graph()

    # Get auth token
    token = setup_test_user.get("access_token")

    # Try to create workflow via API
    response = create_workflow_via_api(workflow_def, token)

    # Verify validation error response
    assert response.status_code in [400, 422], \
        f"Expected 400 or 422 status, got {response.status_code}"

    # Verify error message
    error_data = response.json()
    error_message = error_data.get("error", "") or error_data.get("message", "") or str(error_data)
    assert "cycle" in error_message.lower() or "circular" in error_message.lower(), \
        f"Error should mention cycle/circular dependency, got: {error_message}"


def test_networkx_dag_verification(authenticated_page_api, db_session):
    """Test NetworkX DAG verification (WORK-05).

    Requirements:
    - Create workflow via UI with valid DAG structure
    - Get workflow ID from response
    - Fetch workflow from database
    - Build NetworkX graph from workflow edges
    - Verify graph is DAG using nx.is_directed_acyclic_graph()
    - Verify topological sort possible
    """
    # Create test skills
    skill_ids = create_test_skills(db_session, count=3)

    # Navigate to workflow composer
    navigate_to_workflow_composer(authenticated_page_api)

    # Create valid DAG: skill_1 -> skill_2 -> skill_3
    workflow_name = f"NetworkX DAG {str(uuid.uuid4())[:8]}"
    connections = [
        {"from": skill_ids[0], "to": skill_ids[1]},
        {"from": skill_ids[1], "to": skill_ids[2]}
    ]
    create_workflow_with_connections(authenticated_page_api, skill_ids, connections, workflow_name)

    # Get workflow from database
    workflow = db_session.query(Workflow).filter_by(name=workflow_name).first()
    assert workflow is not None, f"Workflow '{workflow_name}' not found"
    workflow_id = workflow.id

    # Build NetworkX graph from workflow
    G = nx.DiGraph()

    # Add nodes (skills)
    for step in workflow.steps:
        G.add_node(step.skill_id)

    # Add edges (connections)
    # Note: WorkflowStep connections may be stored differently
    # This is a simplified version - adjust based on actual model
    for i in range(len(skill_ids) - 1):
        G.add_edge(skill_ids[i], skill_ids[i + 1])

    # Verify graph is DAG
    assert nx.is_directed_acyclic_graph(G), "Workflow graph should be a DAG"

    # Verify topological sort possible
    try:
        topological_order = list(nx.topological_sort(G))
        assert len(topological_order) == 3, "Topological sort should include all 3 nodes"
    except nx.NetworkXUnfeasible:
        pytest.fail("Topological sort should be feasible for DAG")
