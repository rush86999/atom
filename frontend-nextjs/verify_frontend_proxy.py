
import requests
import json

def test_proxy():
    url = "http://localhost:3000/api/workflows/optimize"
    
    # Mock Workflow Payload (Frontend Structure)
    payload = {
        "workflow": {
            "workflow_id": "test_proxy_wf",
            "steps": [
                { "step_id": "A", "description": "Step A", "parameters": {}, "next_steps": ["B"] },
                { "step_id": "B", "description": "Step B", "parameters": {}, "next_steps": [] }
            ]
        }
    }
    
    print(f"🚀 Sending request to {url}...")
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"Status Code: {response.status_code}")
        if response.ok:
            print("✅ Proxy Success!")
            print("Response:", json.dumps(response.json(), indent=2))
        else:
            print(f"❌ Proxy Failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_proxy()
