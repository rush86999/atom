import os
import sys
import asyncio
import json
import logging
import uuid
from pathlib import Path
from fastapi.testclient import TestClient

# Set test database
os.environ["DATABASE_URL"] = "sqlite:///test_atom_data.db"

# Add backend to path
backend_path = str(Path(__file__).parent)
sys.path.insert(0, backend_path)

from main_api_app import app
from core.workflow_engine import get_workflow_engine
from core.execution_state_manager import get_state_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_websocket_and_resume():
    print("\n==================================================")
    print("WEBSOCKET & RESUME VERIFICATION (TestClient)")
    print("==================================================")

    client = TestClient(app)
    
    # 1. Create a workflow that requires input
    workflow_id = str(uuid.uuid4())
    workflow = {
        "id": workflow_id,
        "name": "WebSocket Test Workflow",
        "description": "Testing WebSocket notifications and resume",
        "version": "1.0.0",
        "nodes": [
            {
                "id": "step1",
                "type": "trigger",
                "title": "Start",
                "description": "Manual trigger",
                "position": {"x": 0, "y": 0},
                "config": {"action": "manual_trigger"},
                "connections": ["step2"]
            },
            {
                "id": "step2",
                "type": "action",
                "title": "Process Input",
                "description": "Process data",
                "position": {"x": 200, "y": 0},
                "config": {
                    "service": "test_service",
                    "action": "process_data",
                    "parameters": {
                        "required_param": "${input.user_input}"
                    }
                },
                "connections": []
            }
        ],
        "connections": [
            {
                "id": "c1",
                "source": "step1",
                "target": "step2"
            }
        ],
        "steps": [  # Adding steps explicitly as the engine might use them directly if passed
            {
                "id": "step1",
                "name": "Start",
                "type": "trigger",
                "action": "manual_trigger",
                "sequence_order": 1
            },
            {
                "id": "step2",
                "name": "Process Input",
                "type": "action",
                "action": "process_data",
                "parameters": {
                    "required_param": "${input.user_input}"
                },
                "sequence_order": 2
            }
        ],
        "triggers": ["manual"],
        "enabled": True,
        "created_by": "default"
    }
    
    # Create workflow
    response = client.post("/workflows", json=workflow)
    if response.status_code != 200:
        print(f"❌ Failed to create workflow: {response.text}")
        return False
    print("✅ Workflow created")

    # Connect to WebSocket
    print("Connecting to WebSocket...")
    with client.websocket_connect("/ws/default") as websocket:
        print("✅ WebSocket connected")
        
        # Start execution
        print("Starting execution...")
        response = client.post(f"/workflows/{workflow_id}/execute", json={})
        if response.status_code != 200:
            print(f"❌ Failed to start execution: {response.text}")
            return False
            
        execution_data = response.json()
        execution_id = execution_data['execution_id']
        status = execution_data.get('status')
        
        if status == 'failed':
            print(f"❌ Execution failed immediately: {execution_data.get('errors')}")
            return False
            
        print(f"✅ Execution started: {execution_id} (Status: {status})")
        
        # Listen for PAUSED event
        paused_event_received = False
        try:
            while True:
                data = websocket.receive_json()
                print(f"📡 Received: {data['type']} - {data.get('data', {}).get('status')}")
                
                if data['type'] == 'workflow_status_update':
                    status = data['data']['status']
                    if status == 'PAUSED':
                        print("✅ Received PAUSED event")
                        paused_event_received = True
                        break
        except Exception as e:
            print(f"❌ Error waiting for PAUSED event: {e}")
            return False
            
        if not paused_event_received:
            return False
            
        # Resume execution
        print("Resuming execution with input...")
        resume_data = {"user_input": "Hello WebSocket"}
        response = client.post(f"/workflows/{execution_id}/resume", json=resume_data)
        
        if response.status_code != 200:
            print(f"❌ Failed to resume: {response.text}")
            return False
        print("✅ Resume request sent")
        
        # Listen for COMPLETED event
        completed_event_received = False
        try:
            while True:
                data = websocket.receive_json()
                print(f"📡 Received: {data['type']} - {data.get('data', {}).get('status')}")
                
                if data['type'] == 'workflow_status_update':
                    status = data['data']['status']
                    if status == 'COMPLETED':
                        print("✅ Received COMPLETED event")
                        completed_event_received = True
                        break
                    elif status == 'FAILED':
                        print(f"❌ Received FAILED event: {data['data'].get('details')}")
                        return False
        except Exception as e:
            print(f"❌ Error waiting for COMPLETED event: {e}")
            return False
            
        if completed_event_received:
            print("\n✅ VERIFICATION SUCCESSFUL")
            return True
        else:
            return False

if __name__ == "__main__":
    try:
        success = test_websocket_and_resume()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error: {e}")
        sys.exit(1)
