import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
WORKFLOW_ID = "verify-e2e-test-workflow-FINAL"
STEP_ID = "step-999"
LOG_FILE = "internal_log.txt"

def log(msg):
    print(msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

# Clear log
try:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")
except Exception:
    pass

def run_test():
    log(f"[-] Starting Verification for Workflow: {WORKFLOW_ID}")

    # 1. Trigger Test Step
    payload = {
        "service": "System",
        "action": "execute",
        "parameters": {"test": "final_verification"},
        "workflow_id": WORKFLOW_ID,
        "step_id": STEP_ID
    }
    
    # Try /workflows/test-step (as defined in workflow_automation_routes.py prefix)
    url_test = f"{BASE_URL}/workflows/test-step"
    log(f"[-] Sending POST {url_test}...")
    
    try:
        resp = requests.post(url_test, json=payload)
        if resp.status_code != 200:
            log(f"[!] Test Step Error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
        log(f"[+] Test Step Success! Duration: {resp.json().get('duration_ms')}ms")
    except Exception as e:
        log(f"[!] Test Step Execution Failed: {e}")
        return

    # 2. Wait for async DB write
    log("[-] Waiting 2s for analytics ingestion...")
    time.sleep(2)

    # 3. Check Logs
    # Backend Plugin prefixes with /api/v1
    # Analytics Router prefixes with /analytics
    # Full Path: /api/v1/analytics/workflows/{id}/logs
    url_logs = f"{BASE_URL}/api/v1/analytics/workflows/{WORKFLOW_ID}/logs"
    log(f"[-] Checking GET {url_logs}...")
    
    try:
        resp = requests.get(url_logs)
        if resp.status_code != 200:
            log(f"[!] Logs Error {resp.status_code}: {resp.text}")
            
            # Fallback check
            url_fallback = f"{BASE_URL}/analytics/workflows/{WORKFLOW_ID}/logs"
            log(f"[-] Retrying fallback {url_fallback}...")
            resp = requests.get(url_fallback)
            if resp.status_code != 200:
                 log(f"[!] Fallback Logs Error {resp.status_code}: {resp.text}")

        resp.raise_for_status()
        logs = resp.json()
        
        found = False
        for log_entry in logs:
            if log_entry.get('step_id') == STEP_ID:
                log("[+] Verified Log Entry Found!")
                log(f"    - ID: {log_entry['id']}")
                log(f"    - Status: {log_entry['status']}")
                log(f"    - Inputs: {json.dumps(log_entry.get('trigger_data'))}")
                log(f"    - Outputs: {json.dumps(log_entry.get('results'))}")
                found = True
                break
        
        if not found:
            log(f"[!] Log entry for {STEP_ID} NOT found in response.")
            log("Response Dump: " + json.dumps(logs[:2], indent=2)) # Show first 2
        else:
            log("\n[SUCCESS] Feature Verification Passed: End-to-End.")

    except Exception as e:
        log(f"[!] Fetch Logs Failed: {e}")

if __name__ == "__main__":
    run_test()
