import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def test():
    print(f"Testing connectivity to {BASE_URL}...")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"GET /health: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"GET /health FAILED: {e}")
        return

    creds = {"username": "admin@example.com", "password": "securePass123"}
    
    endpoints = [
        "/api/auth/login",
        "/api/token",
        "/api/v1/auth/login",
        "/api/login"
    ]
    
    token = None
    
    for ep in endpoints:
        print(f"\nTrying POST {ep}...")
        try:
            # Try JSON
            try_resp = requests.post(f"{BASE_URL}{ep}", json=creds, timeout=5)
            print(f"  JSON response: {try_resp.status_code}")
            if try_resp.status_code != 404:
                print(f"  Body: {try_resp.text[:200]}")
                if try_resp.ok:
                    token = try_resp.json().get("access_token")
                    print("  SUCCESS!")
                    break
            
            # Try Data (Form)
            try_resp = requests.post(f"{BASE_URL}{ep}", data=creds, timeout=5)
            print(f"  DATA response: {try_resp.status_code}")
            if try_resp.status_code != 404:
                print(f"  Body: {try_resp.text[:200]}")
                if try_resp.ok:
                    token = try_resp.json().get("access_token")
                    print("  SUCCESS!")
                    break
        except Exception as e:
            print(f"  FAILED: {e}")

    if not token:
        print("\nCould not get token.")
        return

    print(f"\nGot token: {token[:20]}...")
    
    # Try trigger agent
    headers = {"Authorization": f"Bearer {token}"}
    agent_id = "inventory_reconcile" # Known agent
    
    print(f"\nTriggering agent {agent_id}...")
    try:
        run_resp = requests.post(
            f"{BASE_URL}/api/agents/{agent_id}/run", 
            headers=headers,
            json={"prompt": "Reconcile inventory", "sync": True},
            timeout=30 # Wait longer for sync
        )
        print(f"Run Agent: {run_resp.status_code}")
        print(f"Response: {run_resp.text}")
    except Exception as e:
        print(f"Run Agent FAILED: {e}")

if __name__ == "__main__":
    test()
