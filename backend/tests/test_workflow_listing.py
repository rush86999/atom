"""
Tests for Improved Workflow Listing from State Manager
Tests comprehensive filtering, sorting, and pagination of workflows.
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from core.advanced_workflow_system import (
    StateManager,
    WorkflowState,
    AdvancedWorkflowDefinition
)


@pytest.fixture
def state_manager():
    """Create StateManager instance"""
    return StateManager()


@pytest.fixture
def sample_workflows(state_manager):
    """Create sample workflows for testing"""
    # Clear any existing workflows
    state_manager.state_store.clear()

    # Clear any existing workflow files
    import os
    import shutil
    if os.path.exists("workflow_states"):
        shutil.rmtree("workflow_states")

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    workflows = [
        {
            "workflow_id": "workflow_001",
            "name": "Data Pipeline",
            "description": "ETL workflow for data processing",
            "state": WorkflowState.RUNNING,
            "category": "data",
            "tags": ["automation", "etl", "critical"],
            "created_at": two_days_ago.isoformat(),
            "updated_at": yesterday.isoformat(),
            "steps": [{"step_id": "step1"}, {"step_id": "step2"}]
        },
        {
            "workflow_id": "workflow_002",
            "name": "Email Campaign",
            "description": "Marketing email automation",
            "state": WorkflowState.COMPLETED,
            "category": "marketing",
            "tags": ["automation", "email"],
            "created_at": yesterday.isoformat(),
            "updated_at": now.isoformat(),
            "steps": [{"step_id": "step1"}]
        },
        {
            "workflow_id": "workflow_003",
            "name": "Report Generator",
            "description": "Daily report generation",
            "state": WorkflowState.DRAFT,
            "category": "reporting",
            "tags": ["reports", "daily"],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "steps": [{"step_id": "step1"}, {"step_id": "step2"}, {"step_id": "step3"}]
        },
        {
            "workflow_id": "workflow_004",
            "name": "Backup Process",
            "description": "Automated backup system",
            "state": WorkflowState.RUNNING,
            "category": "data",
            "tags": ["automation", "backup"],
            "created_at": two_days_ago.isoformat(),
            "updated_at": now.isoformat(),
            "steps": [{"step_id": "step1"}]
        },
        {
            "workflow_id": "workflow_005",
            "name": "API Integration",
            "description": "Third-party API integration",
            "state": WorkflowState.FAILED,
            "category": "integration",
            "tags": ["api", "external"],
            "created_at": yesterday.isoformat(),
            "updated_at": yesterday.isoformat(),
            "steps": []
        }
    ]

    # Save all workflows
    for workflow in workflows:
        state_manager.save_state(workflow["workflow_id"], workflow)

    return workflows


class TestWorkflowListing:
    """Test workflow listing functionality"""

    def test_list_all_workflows(self, state_manager, sample_workflows):
        """Test listing all workflows without filters"""
        workflows = state_manager.list_workflows()

        assert len(workflows) == 5
        assert all("workflow_id" in w for w in workflows)
        assert all("name" in w for w in workflows)
        assert all("status" in w for w in workflows)

    def test_list_workflows_with_status_filter(self, state_manager):
        """Test filtering workflows by status"""
        # Get only running workflows
        running_workflows = state_manager.list_workflows(status="running")

        assert len(running_workflows) == 2
        assert all(w["status"] == "running" for w in running_workflows)
        assert set([w["workflow_id"] for w in running_workflows]) == {"workflow_001", "workflow_004"}

        # Get only completed workflows
        completed_workflows = state_manager.list_workflows(status="completed")

        assert len(completed_workflows) == 1
        assert completed_workflows[0]["workflow_id"] == "workflow_002"

    def test_list_workflows_with_category_filter(self, state_manager):
        """Test filtering workflows by category"""
        # Get only data category workflows
        data_workflows = state_manager.list_workflows(category="data")

        assert len(data_workflows) == 2
        assert all(w["category"] == "data" for w in data_workflows)
        assert set([w["workflow_id"] for w in data_workflows]) == {"workflow_001", "workflow_004"}

    def test_list_workflows_with_tag_filter(self, state_manager):
        """Test filtering workflows by tags"""
        # Get workflows with "automation" tag
        automation_workflows = state_manager.list_workflows(tags=["automation"])

        assert len(automation_workflows) == 3
        assert all("automation" in w.get("tags", []) for w in automation_workflows)

        # Get workflows with multiple tags (must have ALL specified)
        # Use "etl" and "critical" which appear together in workflow_001
        multi_tag_workflows = state_manager.list_workflows(tags=["etl", "critical"])

        assert len(multi_tag_workflows) == 1
        assert multi_tag_workflows[0]["workflow_id"] == "workflow_001"

    def test_list_workflows_with_combined_filters(self, state_manager):
        """Test filtering workflows with multiple filters"""
        # Get running workflows in data category
        filtered = state_manager.list_workflows(
            status="running",
            category="data"
        )

        assert len(filtered) == 2
        assert all(w["status"] == "running" for w in filtered)
        assert all(w["category"] == "data" for w in filtered)

    def test_list_workflows_sorting(self, state_manager):
        """Test sorting workflows by different fields"""
        # Sort by updated_at descending (default)
        workflows_desc = state_manager.list_workflows(sort_by="updated_at", sort_order="desc")

        assert len(workflows_desc) == 5
        # Most recently updated should be first
        assert workflows_desc[0]["workflow_id"] in ["workflow_002", "workflow_003", "workflow_004"]

        # Sort by name ascending
        workflows_name_asc = state_manager.list_workflows(sort_by="name", sort_order="asc")

        assert len(workflows_name_asc) == 5
        # Check alphabetical order
        names = [w["name"] for w in workflows_name_asc]
        assert names == sorted(names)

    def test_list_workflows_pagination(self, state_manager):
        """Test pagination of workflow listings"""
        # Get first 2 workflows
        page1 = state_manager.list_workflows(limit=2, offset=0)

        assert len(page1) == 2

        # Get next 2 workflows
        page2 = state_manager.list_workflows(limit=2, offset=2)

        assert len(page2) == 2

        # Verify no duplicates between pages
        page1_ids = {w["workflow_id"] for w in page1}
        page2_ids = {w["workflow_id"] for w in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_list_workflows_empty_result(self, state_manager):
        """Test listing workflows with filters that return no results"""
        # Filter by non-existent category
        empty = state_manager.list_workflows(category="nonexistent")

        assert len(empty) == 0

        # Filter by non-existent tag
        empty = state_manager.list_workflows(tags=["nonexistent_tag"])

        assert len(empty) == 0


class TestWorkflowListingMemoryAndFile:
    """Test workflow listing with both in-memory and file-based workflows"""

    def test_list_workflows_includes_memory(self, state_manager):
        """Test that in-memory workflows are included in listings"""
        # Create a workflow only in memory (not persisted)
        memory_workflow = {
            "workflow_id": "memory_workflow",
            "name": "Memory Only Workflow",
            "state": WorkflowState.DRAFT,
            "category": "test",
            "tags": ["memory"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "steps": []
        }

        # Save to memory (won't persist to file if state_manager is mocked)
        state_manager.state_store["memory_workflow"] = memory_workflow

        # List workflows
        workflows = state_manager.list_workflows()

        # Should include the in-memory workflow
        workflow_ids = [w["workflow_id"] for w in workflows]
        assert "memory_workflow" in workflow_ids

    def test_list_workflows_no_duplicates(self, state_manager):
        """Test that workflows in both memory and file aren't duplicated"""
        # Create workflow that exists in both memory and file
        workflow_data = {
            "workflow_id": "duplicate_test",
            "name": "Duplicate Test",
            "state": WorkflowState.DRAFT,
            "category": "test",
            "tags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "steps": []
        }

        # Save to both memory and file
        state_manager.state_store["duplicate_test"] = workflow_data
        state_manager.save_state("duplicate_test", workflow_data)

        # List workflows
        workflows = state_manager.list_workflows()

        # Should only appear once
        duplicates = [w for w in workflows if w["workflow_id"] == "duplicate_test"]
        assert len(duplicates) == 1


