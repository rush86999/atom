"""Generic source answer: authorized document bound to the same job.

Real public answer route, real Generic consumer/registered effect/scratch DB;
only model transport is doubled. Source reads use the existing resolver and
document.text reader. No live provider/account/browser action.
"""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

import core.generic_agent as real_generic
import core.lancedb_handler as lance
from core.models import IngestedDocument
from core.models_board import BoardTask
from core.react_models import InformationWaitRequest, ReActStep, ToolCall
from tests.test_agent_generic_information_wait import (
    _install_model,
    _seed_board,
)
from tests.test_agent_run_outcome_join_contract import (
    _client,
    _job_payload,
    _run,
    real_env,  # noqa: F401
)


def _source_fixture(real_env, tmp_path, monkeypatch):
    path = tmp_path / "source.json"
    payload = {"po_id": "PO-SOURCE-1", "quantity": "2", "unit_price": "5.00"}
    path.write_text(json.dumps(payload))
    version = "ev4:" + hashlib.sha256(path.read_bytes()).hexdigest()
    doc = IngestedDocument(
        id="generic-source-doc",
        workspace_id="ws1",
        tenant_id="t1",
        file_name=path.name,
        file_path=str(path),
        file_type="json",
        integration_id="upload",
        external_id="generic-source-doc",
        source_content_hash=version,
        freshness_status="fresh",
    )
    with real_env.SessionLocal() as db:
        db.add(doc)
        db.commit()
    indexed = {
        "id": doc.id,
        "text": json.dumps(payload),
        "source": path.name,
        "metadata": {
            "source_content_hash": version,
            "pg_document_id": doc.id,
            "workspace_id": "ws1",
            "tenant_id": "t1",
        },
    }
    monkeypatch.setattr(
        lance, "get_lancedb_handler",
        lambda workspace: SimpleNamespace(
            get_document_by_id=lambda table, identity: indexed))
    return doc, version


def test_source_only_answer_resumes_same_job_with_verified_effect(
        real_env, tmp_path, monkeypatch):
    board_id, column_id = _seed_board(real_env)
    doc, version = _source_fixture(real_env, tmp_path, monkeypatch)

    def wait(task_input, history, context):
        return ReActStep(
            thought="Need the authorized invoice document.",
            information_wait=InformationWaitRequest(
                question="Which authorized invoice should be used?",
                missing_fact="authorized invoice",
                subject="invoice reconciliation",
            ),
        )

    def resumed(task_input, history, context):
        source = context.get("information_source") or {}
        assert "PO-SOURCE-1" in str(source.get("content") or "")
        assert source.get("source_version") == version
        assert source.get("receipt", {}).get("status") == "verified"
        return ReActStep(
            thought="The authorized source is available.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id,
                    "column_id": column_id,
                    "title": "Source-backed task",
                    "status": "backlog",
                },
            ),
        )

    def finished(task_input, history, context):
        finished.called = True
        return ReActStep(
            thought="The task was verified.",
            final_answer="Created the source-backed task.",
        )
    finished.called = False

    calls = _install_model(monkeypatch, [wait, resumed, finished])
    started = _run(
        real_env, operation_id="generic-source-answer",
        parameters={"sync": True, "task_input": "Create a source-backed task"})
    assert started.status_code == 202, started.text
    data = started.json()["data"]
    receipt = data["wait_receipt"]
    assert data["job_status"] == "waiting"
    assert len(calls) == 1

    answer = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer",
        json={
            "answer": "",
            "correlation_id": receipt["correlation_id"],
            "source": {"document_id": doc.id, "source_version": version},
        },
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()["data"]
    assert body["job_status"] == "success", body
    assert body["execution_id"] == data["execution_id"]
    assert finished.called is True
    assert any(
        (step.get("action") or {}).get("tool") == "tasks.create"
        and step["output"].get("oracle_verified") is True
        for step in body["result"]["steps"])
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(
            BoardTask.board_id == board_id,
            BoardTask.title == "Source-backed task").count() == 1


def test_source_answer_wrong_correlation_does_not_wake_or_read(
        real_env, tmp_path, monkeypatch):
    _seed_board(real_env)
    doc, version = _source_fixture(real_env, tmp_path, monkeypatch)

    def wait(task_input, history, context):
        return ReActStep(
            thought="Need source.",
            information_wait=InformationWaitRequest(
                question="Which authorized invoice should be used?",
                missing_fact="authorized invoice",
            ),
        )

    calls = _install_model(monkeypatch, [wait])
    started = _run(
        real_env, operation_id="generic-source-wrong-corr",
        parameters={"sync": True, "task_input": "Create a task"})
    assert started.status_code == 202, started.text
    data = started.json()["data"]
    receipt = data["wait_receipt"]
    answer = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer",
        json={
            "answer": "",
            "correlation_id": "wrong-correlation",
            "source": {"document_id": doc.id, "source_version": version},
        },
    )
    assert answer.status_code == 409, answer.text
    job, payload = _job_payload(real_env, data["job_id"])
    assert job.status == "waiting"
    assert payload["wait_receipt"]["correlation_id"] == receipt["correlation_id"]
    assert len(calls) == 1


