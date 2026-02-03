import json
import requests


def test_endpoints():
    base_url = "http://localhost:5058"
    endpoints_to_test = [
        "/healthz",
        "/api/accounts",
        "/auth/google/authorize",
        "/auth/dropbox/authorize",
        "/auth/asana/authorize",
        "/auth/trello/authorize",
        "/auth/notion/authorize",
        "/api/dropbox/files",
        "/api/google/drive/files",
        "/api/trello/boards",
        "/api/asana/workspaces",
        "/api/notion/databases",
        "/api/calendar/events",
        "/api/tasks",
        "/api/atom/message",
    ]

    print("🔍 Testing ATOM API Endpoints")
    print("=" * 50)

    for endpoint in endpoints_to_test:
        try:
            response = requests.get(
                f"{base_url}{endpoint}", timeout=5, allow_redirects=False
            )
            print(f"{endpoint:<30} -> Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)[:100]}...")
                except:
                    print(f"   Response: {response.text[:100]}...")
            elif response.status_code == 302:
                print(f"   Redirects to: {response.headers.get('Location', 'Unknown')}")

        except requests.exceptions.RequestException as e:
            print(f"{endpoint:<30} -> Error: {e}")


if __name__ == "__main__":
    test_endpoints()
