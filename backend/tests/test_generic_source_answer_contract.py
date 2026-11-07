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
