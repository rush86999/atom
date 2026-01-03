import requests

url = "http://localhost:5059/api/auth/login"
payload = {
    "username": "admin@example.com",
    "password": "securePass123"
}
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

try:
    response = requests.post(url, data=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(response.text)
except Exception as e:
    print(f"Request failed: {e}")
