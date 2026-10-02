#!/usr/bin/env python3
"""Build a minimal D5 candidate: clean DB, admin user, one canvas via the app's API."""
import sys, os, json, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DB_DIR = tempfile.mkdtemp(prefix="d5_minimal_")
DB_PATH = os.path.join(DB_DIR, "d5.db")
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ATOM_TASK_LIFECYCLE_ENABLED"] = "1"
os.environ["CHAT_FINALIZATION_M1"] = "1"
os.environ["CHAT_FINALIZATION_M2"] = "1"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["ENABLE_INGESTION_SYNC"] = "false"

print(f"[d5] DB: {DB_PATH}")

from core.database import Base, engine
from core.models import (
    User, GoalObjective, GoalRun, ChatMessage, CanvasAudit,
    AgentExecution, AgentReasoningStep, AsyncContinuationClaim,
)
Base.metadata.create_all(bind=engine)
print("[d5] schema created")

from core.admin_bootstrap import ensure_admin_user
from core.database import get_db_session
ensure_admin_user()
with get_db_session() as db:
    user = db.query(User).filter(User.email == "admin@example.com").first()
    user_id = str(user.id)
print(f"[d5] admin user: {user_id}")

# Create the canvas through the app's own model path (not a raw SQL insert)
from core.models import Canvas, CanvasAudit
import uuid
canvas_id = str(uuid.uuid4())
canvas_body = "Hi Steve,<br><br>Quote validity: 99 days.<br><br>Regards,"
canvas_content = json.dumps({
    "to": "steve@example.com", "cc": "", "subject": "Machinery quote",
    "body": canvas_body,
})
with get_db_session() as db:
    db.add(Canvas(
        id=canvas_id, tenant_id="default", workspace_id="default",
        created_by=user_id, name="D5 test canvas", canvas_type="email",
        content=canvas_content, status="active",
    ))
    db.add(CanvasAudit(
        canvas_id=canvas_id, tenant_id="default", action_type="create",
        canvas_type="email", user_id=user_id,
        details_json={"content": json.loads(canvas_content)},
    ))
    db.commit()
print(f"[d5] canvas created: {canvas_id}")

# Verify through the canonical reader
import asyncio
from tools.canvas_crud_tool import read_canvas
read_result = asyncio.run(read_canvas(user_id, canvas_id))
assert read_result.get("success"), f"canvas read failed: {read_result}"
print(f"[d5] canvas readable via canonical reader")

fixture = {
    "db_path": DB_PATH, "db_dir": DB_DIR, "user_id": user_id,
    "canvas_id": canvas_id, "canvas_content": canvas_content,
    "flags": {"ATOM_TASK_LIFECYCLE_ENABLED": "1",
              "CHAT_FINALIZATION_M1": "1", "CHAT_FINALIZATION_M2": "1",
              "ENABLE_SCHEDULER": "false", "ENABLE_INGESTION_SYNC": "false"},
}
Path("/tmp/d5_minimal_fixture.json").write_text(json.dumps(fixture, indent=1))
print("[d5] READY — fixture at /tmp/d5_minimal_fixture.json")
