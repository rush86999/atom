import json
import time
import requests

url = "http://localhost:8000/api/v1/workflow-ui/execute"
payload = {
    "workflow_id": "customer_support_automation",
    "input": {"text": "I have a billing issue"}
}

try:
    for i in range(10):
        try:
            print(f"Sending POST to {url} (Attempt {i+1})...")
            response = requests.post(url, json=payload)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                exec_id = data.get('execution_id')
                print(f"Execution ID: {exec_id}")
                with open("last_execution_id.txt", "w") as f:
                    f.write(exec_id)
                break
            else:
                print(f"Error: {response.text}")
        except requests.exceptions.ConnectionError:
            print("Server not ready, retrying in 2s...")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"Request failed: {e}")
            break

except Exception as e:
    print(f"Script failed: {e}")
