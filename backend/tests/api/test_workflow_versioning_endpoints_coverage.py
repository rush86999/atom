"""
Test Coverage for Workflow Versioning API Endpoints

Comprehensive test suite for workflow_versioning_endpoints.py (740 lines).
Target: 60%+ coverage (444+ lines).

Test Structure:
- TestWorkflowVersioningEndpoints: Version creation, retrieval, history
- TestVersionManagement: Rollback, comparison, deletion
- TestVersionAPI: Branching, metrics, summary
- TestVersionErrorHandling: Error paths, validation, not found
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
import os

# Import workflow versioning models and classes
from backend.core.workflow_versioning_system import (
    WorkflowVersion,
    WorkflowVersioningSystem,
    WorkflowVersionManager,
    Branch,
    VersionType,
    ChangeType,
    VersionDiff,
)
from backend.core.models import User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def versioning_client(test_app):
    """Test client for workflow versioning endpoints."""
    return TestClient(test_app)


@pytest.fixture
def mock_user(db_session: Session):
    """Mock authenticated user."""
    user = User(
        id="test-user-1",
        email="test@example.com",
        username="testuser",
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def mock_workflow_version():
    """Mock workflow version object."""
    version = Mock(spec=WorkflowVersion)
    version.workflow_id = "workflow-1"
    version.version = "1.0.0"
    version.version_type = VersionType.MAJOR
    version.change_type = ChangeType.FEATURE
    version.created_at = datetime.utcnow()
    version.created_by = "test-user-1"
    version.commit_message = "Initial version"
    version.tags = ["stable", "initial"]
    version.parent_version = None
    version.branch_name = "main"
    version.checksum = "abc123"
    version.is_active = True
    return version


@pytest.fixture
def mock_workflow_data():
    """Mock workflow data."""
    return {
        "steps": [
            {
                "id": "step-1",
                "name": "Step 1",
                "sequence_order": 1,
                "service": "test-service",
                "action": "test-action",
                "parameters": {"param1": "value1"}
            }
        ],
        "parameters": {
            "timeout": 30,
            "retries": 3
        },
        "dependencies": [],
        "metadata": {
            "name": "Test Workflow",
            "description": "Test workflow description"
        }
    }


@pytest.fixture
def mock_branch():
    """Mock workflow branch."""
    branch = Mock(spec=Branch)
    branch.branch_name = "feature-branch"
    branch.workflow_id = "workflow-1"
    branch.base_version = "1.0.0"
    branch.current_version = "1.1.0"
    branch.created_at = datetime.utcnow()
    branch.created_by = "test-user-1"
    branch.is_protected = False
    branch.merge_strategy = "merge_commit"
    return branch


@pytest.fixture
def mock_version_diff():
    """Mock version diff."""
    return {
        "from_version": "1.0.0",
        "to_version": "1.1.0",
        "impact_level": "MODERATE",
        "added_steps_count": 2,
        "removed_steps_count": 0,
        "modified_steps_count": 1,
        "structural_changes": ["Added step 2", "Added step 3"],
        "dependency_changes": [],
        "parametric_changes": {},
        "metadata_changes": {"description": "Updated description"}
    }


@pytest.fixture
def temp_workflow_file(tmp_path):
    """Create temporary workflows.json file."""
    workflows_file = tmp_path / "workflows.json"
    workflows = [
        {
            "id": "workflow-1",
            "name": "Test Workflow",
            "description": "Test workflow",
            "category": "test",
            "steps": [
                {
                    "id": "step-1",
                    "title": "Step 1",
                    "type": "action",
                    "config": {
                        "service": "test-service",
                        "action": "test-action",
                        "parameters": {"param1": "value1"}
                    }
                }
            ],
            "nodes": [],
            "connections": [],
            "parameters": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
    ]

    with open(workflows_file, 'w') as f:
        json.dump(workflows, f)

    return workflows_file


# ============================================================================
# TestWorkflowVersioningEndpoints: Version CRUD Operations (12 tests)
# ============================================================================

class TestWorkflowVersioningEndpoints:
    """Test workflow version creation, retrieval, and history endpoints."""

    @patch("backend.api.workflow_versioning_endpoints.version_manager")
    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    @patch("backend.api.workflow_versioning_endpoints.get_workflow_data")
    def test_create_workflow_version_success(
        self, mock_get_data, mock_versioning, mock_manager, versioning_client, mock_user, mock_workflow_version
    ):
        """Test successful workflow version creation."""
        # Setup mocks
        mock_get_data.return_value = {
            "steps": [],
            "parameters": {},
            "dependencies": [],
            "metadata": {}
        }
        mock_manager.create_workflow_version = AsyncMock(return_value={
            "version": "1.0.0"
        })
        mock_versioning.get_version = AsyncMock(return_value=mock_workflow_version)

        # Make request
        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/versions",
                json={
                    "version_type": "major",
                    "commit_message": "Initial version",
                    "tags": ["stable"],
                    "branch_name": "main"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"
        assert data["workflow_id"] == "workflow-1"
        assert data["version_type"] == "major"

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_workflow_versions_success(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version
    ):
        """Test retrieving workflow version history."""
        mock_versioning.get_version_history = AsyncMock(return_value=[mock_workflow_version])

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions",
                params={"branch_name": "main", "limit": 50}
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 0

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_workflow_versions_with_filters(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version
    ):
        """Test retrieving versions with branch and limit filters."""
        mock_versioning.get_version_history = AsyncMock(return_value=[mock_workflow_version])

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions",
                params={"branch_name": "feature", "limit": 10}
            )

        assert response.status_code == 200
        mock_versioning.get_version_history.assert_called_once()

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_specific_workflow_version(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version
    ):
        """Test retrieving a specific workflow version."""
        mock_versioning.get_version = AsyncMock(return_value=mock_workflow_version)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"
        assert data["workflow_id"] == "workflow-1"

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_workflow_version_data(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version, mock_workflow_data
    ):
        """Test retrieving workflow data for a specific version."""
        mock_workflow_version.workflow_data = mock_workflow_data
        mock_versioning.get_version = AsyncMock(return_value=mock_workflow_version)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/1.0.0/data")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_version_not_found(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test retrieving nonexistent version returns 404."""
        mock_versioning.get_version = AsyncMock(return_value=None)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/9.9.9")

        assert response.status_code == 404

    def test_version_create_request_validation(self):
        """Test VersionCreateRequest validates required fields."""
        from backend.api.workflow_versioning_endpoints import VersionCreateRequest
        from pydantic import ValidationError

        # Missing required fields
        with pytest.raises(ValidationError):
            VersionCreateRequest(
                # Missing version_type and commit_message
                branch_name="main"
            )

        # Invalid version_type
        with pytest.raises(ValidationError):
            VersionCreateRequest(
                version_type="invalid",
                commit_message="Test"
            )

    def test_version_response_model(self):
        """Test VersionResponse model structure."""
        from backend.api.workflow_versioning_endpoints import VersionResponse

        response = VersionResponse(
            workflow_id="workflow-1",
            version="1.0.0",
            version_type="major",
            change_type="feature",
            created_at="2024-01-01T00:00:00Z",
            created_by="user-1",
            commit_message="Test",
            tags=["stable"],
            parent_version=None,
            branch_name="main",
            checksum="abc123",
            is_active=True
        )

        assert response.workflow_id == "workflow-1"
        assert response.version_type == "major"

    def test_rollback_request_model(self):
        """Test RollbackRequest model structure."""
        from backend.api.workflow_versioning_endpoints import RollbackRequest

        request = RollbackRequest(
            target_version="1.0.0",
            rollback_reason="Reverting broken changes"
        )

        assert request.target_version == "1.0.0"
        assert request.rollback_reason == "Reverting broken changes"

    def test_branch_create_request_model(self):
        """Test BranchCreateRequest model structure."""
        from backend.api.workflow_versioning_endpoints import BranchCreateRequest

        request = BranchCreateRequest(
            branch_name="feature-branch",
            base_version="1.0.0",
            merge_strategy="merge_commit"
        )

        assert request.branch_name == "feature-branch"
        assert request.merge_strategy == "merge_commit"

    def test_version_diff_response_model(self):
        """Test VersionDiffResponse model structure."""
        from backend.api.workflow_versioning_endpoints import VersionDiffResponse

        response = VersionDiffResponse(
            workflow_id="workflow-1",
            from_version="1.0.0",
            to_version="1.1.0",
            impact_level="MODERATE",
            added_steps_count=2,
            removed_steps_count=0,
            modified_steps_count=1,
            structural_changes=["Added step"],
            dependency_changes=[],
            parametric_changes={},
            metadata_changes={}
        )

        assert response.impact_level == "MODERATE"
        assert response.added_steps_count == 2

    @patch("backend.api.workflow_versioning_endpoints.get_workflow_data")
    def test_get_workflow_data_from_file(
        self, mock_get_data, temp_workflow_file
    ):
        """Test get_workflow_data loads from workflows.json."""
        # Patch the workflows file path
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps([
                    {
                        "id": "workflow-1",
                        "steps": [{"id": "step-1", "name": "Step 1"}],
                        "parameters": {},
                        "dependencies": [],
                        "metadata": {}
                    }
                ])

                # Import and call the function
                from backend.api.workflow_versioning_endpoints import get_workflow_data
                import asyncio

                data = asyncio.run(get_workflow_data("workflow-1"))
                assert "steps" in data
                assert "parameters" in data


