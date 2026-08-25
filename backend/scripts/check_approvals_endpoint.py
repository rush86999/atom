"""Manual checker: GET /api/agents/approvals/pending (the GlobalChatWidget probe).

Verifies the endpoint returns 200 + JSON list for a user with
Permission.AGENT_MANAGE, so the frontend never hits the plain-text
"Internal Server Error" body that breaks axios JSON parsing
("Unexpected token 'I', \"Internal S\"... is not valid JSON").

Run from repo root:  python backend/scripts/check_approvals_endpoint.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient

from main_api_app import app
from core.auth import create_access_token
from core.database import SessionLocal
from core.models import User

db = SessionLocal()
try:
    u = db.query(User).filter(User.email == "admin@example.com").first()
finally:
    db.close()
if u is None:
    print("FAIL: admin@example.com not found in DB")
    sys.exit(1)

token = create_access_token({"sub": u.id, "user_id": u.id, "role": u.role})
print(f"token minted for {u.email} role={u.role} status={u.status}")

client = TestClient(app, raise_server_exceptions=True)
r = client.get("/api/agents/approvals/pending", headers={"Authorization": f"Bearer {token}"})
print(f"STATUS {r.status_code}")
print(f"BODY[:300] {r.text[:300]}")

if r.status_code == 200:
    try:
        data = r.json()
        assert isinstance(data, list)
        print(f"OK: endpoint returned JSON list with {len(data)} pending approval(s)")
        sys.exit(0)
    except Exception as e:  # noqa: BLE001 - checker script, surface for diagnosis
        print(f"FAIL: body is not a JSON list: {e}")
        sys.exit(1)
else:
    print("FAIL: endpoint did not return 200 (stale server / wrong DB / missing table)")
    sys.exit(1)
