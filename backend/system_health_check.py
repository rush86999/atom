
import requests
import sys

BASE_URL = "http://localhost:8000/api"
AUTH_URL = f"{BASE_URL}/auth"

def check(name, url, method="GET", headers=None, data=None, expected_code=200):
    print(f"[{name}] Checking {url}...", end=" ")
    try:
        if method == "GET":
            res = requests.get(url, headers=headers)
        elif method == "POST":
            res = requests.post(url, headers=headers, json=data, data=data)
        
        if res.status_code == expected_code:
            print(f"✅ OK ({res.status_code})")
            return res
        else:
            print(f"❌ FAILED ({res.status_code})")
            print(f"   Response: {res.text[:200]}...")
            return res
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

def main():
    print("=== STARTING SYSTEM HEALTH CHECK ===")
    
    # 1. Basic Health
    check("Health", "http://localhost:8000/health")
    
    # 2. Auth - Login
    login_data = {"username": "admin@example.com", "password": "securePass123"}
    res = requests.post(f"{AUTH_URL}/login", data=login_data)
    
    token = None
    if res and res.status_code == 200:
        print("✅ Login Successful")
        token = res.json().get("access_token")
    else:
        print("❌ Login Failed")
        print(f"   Response: {res.text if res else 'No Connection'}")
        
    if not token:
        print("!!! CANVAS CRITIQUE: Auth is broken. Cannot check authenticated endpoints.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Auth - Profile
    check("Profile", f"{AUTH_URL}/me", headers=headers)
    
    # 4. Auth - Accounts (New Endpoint)
    check("Linked Accounts", f"{AUTH_URL}/accounts", headers=headers)
    
    # 5. Agents / Workflow (Core Functionality)
    check("Agents List", "http://localhost:8000/api/agents", headers=headers) 
    
    # 6. Integrations Status
    check("Integrations Stats", f"{BASE_URL}/integrations/stats", headers=headers)

if __name__ == "__main__":
    main()
