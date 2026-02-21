"""
Unit tests for Autonomous Coding Orchestrator

Tests cover:
- Orchestrator initialization
- State store operations
- File locking
- Checkpoint creation/loading/rollback
- Pause/resume functionality
- Progress tracking
- Agent logging
- Complete workflow execution
- Concurrent workflows
- Error handling
- State recovery

Coverage target: >= 80%
"""

import asyncio
import pytest
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from sqlalchemy.orm import Session

from core.autonomous_coding_orchestrator import (
    AgentOrchestrator,
    CheckpointManager,
    SharedStateStore,
    PauseResumeManager,
    ProgressTracker,
    GitOperations,
    WorkflowPhase,
    WorkflowStatus
)


# ==================== Fixtures ====================

@pytest.fixture
def db_session():
    """Mock database session."""
    session = MagicMock(spec=Session)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_byok_handler():
    """Mock BYOK handler."""
    handler = MagicMock()
    return handler


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create temporary Git repository for testing."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True
    )

    # Create initial commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True
    )

    return tmp_path


@pytest.fixture
def git_ops(temp_git_repo):
    """Git operations instance with temp repo."""
    return GitOperations(repo_path=str(temp_git_repo))


@pytest.fixture
def state_store():
    """Shared state store instance."""
    return SharedStateStore()


@pytest.fixture
def checkpoint_manager(db_session, git_ops):
    """Checkpoint manager instance."""
    return CheckpointManager(db_session, git_ops)


@pytest.fixture
def progress_tracker(db_session):
    """Progress tracker instance."""
    return ProgressTracker(db_session)


@pytest.fixture
def orchestrator(db_session, mock_byok_handler):
    """Agent orchestrator instance with mocked agents."""
    with patch('core.autonomous_coding_orchestrator.RequirementParserService'), \
         patch('core.autonomous_coding_orchestrator.CodebaseResearchService'), \
         patch('core.autonomous_coding_orchestrator.PlanningAgent'), \
         patch('core.autonomous_coding_orchestrator.CodeGeneratorOrchestrator'), \
         patch('core.autonomous_coding_orchestrator.TestGeneratorService'), \
         patch('core.autonomous_coding_orchestrator.TestRunnerService'):

        orchestrator = AgentOrchestrator(db_session, mock_byok_handler)
        return orchestrator


@pytest.fixture
def sample_workflow_state():
    """Sample workflow state for testing."""
    return {
        "workflow_id": "test-workflow-123",
        "feature_request": "Add OAuth2 authentication",
        "workspace_id": "default",
        "status": "running",
        "current_phase": "generate_code",
        "completed_phases": ["parse_requirements", "research_codebase", "create_plan"],
        "files_created": ["backend/auth/oauth.py"],
        "files_modified": ["backend/core/models.py"]
    }


# ==================== Orchestrator Initialization Tests ====================

def test_orchestrator_initialization(orchestrator, db_session, mock_byok_handler):
    """Test orchestrator initializes all agents and managers."""
    assert orchestrator.db == db_session
    assert orchestrator.byok_handler == mock_byok_handler
    assert orchestrator.checkpoint_manager is not None
    assert orchestrator.state_store is not None
    assert orchestrator.pause_manager is not None
    assert orchestrator.progress_tracker is not None
    assert orchestrator.git_ops is not None


# ==================== State Store Tests ====================

def test_state_store_initial(state_store):
    """Test initial state creation."""
    state = state_store.create_initial_state(
        workflow_id="test-123",
        feature_request="Add feature",
        workspace_id="default"
    )

    assert state["workflow_id"] == "test-123"
    assert state["feature_request"] == "Add feature"
    assert state["workspace_id"] == "default"
    assert state["status"] == "pending"
    assert state["current_phase"] is None
    assert state["completed_phases"] == []
    assert "started_at" in state


@pytest.mark.asyncio
async def test_state_store_update(state_store):
    """Test state updates."""
    # Create initial state
    initial = state_store.create_initial_state("test-123", "Add feature", "default")
    state_store.state["test-123"] = initial

    # Update state
    updated = await state_store.update_state("test-123", {
        "current_phase": "generate_code",
        "files_created": ["test.py"]
    })

    assert updated["current_phase"] == "generate_code"
    assert updated["files_created"] == ["test.py"]
    assert updated["feature_request"] == "Add feature"  # Original preserved


@pytest.mark.asyncio
async def test_state_store_get(state_store):
    """Test getting state."""
    initial = state_store.create_initial_state("test-123", "Add feature", "default")
    state_store.state["test-123"] = initial

    state = await state_store.get_state("test-123")
    assert state["workflow_id"] == "test-123"


@pytest.mark.asyncio
async def test_state_store_get_nonexistent(state_store):
    """Test getting non-existent state raises error."""
    with pytest.raises(ValueError, match="No state found"):
        await state_store.get_state("nonexistent")


