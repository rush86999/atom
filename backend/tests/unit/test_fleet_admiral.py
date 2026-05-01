"""
Fleet Admiral Tests

Comprehensive tests for FleetAdmiral covering fleet recruitment, blackboard coordination,
multi-agent execution, and agent teardown.

Coverage: 80%+ for core/fleet_admiral.py
Lines: 250+, Tests: 15-20
"""

import pytest
import uuid
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.fleet_admiral import FleetAdmiral, TaskAnalysis
from core.models import DelegationChain, ChainLink


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def fleet_admiral(postgresql_db: Session):
    """Create FleetAdmiral instance for testing."""
    if postgresql_db is None:
        pytest.skip("PostgreSQL unavailable")
    
    from core.llm_service import LLMService
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.generate_structured_response = AsyncMock(return_value={
        "complexity": "medium",
        "required_capabilities": ["analysis", "reporting"],
        "estimated_duration": "minutes",
        "specialist_count": 2,
        "reasoning": "Task requires analysis and reporting"
    })
    
    return FleetAdmiral(db=postgresql_db, llm=mock_llm)


@pytest.fixture
def mock_specialist_agents():
    """Mock specialist agents for fleet testing."""
    agents = []
    for i in range(3):
        agent = MagicMock()
        agent.id = f"specialist_{i}"
        agent.name = f"Specialist {i}"
        agent.capabilities = [f"capability_{i}"]
        agents.append(agent)
    return agents


# ============================================================================
# Test Fleet Recruitment
# ============================================================================

class TestFleetRecruitment:
    """Tests for agent recruitment logic."""

    @pytest.mark.asyncio
    async def test_analyze_task_complexity(self, fleet_admiral: FleetAdmiral):
        """Test task analysis for complexity and requirements."""
        task_description = "Analyze sales data and create marketing strategy"
        
        analysis = await fleet_admiral.analyze_task(task_description)
        
        assert analysis is not None
        assert analysis.complexity in ["low", "medium", "high"]
        assert isinstance(analysis.required_capabilities, list)
        assert analysis.specialist_count >= 1

    @pytest.mark.asyncio
    async def test_recruit_fleet_for_task(self, fleet_admiral: FleetAdmiral):
        """Test recruiting specialists for a task."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.initialize_delegation_chain = MagicMock(return_value="delegation_123")
            mock_fleet.recruit_member = AsyncMock(return_value="agent_123")
            mock_fleet_service.return_value = mock_fleet
            
            result = await fleet_admiral.recruit_fleet(
                task_description="Analyze financial data",
                required_capabilities=["analysis", "reporting"]
            )
            
            assert result is not None
            assert "delegation_chain_id" in result or "success" in result

    @pytest.mark.asyncio
    async def test_recruit_with_no_capabilities(self, fleet_admiral: FleetAdmiral):
        """Test recruitment with no required capabilities."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.initialize_delegation_chain = MagicMock(return_value="delegation_123")
            mock_fleet_service.return_value = mock_fleet
            
            result = await fleet_admiral.recruit_fleet(
                task_description="Simple task",
                required_capabilities=[]
            )
            
            # Should handle gracefully
            assert result is not None

    @pytest.mark.asyncio
    async def test_specialist_matching(self, fleet_admiral: FleetAdmiral, mock_specialist_agents):
        """Test intelligent specialist matching based on capabilities."""
        with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit:
            mock_recruit_service = MagicMock()
            mock_recruit_service.match_specialists = AsyncMock(
                return_value=mock_specialist_agents[:2]
            )
            mock_recruit.return_value = mock_recruit_service
            
            fleet_admiral._initialize_recruitment_intelligence()
            
            specialists = await fleet_admiral.recruitment_intelligence.match_specialists(
                capabilities=["analysis", "reporting"],
                count=2
            )
            
            assert len(specialists) == 2


# ============================================================================
# Test Blackboard Coordination
# ============================================================================

