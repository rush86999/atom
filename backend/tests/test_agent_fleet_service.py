"""
Test Suite for Agent Fleet Service — Multi-Agent Fleet Orchestration

Tests the Admiralty model for multi-agent fleet coordination:
- Fleet initialization and delegation chain creation
- Agent recruitment and task distribution
- Shared blackboard context management
- Link status tracking and updates
- Fleet lifecycle management (completion, cleanup)

Target Module: core.agent_fleet_service.py (168 lines)
Test Count: 18 tests
Quality Standards: 303-QUALITY-STANDARDS.md (no stub tests, imports from target module)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

# Import from target module (303-QUALITY-STANDARDS.md requirement)
from core.agent_fleet_service import AgentFleetService
from core.models import DelegationChain, ChainLink


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    db = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def fleet_service(db_session):
    """Create AgentFleetService instance."""
    return AgentFleetService(db_session)


@pytest.fixture
def mock_delegation_chain():
    """Create mock DelegationChain for testing."""
    chain = MagicMock()
    chain.id = "chain-001"
    chain.tenant_id = "tenant-uuid"
    chain.root_agent_id = "root-agent-001"
    chain.root_task = "Analyze sales data and create marketing strategy"
    chain.root_execution_id = "exec-001"
    chain.status = "active"
    chain.metadata_json = {}
    chain.started_at = datetime.now(timezone.utc)
    chain.completed_at = None
    chain.total_links = 0
    return chain


@pytest.fixture
def mock_chain_link():
    """Create mock ChainLink for testing."""
    link = MagicMock()
    link.id = "link-001"
    link.chain_id = "chain-001"
    link.parent_agent_id = "parent-agent-001"
    link.child_agent_id = "child-agent-001"
    link.task_description = "Subtask: Analyze Q1 sales data"
    link.context_json = {}
    link.status = "pending"
    link.link_order = 1
    link.started_at = datetime.now(timezone.utc)
    link.completed_at = None
    link.duration_ms = None
    link.result_json = None
    link.error_message = None
    return link


# ============================================================================
# Test Class 1: Fleet Initialization (5 tests)
# ============================================================================

class TestFleetInitialization:
    """Test fleet initialization and delegation chain creation."""

    def test_fleet_service_initialization(self, fleet_service, db_session):
        """Test AgentFleetService initializes with database session."""
        # Assert
        assert fleet_service.db == db_session
        assert hasattr(fleet_service, 'initialize_fleet')
        assert hasattr(fleet_service, 'recruit_member')
        assert hasattr(fleet_service, 'update_blackboard')

    def test_initialize_fleet_creates_delegation_chain(self, fleet_service, db_session):
        """Test initialize_fleet creates DelegationChain database entry."""
        # Arrange
        tenant_id = "tenant-uuid"
        root_agent_id = "root-agent-001"
        root_task = "Analyze sales data"
        root_execution_id = "exec-001"
        initial_metadata = {"priority": "high", "deadline": "2026-04-27"}

        # Act
        with patch('core.agent_fleet_service.DelegationChain') as mock_chain_class:
            mock_chain = MagicMock()
            mock_chain.id = "chain-001"
            mock_chain_class.return_value = mock_chain

            chain = fleet_service.initialize_fleet(
                tenant_id=tenant_id,
                root_agent_id=root_agent_id,
                root_task=root_task,
                root_execution_id=root_execution_id,
                initial_metadata=initial_metadata
            )

        # Assert
        assert chain is not None
        db_session.add.assert_called()
        db_session.commit.assert_called()
        db_session.refresh.assert_called()

    def test_initialize_fleet_sets_all_fields(self, fleet_service):
        """Test initialize_fleet sets all required fields correctly."""
        # Arrange
        tenant_id = "tenant-uuid"
        root_agent_id = "root-agent-001"
        root_task = "Complex task requiring fleet"

        # Act
        with patch('core.agent_fleet_service.DelegationChain') as mock_chain_class:
            mock_chain = MagicMock()
            mock_chain_class.return_value = mock_chain

            chain = fleet_service.initialize_fleet(
                tenant_id=tenant_id,
                root_agent_id=root_agent_id,
                root_task=root_task
            )

        # Assert - DelegationChain should be created with correct params
        mock_chain_class.assert_called_once()
        call_kwargs = mock_chain_class.call_args[1]
        assert call_kwargs['tenant_id'] == tenant_id
        assert call_kwargs['root_agent_id'] == root_agent_id
        assert call_kwargs['root_task'] == root_task
        assert call_kwargs['status'] == "active"

    def test_initialize_fleet_with_optional_params(self, fleet_service):
        """Test initialize_fleet handles optional parameters correctly."""
        # Arrange
        initial_metadata = {"workspace_id": "ws-001", "priority": "urgent"}

        # Act
        with patch('core.agent_fleet_service.DelegationChain') as mock_chain_class:
            mock_chain = MagicMock()
            mock_chain_class.return_value = mock_chain

            chain = fleet_service.initialize_fleet(
                tenant_id="tenant-uuid",
                root_agent_id="root-agent",
                root_task="Task",
                initial_metadata=initial_metadata
            )

        # Assert
        call_kwargs = mock_chain_class.call_args[1]
        assert call_kwargs['metadata_json'] == initial_metadata

    def test_initialize_fleet_defaults_metadata_to_empty_dict(self, fleet_service):
        """Test initialize_fleet defaults metadata_json to {} if not provided."""
        # Act
        with patch('core.agent_fleet_service.DelegationChain') as mock_chain_class:
            mock_chain = MagicMock()
            mock_chain_class.return_value = mock_chain

            chain = fleet_service.initialize_fleet(
                tenant_id="tenant-uuid",
                root_agent_id="root-agent",
                root_task="Task"
            )

        # Assert
        call_kwargs = mock_chain_class.call_args[1]
        assert call_kwargs['metadata_json'] == {}


# ============================================================================
# Test Class 2: Fleet Recruitment (5 tests)
# ============================================================================

class TestFleetRecruitment:
    """Test agent recruitment and task distribution to fleet members."""

    def test_recruit_member_creates_chain_link(self, fleet_service, db_session):
        """Test recruit_member creates ChainLink database entry."""
        # Arrange
        chain_id = "chain-001"
        parent_agent_id = "parent-001"
        child_agent_id = "child-001"
        task_description = "Analyze Q1 sales data"

        # Act
        with patch('core.agent_fleet_service.ChainLink') as mock_link_class:
            mock_link = MagicMock()
            mock_link.id = "link-001"
            mock_link_class.return_value = mock_link

            # Mock chain query
            mock_chain = MagicMock()
            mock_chain.total_links = 0
            fleet_service.db.query().filter().first.return_value = mock_chain

            link = fleet_service.recruit_member(
                chain_id=chain_id,
                parent_agent_id=parent_agent_id,
                child_agent_id=child_agent_id,
                task_description=task_description
            )

        # Assert
        assert link is not None
        db_session.add.assert_called()
        db_session.commit.assert_called()
        db_session.refresh.assert_called()

    def test_recruit_member_increments_total_links(self, fleet_service):
        """Test recruit_member increments total_links in chain."""
        # Arrange
        mock_chain = MagicMock()
        mock_chain.total_links = 5

        # Act
        with patch('core.agent_fleet_service.ChainLink') as mock_link_class:
            mock_link = MagicMock()
            mock_link_class.return_value = mock_link

            fleet_service.db.query().filter().first.return_value = mock_chain

            link = fleet_service.recruit_member(
                chain_id="chain-001",
                parent_agent_id="parent-001",
                child_agent_id="child-001",
                task_description="Task"
            )

        # Assert - total_links should be incremented
        assert mock_chain.total_links == 6
        fleet_service.db.commit.assert_called()

    def test_recruit_member_merges_optimization_metadata(self, fleet_service):
        """Test recruit_member merges optimization_metadata into context."""
        # Arrange
        context_json = {"workspace_id": "ws-001"}
        optimization_metadata = {"strategy": "parallel", "timeout": 300}

        # Act
        with patch('core.agent_fleet_service.ChainLink') as mock_link_class:
            mock_link = MagicMock()
            mock_link_class.return_value = mock_link

            fleet_service.db.query().filter().first.return_value = MagicMock(total_links=0)

            link = fleet_service.recruit_member(
                chain_id="chain-001",
                parent_agent_id="parent-001",
                child_agent_id="child-001",
                task_description="Task",
                context_json=context_json,
                optimization_metadata=optimization_metadata
            )

        # Assert
        call_kwargs = mock_link_class.call_args[1]
        assert call_kwargs['context_json']['workspace_id'] == "ws-001"
        assert call_kwargs['context_json']['optimization']['strategy'] == "parallel"

    def test_recruit_member_sets_link_order(self, fleet_service):
        """Test recruit_member sets link_order parameter correctly."""
        # Arrange
        link_order = 3

        # Act
        with patch('core.agent_fleet_service.ChainLink') as mock_link_class:
            mock_link = MagicMock()
            mock_link_class.return_value = mock_link

            fleet_service.db.query().filter().first.return_value = MagicMock(total_links=0)

            link = fleet_service.recruit_member(
                chain_id="chain-001",
                parent_agent_id="parent-001",
                child_agent_id="child-001",
                task_description="Task",
                link_order=link_order
            )

        # Assert
        call_kwargs = mock_link_class.call_args[1]
        assert call_kwargs['link_order'] == link_order

    def test_recruit_member_defaults_to_pending_status(self, fleet_service):
        """Test recruit_member sets status to 'pending' by default."""
        # Act
        with patch('core.agent_fleet_service.ChainLink') as mock_link_class:
            mock_link = MagicMock()
            mock_link_class.return_value = mock_link

            fleet_service.db.query().filter().first.return_value = MagicMock(total_links=0)

            link = fleet_service.recruit_member(
                chain_id="chain-001",
                parent_agent_id="parent-001",
                child_agent_id="child-001",
                task_description="Task"
            )

        # Assert
        call_kwargs = mock_link_class.call_args[1]
        assert call_kwargs['status'] == "pending"


# ============================================================================
# Test Class 3: Blackboard Management (4 tests)
# ============================================================================

class TestBlackboardManagement:
    """Test shared fleet context (blackboard) management."""

    def test_update_blackboard_merges_updates(self, fleet_service):
        """Test update_blackboard merges updates into existing metadata."""
        # Arrange
        chain_id = "chain-001"
        current_metadata = {"step1": "completed", "step2": "in_progress"}
        updates = {"step2": "completed", "step3": "started"}

        mock_chain = MagicMock()
        mock_chain.metadata_json = current_metadata
        fleet_service.db.query().filter().first.return_value = mock_chain

        # Act
        fleet_service.update_blackboard(chain_id, updates)

        # Assert
        assert mock_chain.metadata_json["step1"] == "completed"
        assert mock_chain.metadata_json["step2"] == "completed"  # Updated
        assert mock_chain.metadata_json["step3"] == "started"  # Added
        fleet_service.db.commit.assert_called()

    def test_update_blackboard_handles_missing_chain(self, fleet_service):
        """Test update_blackboard logs error when chain not found."""
        # Arrange
        fleet_service.db.query().filter().first.return_value = None

        # Act
        fleet_service.update_blackboard("nonexistent-chain", {"key": "value"})

        # Assert - should not commit, should log error
        fleet_service.db.commit.assert_not_called()

    def test_get_blackboard_returns_metadata(self, fleet_service):
        """Test get_blackboard returns chain metadata."""
        # Arrange
        chain_id = "chain-001"
        metadata = {"agent1_result": "success", "agent2_result": "pending"}

        mock_chain = MagicMock()
        mock_chain.metadata_json = metadata
        fleet_service.db.query().filter().first.return_value = mock_chain

        # Act
        result = fleet_service.get_blackboard(chain_id)

        # Assert
        assert result == metadata
        assert result["agent1_result"] == "success"

    def test_get_blackboard_returns_empty_dict_for_missing_chain(self, fleet_service):
        """Test get_blackboard returns empty dict when chain not found."""
        # Arrange
        fleet_service.db.query().filter().first.return_value = None

        # Act
        result = fleet_service.get_blackboard("nonexistent-chain")

        # Assert
        assert result == {}


# ============================================================================
# Test Class 4: Link Status Updates (4 tests)
# ============================================================================

class TestLinkStatusUpdates:
    """Test link status tracking and result updates."""

    def test_update_link_status_to_completed(self, fleet_service, mock_chain_link):
        """Test update_link_status updates status to completed."""
        # Arrange
        link_id = "link-001"
        result = {"output": "Task completed successfully", "metrics": {"accuracy": 0.95}}

        fleet_service.db.query().filter().first.return_value = mock_chain_link

        # Act
        fleet_service.update_link_status(link_id, "completed", result=result)

        # Assert
        assert mock_chain_link.status == "completed"
        assert mock_chain_link.result_json == result
        assert mock_chain_link.completed_at is not None
        fleet_service.db.commit.assert_called()

    def test_update_link_status_to_failed_with_error(self, fleet_service, mock_chain_link):
        """Test update_link_status updates status to failed with error message."""
        # Arrange
        link_id = "link-001"
        error = "Agent execution timeout after 300 seconds"

        fleet_service.db.query().filter().first.return_value = mock_chain_link

        # Act
        fleet_service.update_link_status(link_id, "failed", error=error)

        # Assert
        assert mock_chain_link.status == "failed"
        assert mock_chain_link.error_message == error
        assert mock_chain_link.completed_at is not None
        fleet_service.db.commit.assert_called()

    def test_update_link_status_calculates_duration(self, fleet_service, mock_chain_link):
        """Test update_link_status calculates duration_ms for completed/failed links."""
        # Arrange
        link_id = "link-001"
        mock_chain_link.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        fleet_service.db.query().filter().first.return_value = mock_chain_link

        # Act
        fleet_service.update_link_status(link_id, "completed")

        # Assert - duration should be approximately 10000ms (10 seconds)
        assert mock_chain_link.duration_ms is not None
        assert mock_chain_link.duration_ms >= 9000  # Allow some timing variance
        assert mock_chain_link.duration_ms <= 11000

    def test_update_link_status_handles_missing_link(self, fleet_service):
        """Test update_link_status logs error when link not found."""
        # Arrange
        fleet_service.db.query().filter().first.return_value = None

        # Act - should not raise exception
        fleet_service.update_link_status("nonexistent-link", "completed")

        # Assert
        fleet_service.db.commit.assert_not_called()


# ============================================================================
# Total Test Count: 18 tests
# ============================================================================
# Test Class 1: Fleet Initialization - 5 tests
# Test Class 2: Fleet Recruitment - 5 tests
# Test Class 3: Blackboard Management - 4 tests
# Test Class 4: Link Status Updates - 4 tests
# ============================================================================
