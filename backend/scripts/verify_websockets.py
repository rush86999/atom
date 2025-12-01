#!/usr/bin/env python3
"""
WebSocket Real-time Updates Verification Script
Tests WebSocket connection, subscription, and broadcasting
"""

import asyncio
import websockets
import json
from datetime import datetime

print("="*70)
print("WEBSOCKET REAL-TIME UPDATES VERIFICATION")
print("="*70)
print()

async def test_websocket_connection():
    """Test WebSocket connection and basic messaging"""
    uri = "ws://localhost:5059/ws?user_id=test_user&channels=workflows,system"
    
    try:
        print("Test 1: WebSocket Connection")
        print("-"*70)
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established message
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get("type") == "connection_established":
                print(f"✅ Connected as: {data.get('user_id')}")
                print(f"   Message: {data.get('message')}")
            else:
                print(f"❌ Unexpected message type: {data.get('type')}")
                return False
            
            print()
            print("Test 2: Channel Subscription")
            print("-"*70)
            
            # Subscribe to a channel
            await websocket.send(json.dumps({
                "type": "subscribe",
                "channel": "test_channel"
            }))
            
            # Wait for subscription confirmation
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get("type") == "subscribed":
                print(f"✅ Subscribed to channel: {data.get('channel')}")
            else:
                print(f"❌ Subscription failed")
                return False
            
            print()
            print("Test 3: Ping/Pong")
            print("-"*70)
            
            # Send ping
            ping_time = datetime.now().isoformat()
            await websocket.send(json.dumps({
                "type": "ping",
                "timestamp": ping_time
            }))
            
            # Wait for pong
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get("type") == "pong":
                print(f"✅ Ping/Pong working")
                print(f"   Round trip completed")
            else:
                print(f"❌ Pong not received")
                return False
            
            print()
            print("Test 4: Get Stats")
            print("-"*70)
            
            # Request stats
            await websocket.send(json.dumps({
                "type": "get_stats"
            }))
            
            # Wait for stats
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get("type") == "stats":
                stats = data.get("data", {})
                print(f"✅ Stats received:")
                print(f"   Total connections: {stats.get('total_connections')}")
                print(f"   Active users: {stats.get('active_users')}")
                print(f"   Channels: {len(stats.get('channels', {}))}")
            else:
                print(f"❌ Stats not received")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ Connection Error: {str(e)}")
        print(f"   Make sure the backend server is running on port 5059")
        return False

# Run the test
success = asyncio.run(test_websocket_connection())

print()
print("="*70)
if success:
    print("VERIFICATION COMPLETE: SUCCESS")
    print("="*70)
    print()
    print("WebSocket Infrastructure Working:")
    print("  ✅ Connection management")
    print("  ✅ Channel subscriptions")
    print("  ✅ Ping/Pong keep-alive")
    print("  ✅ Stats reporting")
else:
    print("VERIFICATION FAILED")
    print("="*70)
    print()
    print("Please ensure:")
    print("  1. Backend server is running (uvicorn main_api_app:app --port 5059)")
    print("  2. WebSocket routes are properly registered")
    print("  3. No firewall blocking WebSocket connections")
print()

exit(0 if success else 1)
