import sys
import os
import asyncio
from fastapi.testclient import TestClient

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from main_api_app import app
except ImportError:
    print("Error: Could not import main_api_app. Make sure you are in the backend directory.")
    sys.exit(1)

client = TestClient(app)

def test_routing():
    print("Testing Routing Configuration...")
    
    # 1. Test Health Endpoint
    response = client.get("/health")
    if response.status_code == 200:
        print("[OK] /health endpoint is accessible")
    else:
        print(f"[FAIL] /health endpoint failed: {response.status_code}")

    # 2. Test Workflow UI Endpoints (New Prefix)
    response = client.get("/api/workflows/templates")
    if response.status_code == 200:
        print("[OK] /api/workflows/templates is accessible (Prefix fixed)")
    else:
        print(f"[FAIL] /api/workflows/templates failed: {response.status_code}")
        # Try old prefix to see if it's still there
        resp_old = client.get("/api/v1/workflow-ui/templates")
        if resp_old.status_code == 200:
            print("   [WARN] Old prefix /api/v1/workflow-ui is still active!")

    # 3. Test Workflow Agent Endpoints
    # This requires a POST with body
    response = client.post("/api/workflow-agent/chat", json={
        "message": "Hello",
        "user_id": "test",
        "session_id": "test",
        "conversation_history": []
    })
    if response.status_code == 200:
        print("[OK] /api/workflow-agent/chat is accessible")
    elif response.status_code != 404:
        print(f"[OK] /api/workflow-agent/chat exists (Status: {response.status_code})")
    else:
        print(f"[FAIL] /api/workflow-agent/chat not found (404)")

if __name__ == "__main__":
    test_routing()