class TestBlackboardCoordination:
    """Tests for shared blackboard state synchronization."""

    @pytest.mark.asyncio
    async def test_blackboard_initialization(self, fleet_admiral: FleetAdmiral):
        """Test blackboard is initialized for fleet."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.initialize_delegation_chain = MagicMock(
                return_value="delegation_chain_123"
            )
            mock_fleet.get_blackboard = MagicMock(return_value={})
            mock_fleet_service.return_value = mock_fleet
            
            chain_id = await fleet_admiral.initialize_blackboard(
                task_description="Test task"
            )
            
            assert chain_id == "delegation_chain_123"

    @pytest.mark.asyncio
    async def test_blackboard_state_update(self, fleet_admiral: FleetAdmiral):
        """Test updating blackboard state."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.update_blackboard = AsyncMock(return_value=True)
            mock_fleet_service.return_value = mock_fleet
            
            success = await fleet_admiral.update_blackboard(
                delegation_chain_id="chain_123",
                agent_id="agent_1",
                updates={"result": "partial_result"}
            )
            
            assert success is True

    @pytest.mark.asyncio
    async def test_blackboard_state_retrieval(self, fleet_admiral: FleetAdmiral):
        """Test retrieving blackboard state."""
        mock_state = {
            "task": "Test task",
            "agents": ["agent_1", "agent_2"],
            "results": {"agent_1": "done"}
        }
        
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.get_blackboard = MagicMock(return_value=mock_state)
            mock_fleet_service.return_value = mock_fleet
            
            state = await fleet_admiral.get_blackboard_state("chain_123")
            
            assert state is not None
            assert "task" in state
            assert "agents" in state


# ============================================================================
# Test Multi-Agent Execution
# ============================================================================

class TestMultiAgentExecution:
    """Tests for parallel agent task distribution."""

    @pytest.mark.asyncio
    async def test_coordinate_task_execution(self, fleet_admiral: FleetAdmiral):
        """Test coordinating task across multiple agents."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.initialize_delegation_chain = MagicMock(
                return_value="delegation_123"
            )
            mock_fleet.execute_chain = AsyncMock(
                return_value={
                    "success": True,
                    "final_result": "Task completed successfully"
                }
            )
            mock_fleet_service.return_value = mock_fleet
            
            result = await fleet_admiral.coordinate_task(
                task_description="Analyze data and create report",
                user_id="test_user"
            )
            
            assert result["success"] is True
            assert "final_result" in result

    @pytest.mark.asyncio
    async def test_distribute_subtasks(self, fleet_admiral: FleetAdmiral):
        """Test distributing subtasks among specialists."""
        subtasks = [
            {"agent": "agent_1", "task": "subtask_1"},
            {"agent": "agent_2", "task": "subtask_2"}
        ]
        
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.distribute_tasks = AsyncMock(return_value=True)
            mock_fleet_service.return_value = mock_fleet
            
            success = await fleet_admiral.distribute_subtasks(
                delegation_chain_id="chain_123",
                subtasks=subtasks
            )
            
            assert success is True

    @pytest.mark.asyncio
    async def test_aggregate_results(self, fleet_admiral: FleetAdmiral):
        """Test aggregating results from multiple agents."""
        mock_results = {
            "agent_1": {"status": "completed", "result": "result_1"},
            "agent_2": {"status": "completed", "result": "result_2"}
        }
        
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.aggregate_results = MagicMock(
                return_value=mock_results
            )
            mock_fleet_service.return_value = mock_fleet
            
            aggregated = await fleet_admiral.aggregate_results("chain_123")
            
            assert "agent_1" in aggregated
            assert "agent_2" in aggregated


# ============================================================================
# Test Agent Teardown
# ============================================================================

class TestAgentTeardown:
    """Tests for cleanup after task completion."""

    @pytest.mark.asyncio
    async def test_fleet_teardown(self, fleet_admiral: FleetAdmiral):
        """Test proper fleet teardown after completion."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.close_delegation_chain = AsyncMock(return_value=True)
            mock_fleet_service.return_value = mock_fleet
            
            success = await fleet_admiral.teardown_fleet(
                delegation_chain_id="chain_123"
            )
            
            assert success is True

    @pytest.mark.asyncio
    async def test_cleanup_temporary_resources(self, fleet_admiral: FleetAdmiral):
        """Test cleanup of temporary resources."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.cleanup_resources = AsyncMock(return_value=True)
            mock_fleet_service.return_value = mock_fleet
            
            success = await fleet_admiral.cleanup_resources("chain_123")
            
            assert success is True


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_task_analysis_failure(self, fleet_admiral: FleetAdmiral):
        """Test handling of task analysis failure."""
        fleet_admiral.llm.generate_structured_response = AsyncMock(
            side_effect=Exception("LLM failed")
        )
        
        # Should fallback to default analysis
        analysis = await fleet_admiral.analyze_task("Test task")
        
        assert analysis is not None

    @pytest.mark.asyncio
    async def test_recruitment_failure(self, fleet_admiral: FleetAdmiral):
        """Test handling of recruitment failure."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.initialize_delegation_chain = MagicMock(
                side_effect=Exception("Recruitment failed")
            )
            mock_fleet_service.return_value = mock_fleet
            
            result = await fleet_admiral.recruit_fleet(
                task_description="Test task",
                required_capabilities=["test"]
            )
            
            # Should handle error gracefully
            assert result is not None

    @pytest.mark.asyncio
    async def test_agent_failure_during_execution(self, fleet_admiral: FleetAdmiral):
        """Test handling of agent failure during task execution."""
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.execute_chain = AsyncMock(
                side_effect=Exception("Agent failed")
            )
            mock_fleet_service.return_value = mock_fleet
            
            result = await fleet_admiral.coordinate_task(
                task_description="Test task",
                user_id="test_user"
            )
            
            # Should handle error
            assert result is not None


