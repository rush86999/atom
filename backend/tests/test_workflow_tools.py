
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from integrations.mcp_service import MCPService
from datetime import datetime
from advanced_workflow_orchestrator import WorkflowStatus, WorkflowContext

@pytest.mark.asyncio
async def test_workflow_tools():
    """Test list_workflows and trigger_workflow tools via MCPService"""
    service = MCPService()
    
    # Mock Orchestrator
    with patch("advanced_workflow_orchestrator.get_orchestrator") as MockFactory:
        mock_orchestrator = MockFactory.return_value
        
        # Setup mock workflows
        mock_wf = MagicMock()
        mock_wf.name = "Test Workflow"
        mock_wf.description = "A test workflow"
        mock_wf.inputs = [] # No inputs for simplicity
        
        mock_orchestrator.workflows = {"test_wf_1": mock_wf}
        
        # Setup mock execution result
        mock_context = WorkflowContext(
            workflow_id="exec_123",
            user_id="test_user",
            status=WorkflowStatus.COMPLETED,
            results={"outcome": "success"}
        )
        mock_orchestrator.execute_workflow = AsyncMock(return_value=mock_context)
        
        # 1. Test list_workflows
        tool_result = await service.execute_tool("local-tools", "list_workflows", {})
        assert len(tool_result) == 1
        assert tool_result[0]["id"] == "test_wf_1"
        assert tool_result[0]["name"] == "Test Workflow"
        
        # 2. Test trigger_workflow
        trigger_args = {
            "workflow_id": "test_wf_1",
            "input_data": {"foo": "bar"}
        }
        exec_result = await service.execute_tool("local-tools", "trigger_workflow", trigger_args)
        
        # Verify Orchestrator Call
        mock_orchestrator.execute_workflow.assert_called_once_with("test_wf_1", {"foo": "bar"})
        
        # Verify Output
        assert exec_result["status"] == "completed"
        assert exec_result["execution_id"] == "exec_123"
        assert exec_result["result"] == {"outcome": "success"}

@pytest.mark.asyncio
async def test_trigger_workflow_invalid_id():
    service = MCPService()
    # No ID provided
    result = await service.execute_tool("local-tools", "trigger_workflow", {})
    assert "error" in result
