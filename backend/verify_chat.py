
import requests
import json

BASE_URL = "http://localhost:8000/api/chat"

def check_chat():
    print("=== CHECKING CHAT SYSTEM ===")
    
    # 1. Health Check
    try:
        res = requests.get(f"{BASE_URL}/health")
        print(f"[Health] {res.status_code}")
        if res.status_code == 200:
            print(json.dumps(res.json(), indent=2))
        else:
            print(res.text)
    except Exception as e:
        print(f"[Health] FAILED: {e}")

    # 2. Root Check
    try:
        res = requests.get(f"{BASE_URL}/")
        print(f"\n[Root] {res.status_code}")
        if res.status_code == 200:
            print("OK")
    except Exception as e:
        print(f"[Root] FAILED: {e}")

    # 3. Message Test (Login first for user_id context if needed, but endpoint expects manual user_id in body)
    print("\n[Message] Sending test message...")
    try:
        payload = {
            "message": "Hello, are you working?",
            "user_id": "admin-test",
            "session_id": "test-session-1"
        }
        res = requests.post(f"{BASE_URL}/message", json=payload)
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            print(json.dumps(res.json(), indent=2))
        else:
            print(f"Error: {res.text}")
    except Exception as e:
        print(f"[Message] FAILED: {e}")

if __name__ == "__main__":
    check_chat()
