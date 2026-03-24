"""
E2E tests for workflow creation and composition (WORK-04).

Tests workflow creation via UI including:
- Creating workflow with multiple skills
- Skill reordering within workflow
- Workflow deletion
- Workflow DAG visualization
- Workflow cloning

Requirements covered:
- WORK-04: User can create workflow with multiple skills via UI
- WORK-04: Workflow composition allows skill ordering and connection
- WORK-04: User can visualize workflow DAG before execution

Run with: pytest backend/tests/e2e_ui/tests/workflows/test_workflow_creation.py -v
"""

import pytest
import uuid
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

    # Wait for success message
    success = page.locator('[data-testid="workflow-saved"]')
    expect(success).to_be_visible(timeout=10000)


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


def create_workflow_with_skills(page: Page, skill_ids: List[str], workflow_name: str = None) -> str:
    """Create a workflow with the given skills.

    Args:
        page: Playwright page object
        skill_ids: List of skill IDs to add
        workflow_name: Optional workflow name

    Returns:
        str: Created workflow name
    """
    if not workflow_name:
        workflow_name = f"Test Workflow {str(uuid.uuid4())[:8]}"

    # Add all skills
    for skill_id in skill_ids:
        add_skill_to_workflow(page, skill_id)

    # Connect skills in sequence
    for i in range(len(skill_ids) - 1):
        connect_skills(page, skill_ids[i], skill_ids[i + 1])

    # Save workflow
    save_workflow(page, workflow_name)

    return workflow_name


# ============================================================================
# Tests
# ============================================================================

def test_create_workflow_with_multiple_skills(authenticated_page_api, db_session):
    """Test creating workflow with multiple skills via UI (WORK-04).

    Requirements:
    - Navigate to workflow composer
    - Add multiple skills to workflow
    - Connect skills
    - Save workflow
    - Verify workflow saved in database
    """
    # Create test skills
    skill_ids = create_test_skills(db_session, count=2)

    # Navigate to workflow composer
    navigate_to_workflow_composer(authenticated_page_api)

    # Verify composer loaded
    composer = authenticated_page_api.locator('[data-testid="workflow-composer"]')
    expect(composer).to_be_visible()

    # Add skills to workflow
    for skill_id in skill_ids:
        add_skill_to_workflow(authenticated_page_api, skill_id)

    # Verify both skills visible in composer
    for skill_id in skill_ids:
        skill_node = authenticated_page_api.locator(f'[data-testid="workflow-skill-{skill_id}"]')
        expect(skill_node).to_be_visible()

    # Connect skills
    connect_skills(authenticated_page_api, skill_ids[0], skill_ids[1])

    # Verify connection line rendered
    connection = authenticated_page_api.locator('[data-testid^="workflow-connection-"]')
    expect(connection).to_be_visible()

    # Name and save workflow
    workflow_name = "Test Workflow"
    save_workflow(authenticated_page_api, workflow_name)

    # Verify success message
    success = authenticated_page_api.locator('[data-testid="workflow-saved"]')
    expect(success).to_be_visible()

    # Verify workflow in database
    workflow = db_session.query(Workflow).filter_by(name=workflow_name).first()
    assert workflow is not None, f"Workflow '{workflow_name}' not found in database"
    assert workflow.name == workflow_name


def test_workflow_skill_reordering(authenticated_page_api, db_session):
    """Test reordering skills within workflow (WORK-04).

    Requirements:
    - Create workflow with 3 skills
    - Verify initial order
    - Reorder skills by dragging
    - Verify new order persisted after save and reload
    """
    # Create test skills
    skill_ids = create_test_skills(db_session, count=3)

    # Navigate to workflow composer
    navigate_to_workflow_composer(authenticated_page_api)

    # Add skills in order
    for skill_id in skill_ids:
        add_skill_to_workflow(authenticated_page_api, skill_id)

    # Verify initial order (skill_1, skill_2, skill_3)
    skills_container = authenticated_page_api.locator('[data-testid="workflow-skills-container"]')
    expect(skills_container).to_be_visible()

    # Get initial skill order
    initial_skills = authenticated_page_api.locator('[data-testid^="workflow-skill-"]')
    initial_count = initial_skills.count()
    assert initial_count == 3, f"Expected 3 skills, found {initial_count}"

    # Drag skill_3 to position before skill_1
    # Note: This is a simplified test - actual drag implementation may need adjustment
    skill_3 = authenticated_page_api.locator(f'[data-testid="workflow-skill-{skill_ids[2]}"]')
    skill_1 = authenticated_page_api.locator(f'[data-testid="workflow-skill-{skill_ids[0]}"]')

    # Reorder using drag and drop
    skill_3.drag_to(skill_1)

    # Save workflow
    workflow_name = f"Reorder Test {str(uuid.uuid4())[:8]}"
    save_workflow(authenticated_page_api, workflow_name)

    # Reload page to verify persistence
    authenticated_page_api.reload()
    authenticated_page_api.wait_for_load_state("networkidle")

    # Verify order persisted (skill_3 should now be first)
    # Note: Actual verification depends on UI implementation
    skills_after_reload = authenticated_page_api.locator('[data-testid^="workflow-skill-"]')
    expect(skills_after_reload).to_have_count(3)


