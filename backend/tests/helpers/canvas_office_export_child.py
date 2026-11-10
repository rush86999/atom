"""Fresh-process Canvas office export readback helper (test-only)."""
from __future__ import annotations

import hashlib
import json
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.canvas_routes import router
from core.auth import get_current_user
from core.database import get_db
from core.deployment_audience import require_pilot_user
from core.models import User


def main() -> int:
    db_url, canvas_id, audit_id, user_id, tenant_id, workspace_id, fmt = (
        sys.argv[1:8])
    engine = create_engine(
        db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    async def override_user():
        db = Session()
        try:
            return db.query(User).filter(User.id == user_id).one()
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[require_pilot_user] = lambda: None
    client = TestClient(app)
    response = client.get(
        f"/api/canvas/{canvas_id}/export/office",
        params={"format": fmt, "expected_audit_id": audit_id})
    payload = {
        "status": response.status_code,
        "format": fmt,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "length": len(response.content),
        "etag": response.headers.get("etag"),
        "source_audit_id": response.headers.get("x-atom-source-audit-id"),
        "model_calls": False,
    }
    if response.status_code == 200 and fmt == "pptx":
        import io

        from pptx import Presentation

        deck = Presentation(io.BytesIO(response.content))
        slide_data = []
        for slide in deck.slides:
            title_shape = slide.shapes.title
            body = []
            tables = []
            for shape in slide.shapes:
                if title_shape is not None and shape == title_shape:
                    continue
                if getattr(shape, "has_table", False):
                    tables.append([[cell.text for cell in row.cells]
                                   for row in shape.table.rows])
                elif getattr(shape, "has_text_frame", False):
                    body.append(shape.text_frame.text)
            slide_data.append({
                "title": title_shape.text if title_shape is not None else "",
                "body": "\n".join(body),
                "tables": tables,
                "notes": (
                    slide.notes_slide.notes_text_frame.text
                    if slide.has_notes_slide else ""),
            })
        payload["slide_count"] = len(deck.slides)
        payload["slides"] = slide_data
    print("RESULT_JSON:" + json.dumps(payload, sort_keys=True))
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