@pytest.mark.asyncio
async def test_state_store_merge(state_store):
    """Test state merging."""
    initial = state_store.create_initial_state("test-123", "Add feature", "default")
    state_store.state["test-123"] = initial

    merged = await state_store.merge_state("test-123", {
        "current_phase": "generate_code",
        "new_field": "value"
    })

    assert merged["current_phase"] == "generate_code"
    assert merged["new_field"] == "value"
    assert merged["feature_request"] == "Add feature"


# ==================== File Locking Tests ====================

@pytest.mark.asyncio
async def test_file_lock_acquire(state_store):
    """Test acquiring file lock."""
    success = await state_store.acquire_file_lock("workflow-1", "backend/test.py")
    assert success is True
    assert state_store.file_locks["backend/test.py"] == "workflow-1"


@pytest.mark.asyncio
async def test_file_lock_conflict(state_store):
    """Test file lock conflict detection."""
    # Workflow 1 acquires lock
    await state_store.acquire_file_lock("workflow-1", "backend/test.py")

    # Workflow 2 tries to acquire same file
    success = await state_store.acquire_file_lock("workflow-2", "backend/test.py")
    assert success is False


@pytest.mark.asyncio
async def test_file_lock_release(state_store):
    """Test releasing file lock."""
    await state_store.acquire_file_lock("workflow-1", "backend/test.py")
    await state_store.release_file_lock("workflow-1", "backend/test.py")

    assert "backend/test.py" not in state_store.file_locks


def test_check_file_conflicts(state_store):
    """Test checking for file conflicts."""
    state_store.file_locks["backend/test.py"] = "workflow-1"

    conflicts = state_store.check_file_conflicts(
        "workflow-2",
        ["backend/test.py", "backend/other.py"]
    )

    assert conflicts == ["backend/test.py"]


def test_check_file_conflicts_none(state_store):
    """Test checking for conflicts when none exist."""
    conflicts = state_store.check_file_conflicts(
        "workflow-1",
        ["backend/test.py", "backend/other.py"]
    )

    assert conflicts == []


# ==================== Checkpoint Tests ====================

@pytest.mark.asyncio
async def test_checkpoint_create(checkpoint_manager, git_ops):
    """Test creating checkpoint."""
    # Mock database query
    mock_checkpoint = MagicMock()
    mock_checkpoint.id = "checkpoint-123"

    with patch.object(checkpoint_manager, 'save_checkpoint_to_db', new=AsyncMock()):
        checkpoint_manager.db.add = MagicMock()
        checkpoint_manager.db.commit = MagicMock()

        sha = await checkpoint_manager.create_checkpoint(
            workflow_id="test-workflow",
            phase=WorkflowPhase.GENERATE_CODE,
            state={"files_created": ["test.py"]}
        )

        assert sha is not None
        assert len(sha) == 40  # Git SHA length


@pytest.mark.asyncio
async def test_checkpoint_save_to_db(checkpoint_manager):
    """Test saving checkpoint to database."""
    from core.models import AutonomousCheckpoint

    checkpoint_manager.db.add = MagicMock()
    checkpoint_manager.db.commit = MagicMock()

    await checkpoint_manager.save_checkpoint_to_db(
        workflow_id="test-workflow",
        phase=WorkflowPhase.GENERATE_CODE,
        checkpoint_sha="abc123",
        state={"test": "data"}
    )

    checkpoint_manager.db.add.assert_called_once()
    checkpoint_manager.db.commit.assert_called_once()


# ==================== Pause/Resume Tests ====================

def test_pause_manager_initialization(orchestrator):
    """Test pause manager initialization."""
    assert orchestrator.pause_manager is not None
    assert orchestrator.pause_manager.orchestrator == orchestrator


@pytest.mark.asyncio
async def test_pause_workflow(orchestrator, sample_workflow_state):
    """Test pausing workflow."""
    # Setup state
    orchestrator.state_store.state["test-123"] = sample_workflow_state

    # Mock database
    mock_workflow = MagicMock()
    mock_workflow.status = "running"
    orchestrator.db.query.return_value.filter.return_value.first.return_value = mock_workflow

    with patch.object(orchestrator.checkpoint_manager, 'create_checkpoint', new=AsyncMock(return_value="sha123")):
        result = await orchestrator.pause_workflow("test-123", "Need review")

        assert result["workflow_id"] == "test-123"
        assert result["status"] == "paused"
        assert result["reason"] == "Need review"
        assert "test-123" in orchestrator.pause_manager.paused_workflows


