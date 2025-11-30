
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Create mocks for dependencies
mock_workflow_engine_module = MagicMock()
mock_state_manager_module = MagicMock()
mock_automation_engine_module = MagicMock()
mock_scheduler_module = MagicMock()

# Mock the modules in sys.modules
sys.modules["core.workflow_engine"] = mock_workflow_engine_module
sys.modules["core.execution_state_manager"] = mock_state_manager_module
sys.modules["ai.automation_engine"] = mock_automation_engine_module
sys.modules["ai.workflow_scheduler"] = mock_scheduler_module

# Import endpoints AFTER mocking
from core.workflow_endpoints import router

app = FastAPI()
app.include_router(router)

client = TestClient(app)

def test_resume_workflow():
    print("Testing Resume Workflow Endpoint...")
    
    execution_id = "test-exec-123"
    workflow_id = "test-workflow-456"
    
    # Configure State Manager Mock
    mock_state_manager = MagicMock()
    mock_state_manager.get_execution_state.return_value = asyncio.Future()
    mock_state_manager.get_execution_state.return_value.set_result({
        "execution_id": execution_id,
        "workflow_id": workflow_id,
        "status": "paused"
    })
    mock_state_manager_module.get_state_manager.return_value = mock_state_manager
    
    # Configure Workflow Engine Mock
    mock_engine = MagicMock()
    mock_engine.resume_workflow.return_value = asyncio.Future()
    mock_engine.resume_workflow.return_value.set_result(True)
    mock_workflow_engine_module.get_workflow_engine.return_value = mock_engine
    
    # Mock load_workflows to return our workflow
    with patch("core.workflow_endpoints.load_workflows") as mock_load:
        mock_load.return_value = [{"id": workflow_id, "name": "Test Workflow"}]
        
        response = client.post(
            f"/workflows/{execution_id}/resume",
            json={"input": "value"}
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.json()}")
        
        if response.status_code == 200 and response.json()["status"] == "resumed":
            print("✅ Resume endpoint verified successfully!")
        else:
            print("❌ Resume endpoint verification failed.")
            sys.exit(1)

if __name__ == "__main__":
    test_resume_workflow()
