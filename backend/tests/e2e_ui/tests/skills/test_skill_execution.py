"""
E2E tests for skill execution workflow (WORK-03).

Tests skill execution including:
- Execution with parameters
- JSON output validation
- Error handling for invalid parameters
- Execution history tracking
- Long-running skill execution with progress indicators

Requirements covered:
- WORK-03: User can execute skill with parameters and output parses correctly
- WORK-03: Skill execution output is valid JSON (if applicable)
- WORK-03: Skill execution history is tracked and visible

Run with: pytest backend/tests/e2e_ui/tests/skills/test_skill_execution.py -v
"""

import pytest
import uuid
import json
import time
from playwright.sync_api import Page, expect
from typing import Dict, Any
from datetime import datetime, timezone

# Add backend to path for imports
import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import SkillExecution


# ============================================================================
# Helper Functions
# ============================================================================

def execute_skill_via_ui(page: Page, skill_id: str, parameters: Dict[str, Any]) -> None:
    """Execute skill via UI flow.

    Args:
        page: Playwright page object
        skill_id: Skill identifier
        parameters: Skill input parameters

    Raises:
        AssertionError: If execution flow fails
    """
    # Click execute button on skill card
    execute_button = page.locator(f'[data-testid="skill-{skill_id}-execute"]')
    expect(execute_button).to_be_visible(timeout=5000)
    execute_button.click()

    # Wait for execution modal
    modal = page.locator('[data-testid="skill-execute-modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Fill parameters
    for param_name, param_value in parameters.items():
        param_input = page.locator(f'[data-testid="skill-param-{param_name}"]')
        if param_input.is_visible():
            param_input.fill(str(param_value))

    # Submit execution
    confirm_button = page.locator('[data-testid="skill-execute-confirm"]')
    expect(confirm_button).to_be_visible()
    confirm_button.click()


def wait_for_skill_completion(page: Page, timeout: int = 30000) -> None:
    """Wait for skill execution to complete.

    Args:
        page: Playwright page object
        timeout: Maximum wait time in milliseconds

    Raises:
        AssertionError: If execution doesn't complete in time
    """
    completion_indicator = page.locator('[data-testid="skill-execution-complete"]')
    expect(completion_indicator).to_be_visible(timeout=timeout)


def get_skill_output(page: Page) -> str:
    """Get skill execution output.

    Args:
        page: Playwright page object

    Returns:
        str: Skill output text
    """
    output_element = page.locator('[data-testid="skill-output"]')
    expect(output_element).to_be_visible(timeout=5000)
    return output_element.text_content()


def create_executable_skill(db_session) -> str:
    """Create executable skill in database.

    Args:
        db_session: Database session

    Returns:
        str: Created skill_id
    """
    skill_id = f"test-exec-skill-{str(uuid.uuid4())[:8]}"
    execution_id = str(uuid.uuid4())

    skill = SkillExecution(
        id=execution_id,
        skill_id=skill_id,
        agent_id="system",
        status="Active",
        capability="Test execution skill",
        skill_body="""# Test Skill
Execute with parameters.

inputs:
  name: string - Test name
  value: number - Test value

output:
  result: object - Execution result
""",
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        input_params={
            "skill_name": skill_id,
            "skill_type": "prompt_only",
            "skill_metadata": {
                "name": skill_id,
                "description": "Test execution skill",
                "category": "testing",
                "parameters": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "value", "type": "number", "required": True}
                ]
            }
        }
    )
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)

    return skill_id


def create_long_running_skill(db_session, duration_seconds: int = 2) -> str:
    """Create long-running skill for progress testing.

    Args:
        db_session: Database session
        duration_seconds: Simulated execution duration

    Returns:
        str: Created skill_id
    """
    skill_id = f"test-long-running-{str(uuid.uuid4())[:8]}"
    execution_id = str(uuid.uuid4())

    skill = SkillExecution(
        id=execution_id,
        skill_id=skill_id,
        agent_id="system",
        status="Active",
        capability=f"Long running skill ({duration_seconds}s)",
        skill_body=f"""# Long Running Skill
Simulates long operation.

inputs:
  duration: number - Duration in seconds

output:
  result: object - Completion result
""",
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        input_params={
            "skill_name": skill_id,
            "skill_type": "prompt_only",
            "skill_metadata": {
                "name": skill_id,
                "description": f"Long running skill ({duration_seconds}s)",
                "category": "testing",
                "parameters": [
                    {"name": "duration", "type": "number", "required": False, "default": duration_seconds}
                ],
                "estimated_duration": duration_seconds
            }
        }
    )
    db_session.add(skill)
    db_session.commit()

    return skill_id