# ============================================================================
# Test PostgreSQL Integration
# ============================================================================

class TestPostgreSQLIntegration:
    """Tests for PostgreSQL database integration."""

    def test_delegation_chain_persistence(self, fleet_admiral: FleetAdmiral, postgresql_db: Session):
        """Test that delegation chains are persisted."""
        chain_id = str(uuid.uuid4())
        chain = DelegationChain(
            id=chain_id,
            task_description="Test task",
            user_id="test_user",
            status="in_progress",
            created_at=datetime.now(timezone.utc)
        )
        postgresql_db.add(chain)
        postgresql_db.commit()
        
        # Verify chain exists
        retrieved = postgresql_db.query(DelegationChain).filter(
            DelegationChain.id == chain_id
        ).first()
        
        assert retrieved is not None
        assert retrieved.task_description == "Test task"

    def test_chain_link_persistence(self, fleet_admiral: FleetAdmiral, postgresql_db: Session):
        """Test that chain links are persisted."""
        chain_id = str(uuid.uuid4())
        link = ChainLink(
            id=str(uuid.uuid4()),
            delegation_chain_id=chain_id,
            agent_id="agent_123",
            task_description="Subtask",
            status="completed",
            order_index=1
        )
        postgresql_db.add(link)
        postgresql_db.commit()
        
        # Verify link exists
        retrieved = postgresql_db.query(ChainLink).filter(
            ChainLink.delegation_chain_id == chain_id
        ).first()
        
        assert retrieved is not None
        assert retrieved.agent_id == "agent_123"


# ============================================================================
# Test Performance
# ============================================================================

class TestPerformance:
    """Performance benchmark tests."""

    @pytest.mark.asyncio
    async def test_task_analysis_performance(self, fleet_admiral: FleetAdmiral):
        """Test task analysis meets performance target."""
        import time
        
        start_time = time.time()
        await fleet_admiral.analyze_task("Analyze sales data")
        elapsed = time.time() - start_time
        
        # Target: <500ms for task analysis
        assert elapsed < 0.5, f"Analysis took {elapsed:.3f}s, target <0.5s"

    @pytest.mark.asyncio
    async def test_recruitment_performance(self, fleet_admiral: FleetAdmiral):
        """Test fleet recruitment meets performance target."""
        import time
        
        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service:
            mock_fleet = MagicMock()
            mock_fleet.initialize_delegation_chain = MagicMock(
                return_value="chain_123"
            )
            mock_fleet_service.return_value = mock_fleet
            
            start_time = time.time()
            await fleet_admiral.recruit_fleet(
                task_description="Test task",
                required_capabilities=["test"]
            )
            elapsed = time.time() - start_time
            
            # Target: <1s for recruitment
            assert elapsed < 1.0, f"Recruitment took {elapsed:.3f}s, target <1.0s"
