from datetime import datetime
import json
import requests


def verify_conflict_resolution():
    base_url = "http://localhost:8000/api/v1/calendar"
    print("🚀 Starting Schedule Conflict Resolution Verification...")

    # 1. Verify Optimization Endpoint
    print("\n[1/2] Testing /optimize endpoint...")
    try:
        response = requests.get(f"{base_url}/optimize")
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                print(f"✅ Success! Found {len(data)} optimizations.")
                for opt in data:
                    print(f"   - Resolving conflict: '{opt['event_to_move']}' vs '{opt['conflict_with']}'")
                    print(f"   - Suggested slots: {len(opt['suggested_slots'])}")
            else:
                print("ℹ️ No conflicts found in current mock data (this is okay if mock events don't overlap).")
        else:
            print(f"❌ Failed to reach /optimize. Status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")

    # 2. Verify NLU Registration
    print("\n[2/2] Checking NLU intent registration...")
    try:
        with open("src/services/ai/nluService.ts", "r") as f:
            content = f.read()
            if "schedule_optimization" in content:
                print("✅ 'schedule_optimization' intent found in nluService.ts")
            else:
                print("❌ 'schedule_optimization' intent missing from nluService.ts")
    except Exception as e:
        print(f"❌ Error checking NLU file: {e}")

    print("\n✨ Verification Complete!")

if __name__ == "__main__":
    verify_conflict_resolution()
