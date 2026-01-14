
import requests

# 1. Login to get token
login_url = "http://localhost:8000/api/auth/login"
payload = {
    "username": "admin@example.com",
    "password": "securePass123" 
}
print(f"Logging in...")
try:
    login_res = requests.post(login_url, data=payload)
    if login_res.status_code != 200:
        print(f"Login failed: {login_res.text}")
        exit(1)
        
    token = login_res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # 2. Test Accounts Endpoint
    accounts_url = "http://localhost:8000/api/auth/accounts"
    print(f"Testing {accounts_url}...")
    
    res = requests.get(accounts_url, headers=headers)
    print(f"Status: {res.status_code}")
    if res.status_code == 200:
        print("Response JSON:")
        print(res.json())
        print("SUCCESS")
    else:
        print(f"FAILED: {res.text}")

except Exception as e:
    print(f"Error: {e}")
