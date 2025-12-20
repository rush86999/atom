
import requests
import sys

def check_health():
    url = "http://127.0.0.1:5059/health"
    try:
        print(f"Checking {url}...")
        response = requests.get(url, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Health check failed: {e}")

if __name__ == "__main__":
    check_health()
