"""Standalone browser-acceptance server for durable assignments.

Uses the real assignment routes and the real executor on a scratch sqlite
database. The only substitution is the environment-gated controlled outbox
transport; no live provider is contacted.
"""
from __future__ import annotations

import json
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

import csv  # noqa: E402
import io  # noqa: E402

# ---------------------------------------------------------------------------
# Controlled connected providers for the browser journey.
# The real registered actions run; only the provider services are fakes.
# ---------------------------------------------------------------------------
CONNECTED = {
    "bytes": (
        "sku,category,quantity,unit,pack,unit_price,currency,"
        "discount_percent\n"
        "A,A,2,each,1,100.00,USD,0\n"
        "B,B,3,each,1,50.00,USD,0\n"
    ).encode("utf-8"),
    "version": "v1",
    "calls": 0,
    "estimates": [],
    "drafts": [],
    "last_payload": None,
}


class _ControlledWorkDrive:
    async def get_file_metadata(self, user_id, file_id, workspace_id=None):
        return {"id": file_id, "name": "price-list.csv",
                "version": CONNECTED["version"],
                "size": len(CONNECTED["bytes"])}

    async def download_file(self, user_id, file_id, workspace_id=None):
        return CONNECTED["bytes"]

    async def get_access_token(self, user_id, workspace_id=None):
        return "controlled-token"


async def _controlled_workdrive_service(ids):
    return _ControlledWorkDrive()


class _ControlledBooks:
    async def _get_active_token(self, *args, **kwargs):
        return "controlled-token"

    async def get_estimates_page(self, token, org, page=1, per_page=200):
        return list(CONNECTED["estimates"]), {"has_more": False}

    async def create_estimate(self, token, org, data):
        CONNECTED["calls"] += 1
        CONNECTED["last_payload"] = data
        estimate = {
            "estimate_id": f"est-browser-{len(CONNECTED['estimates']) + 1}",
            "estimate_number": f"EST-B{len(CONNECTED['estimates']) + 1}",
            "customer_id": data["customer_id"],
            "reference_number": data["reference_number"],
            "date": data["date"],
            "currency_code": data["currency_code"],
            "total": data["total"],
            "sub_total": data["sub_total"],
            "tax_total": data["tax_total"],
            "line_items": data["line_items"],
        }
        CONNECTED["estimates"].append(estimate)
        return estimate

    async def get_estimate(self, token, org, estimate_id):
        return next(item for item in CONNECTED["estimates"]
                    if item["estimate_id"] == estimate_id)


async def _controlled_books_service(ids):
    return _ControlledBooks()


class _ControlledOutlook:
    def __init__(self):
        self.sent = False

    async def _get_access_token(self, user_id):
        return "controlled-token"

    async def create_draft_email(self, **kwargs):
        CONNECTED["drafts"].append({
            "subject": kwargs.get("subject"),
            "body": kwargs.get("body"),
            "to": kwargs.get("to_recipients"),
        })
        return {"id": f"draft-browser-{len(CONNECTED['drafts'])}",
                "subject": kwargs.get("subject")}

    async def send_email(self, *args, **kwargs):  # pragma: no cover
        self.sent = True
        raise AssertionError("controlled draft must not send")


import core.connected_actions as connected_actions  # noqa: E402
from core.action_registry import action_registry  # noqa: E402
import integrations.outlook_service as outlook_module  # noqa: E402

connected_actions._books_service = _controlled_books_service
connected_actions._workdrive_service = _controlled_workdrive_service
outlook_module.OutlookService = lambda *a, **k: _ControlledOutlook()
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

grant_parquet = datasets_dir / "grant-applications.parquet"
grant_frame = pd.DataFrame({
    "Application": ["G-1", "G-2", "G-3"],
    "Approved Amount": [1500.0, 2000.0, 750.0],
    "Status": ["approved", "approved", "pending"],
    "Region": ["North", "South", "North"],
    "__sheet_row": [2, 3, 4],
})
grant_frame.to_parquet(grant_parquet, index=False)
grant_entry = db.query(DatasetEntry).filter(
    DatasetEntry.dataset_name == "grant_applications").first()
if grant_entry is None:
    grant_entry = DatasetEntry(
        id="browser-grant-entry",
        workspace_id="default", tenant_id="default",
        created_by=admin.id, source_kind="file", source="onedrive",
        external_id="browser-grant-drive-1",
        file_name="grant-applications.xlsx", content_hash="c" * 40,
        entity_name="GRANT APPLICATIONS",
        dataset_name="grant_applications",
        parquet_path=str(grant_parquet), row_count=len(grant_frame),
        column_count=len(grant_frame.columns),
        columns_json={
            "columns": [
                {"name": column,
                 "samples": [value.item() if hasattr(value, "item") else value
                             for value in grant_frame[column].head(2).tolist()]}
                for column in grant_frame.columns
            ],
            "coverage": {
                "known": True, "source_row_count": len(grant_frame),
                "materialized_row_count": len(grant_frame),
                "truncated": False,
            },
        },
        status="active",
    )
    db.add(grant_entry)
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
        "hitl_assignment_approvals": db.query(HITLAction).filter(
            HITLAction.action_type == "assignment_approval").count(),
    }


