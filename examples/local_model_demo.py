"""
Example: Run Atom with a local model (Ollama).

No cloud API key needed — runs entirely on your machine.

Prerequisites:
  - Ollama installed (https://ollama.ai)
  - A model pulled: ollama pull llama3:8b
  - Atom backend running with ATOM_LOCAL_ONLY=true

Run:
  ATOM_LOCAL_ONLY=true python examples/local_model_demo.py
"""

import httpx
import os
import sys

BASE_URL = os.getenv("ATOM_BASE_URL", "http://localhost:8000")

async def main():
    print("🦙 Local Model Demo")
    print("===================")
    print("This example sends a chat message using a local Ollama model.")
    print("No cloud API key required.\n")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        # Check health
        resp = await client.get("/health/live")
        if resp.status_code != 200:
            print("❌ Backend not running on :8000. Start it with: ./scripts/dev.sh")
            return
        print("✅ Backend is live")

        # Register a local model provider
        print("\n1. Registering Ollama as a local model provider...")
        # Note: requires auth — in production this would use a real token
        # For demo purposes, we skip if auth fails
        try:
            resp = await client.post("/api/local-models", json={
                "name": "Demo Ollama",
                "provider_type": "ollama",
                "base_url": "http://localhost:11434/v1",
            })
            if resp.status_code == 200:
                provider_id = resp.json().get("id")
                print(f"   ✅ Registered provider (id: {provider_id})")

                # Discover models
                print("\n2. Discovering models...")
                resp = await client.get(f"/api/local-models/{provider_id}/models")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    print(f"   ✅ Found {len(models)} model(s): {models[:5]}")
                else:
                    print(f"   ⚠️ Discovery failed (is Ollama running?)")
            else:
                print(f"   (skipped — auth required: {resp.status_code})")
        except Exception:
            print("   (skipped — register manually in Settings → Local Models)")

        print("\n3. To chat with your local model:")
        print("   a. Open http://localhost:3000")
        print("   b. Log in (check backend/logs/ for admin password)")
        print("   c. Send a message — it routes to Ollama automatically!")
        print("\n   With ATOM_LOCAL_ONLY=true, no cloud API key is needed.")
        print("   The learning router will prefer the local model when it performs well.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
