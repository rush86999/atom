"""Connected-catalog binding controls.

These tests exercise the server-resolved path only: a real materialized
Parquet sheet, a scoped catalog lookup, an active token grant, and the
existing capability assessment adapter. No rows are supplied by the caller.
"""
from __future__ import annotations

import asyncio
import io
import json
from types import SimpleNamespace

import pandas as pd
import pytest
from pydantic import ValidationError

from core.database import Base, SessionLocal, engine
import core.models  # noqa: F401
from core.models import Canvas, CanvasAudit, DatasetEntry, IntegrationToken
from core.sheet_dataset_service import (
    DatasetScopeError,
    materialize_sheet_bytes_sync,
    resolve_dataset_entry_scoped_sync,
)


def _workbook(rows=None) -> bytes:
    rows = rows or [
        ["A-1", 10, "Open"],
        ["A-2", 20, "Open"],
        ["A-3", 30, "Closed"],
        ["A-4", 40, "Open"],
        ["A-5", 50, "Closed"],
    ]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=["Part", "Amount", "Status"]).to_excel(
            writer, sheet_name="Parts", index=False
        )
        pd.DataFrame({"X": [1], "Y": [2]}).to_excel(
            writer, sheet_name="Other", index=False
        )
    return buf.getvalue()


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "data"))
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.query(CanvasAudit).delete()
        db.query(Canvas).delete()
        db.query(DatasetEntry).delete()
        db.query(IntegrationToken).filter(
            IntegrationToken.user_id == "connected-user"
        ).delete()
        db.add(IntegrationToken(
            id="connected-token", tenant_id="default",
            user_id="connected-user", workspace_id="ws-connected",
            provider="onedrive", access_token="test-token", status="active",
        ))
        db.add(Canvas(
            id="connected-canvas", tenant_id="default",
            workspace_id="ws-connected", created_by="connected-user",
            name="Connected", canvas_type="sheet", content={}, status="active",
        ))
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(CanvasAudit).delete()
        db.query(Canvas).delete()
        db.query(DatasetEntry).delete()
        db.query(IntegrationToken).filter(
            IntegrationToken.user_id == "connected-user"
        ).delete()
        db.commit()


def _user(workspace_id="ws-connected"):
    return SimpleNamespace(
        id="connected-user", workspace_id=workspace_id,
        tenant_id="default", role="workspace_admin",
    )


def _canvas():
    with SessionLocal() as db:
        return db.query(Canvas).filter(Canvas.id == "connected-canvas").one()