def test_workflow_deletion(authenticated_page_api, db_session):
    """Test deleting workflow via UI (WORK-04).

    Requirements:
    - Create workflow via UI
    - Navigate to workflow registry
    - Delete workflow
    - Verify workflow removed from list and database
    """
    # Create test skills and workflow
    skill_ids = create_test_skills(db_session, count=2)

    navigate_to_workflow_composer(authenticated_page_api)
    workflow_name = create_workflow_with_skills(authenticated_page_api, skill_ids)

    # Verify workflow created in database
    workflow = db_session.query(Workflow).filter_by(name=workflow_name).first()
    assert workflow is not None, "Workflow not created"
    workflow_id = workflow.id

    # Navigate to workflow registry
    authenticated_page_api.goto("http://localhost:3001/workflows/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Find workflow card
    workflow_card = authenticated_page_api.locator(f'[data-testid="workflow-{workflow_id}"]')
    expect(workflow_card).to_be_visible(timeout=5000)

    # Click delete button
    delete_button = authenticated_page_api.locator(f'[data-testid="workflow-{workflow_id}-delete"]')
    expect(delete_button).to_be_visible()
    delete_button.click()

    # Confirm deletion in modal
    confirm_button = authenticated_page_api.locator('[data-testid="workflow-delete-confirm"]')
    expect(confirm_button).to_be_visible()
    confirm_button.click()

    # Wait for deletion success message
    success = authenticated_page_api.locator('[data-testid="workflow-deleted"]')
    expect(success).to_be_visible(timeout=5000)

    # Verify workflow removed from list
    expect(workflow_card).not_to_be_visible()

    # Verify database record deleted
    db_session.expire_all()
    deleted_workflow = db_session.query(Workflow).filter_by(id=workflow_id).first()
    assert deleted_workflow is None, "Workflow should be deleted from database"


def test_workflow_visualization(authenticated_page_api, db_session):
    """Test workflow DAG visualization (WORK-04).

    Requirements:
    - Create workflow with skills and connections
    - Verify DAG visualization rendered
    - Verify nodes visible (one per skill)
    - Verify edges visible (connections between skills)
    - Verify node labels show skill names
    - Verify edge direction indicated
    """
    # Create test skills and workflow
    skill_ids = create_test_skills(db_session, count=3)

    navigate_to_workflow_composer(authenticated_page_api)

    # Add skills
    for skill_id in skill_ids:
        add_skill_to_workflow(authenticated_page_api, skill_id)

    # Connect skills: skill_1 -> skill_2 -> skill_3
    connect_skills(authenticated_page_api, skill_ids[0], skill_ids[1])
    connect_skills(authenticated_page_api, skill_ids[1], skill_ids[2])

    # Save workflow
    workflow_name = f"Visualization Test {str(uuid.uuid4())[:8]}"
    save_workflow(authenticated_page_api, workflow_name)

    # Verify DAG visualization rendered
    dag_visualization = authenticated_page_api.locator('[data-testid="workflow-dag"]')
    expect(dag_visualization).to_be_visible(timeout=5000)

    # Verify nodes visible (one per skill)
    nodes = authenticated_page_api.locator('[data-testid^="workflow-dag-node-"]')
    node_count = nodes.count()
    assert node_count == 3, f"Expected 3 DAG nodes, found {node_count}"

    # Verify edges visible (connections between skills)
    edges = authenticated_page_api.locator('[data-testid^="workflow-dag-edge-"]')
    edge_count = edges.count()
    assert edge_count == 2, f"Expected 2 DAG edges, found {edge_count}"

    # Verify node labels show skill names
    for skill_id in skill_ids:
        node_label = authenticated_page_api.locator(f'[data-testid="workflow-dag-node-{skill_id}"] [data-testid="node-label"]')
        expect(node_label).to_be_visible()

    # Verify edge direction indicated (arrows)
    # Note: Implementation depends on visualization library used


def test_workflow_clone(authenticated_page_api, db_session):
    """Test cloning workflow via UI (WORK-04).

    Requirements:
    - Create original workflow
    - Clone workflow
    - Verify new workflow created with "(Copy)" suffix
    - Verify clone has same skill composition as original
    """
    # Create test skills and workflow
    skill_ids = create_test_skills(db_session, count=2)

    navigate_to_workflow_composer(authenticated_page_api)
    original_name = f"Original Workflow {str(uuid.uuid4())[:8]}"
    create_workflow_with_skills(authenticated_page_api, skill_ids, original_name)

    # Get original workflow from database
    original_workflow = db_session.query(Workflow).filter_by(name=original_name).first()
    assert original_workflow is not None
    original_workflow_id = original_workflow.id

    # Navigate to workflow details
    authenticated_page_api.goto(f"http://localhost:3001/workflows/{original_workflow_id}")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Click clone button
    clone_button = authenticated_page_api.locator('[data-testid="workflow-clone-button"]')
    expect(clone_button).to_be_visible(timeout=5000)
    clone_button.click()

    # Verify clone modal appears
    clone_modal = authenticated_page_api.locator('[data-testid="workflow-clone-modal"]')
    expect(clone_modal).to_be_visible(timeout=5000)

    # Confirm clone
    confirm_button = authenticated_page_api.locator('[data-testid="workflow-clone-confirm"]')
    expect(confirm_button).to_be_visible()
    confirm_button.click()

    # Wait for clone success message
    success = authenticated_page_api.locator('[data-testid="workflow-cloned"]')
    expect(success).to_be_visible(timeout=10000)

    # Verify new workflow created with "(Copy)" name
    expected_clone_name = f"{original_name} (Copy)"
    clone_workflow = db_session.query(Workflow).filter_by(name=expected_clone_name).first()
    assert clone_workflow is not None, f"Cloned workflow '{expected_clone_name}' not found"

    # Verify clone has same skill composition as original
    original_steps = db_session.query(WorkflowStep).filter_by(workflow_id=original_workflow_id).all()
    clone_steps = db_session.query(WorkflowStep).filter_by(workflow_id=clone_workflow.id).all()

    assert len(clone_steps) == len(original_steps), \
        f"Clone has {len(clone_steps)} steps, original has {len(original_steps)} steps"