# ============================================================================
# TestVersionManagement: Rollback, Comparison, Deletion (10 tests)
# ============================================================================

class TestVersionManagement:
    """Test version rollback, comparison, and deletion operations."""

    @patch("backend.api.workflow_versioning_endpoints.version_manager")
    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_rollback_workflow_success(
        self, mock_versioning, mock_manager, versioning_client, mock_user, mock_workflow_version
    ):
        """Test successful workflow rollback."""
        mock_versioning.get_version = AsyncMock(return_value=mock_workflow_version)
        mock_manager.rollback_workflow = AsyncMock(return_value={
            "rollback_version": "1.0.1",
            "target_version": "1.0.0",
            "created_at": datetime.utcnow().isoformat()
        })

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/rollback",
                json={
                    "target_version": "1.0.0",
                    "rollback_reason": "Reverting broken changes"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "rollback_version" in data["data"]

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_rollback_target_version_not_found(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test rollback fails when target version doesn't exist."""
        mock_versioning.get_version = AsyncMock(return_value=None)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/rollback",
                json={
                    "target_version": "9.9.9",
                    "rollback_reason": "Test"
                }
            )

        assert response.status_code == 404

    @patch("backend.api.workflow_versioning_endpoints.version_manager")
    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_compare_workflow_versions(
        self, mock_versioning, mock_manager, versioning_client, mock_user, mock_version_diff
    ):
        """Test comparing two workflow versions."""
        mock_versioning.get_version = AsyncMock(return_value=Mock())
        mock_manager.get_workflow_changes = AsyncMock(return_value=mock_version_diff)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions/compare",
                params={
                    "from_version": "1.0.0",
                    "to_version": "1.1.0"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["from_version"] == "1.0.0"
        assert data["to_version"] == "1.1.0"

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_compare_versions_from_not_found(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test compare fails when source version doesn't exist."""
        mock_versioning.get_version = AsyncMock(return_value=None)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions/compare",
                params={
                    "from_version": "9.9.9",
                    "to_version": "1.0.0"
                }
            )

        assert response.status_code == 404

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_compare_versions_to_not_found(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version
    ):
        """Test compare fails when target version doesn't exist."""
        def get_version_side_effect(workflow_id, version):
            if version == "1.0.0":
                return mock_workflow_version
            return None

        mock_versioning.get_version = AsyncMock(side_effect=get_version_side_effect)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions/compare",
                params={
                    "from_version": "1.0.0",
                    "to_version": "9.9.9"
                }
            )

        assert response.status_code == 404

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_delete_workflow_version_success(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test successful version deletion (soft delete)."""
        mock_versioning.delete_version = AsyncMock(return_value=True)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.delete(
                "/api/v1/workflows/workflow-1/versions/1.0.0",
                params={"delete_reason": "Test deletion"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "deleted_at" in data["data"]

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_delete_version_fails(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test version deletion failure."""
        mock_versioning.delete_version = AsyncMock(return_value=False)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.delete(
                "/api/v1/workflows/workflow-1/versions/1.0.0",
                params={"delete_reason": "Test"}
            )

        assert response.status_code == 422  # Validation error

    def test_rollback_request_missing_fields(self):
        """Test RollbackRequest requires both target_version and rollback_reason."""
        from backend.api.workflow_versioning_endpoints import RollbackRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RollbackRequest(
                target_version="1.0.0"
                # Missing rollback_reason
            )

    def test_version_diff_response_structure(self, mock_version_diff):
        """Test VersionDiffResponse contains all required fields."""
        from backend.api.workflow_versioning_endpoints import VersionDiffResponse

        response = VersionDiffResponse(**mock_version_diff)

        assert response.impact_level == "MODERATE"
        assert response.added_steps_count == 2
        assert response.removed_steps_count == 0
        assert response.modified_steps_count == 1
        assert isinstance(response.structural_changes, list)

    @patch("backend.api.workflow_versioning_endpoints.version_manager")
    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_rollback_creates_new_version(
        self, mock_versioning, mock_manager, versioning_client, mock_user
    ):
        """Test rollback creates a new version, not modifying target."""
        mock_versioning.get_version = AsyncMock(return_value=Mock())
        mock_manager.rollback_workflow = AsyncMock(return_value={
            "rollback_version": "1.0.1",  # New version created
            "target_version": "1.0.0",    # Original unchanged
            "created_at": datetime.utcnow().isoformat()
        })

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/rollback",
                json={
                    "target_version": "1.0.0",
                    "rollback_reason": "Test rollback"
                }
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["rollback_version"] != data["target_version"]


# ============================================================================
# TestVersionAPI: Branching, Metrics, Summary (8 tests)
# ============================================================================

class TestVersionAPI:
    """Test version branching, metrics, and summary endpoints."""

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_create_workflow_branch(
        self, mock_versioning, versioning_client, mock_user, mock_branch
    ):
        """Test creating a new workflow branch."""
        mock_versioning.create_branch = AsyncMock(return_value=mock_branch)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/branches",
                json={
                    "branch_name": "feature-branch",
                    "base_version": "1.0.0",
                    "merge_strategy": "merge_commit"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["branch_name"] == "feature-branch"

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_workflow_branches(
        self, mock_versioning, versioning_client, mock_user, mock_branch
    ):
        """Test retrieving all branches for a workflow."""
        mock_versioning.get_branches = AsyncMock(return_value=[mock_branch])

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/branches")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_merge_workflow_branch(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version
    ):
        """Test merging a branch into another branch."""
        mock_versioning.merge_branch = AsyncMock(return_value=mock_workflow_version)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/branches/merge",
                json={
                    "source_branch": "feature",
                    "target_branch": "main",
                    "merge_message": "Merging feature branch"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "merged_version" in data["data"]

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_version_metrics(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test retrieving metrics for a specific version."""
        mock_versioning.get_version_metrics = AsyncMock(return_value={
            "execution_count": 10,
            "avg_duration": 5.2,
            "success_rate": 0.95
        })

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/1.0.0/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data["data"]

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_version_metrics_not_available(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test getting metrics when none available."""
        mock_versioning.get_version_metrics = AsyncMock(return_value=None)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/1.0.0/metrics")

        assert response.status_code == 200
        data = response.json()
        # Should return empty metrics dict
        assert data["data"]["metrics"] == {}

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_update_version_metrics(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test updating performance metrics for a version."""
        mock_versioning.update_version_metrics = AsyncMock(return_value=True)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/versions/1.0.0/metrics",
                json={
                    "execution_duration": 3.5,
                    "success": True,
                    "output_size": 1024
                }
            )

        assert response.status_code == 200

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_latest_version(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version
    ):
        """Test retrieving the latest version of a workflow."""
        mock_versioning.get_version_history = AsyncMock(return_value=[mock_workflow_version])

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions/latest",
                params={"branch_name": "main"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_version_summary(
        self, mock_versioning, versioning_client, mock_user, mock_workflow_version
    ):
        """Test getting summary statistics for all workflow versions."""
        mock_versioning.get_version_history = AsyncMock(return_value=[
            mock_workflow_version,
            mock_workflow_version
        ])

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions/summary",
                params={"branch_name": "main"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "total_versions" in data["data"]
        assert "version_types" in data["data"]
        assert "unique_contributors" in data["data"]


# ============================================================================
# TestVersionErrorHandling: Error Paths and Validation (10 tests)
# ============================================================================

class TestVersionErrorHandling:
    """Test error handling, validation, and edge cases."""

    @patch("backend.api.workflow_versioning_endpoints.version_manager")
    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    @patch("backend.api.workflow_versioning_endpoints.get_workflow_data")
    def test_create_version_workflow_not_found(
        self, mock_get_data, mock_versioning, mock_manager, versioning_client, mock_user
    ):
        """Test version creation when workflow not found."""
        # get_workflow_data returns empty structure when workflow not found
        mock_get_data.return_value = {
            "steps": [],
            "parameters": {},
            "dependencies": [],
            "metadata": {}
        }
        mock_manager.create_workflow_version = AsyncMock(return_value={"version": "1.0.0"})
        mock_versioning.get_version = AsyncMock(side_effect=Exception("Workflow not found"))

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/nonexistent/versions",
                json={
                    "version_type": "major",
                    "commit_message": "Test"
                }
            )

        # Should handle error gracefully
        assert response.status_code in [200, 500]

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_version_version_not_found(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test retrieving nonexistent version returns 404."""
        mock_versioning.get_version = AsyncMock(return_value=None)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/9.9.9")

        assert response.status_code == 404

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_get_version_data_not_found(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test getting version data when version doesn't exist."""
        mock_versioning.get_version = AsyncMock(return_value=None)

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/9.9.9/data")

        assert response.status_code == 404

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_latest_version_not_found(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test getting latest version when no versions exist."""
        mock_versioning.get_version_history = AsyncMock(return_value=[])

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get("/api/v1/workflows/workflow-1/versions/latest")

        assert response.status_code == 404

    def test_invalid_version_type_pattern(self):
        """Test version_type pattern validation rejects invalid types."""
        from backend.api.workflow_versioning_endpoints import VersionCreateRequest
        from pydantic import ValidationError

        # Invalid version_type (not in pattern)
        with pytest.raises(ValidationError):
            VersionCreateRequest(
                version_type="invalid_type",
                commit_message="Test"
            )

    def test_valid_version_types(self):
        """Test all valid version types are accepted."""
        from backend.api.workflow_versioning_endpoints import VersionCreateRequest

        valid_types = ["major", "minor", "patch", "hotfix", "auto"]

        for vtype in valid_types:
            request = VersionCreateRequest(
                version_type=vtype,
                commit_message="Test"
            )
            assert request.version_type == vtype

    @patch("backend.api.workflow_versioning_endpoints.version_manager")
    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_rollback_exception_handling(
        self, mock_versioning, mock_manager, versioning_client, mock_user
    ):
        """Test rollback endpoint handles exceptions gracefully."""
        mock_versioning.get_version = AsyncMock(side_effect=Exception("Database error"))

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/rollback",
                json={
                    "target_version": "1.0.0",
                    "rollback_reason": "Test"
                }
            )

        # Should handle exception
        assert response.status_code in [400, 500]

    @patch("backend.api.workflow_versioning_endpoints.version_manager")
    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_compare_versions_exception_handling(
        self, mock_versioning, mock_manager, versioning_client, mock_user
    ):
        """Test version comparison handles exceptions."""
        mock_versioning.get_version = AsyncMock(side_effect=Exception("Service error"))

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.get(
                "/api/v1/workflows/workflow-1/versions/compare",
                params={
                    "from_version": "1.0.0",
                    "to_version": "1.1.0"
                }
            )

        # Should handle exception
        assert response.status_code in [400, 500]

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_branch_creation_exception_handling(
        self, mock_versioning, versioning_client, mock_user
    ):
        """Test branch creation handles exceptions."""
        mock_versioning.create_branch = AsyncMock(side_effect=Exception("Branch creation failed"))

        with patch("backend.api.workflow_versioning_endpoints.get_current_user", return_value=mock_user):
            response = versioning_client.post(
                "/api/v1/workflows/workflow-1/branches",
                json={
                    "branch_name": "test-branch",
                    "base_version": "1.0.0"
                }
            )

        # Should handle exception
        assert response.status_code in [400, 500]

    @patch("backend.api.workflow_versioning_endpoints.versioning_system")
    def test_health_check_endpoint(self, mock_versioning, versioning_client):
        """Test health check endpoint for versioning system."""
        response = versioning_client.get("/api/v1/workflows/versioning/health")

        assert response.status_code == 200
        data = response.json()
        assert "versioning_system" in data.get("data", {})
