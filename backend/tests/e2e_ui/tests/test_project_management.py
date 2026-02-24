"""
E2E UI tests for Project management functionality.

This test suite validates project CRUD operations:
- Creating new projects via Quick Create modal
- Editing existing project names and descriptions
- Deleting projects with confirmation dialog
- Canceling project deletion
- Project list displays all user projects

Tests use authenticated_page fixture for API-first authentication (10-100x faster than UI login).
Tests use setup_test_project fixture for API-first project creation.
"""

import pytest
from typing import Dict, Any
from playwright.sync_api import Page
from tests.e2e_ui.pages.page_objects import ProjectsPage


class TestCreateProject:
    """Tests for creating new projects."""

    def test_create_new_project(self, authenticated_page):
        """Test that user can create a new project and see it in the project list.

        Verifies:
        1. Projects page loads successfully
        2. Initial project count can be retrieved
        3. Quick Create button opens create modal
        4. Project form can be filled with name and description
        5. Submitting form creates project
        6. Project count increases by 1
        7. New project name appears in list

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to projects page
        projects = ProjectsPage(authenticated_page)
        projects.navigate()

        # Wait for page to load
        assert projects.is_loaded(), "Projects page should be loaded"

        # Get initial project count
        initial_count = projects.get_project_count()

        # Generate unique project name
        import uuid
        project_name = f"Test Project {str(uuid.uuid4())[:8]}"
        project_description = f"Test project description {str(uuid.uuid4())[:8]}"

        # Create project via Quick Create
        projects.create_project(project_name, project_description)

        # Wait for creation to complete
        authenticated_page.wait_for_timeout(1000)

        # Refresh to see updated list
        authenticated_page.reload()
        projects.wait_for_load(timeout=5000)

        # Verify project count increased by 1
        new_count = projects.get_project_count()
        assert new_count == initial_count + 1, \
            f"Project count should increase from {initial_count} to {initial_count + 1}, got: {new_count}"

        # Verify new project name appears in list
        project_names = projects.get_project_names()
        assert project_name in project_names, \
            f"New project '{project_name}' should appear in list. Got: {project_names}"


class TestEditProject:
    """Tests for editing existing projects."""

    def test_edit_existing_project(self, authenticated_page, setup_test_project):
        """Test that user can edit an existing project.

        Verifies:
        1. Project created via API appears in list
        2. Edit button can be clicked on project card
        3. Edit modal opens with current values
        4. Project name and description can be changed
        5. Saving changes updates project
        6. Updated project name appears in list

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
            setup_test_project: Project created via API fixture
        """
        # Get project data from fixture
        original_name = setup_test_project["name"]
        original_description = setup_test_project["description"]

        # Navigate to projects page
        projects = ProjectsPage(authenticated_page)
        projects.navigate()

        # Wait for page to load
        assert projects.is_loaded(), "Projects page should be loaded"

        # Wait for project to appear in list
        authenticated_page.wait_for_timeout(1000)

        # Verify original project is in list
        project_names = projects.get_project_names()
        assert original_name in project_names, \
            f"Original project '{original_name}' should appear in list. Got: {project_names}"

        # Generate new unique name
        import uuid
        new_name = f"Edited Project {str(uuid.uuid4())[:8]}"
        new_description = f"Edited description {str(uuid.uuid4())[:8]}"

        # Edit the project
        projects.edit_project(original_name, new_name, new_description)

        # Wait for edit to complete
        authenticated_page.wait_for_timeout(1000)

        # Refresh to see updated list
        authenticated_page.reload()
        projects.wait_for_load(timeout=5000)

        # Verify updated name appears in list
        project_names = projects.get_project_names()
        assert new_name in project_names, \
            f"Updated project '{new_name}' should appear in list. Got: {project_names}"

        # Verify original name no longer in list
        assert original_name not in project_names, \
            f"Original name '{original_name}' should not appear in list after edit"


class TestDeleteProject:
    """Tests for deleting projects."""

    def test_delete_project_with_confirmation(self, authenticated_page, setup_test_project):
        """Test that user can delete a project with confirmation dialog.

        Verifies:
        1. Project created via API appears in list
        2. Delete button can be clicked on project card
        3. Confirmation dialog appears
        4. Confirming deletion removes project
        5. Project count decreases by 1
        6. Deleted project no longer appears in list

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
            setup_test_project: Project created via API fixture
        """
        # Get project data from fixture
        project_name = setup_test_project["name"]

        # Navigate to projects page
        projects = ProjectsPage(authenticated_page)
        projects.navigate()

        # Wait for page to load
        assert projects.is_loaded(), "Projects page should be loaded"

        # Wait for project to appear in list
        authenticated_page.wait_for_timeout(1000)

        # Get initial project count
        initial_count = projects.get_project_count()

        # Verify project is in list before deletion
        project_names = projects.get_project_names()
        assert project_name in project_names, \
            f"Project '{project_name}' should appear in list before deletion. Got: {project_names}"

        # Delete the project with confirmation
        projects.delete_project(project_name, confirm=True)

        # Wait for deletion to complete
        authenticated_page.wait_for_timeout(1000)

        # Refresh to see updated list
        authenticated_page.reload()
        projects.wait_for_load(timeout=5000)

        # Verify project count decreased by 1
        new_count = projects.get_project_count()
        assert new_count == initial_count - 1, \
            f"Project count should decrease from {initial_count} to {initial_count - 1}, got: {new_count}"

        # Verify project removed from list
        project_names = projects.get_project_names()
        assert project_name not in project_names, \
            f"Deleted project '{project_name}' should not appear in list. Got: {project_names}"

    def test_delete_project_cancellation(self, authenticated_page, setup_test_project):
        """Test that canceling project deletion keeps the project.

        Verifies:
        1. Project created via API appears in list
        2. Delete button can be clicked on project card
        3. Confirmation dialog appears
        4. Canceling deletion keeps project
        5. Project count remains unchanged
        6. Project still appears in list

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
            setup_test_project: Project created via API fixture
        """
        # Get project data from fixture
        project_name = setup_test_project["name"]

        # Navigate to projects page
        projects = ProjectsPage(authenticated_page)
        projects.navigate()

        # Wait for page to load
        assert projects.is_loaded(), "Projects page should be loaded"

        # Wait for project to appear in list
        authenticated_page.wait_for_timeout(1000)

        # Get initial project count
        initial_count = projects.get_project_count()

        # Verify project is in list
        project_names = projects.get_project_names()
        assert project_name in project_names, \
            f"Project '{project_name}' should appear in list. Got: {project_names}"

        # Attempt to delete but cancel
        projects.delete_project(project_name, confirm=False)

        # Wait for dialog to close
        authenticated_page.wait_for_timeout(1000)

        # Refresh to verify state
        authenticated_page.reload()
        projects.wait_for_load(timeout=5000)

        # Verify project count unchanged
        new_count = projects.get_project_count()
        assert new_count == initial_count, \
            f"Project count should remain {initial_count} after cancel, got: {new_count}"

        # Verify project still in list
        project_names = projects.get_project_names()
        assert project_name in project_names, \
            f"Project '{project_name}' should still appear in list after cancel. Got: {project_names}"


class TestProjectList:
    """Tests for project list display."""

    def test_project_list_displays_all(self, authenticated_page):
        """Test that project list displays all user projects accurately.

        Verifies:
        1. Multiple projects can be created via API
        2. All projects appear in list
        3. Project names match created ones
        4. Project count matches number of projects created

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Import API client for setup
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from tests.e2e_ui.utils.api_setup import APIClient, create_test_project, get_test_user_token

        # Create API client and authenticate
        from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user
        # We need to get the user's token from the page's localStorage
        token = authenticated_page.evaluate("localStorage.getItem('auth_token')")

        api_client = APIClient(base_url="http://localhost:8001", token=token)

        # Create 3 test projects
        import uuid
        created_projects = []
        for i in range(3):
            project_name = f"List Test Project {i} {str(uuid.uuid4())[:8]}"
            description = f"Description {i}"
            response = create_test_project(api_client, project_name, description)
            created_projects.append(project_name)

        # Navigate to projects page
        projects = ProjectsPage(authenticated_page)
        projects.navigate()

        # Wait for page to load and projects to appear
        assert projects.is_loaded(), "Projects page should be loaded"
        authenticated_page.wait_for_timeout(1500)

        # Verify all projects displayed
        project_names = projects.get_project_names()

        # Check that each created project appears in list
        for project_name in created_projects:
            assert project_name in project_names, \
                f"Created project '{project_name}' should appear in list. Got: {project_names}"

        # Verify project count is at least 3 (may have other projects)
        project_count = projects.get_project_count()
        assert project_count >= 3, \
            f"Project count should be at least 3, got: {project_count}"
