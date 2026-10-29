"""Correction controls: server-resolved resources, authority and deliverables."""
from __future__ import annotations

import os
import uuid

import pytest

from core.assignment_plan import (
    new_assignment, new_deliverable, new_step, new_teaching_snapshot,
)
from core.assignment_planner import AssignmentPlanError, validate_proposed_plan
from core.assignment_resources import (
    AssignmentResourceError, allocate_output_path, resolve_assignment_source,
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
