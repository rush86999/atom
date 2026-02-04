#!/usr/bin/env python3
"""
Test script for Chat History & Context Resolution (Phase 28)
"""

import asyncio
import json
import time
import aiohttp

BASE_URL = "http://localhost:8000"

async def test_chat_context():
    print("Testing Chat Context Resolution...")
    print()
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Create a workflow (saves ID to history)
        print("--- 1. Create Workflow ---")
        async with session.post(
            f"{BASE_URL}/api/atom-agent/chat",
            json={
                "message": "Create a workflow to backup files",
                "user_id": "test_user_context"
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                session_id = data.get("session_id")
                response_msg = data.get('response', {}).get('message', '')
                print(f"✅ Session created: {session_id}")
                print(f"   Response: {response_msg[:80]}...")
                
                # Extract workflow name/ID from response text or data if possible
                # The response text usually contains "I've created a workflow: **Name**"
                print()
            else:
                print(f"❌ Failed: {resp.status}")
                return
        
        # Wait a bit for async saving (though it's awaited in endpoint, good to be safe)
        time.sleep(1)
        
        # Test 2: Schedule "that workflow" (should resolve ID)
        print("--- 2. Schedule 'that workflow' ---")
        async with session.post(
            f"{BASE_URL}/api/atom-agent/chat",
            json={
                "message": "Schedule that workflow every day at 2am",
                "user_id": "test_user_context",
                "session_id": session_id
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                response_msg = data.get('response', {}).get('message', '')
                print(f"✅ Response: {response_msg}")
                
                if "Scheduled" in response_msg and "Every day at 02:00" in response_msg:
                    print("✅ SUCCESS: Context resolved and workflow scheduled!")
                else:
                    print("❌ FAILURE: Context resolution failed or scheduling failed.")
                print()
            else:
                print(f"❌ Failed: {resp.status}")
                return
        
        print("--- Test completed ---")

if __name__ == "__main__":
    try:
        asyncio.run(test_chat_context())
    except Exception as e:
        print(f"Error: {e}")
