
import json
import sys
import time
import requests

BASE_URL = "http://localhost:5063"

def print_pass(message):
    print(f"✅ PASS: {message}")

def print_fail(message, details=None):
    print(f"❌ FAIL: {message}")
    if details:
        print(f"   Details: {details}")

def verify_migration():
    print("🚀 Starting Enterprise Migration Verification")
    print("============================================")

    # 1. Create Workspace
    print("\n1. Testing Workspace Creation...")
    ws_data = {
        "name": f"Test Workspace {int(time.time())}",
        "description": "Created by verification script",
        "plan_tier": "enterprise"
    }
    try:
        resp = requests.post(f"{BASE_URL}/api/enterprise/workspaces", json=ws_data)
        if resp.status_code == 201:
            ws_id = resp.json()["workspace_id"]
            print_pass(f"Created workspace: {ws_id}")
        else:
            print_fail("Failed to create workspace", resp.text)
            return
    except Exception as e:
        print_fail(f"Connection error: {e}")
        return

    # 2. Get Workspace
    print("\n2. Testing Get Workspace...")
    resp = requests.get(f"{BASE_URL}/api/enterprise/workspaces/{ws_id}")
    if resp.status_code == 200 and resp.json()["name"] == ws_data["name"]:
        print_pass("Retrieved workspace details correctly")
    else:
        print_fail("Failed to get workspace", resp.text)

    # 3. Create Team
    print("\n3. Testing Team Creation...")
    team_data = {
        "name": "Engineering",
        "description": "Core dev team",
        "workspace_id": ws_id
    }
    resp = requests.post(f"{BASE_URL}/api/enterprise/teams", json=team_data)
    if resp.status_code == 201:
        team_id = resp.json()["team_id"]
        print_pass(f"Created team: {team_id}")
    else:
        print_fail("Failed to create team", resp.text)
        return

    # 4. Create User
    print("\n4. Testing User Creation...")
    # Use a unique email
    email = f"verify_{int(time.time())}@example.com"
    user_data = {
        "email": email,
        "password": "Password123!",
        "first_name": "Verify",
        "last_name": "User",
        "workspace_id": ws_id
    }
    # Note: Using auth register endpoint as it creates the user in DB
    resp = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        print_pass(f"Created user and got token")
        
        # Get user ID from /me
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        user_id = me_resp.json()["id"]
        print_pass(f"User ID: {user_id}")
    else:
        print_fail("Failed to create user", resp.text)
        return

    # 5. Add User to Team
    print("\n5. Testing Add User to Team...")
    resp = requests.post(f"{BASE_URL}/api/enterprise/teams/{team_id}/users/{user_id}")
    if resp.status_code == 200:
        print_pass("Added user to team")
    else:
        print_fail("Failed to add user to team", resp.text)

    # 6. Verify Team Membership
    print("\n6. Verifying Team Membership...")
    resp = requests.get(f"{BASE_URL}/api/enterprise/teams/{team_id}")
    if resp.status_code == 200:
        members = resp.json().get("members", [])
        member_ids = [m["user_id"] for m in members]
        if user_id in member_ids:
            print_pass("User found in team members list")
        else:
            print_fail("User NOT found in team members list", members)
    else:
        print_fail("Failed to get team details", resp.text)

    # 7. List Workspaces (Persistence Check)
    print("\n7. Testing List Workspaces...")
    resp = requests.get(f"{BASE_URL}/api/enterprise/workspaces")
    if resp.status_code == 200:
        workspaces = resp.json()
        if any(w["workspace_id"] == ws_id for w in workspaces):
            print_pass(f"Found workspace {ws_id} in list")
        else:
            print_fail("Workspace not found in list")
    else:
        print_fail("Failed to list workspaces", resp.text)

    print("\n============================================")
    print("✨ Verification Complete")

if __name__ == "__main__":
    verify_migration()
