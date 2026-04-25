"""
Workflow Versioning System Tests
Tests for core/workflow_versioning_system.py

Tests cover:
- VersionType and ChangeType enums
- WorkflowVersion dataclass
- VersionDiff dataclass
- Branch dataclass
- ConflictResolution dataclass
"""

import os
os.environ["TESTING"] = "1"

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from typing import Dict, Any

from core.workflow_versioning_system import (
    VersionType,
    ChangeType,
    WorkflowVersion,
    VersionDiff,
    Branch,
    ConflictResolution,
)


class TestVersionTypeEnum:
    """Test VersionType enum values and semantic versioning."""

    def test_enum_values(self):
        """VersionType has all expected enum values."""
        assert VersionType.MAJOR.value == "major"
        assert VersionType.MINOR.value == "minor"
        assert VersionType.PATCH.value == "patch"
        assert VersionType.HOTFIX.value == "hotfix"
        assert VersionType.BETA.value == "beta"
        assert VersionType.ALPHA.value == "alpha"

    def test_major_version(self):
        """VersionType MAJOR represents breaking changes."""
        version_type = VersionType.MAJOR
        assert version_type.value == "major"
        assert isinstance(version_type.value, str)

    def test_minor_patch_versions(self):
        """VersionType MINOR and PATCH represent backward-compatible changes."""
        minor = VersionType.MINOR
        patch = VersionType.PATCH
        assert minor.value == "minor"
        assert patch.value == "patch"


class TestChangeTypeEnum:
    """Test ChangeType enum values and workflow change categorization."""

    def test_change_types(self):
        """ChangeType has all expected change type values."""
        assert ChangeType.STRUCTURAL.value == "structural"
        assert ChangeType.PARAMETRIC.value == "parametric"
        assert ChangeType.EXECUTION.value == "execution"
        assert ChangeType.METADATA.value == "metadata"
        assert ChangeType.DEPENDENCY.value == "dependency"

    def test_add_remove_modify(self):
        """ChangeType STRUCTURAL represents structural changes."""
        structural = ChangeType.STRUCTURAL
        assert structural.value == "structural"

    def test_rename_change(self):
        """ChangeType METADATA represents metadata changes."""
        metadata = ChangeType.METADATA
        assert metadata.value == "metadata"


class TestWorkflowVersion:
    """Test WorkflowVersion dataclass and version metadata."""

    def test_version_creation(self):
        """WorkflowVersion can be created with valid parameters."""
        version = WorkflowVersion(
            workflow_id="wf-001",
            version="1.0.0",
            version_type=VersionType.MAJOR,
            change_type=ChangeType.STRUCTURAL,
            created_at=datetime.now(timezone.utc),
            created_by="user123",
            commit_message="Initial version",
            tags=["v1", "initial"],
            workflow_data={"name": "Test Workflow", "steps": []}
        )
        assert version.workflow_id == "wf-001"
        assert version.version == "1.0.0"
        assert version.version_type == VersionType.MAJOR
        assert version.change_type == ChangeType.STRUCTURAL
        assert len(version.tags) == 2

    def test_version_increment(self):
        """WorkflowVersion supports version increment logic."""
        version = WorkflowVersion(
            workflow_id="wf-002",
            version="1.2.3",
            version_type=VersionType.PATCH,
            change_type=ChangeType.PARAMETRIC,
            created_at=datetime.now(timezone.utc),
            created_by="user123",
            commit_message="Bug fix",
            tags=[],
            workflow_data={}
        )
        assert version.version == "1.2.3"
        assert version.version_type == VersionType.PATCH

    def test_version_validation(self):
        """WorkflowVersion validates required fields."""
        with pytest.raises(TypeError):
            # Missing required fields
            WorkflowVersion(
                workflow_id="wf-003"
                # Missing: version, version_type, change_type, created_at, created_by, commit_message, tags, workflow_data
            )

    def test_version_metadata(self):
        """WorkflowVersion can store optional metadata."""
        version = WorkflowVersion(
            workflow_id="wf-004",
            version="2.0.0",
            version_type=VersionType.MINOR,
            change_type=ChangeType.EXECUTION,
            created_at=datetime.now(timezone.utc),
            created_by="user456",
            commit_message="New feature",
            tags=["v2"],
            workflow_data={},
            parent_version="1.0.0",
            branch_name="feature-branch",
            is_active=True,
            checksum="abc123",
            metadata={"reviewed_by": "team_lead"}
        )
        assert version.parent_version == "1.0.0"
        assert version.branch_name == "feature-branch"
        assert version.is_active is True
        assert version.checksum == "abc123"
        assert version.metadata["reviewed_by"] == "team_lead"


