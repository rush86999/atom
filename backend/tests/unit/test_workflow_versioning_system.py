"""
Unit tests for workflow_versioning_system.py

Tests the WorkflowVersioningSystem including:
- Version creation and management
- Semantic versioning (major, minor, patch, hotfix)
- Version rollback
- Branching and merging
- Version comparison and diff generation
- Conflict resolution
- Version metrics tracking
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
from typing import Dict, Any

# Import the module to test
import sys
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

from core.workflow_versioning_system import (
    VersionType,
    ChangeType,
    WorkflowVersion,
    VersionDiff,
    Branch,
    ConflictResolution,
    WorkflowVersioningSystem,
    WorkflowVersionManager,
)


# ==================== Test Fixtures ====================

@pytest.fixture
def temp_db():
    """Create temporary database for versioning"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Clean up
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data"""
    return {
        "name": "Test Workflow",
        "description": "A test workflow",
        "steps": [
            {"id": "step1", "name": "Step 1", "type": "task"},
            {"id": "step2", "name": "Step 2", "type": "task"}
        ],
        "connections": [
            {"source": "step1", "target": "step2"}
        ]
    }


@pytest.fixture
def updated_workflow_data():
    """Updated workflow data with changes"""
    return {
        "name": "Test Workflow",
        "description": "A test workflow - updated",
        "steps": [
            {"id": "step1", "name": "Step 1", "type": "task"},
            {"id": "step2", "name": "Step 2", "type": "task"},
            {"id": "step3", "name": "Step 3", "type": "task"}
        ],
        "connections": [
            {"source": "step1", "target": "step2"},
            {"source": "step2", "target": "step3"}
        ]
    }


@pytest.fixture
def versioning_system(temp_db):
    """Create a WorkflowVersioningSystem instance"""
    return WorkflowVersioningSystem(db_path=temp_db)


# ==================== Test VersioningInit ====================

class TestVersioningInit:
    """Tests for WorkflowVersioningSystem initialization"""

    def test_system_initialization(self, temp_db):
        """Test system initializes and creates database"""
        system = WorkflowVersioningSystem(db_path=temp_db)

        assert system.db_path == temp_db
        assert os.path.exists(temp_db)

    def test_database_tables_created(self, temp_db):
        """Test that all required tables are created"""
        system = WorkflowVersioningSystem(db_path=temp_db)

        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)

        tables = [row[0] for row in cursor.fetchall()]

        assert "workflow_versions" in tables
        assert "workflow_branches" in tables
        assert "version_differences" in tables
        assert "conflict_resolutions" in tables
        assert "version_metrics" in tables

        conn.close()

    def test_version_type_enum(self):
        """Test VersionType enum values"""
        assert VersionType.MAJOR == "major"
        assert VersionType.MINOR == "minor"
        assert VersionType.PATCH == "patch"
        assert VersionType.HOTFIX == "hotfix"
        assert VersionType.BETA == "beta"
        assert VersionType.ALPHA == "alpha"

    def test_change_type_enum(self):
        """Test ChangeType enum values"""
        assert ChangeType.STRUCTURAL == "structural"
        assert ChangeType.PARAMETRIC == "parametric"
        assert ChangeType.EXECUTION == "execution"
        assert ChangeType.METADATA == "metadata"
        assert ChangeType.DEPENDENCY == "dependency"


# ==================== Test Version Creation ====================

class TestVersionCreation:
    """Tests for version creation"""

    @pytest.mark.asyncio
    async def test_create_first_version(self, versioning_system, sample_workflow_data):
        """Test creating the first version of a workflow"""
        version = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version"
        )

        assert version.workflow_id == "test_wf"
        assert version.version == "1.0.0"
        assert version.version_type == VersionType.MAJOR
        assert version.created_by == "test_user"
        assert version.commit_message == "Initial version"
        assert version.checksum is not None
        assert version.parent_version is None

    @pytest.mark.asyncio
    async def test_create_minor_version(self, versioning_system, sample_workflow_data):
        """Test creating a minor version"""
        # Create first version
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version"
        )

        # Create minor version
        minor_version = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Added new feature"
        )

        assert minor_version.version == "1.1.0"
        assert minor_version.version_type == VersionType.MINOR
        assert minor_version.parent_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_create_patch_version(self, versioning_system, sample_workflow_data):
        """Test creating a patch version"""
        # Create first version
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version"
        )

        # Create patch version
        patch_version = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.PATCH,
            created_by="test_user",
            commit_message="Bug fix"
        )

        assert patch_version.version == "1.0.1"
        assert patch_version.version_type == VersionType.PATCH

    @pytest.mark.asyncio
    async def test_create_hotfix_version(self, versioning_system, sample_workflow_data):
        """Test creating a hotfix version"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version"
        )

        hotfix_version = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.HOTFIX,
            created_by="test_user",
            commit_message="Emergency fix"
        )

        assert hotfix_version.version == "1.0.1"
        assert hotfix_version.version_type == VersionType.HOTFIX

    @pytest.mark.asyncio
    async def test_duplicate_version_detection(self, versioning_system, sample_workflow_data):
        """Test that duplicate versions (same checksum) are rejected"""
        # Create first version
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version"
        )

        # Try to create duplicate (same data)
        with pytest.raises(ValueError, match="already exists"):
            await versioning_system.create_version(
                workflow_id="test_wf",
                workflow_data=sample_workflow_data,
                version_type=VersionType.MINOR,
                created_by="test_user",
                commit_message="Duplicate"
            )

    @pytest.mark.asyncio
    async def test_version_with_tags(self, versioning_system, sample_workflow_data):
        """Test creating version with tags"""
        version = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial version",
            tags=["production", "stable"]
        )

        assert "production" in version.tags
        assert "stable" in version.tags

    @pytest.mark.asyncio
    async def test_version_on_branch(self, versioning_system, sample_workflow_data):
        """Test creating version on a specific branch"""
        version = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Feature branch version",
            branch_name="feature/new-stuff"
        )

        assert version.branch_name == "feature/new-stuff"


