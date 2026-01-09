import requests
import sys

# Read last execution ID
try:
    with open("last_execution_id.txt", "r") as f:
        execution_id = f.read().strip()
except FileNotFoundError:
    print("Error: last_execution_id.txt not found. Run create_execution.py first.")
    sys.exit(1)

url = f"http://localhost:8000/api/time-travel/workflows/{execution_id}/fork"
payload = {
    "step_id": "analyze_ticket" # Trying a known step ID for customer_support_automation
}

print(f"Sending POST to {url}...")
try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