class TestWorkflowSummaryCreation:
    """Test workflow summary creation"""

    def test_create_workflow_summary(self, state_manager):
        """Test creating a workflow summary"""
        workflow_state = {
            "workflow_id": "test_workflow",
            "name": "Test Workflow",
            "description": "Test description",
            "state": WorkflowState.RUNNING,
            "category": "test",
            "tags": ["tag1", "tag2"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "steps": [{"step_id": "step1"}, {"step_id": "step2"}, {"step_id": "step3"}],
            "version": "2.0",
            "created_by": "user123"
        }

        summary = state_manager._create_workflow_summary("test_workflow", workflow_state)

        assert summary["workflow_id"] == "test_workflow"
        assert summary["name"] == "Test Workflow"
        assert summary["status"] == "running"
        assert summary["category"] == "test"
        assert summary["tags"] == ["tag1", "tag2"]
        assert summary["total_steps"] == 3
        assert summary["version"] == "2.0"
        assert summary["created_by"] == "user123"

    def test_create_workflow_summary_defaults(self, state_manager):
        """Test workflow summary with missing optional fields"""
        workflow_state = {
            "workflow_id": "minimal_workflow",
            "name": "Minimal Workflow",
            "state": WorkflowState.DRAFT,
            "steps": []
        }

        summary = state_manager._create_workflow_summary("minimal_workflow", workflow_state)

        assert summary["workflow_id"] == "minimal_workflow"
        assert summary["category"] == "general"  # Default
        assert summary["tags"] == []  # Default
        assert summary["total_steps"] == 0
        assert summary["version"] == "1.0"  # Default


class TestWorkflowFilterMatching:
    """Test workflow filter matching logic"""

    def test_matches_filters_all_pass(self, state_manager):
        """Test filter matching with no filters"""
        summary = {
            "status": "running",
            "category": "data",
            "tags": ["automation", "critical"]
        }

        assert state_manager._matches_filters(summary) is True

    def test_matches_filters_status(self, state_manager):
        """Test status filter matching"""
        summary = {
            "status": "running",
            "category": "data",
            "tags": ["automation"]
        }

        assert state_manager._matches_filters(summary, status="running") is True
        assert state_manager._matches_filters(summary, status="completed") is False

    def test_matches_filters_category(self, state_manager):
        """Test category filter matching"""
        summary = {
            "status": "running",
            "category": "data",
            "tags": ["automation"]
        }

        assert state_manager._matches_filters(summary, category="data") is True
        assert state_manager._matches_filters(summary, category="marketing") is False

    def test_matches_filters_tags(self, state_manager):
        """Test tag filter matching"""
        summary = {
            "status": "running",
            "category": "data",
            "tags": ["automation", "critical", "etl"]
        }

        # Must have ALL specified tags
        assert state_manager._matches_filters(summary, tags=["automation"]) is True
        assert state_manager._matches_filters(summary, tags=["automation", "critical"]) is True
        assert state_manager._matches_filters(summary, tags=["automation", "email"]) is False

    def test_matches_filters_combined(self, state_manager):
        """Test combined filter matching"""
        summary = {
            "status": "running",
            "category": "data",
            "tags": ["automation", "critical"]
        }

        # All filters match
        assert state_manager._matches_filters(
            summary,
            status="running",
            category="data",
            tags=["automation"]
        ) is True

        # Status doesn't match
        assert state_manager._matches_filters(
            summary,
            status="completed",
            category="data",
            tags=["automation"]
        ) is False

        # Category doesn't match
        assert state_manager._matches_filters(
            summary,
            status="running",
            category="marketing",
            tags=["automation"]
        ) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
