import json
import time
import requests


def verify_burnout_features():
    base_url = "http://localhost:8000/api/v1/analytics"
    print("🚀 Starting Burnout & Deadline Risk Verification...")

    # 1. Verify Burnout Risk Endpoint
    print("\n[1/3] Testing /burnout-risk endpoint...")
    try:
        response = requests.get(f"{base_url}/burnout-risk")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Risk Level: {data['risk_level']} (Score: {data['score']})")
            print(f"📋 Recommendations: {data['recommendations']}")
        else:
            print(f"❌ Failed to reach /burnout-risk. Status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")

    # 2. Verify Deadline Risk Endpoint
    print("\n[2/3] Testing /deadline-risk endpoint...")
    try:
        response = requests.get(f"{base_url}/deadline-risk")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Risk Level: {data['risk_level']} (Score: {data['score']})")
            print(f"📋 Recommendations: {data['recommendations']}")
        else:
            print(f"❌ Failed to reach /deadline-risk. Status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")

    # 3. Verify NLU Intent Recognition (Simulated)
    print("\n[3/3] NLU Intent Registration Check...")
    # This is a file check since NLU is usually integrated into a larger agent flow
    try:
        with open("src/services/ai/nluService.ts", "r") as f:
            content = f.read()
            if "workload_assessment" in content and "wellness_mitigation" in content:
                print("✅ Wellness intents found in nluService.ts")
            else:
                print("❌ Wellness intents missing from nluService.ts")
    except Exception as e:
        print(f"❌ Error checking NLU service file: {e}")

    print("\n✨ Verification Complete!")

if __name__ == "__main__":
    verify_burnout_features()
