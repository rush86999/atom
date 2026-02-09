import requests
import sys

# Test via the Frontend Proxy (Next.js)
BASE_URL = "http://localhost:3000" 

def test_proxy_access():
    print(f"Testing Proxy Access at {BASE_URL}...")
    
    # 1. Login via Proxy
    login_url = f"{BASE_URL}/api/auth/login"
    payload = {"username": "admin@example.com", "password": "securePass123"}
    print(f"1. Logging in via {login_url}...")
    
    try:
        res = requests.post(login_url, json=payload)
        if res.status_code != 200:
            print(f"❌ Login Failed at Proxy: {res.status_code} {res.text}")
            return
        
        data = res.json()
        token = data.get("access_token")
        if not token:
             print("❌ Login succeeded but no token returned!")
             print(f"Response keys: {data.keys()}")
             return
             
        print("✓ Login successful via Proxy. Token received.")
        
    except Exception as e:
         print(f"❌ Login Request Error: {e}")
         print("Is the Next.js server (npm run dev) running on port 3000?")
         return

    # 2. Access /api/agents/ via Proxy
    agents_url = f"{BASE_URL}/api/agents/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    print(f"2. Requesting {agents_url} via Proxy...")
    
    try:
        res = requests.get(agents_url, headers=headers)
        print(f"Status: {res.status_code}")
        
        if res.status_code == 200:
            print("✅ Proxy Access GRANTED.")
        elif res.status_code == 401:
            print("❌ Proxy Access DENIED (401 Unauthorized). Header likely stripped or token rejected.")
            print(f"Response: {res.text[:200]}")
        elif res.status_code == 403:
            print("❌ Proxy Access FORBIDDEN (403 Permission Denied).")
        else:
            print(f"❌ Unexpected Status: {res.status_code}")
            print(f"Response: {res.text[:200]}")

    except Exception as e:
        print(f"❌ Agent Request Error: {e}")

if __name__ == "__main__":
    test_proxy_access()
