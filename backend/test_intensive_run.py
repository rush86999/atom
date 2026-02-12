
import requests
import json
import sys

def test_intensive_run():
    base_url = "http://localhost:8000"
    
    # 1. Login
    print("Logging in...")
    try:
        auth_resp = requests.post(f"{base_url}/api/auth/token", data={
            "username": "admin@example.com",
            "password": "securePass123"
        })
        if auth_resp.status_code != 200:
            print(f"Login failed: {auth_resp.text}")
            sys.exit(1)
            
        token = auth_resp.json()["access_token"]
        print("Login success. Token obtained.")
    except Exception as e:
        print(f"Login error: {e}")
        sys.exit(1)

    # 2. Run Agent
    url = f"{base_url}/api/agents/inventory_reconcile/run"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "parameters": {
            "task_input": "Intensive Test SKU-999"
        }
    }
    
    try:
        print(f"Sending POST to {url} with payload: {payload}")
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("SUCCESS: Run triggered.")
        else:
            print("FAILURE: Run failed.")
            sys.exit(1)
            
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_intensive_run()