@app.get("/_acceptance/outbox")
def acceptance_outbox():
    return {
        "ok": True,
        "lines": [json.loads(line) for line in _outbox_lines()],
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


from core.assignment_plan import new_step  # noqa: E402


@app.get("/_acceptance/connected/plan")
def acceptance_connected_plan(objective: str, ref: str):
    steps = [
        new_step(
            step_id="read", title="Read connected price bytes",
            operation_type="retrieve", adapter="action.registry",
            inputs={"action": "connected.workdrive.read_file",
                    "arguments": {"file_id": "price-file",
                                  "evidence_kind": "price_rows"}},
            effect="read_only"),
        new_step(
            step_id="map", title="Map parsed rows to quote lines",
            operation_type="calculate", adapter="quote.lines_from_rows",
            depends_on=["read"],
            inputs={
                "rows": {"$ref": "read.data.rows"},
                "columns": {
                    "item_id": "sku", "quantity": "quantity",
                    "unit": "unit", "pack_size": "pack",
                    "unit_price": "unit_price", "currency": "currency",
                    "description": "sku", "category": "category",
                    "discount": "discount_percent",
                },
                "defaults": {"price_basis": "contract"},
                "discount_mode": "percent",
                "discount_authority": "price-list:v1",
                "source_identity": {
                    "resource_id": {
                        "$ref": "read.data.read_receipt.resource_id"},
                    "version": {
                        "$ref": "read.data.read_receipt.version"},
                    "sha256": {
                        "$ref": "read.data.read_receipt.fields.sha256"},
                },
            },
            effect="local"),
        new_step(
            step_id="calculate", title="Calculate the quote",
            operation_type="calculate", adapter="quote.calculate",
            depends_on=["map"],
            inputs={
                "line_items": {"$ref": "map.line_items"},
                "currency": "USD", "freight": "20.00",
                "tax": {"basis": "none"},
                "discount_rules": [
                    {"lesson_id": "general-b", "revision": 1,
                     "name": "general B", "when": {"category": "B"},
                     "rate": "0.05"},
                    {"lesson_id": "licensed-b", "revision": 1,
                     "name": "licensed B",
                     "when": {"category": "B",
                              "qualification": "licensed"},
                     "rate": "0.10"},
                ],
                "rounding": "half_up", "scale": 2,
                "rounding_authority": "agreement:round-half-up-2dp",
                "source_evidence": [{
                    "resource_id": "price-file",
                    "source_version": "${read.data.read_receipt.version}",
                }],
            },
            effect="local"),
        new_step(
            step_id="email-draft", title="Prepare the quote email body",
            operation_type="present", adapter="email.draft",
            depends_on=["calculate"],
            inputs={"to": ["buyer@example.invalid"],
                    "subject": f"Quote {ref}",
                    "body": "Quoted total: ${calculate.value} USD"},
            effect="local"),
        new_step(
            step_id="prepare-lines", title="Prepare provider estimate lines",
            operation_type="calculate", adapter="quote.estimate_lines",
            depends_on=["calculate"],
            inputs={"rows": {"$ref": "calculate.rows"},
                    "account_map": {"A": "acct-1", "B": "acct-1"}},
            effect="local"),
        new_step(
            step_id="estimate", title="Create the verified estimate",
            operation_type="outbound", adapter="action.registry",
            depends_on=["prepare-lines"],
            inputs={
                "action": "connected.books.create_estimate",
                "arguments": {
                    "organization_id": "org-browser",
                    "estimate_data": {
                        "customer_id": "customer-1",
                        "reference_number": ref,
                        "date": "2026-11-01", "currency_code": "USD",
                        "total": "${calculate.value}",
                        "sub_total": "${calculate.value}",
                        "tax_total": "0.00",
                        "line_items": {"$ref": "prepare-lines.line_items"},
                    },
                    "authority_reference": "grant-browser-1",
                    "operation_id": f"op-browser-{ref}",
                },
            },
            effect="external", approval_required=True,
            approval_purpose="Create the estimate"),
        new_step(
            step_id="outlook-draft", title="Create the Outlook draft",
            operation_type="outbound", adapter="action.registry",
            depends_on=["estimate", "email-draft"],
            inputs={
                "action": "connected.outlook.create_draft",
                "arguments": {
                    "to": ["buyer@example.invalid"],
                    "subject": f"Quote {ref}",
                    "body": "Quoted total: ${calculate.value} USD",
                    "operation_id": f"op-draft-{ref}",
                },
            },
            effect="external", approval_required=True,
            approval_purpose="Create the Outlook draft"),
    ]
    return {"ok": True, "objective": objective, "steps": steps}


class ConnectedSourceRequest(BaseModel):
    content: str
    version: str = "v1"


@app.post("/_acceptance/connected/source")
def acceptance_connected_source(body: ConnectedSourceRequest):
    CONNECTED["bytes"] = body.content.encode("utf-8")
    CONNECTED["version"] = body.version
    return {"ok": True, "version": body.version,
            "bytes": len(CONNECTED["bytes"])}


@app.get("/_acceptance/connected/run/{run_id}")
def acceptance_connected_run(run_id: str):
    return {"ok": True, "assignment": lifecycle.get_assignment(run_id)}


@app.get("/_acceptance/connected/state")
def acceptance_connected_state():
    return {
        "ok": True,
        "version": CONNECTED["version"],
        "bytes": len(CONNECTED["bytes"]),
        "calls": CONNECTED["calls"],
        "estimates": [{
            "estimate_id": item["estimate_id"],
            "reference_number": item["reference_number"],
            "total": item["total"],
        } for item in CONNECTED["estimates"]],
        "drafts": list(CONNECTED["drafts"]),
        "last_payload": CONNECTED["last_payload"],
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
        "grant_dataset": "grant_applications",
        "grant_sheet": "GRANT APPLICATIONS",
        "grant_output": str(SCRATCH / "grant-summary.pptx"),
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
            {
                "objective": "Summarize the grant applications",
                "scope": "grant applications",
                "kind": "presentation",
                "recipient": "grants@example.invalid",
                "expected": "4250.00",
                "source": "grant-applications.xlsx",
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app, host="127.0.0.1",
        port=int(os.getenv("ATOM_ASSIGNMENT_BROWSER_PORT", "8090")),
        log_level="warning")
