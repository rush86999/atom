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
    AgentRegistry, Base, DatasetEntry, GoalObjective, GoalRun, HITLAction,
    IntegrationToken, TaskOperationRecord, Tenant, User, Workspace,
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
              TaskOperationRecord.__table__, HITLAction.__table__,
              Tenant.__table__, Workspace.__table__,
              DatasetEntry.__table__, IntegrationToken.__table__):
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

# A real scoped connected catalog entry backed by a real materialized Parquet
# frame. This is the guided-discovery path; it is not an internal fixture path.
import pandas as pd  # noqa: E402

datasets_dir = SCRATCH / "sheet_datasets"
datasets_dir.mkdir(parents=True, exist_ok=True)
scotch_parquet = datasets_dir / "scotch-parts.parquet"
scotch_frame = pd.DataFrame({
    "Item Number": ["SC-1", "SC-2", "SC-3"],
    "Description": ["Scotch A", "Scotch B", "Scotch C"],
    "Quantity": [2, 3, 1],
    "Unit Price": [10.0, 20.0, 5.0],
    "Total": [20.0, 60.0, 5.0],
    "Currency": ["USD", "USD", "USD"],
    "__sheet_row": [2, 3, 4],
})
scotch_frame.to_parquet(scotch_parquet, index=False)
scotch_entry = db.query(DatasetEntry).filter(
    DatasetEntry.dataset_name == "scotch_parts_price_list").first()
if scotch_entry is None:
    scotch_entry = DatasetEntry(
        id="browser-scotch-entry",
        workspace_id="default", tenant_id="default",
        created_by=admin.id, source_kind="file", source="onedrive",
        external_id="browser-scotch-drive-1",
        file_name="scotch-parts.xlsx", content_hash="a" * 40,
        entity_name="US$ SCOTCH PARTS",
        dataset_name="scotch_parts_price_list",
        parquet_path=str(scotch_parquet), row_count=len(scotch_frame),
        column_count=len(scotch_frame.columns),
        columns_json={
            "columns": [
                {"name": column,
                 "samples": [value.item() if hasattr(value, "item") else value
                             for value in scotch_frame[column].head(2).tolist()]}
                for column in scotch_frame.columns
            ],
            "coverage": {
                "known": True, "source_row_count": len(scotch_frame),
                "materialized_row_count": len(scotch_frame),
                "truncated": False,
            },
        },
        status="active",
    )
    db.add(scotch_entry)
    db.commit()
if db.query(IntegrationToken).filter(
        IntegrationToken.user_id == admin.id,
        IntegrationToken.provider == "onedrive").first() is None:
    db.add(IntegrationToken(
        id="browser-scotch-token", tenant_id="default",
        user_id=admin.id, workspace_id="default", provider="onedrive",
        access_token="browser-acceptance-not-a-secret", status="active"))
    db.commit()

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
    # Two confirmed mappings for the same concept/sheet/version family. The
    # current dataset version (a*40) binds the first; the second names an
    # alternate version and is visible but not correctable. This is the
    # ambiguous-identity surface the browser journey must disambiguate.
    for label, version in (
        ("Use the Total field for the current price list", "a" * 40),
        ("Use the Total field for the alternate price list", "b" * 40),
    ):
        deliver_teacher_lesson(
            db, agent.id, label, topic="field mapping",
            applies_to=["document"],
            format_spec={"font_name": "Arial", "font_size": 11},
            context={"field_mappings": [{
                "concept": "Total", "sheet": "US$ SCOTCH PARTS",
                "column": "Total", "unit": "USD",
                "unit_authority": "source_evidence",
                "required_unit": "USD", "source_unit": "USD",
                "source_unit_column": "Currency",
                "source_version": version, "revision": 1,
            }]},
            workspace_id="default",
        )

from api.assignment_routes import router  # noqa: E402
from pydantic import BaseModel  # noqa: E402

