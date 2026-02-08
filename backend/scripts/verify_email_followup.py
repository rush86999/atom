from datetime import datetime, timedelta
import json
import requests


def verify_email_followup():
    base_url = "http://localhost:8000/api/v1/analytics"
    print("🚀 Starting Email Follow-up Verification...")

    # 1. Verify Endpoint
    print("\n[1/2] Testing /email-followups endpoint...")
    try:
        response = requests.get(f"{base_url}/email-followups")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Found {len(data)} follow-up candidates.")
            for cand in data:
                print(f"   - Candidate: {cand['recipient']} | Subject: {cand['subject']}")
                print(f"   - Days since sent: {cand['days_since_sent']}")
        else:
            print(f"❌ Failed to reach /email-followups. Status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")

    # 2. Verify Template Registration
    print("\n[2/2] Checking Workflow Template registration...")
    try:
        with open("backend/core/workflow_template_system.py", "r") as f:
            content = f.read()
            if "email_followup" in content and "_create_email_followup_template" in content:
                print("✅ Email follow-up template found in workflow_template_system.py")
            else:
                print("❌ Email follow-up template missing from workflow_template_system.py")
    except Exception as e:
        print(f"❌ Error checking workflow file: {e}")

    print("\n✨ Verification Complete!")

if __name__ == "__main__":
    verify_email_followup()
