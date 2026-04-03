import requests
import sys

BASE_URL = "http://localhost:8000"

def test_agent_access():
    # 1. Login
    login_url = f"{BASE_URL}/api/auth/login"
    payload = {"username": "admin@example.com", "password": "securePass123"}
    print(f"Logging in to {login_url}...")
    
    try:
        res = requests.post(login_url, json=payload)
        if res.status_code != 200:
            print(f"❌ Login Failed: {res.status_code} {res.text}")
            return
        
        token = res.json().get("access_token")
        print("✓ Login successful. Token received.")
        
    except Exception as e:
         print(f"❌ Login Request Error: {e}")
         return

    # 2. Access /api/agents/
    agents_url = f"{BASE_URL}/api/agents/"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Requesting {agents_url}...")
    
    try:
        res = requests.get(agents_url, headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text[:500]}...") # truncate
        
        if res.status_code == 200:
            print("✅ Access GRANTED.")
        elif res.status_code == 401:
            print("❌ Access DENIED (401 Unauthorized).")
        elif res.status_code == 403:
            print("❌ Access FORBIDDEN (403 Permission Denied).")
        else:
            print(f"❌ Unexpected Status: {res.status_code}")

    except Exception as e:
        print(f"❌ Agent Request Error: {e}")

if __name__ == "__main__":
    test_agent_access()
