"""A calculation over several accepted sources totals ALL of them.

The 2026-11-13 full-population workbook (24 sheets, 20 x 25 data rows)
reported ``completed`` while serving 1,758.00 — the first data sheet — as the
grand total of a 20-source assignment. The other 19 sources were merely read,
so the deliverable looked answered and was silently partial.

These tests lock the whole-scope aggregate (one dataset.aggregate step over
every accepted binding), its per-sheet evidence, and the preserved
single-source / explicitly-indexed behaviour.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import docx
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.assignment_executor import AssignmentExecutor
from core.assignment_planner import plan_assignment
from core.assignment_resources import resolve_assignment_source
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import (
    Base,
    DatasetEntry,
    GoalObjective,
    GoalRun,
    IntegrationToken,
    TaskOperationRecord,
    User,
)
from core.task_lifecycle import TaskLifecycle

WORKSPACE = "ws-a"
TENANT = "t1"
USER = "u1"
FILE_NAME = "full-population.xlsx"
WORKBOOK_HASH = hashlib.sha1(b"full-population-workbook").hexdigest()


def _sheet_frame(sheet: str, values) -> pd.DataFrame:
    return pd.DataFrame({
        "Item": [f"{sheet}-{index + 1}" for index in range(len(values))],
        "Total": [float(value) for value in values],
        "Currency": ["USD"] * len(values),
        "__sheet_row": list(range(2, len(values) + 2)),
    })


def _planner_source(tmp_path: Path, sheet: str) -> dict:
    """A resolved-source shape for planner-only assertions (never read)."""
    path = tmp_path / f"{sheet.lower()}.parquet"
    _sheet_frame(sheet, [1.0]).to_parquet(path, index=False)
    return {
        "kind": "workbook",
        "representation": "parquet_frame",
        "path": str(path),
        "resource_id": f"fixture:{path.name}",
        "dataset_name": f"{sheet.lower()}_dataset",
        "external_id": f"sha1:{WORKBOOK_HASH}",
        "original_file_name": FILE_NAME,
        "source": "onedrive",
        "source_kind": "file",
        "source_version": WORKBOOK_HASH,
        "sheet": sheet,
        "columns": ["Item", "Total", "Currency", "__sheet_row"],
        "numeric_columns": ["Total"],
        "row_count": 1,
        "coverage": {"known": True, "truncated": False,
                     "source_row_count": 1, "materialized_row_count": 1},
        "access_scope": {"user_id": USER, "workspace_id": WORKSPACE,
                         "tenant_id": TENANT},
        "workspace_id": WORKSPACE,
        "tenant_id": TENANT,
        "internal_fixture": False,
    }


def _plan(sources, tmp_path, *, calculation, deliverable_path=None):
    return plan_assignment(
        objective="Grand total of the Total column across the workbook",
        sources=sources,
        deliverables=[{
            "kind": "document",
            "description": "Grand total across the workbook",
            "path": str(deliverable_path or tmp_path / "grand-total.docx"),
        }],
        calculation=calculation,
        authorized_actions=["retrieve", "calculate", "present"],
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
    )


def _document_text(path: Path) -> str:
    """Every visible word in the DOCX, including table cells."""
    document = docx.Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(part for part in parts if part.strip())


def _catalog(tmp_path, monkeypatch, sheets):
    """Materialize one workbook's sheets as active connected catalog entries."""
    engine = create_engine(f"sqlite:///{tmp_path}/catalog.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("core.database.get_db_session", factory)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "out"))
    db = factory()
    user = User(
        id=USER, email="u1@example.com", hashed_password="x",
        first_name="U", last_name="One", role="member", status="active",
        workspace_id=WORKSPACE, tenant_id=TENANT, is_active=True)
    db.add(user)
    root = tmp_path / "sheet_datasets" / WORKSPACE / WORKBOOK_HASH[:12]
    root.mkdir(parents=True, exist_ok=True)
    for index, (sheet, values) in enumerate(sheets.items(), start=1):
        frame = _sheet_frame(sheet, values)
        parquet = root / f"upload__{sheet.lower()}.parquet"
        frame.to_parquet(parquet, index=False)
        db.add(DatasetEntry(
            id=f"entry-{index}",
            workspace_id=WORKSPACE,
            tenant_id=TENANT,
            created_by=USER,
            source_kind="file",
            source="onedrive",
            external_id=f"sha1:{WORKBOOK_HASH}",
            file_name=FILE_NAME,
            content_hash=WORKBOOK_HASH,
            entity_name=sheet,
            dataset_name=f"{sheet.lower()}_dataset",
            parquet_path=str(parquet),
            row_count=len(values),
            column_count=len(frame.columns),
            columns_json={
                "columns": [{"name": column} for column in frame.columns],
                "coverage": {"known": True, "source_row_count": len(values),
                             "materialized_row_count": len(values),
                             "truncated": False},
            },
            status="active",
        ))
    db.add(IntegrationToken(
        id="tok-1", tenant_id=TENANT, user_id=USER, workspace_id=WORKSPACE,
        provider="onedrive", access_token="not-a-secret", status="active"))
    db.commit()
    sources = [
        resolve_assignment_source(db, user, {
            "dataset_name": f"{sheet.lower()}_dataset", "sheet": sheet,
            "source_version": WORKBOOK_HASH,
        })
        for sheet in sheets
    ]
    return db, sources


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/assignment.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    lifecycle = TaskLifecycle(
        GoalRunService(workspace_id=WORKSPACE, tenant_id=TENANT,
                       session_factory=factory),
        GoalService(workspace_id=WORKSPACE, tenant_id=TENANT,
                    session_factory=factory))
    return {
        "tmp": tmp_path,
        "lifecycle": lifecycle,
        "executor": AssignmentExecutor(lifecycle),
    }


def test_aggregate_without_source_index_covers_every_source(tmp_path):
    sources = [_planner_source(tmp_path, "Data01"),
               _planner_source(tmp_path, "Data02")]
    plan = _plan(
        sources, tmp_path,
        calculation={"aggregate": {"operation": "sum",
                                   "value_column": "Total"}})

    aggregate_steps = [step for step in plan["steps"]
                       if step["adapter"] == "dataset.aggregate"]
    assert len(aggregate_steps) == 1, plan["steps"]
    step = aggregate_steps[0]
    assert step["step_id"] == "source-1"
    bindings = step["inputs"]["resource_bindings"]
    assert [binding["sheet"] for binding in bindings] == ["Data01", "Data02"]
    # Every accepted source is inside the calculation, not merely read.
    assert not [item for item in plan["steps"]
                if item["adapter"] == "dataset.read"]
    assert step["inputs"]["operation"] == "sum"
    assert step["inputs"]["value_column"] == "Total"
    deliverable = next(
        item for item in plan["steps"] if item["adapter"] == "artifact.document")
    assert deliverable["depends_on"] == ["source-1"]


def test_single_source_and_explicit_index_keep_their_shape(tmp_path):
    first = _planner_source(tmp_path, "Data01")
    second = _planner_source(tmp_path, "Data02")
    aggregate = {"aggregate": {"operation": "sum", "value_column": "Total"}}

    single = _plan([first], tmp_path, calculation=aggregate)
    single_step = next(item for item in single["steps"]
                       if item["adapter"] == "dataset.aggregate")
    assert single_step["step_id"] == "source-1"
    assert single_step["inputs"]["resource_binding"]["sheet"] == "Data01"
    assert not single_step["inputs"].get("resource_bindings")

    explicit = _plan([first, second], tmp_path,
                     calculation={**aggregate, "source_index": 0})
    adapters = {item["step_id"]: item["adapter"]
                for item in explicit["steps"]}
    assert adapters["source-1"] == "dataset.aggregate"
    assert adapters["source-2"] == "dataset.read"
    named = next(item for item in explicit["steps"]
                 if item["step_id"] == "source-1")
    assert named["inputs"]["resource_binding"]["sheet"] == "Data01"
    assert not named["inputs"].get("resource_bindings")


def test_multi_source_aggregate_executes_the_full_population(
        env, tmp_path, monkeypatch):
    sheets = {
        "Data01": [10, 20.5],
        "Data02": [1.5, 8],
        "Data03": [100],
    }
    _db, sources = _catalog(tmp_path, monkeypatch, sheets)
    expected = round(sum(sum(values) for values in sheets.values()), 2)
    plan = _plan(
        sources, env["tmp"],
        calculation={"aggregate": {"operation": "sum",
                                   "value_column": "Total"}},
        deliverable_path=env["tmp"] / "office" / "grand-total.docx")
    record = env["executor"].create_assignment(
        "conv-full-population", plan["objective"], assignment=plan,
        employee_id=USER, workspace_id=WORKSPACE, tenant_id=TENANT)
    asyncio.run(env["executor"].execute(record["run_id"]))

    status = env["executor"].status(record["run_id"])
    assert status["assignment"]["status"] == "completed", status
    assert not status["open_gaps"], status["open_gaps"]
    durable = env["lifecycle"].get_task(record["run_id"])
    aggregate = next(
        step for step in durable["assignment"]["steps"]
        if step["adapter"] == "dataset.aggregate")
    result = aggregate["result"]
    assert float(result["value"]) == expected, result
    assert result["selected_count"] == 5
    assert [item["sheet"] for item in result["per_source"]] == list(sheets)
    assert [float(item["value"]) for item in result["per_source"]] == [
        round(sum(values), 2) for values in sheets.values()]
    assert [item["sheet"] for item in result["evidence"]] == list(sheets)
    assert all(item["path"] for item in result["evidence"])
    assert {item["source_version"] for item in result["evidence"]} == {
        WORKBOOK_HASH}
    assert [row["sheet"] for row in result["rows"]] == [
        sheet for sheet, values in sheets.items() for _ in values]

    artifact = next(
        item for item in status["assignment"]["deliverables"]
        if item["kind"] == "document")
    text = _document_text(Path(artifact["artifact_path"]))
    assert f"{expected:.2f}" in text, text
    assert FILE_NAME in text, text
    for sheet in sheets:
        assert sheet in text, text


def test_document_exposes_every_source_and_separates_retained_preview(
        env, tmp_path, monkeypatch):
    """20 sheets x 25 rows: 500 selected, 80 retained, all sheets cited.

    The 2026-11-13 workbook served 34,533.00 from 500 rows but its DOCX
    evidence listed only four sheet names and reported the 80-row preview as
    if it were the population. The document must name every contributing
    source with identity/revision/counts and keep the 500-row population
    distinct from the 80-row retained preview.
    """
    sheets = {
        f"Data{index:02d}": [
            float(index * 100 + row) for row in range(25)]
        for index in range(1, 21)
    }
    _db, sources = _catalog(tmp_path, monkeypatch, sheets)
    expected = round(
        sum(sum(values) for values in sheets.values()), 2)
    plan = _plan(
        sources, env["tmp"],
        calculation={"aggregate": {"operation": "sum",
                                   "value_column": "Total"}},
        deliverable_path=env["tmp"] / "office" / "grand-total.docx")
    record = env["executor"].create_assignment(
        "conv-20-sources", plan["objective"], assignment=plan,
        employee_id=USER, workspace_id=WORKSPACE, tenant_id=TENANT)
    asyncio.run(env["executor"].execute(record["run_id"]))

    status = env["executor"].status(record["run_id"])
    assert status["assignment"]["status"] == "completed", status
    assert not status["open_gaps"], status["open_gaps"]
    durable = env["lifecycle"].get_task(record["run_id"])
    aggregate = next(
        step for step in durable["assignment"]["steps"]
        if step["adapter"] == "dataset.aggregate")
    result = aggregate["result"]
    assert float(result["value"]) == expected, result
    assert result["selected_count"] == 500
    assert result["population_count"] == 500
    assert result["retained_count"] == 80
    assert result["rows_truncated"] is True
    assert result["source_count"] == 20
    assert len(result["rows"]) == 80
    assert [item["sheet"] for item in result["per_source"]] == list(sheets)
    for item in result["per_source"]:
        assert item["selected_count"] == 25
        assert item["retained_rows"] == 4
        assert item["row_count"] == 25
        assert item["dataset_name"]
        assert item["resource_id"]
        assert item["source_version"] == WORKBOOK_HASH
        assert item["first_row"] == 2
        assert item["last_row"] == 26

    artifact = next(
        item for item in status["assignment"]["deliverables"]
        if item["kind"] == "document")
    text = _document_text(Path(artifact["artifact_path"]))
    assert f"{expected:.2f}" in text, text
    assert FILE_NAME in text, text
    for sheet, values in sheets.items():
        assert sheet in text, text
        assert f"{sum(values):.2f}" in text, text
    # The population (500 summands) and the retained preview (80 rows) are
    # separate facts, and every source keeps its revision.
    assert "500 row(s) selected across 20 source(s)" in text, text
    assert "80 row(s) retained" in text, text
    assert text.count(WORKBOOK_HASH) >= 20, text
    assert "Audit" in text, text


def test_aggregate_never_silently_drops_an_unaggregatable_source(tmp_path):
    aggregate_source = _planner_source(tmp_path, "Data01")
    read_only = {
        **_planner_source(tmp_path, "Notes"),
        "representation": "file",
        "kind": "document",
    }
    with pytest.raises(Exception) as refused:
        _plan([aggregate_source, read_only], tmp_path,
              calculation={"aggregate": {"operation": "sum",
                                         "value_column": "Total"}})
    assert "Parquet" in str(refused.value)
