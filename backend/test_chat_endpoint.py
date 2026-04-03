import json
import uuid
import requests


def test_chat():
    url = "http://localhost:8000/api/workflow-agent/chat"
    
    payload = {
        "message": "Create a workflow to send an email to sales@example.com when a new lead arrives in Slack",
        "user_id": "test_user",
        "session_id": "test_session",
        "conversation_history": []
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat()
