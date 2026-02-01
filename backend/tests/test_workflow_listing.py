"""
Tests for Workflow Listing Implementation
Tests the proper listing of workflows from state manager with filtering.
"""

import pytest
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from core.advanced_workflow_system import StateManager, WorkflowState


@pytest.fixture
def temp_state_dir():
    """Create a temporary directory for workflow states"""
    temp_dir = tempfile.mkdtemp()
    original_cwd = os.getcwd()

    # Change to temp directory
    os.chdir(temp_dir)

    # Create workflow_states directory
    os.makedirs("workflow_states", exist_ok=True)

    yield temp_dir

    # Cleanup
    os.chdir(original_cwd)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def state_manager(temp_state_dir):
    """Create a StateManager instance with temp directory"""
    return StateManager()


@pytest.fixture
def sample_workflows(state_manager):
    """Create sample workflow states for testing"""
    workflows = [
        {
            "workflow_id": "wf_001",
            "name": "Active Marketing Workflow",
            "description": "Process marketing leads",
            "status": "active",
            "category": "marketing",
            "tags": ["leads", "automation"],
            "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
            "updated_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            "current_step": 2,
            "total_steps": 5,
            "steps": [{"step_id": f"step_{i}"} for i in range(5)]
        },
        {
            "workflow_id": "wf_002",
            "name": "Completed Sales Workflow",
            "description": "Sales qualification process",
            "status": "completed",
            "category": "sales",
            "tags": ["sales", "qualification"],
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "updated_at": (datetime.now() - timedelta(hours=3)).isoformat(),
            "current_step": 5,
            "total_steps": 5,
            "steps": [{"step_id": f"step_{i}"} for i in range(5)]
        },
        {
            "workflow_id": "wf_003",
            "name": "Failed Data Processing",
            "description": "Data ETL workflow that failed",
            "status": "failed",
            "category": "data",
            "tags": ["etl", "processing"],
            "created_at": (datetime.now() - timedelta(hours=5)).isoformat(),
            "updated_at": (datetime.now() - timedelta(hours=4)).isoformat(),
            "current_step": 3,
            "total_steps": 8,
            "steps": [{"step_id": f"step_{i}"} for i in range(8)]
        },
        {
            "workflow_id": "wf_004",
            "name": "Active HR Workflow",
            "description": "Employee onboarding",
            "status": "active",
            "category": "hr",
            "tags": ["onboarding", "hr"],
            "created_at": (datetime.now() - timedelta(hours=6)).isoformat(),
            "updated_at": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "current_step": 1,
            "total_steps": 10,
            "steps": [{"step_id": f"step_{i}"} for i in range(10)]
        },
        {
            "workflow_id": "wf_005",
            "name": "Paused Finance Workflow",
            "description": "Invoice processing (paused for approval)",
            "status": "paused",
            "category": "finance",
            "tags": ["invoice", "approval"],
            "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "updated_at": (datetime.now() - timedelta(hours=12)).isoformat(),
            "current_step": 4,
            "total_steps": 6,
            "steps": [{"step_id": f"step_{i}"} for i in range(6)]
        }
    ]

    # Save all workflows
    for wf in workflows:
        state_manager.save_state(wf["workflow_id"], wf)

    return workflows