def test_duplicate_exact_source_is_idempotent_and_changed_material_refuses(
        real_env, tmp_path, monkeypatch):
    board_id, column_id = _seed_board(real_env)
    doc, version = _source_fixture(real_env, tmp_path, monkeypatch)

    def wait(task_input, history, context):
        return ReActStep(
            thought="Need the authorized source.",
            information_wait=InformationWaitRequest(
                question="Which authorized source?",
                missing_fact="source",
            ),
        )

    def resumed(task_input, history, context):
        return ReActStep(
            thought="Create once.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id,
                    "column_id": column_id,
                    "title": "Duplicate source task",
                    "status": "backlog",
                },
            ),
        )

    def finished(task_input, history, context):
        return ReActStep(
            thought="Verified.",
            final_answer="Created once.",
        )

    _install_model(monkeypatch, [wait, resumed, finished])
    started = _run(
        real_env, operation_id="generic-source-duplicate",
        parameters={"sync": True, "task_input": "Create once"})
    data = started.json()["data"]
    body = {
        "answer": "",
        "correlation_id": data["wait_receipt"]["correlation_id"],
        "source": {"document_id": doc.id, "source_version": version},
    }
    first = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer", json=body)
    assert first.status_code == 200, first.text
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(
            BoardTask.title == "Duplicate source task").count() == 1

    duplicate = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer", json=body)
    assert duplicate.status_code in (200, 409), duplicate.text
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(
            BoardTask.title == "Duplicate source task").count() == 1

    # Same resource, changed authoritative material/version: refuse, no new
    # effect and no overwrite of the accepted snapshot.
    changed_payload = {"po_id": "PO-SOURCE-1", "quantity": "3", "unit_price": "9.00"}
    changed_path = tmp_path / "changed.json"
    changed_path.write_text(json.dumps(changed_payload))
    changed_version = "ev4:" + hashlib.sha256(changed_path.read_bytes()).hexdigest()
    with real_env.SessionLocal() as db:
        row = db.get(IngestedDocument, doc.id)
        row.source_content_hash = changed_version
        row.file_path = str(changed_path)
        db.commit()
    changed_indexed = {
        "id": doc.id,
        "text": json.dumps(changed_payload),
        "source": changed_path.name,
        "metadata": {
            "source_content_hash": changed_version,
            "pg_document_id": doc.id,
            "workspace_id": "ws1",
            "tenant_id": "t1",
        },
    }
    monkeypatch.setattr(
        lance, "get_lancedb_handler",
        lambda workspace: SimpleNamespace(
            get_document_by_id=lambda table, identity: changed_indexed))
    changed = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer",
        json={
            "answer": "",
            "correlation_id": data["wait_receipt"]["correlation_id"],
            "source": {"document_id": doc.id, "source_version": changed_version},
        },
    )
    assert changed.status_code == 409, changed.text
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(
            BoardTask.title == "Duplicate source task").count() == 1


@pytest.mark.parametrize("failure", ["missing", "foreign", "stale", "revoked"])
def test_source_authority_failures_do_not_wake_or_effect(
        real_env, tmp_path, monkeypatch, failure):
    _seed_board(real_env)
    doc, version = _source_fixture(real_env, tmp_path, monkeypatch)
    requested_version = version
    if failure == "missing":
        with real_env.SessionLocal() as db:
            row = db.get(IngestedDocument, doc.id)
            db.delete(row)
            db.commit()
    elif failure == "foreign":
        with real_env.SessionLocal() as db:
            row = db.get(IngestedDocument, doc.id)
            row.workspace_id = "ws-foreign"
            db.commit()
    elif failure == "stale":
        requested_version = "ev4:" + "0" * 64
    else:
        with real_env.SessionLocal() as db:
            row = db.get(IngestedDocument, doc.id)
            row.freshness_status = "stale"
            db.commit()

    def wait(task_input, history, context):
        return ReActStep(
            thought="Need authorized source.",
            information_wait=InformationWaitRequest(
                question="Which source?", missing_fact="source"),
        )

    calls = _install_model(monkeypatch, [wait])
    started = _run(
        real_env, operation_id=f"generic-source-{failure}",
        parameters={"sync": True, "task_input": "Create a task"})
    assert started.status_code == 202, started.text
    data = started.json()["data"]
    answer = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer",
        json={
            "answer": "use source",
            "correlation_id": data["wait_receipt"]["correlation_id"],
            "source": {
                "document_id": doc.id,
                "source_version": requested_version,
            },
        },
    )
    assert answer.status_code in (404, 409, 422), answer.text
    job, payload = _job_payload(real_env, data["job_id"])
    assert job.status == "waiting"
    assert payload["wait_receipt"]["correlation_id"] == (
        data["wait_receipt"]["correlation_id"])
    assert len(calls) == 1


