
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from api.agent_routes import execute_agent_task
from core.models import AgentRegistry

@pytest.fixture
def mock_db_session():
    with patch("api.agent_routes.SessionLocal") as MockSession:
        yield MockSession.return_value

@pytest.mark.asyncio
async def test_legacy_agent_uses_react_loop(mock_db_session):
    """
    Test that a legacy agent ID (e.g. competitive_intel) is executed via GenericAgent ReAct loop.
    """
    # Setup Data
    legacy_agent = AgentRegistry(
        id="competitive_intel", 
        name="Competitor Bot", 
        class_name="CompetitiveIntelligenceAgent", # Legacy class name
        module_path="operations.automations",
        configuration={} # No tools configured
    )
    
    # Mock DB Query
    mock_db_session.query.return_value.filter.return_value.first.return_value = legacy_agent
    
    # Mock Dependencies
    with patch("core.generic_agent.GenericAgent") as MockGenericAgent, \
         patch("api.agent_routes.notification_manager") as mock_nm, \
         patch("api.agent_routes.WorldModelService") as MockWM:
         
        # Setup Notification Manager
        mock_nm.broadcast = AsyncMock()
        mock_nm.send_urgent_notification = AsyncMock()

        # Setup GenericAgent Mock
        mock_runner = MagicMock()
        mock_runner.execute = AsyncMock(return_value={"output": "Migration Success"})
        MockGenericAgent.return_value = mock_runner
        
        # Setup WorldModel Mock
        mock_wm_instance = MockWM.return_value
        mock_wm_instance.record_experience = AsyncMock()
        mock_wm_instance.recall_experiences = AsyncMock(return_value=[])
        
        # Execute
        params = {"product": "TestWidget"}
        await execute_agent_task("competitive_intel", params)
        
        # Verify GenericAgent was instantiated
        assert MockGenericAgent.called
        
        # Verify Configuration Injection
        # We can check the args passed to GenericAgent constructor
        args, _ = MockGenericAgent.call_args
        agent_passed = args[0]
        assert "track_competitor_pricing" in agent_passed.configuration["tools"]
        assert "Competitive Intelligence Agent" in agent_passed.configuration["system_prompt"]
        
        # Verify Execute called
        mock_runner.execute.assert_called_once()
        call_args = mock_runner.execute.call_args
        assert "Track pricing for TestWidget" in call_args[0][0] # Input prompt construction test

@pytest.mark.asyncio
async def test_payroll_agent_defaults(mock_db_session):
    """Test Payroll agent default prompt construction"""
    legacy_agent = AgentRegistry(
        id="payroll_guardian", 
        name="Payroll Bot", 
        class_name="PayrollReconciliationWorkflow",
        configuration={}
    )
    mock_db_session.query.return_value.filter.return_value.first.return_value = legacy_agent
    
    with patch("core.generic_agent.GenericAgent") as MockGenericAgent, \
         patch("api.agent_routes.notification_manager") as mock_nm, \
         patch("api.agent_routes.WorldModelService") as MockWM:
         
        mock_nm.broadcast = AsyncMock()
        mock_nm.send_urgent_notification = AsyncMock()
        
        MockWM.return_value.recall_experiences = AsyncMock(return_value=[])
         
        mock_runner = MagicMock()
        mock_runner.execute = AsyncMock(return_value={"output": "Done"})
        MockGenericAgent.return_value = mock_runner
        
        await execute_agent_task("payroll_guardian", {})
        
        call_args = mock_runner.execute.call_args
        assert "Reconcile payroll for period current" in call_args[0][0]
