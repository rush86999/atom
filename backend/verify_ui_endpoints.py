import requests
import json
import sys

BASE_URL = "http://localhost:5059"

def test_endpoint(method, path, payload=None):
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url)
        else:
            response = requests.post(url, json=payload)
        
        print(f"{method} {path}: {response.status_code}")
        if response.status_code == 200:
            # print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(response.text)
            return False
    except Exception as e:
        print(f"Error calling {path}: {e}")
        return False

def main():
    print("Verifying UI Endpoints...")
    
    # 1. Service Health (Dashboard)
    # Note: These are mounted at root /api/v1/integrations in main_api_app.py
    # But service_health_endpoints.py defines router with prefix /api/v1/integrations
    # AND main_api_app.py mounts it with prefix=""
    # So path is /api/v1/integrations/{service}/health
    
    print("\n--- Service Health ---")
    test_endpoint("GET", "/api/v1/integrations/box/health")
    test_endpoint("GET", "/api/v1/integrations/services/status")
    
    # 2. Workflow UI
    # Mounted at /api/v1/workflow-ui
    print("\n--- Workflow UI ---")
    test_endpoint("GET", "/api/v1/workflow-ui/templates")
    test_endpoint("GET", "/api/v1/workflow-ui/definitions")
    test_endpoint("GET", "/api/v1/workflow-ui/services")
    
    # 3. Workflow Agent (Chat)
    # Mounted at /api/workflow-agent (no v1 prefix in router, but check main_api_app mount)
    # main_api_app mounts it with include_router(workflow_agent_router)
    # workflow_agent_endpoints.py defines prefix="/api/workflow-agent"
    print("\n--- Workflow Agent ---")
    chat_payload = {
        "message": "Create a workflow to summarize emails",
        "user_id": "test_user",
        "session_id": "test_session",
        "conversation_history": []
    }
    test_endpoint("POST", "/api/workflow-agent/chat", chat_payload)

if __name__ == "__main__":
    main()