def _manifest(subject="Part", measure="Amount"):
    return {
        "schema_version": 1,
        "base_component": "table",
        "operations": [
            "read", "select", "calculate", "assess", "edit", "export", "bind",
        ],
        "data_binding": {
            "subject_field": subject, "measure_field": measure,
            "status_field": "Status",
        },
        "editable_fields": ["Amount", "Status"],
        "teaching_binding": {"agent_id": "agent-1", "scope_id": "task-1"},
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": "Approve Amount >= 20; review below 20.",
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _bind(world, monkeypatch, *, rows=None, subject="Part", measure="Amount"):
    from core.canvas_capability_service import bind_connected_dataset, set_manifest

    monkeypatch.setenv("ATOM_REVIEW_MODEL", "deepseek-flash")
    with SessionLocal() as db:
        canvas = db.query(Canvas).filter(Canvas.id == "connected-canvas").one()
        user = _user()
        set_manifest(db, canvas, user, _manifest(subject=subject, measure=measure))
        materialized = materialize_sheet_bytes_sync(
            _workbook(rows), "connected.xlsx", "onedrive",
            user_id="connected-user", workspace_id="ws-connected",
            external_id="item-connected",
        )
        assert materialized["status"] == "materialized"
        entry = next(
            e for e in materialized["datasets"] if e["entity_name"] == "Parts"
        )
        bound = bind_connected_dataset(
            db, canvas, user,
            dataset_name=entry["dataset_name"],
            expected_version=entry["content_hash"],
            title="Connected parts",
        )
        return bound, entry, canvas, user


def test_scoped_lookup_refuses_missing_workspace():
    with pytest.raises(DatasetScopeError):
        resolve_dataset_entry_scoped_sync("anything", workspace_id="")


def test_grant_state_distinguishes_revoked_from_disconnected(world):
    from core.integrations.token_store import connected_source_grant_state

    assert connected_source_grant_state("onedrive", "connected-user") == "active"
    with SessionLocal() as db:
        token = db.query(IntegrationToken).filter(
            IntegrationToken.id == "connected-token"
        ).one()
        token.status = "revoked"
        db.commit()
    assert connected_source_grant_state("onedrive", "connected-user") == "revoked"
    with SessionLocal() as db:
        db.query(IntegrationToken).filter(
            IntegrationToken.id == "connected-token"
        ).delete()
        db.commit()
    assert connected_source_grant_state("onedrive", "connected-user") == "disconnected"


def test_connected_bind_preserves_snapshot_and_upstream_identity(world, monkeypatch):
    from core.canvas_capability_service import calculate_operation, edit_operation

    bound, entry, canvas, user = _bind(world, monkeypatch)
    assert bound["row_count"] == 5
    assert bound["snapshot"]["kind"] == "canvas_dataset_snapshot"
    assert bound["snapshot"]["version"] != bound["upstream"]["content_hash"]
    assert bound["upstream"]["provider"] == "onedrive"
    assert bound["upstream"]["external_id"] == "item-connected"
    assert bound["upstream"]["sheet_name"] == "Parts"
    assert bound["upstream"]["content_hash"] == entry["content_hash"]
    assert bound["source_access"]["status"] == "active"
    assert bound["source"]["writeback"]["upstream_mutated"] is False

    with SessionLocal() as db:
        canvas = db.query(Canvas).filter(Canvas.id == canvas.id).one()
        dataset = canvas.content["dataset"]
        assert dataset["sheet_rows"] == [2, 3, 4, 5, 6]
        calc = calculate_operation(db, canvas, user, "sum Amount")
        assert calc["total_values"]["(unstated)"] == "150.00"
        assert calc["coverage"]["upstream_version"] == entry["content_hash"]
        assert "Canvas snapshot" in calc["block"]
        edited = edit_operation(
            db, canvas, user,
            [{"row": 3, "column": "Amount", "value": 25}],
            expected_revision=bound["revision"],
        )
        assert edited["edits"][0]["readback_matches"] is True
        assert edited["upstream_revision"] == entry["content_hash"]
        assert edited["source_version"] != bound["snapshot"]["version"]
        assert edited["writeback"] == {
            "supported": False, "upstream_mutated": False, "performed": False,
        }


def test_connected_refresh_rebinds_and_invalidates_reuse(world, monkeypatch):
    from core.canvas_capability_service import bind_connected_dataset, set_manifest

    bound, entry, canvas, user = _bind(world, monkeypatch)
    with SessionLocal() as db:
        canvas = db.query(Canvas).filter(Canvas.id == canvas.id).one()
        refreshed_materialization = materialize_sheet_bytes_sync(
            _workbook([["A-1", 11, "Open"], ["A-2", 21, "Open"]]),
            "connected.xlsx", "onedrive",
            user_id="connected-user", workspace_id="ws-connected",
            external_id="item-connected",
        )
        new_entry = next(
            e for e in refreshed_materialization["datasets"]
            if e["entity_name"] == "Parts"
        )
        assert new_entry["content_hash"] != entry["content_hash"]
        refreshed = bind_connected_dataset(
            db, canvas, user,
            dataset_name=new_entry["dataset_name"],
            expected_version=new_entry["content_hash"],
        )
        assert refreshed["refresh"]["replaced"] is True
        assert refreshed["refresh"]["prior_upstream_version"] == entry["content_hash"]
        assert refreshed["refresh"]["assessment_reuse_invalidated"] is True
        assert refreshed["refresh"]["new_upstream_version"] == new_entry["content_hash"]
        assert refreshed["snapshot"]["version"] != bound["snapshot"]["version"]
        assert refreshed["source"]["previous_bindings"][-1]["upstream"]["content_hash"] == entry["content_hash"]


def test_connected_assessment_is_bounded_and_names_unassessed(world, monkeypatch):
    from core import review_result
    from core.canvas_capability_service import assess_operation, policy_revision

    bound, entry, canvas, user = _bind(world, monkeypatch)
    rev = policy_revision(_manifest())
    seen = {}

    async def fake_generate(_llm, **kwargs):
        seen["messages"] = kwargs["messages"]
        return (
            "```review_result\n"
            + json.dumps({"assessments": [
                {
                    "subject_id": "A-1", "decision": "REVIEW",
                    "basis": ["Amount 10"],
                    "evidence_ids": ["ev:A-1:2"],
                    "policy_ids": [f"policy:{rev}"],
                    "unresolved_requirements": [],
                },
                {
                    "subject_id": "A-2", "decision": "APPROVE",
                    "basis": ["Amount 20"],
                    "evidence_ids": ["ev:A-2:3"],
                    "policy_ids": [f"policy:{rev}"],
                    "unresolved_requirements": [],
                },
            ]})
            + "\n```"
        )

    monkeypatch.setattr(review_result, "generate_structured_review", fake_generate)
    with SessionLocal() as db:
        canvas = db.query(Canvas).filter(Canvas.id == canvas.id).one()
        result = asyncio.run(assess_operation(
            db, canvas, user, "all rows", llm_service=object(), max_subjects=2,
        ))
    assert result["certified"] is True
    assert result["coverage"]["selected_count"] == 5
    assert result["coverage"]["assessed_count"] == 2
    assert result["coverage"]["unassessed_count"] == 3
    assert result["coverage"]["assessment_truncated"] is True
    assert result["unassessed_subjects"] == ["A-3", "A-4", "A-5"]
    prompt = seen["messages"][0]["content"]
    assert "A-1" in prompt and "A-2" in prompt
    assert "A-3" not in prompt and "A-4" not in prompt
    assert entry["content_hash"] in prompt


def test_connected_negatives_are_distinguishable(world, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, bind_connected_dataset, set_manifest,
    )

    with SessionLocal() as db:
        canvas = db.query(Canvas).filter(Canvas.id == "connected-canvas").one()
        user = _user()
        set_manifest(db, canvas, user, _manifest())
        materialized = materialize_sheet_bytes_sync(
            _workbook(), "connected.xlsx", "onedrive",
            user_id="connected-user", workspace_id="ws-connected",
            external_id="item-connected",
        )
        entry = next(
            e for e in materialized["datasets"] if e["entity_name"] == "Parts"
        )

        def code(call):
            with pytest.raises(CapabilityError) as exc:
                call()
            return exc.value.code

        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name="guessed-name",
        )) == "source_not_found"
        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name=entry["dataset_name"],
            expected_version="deadbeef",
        )) == "stale_source_version"

        # Wrong workspace: same catalog name exists, but not in ws-connected.
        other = materialize_sheet_bytes_sync(
            _workbook(), "other.xlsx", "onedrive",
            user_id="other-user", workspace_id="ws-other",
            external_id="item-other",
        )["datasets"][0]
        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name=other["dataset_name"],
        )) == "workspace_mismatch"

        # Inactive/superseded source.
        row = db.query(DatasetEntry).filter(
            DatasetEntry.dataset_name == entry["dataset_name"]
        ).one()
        row.status = "superseded"
        db.commit()
        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name=entry["dataset_name"],
        )) == "source_inactive"
        row.status = "active"
        db.commit()

        # Revoked grant vs no grant at all.
        token = db.query(IntegrationToken).filter(
            IntegrationToken.id == "connected-token"
        ).one()
        token.status = "revoked"
        db.commit()
        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name=entry["dataset_name"],
        )) == "source_permission_revoked"
        db.delete(token)
        db.commit()
        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name=entry["dataset_name"],
        )) == "source_disconnected"

        db.add(IntegrationToken(
            id="connected-token", tenant_id="default",
            user_id="connected-user", workspace_id="ws-connected",
            provider="onedrive", access_token="test-token", status="active",
        ))
        db.commit()

        # Incomplete materialization coverage is not a bindable frame.
        row = db.query(DatasetEntry).filter(
            DatasetEntry.dataset_name == entry["dataset_name"]
        ).one()
        original_schema = row.columns_json
        row.columns_json = {
            "columns": [],
            "coverage": {
                "known": True, "source_row_count": 5,
                "materialized_row_count": 5, "truncated": True,
            },
        }
        db.commit()
        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name=entry["dataset_name"],
        )) == "materialization_incomplete"
        row.columns_json = original_schema
        db.commit()

        # No subject field at all is a clarification, not a guessed column.
        set_manifest(db, canvas, user, _manifest(subject=""))
        assert code(lambda: bind_connected_dataset(
            db, canvas, user, dataset_name=entry["dataset_name"],
        )) == "subject_field_required"


