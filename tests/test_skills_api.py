import urllib.request
import json
import urllib.error

url = 'http://127.0.0.1:8000/api/skills/list'

try:
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req) as response:
        result = response.read()
        print(f"Status: {response.status}")
        print(json.dumps(json.loads(result), indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode())
except urllib.error.URLError as e:
    print(f"URL Error: {e.reason}")
