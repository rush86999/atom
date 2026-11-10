"""Fresh-process email draft readback helper (test-only)."""
from __future__ import annotations

import json
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.canvas_email_routes import router as email_router
from core.auth import create_access_token
from core.database import get_db
from core.models import User


def main() -> int:
    db_url, canvas_id, user_id = sys.argv[1:4]
    engine = create_engine(f"sqlite:///{db_url}",
                           connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(email_router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with Session() as db:
        user = db.query(User).filter(User.id == user_id).one()
        token = create_access_token({"sub": user.id}, user=user)
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    response = client.get(f"/api/canvas/email/{canvas_id}")
    data = response.json() if response.status_code == 200 else {}
    payload = {
        "status": response.status_code,
        "draft": (data or {}).get("draft"),
    }
    print("RESULT_JSON:" + json.dumps(payload, sort_keys=True))
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