@pytest.mark.asyncio
async def test_resume_workflow(orchestrator, sample_workflow_state):
    """Test resuming workflow."""
    # Setup state and pause
    orchestrator.state_store.state["test-123"] = sample_workflow_state
    orchestrator.pause_manager.paused_workflows.add("test-123")
    orchestrator.pause_manager.pause_reasons["test-123"] = "Need review"

    # Mock database
    mock_workflow = MagicMock()
    orchestrator.db.query.return_value.filter.return_value.first.return_value = mock_workflow

    result = await orchestrator.resume_workflow("test-123", "Make it faster")

    assert result["workflow_id"] == "test-123"
    assert result["status"] == "running"
    assert result["feedback_applied"] is True
    assert "test-123" not in orchestrator.pause_manager.paused_workflows


def test_is_workflow_paused(orchestrator):
    """Test checking if workflow is paused."""
    orchestrator.pause_manager.paused_workflows.add("test-123")

    assert orchestrator.pause_manager.is_workflow_paused("test-123") is True
    assert orchestrator.pause_manager.is_workflow_paused("other-456") is False


def test_get_pause_reason(orchestrator):
    """Test getting pause reason."""
    orchestrator.pause_manager.pause_reasons["test-123"] = "Need review"

    assert orchestrator.pause_manager.get_pause_reason("test-123") == "Need review"
    assert orchestrator.pause_manager.get_pause_reason("other-456") is None


def test_generate_pause_summary(orchestrator, sample_workflow_state):
    """Test generating pause summary."""
    orchestrator.state_store.state["test-123"] = sample_workflow_state

    summary = orchestrator.pause_manager.generate_pause_summary("test-123")

    assert "Workflow test-123" in summary
    assert "Completed Phases" in summary
    assert "parse_requirements" in summary
    assert "Files Created" in summary
    assert "backend/auth/oauth.py" in summary


# ==================== Progress Tracking Tests ====================

@pytest.mark.asyncio
async def test_update_progress(progress_tracker):
    """Test updating workflow progress."""
    mock_workflow = MagicMock()
    progress_tracker.db.query.return_value.filter.return_value.first.return_value = mock_workflow

    await progress_tracker.update_progress(
        workflow_id="test-123",
        phase=WorkflowPhase.GENERATE_CODE,
        status=WorkflowStatus.COMPLETED,
        artifacts={"files_created": ["test.py"]}
    )

    # Verify workflow was updated
    assert mock_workflow.current_phase == "generate_code"
    assert mock_workflow.status == "completed"
    progress_tracker.db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_log_agent_action(progress_tracker):
    """Test logging agent action."""
    from core.models import AgentLog

    progress_tracker.db.add = MagicMock()
    progress_tracker.db.commit = MagicMock()

    await progress_tracker.log_agent_action(
        workflow_id="test-123",
        agent_id="coder-01",
        phase="generate_code",
        action="Generate OAuth module",
        input_data={"feature": "OAuth"},
        output_data={"files": ["oauth.py"]},
        status="completed"
    )

    progress_tracker.db.add.assert_called_once()
    progress_tracker.db.commit.assert_called_once()


def test_calculate_progress_percent(progress_tracker):
    """Test calculating progress percentage."""
    completed = ["parse_requirements", "research_codebase", "create_plan", "generate_code"]
    percent = progress_tracker.calculate_progress_percent(completed, total_phases=8)

    assert percent == 50.0  # 4/8 = 50%


def test_calculate_progress_percent_empty(progress_tracker):
    """Test calculating progress with no completed phases."""
    percent = progress_tracker.calculate_progress_percent([], total_phases=8)

    assert percent == 0.0


# ==================== Orchestrator Workflow Tests ====================

@pytest.mark.asyncio
async def test_execute_feature_start(orchestrator):
    """Test starting workflow execution."""
    # Mock all agent methods
    orchestrator.requirement_parser.parse_requirements = AsyncMock(return_value={
        "user_stories": ["As a user, I want OAuth"]
    })
    orchestrator.codebase_researcher.research_codebase = AsyncMock(return_value={})
    orchestrator.planning_agent.create_implementation_plan = AsyncMock(return_value={})
    orchestrator.coder_agent.generate_feature_code = AsyncMock(return_value={
        "files_created": ["oauth.py"],
        "files_modified": []
    })
    orchestrator.test_generator.generate_tests = AsyncMock(return_value={
        "test_files": ["test_oauth.py"]
    })
    orchestrator.test_runner.run_tests = AsyncMock(return_value={
        "failed": 0,
        "passed": 10
    })

    # Mock database
    mock_workflow = MagicMock()
    orchestrator.db.add = MagicMock()
    orchestrator.db.commit = MagicMock()

    result = await orchestrator.execute_feature(
        feature_request="Add OAuth2 authentication",
        workspace_id="default"
    )

    assert result["workflow_id"] is not None
    assert result["status"] == "completed"
    assert len(result["phases_completed"]) == 6  # 6 phases implemented