app = FastAPI(title="Assignment browser acceptance")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://127.0.0.1:3003",
                                   "http://localhost:3003",
                                   "http://127.0.0.1:3004",
                                   "http://localhost:3004"],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(router)
app.dependency_overrides[get_current_user] = lambda: admin
app.dependency_overrides[get_db] = lambda: db


class TeachMappingRequest(BaseModel):
    concept: str = "Total"
    sheet: str = "US$ SCOTCH PARTS"
    column: str = "Total"
    source_version: str = "a" * 40
    revision: int = 1
    unit: str = "USD"
    unit_authority: str = "source_evidence"
    required_unit: str = "USD"
    source_unit: str = "USD"
    source_unit_column: str = "Currency"


class SourceVersionRequest(BaseModel):
    dataset_name: str = "scotch_parts_price_list"
    content_hash: str


def _outbox_lines():
    outbox = SCRATCH / "outbox.jsonl"
    if not outbox.exists():
        return []
    return [
        line for line in outbox.read_text().splitlines() if line.strip()
    ]


@app.get("/_acceptance/state")
def acceptance_state():
    entry = db.query(DatasetEntry).filter(
        DatasetEntry.dataset_name == "scotch_parts_price_list").first()
    return {
        "ok": True,
        "pid": os.getpid(),
        "world": str(SCRATCH),
        "agent_id": agent.id,
        "dataset_name": entry.dataset_name if entry else None,
        "dataset_version": entry.content_hash if entry else None,
        "outbox_path": str(SCRATCH / "outbox.jsonl"),
        "outbox_lines": len(_outbox_lines()),
    }


@app.post("/_acceptance/source-version")
def acceptance_set_source_version(body: SourceVersionRequest):
    entry = db.query(DatasetEntry).filter(
        DatasetEntry.dataset_name == body.dataset_name).first()
    if entry is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="dataset not found")
    entry.content_hash = body.content_hash
    db.commit()
    db.expire_all()
    return {
        "ok": True,
        "dataset_name": entry.dataset_name,
        "content_hash": entry.content_hash,
    }


@app.post("/_acceptance/teach-mapping")
def acceptance_teach_mapping(body: TeachMappingRequest):
    """Setup-only: append one mapping lesson and return its entry id."""
    result = deliver_teacher_lesson(
        db, agent.id,
        f"Use the {body.concept} field from {body.column} "
        f"({body.source_version[-8:]})",
        topic="field mapping", applies_to=["document"],
        format_spec={"font_name": "Arial", "font_size": 11},
        context={"field_mappings": [{
            "concept": body.concept, "sheet": body.sheet,
            "column": body.column, "unit": body.unit,
            "unit_authority": body.unit_authority,
            "required_unit": body.required_unit,
            "source_unit": body.source_unit,
            "source_unit_column": body.source_unit_column,
            "source_version": body.source_version,
            "revision": body.revision,
        }]},
        workspace_id="default",
    )
    db.expire_all()
    return {
        "ok": result.get("status") == "ok",
        "status": result.get("status"),
        "entry": result.get("entry"),
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "agent_id": agent.id,
        "workbook": str(source_workbook),
        "document": str(source_document),
        "commercial_output": str(SCRATCH / "commercial.docx"),
        "eligibility_output": str(SCRATCH / "eligibility.pptx"),
        "outbox": str(SCRATCH / "outbox.jsonl"),
        "guided": [
            {
                "objective": "Sum the total for the scotch parts price list",
                "scope": "scotch parts price list",
                "kind": "document",
                "recipient": "browser-guided@example.invalid",
                "expected": "85.00",
                "source": "scotch-parts.xlsx",
            },
            {
                "objective": "Count the records in the scotch parts price list",
                "scope": "scotch parts price list",
                "kind": "presentation",
                "recipient": "",
                "expected": "3",
                "source": "scotch-parts.xlsx",
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app, host="127.0.0.1",
        port=int(os.getenv("ATOM_ASSIGNMENT_BROWSER_PORT", "8090")),
        log_level="warning")