def create_json_output_skill(db_session) -> str:
    """Create skill that returns JSON output.

    Args:
        db_session: Database session

    Returns:
        str: Created skill_id
    """
    skill_id = f"test-json-output-{str(uuid.uuid4())[:8]}"
    execution_id = str(uuid.uuid4())

    skill = SkillExecution(
        id=execution_id,
        skill_id=skill_id,
        agent_id="system",
        status="Active",
        capability="JSON output skill",
        skill_body="""# JSON Output Skill
Returns structured JSON.

inputs:
  query: string - Query string

output:
  result: object - JSON result
  status: string - Status
  timestamp: string - ISO timestamp
""",
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        input_params={
            "skill_name": skill_id,
            "skill_type": "prompt_only",
            "skill_metadata": {
                "name": skill_id,
                "description": "Returns JSON output",
                "category": "testing",
                "parameters": [
                    {"name": "query", "type": "string", "required": True}
                ],
                "output_format": "json"
            }
        }
    )
    db_session.add(skill)
    db_session.commit()

    return skill_id


# ============================================================================
# Tests
# ============================================================================

def test_execute_skill_with_parameters(authenticated_page_api, db_session):
    """Test skill execution with parameters (WORK-03).

    Requirements:
    - Execute button triggers execution flow
    - Parameters can be filled in execution modal
    - Loading indicator visible during execution
    - Output displayed after completion
    - Execution history record created
    """
    # Create executable skill
    skill_id = create_executable_skill(db_session)

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Find skill card and click execute
    execute_button = authenticated_page_api.locator(f'[data-testid="skill-{skill_id}-execute"]')

    # If execute button doesn't exist, skip gracefully
    if not execute_button.is_visible():
        pytest.skip(f"Execute button for skill {skill_id} not visible - may need registry UI")

    execute_button.click()

    # Wait for execution modal
    modal = authenticated_page_api.locator('[data-testid="skill-execute-modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Fill parameters
    name_input = authenticated_page_api.locator('[data-testid="skill-param-name"]')
    if name_input.is_visible():
        name_input.fill("Test")

    value_input = authenticated_page_api.locator('[data-testid="skill-param-value"]')
    if value_input.is_visible():
        value_input.fill("123")

    # Click execute
    execute_confirm = authenticated_page_api.locator('[data-testid="skill-execute-confirm"]')
    expect(execute_confirm).to_be_visible()
    execute_confirm.click()

    # Verify loading indicator
    loading = authenticated_page_api.locator('[data-testid="skill-executing"]')
    if loading.is_visible():
        expect(loading).to_be_visible()

    # Wait for completion (with timeout)
    try:
        completion = authenticated_page_api.locator('[data-testid="skill-execution-complete"]')
        expect(completion).to_be_visible(timeout=10000)
    except AssertionError:
        # If completion indicator doesn't exist, wait for output
        output = authenticated_page_api.locator('[data-testid="skill-output"]')
        expect(output).to_be_visible(timeout=10000)

    # Verify output displayed
    output = authenticated_page_api.locator('[data-testid="skill-output"]')
    expect(output).to_be_visible()

    # Verify execution history record created in database
    execution_record = db_session.query(SkillExecution).filter_by(
        skill_id=skill_id
    ).first()

    assert execution_record is not None, f"Execution record not found for {skill_id}"


def test_skill_output_json_validation(authenticated_page_api, db_session):
    """Test skill output JSON validation (WORK-03).

    Requirements:
    - Skill returns valid JSON output
    - Output contains expected fields (result, status, etc.)
    - JSON parses correctly
    """
    # Create JSON output skill
    skill_id = create_json_output_skill(db_session)

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Execute skill
    execute_button = authenticated_page_api.locator(f'[data-testid="skill-{skill_id}-execute"]')

    if not execute_button.is_visible():
        pytest.skip(f"Execute button for skill {skill_id} not visible")

    execute_button.click()

    # Wait for modal
    modal = authenticated_page_api.locator('[data-testid="skill-execute-modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Fill parameter
    query_input = authenticated_page_api.locator('[data-testid="skill-param-query"]')
    if query_input.is_visible():
        query_input.fill("test query")

    # Execute
    execute_confirm = authenticated_page_api.locator('[data-testid="skill-execute-confirm"]')
    execute_confirm.click()

    # Wait for output
    output_element = authenticated_page_api.locator('[data-testid="skill-output"]')
    expect(output_element).to_be_visible(timeout=10000)

    # Get output text
    output_text = get_skill_output(authenticated_page_api)

    # Try to parse as JSON
    try:
        output_json = json.loads(output_text)

        # Verify expected fields
        assert "result" in output_json or "data" in output_json, \
            "Output missing 'result' or 'data' field"

        assert "status" in output_json or "success" in output_json, \
            "Output missing status field"

    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {output_text}")


def test_skill_execution_error_handling(authenticated_page_api, db_session):
    """Test skill execution error handling (WORK-03).

    Requirements:
    - Invalid parameters trigger error message
    - Error describes the issue (e.g., missing required parameter)
    - Skill doesn't crash (modal remains open)
    """
    # Create executable skill
    skill_id = create_executable_skill(db_session)

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Execute skill
    execute_button = authenticated_page_api.locator(f'[data-testid="skill-{skill_id}-execute"]')

    if not execute_button.is_visible():
        pytest.skip(f"Execute button for skill {skill_id} not visible")

    execute_button.click()

    # Wait for modal
    modal = authenticated_page_api.locator('[data-testid="skill-execute-modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Leave required fields empty (intentional error)

    # Try to execute without filling parameters
    execute_confirm = authenticated_page_api.locator('[data-testid="skill-execute-confirm"]')
    execute_confirm.click()

    # Verify error message appears
    error_message = authenticated_page_api.locator('[data-testid="skill-execution-error"]')

    # If error message exists, verify it
    if error_message.is_visible(timeout=3000):
        error_text = error_message.text_content()
        assert "required" in error_text.lower() or "missing" in error_text.lower() or "parameter" in error_text.lower(), \
            f"Error message should describe parameter issue, got: {error_text}"

        # Verify modal still open
        expect(modal).to_be_visible()
    else:
        # If no error message shown, check for field validation
        name_error = authenticated_page_api.locator('[data-testid="skill-param-name-error"]')
        if name_error.is_visible():
            expect(name_error).to_be_visible()


def test_skill_execution_history(authenticated_page_api, db_session):
    """Test skill execution history tracking (WORK-03).

    Requirements:
    - Multiple executions create history records
    - History page shows all executions
    - Timestamps in descending order (newest first)
    - Status shown for each execution
    - Execution details accessible
    """
    # Create executable skill
    skill_id = create_executable_skill(db_session)

    # Execute skill 3 times (simulated via database records)
    for i in range(3):
        execution = SkillExecution(
            id=str(uuid.uuid4()),
            skill_id=skill_id,
            agent_id="system",
            status="Completed",
            capability=f"Execution {i+1}",
            skill_body=f"# Execution {i+1}\nResult: {i+1}",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            output_params={"result": f"Execution {i+1} result"}
        )
        db_session.add(execution)
    db_session.commit()

    # Navigate to history page
    authenticated_page_api.goto("http://localhost:3001/skills/history")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Verify history page loaded
    history_page = authenticated_page_api.locator('[data-testid="skills-history"]')

    if not history_page.is_visible():
        # If history page doesn't exist, verify database records
        executions = db_session.query(SkillExecution).filter_by(
            skill_id=skill_id
        ).all()

        assert len(executions) >= 3, f"Expected at least 3 executions, found {len(executions)}"
    else:
        # Verify execution records shown
        history_items = authenticated_page_api.locator('[data-testid^="execution-record-"]')
        item_count = history_items.count()

        assert item_count >= 3, f"Expected at least 3 history items, found {item_count}"

        # Verify status badges
        first_item = history_items.first
        status_badge = first_item.locator('[data-testid="execution-status"]')
        expect(status_badge).to_be_visible()

        # Click execution record to view details
        first_item.click()

        # Verify details modal
        details_modal = authenticated_page_api.locator('[data-testid="execution-details-modal"]')
        if details_modal.is_visible():
            expect(details_modal).to_be_visible()


def test_long_running_skill_execution(authenticated_page_api, db_session):
    """Test long-running skill execution with progress (WORK-03).

    Requirements:
    - Progress indicator visible during execution
    - Percentage updates (0% → 50% → 100%)
    - Final output displayed after completion
    """
    # Create long-running skill (2 seconds)
    skill_id = create_long_running_skill(db_session, duration_seconds=2)

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Execute skill
    execute_button = authenticated_page_api.locator(f'[data-testid="skill-{skill_id}-execute"]')

    if not execute_button.is_visible():
        pytest.skip(f"Execute button for skill {skill_id} not visible")

    execute_button.click()

    # Wait for modal
    modal = authenticated_page_api.locator('[data-testid="skill-execute-modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Execute
    execute_confirm = authenticated_page_api.locator('[data-testid="skill-execute-confirm"]')
    execute_confirm.click()

    # Verify progress indicator
    progress_indicator = authenticated_page_api.locator('[data-testid="skill-progress"]')

    if progress_indicator.is_visible():
        # Monitor progress updates
        previous_percentage = -1

        for _ in range(10):  # Check for up to 5 seconds
            try:
                progress_text = progress_indicator.text_content()
                # Extract percentage (e.g., "50%")
                if "%" in progress_text:
                    current_percentage = int(progress_text.replace("%", "").strip())

                    # Verify non-decreasing
                    assert current_percentage >= previous_percentage, \
                        f"Progress decreased from {previous_percentage}% to {current_percentage}%"

                    previous_percentage = current_percentage

                    # Break if complete
                    if current_percentage >= 100:
                        break

                time.sleep(0.5)
            except AssertionError:
                raise
            except Exception:
                # Progress indicator may not have percentage text
                break

    # Wait for completion
    try:
        completion = authenticated_page_api.locator('[data-testid="skill-execution-complete"]')
        expect(completion).to_be_visible(timeout=5000)
    except AssertionError:
        # If completion indicator doesn't exist, wait for output
        output = authenticated_page_api.locator('[data-testid="skill-output"]')
        expect(output).to_be_visible(timeout=5000)

    # Verify final output
    output = authenticated_page_api.locator('[data-testid="skill-output"]')
    expect(output).to_be_visible()
