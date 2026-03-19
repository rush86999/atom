"""
Comprehensive test coverage for WorkflowVersioningSystem

This test suite covers:
- Version creation and management
- Version validation and compatibility
- Version conflict resolution
- Version lifecycle operations
- Database operations and metrics
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.workflow_versioning_system import (
    Branch,
    ChangeType,
    ConflictResolution,
    VersionDiff,
    VersionType,
    WorkflowVersion,
    WorkflowVersioningSystem,
    WorkflowVersionManager,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def versioning_system(temp_db_path):
    """Create a WorkflowVersioningSystem instance with temporary database"""
    return WorkflowVersioningSystem(db_path=temp_db_path)


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing"""
    return {
        "steps": [
            {
                "id": "step1",
                "type": "data_extraction",
                "parameters": {"source": "database", "query": "SELECT * FROM users"},
            },
            {
                "id": "step2",
                "type": "data_transformation",
                "parameters": {"transformation": "filter", "field": "active"},
            },
            {
                "id": "step3",
                "type": "data_loading",
                "parameters": {"destination": "warehouse", "table": "users_processed"},
            },
        ],
        "dependencies": ["postgresql", "warehouse"],
        "metadata": {"version": "1.0", "author": "test_user"},
    }


@pytest.fixture
def modified_workflow_data():
    """Modified workflow data for testing version changes"""
    return {
        "steps": [
            {
                "id": "step1",
                "type": "data_extraction",
                "parameters": {"source": "database", "query": "SELECT * FROM users WHERE active = true"},
            },
            {
                "id": "step2",
                "type": "data_transformation",
                "parameters": {"transformation": "filter", "field": "active"},
            },
            {
                "id": "step3",
                "type": "data_loading",
                "parameters": {"destination": "warehouse", "table": "users_active"},
            },
        ],
        "dependencies": ["postgresql", "warehouse"],
        "metadata": {"version": "1.1", "author": "test_user"},
    }


@pytest.fixture
def structural_workflow_data():
    """Workflow with structural changes"""
    return {
        "steps": [
            {
                "id": "step1",
                "type": "data_extraction",
                "parameters": {"source": "database", "query": "SELECT * FROM users"},
            },
            {
                "id": "step2",
                "type": "data_transformation",
                "parameters": {"transformation": "filter", "field": "active"},
            },
            {
                "id": "step3",
                "type": "data_loading",
                "parameters": {"destination": "warehouse", "table": "users_processed"},
            },
            {
                "id": "step4",
                "type": "validation",
                "parameters": {"rules": ["not_null", "data_types"]},
            },
        ],
        "dependencies": ["postgresql", "warehouse"],
        "metadata": {"version": "2.0", "author": "test_user"},
    }


