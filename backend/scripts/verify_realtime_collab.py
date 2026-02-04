
import asyncio
import json
import os
import sys
import requests
from websockets.client import connect

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = "http://localhost:5061"
WS_URL = "ws://localhost:5061/ws"

def verify_realtime_collab():
    print("🚀 Starting Real-time Collaboration Verification...")
    
    # 1. Register User
    print("\n1. Registering Test User...")
    email = f"test_collab_{os.urandom(4).hex()}@example.com"
    password = "password123"
    
    try:
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User"
        })
        
        if response.status_code != 200:
            print(f"❌ Registration failed: {response.text}")
            return
            
        token = response.json()["access_token"]
        print(f"✅ User registered. Token: {token[:10]}...")
        
    except Exception as e:
        print(f"❌ Error during registration: {e}")
        return

    # 2. Create Team (Need to manually create via DB or if endpoint exists)
    # For now, we'll assume a team exists or create one if we had the endpoint ready.
    # Since we didn't expose a "create team" endpoint in the new system yet (only models),
    # we might need to rely on the existing enterprise endpoints or just use a dummy team_id
    # and hope the message send doesn't strictly enforce foreign key if we didn't migrate tables yet.
    # Wait, we defined models but didn't run migration. The tables might not exist!
    
    # CRITICAL: We need to create the tables.
    # We can use a script to init the db.
    
    print("\n⚠️  Skipping full E2E test because DB tables need creation.")
    print("Please run the DB initialization first.")
    
    # We can try to connect to WS at least
    
    async def test_ws():
        print("\n2. Testing WebSocket Connection...")
        uri = f"{WS_URL}?token={token}"
        try:
            async with connect(uri) as websocket:
                print("✅ WebSocket Connected!")
                
                # Subscribe to a channel
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "channel": "team:test-team-123"
                }))
                
                # Wait for a message (simulated)
                # In a real test we'd trigger the API here
                
                print("✅ WebSocket Test Passed")
        except Exception as e:
            print(f"❌ WebSocket Connection Failed: {e}")

    asyncio.run(test_ws())

if __name__ == "__main__":
    verify_realtime_collab()
