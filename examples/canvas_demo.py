"""
Example: Canvas CRUD lifecycle — present, read, update, delete.

Demonstrates the full canvas CRUD workflow that agents can perform.

Prerequisites:
  - Atom backend running on http://localhost:8000

Run:
  python examples/canvas_demo.py
"""

import httpx
import os
import json

BASE_URL = os.getenv("ATOM_BASE_URL", "http://localhost:8000")

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        canvas_id = "demo_canvas_001"

        # 1. Present a canvas (simulates agent creating it)
        print("1. Presenting a markdown canvas...")
        # This would normally be done via the agent tool, but we can
        # demonstrate the CRUD API directly.
        resp = await client.put(f"/api/canvas/{canvas_id}", params={
            "canvas_type": "generic",
            "title": "Demo Canvas",
        }, json={"content": "# Hello from Atom!\n\nThis canvas was created via the API."})
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"   ✅ {resp.json()}")

        # 2. Read the canvas
        print("\n2. Reading canvas content...")
        resp = await client.get(f"/api/canvas/{canvas_id}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ Canvas type: {data.get('canvas_type')}")
            print(f"   Content preview: {str(data.get('content', ''))[:100]}")
        else:
            print(f"   Result: {resp.status_code} {resp.text}")

        # 3. List canvases
        print("\n3. Listing all canvases...")
        resp = await client.get("/api/canvas/")
        if resp.status_code == 200:
            data = resp.json()
            count = data.get("count", 0)
            print(f"   ✅ Found {count} canvas(es)")

        # 4. Get version history
        print("\n4. Getting version history...")
        resp = await client.get(f"/api/canvas/{canvas_id}/history")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ {data.get('count', 0)} history entries")

        # 5. Delete the canvas
        print("\n5. Deleting canvas...")
        resp = await client.delete(f"/api/canvas/{canvas_id}")
        if resp.status_code == 200:
            print(f"   ✅ {resp.json()}")

        # 6. Verify it's deleted
        print("\n6. Verifying deletion...")
        resp = await client.get(f"/api/canvas/{canvas_id}")
        if resp.status_code == 404:
            print("   ✅ Canvas correctly shows as not found after deletion")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