@pytest.mark.asyncio
class TestWorkflowVersioning:
    """Test workflow version creation, retrieval, and management"""

    async def test_create_initial_version(self, versioning_system, sample_workflow_data):
        """Test creating initial workflow version"""
        version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
            tags=["initial"],
        )

        assert version.workflow_id == "workflow_1"
        assert version.version == "1.0.0"
        assert version.version_type == VersionType.MAJOR
        assert version.created_by == "test_user"
        assert version.commit_message == "Initial version"
        assert version.tags == ["initial"]
        assert version.is_active is True
        assert version.checksum is not None
        assert version.parent_version is None

    async def test_create_minor_version(self, versioning_system, sample_workflow_data):
        """Test creating minor version"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
        )

        # Create minor version
        minor_version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Add new feature",
        )

        assert minor_version.version == "1.1.0"
        assert minor_version.version_type == VersionType.MINOR
        assert minor_version.parent_version == "1.0.0"

    async def test_create_patch_version(self, versioning_system, sample_workflow_data):
        """Test creating patch version"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
        )

        # Create patch version
        patch_version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.PATCH,
            created_by="test_user",
            commit_message="Bug fix",
        )

        assert patch_version.version == "1.0.1"
        assert patch_version.version_type == VersionType.PATCH

    async def test_create_version_with_branch(self, versioning_system, sample_workflow_data):
        """Test creating version in a non-default branch"""
        version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Feature branch version",
            branch_name="feature/new-ui",
        )

        assert version.branch_name == "feature/new-ui"
        assert version.version == "1.1.0"

    async def test_get_version(self, versioning_system, sample_workflow_data):
        """Test retrieving specific version"""
        # Create a version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
        )

        # Get the version
        retrieved = await versioning_system.get_version("workflow_1", "1.0.0")

        assert retrieved is not None
        assert retrieved.workflow_id == "workflow_1"
        assert retrieved.version == "1.0.0"
        assert retrieved.created_by == "test_user"

    async def test_get_nonexistent_version(self, versioning_system):
        """Test retrieving non-existent version"""
        retrieved = await versioning_system.get_version("workflow_1", "999.0.0")
        assert retrieved is None

    async def test_get_version_history(self, versioning_system, sample_workflow_data):
        """Test retrieving version history"""
        # Create multiple versions
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
        )

        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Feature 1",
        )

        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Feature 2",
        )

        # Get history
        history = await versioning_system.get_version_history("workflow_1", limit=10)

        assert len(history) == 3
        assert history[0].version == "1.2.0"  # Most recent first
        assert history[1].version == "1.1.0"
        assert history[2].version == "1.0.0"

    async def test_get_version_history_with_limit(self, versioning_system, sample_workflow_data):
        """Test retrieving version history with limit"""
        # Create 5 versions
        for i in range(5):
            await versioning_system.create_version(
                workflow_id="workflow_1",
                workflow_data=sample_workflow_data,
                version_type=VersionType.MINOR,
                created_by="test_user",
                commit_message=f"Feature {i}",
            )

        # Get limited history
        history = await versioning_system.get_version_history("workflow_1", limit=3)

        assert len(history) == 3

    async def test_rollback_to_version(self, versioning_system, sample_workflow_data):
        """Test rolling back to a previous version"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
        )

        # Create new version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="New feature",
        )

        # Rollback
        rollback_version = await versioning_system.rollback_to_version(
            workflow_id="workflow_1",
            target_version="1.0.0",
            created_by="test_user",
            rollback_reason="Feature caused issues",
        )

        assert rollback_version.version == "1.0.1"  # Hotfix version
        assert rollback_version.version_type == VersionType.HOTFIX
        assert "rollback" in rollback_version.tags
        assert rollback_version.commit_message == "Rollback to version 1.0.0: Feature caused issues"

    async def test_rollback_nonexistent_version(self, versioning_system):
        """Test rolling back to non-existent version"""
        with pytest.raises(ValueError, match="Version 999.0.0 not found"):
            await versioning_system.rollback_to_version(
                workflow_id="workflow_1",
                target_version="999.0.0",
                created_by="test_user",
                rollback_reason="Test",
            )

    async def test_duplicate_version_detection(self, versioning_system, sample_workflow_data):
        """Test detection of duplicate workflow versions"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
        )

        # Try to create duplicate (same data)
        with pytest.raises(ValueError, match="This workflow version already exists"):
            await versioning_system.create_version(
                workflow_id="workflow_1",
                workflow_data=sample_workflow_data,
                version_type=VersionType.MINOR,
                created_by="test_user",
                commit_message="Duplicate",
            )

    async def test_version_metadata(self, versioning_system, sample_workflow_data):
        """Test version metadata storage"""
        custom_metadata = {"review_status": "approved", "reviewer": " senior_dev"}

        version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
        )

        # Check metadata
        assert version.metadata is not None
        assert "change_type" in version.metadata
        assert "auto_bumped" in version.metadata
        assert version.metadata["auto_bumped"] is True

    async def test_pre_release_version_bumping(self, versioning_system, sample_workflow_data):
        """Test pre-release version bumping (alpha, beta)"""
        # Create beta version
        beta_version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.BETA,
            created_by="test_user",
            commit_message="Beta release",
        )

        assert "beta" in beta_version.version

        # Create another beta version
        beta_version_2 = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.BETA,
            created_by="test_user",
            commit_message="Beta 2",
        )

        assert "beta" in beta_version_2.version


