"""Standalone browser-acceptance server for durable assignments.

Uses the real assignment routes and the real executor on a scratch sqlite
database. The only substitution is the environment-gated controlled outbox
transport; no live provider is contacted.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCRATCH = Path(os.getenv(
    "ATOM_ASSIGNMENT_BROWSER_WORLD",
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "atom-assignment-browser-world"))

from core.assignment_launcher_guard import prepare_scratch_dir  # noqa: E402

SCRATCH = prepare_scratch_dir(
    SCRATCH,
    reset=os.getenv("ATOM_ASSIGNMENT_BROWSER_WORLD_RESET") == "1",
)
os.environ["ATOM_DATA_DIR"] = str(SCRATCH)
os.environ["ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT"] = "1"
os.environ["ATOM_ASSIGNMENT_OUTBOX"] = str(SCRATCH / "outbox.jsonl")
os.environ["ATOM_OFFICE_DIR"] = str(SCRATCH)
os.environ["ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS"] = "1"
os.environ["ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT"] = str(SCRATCH)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.assignment_executor import AssignmentExecutor  # noqa: E402
import core.assignment_controlled_transport  # noqa: E402,F401
from core.auth import get_current_user  # noqa: E402
from core.database import get_db  # noqa: E402
from core.goals.goal_run_service import GoalRunService  # noqa: E402
from core.goals.goal_service import GoalService  # noqa: E402
from core.models import (  # noqa: E402
    AgentRegistry, Base, GoalObjective, GoalRun, HITLAction,
    TaskOperationRecord, User,
)
from core.student_learning_service import deliver_teacher_lesson  # noqa: E402
from core.task_lifecycle import TaskLifecycle  # noqa: E402

SCRATCH = prepare_scratch_dir(
    SCRATCH,
    reset=os.getenv("ATOM_ASSIGNMENT_BROWSER_WORLD_RESET") == "1",
)
os.environ["ATOM_DATA_DIR"] = str(SCRATCH)
os.environ["ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT"] = "1"
os.environ["ATOM_ASSIGNMENT_OUTBOX"] = str(SCRATCH / "outbox.jsonl")

engine = create_engine(f"sqlite:///{SCRATCH}/atom.db")
for table in (User.__table__, AgentRegistry.__table__,
              GoalObjective.__table__, GoalRun.__table__,
              TaskOperationRecord.__table__, HITLAction.__table__):
    table.create(engine, checkfirst=True)
factory = sessionmaker(bind=engine, expire_on_commit=False)
db = factory()
admin = db.query(User).filter(User.id == "browser-admin").first()
if admin is None:
    admin = User(
        id="browser-admin", email="browser@example.com",
        hashed_password="x", first_name="Browser", last_name="Admin",
        role="admin", status="active", workspace_id="default",
        tenant_id="default", is_active=True)
    db.add(admin)
    db.commit()

import core.database as database_module  # noqa: E402
import core.intervention_service as intervention_module  # noqa: E402

database_module.get_db_session = factory
intervention_module.get_db_session = factory

runs = GoalRunService(
    workspace_id="default", tenant_id="default", session_factory=factory)
goals = GoalService(
    workspace_id="default", tenant_id="default", session_factory=factory)
lifecycle = TaskLifecycle(runs, goals)
executor = AssignmentExecutor(lifecycle)

import openpyxl  # noqa: E402
import docx  # noqa: E402

source_workbook = SCRATCH / "connected-records.xlsx"
workbook = openpyxl.Workbook()
sheet = workbook.active
sheet.title = "Records"
sheet.append(["Item", "Quantity", "Unit Price"])
sheet.append(["A-1", 2, 10])
sheet.append(["B-2", 3, 20])
workbook.save(source_workbook)

source_document = SCRATCH / "qualification.txt"
source_document.write_text(
    "Subject: record-2\nStatus: active\nQualification: Q-2\n")

agent = db.query(AgentRegistry).filter(
    AgentRegistry.name == "Browser Employee",
    AgentRegistry.workspace_id == "default",
).first()
if agent is None:
    agent = AgentRegistry(
        id=f"browser-agent-{uuid.uuid4().hex[:8]}",
        name="Browser Employee", category="operations",
        description="browser acceptance employee",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5, configuration={},
        capabilities=[], workspace_id="default", tenant_id="default",
    )
    db.add(agent)
    db.commit()
    deliver_teacher_lesson(
        db, agent.id, "Use the Arial document standard",
        topic="document standard", applies_to=["document"],
        format_spec={"font_name": "Arial", "font_size": 11},
        workspace_id="default",
    )
    deliver_teacher_lesson(
        db, agent.id, "Use the Georgia presentation standard",
        topic="presentation standard", applies_to=["presentation"],
        format_spec={"font_name": "Georgia", "font_size": 18},
        workspace_id="default",
    )

from api.assignment_routes import router  # noqa: E402

app = FastAPI(title="Assignment browser acceptance")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://127.0.0.1:3003",
                                   "http://localhost:3003"],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(router)
app.dependency_overrides[get_current_user] = lambda: admin
app.dependency_overrides[get_db] = lambda: db


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "agent_id": agent.id,
        "workbook": str(source_workbook),
        "document": str(source_document),
        "commercial_output": str(SCRATCH / "commercial.docx"),
        "eligibility_output": str(SCRATCH / "eligibility.pptx"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090, log_level="warning")
