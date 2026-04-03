import urllib.request
import json
import uuid

url = "http://localhost:8000/api/v1/employee/task"
data = {
    "workspace_id": str(uuid.uuid4()),
    "command": "test",
    "current_state": {}
}

req = urllib.request.Request(url, method="OPTIONS")
req.add_header("Origin", "http://localhost:3000")
req.add_header("Access-Control-Request-Method", "POST")
req.add_header("Access-Control-Request-Headers", "content-type")

try:
    with urllib.request.urlopen(req) as response:
        print("OPTIONS STATUS:", response.status)
        print("OPTIONS HEADERS:", response.headers)
except Exception as e:
    print("OPTIONS ERROR:", str(e))
    try:
        print("OPTIONS ERROR HEADERS:", e.headers)
    except:
        pass

req_post = urllib.request.Request(url, method="POST")
req_post.add_header("Content-Type", "application/json")
req_post.add_header("Origin", "http://localhost:3000")

try:
    with urllib.request.urlopen(req_post, data=json.dumps(data).encode("utf-8")) as response:
        print("POST STATUS:", response.status)
        print("POST RESPONSE:", response.read().decode())
except Exception as e:
    print("POST ERROR:", str(e))
    try:
        print("POST ERROR BODY:", e.read().decode())
    except:
        pass

