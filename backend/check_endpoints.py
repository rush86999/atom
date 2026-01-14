import requests

def check(url):
    try:
        r = requests.get(url, allow_redirects=False)
        print(f"GET {url} -> {r.status_code}")
        if r.status_code in [301, 302, 307, 308]:
            print(f"  Location: {r.headers.get('Location')}")
    except Exception as e:
        print(f"GET {url} -> ERROR: {e}")

print("Checking backend directly...")
check("http://127.0.0.1:8000/api/agents")
check("http://127.0.0.1:8000/api/agents/")
check("http://localhost:8000/api/agents")
check("http://localhost:8000/api/agents/")