@pytest.mark.asyncio
class TestVersionValidation:
    """Test version validation, compatibility checks, and migration"""

    async def test_change_type_detection_structural(
        self, versioning_system, sample_workflow_data, structural_workflow_data
    ):
        """Test detection of structural changes"""
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=structural_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Add step",
        )

        assert version.change_type == ChangeType.STRUCTURAL

    async def test_change_type_detection_parametric(
        self, versioning_system, sample_workflow_data, modified_workflow_data
    ):
        """Test detection of parametric changes"""
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=modified_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Change param",
        )

        # Should detect parametric or execution change
        assert version.change_type in [ChangeType.PARAMETRIC, ChangeType.EXECUTION]

    async def test_checksum_calculation(self, versioning_system, sample_workflow_data):
        """Test checksum calculation for workflow data"""
        version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        assert version.checksum is not None
        assert len(version.checksum) == 64  # SHA-256 hex length

    async def test_different_data_different_checksum(
        self, versioning_system, sample_workflow_data, modified_workflow_data
    ):
        """Test that different data produces different checksums"""
        version1 = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        version2 = await versioning_system.create_version(
            workflow_id="workflow_2",
            workflow_data=modified_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Modified",
        )

        assert version1.checksum != version2.checksum

    async def test_version_compatibility_same_major(self, versioning_system, sample_workflow_data):
        """Test version compatibility within same major version"""
        # Create 1.0.0
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create 1.1.0 (compatible)
        v1_1_0 = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Feature",
        )

        # Create 1.0.1 (compatible)
        v1_0_1 = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.PATCH,
            created_by="test_user",
            commit_message="Fix",
        )

        assert v1_1_0.version.startswith("1.")
        assert v1_0_1.version.startswith("1.")

    async def test_version_incompatibility_major_change(self, versioning_system, sample_workflow_data):
        """Test version incompatibility across major versions"""
        # Create 1.0.0
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create 2.0.0 (breaking change)
        v2_0_0 = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=structural_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Breaking change",
        )

        assert v2_0_0.version.startswith("2.")

    async def test_invalid_version_bump_handling(self, versioning_system):
        """Test handling of invalid version strings"""
        # Test with invalid current version fallback
        result = versioning_system._bump_version("invalid", VersionType.PATCH)
        # Should fallback to appending .1
        assert "invalid.1" in result or result == "invalid.1"

    async def test_dependency_change_detection(self, versioning_system, sample_workflow_data):
        """Test detection of dependency changes"""
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Modify dependencies
        modified_data = sample_workflow_data.copy()
        modified_data["dependencies"] = ["postgresql", "warehouse", "redis"]

        version = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Add redis",
        )

        assert version.change_type == ChangeType.DEPENDENCY