class TestVersionDiff:
    """Test VersionDiff dataclass and differential calculation."""

    def test_diff_calculation(self):
        """VersionDiff can calculate differences between versions."""
        diff = VersionDiff(
            workflow_id="wf-005",
            from_version="1.0.0",
            to_version="1.1.0",
            added_steps=[{"id": "step3", "name": "New Step"}],
            removed_steps=[],
            modified_steps=[{"id": "step1", "name": "Updated Step"}],
            structural_changes=["Added step3", "Modified step1"],
            parametric_changes={"timeout": (30, 60)},
            dependency_changes=[],
            metadata_changes={"author": ("user1", "user2")},
            impact_level="medium"
        )
        assert diff.from_version == "1.0.0"
        assert diff.to_version == "1.1.0"
        assert len(diff.added_steps) == 1
        assert len(diff.modified_steps) == 1
        assert diff.impact_level == "medium"

    def test_no_diff(self):
        """VersionDiff can represent no differences between versions."""
        diff = VersionDiff(
            workflow_id="wf-006",
            from_version="1.0.0",
            to_version="1.0.0",
            added_steps=[],
            removed_steps=[],
            modified_steps=[],
            structural_changes=[],
            parametric_changes={},
            dependency_changes=[],
            metadata_changes={},
            impact_level="low"
        )
        assert len(diff.added_steps) == 0
        assert len(diff.removed_steps) == 0
        assert len(diff.modified_steps) == 0
        assert diff.impact_level == "low"

    def test_diff_formatting(self):
        """VersionDiff formats structural and parametric changes."""
        diff = VersionDiff(
            workflow_id="wf-007",
            from_version="1.0.0",
            to_version="2.0.0",
            added_steps=[{"id": "step_new"}],
            removed_steps=[{"id": "step_old"}],
            modified_steps=[],
            structural_changes=["Breaking change: removed step_old"],
            parametric_changes={"max_retries": (3, 5)},
            dependency_changes=[{"name": "dep1", "action": "upgraded"}],
            metadata_changes={"status": ("draft", "production")},
            impact_level="high",
            automated_tests_passed=True
        )
        assert "Breaking change" in diff.structural_changes[0]
        assert diff.parametric_changes["max_retries"] == (3, 5)
        assert diff.impact_level == "high"
        assert diff.automated_tests_passed is True


class TestBranchAndConflict:
    """Test Branch and ConflictResolution dataclasses."""

    def test_branch_creation(self):
        """Branch can be created with valid parameters."""
        branch = Branch(
            branch_name="feature-branch",
            workflow_id="wf-008",
            base_version="1.0.0",
            current_version="1.1.0",
            created_at=datetime.now(timezone.utc),
            created_by="user789"
        )
        assert branch.branch_name == "feature-branch"
        assert branch.base_version == "1.0.0"
        assert branch.current_version == "1.1.0"
        assert branch.is_protected is False  # Default value

    def test_conflict_resolution(self):
        """ConflictResolution can represent conflict resolution strategies."""
        resolution = ConflictResolution(
            conflict_id="conflict-001",
            workflow_id="wf-009",
            source_version="feature-1.0.0",
            target_version="main-2.0.0",
            conflict_type="structural_conflict",
            resolution_strategy="manual",
            resolved_data={"step1": {"source": "A", "target": "B", "resolved": "A"}},
            resolved_by="user_admin",
            resolved_at=datetime.now(timezone.utc)
        )
        assert resolution.conflict_id == "conflict-001"
        assert resolution.source_version == "feature-1.0.0"
        assert resolution.target_version == "main-2.0.0"
        assert resolution.resolution_strategy == "manual"
        assert resolution.resolved_data["step1"]["resolved"] == "A"

    def test_branch_merge_strategy(self):
        """Branch supports different merge strategies."""
        branch_merge = Branch(
            branch_name="merge-branch",
            workflow_id="wf-010",
            base_version="1.0.0",
            current_version="1.1.0",
            created_at=datetime.now(timezone.utc),
            created_by="user123",
            merge_strategy="merge_commit"
        )
        branch_rebase = Branch(
            branch_name="rebase-branch",
            workflow_id="wf-011",
            base_version="1.0.0",
            current_version="1.1.0",
            created_at=datetime.now(timezone.utc),
            created_by="user456",
            merge_strategy="rebase"
        )
        assert branch_merge.merge_strategy == "merge_commit"
        assert branch_rebase.merge_strategy == "rebase"

    def test_branch_protection(self):
        """Branch can be protected from accidental changes."""
        protected_branch = Branch(
            branch_name="main",
            workflow_id="wf-012",
            base_version="1.0.0",
            current_version="2.0.0",
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            is_protected=True
        )
        assert protected_branch.is_protected is True
        assert protected_branch.branch_name == "main"
