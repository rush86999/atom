"""Correction controls: server-resolved resources, authority and deliverables."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.assignment_plan import (
    new_assignment, new_deliverable, new_step, new_teaching_snapshot,
)
from core.assignment_planner import AssignmentPlanError, validate_proposed_plan
from core.assignment_resources import (
    AssignmentResourceError, allocate_output_path, derive_aggregate_spec,
    resolve_assignment_source, resource_binding, select_resource_candidates,
)
from core.assignment_executor import default_adapter_registry


def _user(workspace="ws-a", user_id="u1"):
    from types import SimpleNamespace

    return SimpleNamespace(id=user_id, workspace_id=workspace, tenant_id="t1")


def test_public_source_rejects_filesystem_path(monkeypatch, tmp_path):
    monkeypatch.delenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", raising=False)
    with pytest.raises(AssignmentResourceError) as exc:
        resolve_assignment_source(
            None, _user(), {"kind": "workbook", "path": str(tmp_path / "x.xlsx")})
    assert exc.value.code == "filesystem_path_not_allowed"


def test_internal_fixture_must_stay_under_configured_root(monkeypatch, tmp_path):
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT",
                       str(tmp_path / "allowed"))
    outside = tmp_path / "outside.xlsx"
    outside.write_text("x")
    with pytest.raises(AssignmentResourceError) as exc:
        resolve_assignment_source(
            None, _user(), {"kind": "workbook", "path": str(outside)},
            allow_internal=True)
    assert exc.value.code == "fixture_path_outside_scope"


def test_forged_catalog_reference_is_refused(monkeypatch):
    import core.sheet_dataset_service as catalog

    monkeypatch.setattr(
        catalog, "resolve_dataset_entry_scoped_sync",
        lambda *a, **k: {"state": "not_found", "entry": None,
                         "candidates": []})
    with pytest.raises(AssignmentResourceError) as exc:
        resolve_assignment_source(
            None, _user(), {"dataset_name": "forged"})
    assert exc.value.code == "resource_not_found"


def test_wrong_workspace_catalog_reference_is_refused(monkeypatch):
    import core.sheet_dataset_service as catalog

    monkeypatch.setattr(
        catalog, "resolve_dataset_entry_scoped_sync",
        lambda *a, **k: {"state": "workspace_mismatch", "entry": None,
                         "candidates": []})
    with pytest.raises(AssignmentResourceError) as exc:
        resolve_assignment_source(
            None, _user(), {"dataset_name": "other-workspace"})
    assert exc.value.code == "resource_workspace_mismatch"


def _patch_active_catalog(monkeypatch, tmp_path, *, version="v1"):
    import core.sheet_dataset_service as catalog
    import core.canvas_capability_service as capability

    parquet = tmp_path / "sheet.parquet"
    parquet.write_bytes(b"not-read")
    entry = {
        "id": "entry-1", "dataset_name": "owned-dataset",
        "file_name": "owned.xlsx", "entity_name": "Sheet1",
        "source_kind": "file", "source": "onedrive",
        "external_id": "ext-1", "content_hash": version,
        "row_count": 1, "status": "active", "workspace_id": "ws-a",
        "parquet_path": str(parquet),
        "coverage": {"known": True, "truncated": False,
                     "source_row_count": 1, "materialized_row_count": 1},
    }
    monkeypatch.setattr(
        catalog, "resolve_dataset_entry_scoped_sync",
        lambda *a, **k: {"state": "active", "entry": entry,
                         "candidates": []})
    monkeypatch.setattr(catalog, "connected_parquet_path",
                        lambda item: parquet)
    monkeypatch.setattr(capability, "_validate_connected_coverage",
                        lambda item: item["coverage"])
    return entry


def test_revoked_grant_is_refused(monkeypatch, tmp_path):
    _patch_active_catalog(monkeypatch, tmp_path)
    import core.canvas_capability_service as capability

    def revoked(db, provider, user):
        raise capability.CapabilityError(
            "source_permission_revoked", "revoked", 403)

    monkeypatch.setattr(capability, "_assert_connected_source_access", revoked)
    with pytest.raises(AssignmentResourceError) as exc:
        resolve_assignment_source(
            None, _user(), {"dataset_name": "owned-dataset"})
    assert exc.value.code == "source_permission_revoked"


def test_stale_version_is_refused(monkeypatch, tmp_path):
    _patch_active_catalog(monkeypatch, tmp_path, version="v2")
    import core.canvas_capability_service as capability

    monkeypatch.setattr(
        capability, "_assert_connected_source_access",
        lambda db, provider, user: {"status": "active"})
    with pytest.raises(AssignmentResourceError) as exc:
        resolve_assignment_source(
            None, _user(), {"dataset_name": "owned-dataset",
                            "source_version": "v1"})
    assert exc.value.code == "stale_source_version"


def test_output_is_allocated_under_owned_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    path = allocate_output_path(
        _user(), kind="document", title="Report", assignment_id="asg-1")
    assert str(tmp_path / "artifacts") in path
    assert path.endswith(".docx")
    assert "Report" in path or "report" in path


def _base_assignment(steps, deliverables, actions):
    return new_assignment(
        objective="test",
        workspace_id="ws-a",
        tenant_id="t1",
        employee_id="u1",
        teaching_snapshot=new_teaching_snapshot(revision="t"),
        steps=steps,
        deliverables=deliverables,
        sources=[{"kind": "document", "resource_id": "r1"}],
        authorized_actions=actions,
        completion_criteria=[{"kind": "required_work_complete"}],
    )


def test_external_adapter_declared_read_only_is_rejected():
    step = new_step(
        step_id="send", title="Send", operation_type="outbound",
        adapter="assignment.controlled_outbox",
        inputs={"to": ["x@example.invalid"]},
        effect="read_only", approval_required=False)
    assignment = _base_assignment(
        [step], [], ["retrieve", "outbound"])
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)


def test_action_registry_write_declared_retrieval_is_rejected():
    from core.action_registry import action_registry

    async def handler(args, context):
        return {"ok": True}

    action_registry.register(
        "test.write.action", handler, effects=[{"effect": "update"}])
    step = new_step(
        step_id="act", title="Act", operation_type="retrieve",
        adapter="action.registry",
        inputs={"action": "test.write.action", "arguments": {}},
        effect="read_only")
    assignment = _base_assignment(
        [step], [], ["retrieve", "outbound"])
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)


def test_action_registry_read_requires_accepted_retrieval():
    from core.action_registry import action_registry

    async def handler(args, context):
        return {"ok": True}

    action_registry.register(
        "test.read.scoped.action", handler, effects=[{"effect": "read"}])
    step = new_step(
        step_id="act", title="Act", operation_type="retrieve",
        adapter="action.registry",
        inputs={"action": "test.read.scoped.action", "arguments": {}},
        effect="read_only")
    assignment = _base_assignment([step], [], ["calculate"])
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)
    accepted = _base_assignment([step], [], ["retrieve"])
    validate_proposed_plan(accepted)


def test_invented_standing_authorization_is_rejected():
    step = new_step(
        step_id="send", title="Send", operation_type="outbound",
        adapter="assignment.controlled_outbox",
        inputs={"to": ["x@example.invalid"]},
        effect="external", approval_required=False,
        standing_authorization="caller-says-so")
    assignment = _base_assignment(
        [step], [], ["outbound"])
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)


def test_action_outside_accepted_scope_is_rejected():
    step = new_step(
        step_id="send", title="Send", operation_type="outbound",
        adapter="assignment.controlled_outbox",
        inputs={"to": ["x@example.invalid"]},
        effect="external", approval_required=True)
    assignment = _base_assignment(
        [step], [], ["retrieve"])  # outbound not accepted
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)


def test_deliverable_nonexistent_step_is_rejected():
    step = new_step(
        step_id="doc", title="Doc", operation_type="present",
        adapter="artifact.document", inputs={"path": "/tmp/x.docx",
                                            "content": "x"})
    deliverable = new_deliverable(
        deliverable_id="d1", kind="document", step_id="missing")
    assignment = _base_assignment([step], [deliverable],
                                  ["retrieve", "present"])
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)


def test_read_step_cannot_produce_docx_deliverable():
    step = new_step(
        step_id="read", title="Read", operation_type="retrieve",
        adapter="document.read", inputs={"path": "/tmp/x.txt"})
    deliverable = new_deliverable(
        deliverable_id="d1", kind="document", step_id="read")
    assignment = _base_assignment([step], [deliverable], ["retrieve"])
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)


def test_duplicate_deliverable_identity_is_rejected():
    step = new_step(
        step_id="doc", title="Doc", operation_type="present",
        adapter="artifact.document", inputs={"path": "/tmp/x.docx",
                                            "content": "x"})
    first = new_deliverable(
        deliverable_id="dup", kind="document", step_id="doc")
    second = new_deliverable(
        deliverable_id="dup", kind="document", step_id="doc")
    assignment = _base_assignment([step], [first, second],
                                  ["retrieve", "present"])
    with pytest.raises(AssignmentPlanError):
        validate_proposed_plan(assignment)


def test_matching_artifact_step_is_valid():
    step = new_step(
        step_id="doc", title="Doc", operation_type="present",
        adapter="artifact.document", inputs={"path": "/tmp/x.docx",
                                            "content": "x"})
    deliverable = new_deliverable(
        deliverable_id="d1", kind="document", step_id="doc")
    assignment = _base_assignment([step], [deliverable],
                                  ["retrieve", "present"])
    validate_proposed_plan(assignment)


def _candidate(name, file_name, sheet, columns, *, status="active"):
    return {
        "id": f"id-{name}-{sheet}",
        "dataset_name": name,
        "file_name": file_name,
        "entity_name": sheet,
        "columns": columns,
        "status": status,
        "coverage": {"known": True, "truncated": False},
    }


def test_distractor_ranked_first_is_not_adopted():
    distractor = _candidate(
        "unrelated_notes", "unrelated-notes.xlsx", "Notes",
        ["Label", "Price"])
    target = _candidate(
        "scotch_parts_price_list", "scotch-parts.xlsx",
        "US$ SCOTCH PARTS", ["Total", "Quantity", "Unit Price", "Currency"])
    selected = select_resource_candidates(
        [distractor, target],
        objective="Sum the total for the scotch parts price list",
        scope_query="scotch parts price list",
    )
    assert len(selected) == 1
    assert selected[0]["dataset_name"] == "scotch_parts_price_list"


def test_same_workbook_several_plausible_sheets_is_a_clarification():
    first = _candidate(
        "scotch_parts", "scotch-parts.xlsx", "US$ SCOTCH PARTS",
        ["Total"])
    second = _candidate(
        "scotch_parts", "scotch-parts.xlsx", "EUR SCOTCH PARTS",
        ["Total"])
    with pytest.raises(AssignmentResourceError) as exc:
        select_resource_candidates(
            [first, second],
            objective="Sum the total for the scotch parts price list",
            scope_query="scotch parts price list",
        )
    assert exc.value.code == "ambiguous_resource"
    assert len(exc.value.candidates) == 2


def test_explicit_sheet_selects_that_sheet():
    first = _candidate(
        "scotch_parts", "scotch-parts.xlsx", "US$ SCOTCH PARTS",
        ["Total"])
    second = _candidate(
        "scotch_parts", "scotch-parts.xlsx", "EUR SCOTCH PARTS",
        ["Total"])
    selected = select_resource_candidates(
        [first, second],
        objective="Sum the total for the scotch parts price list",
        scope_query="scotch parts price list",
        explicit_sheet="EUR SCOTCH PARTS",
    )
    assert len(selected) == 1
    assert selected[0]["entity_name"] == "EUR SCOTCH PARTS"


def test_required_two_sources_are_preserved():
    first = _candidate(
        "scotch_parts", "scotch-parts.xlsx", "US$ SCOTCH PARTS",
        ["Total"])
    second = _candidate(
        "open_orders", "open-orders.xlsx", "Orders", ["Total"])
    selected = select_resource_candidates(
        [first, second],
        objective="Compare the scotch parts and open orders totals",
        scope_query="scotch parts open orders totals",
        required_count=2,
    )
    assert {item["dataset_name"] for item in selected} == {
        "scotch_parts", "open_orders"}


def test_no_justified_candidate_is_pending_work():
    target = _candidate(
        "scotch_parts_price_list", "scotch-parts.xlsx",
        "US$ SCOTCH PARTS", ["Total"])
    assert select_resource_candidates(
        [target],
        objective="Summarize the quarterly tax filings",
        scope_query="quarterly tax filings",
    ) == []


def _real_connected_catalog(tmp_path, monkeypatch):
    import pandas as pd

    engine = create_engine(f"sqlite:///{tmp_path}/connected.db")
    from core.models import (
        Base, DatasetEntry, IntegrationToken, User,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("core.database.get_db_session", factory)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "out"))
    db = factory()
    user = User(
        id="u1", email="u1@example.com", hashed_password="x",
        first_name="U", last_name="One", role="member", status="active",
        workspace_id="ws-a", tenant_id="t1", is_active=True)
    db.add(user)
    db.commit()
    root = tmp_path / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    parquet = root / "scotch.parquet"
    frame = pd.DataFrame({
        "Item Number": ["SC-1", "SC-2", "SC-3"],
        "Total": [20.0, 60.0, 5.0],
        "Currency": ["USD", "USD", "USD"],
        "__sheet_row": [2, 3, 4],
    })
    frame.to_parquet(parquet, index=False)
    entry = DatasetEntry(
        id="entry-1", workspace_id="ws-a", tenant_id="t1",
        created_by="u1", source_kind="file", source="onedrive",
        external_id="drive-1", file_name="scotch-parts.xlsx",
        content_hash="a" * 40, entity_name="US$ SCOTCH PARTS",
        dataset_name="scotch_parts_price_list", parquet_path=str(parquet),
        row_count=3, column_count=4,
        columns_json={
            "columns": [{"name": column} for column in frame.columns],
            "coverage": {"known": True, "source_row_count": 3,
                         "materialized_row_count": 3, "truncated": False},
        },
        status="active",
    )
    db.add(entry)
    token = IntegrationToken(
        id="tok-1", tenant_id="t1", user_id="u1", workspace_id="ws-a",
        provider="onedrive", access_token="not-a-secret",
        status="active")
    db.add(token)
    db.commit()
    return db, user, token, factory


def test_real_parquet_read_returns_rows_and_provenance(tmp_path, monkeypatch):
    db, user, _token, _factory = _real_connected_catalog(tmp_path, monkeypatch)
    resolved = resolve_assignment_source(
        db, user, {"dataset_name": "scotch_parts_price_list",
                   "sheet": "US$ SCOTCH PARTS"})
    assert resolved["representation"] == "parquet_frame"
    assert resolved["columns"] == ["Item Number", "Total", "Currency",
                                   "__sheet_row"]
    binding = resource_binding(resolved)
    assert "path" not in binding
    from core.assignment_executor import _dataset_read

    result = asyncio.run(_dataset_read(
        {"resource_binding": binding, "columns": ["Total"], "max_rows": 10},
        {"employee_id": "u1", "workspace_id": "ws-a", "tenant_id": "t1"}))
    assert result["matched_count"] == 3
    assert [row["__sheet_row"] for row in result["rows"]] == [2, 3, 4]
    assert result["source"]["dataset_name"] == "scotch_parts_price_list"
    assert result["source"]["sheet"] == "US$ SCOTCH PARTS"
    assert result["source_version"] == "a" * 40
    assert result["evidence"][0]["sheet_rows"] == [2, 3, 4]


def test_real_parquet_read_preserves_formula_sidecar_for_matched_rows(
        tmp_path, monkeypatch):
    db, user, _token, _factory = _real_connected_catalog(tmp_path, monkeypatch)
    parquet = tmp_path / "sheet_datasets" / "scotch.parquet"
    sidecar = parquet.with_name(parquet.name + ".formulas.json")
    sidecar.write_text(json.dumps({
        "sheet": "US$ SCOTCH PARTS",
        "formulas": {
            "B2": "=B2*C2",
            "B3": "=B3*C3",
            "B99": "=NOT-A-MATCHED-ROW",
        },
    }))
    resolved = resolve_assignment_source(
        db, user, {"dataset_name": "scotch_parts_price_list",
                   "sheet": "US$ SCOTCH PARTS"})
    from core.assignment_executor import _dataset_read

    result = asyncio.run(_dataset_read(
        {"resource_binding": resource_binding(resolved), "max_rows": 10},
        {"employee_id": "u1", "workspace_id": "ws-a", "tenant_id": "t1"}))
    assert result["formulas"] == {"B2": "=B2*C2", "B3": "=B3*C3"}


def test_revoked_access_between_start_and_resumed_read_is_refused(
        tmp_path, monkeypatch):
    db, user, token, _factory = _real_connected_catalog(tmp_path, monkeypatch)
    resolved = resolve_assignment_source(
        db, user, {"dataset_name": "scotch_parts_price_list",
                   "sheet": "US$ SCOTCH PARTS"})
    binding = resource_binding(resolved)
    from core.assignment_executor import NeedsContext, _dataset_read

    context = {"employee_id": "u1", "workspace_id": "ws-a",
               "tenant_id": "t1"}
    first = asyncio.run(_dataset_read(
        {"resource_binding": binding}, context))
    assert first["matched_count"] == 3

    # Between the start resolution and the resumed read, the owner revokes
    # the grant. The earlier path is not continuing access.
    token.status = "revoked"
    db.commit()
    with pytest.raises(NeedsContext) as exc:
        asyncio.run(_dataset_read({"resource_binding": binding}, context))
    waiting = exc.value.gap["waiting"]
    assert waiting["state"] == "source_access_revoked"
    assert waiting["code"] == "source_permission_revoked"
    assert "source_access" == exc.value.gap["concept"]


def test_derived_aggregate_uses_actual_numeric_schema(tmp_path, monkeypatch):
    db, user, _token, _factory = _real_connected_catalog(tmp_path, monkeypatch)
    resolved = resolve_assignment_source(
        db, user, {"dataset_name": "scotch_parts_price_list",
                   "sheet": "US$ SCOTCH PARTS"})
    spec = derive_aggregate_spec(
        "Sum the total for the scotch parts price list", [resolved])
    assert spec == {"aggregate": {"operation": "sum",
                                  "value_column": "Total"}}
    count = derive_aggregate_spec(
        "Count the records in the scotch parts price list", [resolved])
    assert count == {"aggregate": {"operation": "count"}}


def test_short_version_prefix_cannot_satisfy_active_version(
        tmp_path, monkeypatch):
    db, user, _token, _factory = _real_connected_catalog(tmp_path, monkeypatch)
    with pytest.raises(AssignmentResourceError) as exc:
        resolve_assignment_source(
            db, user, {"dataset_name": "scotch_parts_price_list",
                       "sheet": "US$ SCOTCH PARTS",
                       "source_version": "a"})
    assert exc.value.code == "stale_source_version"


def test_sum_over_zero_eligible_rows_is_a_clarification(
        tmp_path, monkeypatch):
    db, user, _token, _factory = _real_connected_catalog(tmp_path, monkeypatch)
    resolved = resolve_assignment_source(
        db, user, {"dataset_name": "scotch_parts_price_list",
                   "sheet": "US$ SCOTCH PARTS"})
    from core.assignment_executor import NeedsContext, _dataset_aggregate

    with pytest.raises(NeedsContext) as exc:
        asyncio.run(_dataset_aggregate(
            {
                "resource_binding": resource_binding(resolved),
                "operation": "sum",
                "value_column": "Total",
                "filters": [{"column": "Total", "operator": "gt",
                             "value": 999}],
            },
            {"employee_id": "u1", "workspace_id": "ws-a",
             "tenant_id": "t1"}))
    assert exc.value.gap["concept"] == "records"


def test_artifact_with_missing_required_result_is_rejected(tmp_path):
    import docx
    from core.assignment_executor import (
        NeedsContext, _verify_artifact_substance,
    )

    artifact = tmp_path / "partial.docx"
    document = docx.Document()
    document.add_paragraph("Result: 10")
    document.save(artifact)
    context = {
        "employee_id": "u1",
        "objective": "Report both totals",
        "teaching": {},
        "sources": [],
        "previous_results": {
            "first": {"expression": "1+9", "value": "10"},
            "second": {"expression": "2+18", "value": "20"},
        },
    }
    with pytest.raises(NeedsContext) as exc:
        _verify_artifact_substance(
            "document", str(artifact), {}, context)
    assert exc.value.gap["concept"] == "artifact_substance"



def test_revoked_grant_between_start_and_resumed_executor_read(
        tmp_path, monkeypatch):
    import core.assignment_controlled_transport  # noqa: F401
    from core.assignment_executor import AssignmentExecutor
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    db, user, token, factory = _real_connected_catalog(tmp_path, monkeypatch)
    resolved = resolve_assignment_source(
        db, user, {"dataset_name": "scotch_parts_price_list",
                   "sheet": "US$ SCOTCH PARTS"})
    binding = resource_binding(resolved)
    plan = new_assignment(
        objective="Read after the external wait",
        employee_id="u1",
        workspace_id="ws-a",
        tenant_id="t1",
        teaching_snapshot=new_teaching_snapshot(revision="t"),
        steps=[
            new_step(
                step_id="wait", title="Wait for the trigger",
                operation_type="retrieve",
                adapter="assignment.controlled_wait",
                inputs={"correlation_id": "revoke-A"},
                effect="read_only"),
            new_step(
                step_id="read", title="Read the connected source",
                operation_type="retrieve", adapter="dataset.read",
                depends_on=["wait"],
                inputs={"resource_binding": binding},
                effect="read_only"),
        ],
        sources=[{"kind": "workbook", "binding": binding}],
        authorized_actions=["retrieve"],
        completion_criteria=[{"kind": "required_work_complete"}],
    )
    runs = GoalRunService(
        workspace_id="ws-a", tenant_id="t1", session_factory=factory)
    goals = GoalService(
        workspace_id="ws-a", tenant_id="t1", session_factory=factory)
    executor = AssignmentExecutor(TaskLifecycle(runs, goals))
    record = executor.create_assignment(
        "conv-revoke", "Read after the external wait", assignment=plan,
        employee_id="u1", workspace_id="ws-a", tenant_id="t1")
    asyncio.run(executor.execute(record["run_id"]))
    waiting = executor.status(record["run_id"])["assignment"]
    assert waiting["status"] == "waiting", waiting

    # The grant is revoked after start, before the read is resumed.
    token.status = "revoked"
    db.commit()
    executor.record_external_response(
        record["run_id"], "revoke-A", response="triggered")
    asyncio.run(executor.resume(record["run_id"]))
    status = executor.status(record["run_id"])
    assert status["assignment"]["status"] == "waiting", status
    gaps = status["open_gaps"]
    assert any(gap.get("concept") == "source_access" for gap in gaps), gaps
    assert any(
        "source_permission_revoked" in str(gap.get("reason") or "")
        for gap in gaps), gaps
    read_step = next(
        step for step in status["assignment"]["steps"]
        if step["step_id"] == "read")
    assert read_step["status"] == "waiting"
    assert (read_step.get("waiting") or {}).get("state") == (
        "source_access_revoked")
