
import requests
try:
    url = "http://localhost:8000/api/auth/login"
    payload = {
        "username": "admin@example.com",
        "password": "securePass123" 
    }
    print(f"Testing Login at {url}...")
    response = requests.post(url, data=payload)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("LOGIN SUCCESS!")
        print(f"Token: {response.json().get('access_token')[:10]}...")
    else:
        print(f"LOGIN FAILED: {response.text}")
except Exception as e:
    print(f"Error: {e}")
