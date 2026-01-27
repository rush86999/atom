import requests
import json
import sys

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def probe_chat():
    url = "http://localhost:8000/api/chat/message"
    payload = {
        "user_id": "test_user",
        "message": "Schedule a meeting",
        "session_id": "probe_session"
    }
    
    print(f"Sending POST to {url}")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        print("\n--- API RESPONSE ---")
        print(json.dumps(data, indent=2))
        
        # Validation
        if "metadata" in data and "actions" in data["metadata"]:
            print("\n✅ SUCCESS: 'metadata.actions' found in response.")
            actions = data["metadata"]["actions"]
            print(f"Actions found: {len(actions)}")
            for a in actions:
                print(f" - Action: {a.get('label')} ({a.get('type')})")
        else:
            print("\n❌ FAILURE: 'metadata.actions' MISSING in response.")
            
    except Exception as e:
        print(f"\n❌ REQUEST FAILED: {e}")

if __name__ == "__main__":
    probe_chat()