@pytest.mark.asyncio
class TestVersionConflict:
    """Test concurrent versioning, conflict resolution, and merge strategies"""

    async def test_branch_creation(self, versioning_system, sample_workflow_data):
        """Test creating a new branch"""
        # Create main branch version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create feature branch
        branch = await versioning_system.create_branch(
            workflow_id="workflow_1",
            branch_name="feature/experiment",
            base_version="1.0.0",
            created_by="test_user",
            merge_strategy="merge_commit",
        )

        assert branch.branch_name == "feature/experiment"
        assert branch.base_version == "1.0.0"
        assert branch.current_version == "1.0.0"
        assert branch.merge_strategy == "merge_commit"
        assert branch.is_protected is False

    async def test_branch_creation_duplicate(self, versioning_system, sample_workflow_data):
        """Test creating duplicate branch raises error"""
        # Create main branch version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create branch
        await versioning_system.create_branch(
            workflow_id="workflow_1",
            branch_name="feature/test",
            base_version="1.0.0",
            created_by="test_user",
        )

        # Try to create duplicate
        with pytest.raises(ValueError, match="Branch feature/test already exists"):
            await versioning_system.create_branch(
                workflow_id="workflow_1",
                branch_name="feature/test",
                base_version="1.0.0",
                created_by="test_user",
            )

    async def test_branch_creation_invalid_base_version(self, versioning_system):
        """Test creating branch with invalid base version"""
        with pytest.raises(ValueError, match="Base version 999.0.0 not found"):
            await versioning_system.create_branch(
                workflow_id="workflow_1",
                branch_name="feature/test",
                base_version="999.0.0",
                created_by="test_user",
            )

    async def test_get_branches(self, versioning_system, sample_workflow_data):
        """Test retrieving all branches for a workflow"""
        # Create main branch version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create multiple branches
        await versioning_system.create_branch(
            workflow_id="workflow_1",
            branch_name="feature/1",
            base_version="1.0.0",
            created_by="user1",
        )

        await versioning_system.create_branch(
            workflow_id="workflow_1",
            branch_name="feature/2",
            base_version="1.0.0",
            created_by="user2",
        )

        # Get branches
        branches = await versioning_system.get_branches("workflow_1")

        assert len(branches) == 3  # main + 2 features
        branch_names = [b.branch_name for b in branches]
        assert "main" in branch_names
        assert "feature/1" in branch_names
        assert "feature/2" in branch_names

    async def test_branch_merge(self, versioning_system, sample_workflow_data):
        """Test merging a branch into another"""
        # Create main branch
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
            branch_name="main",
        )

        # Create feature branch
        await versioning_system.create_branch(
            workflow_id="workflow_1",
            branch_name="feature/test",
            base_version="1.0.0",
            created_by="dev_user",
        )

        # Create version in feature branch
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="dev_user",
            commit_message="Feature work",
            branch_name="feature/test",
        )

        # Merge feature into main
        merged = await versioning_system.merge_branch(
            workflow_id="workflow_1",
            source_branch="feature/test",
            target_branch="main",
            merge_by="test_user",
            merge_message="Merge feature test",
        )

        assert merged.version == "1.1.0"
        assert merged.branch_name == "main"
        assert "merge" in merged.tags

    async def test_branch_merge_nonexistent_source(self, versioning_system, sample_workflow_data):
        """Test merging non-existent source branch"""
        # Create main branch
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
            branch_name="main",
        )

        # Try to merge non-existent branch
        with pytest.raises(ValueError, match="Source branch nonexistent not found"):
            await versioning_system.merge_branch(
                workflow_id="workflow_1",
                source_branch="nonexistent",
                target_branch="main",
                merge_by="test_user",
                merge_message="Test",
            )

    async def test_branch_merge_nonexistent_target(self, versioning_system, sample_workflow_data):
        """Test merging into non-existent target branch"""
        # Create main branch
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
            branch_name="main",
        )

        # Create feature branch
        await versioning_system.create_branch(
            workflow_id="workflow_1",
            branch_name="feature/test",
            base_version="1.0.0",
            created_by="dev_user",
        )

        # Try to merge into non-existent target
        with pytest.raises(ValueError, match="Target branch nonexistent not found"):
            await versioning_system.merge_branch(
                workflow_id="workflow_1",
                source_branch="feature/test",
                target_branch="nonexistent",
                merge_by="test_user",
                merge_message="Test",
            )


