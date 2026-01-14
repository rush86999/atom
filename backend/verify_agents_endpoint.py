
import requests
import sys

# Try both common paths
PATHS = [
    "http://localhost:8000/api/agents",
    "http://localhost:8000/api/v1/agents"
]

def check_agents():
    # 1. Login
    try:
        auth = requests.post("http://localhost:8000/api/auth/login", 
                           data={"username": "admin@example.com", "password": "securePass123"})
        if auth.status_code != 200:
            print(f"LOGIN_FAILED: {auth.status_code}")
            return
            
        token = auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Check Paths
        success = False
        for url in PATHS:
            res = requests.get(url, headers=headers)
            print(f"CHECKING {url} -> {res.status_code}")
            if res.status_code == 200:
                print(f"FOUND AT: {url}")
                print(f"RESPONSE: {str(res.json())[:100]}...")
                success = True
                break
        
        if success:
            print("AGENTS_ENDPOINT_VERIFIED")
        else:
            print("AGENTS_ENDPOINT_NOT_FOUND")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    check_agents()
