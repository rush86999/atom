
import requests
import time
import sys

try:
    print("[-] POSTing test step...")
    res = requests.post(
        "http://127.0.0.1:8000/workflows/test-step", 
        json={
            "service": "System",
            "action": "execute",
            "workflow_id": "manual_verify_v2", 
            "step_id": "step1"
        }
    )
    print(f"[+] POST Status: {res.status_code}")
    if res.status_code != 200:
        print(f"[!] POST Failed: {res.text}")
        sys.exit(1)

    print("[-] Waiting for async log...")
    time.sleep(2)

    print("[-] GETting logs...")
    res_logs = requests.get("http://127.0.0.1:8000/api/v1/analytics/workflows/manual_verify_v2/logs")
    print(f"[+] GET Status: {res_logs.status_code}")
    
    logs = res_logs.json()
    print(f"[+] Logs found: {len(logs)}")
    if len(logs) > 0:
        print("[+] SUCCESS: Log entry found!")
        print(logs[0])
    else:
        print("[!] FAILURE: No logs returned.")
        sys.exit(1)

except Exception as e:
    print(f"[!] Exception: {e}")
    sys.exit(1)