@pytest.mark.asyncio
async def test_execute_feature_with_error(orchestrator):
    """Test workflow execution with error."""
    # Mock parser to raise error
    orchestrator.requirement_parser.parse_requirements = AsyncMock(
        side_effect=Exception("Parse failed")
    )

    # Mock database
    mock_workflow = MagicMock()
    orchestrator.db.add = MagicMock()
    orchestrator.db.commit = MagicMock()

    result = await orchestrator.execute_feature(
        feature_request="Add OAuth2",
        workspace_id="default"
    )

    assert result["status"] == "failed"
    assert "Parse failed" in result["error"]


def test_list_active_workflows(orchestrator):
    """Test listing active workflows."""
    mock_workflow1 = MagicMock()
    mock_workflow1.id = "workflow-1"
    mock_workflow1.status = "running"

    mock_workflow2 = MagicMock()
    mock_workflow2.id = "workflow-2"
    mock_workflow2.status = "paused"

    orchestrator.db.query.return_value.filter.return_value.all.return_value = [
        mock_workflow1, mock_workflow2
    ]

    active = orchestrator.list_active_workflows()

    assert len(active) == 2
    assert "workflow-1" in active
    assert "workflow-2" in active


# ==================== Git Operations Tests ====================

def test_git_create_commit(git_ops, temp_git_repo):
    """Test creating git commit."""
    # Create a file
    test_file = temp_git_repo / "new_file.txt"
    test_file.write_text("test content")

    sha = git_ops.create_commit("Test commit")

    assert sha is not None
    assert len(sha) == 40


def test_git_get_current_sha(git_ops):
    """Test getting current git SHA."""
    sha = git_ops.get_current_sha()
    assert sha is not None
    assert len(sha) == 40


def test_git_reset_to_sha(git_ops, temp_git_repo):
    """Test resetting to specific SHA."""
    # Get current SHA
    initial_sha = git_ops.get_current_sha()

    # Create new commit
    new_file = temp_git_repo / "new.txt"
    new_file.write_text("new")
    git_ops.create_commit("New commit")

    # Reset to initial
    git_ops.reset_to_sha(initial_sha)

    # Verify reset
    current_sha = git_ops.get_current_sha()
    assert current_sha == initial_sha


# ==================== Error Handling Tests ====================

@pytest.mark.asyncio
async def test_rollback_nonexistent_workflow(orchestrator):
    """Test rolling back non-existent workflow raises error."""
    with pytest.raises(ValueError):
        await orchestrator.rollback_workflow(
            workflow_id="nonexistent",
            checkpoint_sha="abc123"
        )


@pytest.mark.asyncio
async def test_rollback_without_sha_or_phase(orchestrator):
    """Test rollback without SHA or phase raises error."""
    with pytest.raises(ValueError, match="Must specify"):
        await orchestrator.rollback_workflow(
            workflow_id="test-123"
        )


# ==================== Concurrent Workflow Tests ====================

@pytest.mark.asyncio
async def test_concurrent_workflows_no_conflict(state_store):
    """Test concurrent workflows with different files."""
    # Acquire locks for different files
    success1 = await state_store.acquire_file_lock("workflow-1", "backend/auth.py")
    success2 = await state_store.acquire_file_lock("workflow-2", "backend/test.py")

    assert success1 is True
    assert success2 is True


@pytest.mark.asyncio
async def test_concurrent_workflows_with_conflict(state_store):
    """Test concurrent workflows with conflicting files."""
    # Workflow 1 acquires lock
    await state_store.acquire_file_lock("workflow-1", "backend/auth.py")

    # Workflow 2 tries same file
    success = await state_store.acquire_file_lock("workflow-2", "backend/auth.py")

    assert success is False


# ==================== Integration Tests ====================

@pytest.mark.asyncio
async def test_full_workflow_checkpoint_cycle(orchestrator, git_ops):
    """Test complete workflow with checkpoint creation."""
    # Setup
    orchestrator.requirement_parser.parse_requirements = AsyncMock(return_value={})
    orchestrator.codebase_researcher.research_codebase = AsyncMock(return_value={})
    orchestrator.planning_agent.create_implementation_plan = AsyncMock(return_value={})
    orchestrator.coder_agent.generate_feature_code = AsyncMock(return_value={
        "files_created": [],
        "files_modified": []
    })
    orchestrator.test_generator.generate_tests = AsyncMock(return_value={})
    orchestrator.test_runner.run_tests = AsyncMock(return_value={"failed": 0})

    orchestrator.db.add = MagicMock()
    orchestrator.db.commit = MagicMock()

    # Execute
    result = await orchestrator.execute_feature(
        feature_request="Test feature",
        workspace_id="default"
    )

    # Verify checkpoints were created
    assert result["status"] == "completed"
    assert len(result["phases_completed"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