def test_client_paths_hashes_and_rows_are_rejected_by_the_request_model():
    from api.canvas_capability_routes import BindConnectedRequest

    with pytest.raises(ValidationError):
        BindConnectedRequest(
            dataset_name="x", file_path="/etc/passwd",
        )
    with pytest.raises(ValidationError):
        BindConnectedRequest(
            dataset_name="x", sha256="deadbeef",
        )
    with pytest.raises(ValidationError):
        BindConnectedRequest(
            dataset_name="x", rows=[[1, 2, 3]],
        )


def test_duplicate_subjects_cannot_be_assessed(world, monkeypatch):
    from core import review_result
    from core.canvas_capability_service import assess_operation

    rows = [["DUP", 10, "Open"], ["DUP", 20, "Open"]]
    bound, entry, canvas, user = _bind(world, monkeypatch, rows=rows)

    async def fake_generate(_llm, **kwargs):
        return "```review_result\n" + json.dumps({"assessments": []}) + "\n```"

    monkeypatch.setattr(review_result, "generate_structured_review", fake_generate)
    with SessionLocal() as db:
        canvas = db.query(Canvas).filter(Canvas.id == canvas.id).one()
        with pytest.raises(Exception) as exc:
            asyncio.run(assess_operation(
                db, canvas, user, "all rows", llm_service=object(), max_subjects=10,
            ))
    assert getattr(exc.value, "code", "") == "duplicate_subject_mapping"
