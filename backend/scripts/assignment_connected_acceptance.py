"""Real connected guided-start acceptance for durable assignments.

This is the production-boundary control:

    authenticated objective -> real scoped catalog entry -> real materialized
    Parquet rows -> applicable teaching -> validated plan -> grounded saved
    document/presentation -> controlled approval/outbox -> durable reopen.

No catalog function, Parquet reader or resource resolver is mocked. The only
controlled substitutions are an isolated active integration-token row (a
plain non-secret string) and the environment-gated local outbox transport.
No provider is contacted.
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
    "ATOM_ASSIGNMENT_ACCEPTANCE_DIR",
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "atom-connected-acceptance",
))
RESET = os.getenv("ATOM_ASSIGNMENT_ACCEPTANCE_RESET") == "1"
from core.assignment_launcher_guard import prepare_scratch_dir  # noqa: E402

SCRATCH = prepare_scratch_dir(SCRATCH, reset=RESET)
os.environ["ATOM_DATA_DIR"] = str(SCRATCH)
os.environ["ATOM_OFFICE_DIR"] = str(SCRATCH / "office")
os.environ["ATOM_ASSIGNMENT_OUTPUT_DIR"] = str(SCRATCH / "outputs")
os.environ["ATOM_ASSIGNMENT_OUTBOX"] = str(SCRATCH / "outbox.jsonl")
os.environ["ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT"] = "1"
os.environ["ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS"] = "0"
os.environ["TESTING"] = "1"

import docx  # noqa: E402
import pandas as pd  # noqa: E402
import pptx  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.assignment_executor import AssignmentExecutor  # noqa: E402
import core.assignment_controlled_transport  # noqa: E402,F401
from core.auth import get_current_user  # noqa: E402
from core.database import get_db  # noqa: E402
from core.goals.goal_run_service import GoalRunService  # noqa: E402
from core.goals.goal_service import GoalService  # noqa: E402
from core.models import (  # noqa: E402
    AgentRegistry, Base, DatasetEntry, HITLAction, IntegrationToken, User,
)
from core.student_learning_service import deliver_teacher_lesson  # noqa: E402
from core.task_lifecycle import TaskLifecycle  # noqa: E402

ENGINE = create_engine(f"sqlite:///{SCRATCH}/acceptance.db")
Base.metadata.create_all(ENGINE)
FACTORY = sessionmaker(bind=ENGINE, expire_on_commit=False)
import core.database as database_module  # noqa: E402
import core.intervention_service as intervention_module  # noqa: E402

database_module.get_db_session = FACTORY
intervention_module.get_db_session = FACTORY

DB = FACTORY()
USER = DB.query(User).filter(User.id == "acceptance-user").first()
if USER is None:
    USER = User(
        id="acceptance-user", email="acceptance@example.invalid",
        hashed_password="x", first_name="Acceptance", last_name="User",
        role="admin", status="active", workspace_id="acceptance-ws",
        tenant_id="acceptance-tenant", is_active=True)
    DB.add(USER)
    DB.commit()

AGENT = DB.query(AgentRegistry).filter(
    AgentRegistry.name == "Connected Acceptance Employee").first()
if AGENT is None:
    AGENT = AgentRegistry(
        id=f"acceptance-agent-{uuid.uuid4().hex[:8]}",
        name="Connected Acceptance Employee", category="operations",
        description="real connected acceptance", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration={}, capabilities=[], workspace_id=USER.workspace_id,
        tenant_id=USER.tenant_id)
    DB.add(AGENT)
    DB.commit()
    deliver_teacher_lesson(
        DB, AGENT.id, "Use the approved document standard",
        topic="document standard", applies_to=["document"],
        format_spec={"font_name": "Times New Roman", "font_size": 11},
        context={}, workspace_id=USER.workspace_id)
    deliver_teacher_lesson(
        DB, AGENT.id, "Use the approved presentation standard",
        topic="presentation standard", applies_to=["presentation"],
        format_spec={"font_name": "Georgia", "font_size": 18},
        context={}, workspace_id=USER.workspace_id)

DATASETS = SCRATCH / "sheet_datasets"
DATASETS.mkdir(parents=True, exist_ok=True)
PARQUET = DATASETS / "scotch-parts.parquet"
FRAME = pd.DataFrame({
    "Item Number": ["SC-1", "SC-2", "SC-3"],
    "Description": ["Scotch A", "Scotch B", "Scotch C"],
    "Quantity": [2, 3, 1],
    "Unit Price": [10.0, 20.0, 5.0],
    "Total": [20.0, 60.0, 5.0],
    "Currency": ["USD", "USD", "USD"],
    "__sheet_row": [2, 3, 4],
})
FRAME.to_parquet(PARQUET, index=False)
if DB.query(DatasetEntry).filter(
        DatasetEntry.dataset_name == "scotch_parts_price_list").first() is None:
    DB.add(DatasetEntry(
        id="acceptance-scotch-entry",
        workspace_id=USER.workspace_id, tenant_id=USER.tenant_id,
        created_by=USER.id, source_kind="file", source="onedrive",
        external_id="acceptance-scotch-drive-1",
        file_name="scotch-parts.xlsx", content_hash="a" * 40,
        entity_name="US$ SCOTCH PARTS",
        dataset_name="scotch_parts_price_list",
        parquet_path=str(PARQUET), row_count=len(FRAME),
        column_count=len(FRAME.columns),
        columns_json={
            "columns": [
                {"name": column,
                 "samples": [value.item() if hasattr(value, "item") else value
                             for value in FRAME[column].head(2).tolist()]}
                for column in FRAME.columns
            ],
            "coverage": {
                "known": True, "source_row_count": len(FRAME),
                "materialized_row_count": len(FRAME), "truncated": False,
            },
        },
        status="active",
    ))
    DB.commit()
if DB.query(IntegrationToken).filter(
        IntegrationToken.user_id == USER.id,
        IntegrationToken.provider == "onedrive").first() is None:
    DB.add(IntegrationToken(
        id="acceptance-token", tenant_id=USER.tenant_id, user_id=USER.id,
        workspace_id=USER.workspace_id, provider="onedrive",
        access_token="acceptance-not-a-secret", status="active"))
    DB.commit()

RUNS = GoalRunService(
    workspace_id=USER.workspace_id, tenant_id=USER.tenant_id,
    session_factory=FACTORY)
GOALS = GoalService(
    workspace_id=USER.workspace_id, tenant_id=USER.tenant_id,
    session_factory=FACTORY)
LIFECYCLE = TaskLifecycle(RUNS, GOALS)
EXECUTOR = AssignmentExecutor(LIFECYCLE)

from api.assignment_routes import router  # noqa: E402

APP = FastAPI()
APP.include_router(router)
APP.dependency_overrides[get_current_user] = lambda: USER
APP.dependency_overrides[get_db] = lambda: DB
CLIENT = TestClient(APP)


def _extract_text(kind: str, path: str) -> str:
    if kind == "document":
        document = docx.Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(part for part in parts if part)
    presentation = pptx.Presentation(path)
    return "\n".join(
        shape.text for slide in presentation.slides
        for shape in slide.shapes if getattr(shape, "text", ""))


def _run_objective(objective: str, *, kind: str, recipient: str) -> dict:
    response = CLIENT.post("/api/assignments", json={
        "objective": objective,
        "agent_id": AGENT.id,
        "discover": True,
        "source_scope": {"query": "scotch parts price list"},
        "deliverables": [{
            "kind": kind,
            "description": objective,
        }],
        "outbound": ({
            "to": [recipient],
            "subject": objective,
        } if recipient else None),
        "transport": "controlled",
    })
    if response.status_code != 200:
        raise SystemExit(f"start failed: {response.status_code} {response.text}")
    body = response.json()
    run_id = body["run_id"]
    internal = LIFECYCLE.get_assignment(run_id)
    source_step = next(step for step in internal["steps"]
                       if step["step_id"] == "source-1")
    binding = source_step["inputs"]["resource_binding"]
    assert "path" not in binding, binding
    assert "path" not in source_step["inputs"], source_step["inputs"]
    source_result = source_step.get("result") or {}
    deliverable = next(item for item in body["assignment"]["assignment"][
        "deliverables"] if item["artifact_path"])
    text = _extract_text(kind, deliverable["artifact_path"])
    record = {
        "objective": objective,
        "kind": kind,
        "start_status": body["assignment"]["assignment"]["status"],
        "plan_revision": body["assignment"]["assignment"]["plan_revision"],
        "teaching_revision": body["teaching_revision"],
        "source_adapter": source_step["adapter"],
        "resource_binding": binding,
        "operation": source_result.get("operation"),
        "measure": source_result.get("measure"),
        "value": source_result.get("value"),
        "unit": source_result.get("unit"),
        "subtotals": source_result.get("subtotals"),
        "selected_count": source_result.get("selected_count"),
        "rows": source_result.get("rows"),
        "source": source_result.get("source"),
        "artifact_path": deliverable["artifact_path"],
        "artifact_sha256": deliverable["sha256"],
        "artifact_text": text,
    }
    if recipient:
        action = DB.query(HITLAction).filter(
            HITLAction.action_type == "assignment_approval",
        ).order_by(HITLAction.created_at.desc()).first()
        assert action is not None
        approved = CLIENT.post(
            f"/api/assignments/{run_id}/approve/send", json={})
        assert approved.status_code == 200, approved.text
        record["approved_status"] = (
            approved.json()["assignment"]["assignment"]["status"])
        outbox = Path(os.environ["ATOM_ASSIGNMENT_OUTBOX"])
        record["outbox"] = [
            json.loads(line) for line in outbox.read_text().splitlines()
            if line.strip()
        ]
    return record


SUM_RECORD = _run_objective(
    "Sum the total for the scotch parts price list",
    kind="document",
    recipient="acceptance-reviewer@example.invalid",
)
COUNT_RECORD = _run_objective(
    "Count the records in the scotch parts price list",
    kind="presentation",
    recipient="",
)

# Rebuild from durable state only.
REOPENED = AssignmentExecutor(TaskLifecycle(
    GoalRunService(
        workspace_id=USER.workspace_id, tenant_id=USER.tenant_id,
        session_factory=FACTORY),
    GoalService(
        workspace_id=USER.workspace_id, tenant_id=USER.tenant_id,
        session_factory=FACTORY),
))
REOPEN_STATUS = {}
for record in (SUM_RECORD, COUNT_RECORD):
    summaries = RUNS.list_runs(include_terminal=True, limit=100)
    match = next((
        row for row in summaries
        if (row.get("parameters") or {}).get("objective") == record["objective"]
    ), None)
    if match is None:
        # Goal run parameters are not part of this acceptance's assertion;
        # resolve by the stored assignment projection instead.
        match = next(
            row for row in summaries
            if (LIFECYCLE.get_assignment(row["id"]) or {}).get("objective")
            == record["objective"])
    status = REOPENED.status(match["id"])
    REOPEN_STATUS[record["objective"]] = {
        "status": status["assignment"]["status"],
        "deliverables": [
            item for item in status["assignment"]["deliverables"]
            if item.get("artifact_path")
        ],
    }

assert SUM_RECORD["value"] == "85.00"
assert SUM_RECORD["operation"] == "sum"
assert SUM_RECORD["measure"] == "Total"
assert [row["row"] for row in SUM_RECORD["rows"]] == [2, 3, 4]
assert "85.00" in SUM_RECORD["artifact_text"]
assert "scotch-parts.xlsx" in SUM_RECORD["artifact_text"]
assert SUM_RECORD["approved_status"] == "completed"
assert any("85.00" in str(item.get("body")) for item in SUM_RECORD["outbox"])
assert COUNT_RECORD["value"] == "3"
assert COUNT_RECORD["operation"] == "count"
assert "3" in COUNT_RECORD["artifact_text"]
assert all(item["status"] == "completed"
           for item in REOPEN_STATUS.values())

EVIDENCE = {
    "slice": "connected-guided-start",
    "scratch": str(SCRATCH),
    "source": "real DatasetEntry -> real Parquet -> real resolver/reader",
    "internal_fixture_paths": False,
    "provider_contacted": False,
    "sum": SUM_RECORD,
    "count": COUNT_RECORD,
    "reopened": REOPEN_STATUS,
}
target = Path(os.getenv(
    "ATOM_ASSIGNMENT_ACCEPTANCE_EVIDENCE",
    str(SCRATCH / "connected_acceptance.json")))
target.parent.mkdir(parents=True, exist_ok=True)
import shutil  # noqa: E402

for key, record in (("sum", SUM_RECORD), ("count", COUNT_RECORD)):
    source_artifact = Path(record["artifact_path"])
    stored = target.parent / f"{key}-artifact{source_artifact.suffix}"
    shutil.copy2(source_artifact, stored)
    EVIDENCE[key]["stored_artifact"] = str(stored)
target.write_text(json.dumps(EVIDENCE, indent=2, default=str))
print(json.dumps({
    "evidence": str(target),
    "scratch": str(SCRATCH),
    "sum_value": SUM_RECORD["value"],
    "count_value": COUNT_RECORD["value"],
    "reopened": {key: value["status"]
                 for key, value in REOPEN_STATUS.items()},
}, indent=2))
