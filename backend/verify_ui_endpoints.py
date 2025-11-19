import sys
import os
import asyncio
from fastapi.testclient import TestClient
from datetime import datetime

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from main_api_app import app
except ImportError:
    print("Error: Could not import main_api_app. Make sure you are in the backend directory.")
    sys.exit(1)

client = TestClient(app)

def test_ui_endpoints():
    print("Testing UI Endpoints...")
    
    # 1. Test Calendar Endpoints
    print("\n[Calendar] Testing /api/v1/calendar/events...")
    response = client.get("/api/v1/calendar/events")
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"[OK] Calendar events fetched. Count: {len(data.get('events', []))}")
        else:
            print(f"[FAIL] Calendar success flag missing: {data}")
    else:
        print(f"[FAIL] Calendar endpoint failed: {response.status_code}")

    # 2. Test Task Endpoints
    print("\n[Projects] Testing /api/v1/tasks...")
    response = client.get("/api/v1/tasks?platform=all")
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"[OK] Tasks fetched. Count: {len(data.get('tasks', []))}")
        else:
            print(f"[FAIL] Tasks success flag missing: {data}")
    else:
        print(f"[FAIL] Tasks endpoint failed: {response.status_code}")

    # 3. Test Create Task
    print("\n[Projects] Testing Create Task...")
    new_task = {
        "title": "Verify UI Implementation",
        "description": "Automated test task",
        "priority": "high",
        "dueDate": datetime.now().isoformat(),
        "status": "todo",
        "platform": "local"
    }
    response = client.post("/api/v1/tasks/", json=new_task)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"[OK] Task created successfully: {data.get('task', {}).get('id')}")
        else:
            print(f"[FAIL] Create task failed: {data}")
    else:
        print(f"[FAIL] Create task endpoint failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_ui_endpoints()