def test_dataset_source_answer_resumes_same_job_with_verified_effect(
        real_env, tmp_path, monkeypatch):
    import pandas as pd
    import core.sheet_dataset_service as catalog
    import core.canvas_capability_service as capability

    board_id, column_id = _seed_board(real_env)
    parquet = tmp_path / "dataset.parquet"
    pd.DataFrame([{
        "__sheet_row": 2,
        "po_id": "PO-DATASET-1",
        "amount": "7.50",
    }]).to_parquet(parquet, index=False)
    version = "dataset-v1"
    coverage = {
        "known": True, "truncated": False,
        "source_row_count": 1, "materialized_row_count": 1,
    }
    entry = {
        "id": "generic-dataset-entry",
        "dataset_name": "generic-dataset",
        "file_name": "dataset.parquet",
        "entity_name": "Sheet1",
        "source_kind": "file",
        "source": "onedrive",
        "external_id": "generic-dataset",
        "content_hash": version,
        "row_count": 1,
        "status": "active",
        "workspace_id": "ws1",
        "parquet_path": str(parquet),
        "coverage": coverage,
    }
    monkeypatch.setattr(
        catalog, "resolve_dataset_entry_scoped_sync",
        lambda *a, **k: {"state": "active", "entry": entry,
                         "candidates": []})
    monkeypatch.setattr(catalog, "connected_parquet_path", lambda item: parquet)
    monkeypatch.setattr(
        capability, "_assert_connected_source_access",
        lambda db, provider, user: {"status": "active"})
    monkeypatch.setattr(
        capability, "_validate_connected_coverage", lambda item: coverage)

    def wait(task_input, history, context):
        return ReActStep(
            thought="Need authorized dataset.",
            information_wait=InformationWaitRequest(
                question="Which dataset?", missing_fact="dataset"),
        )

    def resumed(task_input, history, context):
        source = context.get("information_source") or {}
        assert "PO-DATASET-1" in str(source.get("content") or "")
        assert source.get("source_version") == version
        return ReActStep(
            thought="Use dataset.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id,
                    "column_id": column_id,
                    "title": "Dataset-backed task",
                    "status": "backlog",
                },
            ),
        )

    def finished(task_input, history, context):
        return ReActStep(thought="Verified.", final_answer="Created.")

    _install_model(monkeypatch, [wait, resumed, finished])
    started = _run(
        real_env, operation_id="generic-dataset-source",
        parameters={"sync": True, "task_input": "Create a dataset-backed task"})
    assert started.status_code == 202, started.text
    data = started.json()["data"]
    answer = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer",
        json={
            "answer": "",
            "correlation_id": data["wait_receipt"]["correlation_id"],
            "source": {
                "dataset_name": "generic-dataset",
                "sheet": "Sheet1",
                "source": "onedrive",
                "external_id": "generic-dataset",
                "source_version": version,
            },
        },
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["data"]["job_status"] == "success"
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(
            BoardTask.title == "Dataset-backed task").count() == 1


def test_offline_actor_authority_change_refuses_source_replay(
        real_env, tmp_path, monkeypatch):
    """Accepted source material is not perpetual execution authority."""
    import api.agent_routes as routes
    from core.models import User

    _seed_board(real_env)
    doc, version = _source_fixture(real_env, tmp_path, monkeypatch)

    def wait(task_input, history, context):
        return ReActStep(
            thought="Need source.",
            information_wait=InformationWaitRequest(
                question="Which source?", missing_fact="source"),
        )

    calls = _install_model(monkeypatch, [wait])
    started = _run(
        real_env, operation_id="generic-source-offline-authority",
        parameters={"sync": True, "task_input": "Create a task"})
    data = started.json()["data"]
    body = {
        "answer": "priority high",
        "correlation_id": data["wait_receipt"]["correlation_id"],
        "source": {"document_id": doc.id, "source_version": version},
    }
    original = routes.resume_information_wait_action

    async def accepted_but_interrupted(*args, **kwargs):
        return {"handled": True, "resumed": False,
                "reason": "lead_interrupt_after_accept", "status": "waiting"}

    monkeypatch.setattr(
        routes, "resume_information_wait_action", accepted_but_interrupted)
    first = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer", json=body)
    assert first.status_code == 409, first.text
    monkeypatch.setattr(
        routes, "resume_information_wait_action", original)

    with real_env.SessionLocal() as db:
        actor = db.get(User, "member-1")
        actor.workspace_id = "ws-other"
        db.commit()

    replay = _client(real_env).post(
        f"/api/agents/a1/jobs/{data['job_id']}/answer", json=body)
    assert replay.status_code == 409, replay.text
    assert len(calls) == 1
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(
            BoardTask.title.like("Accepted answer %")).count() == 0
