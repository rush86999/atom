import requests
import sys

BASE_URL = "http://localhost:8000"

def test_accounts_endpoint():
    print(f"Testing connectivity to {BASE_URL}...")
    
    # 1. Login to get token
    try:
        login_payload = {
            "username": "admin@example.com",
            "password": "securePass123"
        }
        print("Attempting login...")
        login_res = requests.post(f"{BASE_URL}/api/auth/login", data=login_payload)
        
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.status_code} - {login_res.text}")
            return False
            
        token_data = login_res.json()
        token = token_data["access_token"]
        print(f"Login successful. Got token ending in ...{token[-10:]}")
        
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

    # 2. Test Accounts Endpoint
    try:
        headers = {"Authorization": f"Bearer {token}"}
        print("Calling GET /api/auth/accounts...")
        res = requests.get(f"{BASE_URL}/api/auth/accounts", headers=headers)
        
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.text}")
        
        if res.status_code == 200:
            print("SUCCESS: Accounts endpoint is working.")
            return True
        else:
            print("FAILURE: Accounts endpoint returned error.")
            return False
            
    except Exception as e:
        print(f"Request failed: {e}")
        return False

if __name__ == "__main__":
    success = test_accounts_endpoint()
    sys.exit(0 if success else 1)