class TestWorkflowListing:
    """Test suite for workflow listing functionality"""

    def test_list_all_workflows(self, state_manager, sample_workflows):
        """Test listing all workflows without filters"""
        workflows = state_manager.list_workflows()

        assert len(workflows) == 5
        workflow_ids = {w["workflow_id"] for w in workflows}
        assert workflow_ids == {"wf_001", "wf_002", "wf_003", "wf_004", "wf_005"}

    def test_list_workflows_by_status_active(self, state_manager, sample_workflows):
        """Test listing only active workflows"""
        workflows = state_manager.list_workflows(status="active")

        assert len(workflows) == 2
        workflow_ids = {w["workflow_id"] for w in workflows}
        assert workflow_ids == {"wf_001", "wf_004"}

        # Verify all have active status
        for wf in workflows:
            assert wf["status"] == "active"

    def test_list_workflows_by_status_completed(self, state_manager, sample_workflows):
        """Test listing only completed workflows"""
        workflows = state_manager.list_workflows(status="completed")

        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "wf_002"
        assert workflows[0]["status"] == "completed"

    def test_list_workflows_by_status_failed(self, state_manager, sample_workflows):
        """Test listing only failed workflows"""
        workflows = state_manager.list_workflows(status="failed")

        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "wf_003"
        assert workflows[0]["status"] == "failed"

    def test_list_workflows_by_status_paused(self, state_manager, sample_workflows):
        """Test listing only paused workflows"""
        workflows = state_manager.list_workflows(status="paused")

        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "wf_005"
        assert workflows[0]["status"] == "paused"

    def test_list_workflows_by_status_nonexistent(self, state_manager, sample_workflows):
        """Test listing workflows with non-existent status"""
        workflows = state_manager.list_workflows(status="cancelled")

        assert len(workflows) == 0

    def test_list_workflows_sorted_by_updated_at(self, state_manager, sample_workflows):
        """Test that workflows are sorted by updated_at descending"""
        workflows = state_manager.list_workflows()

        # Check that they are sorted by updated_at (most recent first)
        updated_times = [wf["updated_at"] for wf in workflows]
        assert updated_times == sorted(updated_times, reverse=True)

    def test_workflow_summary_structure(self, state_manager, sample_workflows):
        """Test that workflow summaries have correct structure"""
        workflows = state_manager.list_workflows()

        for wf in workflows:
            # Check required fields
            assert "workflow_id" in wf
            assert "name" in wf
            assert "description" in wf
            assert "status" in wf
            assert "created_at" in wf
            assert "updated_at" in wf
            assert "saved_at" in wf
            assert "current_step" in wf
            assert "total_steps" in wf
            assert "category" in wf
            assert "tags" in wf

            # Check types
            assert isinstance(wf["workflow_id"], str)
            assert isinstance(wf["name"], str)
            assert isinstance(wf["status"], str)
            assert isinstance(wf["total_steps"], int)
            assert isinstance(wf["category"], str)
            assert isinstance(wf["tags"], list)

    def test_list_workflows_empty_directory(self, state_manager):
        """Test listing workflows when directory is empty"""
        # Create new state manager with empty directory
        empty_manager = StateManager()
        workflows = empty_manager.list_workflows()

        assert len(workflows) == 0
        assert workflows == []

    def test_list_workflows_no_directory(self, temp_state_dir):
        """Test listing workflows when workflow_states directory doesn't exist"""
        # Remove the directory
        import shutil
        if os.path.exists("workflow_states"):
            shutil.rmtree("workflow_states")

        state_manager = StateManager()
        workflows = state_manager.list_workflows()

        assert len(workflows) == 0

    def test_workflow_preserves_step_information(self, state_manager, sample_workflows):
        """Test that workflow summaries include step information"""
        workflows = state_manager.list_workflows()

        for wf in workflows:
            # Find original workflow
            original = next((w for w in sample_workflows if w["workflow_id"] == wf["workflow_id"]), None)
            assert original is not None

            # Check step info matches
            assert wf["current_step"] == original["current_step"]
            assert wf["total_steps"] == original["total_steps"]

    def test_workflow_preserves_metadata(self, state_manager, sample_workflows):
        """Test that workflow summaries preserve category and tags"""
        workflows = state_manager.list_workflows()

        for wf in workflows:
            # Find original workflow
            original = next((w for w in sample_workflows if w["workflow_id"] == wf["workflow_id"]), None)
            assert original is not None

            # Check metadata matches
            assert wf["category"] == original["category"]
            assert set(wf["tags"]) == set(original["tags"])


class TestWorkflowListingIntegration:
    """Integration tests for workflow listing with state manager"""

    def test_list_after_crud_operations(self, state_manager):
        """Test listing workflows after create, update, delete operations"""
        # Initially empty
        workflows = state_manager.list_workflows()
        assert len(workflows) == 0

        # Create a workflow
        wf1 = {
            "workflow_id": "test_wf_1",
            "name": "Test Workflow 1",
            "status": "active",
            "category": "test",
            "tags": ["test"],
            "created_at": datetime.now().isoformat(),
            "steps": []
        }
        state_manager.save_state("test_wf_1", wf1)

        workflows = state_manager.list_workflows()
        assert len(workflows) == 1

        # Create another workflow
        wf2 = {
            "workflow_id": "test_wf_2",
            "name": "Test Workflow 2",
            "status": "completed",
            "category": "test",
            "tags": ["test"],
            "created_at": datetime.now().isoformat(),
            "steps": []
        }
        state_manager.save_state("test_wf_2", wf2)

        workflows = state_manager.list_workflows()
        assert len(workflows) == 2

        # Delete a workflow
        state_manager.delete_state("test_wf_1")

        workflows = state_manager.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "test_wf_2"

    def test_list_with_malformed_workflow_files(self, state_manager):
        """Test listing workflows when some files are malformed"""
        # Create valid workflow
        valid_wf = {
            "workflow_id": "valid_wf",
            "name": "Valid Workflow",
            "status": "active",
            "category": "test",
            "tags": [],
            "created_at": datetime.now().isoformat(),
            "steps": []
        }
        state_manager.save_state("valid_wf", valid_wf)

        # Create malformed JSON file
        with open("workflow_states/malformed_wf.json", "w") as f:
            f.write("{ invalid json }")

        # Should only return valid workflow
        workflows = state_manager.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "valid_wf"

    def test_list_with_memory_cached_workflows(self, state_manager):
        """Test that memory-cached workflows are included in listing"""
        # Save workflow (goes to memory and file)
        wf = {
            "workflow_id": "cached_wf",
            "name": "Cached Workflow",
            "status": "active",
            "category": "test",
            "tags": [],
            "created_at": datetime.now().isoformat(),
            "steps": []
        }
        state_manager.save_state("cached_wf", wf)

        # Workflow should be in memory cache
        assert "cached_wf" in state_manager.state_store

        # List should find it
        workflows = state_manager.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "cached_wf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
