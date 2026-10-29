"""Standalone browser-acceptance server for durable assignments.

Uses the real assignment routes and the real executor on a scratch sqlite
database. The only substitution is the environment-gated controlled outbox
transport; no live provider is contacted.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCRATCH = Path(os.getenv(
    "ATOM_ASSIGNMENT_BROWSER_WORLD",
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "atom-assignment-browser-world"))
shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["ATOM_DATA_DIR"] = str(SCRATCH)
os.environ["ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT"] = "1"
os.environ["ATOM_ASSIGNMENT_OUTBOX"] = str(SCRATCH / "outbox.jsonl")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.assignment_executor import AssignmentExecutor  # noqa: E402
import core.assignment_controlled_transport  # noqa: E402,F401
from core.assignment_plan import (  # noqa: E402
    new_assignment, new_deliverable, new_step, new_teaching_snapshot,
)
from core.auth import get_current_user  # noqa: E402
from core.database import get_db  # noqa: E402
from core.goals.goal_run_service import GoalRunService  # noqa: E402
from core.goals.goal_service import GoalService  # noqa: E402
from core.models import (  # noqa: E402
    Base, GoalObjective, GoalRun, HITLAction, TaskOperationRecord, User,
)
from core.task_lifecycle import TaskLifecycle  # noqa: E402

engine = create_engine(f"sqlite:///{SCRATCH}/atom.db")
for table in (User.__table__, GoalObjective.__table__, GoalRun.__table__,
              TaskOperationRecord.__table__, HITLAction.__table__):
    table.create(engine, checkfirst=True)
factory = sessionmaker(bind=engine, expire_on_commit=False)
db = factory()
admin = User(
    id="browser-admin", email="browser@example.com", hashed_password="x",
    first_name="Browser", last_name="Admin", role="admin", status="active",
    workspace_id="default", tenant_id="default", is_active=True)
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


def _make(correlation: str, objective: str, audience: str,
          document_font: str, decision: str) -> str:
    teaching = new_teaching_snapshot(
        revision=f"browser-{correlation}",
        output_requirements={"font_name": document_font, "font_size": 11},
        matched_context={"audience": audience},
        decision_schema=[{"id": decision}, {"id": "HOLD"}],
    )
    plan = new_assignment(
        objective=objective,
        employee_id=admin.id,
        workspace_id="default",
        tenant_id="default",
        teaching_snapshot=teaching,
        steps=[
            new_step(
                step_id="wait", title=f"Wait for {audience} reply",
                operation_type="retrieve",
                adapter="assignment.controlled_wait",
                inputs={"correlation_id": correlation,
                        "party": f"{audience} contact",
                        "detail": f"reply on {correlation}"},
                effect="read_only"),
            new_step(
                step_id="send", title=f"Send {audience} response",
                operation_type="outbound",
                adapter="assignment.controlled_outbox",
                depends_on=["wait"],
                inputs={"to": [f"{audience}@example.invalid"],
                        "subject": objective,
                        "body": f"Decision: {decision}",
                        "deliverable_id": f"del-{correlation}"},
                effect="external", approval_required=True,
                approval_purpose=f"Send the {audience} response"),
        ],
        deliverables=[
            new_deliverable(
                deliverable_id=f"del-{correlation}", kind="email",
                description=f"{audience} response", step_id="send"),
        ],
        authorized_actions=["retrieve", "outbound"],
    )
    record = executor.create_assignment(
        f"conv-{correlation}", objective, assignment=plan)
    asyncio.run(executor.execute(record["run_id"]))
    return record["run_id"]


run_a = _make("browser-A", "Browser commercial response", "customer",
              "Arial", "APPROVE")
run_b = _make("browser-B", "Browser eligibility package", "reviewer",
              "Times New Roman", "CLEAR")

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
    return {"ok": True, "runs": [run_a, run_b]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090, log_level="warning")
