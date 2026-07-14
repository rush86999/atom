"""
Example: Chat with an Atom agent.

Prerequisites:
  - Atom backend running on http://localhost:8000
  - An API key configured (or ATOM_LOCAL_ONLY=true for Ollama)

Run:
  python examples/chat_with_agent.py
"""

import httpx
import sys
import os

BASE_URL = os.getenv("ATOM_BASE_URL", "http://localhost:8000")
EMAIL = os.getenv("ATOM_USER_EMAIL", "admin@example.com")
PASSWORD = os.getenv("ATOM_USER_PASSWORD", "")

if not PASSWORD:
    print("❌ Set ATOM_USER_PASSWORD env var (check backend/logs/bootstrap_admin_password.txt)")
    sys.exit(1)

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # 1. Login
        print("1. Logging in...")
        resp = await client.post("/api/auth/login", json={
            "username": EMAIL,
            "password": PASSWORD,
        })
        if resp.status_code != 200:
            print(f"❌ Login failed: {resp.status_code} {resp.text}")
            return
        token = resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("   ✅ Logged in")

        # 2. Send a chat message
        print("\n2. Sending message to agent...")
        message = "Hello! I'm testing Atom. What can you help me with?"
        resp = await client.post("/api/chat/message", json={
            "message": message,
            "user_id": "default_user",
            "session_id": "new",
            "context": {},
        }, headers=headers)

        data = resp.json()
        if data.get("error_code") == "no_llm_provider":
            print("   ⚠️ No AI provider configured. Set an API key or enable Ollama.")
            return

        if data.get("success"):
            print(f"   🤖 Agent: {data['message'][:200]}")
            if data.get("model"):
                print(f"   🏷️ Model: {data['model']}")
        else:
            print(f"   ❌ Error: {data}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