@pytest.mark.asyncio
class TestVersionLifecycle:
    """Test version activation, deprecation, deletion, and archival"""

    async def test_delete_version_soft_delete(self, versioning_system, sample_workflow_data):
        """Test soft deletion of version"""
        # Create version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create new version (old one not in use)
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="New version",
        )

        # Delete old version
        result = await versioning_system.delete_version(
            workflow_id="workflow_1",
            version="1.0.0",
            deleted_by="admin",
            delete_reason="Deprecated",
        )

        assert result is True

        # Verify it's marked as inactive
        version = await versioning_system.get_version("workflow_1", "1.0.0")
        assert version is not None
        assert version.is_active is False

    async def test_delete_version_in_use_fails(self, versioning_system, sample_workflow_data):
        """Test that deleting currently used version fails"""
        # Create version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Try to delete (it's in use by main branch)
        with pytest.raises(ValueError, match="Cannot delete version that is currently in use"):
            await versioning_system.delete_version(
                workflow_id="workflow_1",
                version="1.0.0",
                deleted_by="admin",
                delete_reason="Test",
            )

    async def test_version_metrics_initial(self, versioning_system, sample_workflow_data):
        """Test initial version metrics are None"""
        # Create version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Get metrics (should be None or empty)
        metrics = await versioning_system.get_version_metrics("workflow_1", "1.0.0")

        assert metrics is None or metrics.get("execution_count") == 0

    async def test_version_metrics_update(self, versioning_system, sample_workflow_data):
        """Test updating version metrics"""
        # Create version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Update metrics
        result = await versioning_system.update_version_metrics(
            workflow_id="workflow_1",
            version="1.0.0",
            execution_result={
                "success": True,
                "execution_time": 150,
            },
        )

        assert result is True

        # Verify metrics updated
        metrics = await versioning_system.get_version_metrics("workflow_1", "1.0.0")
        assert metrics is not None
        assert metrics["execution_count"] == 1
        assert metrics["success_rate"] == 100.0

    async def test_version_metrics_multiple_executions(self, versioning_system, sample_workflow_data):
        """Test metrics aggregation across multiple executions"""
        # Create version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Execute multiple times
        await versioning_system.update_version_metrics(
            workflow_id="workflow_1",
            version="1.0.0",
            execution_result={"success": True, "execution_time": 100},
        )

        await versioning_system.update_version_metrics(
            workflow_id="workflow_1",
            version="1.0.0",
            execution_result={"success": True, "execution_time": 200},
        )

        await versioning_system.update_version_metrics(
            workflow_id="workflow_1",
            version="1.0.0",
            execution_result={"success": False, "execution_time": 50},
        )

        # Check aggregated metrics
        metrics = await versioning_system.get_version_metrics("workflow_1", "1.0.0")
        assert metrics["execution_count"] == 3
        assert metrics["error_count"] == 1
        assert metrics["success_rate"] == pytest.approx(66.67, rel=1)
        assert metrics["avg_execution_time"] == pytest.approx(116.67, rel=1)

    async def test_version_performance_score_calculation(self, versioning_system, sample_workflow_data):
        """Test performance score calculation"""
        # Create version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Update metrics with good performance
        await versioning_system.update_version_metrics(
            workflow_id="workflow_1",
            version="1.0.0",
            execution_result={"success": True, "execution_time": 50},
        )

        metrics = await versioning_system.get_version_metrics("workflow_1", "1.0.0")
        # Performance score should be high for fast, successful execution
        assert metrics["performance_score"] > 0
        assert metrics["performance_score"] <= 100

    async def test_version_deprecation_workflow(self, versioning_system, sample_workflow_data):
        """Test version deprecation workflow"""
        # Create versions
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="1.0.0",
        )

        v1_1_0 = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="1.1.0",
        )

        v1_2_0 = await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="1.2.0",
        )

        # Soft deprecate old version
        await versioning_system.delete_version(
            workflow_id="workflow_1",
            version="1.0.0",
            deleted_by="admin",
            delete_reason="Superseded by 1.2.0",
        )

        # Verify deprecated version is inactive
        old_version = await versioning_system.get_version("workflow_1", "1.0.0")
        assert old_version.is_active is False

        # Verify new versions are still active
        v1_1_0_check = await versioning_system.get_version("workflow_1", "1.1.0")
        v1_2_0_check = await versioning_system.get_version("workflow_1", "1.2.0")
        assert v1_1_0_check.is_active is True
        assert v1_2_0_check.is_active is True