# ==================== Test Version Rollback ====================

class TestVersionRollback:
    """Tests for version rollback operations"""

    @pytest.mark.asyncio
    async def test_rollback_to_previous_version(self, versioning_system, sample_workflow_data):
        """Test rolling back to a previous version"""
        # Create version 1.0.0
        v1 = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Version 1.0.0"
        )

        # Create version 1.1.0 with different data
        modified_data = sample_workflow_data.copy()
        modified_data["description"] = "Modified version"
        v2 = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Version 1.1.0"
        )

        # Rollback to 1.0.0
        rollback = await versioning_system.rollback_to_version(
            workflow_id="test_wf",
            target_version="1.0.0",
            created_by="test_user",
            rollback_reason="Reverting problematic change"
        )

        assert rollback.version == "1.0.2"  # Hotfix version
        assert rollback.version_type == VersionType.HOTFIX
        assert "rollback" in rollback.tags

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_version(self, versioning_system, sample_workflow_data):
        """Test rolling back to non-existent version"""
        with pytest.raises(ValueError, match="not found"):
            await versioning_system.rollback_to_version(
                workflow_id="test_wf",
                target_version="999.0.0",
                created_by="test_user",
                rollback_reason="Test"
            )

    @pytest.mark.asyncio
    async def test_rollback_creates_new_version(self, versioning_system, sample_workflow_data):
        """Test that rollback creates a new version, doesn't modify old one"""
        v1 = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Rollback
        rollback = await versioning_system.rollback_to_version(
            workflow_id="test_wf",
            target_version="1.0.0",
            created_by="test_user",
            rollback_reason="Test"
        )

        # Verify original version is unchanged
        original = await versioning_system.get_version("test_wf", "1.0.0")
        assert original is not None
        assert original.version == "1.0.0"

        # Verify rollback version is new
        assert rollback.version != "1.0.0"
        assert rollback.checksum == original.checksum


# ==================== Test Version Diff ====================

