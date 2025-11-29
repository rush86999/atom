"""
Test script for Advanced Execution Engine

Verifies:
- Workflow pause on missing input
- State persistence
- Resume capability
- WebSocket notifications (simulated)
"""

import asyncio
import sys
import json
import os
from pathlib import Path
from typing import Dict, Any

# Add backend to path
backend_path = str(Path(__file__).parent / "backend")
sys.path.insert(0, backend_path)

from core.workflow_engine import get_workflow_engine, WorkflowEngine
from core.execution_state_manager import get_state_manager
from core.websockets import get_connection_manager

# Mock WebSocket for testing
class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        
    async def send_json(self, message: Dict[str, Any]):
        self.sent_messages.append(message)
        print(f"📡 WebSocket Message: {message['type']} - {message.get('status')}")

async def test_pause_resume_logic():
    print("\n=== Testing Pause/Resume Logic ===")
    
    engine = get_workflow_engine()
    state_manager = get_state_manager()
    ws_manager = get_connection_manager()
    
    # Mock WebSocket connection
    mock_ws = MockWebSocket()
    ws_manager.active_connections["test_user"] = [mock_ws]
    
    # Define a workflow with missing input dependency
    workflow = {
        "id": "test_workflow_pause",
        "created_by": "test_user",
        "steps": [
            {
                "id": "step1",
                "service": "test_service",
                "action": "action1",
                "sequence_order": 1,
                "parameters": {
                    "param1": "value1"
                }
            },
            {
                "id": "step2",
                "service": "test_service",
                "action": "action2",
                "sequence_order": 2,
                "parameters": {
                    # This variable is missing from input
                    "required_param": "${input.missing_key}"
                },
                "depends_on": ["step1"]
            }
        ]
    }
    
    print("1. Starting workflow execution...")
    execution_id = await engine.start_workflow(workflow, input_data={"existing_key": "exists"})
    print(f"   Execution ID: {execution_id}")
    
    # Wait for execution to process
    await asyncio.sleep(2)
    
    # Check state
    state = await state_manager.get_execution_state(execution_id)
    print(f"   Status: {state['status']}")
    
    if state['status'] == "PAUSED":
        print("✅ Workflow correctly PAUSED due to missing input")
        print(f"   Error: {state.get('error')}")
    else:
        print(f"❌ Workflow failed to pause. Status: {state['status']}")
        return False
        
    # Check WebSocket messages
    paused_msg = next((m for m in mock_ws.sent_messages if m['status'] == 'PAUSED'), None)
    if paused_msg:
        print("✅ WebSocket notification received for PAUSED state")
        print(f"   Details: {paused_msg.get('details')}")
    else:
        print("❌ No WebSocket notification for PAUSED state")
        return False

    print("\n2. Resuming workflow with missing input...")
    # Provide the missing input
    success = await engine.resume_workflow(
        execution_id, 
        workflow, 
        new_inputs={"missing_key": "provided_value"}
    )
    
    if success:
        print("✅ Resume command accepted")
    else:
        print("❌ Resume command failed")
        return False
        
    # Wait for execution to complete
    await asyncio.sleep(2)
    
    # Check final state
    state = await state_manager.get_execution_state(execution_id)
    print(f"   Final Status: {state['status']}")
    
    if state['status'] == "COMPLETED":
        print("✅ Workflow COMPLETED successfully after resume")
        
        # Verify step 2 output
        step2_output = await state_manager.get_step_output(execution_id, "step2")
        if step2_output and step2_output.get("params", {}).get("required_param") == "provided_value":
            print("✅ Step 2 received correct resumed input")
            return True
        else:
            print(f"❌ Step 2 output incorrect: {step2_output}")
            return False
    else:
        print(f"❌ Workflow failed to complete. Status: {state['status']}")
        return False

async def main():
    print("="*50)
    print("ADVANCED EXECUTION ENGINE VERIFICATION")
    print("="*50)
    
    success = await test_pause_resume_logic()
    
    print("\n" + "="*50)
    if success:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
