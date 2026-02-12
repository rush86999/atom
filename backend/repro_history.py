import requests
import json
import sys

def probe_history():
    # Test Next.js Proxy
    base_url = "http://localhost:3000"
    session_id = "test_session_123"
    user_id = "test_user"
    
    url = f"{base_url}/api/chat/history/{session_id}"
    params = {"user_id": user_id}
    
    print(f"Probing: {url} with params {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        
        with open("repro_history_output.txt", "w", encoding="utf-8") as f:
            f.write(response.text)
            
        print("Response saved to repro_history_output.txt")
            
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    probe_history()
