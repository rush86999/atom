import json
import uuid
import requests

BASE_URL = "http://localhost:8000/api/atom-agent/chat"

def test_chat(message):
    print(f"\n--- Testing: '{message}' ---")
    payload = {
        "message": message,
        "user_id": "test_user",
        "session_id": f"test_{uuid.uuid4()}",
        "conversation_history": []
    }
    
    try:
        response = requests.post(BASE_URL, json=payload)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Success")
                print(f"Response: {data['response']['message']}")
                if data['response'].get('actions'):
                    print(f"Actions: {[a['label'] for a in data['response']['actions']]}")
            else:
                print(f"❌ Failed: {data.get('error')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    print("Testing Unified Chat Interface...")
    
    # 1. Test Workflow Creation (Phase 24)
    test_chat("Create a workflow to send an email to boss@company.com every Monday")
    
    # 2. Test Finance (Phase 25B)
    test_chat("Show my recent transactions")
    
    # 3. Test Tasks (Phase 25B)
    test_chat("Create a task to buy groceries")
    
    # 4. Test Listing Workflows
    test_chat("List my workflows")