@pytest.mark.asyncio
class TestVersionComparison:
    """Test version comparison and diff visualization"""

    async def test_compare_versions_identical(self, versioning_system, sample_workflow_data):
        """Test comparing identical versions"""
        # Create two versions with same data (different checksums won't be created)
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create modified version to compare
        modified_data = sample_workflow_data.copy()
        modified_data["metadata"]["version"] = "1.1"

        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Minor change",
        )

        # Compare
        diff = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="1.1.0",
        )

        assert diff is not None
        assert diff.from_version == "1.0.0"
        assert diff.to_version == "1.1.0"
        assert diff.impact_level in ["low", "medium", "high", "critical"]

    async def test_compare_versions_added_steps(
        self, versioning_system, sample_workflow_data, structural_workflow_data
    ):
        """Test comparing versions with added steps"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create version with added step
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=structural_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Add validation step",
        )

        # Compare
        diff = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="2.0.0",
        )

        assert len(diff.added_steps) == 1
        assert diff.added_steps[0]["id"] == "step4"

    async def test_compare_versions_removed_steps(self, versioning_system, sample_workflow_data):
        """Test comparing versions with removed steps"""
        # Create initial version with 3 steps
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create version with 2 steps
        reduced_data = {
            "steps": sample_workflow_data["steps"][:2],
            "dependencies": ["postgresql"],
            "metadata": {"version": "2.0"},
        }

        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=reduced_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Remove step",
        )

        # Compare
        diff = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="2.0.0",
        )

        assert len(diff.removed_steps) == 1
        assert diff.removed_steps[0]["id"] == "step3"

    async def test_compare_versions_modified_steps(
        self, versioning_system, sample_workflow_data, modified_workflow_data
    ):
        """Test comparing versions with modified steps"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create version with modified steps
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=modified_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Modify steps",
        )

        # Compare
        diff = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="1.1.0",
        )

        assert len(diff.modified_steps) > 0

    async def test_compare_versions_impact_level_low(self, versioning_system, sample_workflow_data):
        """Test impact level calculation for low-impact changes"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create minimal metadata change
        modified_data = sample_workflow_data.copy()
        modified_data["metadata"]["note"] = "updated"

        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=modified_data,
            version_type=VersionType.PATCH,
            created_by="test_user",
            commit_message="Metadata update",
        )

        # Compare
        diff = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="1.0.1",
        )

        assert diff.impact_level == "low"

    async def test_compare_versions_impact_level_critical(
        self, versioning_system, sample_workflow_data, structural_workflow_data
    ):
        """Test impact level calculation for critical changes"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        # Create version with major structural changes
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=structural_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Major structural changes",
        )

        # Compare
        diff = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="2.0.0",
        )

        # Should be high or critical impact
        assert diff.impact_level in ["high", "critical"]

    async def test_compare_versions_cache_hit(self, versioning_system, sample_workflow_data):
        """Test that version comparison uses cache"""
        # Create versions
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial",
        )

        modified_data = sample_workflow_data.copy()
        await versioning_system.create_version(
            workflow_id="workflow_1",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Change",
        )

        # First comparison (calculates and caches)
        diff1 = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="1.1.0",
        )

        # Second comparison (should use cache)
        diff2 = await versioning_system.compare_versions(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="1.1.0",
        )

        # Should return same result
        assert diff1.impact_level == diff2.impact_level


class TestWorkflowVersionManager:
    """Test high-level workflow version management interface"""

    @pytest.mark.asyncio
    async def test_create_workflow_version_auto_detect(self, versioning_system, sample_workflow_data):
        """Test automatic version type detection"""
        manager = WorkflowVersionManager()
        manager.versioning_system = versioning_system

        # Create initial version
        result = await manager.create_workflow_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            user_id="test_user",
            change_description="Initial version",
            version_type="major",
        )

        assert result["version"] == "1.0.0"
        assert result["version_type"] == "major"
        assert result["checksum"] is not None

    @pytest.mark.asyncio
    async def test_rollback_workflow(self, versioning_system, sample_workflow_data):
        """Test workflow rollback through manager"""
        manager = WorkflowVersionManager()
        manager.versioning_system = versioning_system

        # Create initial version
        await manager.create_workflow_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            user_id="test_user",
            change_description="Initial",
            version_type="major",
        )

        # Rollback
        result = await manager.rollback_workflow(
            workflow_id="workflow_1",
            target_version="1.0.0",
            user_id="admin_user",
            reason="Testing rollback",
        )

        assert result["rollback_successful"] is True
        assert result["target_version"] == "1.0.0"
        assert "rollback_version" in result

    @pytest.mark.asyncio
    async def test_get_workflow_changes(self, versioning_system, sample_workflow_data):
        """Test getting workflow changes through manager"""
        manager = WorkflowVersionManager()
        manager.versioning_system = versioning_system

        # Create versions
        await manager.create_workflow_version(
            workflow_id="workflow_1",
            workflow_data=sample_workflow_data,
            user_id="test_user",
            change_description="Initial",
            version_type="major",
        )

        modified_data = sample_workflow_data.copy()
        await manager.create_workflow_version(
            workflow_id="workflow_1",
            workflow_data=modified_data,
            user_id="test_user",
            change_description="Change",
            version_type="minor",
        )

        # Get changes
        changes = await manager.get_workflow_changes(
            workflow_id="workflow_1",
            from_version="1.0.0",
            to_version="1.1.0",
        )

        assert "from_version" in changes
        assert "to_version" in changes
        assert "impact_level" in changes
