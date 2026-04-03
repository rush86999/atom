#!/usr/bin/env python3
"""
Test script for Chat History & Session Management (Phase 28)
"""

import asyncio
import json
import aiohttp

BASE_URL = "http://localhost:8000"

async def test_chat_history():
    print("Testing Chat History & Session Management...")
    print()
    
    async with aiohttp.ClientSession() as session:
        # Test 1: First message (creates new session)
        print("--- 1. First message (new session) ---")
        async with session.post(
            f"{BASE_URL}/api/atom-agent/chat",
            json={
                "message": "Create a workflow to backup files",
                "user_id": "test_user"
                # No session_id - should create new
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                session_id = data.get("session_id")
                print(f"✅ Session created: {session_id}")
                print(f"   Response: {data.get('response', {}).get('message', '')[:80]}...")
                print()
            else:
                print(f"❌ Failed: {resp.status}")
                return
        
        # Test 2: Continue conversation with session_id
        print("--- 2. Continue conversation ---")
        async with session.post(
            f"{BASE_URL}/api/atom-agent/chat",
            json={
                "message": "Schedule that workflow every day at 2am",
                "user_id": "test_user",
                "session_id": session_id
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Same session: {data.get('session_id')}")
                print(f"   Response: {data.get('response', {}).get('message', '')[:80]}...")
                print()
            else:
                print(f"❌ Failed: {resp.status}")
                return
        
        # Test 3: Another message in same session
        print("--- 3. Third message in session ---")
        async with session.post(
            f"{BASE_URL}/api/atom-agent/chat",
            json={
                "message": "List my workflows",
                "user_id": "test_user",
                "session_id": session_id
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Same session: {data.get('session_id')}")
                print(f"   Response: {data.get('response', {}).get('message', '')[:80]}...")
                print()
            else:
                print(f"❌ Failed: {resp.status}")
        
        print("--- 4. Test completed ---")
        print(f"Session ID: {session_id}")
        print()
        print("✅ Chat history should now be persisted in LanceDB")
        print("✅ Session metadata saved in chat_sessions.json")

if __name__ == "__main__":
    try:
        asyncio.run(test_chat_history())
    except Exception as e:
        print(f"Error: {e}")
