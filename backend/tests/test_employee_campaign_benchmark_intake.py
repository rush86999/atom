"""Scratch acceptance: the held-out runner records benchmark evidence itself.

The test drives the real ``employee_g5_heldout_two_domain.py`` finish path with
a controlled API transport and a scratch SQLite world. The runner reads the
durable route decisions its transport hook wrote, binds the accepted provider
echoes to a completed ``AgentExecution`` and invokes the production producer.
The test never calls the producer, never opens a live provider or database, and
observes the result only through the durable execution row.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.employee_benchmark_evidence import (
    EVIDENCE_KEY,
    inspect_employee_benchmark_evidence,
    load_employee_benchmark_evidence,
)
from core.llm.model_provenance import (
    clear_route_attribution,
    get_route_attribution,
    set_echoed_response_model,
    set_requested_route,
    set_served_route,
)
from core.models import AgentExecution

RUN_ID = "run-heldout-scratch"
COMPLETED = datetime(2026, 11, 11, 18, 30, tzinfo=timezone.utc)
SERVED = {"provider": "ollama", "model": "llama3.1:8b-instruct-q4_K_M"}
REQUESTED = {"provider": "ollama", "model": "llama3.1:8b"}

RUNNER = (
    Path(__file__).resolve().parents[2]
    / "scripts" / "acceptance" / "employee_g5_heldout_two_domain.py"
)


def _runner_module():
    spec = importlib.util.spec_from_file_location(
        "employee_g5_heldout_runner_under_test", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _durable_assignment(artifact: Path):
    return {
        "run_id": RUN_ID,
        "assignment_id": "asg-heldout-scratch",
        "objective": "Reconcile INV-4491 and prepare the held-out review",
        "employee_id": "employee-1",
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "status": "completed",
        "completed_at": COMPLETED.isoformat(),
        "steps": [
            {
                "step_id": "quote",
                "adapter": "quote.calculate",
                "status": "applied",
                "result": {"value": "96.30", "currency": "USD"},
            },
            {
                "step_id": "reconcile",
                "adapter": "invoice.reconcile",
                "status": "applied",
                "result": {"value": "140.25", "currency": "USD"},
            },
            {
                "step_id": "wait",
                "adapter": "assignment.wait",
                "status": "applied",
                "waiting": {"correlation_id": "corr-heldout"},
            },
        ],
        "deliverables": [{
            "kind": "document",
            "status": "applied",
            "artifact_path": str(artifact),
            "sha256": __import__("hashlib").sha256(
                artifact.read_bytes()).hexdigest(),
        }],
        "completion_criteria": [{
            "kind": "business_result", "required": True,
            "criterion_id": "employee_result:objective"}],
        "provenance": {"agent_id": "agent-1"},
    }


def _seed_world(tmp_path, decisions=None):
    import sqlite3

    from docx import Document

    database = tmp_path / "campaign.db"
    artifact = tmp_path / "heldout-review.docx"
    document = Document()
    document.add_paragraph(
        "Held-out review: quote 96.30 USD; reconciled 140.25 USD.")
    document.save(str(artifact))

    assignment = _durable_assignment(artifact)
    if decisions is None:
        decisions = [
            {
            "kind": "employee_route",
            "stage": "employee_proposal",
            "attempt_id": "attempt-discovery",
            "accepted": True,
            "requested_route": dict(REQUESTED),
            "served_route": dict(SERVED),
            "response_identity": dict(SERVED),
            "mode": "pinned",
        },
        {
            "kind": "employee_route",
            "stage": "employee_adaptation",
            "attempt_id": "attempt-failed",
            "accepted": False,
            "requested_route": dict(REQUESTED),
            "served_route": None,
            "response_identity": None,
            "error_code": "provider_failure",
            "mode": "pinned",
        },
    ]
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "create table goal_runs (id text primary key, parameters text, "
            "decision_log text)")
        connection.execute(
            "insert into goal_runs (id, parameters, decision_log) "
            "values (?, ?, ?)",
            (
                RUN_ID,
                json.dumps({"task_lifecycle": {"assignment": assignment}}),
                json.dumps(decisions),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    state = {
        "phase": "start",
        "run_id": RUN_ID,
        "request": {},
        "response": {},
        "status": "waiting",
        "wait": {"correlation_id": "corr-heldout", "party": "warehouse"},
        "restart": {"status": "waiting", "same_wait": True},
        "benchmark_execution_id": f"employee-campaign-{RUN_ID}",
        "finish": {},
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "receiving-records-heldout.json").write_text(
        json.dumps({"po_id": "PO-7302", "received_quantity": "3"}))
    return database, artifact, state_path, fixtures


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):  # noqa: D401 — mirrors requests
        return None


class _ControlledTransport:
    """API responses only; no live app, provider or database is contacted."""

    def __init__(self, assignment):
        self.assignment = assignment

    def get(self, url, **_kwargs):
        return _Response({"assignment": self.assignment})

    def post(self, url, **_kwargs):
        if url.endswith("/documents/upload"):
            return _Response({"id": "doc-heldout"})
        if "/sources" in url:
            return _Response({
                "resolved_question_ids": ["q-receiving"],
                "status": "applied",
            })
        if "/responses/" in url:
            return _Response({"status": "applied"})
        if url.endswith("/advance"):
            return _Response({"assignment": self.assignment, "rounds": []})
        return _Response({"assignment": self.assignment})

    def close(self):
        return None


def test_accepted_transport_identity_is_recorded_not_requested():
    clear_route_attribution()
    set_requested_route(REQUESTED["provider"], REQUESTED["model"])
    # Identity comes from the provider's own response metadata, not from the
    # requested route and not from the served route by itself.
    set_echoed_response_model(SERVED["model"])
    set_served_route(SERVED["provider"], SERVED["model"])
    attribution = get_route_attribution()
    assert attribution["transport"]["accepted"] is True
    assert attribution["transport"]["response_identity"] == SERVED
    assert attribution["transport"]["requested_route"] == REQUESTED

    from api.assignment_routes import _routing_history_entry

    entry = _routing_history_entry(
        attribution, stage="employee_proposal", attempt_id="a-1")
    assert entry["accepted"] is True
    assert entry["response_identity"] == SERVED
    assert entry["served_route"] == SERVED
    assert entry["requested_route"] == REQUESTED
    clear_route_attribution()


def test_heldout_runner_finish_records_durable_evidence(
        tmp_path, monkeypatch):
    database, _artifact, state_path, fixtures = _seed_world(tmp_path)
    runner = _runner_module()
    monkeypatch.setattr(runner, "FIXTURES", fixtures)
    monkeypatch.setattr(runner, "token", lambda: "scratch-token")
    monkeypatch.setattr(
        runner, "requests",
        _ControlledTransport(_durable_assignment(
            _artifact)))
    monkeypatch.setenv("ATOM_EMPLOYEE_BENCHMARK_EVIDENCE", "1")
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setattr(sys, "argv", [
        str(RUNNER), "--phase", "finish",
        "--state", str(state_path),
        "--db", str(database),
        "--out", str(tmp_path / "out"),
    ])

    # The normal runner finish path, not a hand-written producer call. Its
    # named campaign checks do not gate evidence recording; the runner's
    # exit code still reflects the campaign checks.
    runner.main()

    engine = create_engine(f"sqlite:///{database}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as db:
            execution = db.get(
                AgentExecution, f"employee-campaign-{RUN_ID}")
            assert execution is not None
            assert execution.status == "completed"
            assert execution.completed_at == COMPLETED.replace(tzinfo=None)
            metadata = execution.metadata_json or {}
    finally:
        engine.dispose()

    inspection = inspect_employee_benchmark_evidence(metadata)
    assert inspection["rejected"] == []
    assert len(inspection["records"]) == 1
    record = inspection["records"][0]
    assert record["passed"] is True
    assert record["accuracy"] == 1.0
    assert record["provider"] == SERVED["provider"]
    assert record["model"] == SERVED["model"]
    assert record["observed_at"] == COMPLETED.isoformat()
    assert record["execution"]["id"] == f"employee-campaign-{RUN_ID}"
    assert load_employee_benchmark_evidence(metadata)[0]["model"] == (
        SERVED["model"])

    state = json.loads(state_path.read_text())
    assert state["benchmark_evidence"]["status"] == "recorded"
    assert (tmp_path / "out").exists()


def test_accepted_call_without_provider_echo_has_no_identity_fallback():
    """A served route is audit data; only the provider echo is identity."""
    from core.employee_campaign_intake import (
        accepted_calls_missing_identity,
        accepted_transport_calls,
        unique_served_identity,
    )

    decisions = [
        {
            "kind": "employee_route",
            "stage": "employee_proposal",
            "attempt_id": "attempt-served-only",
            "accepted": True,
            "requested_route": dict(REQUESTED),
            "served_route": dict(SERVED),
            "response_identity": None,
            "mode": "pinned",
        },
        {
            "kind": "employee_route",
            "stage": "employee_adaptation",
            "attempt_id": "attempt-partial-echo",
            "accepted": True,
            "requested_route": dict(REQUESTED),
            "served_route": dict(SERVED),
            "response_identity": {"provider": SERVED["provider"]},
            "mode": "pinned",
        },
    ]

    assert accepted_transport_calls(decisions) == []
    assert [
        item["call_id"]
        for item in accepted_calls_missing_identity(decisions)
    ] == ["attempt-served-only", "attempt-partial-echo"]

    # A remaining echo must not be promoted to the campaign identity while an
    # accepted call has none.
    assert unique_served_identity([
        {"call_id": "attempt-discovery",
         "response_identity": dict(SERVED)},
        {"call_id": "attempt-served-only", "response_identity": None},
    ]) is None


def test_finish_rejects_campaign_when_any_accepted_call_lacks_echo(
        tmp_path, monkeypatch):
    """One echoed call cannot stand in for an accepted call with no echo."""
    decisions = [
        {
            "kind": "employee_route",
            "stage": "employee_proposal",
            "attempt_id": "attempt-discovery",
            "accepted": True,
            "requested_route": dict(REQUESTED),
            "served_route": dict(SERVED),
            "response_identity": dict(SERVED),
            "mode": "pinned",
        },
        {
            "kind": "employee_route",
            "stage": "employee_adaptation",
            "attempt_id": "attempt-no-echo",
            "accepted": True,
            "requested_route": dict(REQUESTED),
            "served_route": dict(SERVED),
            "response_identity": None,
            "mode": "pinned",
        },
    ]
    database, artifact, state_path, fixtures = _seed_world(
        tmp_path, decisions=decisions)
    runner = _runner_module()
    monkeypatch.setattr(runner, "FIXTURES", fixtures)
    monkeypatch.setattr(runner, "token", lambda: "scratch-token")
    monkeypatch.setattr(
        runner, "requests",
        _ControlledTransport(_durable_assignment(artifact)))
    monkeypatch.setenv("ATOM_EMPLOYEE_BENCHMARK_EVIDENCE", "1")
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setattr(sys, "argv", [
        str(RUNNER), "--phase", "finish",
        "--state", str(state_path),
        "--db", str(database),
        "--out", str(tmp_path / "out"),
    ])

    runner.main()

    engine = create_engine(f"sqlite:///{database}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as db:
            execution = db.get(
                AgentExecution, f"employee-campaign-{RUN_ID}")
            assert execution is not None
            metadata = execution.metadata_json or {}
    finally:
        engine.dispose()

    # Nothing is written: the campaign is rejected as a whole, not scored
    # from the call that happened to echo its provider identity.
    assert EVIDENCE_KEY not in metadata
    inspection = inspect_employee_benchmark_evidence(metadata)
    assert inspection["records"] == []
    assert load_employee_benchmark_evidence(metadata) == []

    state = json.loads(state_path.read_text())
    result = state["benchmark_evidence"]
    assert result["status"] == "rejected"
    assert "served_identity_missing" in result["reasons"]
    assert [item["call_id"] for item in result["missing_identity_calls"]] == [
        "attempt-no-echo"]
