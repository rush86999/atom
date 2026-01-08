import requests
import os

BASE_URL = "http://localhost:8000/api/openai"

def test_openai_health():
    print("Testing OpenAI Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_openai_chat():
    print("\nTesting OpenAI Chat Completion...")
    payload = {
        "prompt": "Hello, are you operational?",
        "model": "gpt-4o-mini",
        "max_tokens": 10
    }
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response Content: {response.json().get('content')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # In real test, we would need the server running.
    # For now, let's just check if routes are registered.
    print("Checking if OpenAI routes are registered in FastAPI app...")
    import sys
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from main_api_app import app
    from core.lazy_integration_registry import load_integration
    
    print("Manually loading OpenAI integration...")
    router = load_integration("openai")
    if router:
        app.include_router(router)
        print("✓ Router loaded manually")
    else:
        print("✗ Router failed to load")

    found = False
    for route in app.routes:
        if hasattr(route, 'path') and '/api/openai' in route.path:
            print(f"Found Route: {route.path}")
            found = True
    
    if found:
        print("SUCCESS: OpenAI routes are registered.")
    else:
        print("FAILURE: OpenAI routes not found.")
