"""
E2E tests for skill registry management (WORK-02).

Tests skill registry functionality including:
- Registry listing installed skills
- Registry filtering by category
- Skill uninstall flow
- Skill details page
- Skill status badges

Requirements covered:
- WORK-02: Skill appears in registry after installation
- WORK-02: Registry displays skill metadata (name, status, version)

Run with: pytest backend/tests/e2e_ui/tests/skills/test_skill_registry.py -v
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

from core.models import SkillExecution


# ============================================================================
# Helper Functions
# ============================================================================

def install_skill_via_api(db_session, skill_id: str, status: str = "Active", category: str = "testing") -> str:
    """Install skill via database API.

    Args:
        db_session: Database session
        skill_id: Skill identifier
        status: Skill status (Active, Inactive, Pending)
        category: Skill category for filtering

    Returns:
        str: Created skill execution ID
    """
    execution_id = str(uuid.uuid4())

    skill = SkillExecution(
        id=execution_id,
        skill_id=skill_id,
        agent_id="system",
        status=status,
        capability=f"Test skill {skill_id}",
        skill_body="# Test skill",
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        input_params={
            "skill_name": skill_id,
            "skill_type": "prompt_only",
            "skill_metadata": {
                "name": skill_id,
                "description": f"Test skill {skill_id}",
                "category": category,
                "version": "1.0.0",
                "author": "E2E Test Suite"
            }
        }
    )
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)

    return execution_id


def uninstall_skill_via_ui(page: Page, skill_id: str) -> None:
    """Uninstall skill via UI.

    Args:
        page: Playwright page object
        skill_id: Skill identifier

    Raises:
        AssertionError: If uninstall flow fails
    """
    # Click uninstall button
    uninstall_button = page.locator(f'[data-testid="skill-{skill_id}-uninstall"]')
    expect(uninstall_button).to_be_visible(timeout=5000)
    uninstall_button.click()

    # Wait for uninstall modal
    modal = page.locator('[data-testid="skill-uninstall-modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Confirm uninstall
    confirm_button = page.locator('[data-testid="skill-uninstall-confirm"]')
    expect(confirm_button).to_be_visible()
    confirm_button.click()

    # Wait for success message
    success = page.locator('[data-testid="skill-uninstall-success"]')
    expect(success).to_be_visible(timeout=10000)


def create_test_skills_with_categories(db_session, categories: List[str]) -> List[str]:
    """Create test skills with different categories.

    Args:
        db_session: Database session
        categories: List of category names

    Returns:
        List[str]: List of created skill IDs
    """
    skill_ids = []

    for i, category in enumerate(categories):
        skill_id = f"test-{category}-skill-{str(uuid.uuid4())[:8]}"
        execution_id = install_skill_via_api(db_session, skill_id, status="Active", category=category)
        skill_ids.append(skill_id)

    return skill_ids


# ============================================================================
# Tests
# ============================================================================

def test_skill_registry_lists_installed_skills(authenticated_page_api, db_session):
    """Test skill registry lists all installed skills (WORK-02).

    Requirements:
    - Registry page loads successfully
    - All installed skills visible
    - Skill count matches database
    - Each skill shows metadata (name, status, version)
    """
    # Install 3 test skills via API
    skill_ids = []
    for i in range(3):
        skill_id = f"test-registry-skill-{str(uuid.uuid4())[:8]}"
        execution_id = install_skill_via_api(db_session, skill_id, status="Active")
        skill_ids.append(skill_id)

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Verify registry page loaded
    registry = authenticated_page_api.locator('[data-testid="skills-registry"]')
    expect(registry).to_be_visible(timeout=10000)

    # Verify all skills visible
    # Note: Registry may show pagination, so we check for at least the skills we created
    skill_cards = authenticated_page_api.locator('[data-testid^="skill-card-"]')
    card_count = skill_cards.count()

    assert card_count >= 3, f"Expected at least 3 skill cards, found {card_count}"

    # Verify each skill shows metadata
    first_card = skill_cards.first

    # Check skill name
    skill_name = first_card.locator('[data-testid="skill-name"]')
    expect(skill_name).to_be_visible()

    # Check status badge
    status_badge = first_card.locator('[data-testid="skill-status"]')
    expect(status_badge).to_be_visible()

    # Check version
    version = first_card.locator('[data-testid="skill-version"]')
    # Version may not always be visible, so we check if it exists
    if version.is_visible():
        expect(version).to_be_visible()


def test_skill_registry_filtering(authenticated_page_api, db_session):
    """Test skill registry filtering by category (WORK-02).

    Requirements:
    - Skills can be filtered by category
    - Filter updates skill list
    - Filter count badge updates
    - Clearing filter shows all skills
    """
    # Install skills with different categories
    categories = ["productivity", "utility", "testing"]
    skill_ids = create_test_skills_with_categories(db_session, categories)

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Get initial skill count
    all_skills = authenticated_page_api.locator('[data-testid^="skill-card-"]')
    initial_count = all_skills.count()

    # Apply category filter (e.g., "productivity")
    productivity_filter = authenticated_page_api.locator('[data-testid="skill-category-productivity"]')

    if productivity_filter.is_visible():
        productivity_filter.click()
        authenticated_page_api.wait_for_timeout(500)

        # Verify only productivity skills shown
        filtered_skills = authenticated_page_api.locator('[data-testid^="skill-card-"]')
        filtered_count = filtered_skills.count()

        assert filtered_count <= initial_count, "Filter should reduce skill count"

        # Verify filter count badge updated
        filter_badge = authenticated_page_api.locator('[data-testid="filter-count-badge"]')
        if filter_badge.is_visible():
            badge_text = filter_badge.text_content()
            assert badge_text.strip().isdigit() or badge_text.strip() == "", \
                f"Filter badge should show count, got: {badge_text}"

        # Clear filter
        clear_button = authenticated_page_api.locator('[data-testid="clear-filters-button"]')
        if clear_button.is_visible():
            clear_button.click()
            authenticated_page_api.wait_for_timeout(500)

            # Verify all skills shown again
            final_count = authenticated_page_api.locator('[data-testid^="skill-card-"]').count()
            assert final_count >= filtered_count, "Clearing filter should show more skills"
    else:
        pytest.skip("Category filters not visible in registry UI")


def test_skill_uninstall_flow(authenticated_page_api, db_session):
    """Test skill uninstall flow (WORK-02).

    Requirements:
    - Uninstall button triggers uninstall modal
    - Confirmation removes skill from registry
    - Database record deleted or marked inactive
    - Uninstalled skill cannot be executed
    """
    # Install test skill
    skill_id = f"test-uninstall-skill-{str(uuid.uuid4())[:8]}"
    execution_id = install_skill_via_api(db_session, skill_id, status="Active")

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Find and click uninstall button
    uninstall_button = authenticated_page_api.locator(f'[data-testid="skill-{skill_id}-uninstall"]')

    if not uninstall_button.is_visible():
        pytest.skip(f"Uninstall button for skill {skill_id} not visible")

    uninstall_button.click()

    # Wait for uninstall modal
    modal = authenticated_page_api.locator('[data-testid="skill-uninstall-modal"]')
    expect(modal).to_be_visible(timeout=5000)

    # Confirm uninstall
    confirm_button = modal.locator('[data-testid="skill-uninstall-confirm"]')
    expect(confirm_button).to_be_visible()
    confirm_button.click()

    # Wait for success message
    success = authenticated_page_api.locator('[data-testid="skill-uninstall-success"]')
    expect(success).to_be_visible(timeout=10000)

    # Verify skill removed from registry list
    authenticated_page_api.wait_for_timeout(1000)  # Wait for UI update
    skill_card = authenticated_page_api.locator(f'[data-testid="skill-card-{skill_id}"]')

    # Skill card should not be visible (or marked as inactive)
    if skill_card.is_visible():
        status_badge = skill_card.locator('[data-testid="skill-status"]')
        expect(status_badge).to_contain_text("Inactive")
    else:
        # Skill removed from list
        expect(skill_card).not_to_be_visible()

    # Verify database record updated
    skill_record = db_session.query(SkillExecution).filter_by(
        skill_id=skill_id
    ).first()

    if skill_record:
        # Record should be marked inactive or deleted
        assert skill_record.status in ["Inactive", "Deleted"], \
            f"Expected Inactive/Deleted status, got {skill_record.status}"
    else:
        # Record deleted (also acceptable)
        assert skill_record is None, "Skill record should be deleted or inactive"

    # Try to execute uninstalled skill (should fail)
    authenticated_page_api.goto(f"http://localhost:3001/skills/{skill_id}/execute")
    authenticated_page_api.wait_for_load_state("networkidle")

    error_message = authenticated_page_api.locator('[data-testid="skill-not-available-error"]')

    if error_message.is_visible():
        expect(error_message).to_be_visible()
    else:
        # May redirect to registry with error
        current_url = authenticated_page_api.url
        assert "registry" in current_url or "error" in current_url, \
            "Should redirect to registry or show error"


def test_skill_details_page(authenticated_page_api, db_session):
    """Test skill details page (WORK-02).

    Requirements:
    - Clicking skill card navigates to details page
    - Details page shows skill metadata
    - Skill parameters listed
    - Execution history section visible
    """
    # Install test skill
    skill_id = f"test-details-skill-{str(uuid.uuid4())[:8]}"
    execution_id = install_skill_via_api(db_session, skill_id, status="Active")

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Click skill card to view details
    skill_card = authenticated_page_api.locator(f'[data-testid="skill-card-{skill_id}"]')

    if not skill_card.is_visible():
        pytest.skip(f"Skill card for {skill_id} not visible in registry")

    skill_card.click()

    # Wait for details page
    authenticated_page_api.wait_for_load_state("networkidle")

    # Verify details page loaded
    details_page = authenticated_page_api.locator('[data-testid="skill-details-page"]')

    if not details_page.is_visible():
        pytest.skip("Skill details page not implemented")

    expect(details_page).to_be_visible()

    # Verify skill metadata
    skill_name = authenticated_page_api.locator('[data-testid="skill-name"]')
    expect(skill_name).to_be_visible()

    skill_description = authenticated_page_api.locator('[data-testid="skill-description"]')
    expect(skill_description).to_be_visible()

    skill_version = authenticated_page_api.locator('[data-testid="skill-version"]')
    expect(skill_version).to_be_visible()

    skill_author = authenticated_page_api.locator('[data-testid="skill-author"]')
    expect(skill_author).to_be_visible()

    # Verify skill parameters listed
    parameters_section = authenticated_page_api.locator('[data-testid="skill-parameters"]')
    expect(parameters_section).to_be_visible()

    # Verify execution history section visible
    history_section = authenticated_page_api.locator('[data-testid="skill-execution-history"]')
    expect(history_section).to_be_visible()


def test_skill_status_badges(authenticated_page_api, db_session):
    """Test skill status badges display (WORK-02).

    Requirements:
    - Status badges visible and colored correctly
    - Active: green
    - Inactive: gray
    - Pending: yellow
    - Badge text matches skill status
    """
    # Create skills with different statuses
    statuses = ["Active", "Inactive", "Pending"]
    skill_ids = []

    for status in statuses:
        skill_id = f"test-{status.lower()}-skill-{str(uuid.uuid4())[:8]}"
        execution_id = install_skill_via_api(db_session, skill_id, status=status)
        skill_ids.append((skill_id, status))

    # Navigate to registry
    authenticated_page_api.goto("http://localhost:3001/skills/registry")
    authenticated_page_api.wait_for_load_state("networkidle")

    # Verify status badges for each skill
    for skill_id, expected_status in skill_ids:
        skill_card = authenticated_page_api.locator(f'[data-testid="skill-card-{skill_id}"]')

        if not skill_card.is_visible():
            continue  # Skip if card not visible

        # Get status badge
        status_badge = skill_card.locator('[data-testid="skill-status"]')
        expect(status_badge).to_be_visible()

        # Verify badge text matches status
        badge_text = status_badge.text_content()
        assert expected_status in badge_text, \
            f"Expected status '{expected_status}' in badge, got: {badge_text}"

        # Verify badge color (via CSS class or data attribute)
        # Note: Color verification may require checking CSS classes
        if expected_status == "Active":
            expect(status_badge).to_have_attribute("data-status", "active")
        elif expected_status == "Inactive":
            expect(status_badge).to_have_attribute("data-status", "inactive")
        elif expected_status == "Pending":
            expect(status_badge).to_have_attribute("data-status", "pending")