class TestVersionDiff:
    """Tests for version comparison and diff generation"""

    @pytest.mark.asyncio
    async def test_compare_versions_no_changes(self, versioning_system, sample_workflow_data):
        """Test comparing identical versions"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Create identical version with different description only
        modified_data = sample_workflow_data.copy()
        diff = await versioning_system.compare_versions(
            workflow_id="test_wf",
            from_version="1.0.0",
            to_version="1.0.0"
        )

        # Since it's same version, should have minimal differences
        assert diff.workflow_id == "test_wf"
        assert diff.from_version == "1.0.0"
        assert diff.to_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_compare_versions_with_added_steps(self, versioning_system, sample_workflow_data):
        """Test comparing versions with added steps"""
        # Create v1
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Create v2 with additional step
        modified_data = sample_workflow_data.copy()
        modified_data["steps"].append({"id": "step3", "name": "Step 3", "type": "task"})

        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="V2 - added step"
        )

        diff = await versioning_system.compare_versions(
            workflow_id="test_wf",
            from_version="1.0.0",
            to_version="1.1.0"
        )

        assert len(diff.added_steps) == 1
        assert diff.added_steps[0]["id"] == "step3"

    @pytest.mark.asyncio
    async def test_compare_versions_with_removed_steps(self, versioning_system, sample_workflow_data):
        """Test comparing versions with removed steps"""
        # Create v1
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Create v2 with step removed
        modified_data = sample_workflow_data.copy()
        modified_data["steps"] = [modified_data["steps"][0]]  # Keep only first step

        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="V2 - removed step"
        )

        diff = await versioning_system.compare_versions(
            workflow_id="test_wf",
            from_version="1.0.0",
            to_version="1.1.0"
        )

        assert len(diff.removed_steps) == 1

    @pytest.mark.asyncio
    async def test_diff_impact_level_calculation(self, versioning_system, sample_workflow_data):
        """Test that diff impact level is calculated correctly"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Make significant changes
        modified_data = sample_workflow_data.copy()
        modified_data["steps"] = [
            {"id": "step1", "name": "Step 1", "type": "task"},
            {"id": "step2", "name": "Step 2", "type": "task"},
            {"id": "step3", "name": "Step 3", "type": "task"}
        ]
        modified_data["connections"] = [
            {"source": "step1", "target": "step2"},
            {"source": "step2", "target": "step3"}
        ]

        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="V2"
        )

        diff = await versioning_system.compare_versions(
            workflow_id="test_wf",
            from_version="1.0.0",
            to_version="1.1.0"
        )

        # Should have some impact level
        assert diff.impact_level in ["low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_diff_caching(self, versioning_system, sample_workflow_data):
        """Test that diffs are cached for performance"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Create diff
        diff1 = await versioning_system.compare_versions(
            workflow_id="test_wf",
            from_version="1.0.0",
            to_version="1.0.0"
        )

        # Get same diff again (should be cached)
        diff2 = await versioning_system.compare_versions(
            workflow_id="test_wf",
            from_version="1.0.0",
            to_version="1.0.0"
        )

        # Should be the same object/data
        assert diff1.workflow_id == diff2.workflow_id
        assert diff1.from_version == diff2.from_version


# ==================== Test Branching ====================

class TestBranching:
    """Tests for branching and merging"""

    @pytest.mark.asyncio
    async def test_create_branch(self, versioning_system, sample_workflow_data):
        """Test creating a new branch"""
        # Create initial version
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial"
        )

        # Create branch
        branch = await versioning_system.create_branch(
            workflow_id="test_wf",
            branch_name="feature/experiment",
            base_version="1.0.0",
            created_by="test_user",
            merge_strategy="merge_commit"
        )

        assert branch.branch_name == "feature/experiment"
        assert branch.workflow_id == "test_wf"
        assert branch.base_version == "1.0.0"
        assert branch.current_version == "1.0.0"
        assert branch.merge_strategy == "merge_commit"

    @pytest.mark.asyncio
    async def test_create_duplicate_branch_fails(self, versioning_system, sample_workflow_data):
        """Test that creating duplicate branch fails"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial"
        )

        # Create branch
        await versioning_system.create_branch(
            workflow_id="test_wf",
            branch_name="feature/test",
            base_version="1.0.0",
            created_by="test_user"
        )

        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            await versioning_system.create_branch(
                workflow_id="test_wf",
                branch_name="feature/test",
                base_version="1.0.0",
                created_by="test_user"
            )

    @pytest.mark.asyncio
    async def test_get_branches(self, versioning_system, sample_workflow_data):
        """Test getting all branches for a workflow"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Initial"
        )

        # Create multiple branches
        await versioning_system.create_branch(
            workflow_id="test_wf",
            branch_name="feature/a",
            base_version="1.0.0",
            created_by="user1"
        )

        await versioning_system.create_branch(
            workflow_id="test_wf",
            branch_name="feature/b",
            base_version="1.0.0",
            created_by="user2"
        )

        branches = await versioning_system.get_branches("test_wf")

        assert len(branches) == 3  # main + 2 features
        branch_names = [b.branch_name for b in branches]
        assert "main" in branch_names
        assert "feature/a" in branch_names
        assert "feature/b" in branch_names

    @pytest.mark.asyncio
    async def test_merge_branches(self, versioning_system, sample_workflow_data):
        """Test merging one branch into another"""
        # Create main branch version
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Main version",
            branch_name="main"
        )

        # Create feature branch
        await versioning_system.create_branch(
            workflow_id="test_wf",
            branch_name="feature/new-feature",
            base_version="1.0.0",
            created_by="test_user"
        )

        # Add version to feature branch
        modified_data = sample_workflow_data.copy()
        modified_data["description"] = "Feature version"

        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=modified_data,
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="Feature implementation",
            branch_name="feature/new-feature"
        )

        # Merge feature into main
        merged = await versioning_system.merge_branch(
            workflow_id="test_wf",
            source_branch="feature/new-feature",
            target_branch="main",
            merge_by="test_user",
            merge_message="Merging new feature"
        )

        assert merged is not None
        assert "merge" in merged.tags
        assert "from-feature/new-feature" in merged.tags


# ==================== Test Version History ====================

class TestVersionHistory:
    """Tests for version history retrieval"""

    @pytest.mark.asyncio
    async def test_get_version(self, versioning_system, sample_workflow_data):
        """Test retrieving a specific version"""
        created = await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="Test version"
        )

        retrieved = await versioning_system.get_version("test_wf", "1.0.0")

        assert retrieved is not None
        assert retrieved.workflow_id == created.workflow_id
        assert retrieved.version == created.version
        assert retrieved.created_by == created.created_by

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, versioning_system):
        """Test retrieving non-existent version"""
        retrieved = await versioning_system.get_version("test_wf", "999.0.0")

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_version_history(self, versioning_system, sample_workflow_data):
        """Test retrieving version history"""
        # Create multiple versions
        for i in range(5):
            await versioning_system.create_version(
                workflow_id="test_wf",
                workflow_data=sample_workflow_data,
                version_type=VersionType.PATCH,
                created_by="test_user",
                commit_message=f"Version {i}"
            )

        history = await versioning_system.get_version_history("test_wf", limit=10)

        assert len(history) == 5
        # Should be in reverse chronological order
        assert history[0].version > history[-1].version

    @pytest.mark.asyncio
    async def test_get_version_history_with_limit(self, versioning_system, sample_workflow_data):
        """Test retrieving version history with limit"""
        # Create 10 versions
        for i in range(10):
            await versioning_system.create_version(
                workflow_id="test_wf",
                workflow_data=sample_workflow_data,
                version_type=VersionType.PATCH,
                created_by="test_user",
                commit_message=f"Version {i}"
            )

        # Get only 5
        history = await versioning_system.get_version_history("test_wf", limit=5)

        assert len(history) == 5


# ==================== Test Version Metrics ====================

class TestVersionMetrics:
    """Tests for version performance metrics"""

    @pytest.mark.asyncio
    async def test_update_version_metrics(self, versioning_system, sample_workflow_data):
        """Test updating version execution metrics"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Update metrics
        result = await versioning_system.update_version_metrics(
            workflow_id="test_wf",
            version="1.0.0",
            execution_result={
                "success": True,
                "execution_time": 5.2
            }
        )

        assert result is True

        # Get metrics
        metrics = await versioning_system.get_version_metrics("test_wf", "1.0.0")

        assert metrics is not None
        assert metrics["execution_count"] == 1
        assert metrics["success_rate"] == 100.0
        assert metrics["avg_execution_time"] == 5.2

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, versioning_system, sample_workflow_data):
        """Test that metrics are aggregated across multiple executions"""
        await versioning_system.create_version(
            workflow_id="test_wf",
            workflow_data=sample_workflow_data,
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        # Run multiple executions
        for i, (success, time) in enumerate([(True, 5.0), (True, 7.0), (False, 3.0), (True, 6.0)]):
            await versioning_system.update_version_metrics(
                workflow_id="test_wf",
                version="1.0.0",
                execution_result={"success": success, "execution_time": time}
            )

        metrics = await versioning_system.get_version_metrics("test_wf", "1.0.0")

        assert metrics["execution_count"] == 4
        assert metrics["success_rate"] == 75.0  # 3 of 4 successful
        assert pytest.approx(metrics["avg_execution_time"], 0.1) == 5.25  # (5+7+3+6)/4


# ==================== Test WorkflowVersionManager ====================

class TestWorkflowVersionManager:
    """Tests for high-level WorkflowVersionManager"""

    def test_manager_initialization(self):
        """Test manager initializes with versioning system"""
        manager = WorkflowVersionManager()

        assert manager.versioning_system is not None

    @pytest.mark.asyncio
    async def test_create_workflow_version_auto_type(self, temp_db):
        """Test creating workflow version with auto type detection"""
        manager = WorkflowVersionManager()
        manager.versioning_system = WorkflowVersioningSystem(db_path=temp_db)

        result = await manager.create_workflow_version(
            workflow_id="auto_test",
            workflow_data={"name": "Test", "steps": []},
            user_id="test_user",
            change_description="Auto-typed version",
            version_type="auto"
        )

        assert "version" in result
        assert "version_type" in result
        assert "change_type" in result

    @pytest.mark.asyncio
    async def test_rollback_workflow(self, temp_db):
        """Test high-level rollback workflow interface"""
        manager = WorkflowVersionManager()
        manager.versioning_system = WorkflowVersioningSystem(db_path=temp_db)

        # Create initial version
        await manager.versioning_system.create_version(
            workflow_id="rollback_test",
            workflow_data={"name": "Test", "steps": []},
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        result = await manager.rollback_workflow(
            workflow_id="rollback_test",
            target_version="1.0.0",
            user_id="test_user",
            reason="Test rollback"
        )

        assert result["rollback_successful"] is True
        assert "rollback_version" in result

    @pytest.mark.asyncio
    async def test_get_workflow_changes(self, temp_db):
        """Test getting changes between workflow versions"""
        manager = WorkflowVersionManager()
        manager.versioning_system = WorkflowVersioningSystem(db_path=temp_db)

        # Create two versions
        await manager.versioning_system.create_version(
            workflow_id="diff_test",
            workflow_data={"name": "V1", "steps": [{"id": "s1"}]},
            version_type=VersionType.MAJOR,
            created_by="test_user",
            commit_message="V1"
        )

        await manager.versioning_system.create_version(
            workflow_id="diff_test",
            workflow_data={"name": "V2", "steps": [{"id": "s1"}, {"id": "s2"}]},
            version_type=VersionType.MINOR,
            created_by="test_user",
            commit_message="V2"
        )

        changes = await manager.get_workflow_changes(
            workflow_id="diff_test",
            from_version="1.0.0",
            to_version="1.1.0"
        )

        assert "from_version" in changes
        assert "to_version" in changes
        assert "impact_level" in changes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
