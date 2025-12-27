import asyncio
import httpx
import sys

async def verify_unified_centers():
    base_url = "http://127.0.0.1:5059"
    
    print("--- Verifying Unified Command Centers ---")
    
    async with httpx.AsyncClient() as client:
        # 1. Verify Sales Pipeline
        print("\n1. Checking /api/sales/pipeline...")
        try:
            resp = await client.get(f"{base_url}/api/sales/pipeline")
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Data: {resp.json()[:2]} (truncated)")
            else:
                print(f"Error: {resp.text}")
        except Exception as e:
            print(f"Request failed: {e}")

        # 2. Verify Project Tasks
        print("\n2. Checking /api/projects/unified-tasks...")
        try:
            resp = await client.get(f"{base_url}/api/projects/unified-tasks")
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Data: {resp.json()[:2]} (truncated)")
            else:
                print(f"Error: {resp.text}")
        except Exception as e:
            print(f"Request failed: {e}")

        # 3. Verify Intelligence Entities (Global Search Backend)
        print("\n3. Checking /api/intelligence/entities...")
        try:
            resp = await client.get(f"{base_url}/api/intelligence/entities")
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Count: {len(resp.json())}")
            else:
                print(f"Error: {resp.text}")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    # Note: Server must be running for this to work
    # asyncio.run(verify_unified_centers())
    print("Verification script created. Call manually if server is running.")
