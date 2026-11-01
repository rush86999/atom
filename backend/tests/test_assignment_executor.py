"""Generic durable assignment executor controls.

Two materially different assignments run through the SAME executor and the
SAME production code. Only the task definitions, teaching snapshots, source
schemas and permissions differ. All storage is a scratch sqlite database.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import docx
import openpyxl
import pytest
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.assignment_executor import (
    AssignmentExecutor,
    ExternalOutcomeNotApplied,
    ExternalOutcomeUnknown,
    NeedsContext,
    WaitingForExternal,
    default_adapter_registry,
)
import core.assignment_quote  # noqa: F401,E402  (registers quote.calculate)
from core.assignment_plan import (
    new_assignment,
    new_deliverable,
    new_step,
    new_teaching_snapshot,
    normalize_standing_authority,
    step_by_id,
)
from core.goals.goal_run_events import ingest_event
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.task_lifecycle import TaskLifecycle
from core.task_outcome_contract import build_task_outcome


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/assignment.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=factory)
    goals = GoalService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    registry = default_adapter_registry.clone()
    return {
        "tmp": tmp_path,
        "runs": runs,
        "goals": goals,
        "factory": factory,
        "lifecycle": lifecycle,
        "executor": AssignmentExecutor(lifecycle, adapters=registry),
        "registry": registry,
    }


def _run(coro):
    return asyncio.run(coro)


def _make_workbook(path: Path) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Records"
    sheet.append(["Item", "Quantity", "Unit Price", "Status"])
    sheet.append(["A-1", 2, 10, "APPROVE"])
    sheet.append(["B-2", 3, 20, "REVIEW"])
    sheet.append(["C-3", 1, 99, "SKIP"])
    workbook.save(path)
    return path


def _teaching(**overrides):
    payload = {
        "revision": "teach-r1",
        "output_requirements": {
            "font_name": "Arial",
            "font_size": 11,
            "heading_order": ["Summary", "Findings", "Sources"],
        },
        "matched_context": {"business_category": "alpha"},
        "effective_lesson_ids": [{"id": "tp-1", "revision": 1}],
    }
    payload.update(overrides)
    return new_teaching_snapshot(**payload)


def _create(env, *, objective, steps, teaching, deliverables=None,
            authorized_actions=None, completion_criteria=None,
            employee="user-1", standing_authority=None, budget=None):
    plan = new_assignment(
        objective=objective,
        employee_id=employee,
        workspace_id="ws_assign",
        tenant_id="tenant_assign",
        teaching_snapshot=teaching,
        steps=steps,
        deliverables=deliverables or [],
        authorized_actions=authorized_actions or [],
        completion_criteria=completion_criteria or [],
        standing_authority=standing_authority,
        budget=budget or {"max_steps": 40, "max_attempts_per_step": 3,
                          "max_wall_seconds": 600},
    )
    record = env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}", objective, assignment=plan)
    return record["run_id"], plan


def _install_controlled_adapters(env, monkeypatch, outbox: Path):
    """Controlled technical adapters. No real send is possible."""
    async def request_fact(inputs, context):
        answers = " ".join(
            str(item.get("resolution") or "")
            for item in context.get("resolved_gaps") or [])
        if not answers.strip():
            raise NeedsContext({
                "concept": "external_fact",
                "reason": "the third-party value was not in the retrieved sources",
                "question": "What is the approved external reference value?",
                "affected_subjects": ["A-1", "B-2"],
                "checked_evidence": ["workbook:Records", "email:thread-1"],
                "next_retrieval": "read the authorized reply or supplier record",
                "resolver": "case owner",
                "kind": "business_decision",
                "waiting": {
                    "state": "waiting_for_external",
                    "party": "supplier",
                    "correlation_id": "corr-1",
                    "resume_on": "response",
                    "detail": "reply on thread-1",
                },
            })
        return {"status": "applied", "summary": "external fact recorded",
                "value": inputs.get("value")}

    async def assess(inputs, context):
        text = str(inputs.get("text") or "")
        answers = " ".join(
            str(item.get("resolution") or "")
            for item in context.get("resolved_gaps") or [])
        if "expiry" not in text.lower() and not answers.strip():
            raise NeedsContext({
                "concept": "expiry",
                "reason": "the document does not state an expiry",
                "question": "What expiry date applies to this qualification?",
                "affected_subjects": ["record-1"],
                "checked_evidence": ["document:qualification"],
                "next_retrieval": "ask the qualification owner",
                "resolver": "qualification owner",
                "kind": "missing_evidence",
                "waiting": {
                    "state": "waiting_for_person",
                    "party": "qualification owner",
                    "correlation_id": "corr-2",
                    "resume_on": "answer",
                    "detail": "qualification expiry",
                },
            })
        decision = "CLEAR" if "active" in text.lower() else "HOLD"
        return {
            "status": "applied",
            "summary": f"decision {decision}",
            "value": decision,
            "decision": decision,
        }

    async def outbox_send(inputs, context):
        outbox.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "operation_id": (context.get("step") or {}).get("operation_id"),
            "to": inputs.get("to"),
            "subject": inputs.get("subject"),
            "body": inputs.get("body"),
            "payload_sha256": None,
        }
        lines = []
        if outbox.exists():
            lines = [json.loads(line) for line in outbox.read_text().splitlines()
                     if line.strip()]
        if any(item.get("operation_id") == record["operation_id"]
               for item in lines):
            return {"status": "applied", "summary": "already in outbox",
                    "provider_state": "sent",
                    "provider_ref": record["operation_id"]}
        lines.append(record)
        outbox.write_text("\n".join(json.dumps(item) for item in lines) + "\n")
        if inputs.get("crash_after_accept"):
            raise ExternalOutcomeUnknown(
                "provider accepted before the worker lost the response",
                evidence=f"outbox:{record['operation_id']}")
        return {
            "status": "applied",
            "summary": "provider accepted",
            "provider_state": "sent",
            "provider_ref": record["operation_id"],
        }

    def outbox_prepare(inputs, context):
        return {
            "payload": {
                "to": inputs.get("to"),
                "subject": inputs.get("subject"),
                "body": inputs.get("body"),
                "attachment": inputs.get("attachment"),
            },
            "artifact_revision": inputs.get("draft_revision"),
            "requested_by": "user-1",
        }

    registry = env["registry"]
    registry.register("test.request_fact", request_fact)
    registry.register("test.assess", assess)
    registry.register(
        "test.outbox.send", outbox_send, prepare=outbox_prepare,
        metadata={
            "effect": "external",
            "required_actions": ["outbound"],
            "allow_standing_authorization": True,
        })

    async def fake_hitl(**kwargs):
        return {"status": "PAUSED", "action_id": f"hitl-{uuid.uuid4().hex[:8]}"}

    monkeypatch.setattr(
        "core.intervention_service.intervention_service.request_intervention",
        fake_hitl)


def _dump_evidence(env, run_id: str, name: str) -> None:
    evidence = os.getenv("ATOM_ASSIGNMENT_EVIDENCE_DIR")
    if not evidence:
        return
    root = Path(evidence)
    root.mkdir(parents=True, exist_ok=True)
    record = env["lifecycle"].get_task(run_id) or {}
    decisions = env["runs"].get_decisions(run_id)
    payload = {
        "run_id": run_id,
        "status": env["executor"].status(run_id),
        "task_revision": record.get("task_revision"),
        "operations": record.get("operations"),
        "deliveries": record.get("deliveries"),
        "decisions": decisions,
    }
    (root / f"{name}_evidence.json").write_text(
        json.dumps(payload, indent=1, default=str))


def _commercial_assignment(env, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    evidence = os.getenv("ATOM_ASSIGNMENT_EVIDENCE_DIR")
    if evidence:
        root = Path(evidence)
        root.mkdir(parents=True, exist_ok=True)
        tmp_path = root
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(root))
    outbox = tmp_path / "outbox.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)
    workbook = _make_workbook(tmp_path / "records.xlsx")
    artifact = tmp_path / "commercial.docx"
    teaching = _teaching(
        decision_schema=[{"id": "APPROVE"}, {"id": "REVIEW"}],
        output_requirements={
            "font_name": "Arial", "font_size": 11,
            "heading_order": ["Summary", "Findings", "Sources"],
        },
    )
    steps = [
        new_step(
            step_id="read", title="Read eligible records",
            operation_type="retrieve", adapter="workbook.read",
            inputs={
                "path": str(workbook), "sheet": "Records",
                "columns": ["Item", "Quantity", "Unit Price", "Status"],
                "filters": [{"column": "Status", "operator": "in",
                             "value": ["APPROVE", "REVIEW"]}],
            },
            effect="read_only",
        ),
        new_step(
            step_id="calc", title="Calculate the eligible total",
            operation_type="calculate", adapter="formula.calculate",
            depends_on=["read"],
            inputs={
                "expression": "q1*p1 + q2*p2",
                "bindings": {
                    "q1": {"$ref": "read.rows.0.Quantity"},
                    "p1": {"$ref": "read.rows.0.Unit Price"},
                    "q2": {"$ref": "read.rows.1.Quantity"},
                    "p2": {"$ref": "read.rows.1.Unit Price"},
                },
                "output_unit": "USD",
                "origin": {"source": "records.xlsx"},
            },
            effect="local",
        ),
        new_step(
            step_id="doc", title="Render the commercial response",
            operation_type="present", adapter="artifact.document",
            depends_on=["calc", "read"],
            inputs={
                "path": str(artifact), "title": "Commercial Response",
                "content": (
                    "## Findings\n\nEligible records were read from the "
                    "authorized workbook.\n\n## Summary\n\nTotal: "
                    "${calc.value} ${calc.unit}\n\n## Sources\n\n- Records"),
            },
            effect="local",
        ),
        new_step(
            step_id="draft", title="Prepare the reply draft",
            operation_type="outbound", adapter="email.draft",
            depends_on=["doc"],
            inputs={
                "to": ["test-recipient@example.invalid"],
                "subject": "Commercial response",
                "body": "Total: ${calc.value} ${calc.unit}. See attachment.",
                "deliverable_id": "del-draft",
            },
            effect="local",
        ),
        new_step(
            step_id="fact", title="Resolve the external reference",
            operation_type="retrieve", adapter="test.request_fact",
            depends_on=["read"],
            inputs={"value": "REF-9"}, effect="read_only",
        ),
        new_step(
            step_id="send", title="Send the approved reply",
            operation_type="outbound", adapter="test.outbox.send",
            depends_on=["draft", "fact"],
            inputs={
                "to": ["test-recipient@example.invalid"],
                "subject": "Commercial response",
                "body": "Total: ${calc.value} ${calc.unit}. See attachment.",
                "draft_revision": {"$ref": "draft.artifact.revision"},
                "deliverable_id": "del-sent",
            },
            effect="external", approval_required=True,
            approval_purpose="Send the prepared commercial response",
        ),
    ]
    deliverables = [
        new_deliverable(
            deliverable_id="del-doc", kind="document",
            description="Formatted commercial response", step_id="doc"),
        new_deliverable(
            deliverable_id="del-draft", kind="email_draft",
            description="Reply draft", step_id="draft"),
        new_deliverable(
            deliverable_id="del-sent", kind="email",
            description="Provider-accepted reply", step_id="send"),
    ]
    return _create(
        env, objective="Prepare the commercial response", steps=steps,
        teaching=teaching, deliverables=deliverables,
        authorized_actions=["retrieve", "present", "calculate", "edit",
                            "outbound"],
        completion_criteria=[
            {"kind": "artifact_verified"},
            {"kind": "provider_accepted"},
        ],
    ), outbox, artifact


def _eligibility_assignment(env, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    evidence = os.getenv("ATOM_ASSIGNMENT_EVIDENCE_DIR")
    if evidence:
        root = Path(evidence) / "eligibility"
        root.mkdir(parents=True, exist_ok=True)
        tmp_path = root
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(root))
    outbox = tmp_path / "outbox-eligibility.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)
    source = tmp_path / "qualification.txt"
    source.write_text(
        "Subject: record-1\nStatus: Active\nQualification: Q-2\n"
        "The subject meets the active standard.\n")
    artifact = tmp_path / "eligibility.docx"
    teaching = new_teaching_snapshot(
        revision="teach-b1",
        decision_schema=[{"id": "CLEAR"}, {"id": "HOLD"}],
        output_requirements={
            "font_name": "Times New Roman", "font_size": 12,
            "heading_order": ["Summary", "Sources"],
        },
        matched_context={"business_category": "beta"},
    )
    steps = [
        new_step(
            step_id="read", title="Read the qualification record",
            operation_type="retrieve", adapter="document.read",
            inputs={"path": str(source)}, effect="read_only"),
        new_step(
            step_id="assess", title="Apply the qualification rules",
            operation_type="calculate", adapter="test.assess",
            depends_on=["read"], inputs={"text": "${read.text}"},
            effect="local"),
        new_step(
            step_id="doc", title="Render the assessment package",
            operation_type="present", adapter="artifact.document",
            depends_on=["assess"],
            inputs={
                "path": str(artifact), "title": "Eligibility Assessment",
                "content": (
                    "## Sources\n\n- Qualification record\n\n## Summary\n\n"
                    "Decision: ${assess.value}"),
            },
            effect="local"),
        new_step(
            step_id="notify", title="Send the assessment notice",
            operation_type="outbound", adapter="test.outbox.send",
            depends_on=["doc"],
            inputs={
                "to": ["reviewer@example.invalid"],
                "subject": "Assessment ready",
                "body": "Decision: ${assess.value}",
                "deliverable_id": "del-notice",
            },
            effect="external", approval_required=True,
            approval_purpose="Notify the reviewer of the assessment",
        ),
    ]
    return _create(
        env, objective="Prepare the eligibility assessment", steps=steps,
        teaching=teaching,
        deliverables=[
            new_deliverable(
                deliverable_id="del-doc", kind="document",
                description="Assessment package", step_id="doc"),
            new_deliverable(
                deliverable_id="del-notice", kind="email",
                description="Assessment notice", step_id="notify"),
        ],
        authorized_actions=["retrieve", "calculate", "present", "outbound"],
        completion_criteria=[{"kind": "artifact_verified"}],
    ), outbox, artifact


def test_two_materially_different_assignments_same_executor(env, monkeypatch):
    (run_a, _), outbox_a, doc_a = _commercial_assignment(
        env, env["tmp"], monkeypatch)
    executor = env["executor"]

    waiting = _run(executor.execute(run_a))
    assert waiting["assignment"]["status"] == "waiting", waiting
    assert step_by_id(
        env["lifecycle"].get_assignment(run_a), "doc")["status"] == "applied", waiting
    assert step_by_id(
        env["lifecycle"].get_assignment(run_a), "send")["status"] == "pending"
    assert outbox_a.exists() is False

    # Restart while waiting: same durable run, no model loop.
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    again = _run(restarted.resume(run_a))
    assert again["assignment"]["status"] == "waiting"

    record = env["lifecycle"].get_task(run_a)
    gap = next(item for item in record["task_revision"]["unresolved"]
               if item["status"] == "open")
    executor.resolve_gap(
        run_a, gap["question_id"], resolution="REF-9",
        resolved_by="case owner", evidence="authorized reply")
    approval = _run(executor.execute(run_a))
    assert approval["assignment"]["status"] == "waiting"
    send_step = step_by_id(env["lifecycle"].get_assignment(run_a), "send")
    assert send_step["status"] == "awaiting_approval", approval

    approved = executor.approve_step(
        run_a, "send", approved_by="owner")
    assert approved["status"] == "approved"
    completed = _run(executor.execute(run_a))
    assert completed["assignment"]["status"] == "completed", completed
    _dump_evidence(env, run_a, "commercial")
    assert outbox_a.exists() and len(
        [line for line in outbox_a.read_text().splitlines() if line]) == 1

    # Duplicate approval/execute cannot duplicate the effect.
    executor.approve_step(run_a, "send", approved_by="owner")
    _run(executor.execute(run_a))
    assert len([line for line in outbox_a.read_text().splitlines()
                if line]) == 1

    document = docx.Document(str(doc_a))
    headings = [p.text for p in document.paragraphs
                if p.style.name.startswith("Heading")]
    assert headings.index("Summary") < headings.index("Findings")
    assert document.styles["Normal"].font.name == "Arial"

    # Scenario B: different records, different decision labels, different
    # document schema and approver. Same executor code.
    (env["tmp"] / "b").mkdir(exist_ok=True)
    (run_b, _), outbox_b, doc_b = _eligibility_assignment(
        env, env["tmp"] / "b", monkeypatch)
    waiting_b = _run(executor.execute(run_b))
    assert waiting_b["assignment"]["status"] == "waiting"
    record_b = env["lifecycle"].get_task(run_b)
    gap_b = next(item for item in record_b["task_revision"]["unresolved"]
                 if item["status"] == "open")
    executor.resolve_gap(
        run_b, gap_b["question_id"], resolution="2027-01-01",
        resolved_by="qualification owner")
    approval_b = _run(executor.execute(run_b))
    assert approval_b["assignment"]["status"] == "waiting"
    assert step_by_id(
        env["lifecycle"].get_assignment(run_b), "notify")["status"] == (
            "awaiting_approval"), approval_b
    assert executor.approve_step(
        run_b, "notify", approved_by="reviewer")["status"] == "approved"
    completed_b = _run(executor.execute(run_b))
    assert completed_b["assignment"]["status"] == "completed", completed_b
    _dump_evidence(env, run_b, "eligibility")
    text = "\n".join(p.text for p in docx.Document(str(doc_b)).paragraphs)
    assert "Decision: CLEAR" in text
    assert outbox_b.exists()


def test_changed_artifact_invalidates_approval(env, monkeypatch):
    (run_id, _), outbox, _ = _commercial_assignment(
        env, env["tmp"], monkeypatch)
    executor = env["executor"]
    _run(executor.execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    gap = next(item for item in record["task_revision"]["unresolved"]
               if item["status"] == "open")
    executor.resolve_gap(
        run_id, gap["question_id"], resolution="REF-9")
    _run(executor.execute(run_id))
    executor.approve_step(run_id, "send", approved_by="owner")

    # Change the bound body after approval; the next run must refuse to send
    # and request a fresh approval instead.
    def compute(record, assignment):
        step = step_by_id(assignment, "send")
        step["inputs"]["body"] = "Changed total. See attachment."
        return assignment, {}

    env["lifecycle"].mutate_assignment(
        run_id, compute, rationale="changed body")
    result = _run(executor.execute(run_id))
    assert result["assignment"]["status"] == "waiting"
    assert not outbox.exists() or not outbox.read_text().strip()
    step = step_by_id(env["lifecycle"].get_assignment(run_id), "send")
    assert step["status"] == "awaiting_approval"


def test_provider_accepted_then_worker_lost_is_reconciled_not_resent(
        env, monkeypatch):
    outbox = env["tmp"] / "uncertain.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)
    teaching = _teaching()
    source = _make_workbook(env["tmp"] / "u.xlsx")
    steps = [
        new_step(step_id="read", title="read", operation_type="retrieve",
                 adapter="workbook.read",
                 inputs={"path": str(source)}, effect="read_only"),
        new_step(step_id="send", title="send", operation_type="outbound",
                 adapter="test.outbox.send", depends_on=["read"],
                 inputs={"to": ["x@example.invalid"], "subject": "s",
                         "body": "b", "crash_after_accept": True},
                 effect="external", approval_required=True),
    ]
    run_id, _ = _create(
        env, objective="Uncertain effect", steps=steps, teaching=teaching)
    executor = env["executor"]
    _run(executor.execute(run_id))
    executor.approve_step(run_id, "send", approved_by="owner")
    result = _run(executor.execute(run_id))
    assert result["assignment"]["status"] == "blocked"
    assert len(outbox.read_text().strip().splitlines()) == 1
    send_step = step_by_id(env["lifecycle"].get_assignment(run_id), "send")
    assert send_step["status"] == "uncertain"
    operation = next(op for op in env["lifecycle"].get_task(run_id)["operations"]
                     if op["step_id"] == "send")
    assert operation["needs_reconciliation"] is True

    executor.reconcile_step(
        run_id, "send", "applied",
        evidence="the outbox record proves provider acceptance",
        evidence_ref=str(outbox))
    _run(executor.execute(run_id))
    assert len(outbox.read_text().strip().splitlines()) == 1


def test_cancellation_prevents_unstarted_effect(env, monkeypatch):
    (run_id, _), outbox, _ = _commercial_assignment(
        env, env["tmp"], monkeypatch)
    executor = env["executor"]
    _run(executor.execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    gap = next(item for item in record["task_revision"]["unresolved"]
               if item["status"] == "open")
    executor.resolve_gap(
        run_id, gap["question_id"], resolution="REF-9")
    _run(executor.execute(run_id))
    executor.approve_step(run_id, "send", approved_by="owner")
    executor.cancel(run_id, reason="owner cancelled", cancelled_by="owner")
    result = _run(executor.execute(run_id))
    assert result["assignment"]["status"] == "cancelled"
    assert not outbox.exists() or not outbox.read_text().strip()


def test_external_reply_matches_exact_correlation_once(env):
    async def wait_reply(inputs, context):
        step = context.get("step") or {}
        if step.get("external_response"):
            return {
                "status": "applied",
                "summary": "reply received as evidence",
                "value": step["external_response"].get("response"),
            }
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "party": "supplier",
            "correlation_id": "thread-1",
            "resume_on": "response",
            "detail": "authorized reply on thread-1",
        })

    env["registry"].register("test.wait_reply", wait_reply)
    default_adapter_registry.register("test.wait_reply", wait_reply)
    steps = [new_step(
        step_id="wait", title="Wait for the authorized reply",
        operation_type="retrieve", adapter="test.wait_reply",
        effect="read_only")]
    run_id, _ = _create(
        env, objective="Wait for a reply", steps=steps,
        teaching=_teaching())
    executor = env["executor"]
    first = _run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting"
    assert (env["runs"].get_run(run_id) or {}).get("status") == "waiting"

    wrong = _run(ingest_event(
        {"event": "email", "correlation_id": "thread-10",
         "summary": "unrelated"},
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=env["factory"]))
    assert wrong["woke"] == []
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")["status"] == (
            "waiting")

    # Restart while waiting does not turn a durable wait into a failure.
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    again = _run(restarted.resume(run_id))
    assert again["assignment"]["status"] == "waiting"
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")["waiting"][
            "correlation_id"] == "thread-1"

    exact = _run(ingest_event(
        {"event": "email", "correlation_id": "thread-1",
         "message_id": "msg-1", "source": "outlook",
         "summary": "approved reference REF-9"},
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=env["factory"]))
    assert exact["woke"] == [run_id]
    wait_step = step_by_id(env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "applied", wait_step.get("failure")
    duplicate = _run(ingest_event(
        {"event": "email", "correlation_id": "thread-1",
         "message_id": "msg-1", "source": "outlook",
         "summary": "approved reference REF-9"},
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=env["factory"]))
    assert duplicate["woke"] == []


def test_action_dispatched_alone_is_not_provider_acceptance():
    outcome = build_task_outcome(
        objective="send",
        completion_criteria=[{"kind": "provider_accepted"}],
        delivery={"delivered": True},
        objective_met=None,
    )
    assert outcome["objective_met"] is not True

    accepted = build_task_outcome(
        objective="send",
        completion_criteria=[{"kind": "provider_accepted"}],
        delivery={
            "provider_accepted": True,
            "provider_ref": "graph-202",
            "delivered": False,
        },
        objective_met=None,
    )
    assert accepted["objective_met"] is True

    missing_ref = build_task_outcome(
        objective="send",
        completion_criteria=[{"kind": "provider_accepted"}],
        delivery={"provider_accepted": True, "provider_ref": None},
        objective_met=None,
    )
    assert missing_ref["objective_met"] is not True


def test_assignment_approval_binding_cannot_be_rebound():
    from types import SimpleNamespace

    from api.approvals_routes import _validate_assignment_approval_payload

    action = SimpleNamespace(
        action_type="assignment_approval",
        params={"run_id": "r1", "step_id": "s1",
                "payload_sha256": "abc", "artifact_revision": "rev-1"},
    )
    _validate_assignment_approval_payload(
        action, {"payload_sha256": "abc", "artifact_revision": "rev-1"})
    with pytest.raises(Exception):
        _validate_assignment_approval_payload(
            action, {"payload_sha256": "different"})
    with pytest.raises(Exception):
        _validate_assignment_approval_payload(
            action, {"artifact_revision": "rev-2"})


def test_stale_task_revision_prevents_dispatch(env):
    steps = [new_step(
        step_id="read", title="Read", operation_type="retrieve",
        adapter="workbook.read",
        inputs={"path": str(_make_workbook(env["tmp"] / "stale.xlsx"))},
        effect="read_only")]
    run_id, _ = _create(
        env, objective="Stale revision", steps=steps, teaching=_teaching())
    with pytest.raises(Exception):
        _run(env["executor"].execute(run_id, expected_task_revision=99))


def test_failed_prerequisite_blocks_downstream_effect(env, monkeypatch):
    outbox = env["tmp"] / "prereq-outbox.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)

    async def fail(inputs, context):
        return {"status": "failed", "message": "source rejected",
                "error_class": "source_rejected"}

    env["registry"].register("test.fail", fail)
    steps = [
        new_step(step_id="read", title="Read", operation_type="retrieve",
                 adapter="test.fail", effect="read_only"),
        new_step(step_id="send", title="Send", operation_type="outbound",
                 adapter="test.outbox.send", depends_on=["read"],
                 inputs={"to": ["x@example.invalid"], "subject": "s",
                         "body": "b"},
                 effect="external", approval_required=True),
    ]
    run_id, _ = _create(
        env, objective="Blocked downstream", steps=steps,
        teaching=_teaching())
    result = _run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] in ("failed", "partial")
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "send")["status"] == "pending"
    assert not outbox.exists()


def test_crash_after_wake_before_advance_recovers(env):
    async def wait_reply(inputs, context):
        step = context.get("step") or {}
        if step.get("external_response"):
            return {"status": "applied", "summary": "reply recorded"}
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "correlation_id": "thread-crash",
            "resume_on": "response",
            "detail": "reply on thread-crash",
        })

    env["registry"].register("test.wait_crash", wait_reply)
    default_adapter_registry.register("test.wait_crash", wait_reply)
    steps = [new_step(
        step_id="wait", title="Wait", operation_type="retrieve",
        adapter="test.wait_crash", effect="read_only")]
    run_id, _ = _create(
        env, objective="Crash after wake", steps=steps,
        teaching=_teaching())
    executor = env["executor"]
    _run(executor.execute(run_id))
    # Simulate the wake bridge committing, then the process dying before
    # the successor step runs.
    wake = env["runs"].consume_wake(run_id, {
        "event": "email", "correlation_id": "thread-crash",
        "message_id": "msg-crash", "summary": "the reply is here",
        "source": "outlook"})
    assert wake["consumed"] is True
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")["status"] == "waiting"
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    _run(restarted.recover_ready_assignments())
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")["status"] == "applied"


def test_approval_after_cancellation_is_refused(env, monkeypatch):
    (run_id, _), _, _ = _commercial_assignment(
        env, env["tmp"], monkeypatch)
    executor = env["executor"]
    _run(executor.execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    gap = next(item for item in record["task_revision"]["unresolved"]
               if item["status"] == "open")
    executor.resolve_gap(
        run_id, gap["question_id"], resolution="REF-9")
    _run(executor.execute(run_id))
    executor.cancel(run_id, reason="cancelled", cancelled_by="owner")
    with pytest.raises(Exception):
        executor.approve_step(run_id, "send", approved_by="owner")


def _running_operation(env, monkeypatch, worker: str):
    from core import task_lifecycle as tl

    async def slow(inputs, context):
        return {"status": "applied", "summary": "slow step"}

    env["registry"].register("test.slow", slow)
    steps = [new_step(
        step_id="slow", title="Slow step", operation_type="calculate",
        adapter="test.slow", effect="read_only")]
    run_id, plan = _create(
        env, objective="Slow assignment", steps=steps,
        teaching=_teaching())
    operation = env["lifecycle"].create_operation(
        run_id, op_type="calculate", requested_change="Slow step",
        idempotency_key=f"slow-{worker}",
        extra={
            "assignment_id": plan["assignment_id"],
            "step_id": "slow",
            "plan_revision": 1,
        })
    monkeypatch.setattr(tl, "_current_worker_fingerprint", lambda: worker)
    claimed = env["lifecycle"].claim_execution(
        run_id, operation["operation_id"])
    assert claimed["granted"] is True
    # Reflect the claim in the plan as a healthy in-flight step.
    def compute(record, assignment):
        step = step_by_id(assignment, "slow")
        step["status"] = "running"
        step["operation_id"] = operation["operation_id"]
        return assignment, {}

    env["lifecycle"].mutate_assignment(
        run_id, compute, rationale="test running step")
    return run_id, operation["operation_id"]


def test_ordinary_resume_leaves_healthy_running_operation_intact(env, monkeypatch):
    run_id, operation_id = _running_operation(env, monkeypatch, "worker-live")
    executor = env["executor"]
    _run(executor.resume(run_id))
    operation = next(
        op for op in env["lifecycle"].get_task(run_id)["operations"]
        if op["operation_id"] == operation_id)
    assert operation["status"] == "running"
    assert operation.get("claimed_by") == "worker-live"
    assert operation.get("claimed_task_revision") == 1


def test_recovery_without_worker_proof_does_not_assert_loss(env, monkeypatch):
    from core import task_lifecycle as tl

    run_id, operation_id = _running_operation(env, monkeypatch, "worker-old")
    monkeypatch.setattr(tl, "_current_worker_fingerprint",
                        lambda: "worker-new")
    executor = env["executor"]
    # A stale timestamp/lease is not proof: no lost_worker and no liveness
    # probe means the operation is left alone.
    marked = executor.mark_stranded_uncertain(run_id)
    assert marked == []
    operation = next(
        op for op in env["lifecycle"].get_task(run_id)["operations"]
        if op["operation_id"] == operation_id)
    assert operation["status"] == "running"


def test_recovery_names_previous_worker_and_marks_uncertain(env, monkeypatch):
    from core import task_lifecycle as tl

    run_id, operation_id = _running_operation(env, monkeypatch, "worker-old")
    monkeypatch.setattr(tl, "_current_worker_fingerprint",
                        lambda: "worker-new")
    executor = env["executor"]
    marked = executor.mark_stranded_uncertain(
        run_id, lost_worker="worker-old")
    assert len(marked) == 1
    operation = next(
        op for op in env["lifecycle"].get_task(run_id)["operations"]
        if op["operation_id"] == operation_id)
    assert operation["status"] == "uncertain"
    assert operation["needs_reconciliation"] is True
    assert operation["uncertainty_reason"].startswith("worker worker-old")


def test_liveness_probe_true_keeps_running_operation(env, monkeypatch):
    from core import task_lifecycle as tl

    run_id, operation_id = _running_operation(env, monkeypatch, "worker-old")
    monkeypatch.setattr(tl, "_current_worker_fingerprint",
                        lambda: "worker-new")
    executor = env["executor"]
    marked = executor.mark_stranded_uncertain(
        run_id, is_worker_live=lambda owner: True)
    assert marked == []
    operation = next(
        op for op in env["lifecycle"].get_task(run_id)["operations"]
        if op["operation_id"] == operation_id)
    assert operation["status"] == "running"


def test_two_concurrent_resume_requests_dispatch_once(env):
    calls = {"count": 0}

    async def slow(inputs, context):
        calls["count"] += 1
        await asyncio.sleep(0.15)
        return {"status": "applied", "summary": "one dispatch"}

    env["registry"].register("test.concurrent", slow)
    steps = [new_step(
        step_id="one", title="One effect", operation_type="calculate",
        adapter="test.concurrent", effect="read_only")]
    run_id, _ = _create(
        env, objective="Concurrent resume", steps=steps,
        teaching=_teaching())

    async def run_both():
        first = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
        second = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
        return await asyncio.gather(
            first.resume(run_id), second.resume(run_id))

    _run(run_both())
    assert calls["count"] == 1
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "one")["status"] == "applied"


def test_send_prepare_binds_attachment_bytes_not_just_ids():
    from core.assignment_executor import _outlook_send_prepare
    from core.task_lifecycle import _approval_payload_hash

    base = {
        "canvas_id": "canvas-1", "to": ["x@example.invalid"],
        "subject": "s", "body": "b", "attachment_ids": ["staged_abc"],
    }
    first = _outlook_send_prepare(
        {**base, "attachment_hashes": {"staged_abc": "a" * 64}}, {})
    second = _outlook_send_prepare(
        {**base, "attachment_hashes": {"staged_abc": "b" * 64}}, {})
    assert first["payload"]["attachment_hashes"] == {"staged_abc": "a" * 64}
    assert _approval_payload_hash(first["payload"]) != _approval_payload_hash(
        second["payload"])


def test_send_prepare_refuses_attachment_ids_without_hashes():
    from core.assignment_executor import _outlook_send_prepare

    with pytest.raises(NeedsContext) as exc:
        _outlook_send_prepare(
            {"canvas_id": "canvas-1", "to": ["x@example.invalid"],
             "subject": "s", "body": "b",
             "attachment_ids": ["staged_abc"]}, {})
    assert exc.value.gap.get("concept") == "attachment_binding"


def test_restart_after_artifact_creation_does_not_recreate_work(
        env, monkeypatch):
    """Interruption after the document exists: a new executor resumes from
    durable state, keeps the same artifact bytes, and only continues the
    unresolved wait/approval rather than rebuilding completed work."""
    import hashlib

    (run_id, _), outbox, artifact = _commercial_assignment(
        env, env["tmp"], monkeypatch)
    executor = env["executor"]
    first = _run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting"
    doc_step = step_by_id(env["lifecycle"].get_assignment(run_id), "doc")
    assert doc_step["status"] == "applied"
    before_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    before_mtime = artifact.stat().st_mtime_ns

    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    resumed = _run(restarted.resume(run_id))
    assert resumed["assignment"]["status"] == "waiting"
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == before_hash
    assert artifact.stat().st_mtime_ns == before_mtime
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "doc")["status"] == "applied"
    assert not outbox.exists() or not outbox.read_text().strip()

    record = env["lifecycle"].get_task(run_id)
    gap = next(item for item in record["task_revision"]["unresolved"]
               if item["status"] == "open")
    restarted.resolve_gap(
        run_id, gap["question_id"], resolution="REF-9",
        resolved_by="qualification owner")
    _run(restarted.execute(run_id))
    restarted.approve_step(run_id, "send", approved_by="owner")
    completed = _run(restarted.execute(run_id))
    assert completed["assignment"]["status"] == "completed"
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == before_hash
    assert len(outbox.read_text().strip().splitlines()) == 1


def _research_steps(tmp_path, *, required_fields=None):
    doc = tmp_path / "research-output.docx"
    return [
        new_step(
            step_id="research", title="Retrieve the missing reference",
            operation_type="retrieve", adapter="external.research",
            inputs={
                "action": "test.research.lookup",
                "arguments": {"key": "REF-9"},
                "required_fields": required_fields or ["value"],
                "purpose": "Find the approved external reference",
                "question": "What is the approved external reference?",
            },
            effect="read_only"),
        new_step(
            step_id="calc", title="Calculate from retrieved evidence",
            operation_type="calculate", adapter="formula.calculate",
            depends_on=["research"],
            inputs={
                "expression": "value * 2",
                "bindings": {"value": {"$ref": "research.data.value"}},
                "output_unit": "USD",
            },
            effect="local"),
        new_step(
            step_id="doc", title="Render the grounded response",
            operation_type="present", adapter="artifact.document",
            depends_on=["calc"],
            inputs={
                "path": str(doc), "title": "Research Response",
                "content": "## Summary\n\nTotal: ${calc.value} ${calc.unit}",
            },
            effect="local"),
    ], doc


def test_external_research_reads_action_result_as_evidence(env, monkeypatch):
    from core.action_registry import action_registry

    async def lookup(args, context):
        return {"value": 21, "source": "approved-readonly-source"}

    action_registry.register(
        "test.research.lookup", lookup, effects=[{"effect": "read"}])
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(env["tmp"]))
    steps, doc = _research_steps(env["tmp"])
    run_id, plan = _create(
        env, objective="Research then calculate", steps=steps,
        teaching=_teaching(), authorized_actions=["retrieve", "calculate", "present"],
        completion_criteria=[{"kind": "artifact_verified"}])
    result = _run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    text = "\n".join(p.text for p in docx.Document(str(doc)).paragraphs)
    assert "42" in text and "USD" in text
    research = step_by_id(env["lifecycle"].get_assignment(run_id), "research")
    assert research["result"]["evidence"][0]["kind"] == "external_information"
    assert research["result"]["evidence"][0]["source"] == "approved-readonly-source"
    assert env["lifecycle"].get_task(run_id)["assignment"][
        "teaching_snapshot"]["revision"] == "teach-r1"


def test_external_research_missing_result_is_typed_obligation_and_resumes(
        env, monkeypatch):
    from core.action_registry import action_registry

    async def lookup(args, context):
        return {"value": None, "source": "approved-readonly-source"}

    action_registry.register(
        "test.research.lookup", lookup, effects=[{"effect": "read"}])
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(env["tmp"]))
    steps, doc = _research_steps(env["tmp"])
    run_id, plan = _create(
        env, objective="Research missing reference", steps=steps,
        teaching=_teaching(), authorized_actions=["retrieve", "calculate", "present"],
        completion_criteria=[{"kind": "artifact_verified"}])
    first = _run(env["executor"].execute(run_id))
    assert first["assignment"]["status"] == "waiting"
    record = env["lifecycle"].get_task(run_id)
    gap = next(item for item in record["task_revision"]["unresolved"]
               if item["status"] == "open")
    assert gap["kind"] == "external_research"
    assert gap["concept"] == "external_research"
    assignment_id = record["assignment"]["assignment_id"]

    env["executor"].resolve_gap(
        run_id, gap["question_id"], resolution="21",
        resolved_by="owner", evidence="approved supplier record")
    resumed = _run(env["executor"].execute(run_id))
    assert resumed["assignment"]["status"] == "completed", resumed
    assert resumed["assignment"]["assignment_id"] == assignment_id
    research = step_by_id(env["lifecycle"].get_assignment(run_id), "research")
    assert research["result"]["evidence"][0]["source"] == "resolved_obligation"
    assert research["result"]["data"]["value"] == "21"
    text = "\n".join(p.text for p in docx.Document(str(doc)).paragraphs)
    assert "42" in text and "USD" in text


def test_external_research_rejects_write_actions(env):
    from core.action_registry import action_registry

    async def write_action(args, context):
        return {"value": 21}

    action_registry.register(
        "test.research.write", write_action, effects=[{"effect": "update"}])
    steps, _doc = _research_steps(env["tmp"])
    steps[0]["inputs"]["action"] = "test.research.write"
    run_id, _ = _create(
        env, objective="Reject write research", steps=steps,
        teaching=_teaching(), authorized_actions=["retrieve", "calculate", "present"],
        completion_criteria=[{"kind": "artifact_verified"}])
    result = _run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] in ("failed", "partial")
    research = step_by_id(env["lifecycle"].get_assignment(run_id), "research")
    assert research["failure"]["reason"] == "failed"
    assert "read-only" in research["failure"]["message"]


def test_controlled_outbox_applies_taught_email_protocol(tmp_path, monkeypatch):
    """The approved payload and the outbox bytes both carry the protocol."""
    outbox = tmp_path / "protocol-outbox.jsonl"
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTBOX", str(outbox))
    from core.assignment_controlled_transport import (
        _controlled_prepare,
        _controlled_send,
    )

    teaching = _teaching(output_requirements={
        "greeting": "Dear colleague,",
        "signature": "Sales team",
        "subject_prefix": "[Quote]",
    })
    inputs = {
        "to": ["buyer@example.invalid"],
        "subject": "Press brake total",
        "body": "Result: 400.00 USD",
    }
    context = {"teaching": teaching, "step": {"operation_id": "op-1"}}
    prepared = _controlled_prepare(inputs, context)
    assert prepared["payload"]["subject"] == "[Quote] Press brake total"
    assert prepared["payload"]["body"].startswith("Dear colleague,")
    assert "Sales team" in prepared["payload"]["body"]

    _run(_controlled_send(inputs, context))
    line = json.loads(outbox.read_text().strip())
    assert line["subject"] == "[Quote] Press brake total"
    assert line["body"].startswith("Dear colleague,")
    assert "Sales team" in line["body"]
    assert line["teaching_revision"] == "teach-r1"


def test_external_response_contradicting_source_fact_stays_waiting(env):
    """A reply that denies a fact the source already has is a conflict."""
    async def source(inputs, context):
        return {"status": "applied", "summary": "source read",
                "value": "400.00", "unit": "USD",
                "measure": "Price", "group_by": "currency",
                "values": [{"currency": "USD", "value": "400.00"}],
                "subtotals": {"USD": {"rows": 1, "value": "400.00"}}}

    async def wait_fact(inputs, context):
        step = context.get("step") or {}
        if step.get("external_response"):
            return {"status": "applied", "summary": "reply received",
                    "value": step["external_response"].get("response")}
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "party": "owner",
            "correlation_id": "corr-currency",
            "resume_on": "response",
            "detail": "currency confirmation",
            "fact": "currency",
        })

    env["registry"].register("test.source", source)
    env["registry"].register("test.wait_fact", wait_fact)
    steps = [
        new_step(
            step_id="source", title="Read source",
            operation_type="retrieve", adapter="test.source",
            inputs={"resource_binding": {"columns": ["Currency", "Price"]}},
            effect="read_only"),
        new_step(
            step_id="wait", title="Wait for currency",
            operation_type="retrieve", adapter="test.wait_fact",
            depends_on=["source"], effect="read_only"),
    ]
    run_id, _ = _create(
        env, objective="Wait on currency", steps=steps, teaching=_teaching())
    executor = env["executor"]
    first = _run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting"

    result = executor.record_external_response(
        run_id, "corr-currency",
        response="Currency unstated by source; report the total without a currency.")
    assert result["status"] == "conflict"
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "waiting"
    conflicts = (wait_step.get("waiting") or {}).get("conflicts") or []
    assert conflicts and conflicts[-1]["reason"] == "source_fact_conflict"
    assert "Currency unstated" in conflicts[-1]["response"]


def test_external_response_for_genuinely_missing_fact_resumes(env):
    """A missing fact that is absent from the source can close the wait."""
    async def source(inputs, context):
        return {"status": "applied", "summary": "source read",
                "value": "400.00", "unit": "USD"}

    async def wait_fact(inputs, context):
        step = context.get("step") or {}
        if step.get("external_response"):
            return {"status": "applied", "summary": "reply received",
                    "value": step["external_response"].get("response")}
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "party": "owner",
            "correlation_id": "corr-delivery",
            "resume_on": "response",
            "detail": "delivery term",
            "fact": "delivery_term",
        })

    env["registry"].register("test.source", source)
    env["registry"].register("test.wait_fact", wait_fact)
    steps = [
        new_step(
            step_id="source", title="Read source",
            operation_type="retrieve", adapter="test.source",
            inputs={"resource_binding": {"columns": ["Currency", "Price"]}},
            effect="read_only"),
        new_step(
            step_id="wait", title="Wait for delivery term",
            operation_type="retrieve", adapter="test.wait_fact",
            depends_on=["source"], effect="read_only"),
    ]
    run_id, _ = _create(
        env, objective="Wait on delivery term", steps=steps,
        teaching=_teaching())
    executor = env["executor"]
    first = _run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting"

    result = executor.record_external_response(
        run_id, "corr-delivery", response="FOB destination")
    assert result["status"] == "resumed"
    _run(executor.execute(run_id))
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "applied"
    assert wait_step["external_response"]["fact"] == "delivery_term"


def _wait_assignment(env, *, correlation: str, fact: str, source_values):
    async def source(inputs, context):
        return {"status": "applied", "summary": "source read",
                "value": "400.00", "unit": "USD",
                "measure": "Price", "group_by": "currency",
                "values": source_values,
                "subtotals": {
                    str(item.get("currency") or ""): {"rows": 1,
                                                      "value": item.get("value")}
                    for item in source_values
                }}

    async def wait_fact(inputs, context):
        step = context.get("step") or {}
        if step.get("external_response"):
            return {"status": "applied", "summary": "reply received",
                    "value": step["external_response"].get("response")}
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "party": "owner",
            "correlation_id": correlation,
            "resume_on": "response",
            "detail": f"{fact} confirmation",
            "fact": fact,
        })

    env["registry"].register("test.source", source)
    env["registry"].register("test.wait_fact", wait_fact)
    steps = [
        new_step(
            step_id="source", title="Read source",
            operation_type="retrieve", adapter="test.source",
            inputs={"resource_binding": {"columns": ["Currency", "Price"]}},
            effect="read_only"),
        new_step(
            step_id="wait", title=f"Wait for {fact}",
            operation_type="retrieve", adapter="test.wait_fact",
            depends_on=["source"], effect="read_only"),
    ]
    return _create(
        env, objective=f"Wait on {fact}", steps=steps, teaching=_teaching())


def test_blank_currency_value_accepts_authorized_resolution_and_survives_restart(env):
    run_id, _ = _wait_assignment(
        env, correlation="corr-blank", fact="currency",
        source_values=[{"currency": None, "value": "400.00"}])
    executor = env["executor"]
    first = _run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting"

    result = executor.record_external_response(
        run_id, "corr-blank", response="USD")
    assert result["status"] == "resumed"
    _run(executor.execute(run_id))
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "applied"
    assert wait_step["external_response"]["fact_resolution"]["status"] == "missing"
    assert "fact_confirmation" not in wait_step["external_response"]

    # Restart: the same completed wait is not dispatched a second time.
    before = len([
        op for op in env["lifecycle"].get_task(run_id)["operations"]
        if op.get("step_id") == "wait" and op.get("status") == "applied"
    ])
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    _run(restarted.resume(run_id))
    after = len([
        op for op in env["lifecycle"].get_task(run_id)["operations"]
        if op.get("step_id") == "wait" and op.get("status") == "applied"
    ])
    assert before == 1 and after == 1


def test_agreeing_currency_response_is_confirmation_not_conflict(env):
    run_id, _ = _wait_assignment(
        env, correlation="corr-agree", fact="currency",
        source_values=[{"currency": "USD", "value": "400.00"}])
    executor = env["executor"]
    _run(executor.execute(run_id))
    result = executor.record_external_response(
        run_id, "corr-agree", response="USD")
    assert result["status"] == "resumed"
    _run(executor.execute(run_id))
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "applied"
    confirmation = wait_step["external_response"]["fact_confirmation"]
    assert confirmation["reason"] == "source_fact_confirmed"
    assert confirmation["values"] == ["USD"]


def test_mixed_currency_values_require_record_specific_resolution(env):
    run_id, _ = _wait_assignment(
        env, correlation="corr-mixed", fact="currency",
        source_values=[{"currency": "USD", "value": "400.00"},
                       {"currency": None, "value": "100.00"}])
    executor = env["executor"]
    _run(executor.execute(run_id))
    result = executor.record_external_response(
        run_id, "corr-mixed", response="USD")
    assert result["status"] == "partial"
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "waiting"
    conflict = (wait_step["waiting"]["conflicts"] or [])[-1]
    assert conflict["reason"] == "source_fact_mixed"
    assert conflict["blank_subjects"]
    assert conflict["established_values"] == ["USD"]


def test_substring_replies_do_not_confirm_established_values(env):
    run_id, _ = _wait_assignment(
        env, correlation="corr-substring", fact="currency",
        source_values=[{"currency": "USD", "value": "400.00"}])
    executor = env["executor"]
    _run(executor.execute(run_id))
    for reply in ("Not USD; use EUR", "USDX"):
        result = executor.record_external_response(
            run_id, "corr-substring", response=reply)
        assert result["status"] == "conflict", (reply, result)
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "waiting"
    assert all(item["reason"] == "source_fact_conflict"
               for item in wait_step["waiting"]["conflicts"])


def test_numeric_substring_reply_is_not_agreement(env):
    run_id, _ = _wait_assignment(
        env, correlation="corr-number", fact="currency",
        source_values=[{"currency": "120", "value": "400.00"}])
    executor = env["executor"]
    _run(executor.execute(run_id))
    result = executor.record_external_response(
        run_id, "corr-number", response="20")
    assert result["status"] == "conflict"
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")["status"] == "waiting"


def test_explicit_typed_value_can_confirm_with_explanatory_text(env):
    run_id, _ = _wait_assignment(
        env, correlation="corr-explicit", fact="currency",
        source_values=[{"currency": "USD", "value": "400.00"}])
    executor = env["executor"]
    _run(executor.execute(run_id))
    result = executor.record_external_response(
        run_id, "corr-explicit", response="Use USD for this quote",
        value="USD")
    assert result["status"] == "resumed"
    _run(executor.execute(run_id))
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "applied"
    assert wait_step["external_response"]["fact_confirmation"][
        "reason"] == "source_fact_confirmed"


def _parquet_source(env, rows):
    import pandas as pd

    path = env["tmp"] / f"fact-{uuid.uuid4().hex[:8]}.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def test_fact_resolution_uses_only_accepted_rows(env):
    path = _parquet_source(env, {
        "Currency": ["USD", "EUR"],
        "__sheet_row": [2, 3],
    })
    accepted = {
        "status": "applied", "summary": "accepted row 2",
        "evidence": [{
            "path": str(path),
            "sheet_rows": [2],
            "selected_count": 1,
            "coverage": {"known": True, "source_row_count": 2,
                         "truncated": False},
        }],
        "selected_count": 1,
    }

    async def source(inputs, context):
        return accepted

    async def wait_fact(inputs, context):
        step = context.get("step") or {}
        if step.get("external_response"):
            return {"status": "applied", "summary": "reply received",
                    "value": step["external_response"].get("response")}
        raise WaitingForExternal({
            "event": "email", "state": "waiting_for_external",
            "party": "owner", "correlation_id": "corr-filtered",
            "resume_on": "response", "detail": "currency", "fact": "currency",
        })

    env["registry"].register("test.source", source)
    env["registry"].register("test.wait_fact", wait_fact)
    steps = [
        new_step(
            step_id="source", title="Read accepted row",
            operation_type="retrieve", adapter="test.source",
            inputs={"resource_binding": {
                "columns": ["Currency", "__sheet_row"]}},
            effect="read_only"),
        new_step(
            step_id="wait", title="Wait for currency",
            operation_type="retrieve", adapter="test.wait_fact",
            depends_on=["source"], effect="read_only"),
    ]
    run_id, _ = _create(
        env, objective="Filtered fact", steps=steps, teaching=_teaching())
    executor = env["executor"]
    _run(executor.execute(run_id))
    result = executor.record_external_response(
        run_id, "corr-filtered", response="EUR")
    assert result["status"] == "conflict"
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    conflict = wait_step["waiting"]["conflicts"][-1]
    assert conflict["established_values"] == ["USD"]
    assert conflict["subjects"] == ["row 2"]
    assert "EUR" not in conflict["established_values"]


def test_unreadable_evidence_is_not_treated_as_missing(env):
    async def source(inputs, context):
        return {
            "status": "applied", "summary": "source with missing file",
            "evidence": [{
                "path": str(env["tmp"] / "missing.parquet"),
                "sheet_rows": [2],
                "selected_count": 1,
                "coverage": {"known": True, "source_row_count": 1,
                             "truncated": False},
            }],
            "selected_count": 1,
        }

    async def wait_fact(inputs, context):
        raise WaitingForExternal({
            "event": "email", "state": "waiting_for_external",
            "party": "owner", "correlation_id": "corr-unreadable",
            "resume_on": "response", "detail": "currency", "fact": "currency",
        })

    env["registry"].register("test.source", source)
    env["registry"].register("test.wait_fact", wait_fact)
    steps = [
        new_step(
            step_id="source", title="Read source",
            operation_type="retrieve", adapter="test.source",
            inputs={"resource_binding": {
                "columns": ["Currency", "__sheet_row"]}},
            effect="read_only"),
        new_step(
            step_id="wait", title="Wait for currency",
            operation_type="retrieve", adapter="test.wait_fact",
            depends_on=["source"], effect="read_only"),
    ]
    run_id, _ = _create(
        env, objective="Unreadable fact", steps=steps, teaching=_teaching())
    executor = env["executor"]
    _run(executor.execute(run_id))
    result = executor.record_external_response(
        run_id, "corr-unreadable", response="USD")
    assert result["status"] == "unavailable"
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "waiting"
    assert wait_step["waiting"]["conflicts"][-1]["reason"] == (
        "source_fact_unavailable")


def test_incomplete_coverage_does_not_allow_ordinary_resolution(env):
    path = _parquet_source(env, {
        "Currency": ["USD"], "__sheet_row": [2],
    })

    async def source(inputs, context):
        return {
            "status": "applied", "summary": "truncated source",
            "evidence": [{
                "path": str(path), "sheet_rows": [2], "selected_count": 1,
                "coverage": {"known": True, "source_row_count": 500001,
                             "truncated": True},
            }],
            "selected_count": 1,
        }

    async def wait_fact(inputs, context):
        raise WaitingForExternal({
            "event": "email", "state": "waiting_for_external",
            "party": "owner", "correlation_id": "corr-incomplete",
            "resume_on": "response", "detail": "currency", "fact": "currency",
        })

    env["registry"].register("test.source", source)
    env["registry"].register("test.wait_fact", wait_fact)
    steps = [
        new_step(
            step_id="source", title="Read source",
            operation_type="retrieve", adapter="test.source",
            inputs={"resource_binding": {
                "columns": ["Currency", "__sheet_row"]}},
            effect="read_only"),
        new_step(
            step_id="wait", title="Wait for currency",
            operation_type="retrieve", adapter="test.wait_fact",
            depends_on=["source"], effect="read_only"),
    ]
    run_id, _ = _create(
        env, objective="Incomplete fact", steps=steps, teaching=_teaching())
    executor = env["executor"]
    _run(executor.execute(run_id))
    result = executor.record_external_response(
        run_id, "corr-incomplete", response="USD")
    assert result["status"] == "incomplete"
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "waiting"
    assert wait_step["waiting"]["conflicts"][-1]["reason"] == (
        "source_fact_incomplete")


def test_fact_evidence_branch_matrix(env):
    """Complete/truncated/missing/blank/conflicting/wrong-dimension evidence
    behaves consistently across inline, Parquet and aggregate receipts."""
    from core.assignment_executor import _source_fact_resolution

    def record(result, *, coverage=None, columns=None):
        binding = {
            "columns": columns or ["Currency", "__sheet_row"],
            "coverage": coverage or {
                "known": True, "source_row_count": 2, "truncated": False},
        }
        return {"assignment": {"steps": [{
            "step_id": "source", "status": "applied",
            "inputs": {"resource_binding": binding},
            "result": result,
        }]}}

    def inline(rows, accepted, *, truncated=False):
        return record({
            "rows": rows, "selected_count": len(accepted),
            "evidence": [{
                "sheet_rows": accepted, "selected_count": len(accepted),
                "coverage": {"known": True, "source_row_count": 2,
                             "truncated": truncated},
            }],
        }, coverage={"known": True, "source_row_count": 2,
                     "truncated": truncated})

    assert _source_fact_resolution(
        inline([{"__sheet_row": 2, "Currency": "USD"}], [2]),
        "currency")["status"] == "established"
    assert _source_fact_resolution(
        inline([{"__sheet_row": 2, "Currency": "USD"}], [2],
               truncated=True), "currency")["status"] == "incomplete"
    assert _source_fact_resolution(
        inline([{"__sheet_row": 2, "Currency": "USD"}], [2, 3]),
        "currency")["status"] == "incomplete"
    assert _source_fact_resolution(
        inline([{"__sheet_row": 2, "Currency": "USD"},
                {"__sheet_row": 3, "Currency": "EUR"}], [2]),
        "currency")["status"] == "incomplete"
    assert _source_fact_resolution(
        inline([{"__sheet_row": 2, "Currency": None}], [2]),
        "currency")["status"] == "missing"
    assert _source_fact_resolution(
        inline([{"__sheet_row": 2, "Currency": "USD"},
                {"__sheet_row": 3, "Currency": None}], [2, 3]),
        "currency")["status"] == "mixed"
    assert _source_fact_resolution(
        inline([{"__sheet_row": 2}], [2]), "currency")["status"] == (
            "incomplete")
    # Coverage may arrive only on the receipt evidence, not the binding.
    inline_evidence_truncated = {
        "assignment": {"steps": [{
            "step_id": "source", "status": "applied",
            "inputs": {"resource_binding": {
                "columns": ["Currency", "__sheet_row"]}},
            "result": {
                "rows": [{"__sheet_row": 2, "Currency": "USD"}],
                "selected_count": 1,
                "evidence": [{
                    "sheet_rows": [2], "selected_count": 1,
                    "coverage": {"known": True, "source_row_count": 2,
                                 "truncated": True},
                }],
            },
        }]}}
    assert _source_fact_resolution(
        inline_evidence_truncated, "currency")["status"] == "incomplete"
    inline_result_truncated = inline(
        [{"__sheet_row": 2, "Currency": "USD"}], [2])
    inline_result_truncated["assignment"]["steps"][0]["result"][
        "truncated"] = True
    assert _source_fact_resolution(
        inline_result_truncated, "currency")["status"] == "incomplete"

    path = _parquet_source(env, {
        "Currency": ["USD", "EUR"], "__sheet_row": [2, 3]})
    parquet = record({
        "evidence": [{
            "path": str(path), "sheet_rows": [2], "selected_count": 1,
            "coverage": {"known": True, "source_row_count": 2,
                         "truncated": False},
        }],
        "selected_count": 1,
    })
    assert _source_fact_resolution(parquet, "currency")["status"] == (
        "established")
    parquet_truncated = record({
        "evidence": [{
            "path": str(path), "sheet_rows": [2], "selected_count": 1,
            "coverage": {"known": True, "source_row_count": 2,
                         "truncated": True},
        }],
        "selected_count": 1,
    }, coverage={"known": True, "source_row_count": 2, "truncated": True})
    assert _source_fact_resolution(
        parquet_truncated, "currency")["status"] == "incomplete"
    missing_path = _parquet_source(env, {
        "Currency": ["USD"], "__sheet_row": [2]})
    parquet_missing = record({
        "evidence": [{
            "path": str(missing_path), "sheet_rows": [2, 3],
            "selected_count": 2,
            "coverage": {"known": True, "source_row_count": 3,
                         "truncated": False},
        }],
        "selected_count": 2,
    })
    assert _source_fact_resolution(parquet_missing, "currency")["status"] == (
        "incomplete")
    blank_path = _parquet_source(env, {
        "Currency": [None], "__sheet_row": [2]})
    parquet_blank = record({
        "evidence": [{
            "path": str(blank_path), "sheet_rows": [2], "selected_count": 1,
            "coverage": {"known": True, "source_row_count": 1,
                         "truncated": False},
        }],
        "selected_count": 1,
    })
    assert _source_fact_resolution(parquet_blank, "currency")["status"] == (
        "missing")
    mixed_path = _parquet_source(env, {
        "Currency": ["USD", None], "__sheet_row": [2, 3]})
    parquet_mixed = record({
        "evidence": [{
            "path": str(mixed_path), "sheet_rows": [2, 3],
            "selected_count": 2,
            "coverage": {"known": True, "source_row_count": 2,
                         "truncated": False},
        }],
        "selected_count": 2,
    })
    assert _source_fact_resolution(parquet_mixed, "currency")["status"] == (
        "mixed")
    parquet_unknown = record({
        "evidence": [{
            "path": str(path), "sheet_rows": [2], "selected_count": 1,
            "coverage": {"known": False, "source_row_count": 2,
                         "truncated": False},
        }],
        "selected_count": 1,
    }, coverage={"known": False, "source_row_count": 2,
                 "truncated": False})
    assert _source_fact_resolution(
        parquet_unknown, "currency")["status"] == "incomplete"
    parquet_population_truncated = record({
        "evidence": [{
            "path": str(path), "sheet_rows": [2], "selected_count": 2,
            "coverage": {"known": True, "source_row_count": 2,
                         "truncated": False},
        }],
        "selected_count": 2,
    })
    assert _source_fact_resolution(
        parquet_population_truncated, "currency")["status"] == "incomplete"

    aggregate = record({
        "measure": "Price", "group_by": "currency",
        "values": [{"currency": "USD", "value": "400.00"}],
    }, coverage={"known": True, "source_row_count": 1, "truncated": False})
    assert _source_fact_resolution(aggregate, "currency")["status"] == (
        "established")
    aggregate_population_truncated = record({
        "measure": "Price", "group_by": "currency",
        "values": [{"currency": "USD", "value": "400.00"}],
        "evidence": [{
            "sheet_rows": [2], "selected_count": 2,
            "coverage": {"known": True, "source_row_count": 2,
                         "truncated": False},
        }],
        "selected_count": 2,
    }, coverage={"known": True, "source_row_count": 2, "truncated": False})
    assert _source_fact_resolution(
        aggregate_population_truncated, "currency")["status"] == "incomplete"
    aggregate_truncated = record({
        "measure": "Price", "group_by": "currency",
        "values": [{"currency": "USD", "value": "400.00"}],
    }, coverage={"known": True, "source_row_count": 1, "truncated": True})
    assert _source_fact_resolution(
        aggregate_truncated, "currency")["status"] == "incomplete"
    aggregate_blank = record({
        "measure": "Price", "group_by": "currency",
        "values": [{"currency": None, "value": "400.00"}],
    }, coverage={"known": True, "source_row_count": 1, "truncated": False})
    assert _source_fact_resolution(aggregate_blank, "currency")["status"] == (
        "missing")
    aggregate_mixed = record({
        "measure": "Price", "group_by": "currency",
        "values": [{"currency": "USD", "value": "400.00"},
                   {"currency": None, "value": "100.00"}],
    }, coverage={"known": True, "source_row_count": 2, "truncated": False})
    assert _source_fact_resolution(aggregate_mixed, "currency")["status"] == (
        "mixed")
    aggregate_subtotals = record({
        "measure": "Price", "group_by": "currency",
        "subtotals": {"USD": {"value": "35.00"}},
    }, coverage={"known": True, "source_row_count": 1, "truncated": False})
    assert _source_fact_resolution(
        aggregate_subtotals, "currency")["status"] == "established"
    aggregate_values_unbound = record({
        "measure": "Price",
        "values": [{"currency": "USD", "value": "400.00"}],
    }, coverage={"known": True, "source_row_count": 1, "truncated": False})
    unbound = _source_fact_resolution(aggregate_values_unbound, "currency")
    assert unbound["status"] == "unavailable"
    assert unbound["reason"] == "aggregate_dimension_unbound"
    aggregate_other_dimension = record({
        "measure": "Price", "group_by": "Price",
        "values": [{"currency": "USD", "value": "400.00"}],
    }, coverage={"known": True, "source_row_count": 1, "truncated": False})
    other = _source_fact_resolution(aggregate_other_dimension, "currency")
    assert other["status"] == "unavailable"
    assert other["reason"] == "aggregate_dimension_unbound"
    aggregate_wrong_dimension = record({
        "measure": "Price", "subtotals": {"USD": {"value": "35.00"}},
    }, coverage={"known": True, "source_row_count": 1, "truncated": False},
        columns=["Price", "Currency", "__sheet_row"])
    wrong = _source_fact_resolution(aggregate_wrong_dimension, "price")
    assert wrong["status"] == "unavailable"
    assert wrong["reason"] == "aggregate_dimension_unbound"
    aggregate_no_measure = record({
        "values": [{"currency": "USD", "value": "400.00"}],
    }, coverage={"known": True, "source_row_count": 1, "truncated": False})
    no_measure = _source_fact_resolution(aggregate_no_measure, "currency")
    assert no_measure["status"] == "unavailable"
    assert no_measure["reason"] == "aggregate_measure_missing"


def _standing_send_steps(count, recipients, **step_overrides):
    steps = [new_step(
        step_id="read", title="Read", operation_type="retrieve",
        adapter="workbook.read",
        inputs={"path": str(step_overrides["workbook"]), "sheet": "Records"},
        effect="read_only")]
    for index in range(count):
        steps.append(new_step(
            step_id=f"send-{index + 1}", title=f"Send {index + 1}",
            operation_type="outbound", adapter="test.outbox.send",
            depends_on=["read"],
            inputs={
                "to": [recipients[index]],
                "subject": f"Standing {index + 1}",
                "body": "Bounded standing authority",
            },
            effect="external", approval_required=True,
            approval_purpose="Send the prepared response"))
    return steps


def test_bounded_standing_authority_covers_two_sends_without_approval(
        env, monkeypatch, tmp_path):
    outbox = tmp_path / "standing-outbox.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)
    workbook = _make_workbook(tmp_path / "standing.xlsx")
    grant = normalize_standing_authority(
        {"actions": ["outbound"], "max_effects": 2,
         "recipients": ["one@example.invalid", "two@example.invalid"]},
        granted_by="owner-1")
    run_id, _ = _create(
        env, objective="Two covered sends",
        steps=_standing_send_steps(
            2, ["one@example.invalid", "two@example.invalid"],
            workbook=workbook),
        teaching=_teaching(), authorized_actions=["retrieve", "outbound"],
        standing_authority=grant)

    result = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    effects = [json.loads(line) for line in outbox.read_text().splitlines()]
    assert result["assignment"]["status"] == "completed"
    assert len(effects) == 2
    assert {item["to"][0] for item in effects} == {
        "one@example.invalid", "two@example.invalid"}
    assert assignment["standing_authority"]["used_effects"] == 2
    assert assignment["standing_authority"]["status"] == "exhausted"
    for step in assignment["steps"]:
        if step["step_id"].startswith("send-"):
            assert step["status"] == "applied"
            receipt = step["standing_authority_receipt"]
            assert receipt["grant_id"] == grant["grant_id"]
            assert receipt["use"] in (1, 2)
            assert receipt["payload_sha256"]


def test_standing_authority_bound_falls_back_to_approval(
        env, monkeypatch, tmp_path):
    outbox = tmp_path / "standing-bound.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)
    workbook = _make_workbook(tmp_path / "standing-bound.xlsx")
    grant = normalize_standing_authority(
        {"actions": ["outbound"], "max_effects": 1,
         "recipients": ["one@example.invalid", "two@example.invalid"]},
        granted_by="owner-1")
    run_id, _ = _create(
        env, objective="One covered send then approval",
        steps=_standing_send_steps(
            2, ["one@example.invalid", "two@example.invalid"],
            workbook=workbook),
        teaching=_teaching(), authorized_actions=["retrieve", "outbound"],
        standing_authority=grant)

    result = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    effects = [json.loads(line) for line in outbox.read_text().splitlines()]
    by_id = {step["step_id"]: step for step in assignment["steps"]}
    assert len(effects) == 1
    assert effects[0]["to"] == ["one@example.invalid"]
    assert by_id["send-1"]["status"] == "applied"
    assert by_id["send-2"]["status"] == "awaiting_approval"
    assert assignment["standing_authority"]["used_effects"] == 1
    assert assignment["standing_authority"]["status"] == "exhausted"


def test_recipient_outside_the_grant_requires_approval(
        env, monkeypatch, tmp_path):
    outbox = tmp_path / "standing-recipient.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)
    workbook = _make_workbook(tmp_path / "standing-recipient.xlsx")
    grant = normalize_standing_authority(
        {"actions": ["outbound"], "max_effects": 1,
         "recipients": ["allowed@example.invalid"]},
        granted_by="owner-1")
    steps = _standing_send_steps(
        1, ["other@example.invalid"], workbook=workbook)
    run_id, _ = _create(
        env, objective="Recipient outside grant", steps=steps,
        teaching=_teaching(), authorized_actions=["retrieve", "outbound"],
        standing_authority=grant)

    _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert not outbox.exists() or not outbox.read_text().strip()
    assert step_by_id(assignment, "send-1")["status"] == "awaiting_approval"
    assert assignment["standing_authority"]["used_effects"] == 0


def test_expired_standing_authority_requires_approval(
        env, monkeypatch, tmp_path):
    outbox = tmp_path / "standing-expired.jsonl"
    _install_controlled_adapters(env, monkeypatch, outbox)
    workbook = _make_workbook(tmp_path / "standing-expired.xlsx")
    grant = normalize_standing_authority(
        {"actions": ["outbound"], "max_effects": 1,
         "recipients": ["one@example.invalid"],
         "expires_at": "2000-01-01T00:00:00+00:00"},
        granted_by="owner-1")
    run_id, _ = _create(
        env, objective="Expired grant",
        steps=_standing_send_steps(
            1, ["one@example.invalid"], workbook=workbook),
        teaching=_teaching(), authorized_actions=["retrieve", "outbound"],
        standing_authority=grant)

    _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert not outbox.exists() or not outbox.read_text().strip()
    assert step_by_id(assignment, "send-1")["status"] == "awaiting_approval"
    assert assignment["standing_authority"]["used_effects"] == 0


def test_cost_budget_stops_before_the_next_step(env):
    async def costed(inputs, context):
        return {"status": "applied", "summary": "costed work",
                "cost_usd": 10.0}

    env["registry"].register("test.cost", costed)
    steps = [
        new_step(step_id="cost", title="Costed work",
                 operation_type="calculate", adapter="test.cost",
                 effect="local"),
        new_step(step_id="after", title="After budget",
                 operation_type="retrieve", adapter="workbook.read",
                 depends_on=["cost"],
                 inputs={"path": str(_make_workbook(
                     env["tmp"] / "budget.xlsx")), "sheet": "Records"},
                 effect="read_only"),
    ]
    run_id, _ = _create(
        env, objective="Cost budget", steps=steps, teaching=_teaching(),
        budget={"max_steps": 40, "max_attempts_per_step": 3,
                "max_wall_seconds": 600, "max_cost_usd": 5})

    result = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert assignment["budget"]["cost_usd"] == 10.0
    assert step_by_id(assignment, "cost")["status"] == "applied"
    assert step_by_id(assignment, "after")["status"] == "failed"
    assert step_by_id(assignment, "after")["failure"]["reason"] == (
        "assignment_budget_exhausted")
    assert result["assignment"]["status"] in (
        "running", "blocked", "failed", "partial")


def _external_error_assignment(
        env, tmp_path, monkeypatch, name, handler, budget=None):
    outbox = tmp_path / f"{name}-outbox.jsonl"

    def prepare(inputs, context):
        return {
            "payload": {"to": inputs.get("to"),
                        "subject": inputs.get("subject"),
                        "body": inputs.get("body")},
            "requested_by": "user-1",
        }

    env["executor"].adapters.register(
        name, handler, prepare=prepare,
        metadata={"effect": "external", "required_actions": ["outbound"],
                  "allow_standing_authorization": False})
    steps = [new_step(
        step_id="send", title="External effect",
        operation_type="outbound", adapter=name,
        inputs={"to": ["test@example.invalid"], "subject": "S", "body": "B"},
        effect="external", approval_required=True,
        approval_purpose="Send the effect")]
    run_id, _ = _create(
        env, objective=name, steps=steps, teaching=_teaching(),
        authorized_actions=["outbound"], budget=budget)
    _run(env["executor"].execute(run_id))
    env["executor"].approve_step(run_id, "send", approved_by="owner")
    return run_id, outbox


def _outbox_records(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def test_post_effect_runtime_error_is_uncertain_not_failed_before_effect(
        env, tmp_path, monkeypatch):
    outbox = tmp_path / "post-effect-runtime.jsonl"

    async def writes_then_raises(inputs, context):
        outbox.write_text(json.dumps({"to": inputs.get("to")}) + "\n")
        raise RuntimeError("response parser failed after send")

    run_id, _ = _external_error_assignment(
        env, tmp_path, monkeypatch, "test.post_effect_runtime",
        writes_then_raises)

    _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    operation = next(op for op in record["operations"]
                     if op.get("step_id") == "send")
    step = step_by_id(record["assignment"], "send")
    assert len(_outbox_records(outbox)) == 1
    assert operation["status"] == "uncertain"
    assert operation["needs_reconciliation"] is True
    assert operation["receipt"]["observed_status"] == "uncertain"
    assert operation["receipt"]["reconciliation_required"] is True
    assert step["status"] == "uncertain"
    assert step["failure"]["reason"] == "external_outcome_unknown"

    # A retry must not resend a possibly-applied effect.
    _run(env["executor"].execute(run_id))
    assert len(_outbox_records(outbox)) == 1


def test_post_effect_timeout_is_uncertain_and_does_not_resend(
        env, tmp_path, monkeypatch):
    outbox = tmp_path / "post-effect-timeout.jsonl"

    async def writes_then_hangs(inputs, context):
        outbox.write_text(json.dumps({"to": inputs.get("to")}) + "\n")
        await asyncio.sleep(2)
        return {"status": "applied", "summary": "too late"}

    run_id, _ = _external_error_assignment(
        env, tmp_path, monkeypatch, "test.post_effect_timeout",
        writes_then_hangs,
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 0.5})
    _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    operation = next(op for op in record["operations"]
                     if op.get("step_id") == "send")
    assert len(_outbox_records(outbox)) == 1
    assert operation["status"] == "uncertain"
    assert operation["needs_reconciliation"] is True
    _run(env["executor"].execute(run_id))
    assert len(_outbox_records(outbox)) == 1


def test_post_effect_parse_error_is_uncertain(env, tmp_path, monkeypatch):
    outbox = tmp_path / "post-effect-parse.jsonl"

    async def writes_then_returns_bad_payload(inputs, context):
        outbox.write_text(json.dumps({"to": inputs.get("to")}) + "\n")
        return object()

    run_id, _ = _external_error_assignment(
        env, tmp_path, monkeypatch, "test.post_effect_parse",
        writes_then_returns_bad_payload)
    _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    operation = next(op for op in record["operations"]
                     if op.get("step_id") == "send")
    assert len(_outbox_records(outbox)) == 1
    assert operation["status"] == "uncertain"
    assert operation["receipt"]["observed_status"] == "uncertain"


def test_post_effect_cancellation_is_uncertain(env, tmp_path, monkeypatch):
    outbox = tmp_path / "post-effect-cancel.jsonl"

    async def writes_then_cancels(inputs, context):
        outbox.write_text(json.dumps({"to": inputs.get("to")}) + "\n")
        raise asyncio.CancelledError()

    run_id, _ = _external_error_assignment(
        env, tmp_path, monkeypatch, "test.post_effect_cancel",
        writes_then_cancels)
    with pytest.raises(asyncio.CancelledError):
        _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    operation = next(op for op in record["operations"]
                     if op.get("step_id") == "send")
    step = step_by_id(record["assignment"], "send")
    assert len(_outbox_records(outbox)) == 1
    assert operation["status"] == "uncertain"
    assert step["status"] == "uncertain"
    _run(env["executor"].execute(run_id))
    assert len(_outbox_records(outbox)) == 1


def test_trusted_before_effect_error_remains_retryable(
        env, tmp_path, monkeypatch):
    outbox = tmp_path / "trusted-before-effect.jsonl"

    async def refuses_before_effect(inputs, context):
        raise ExternalOutcomeNotApplied("provider rejected before dispatch")

    run_id, _ = _external_error_assignment(
        env, tmp_path, monkeypatch, "test.before_effect",
        refuses_before_effect)
    _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    operation = next(op for op in record["operations"]
                     if op.get("step_id") == "send")
    step = step_by_id(record["assignment"], "send")
    assert len(_outbox_records(outbox)) == 0
    assert operation["status"] == "failed"
    assert operation.get("needs_reconciliation") is not True
    assert operation["receipt"]["observed_status"] == "failed_before_effect"
    assert step["status"] == "failed"


def _costed_assignment(env, tmp_path, monkeypatch, *, bound, actual,
                       budget, calls):
    async def costed(inputs, context):
        calls["count"] += 1
        return {"status": "applied", "summary": "costed work",
                "cost_usd": actual}

    env["executor"].adapters.register(
        "test.costed", costed,
        metadata={"effect": "local", "cost_bearing": True,
                  **({"max_cost_usd": bound} if bound is not None else {})})
    steps = [new_step(
        step_id="cost", title="Costed work", operation_type="calculate",
        adapter="test.costed", effect="local")]
    run_id, _ = _create(
        env, objective="Costed work", steps=steps, teaching=_teaching(),
        budget=budget)
    return run_id


def test_hard_cost_budget_refuses_before_dispatch(env, tmp_path):
    calls = {"count": 0}
    run_id = _costed_assignment(
        env, tmp_path, None, bound=10.0, actual=10.0,
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600, "max_cost_usd": 5.0},
        calls=calls)
    _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    step = step_by_id(record["assignment"], "cost")
    budget = record["assignment"]["budget"]
    assert calls["count"] == 0
    assert step["status"] == "failed"
    assert step["failure"]["reason"] == "assignment_cost_budget_exhausted"
    assert budget["cost_usd"] == 0.0
    assert budget["reserved_cost_usd"] == 0.0


def test_reserved_cost_blocks_the_next_over_limit_step(env, tmp_path):
    calls = {"count": 0}
    run_id = _costed_assignment(
        env, tmp_path, None, bound=4.0, actual=3.5,
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600, "max_cost_usd": 5.0},
        calls=calls)
    record = env["lifecycle"].get_task(run_id)
    assignment = record["assignment"]
    step = step_by_id(assignment, "cost")
    first = env["executor"]._reserve_step_cost(
        run_id, assignment, step, "op-first", 4.0,
        env["executor"].adapters.get("test.costed"))
    assert first["ok"] is True
    second = env["executor"]._reserve_step_cost(
        run_id, first["assignment"], step, "op-second", 2.0,
        env["executor"].adapters.get("test.costed"))
    assert second["ok"] is False
    assert "committed=0" in second["message"]
    saved = env["lifecycle"].get_assignment(run_id)
    assert saved["budget"]["reserved_cost_usd"] == 4.0
    assert saved["budget"]["cost_usd"] == 0.0


def test_soft_cost_limit_is_explicit_and_exposed(env, tmp_path):
    calls = {"count": 0}
    run_id = _costed_assignment(
        env, tmp_path, None, bound=10.0, actual=10.0,
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600, "max_cost_usd": 5.0,
                "cost_mode": "soft",
                "soft_limit_authorized_by": "owner-1"},
        calls=calls)
    _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    step = step_by_id(record["assignment"], "cost")
    budget = record["assignment"]["budget"]
    assert calls["count"] == 1
    assert step["status"] == "applied"
    assert budget["cost_mode"] == "soft"
    assert budget["soft_limit_authorized_by"] == "owner-1"
    assert budget["soft_limit_exceeded"] is True
    assert budget["cost_usd"] == 10.0


def test_cost_bearing_adapter_without_a_bound_is_refused(env, tmp_path):
    calls = {"count": 0}
    run_id = _costed_assignment(
        env, tmp_path, None, bound=None, actual=1.0,
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600, "max_cost_usd": 5.0},
        calls=calls)
    _run(env["executor"].execute(run_id))
    record = env["lifecycle"].get_task(run_id)
    step = step_by_id(record["assignment"], "cost")
    assert calls["count"] == 0
    assert step["status"] == "failed"
    assert step["failure"]["reason"] == "unbounded_cost_refused"


def test_durable_wait_time_is_excluded_from_the_wall_budget(env):
    """A 15-minute working budget must survive a two-hour external wait.

    The budget gate is the consumer boundary: it must allow the next step
    after a long durable wait, while still refusing a genuinely long-running
    working assignment.
    """
    from datetime import datetime, timedelta, timezone

    executor = env["executor"]
    now = datetime.now(timezone.utc)
    two_hours_ago = (now - timedelta(hours=2)).isoformat()
    base = {
        "max_steps": 40,
        "max_attempts_per_step": 3,
        "max_wall_seconds": 900,
        "started_at": two_hours_ago,
    }

    waiting = dict(base, waiting_since=two_hours_ago, paused_seconds=0.0)
    assert executor._budget_allows({"budget": waiting}, {"attempts": 0}) is True
    assert executor._remaining_wall_seconds({"budget": waiting}) > 800

    resolved = dict(base, waiting_since=None, paused_seconds=7200.0)
    assert executor._budget_allows({"budget": resolved}, {"attempts": 0}) is True
    assert executor._remaining_wall_seconds({"budget": resolved}) > 800

    working = dict(base, waiting_since=None, paused_seconds=0.0)
    assert executor._budget_allows({"budget": working}, {"attempts": 0}) is False
    assert executor._remaining_wall_seconds({"budget": working}) == 0.0



def _waiting_budget_run(env, correlation: str = "corr-budget") -> str:
    adapter = f"test.budget_wait.{uuid.uuid4().hex[:8]}"

    async def wait_reply(inputs, context):
        if (context.get("step") or {}).get("external_response"):
            return {"status": "applied", "summary": "reply received"}
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "party": "supplier",
            "correlation_id": correlation,
            "resume_on": "response",
            "detail": "authorized reply",
        })

    env["registry"].register(adapter, wait_reply)
    default_adapter_registry.register(adapter, wait_reply)
    steps = [new_step(
        step_id="wait", title="Wait for the authorized reply",
        operation_type="retrieve", adapter=adapter, effect="read_only")]
    run_id, _ = _create(
        env, objective="Wait budget control", steps=steps,
        teaching=_teaching(),
        budget={"max_steps": 10, "max_attempts_per_step": 3,
                "max_wall_seconds": 900})
    _run(env["executor"].execute(run_id))
    return run_id


def _force_budget_failure(
    env, run_id: str, *, started_ago: float, wait_started_ago: float,
    wait_ended_ago: float, paused: float | None = None,
    schema: bool = False, attempts: int = 1,
    keep_waiting: bool = False,
) -> None:
    now = datetime.now(timezone.utc)

    def compute(record, assignment):
        budget = dict(assignment.get("budget") or {})
        budget["started_at"] = (
            now - timedelta(seconds=started_ago)).isoformat()
        budget["max_wall_seconds"] = 900.0
        if paused is not None:
            budget["paused_seconds"] = paused
        budget.pop("active_wait", None)
        budget.pop("waiting_since", None)
        # These tests construct pre-idle-ledger budgets on purpose.
        budget.pop("idle_ledger_schema", None)
        budget.pop("idle_open", None)
        budget.pop("idle_intervals", None)
        if schema:
            budget["wait_credits_schema"] = 1
            budget.setdefault("wait_credits", {})
        else:
            budget.pop("wait_credits_schema", None)
            budget.pop("wait_credits", None)
        assignment["budget"] = budget
        step = step_by_id(assignment, "wait")
        step["status"] = "failed"
        step["attempts"] = attempts
        step["failure"] = {
            "reason": "assignment_budget_exhausted",
            "message": "budget exhausted during a durable wait",
        }
        step["waiting"] = {
            "state": "waiting_for_external",
            "correlation_id": "corr-budget",
            "since": (now - timedelta(seconds=wait_started_ago)).isoformat(),
        }
        step["external_response"] = {
            "correlation_id": "corr-budget",
            "response": "net 30",
            "at": (now - timedelta(seconds=wait_ended_ago)).isoformat(),
        }
        if keep_waiting:
            budget["waiting_since"] = step["waiting"]["since"]
            budget["active_wait"] = {
                "id": "legacy-open-wait",
                "step_id": "wait",
                "started_at": step["waiting"]["since"],
            }
            assignment["budget"] = budget
        return assignment, {}

    env["lifecycle"].mutate_assignment(
        run_id, compute, rationale="test: budget failure after wait")


def test_retry_credits_a_legacy_wait_once_and_keeps_working_time(env):
    run_id = _waiting_budget_run(env)
    _force_budget_failure(
        env, run_id, started_ago=2000, wait_started_ago=1500,
        wait_ended_ago=1000, paused=0.0, schema=False)
    executor = env["executor"]
    executor.retry_step(run_id, "wait", reason="repair")
    assignment = env["lifecycle"].get_assignment(run_id)
    budget = assignment["budget"]
    assert 499.0 <= budget["paused_seconds"] <= 501.0
    assert budget["wait_credits"]
    assert len(budget["wait_credits"]) == 1
    step = step_by_id(assignment, "wait")
    assert step["attempts"] == 1
    assert step["pre_dispatch_budget_refusal"] is True
    # 2000s actual - 500s wait = 1500s working, still over 900s.
    assert executor._budget_allows(assignment, step) is False

    # Repeated and restart retries must not add the interval again.
    _force_budget_failure(
        env, run_id, started_ago=2000, wait_started_ago=1500,
        wait_ended_ago=1000, paused=None, schema=True)
    executor.retry_step(run_id, "wait", reason="repeat")
    again = env["lifecycle"].get_assignment(run_id)["budget"]
    assert 499.0 <= again["paused_seconds"] <= 501.0
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    _force_budget_failure(
        env, run_id, started_ago=2000, wait_started_ago=1500,
        wait_ended_ago=1000, paused=None, schema=True)
    restarted.retry_step(run_id, "wait", reason="after restart")
    after_restart = env["lifecycle"].get_assignment(run_id)["budget"]
    assert 499.0 <= after_restart["paused_seconds"] <= 501.0


def test_legacy_already_credited_pause_is_not_extended(env):
    run_id = _waiting_budget_run(env)
    _force_budget_failure(
        env, run_id, started_ago=2000, wait_started_ago=1500,
        wait_ended_ago=1400, paused=100.0, schema=False)
    env["executor"].retry_step(run_id, "wait", reason="legacy repair")
    assignment = env["lifecycle"].get_assignment(run_id)
    budget = assignment["budget"]
    assert budget["paused_seconds"] == 100.0
    assert budget["wait_credits"]
    assert all(item.get("already_credited")
               for item in budget["wait_credits"].values())
    assert env["executor"]._budget_allows(
        assignment, step_by_id(assignment, "wait")) is False


def test_each_new_wait_interval_is_credited_once(env):
    run_id = _waiting_budget_run(env)
    executor = env["executor"]
    assignment = env["lifecycle"].get_assignment(run_id)
    budget = dict(assignment["budget"])
    budget["wait_credits_schema"] = 1
    budget["wait_credits"] = {}
    budget["paused_seconds"] = 0.0
    # Direct legacy credit semantics; executor-owned budgets use the idle
    # interval ledger instead.
    budget.pop("idle_ledger_schema", None)
    budget.pop("idle_open", None)
    budget.pop("idle_intervals", None)
    start = datetime.now(timezone.utc)
    first_start = (start - timedelta(seconds=200)).isoformat()
    first_end = (start - timedelta(seconds=100)).isoformat()
    second_start = (start - timedelta(seconds=80)).isoformat()
    second_end = (start - timedelta(seconds=30)).isoformat()
    assert executor._credit_wait_once(
        budget, wait_id="wait-a", started_at=first_start,
        ended_at=first_end) is True
    assert executor._credit_wait_once(
        budget, wait_id="wait-a", started_at=first_start,
        ended_at=first_end) is False
    assert executor._credit_wait_once(
        budget, wait_id="wait-b", started_at=second_start,
        ended_at=second_end) is True
    assert 149.0 <= budget["paused_seconds"] <= 151.0
    assert set(budget["wait_credits"]) == {"wait-a", "wait-b"}


def test_independent_ready_branch_runs_while_first_branch_waits(env):
    """A waiting supplier branch must not stop an independent ready branch.

    The executor used to return as soon as it saw ANY waiting step, even
    when a different branch had all dependencies satisfied. Supplier B's
    work is independent of Supplier A's external reply and must run in the
    same pass.
    """
    suffix = uuid.uuid4().hex[:8]
    waiting_adapter = f"test.waiting_supplier.{suffix}"
    ready_adapter = f"test.ready_supplier.{suffix}"
    calls = {"ready": 0}

    async def supplier_a(inputs, context):
        raise WaitingForExternal({
            "event": "email",
            "state": "waiting_for_external",
            "party": "supplier A",
            "correlation_id": f"corr-a-{suffix}",
            "resume_on": "response",
            "detail": "supplier A has not replied",
        })

    async def supplier_b(inputs, context):
        calls["ready"] += 1
        return {"status": "applied", "summary": "supplier B priced"}

    env["registry"].register(waiting_adapter, supplier_a)
    env["registry"].register(ready_adapter, supplier_b)
    steps = [
        new_step(
            step_id="supplier_a", title="Wait for supplier A",
            operation_type="retrieve", adapter=waiting_adapter,
            effect="read_only"),
        new_step(
            step_id="supplier_b", title="Read supplier B",
            operation_type="retrieve", adapter=ready_adapter,
            effect="read_only"),
    ]
    run_id, _ = _create(
        env, objective="Independent supplier branches", steps=steps,
        teaching=_teaching())
    _run(env["executor"].execute(run_id))

    assignment = env["lifecycle"].get_assignment(run_id)
    assert calls["ready"] == 1
    assert step_by_id(assignment, "supplier_b")["status"] == "applied"
    assert step_by_id(assignment, "supplier_a")["status"] == "waiting"
    assert assignment["status"] == "waiting"

    # The completed independent branch is durable: another execute pass does
    # not repeat its work and still reports the remaining wait.
    _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert calls["ready"] == 1
    assert step_by_id(assignment, "supplier_a")["status"] == "waiting"


def test_idle_budget_unions_overlapping_waits_across_restart(env):
    """The 40/40/10/10 timeline credits 50s working and 50s paused.

    Work 0-40, all branches blocked 40-80, work 80-90, all branches blocked
    90-100. Two overlapping supplier waits at 90 must not be summed. The
    budget is read after a real executor replacement (restart) and after
    concurrent responses.
    """
    base = 1_700_000_000.0
    clock = [base]
    suffix = uuid.uuid4().hex[:8]
    calls = {"work0": 0, "resume": 0}

    async def work_zero_to_forty(inputs, context):
        calls["work0"] += 1
        clock[0] = base + 40
        return {"status": "applied", "summary": "prepared"}

    async def wait_supplier_a(inputs, context):
        if (context.get("step") or {}).get("external_response"):
            return {"status": "applied", "summary": "supplier A reply used"}
        raise WaitingForExternal({
            "event": "email", "state": "waiting_for_external",
            "party": "supplier A", "correlation_id": f"corr-a-{suffix}",
            "resume_on": "response", "detail": "supplier A reply"})

    async def work_eighty_to_ninety(inputs, context):
        calls["resume"] += 1
        clock[0] = base + 90
        return {"status": "applied", "summary": "continued"}

    async def wait_supplier_b(inputs, context):
        if (context.get("step") or {}).get("external_response"):
            return {"status": "applied", "summary": "supplier B reply used"}
        raise WaitingForExternal({
            "event": "email", "state": "waiting_for_external",
            "party": "supplier B", "correlation_id": f"corr-b-{suffix}",
            "resume_on": "response", "detail": "supplier B reply"})

    async def wait_supplier_c(inputs, context):
        if (context.get("step") or {}).get("external_response"):
            return {"status": "applied", "summary": "supplier C reply used"}
        raise WaitingForExternal({
            "event": "email", "state": "waiting_for_external",
            "party": "supplier C", "correlation_id": f"corr-c-{suffix}",
            "resume_on": "response", "detail": "supplier C reply"})

    for name, handler in (
            (f"test.clock.work0.{suffix}", work_zero_to_forty),
            (f"test.clock.wait_a.{suffix}", wait_supplier_a),
            (f"test.clock.resume.{suffix}", work_eighty_to_ninety),
            (f"test.clock.wait_b.{suffix}", wait_supplier_b),
            (f"test.clock.wait_c.{suffix}", wait_supplier_c)):
        env["registry"].register(name, handler)

    def step(step_id, adapter, depends_on=None):
        return new_step(
            step_id=step_id, title=step_id, operation_type="retrieve",
            adapter=adapter, effect="read_only",
            depends_on=depends_on or [])

    steps = [
        step("work0", f"test.clock.work0.{suffix}"),
        step("wait_a", f"test.clock.wait_a.{suffix}", ["work0"]),
        step("resume", f"test.clock.resume.{suffix}", ["wait_a"]),
        step("wait_b", f"test.clock.wait_b.{suffix}", ["resume"]),
        step("wait_c", f"test.clock.wait_c.{suffix}", ["resume"]),
    ]
    run_id, _ = _create(
        env, objective="Idle budget timeline", steps=steps,
        teaching=_teaching(),
        budget={"max_steps": 40, "max_attempts_per_step": 3,
                "max_wall_seconds": 900})

    def set_started_at(record, assignment):
        budget = dict(assignment.get("budget") or {})
        budget["started_at"] = datetime.fromtimestamp(
            base, tz=timezone.utc).isoformat()
        assignment["budget"] = budget
        return assignment, {}

    env["lifecycle"].mutate_assignment(
        run_id, set_started_at, rationale="test: fixed clock origin")

    executor = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"], clock=lambda: clock[0])
    _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert calls == {"work0": 1, "resume": 0}
    assert assignment["budget"]["paused_seconds"] == 0.0
    assert step_by_id(assignment, "wait_a")["status"] == "waiting"
    assert assignment["budget"].get("idle_open")

    # 40-80: nobody can progress; the reply arrives at 80.
    clock[0] = base + 80
    assert executor.record_external_response(
        run_id, f"corr-a-{suffix}", response="supplier A replied",
        source="email")["status"] == "resumed"
    _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert calls == {"work0": 1, "resume": 1}
    assert 39.9 <= assignment["budget"]["paused_seconds"] <= 40.1
    assert step_by_id(assignment, "resume")["status"] == "applied"

    # 90-100: both branch waits overlap. Restart the executor first so the
    # open interval is recovered from durable state rather than memory.
    assert step_by_id(assignment, "wait_b")["status"] == "waiting"
    assert step_by_id(assignment, "wait_c")["status"] == "waiting"
    restarted = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"], clock=lambda: clock[0])
    clock[0] = base + 100
    _run(restarted.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    budget = assignment["budget"]
    assert 49.9 <= budget["paused_seconds"] <= 50.1
    assert 49.9 <= restarted._effective_wall_elapsed(budget) <= 50.1
    status = restarted.status(run_id)
    assert 49.9 <= status["assignment"]["budget"]["working_seconds"] <= 50.1
    assert 49.9 <= status["assignment"]["budget"]["paused_seconds"] <= 50.1
    assert status["assignment"]["progress"]["waiting_steps"] == 2

    # Concurrent replies for the two outstanding waits must resolve once
    # each without adding another idle interval.
    def reply(correlation):
        return restarted.record_external_response(
            run_id, correlation, response=f"{correlation} replied",
            source="email")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            reply, [f"corr-b-{suffix}", f"corr-c-{suffix}"]))
    assert sorted(item["status"] for item in results) == ["resumed", "resumed"]
    _run(restarted.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    budget = assignment["budget"]
    assert step_by_id(assignment, "wait_b")["status"] == "applied"
    assert step_by_id(assignment, "wait_c")["status"] == "applied"
    assert 49.9 <= budget["paused_seconds"] <= 50.1
    assert 49.9 <= restarted._effective_wall_elapsed(budget) <= 50.1
    assert budget.get("idle_intervals") is not None


def test_legacy_open_wait_migration_does_not_invent_a_second_credit(env):
    executor = env["executor"]
    base = {
        "assignment_id": "asg-legacy",
        "steps": [],
        "budget": {
            "started_at": "2026-11-01T00:00:00+00:00",
            "paused_seconds": 100.0,
            "waiting_since": "2026-11-01T00:00:30+00:00",
            "active_wait": None,
        },
    }
    migrated = executor._ensure_idle_ledger(base)["budget"]
    assert migrated["idle_ledger_schema"] == 2
    assert migrated["paused_seconds"] == 100.0
    assert migrated.get("idle_open") is None

    live = copy.deepcopy(base)
    live["budget"]["active_wait"] = {
        "id": "wait-live", "started_at": "2026-11-01T00:00:30+00:00"}
    migrated = executor._ensure_idle_ledger(live)["budget"]
    assert migrated["idle_open"]["started_at"].startswith(
        "2026-11-01T00:00:30")


def test_absolute_deadline_expires_through_wait_and_restart(env):
    base = 1_700_000_000.0
    clock = [base]
    suffix = uuid.uuid4().hex[:8]

    async def work(inputs, context):
        clock[0] = base + 40
        return {"status": "applied", "summary": "prepared"}

    async def wait(inputs, context):
        raise WaitingForExternal({
            "event": "email", "state": "waiting_for_external",
            "correlation_id": f"deadline-{suffix}",
            "resume_on": "response", "party": "supplier"})

    env["registry"].register(f"test.deadline.work.{suffix}", work)
    env["registry"].register(f"test.deadline.wait.{suffix}", wait)
    run_id, _ = _create(
        env, objective="Deadline control",
        steps=[
            new_step(step_id="work", title="Work", operation_type="retrieve",
                     adapter=f"test.deadline.work.{suffix}",
                     effect="read_only"),
            new_step(step_id="wait", title="Wait", operation_type="retrieve",
                     adapter=f"test.deadline.wait.{suffix}",
                     effect="read_only", depends_on=["work"]),
        ],
        teaching=_teaching(),
        budget={"max_steps": 10, "max_attempts_per_step": 3,
                "max_wall_seconds": 900,
                "deadline": datetime.fromtimestamp(
                    base + 50, tz=timezone.utc).isoformat()})

    def set_start(record, assignment):
        assignment["budget"]["started_at"] = datetime.fromtimestamp(
            base, tz=timezone.utc).isoformat()
        return assignment, {}

    env["lifecycle"].mutate_assignment(
        run_id, set_start, rationale="test: clock origin")
    executor = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"], clock=lambda: clock[0])
    _run(executor.execute(run_id))
    assert step_by_id(env["lifecycle"].get_assignment(run_id),
                      "wait")["status"] == "waiting"

    clock[0] = base + 60
    shadow = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"], clock=lambda: clock[0])
    result = _run(shadow.execute(run_id))
    assert result["assignment"]["status"] == "blocked"
    wait_step = step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")
    assert wait_step["status"] == "failed"
    assert wait_step["failure"]["reason"] == "assignment_deadline_exceeded"
    late = shadow.record_external_response(
        run_id, f"deadline-{suffix}", response="late reply")
    assert late["status"] == "unmatched"

    clock[0] = base + 120
    restarted = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"], clock=lambda: clock[0])
    again = _run(restarted.execute(run_id))
    assert again["assignment"]["status"] == "blocked"
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "wait")["failure"]["reason"]         == "assignment_deadline_exceeded"


def test_concurrent_retries_credit_a_legacy_wait_once(env):
    run_id = _waiting_budget_run(env)
    _force_budget_failure(
        env, run_id, started_ago=2000, wait_started_ago=1500,
        wait_ended_ago=1000, paused=0.0, schema=False)
    executor = env["executor"]

    def retry():
        try:
            executor.retry_step(run_id, "wait", reason="concurrent repair")
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: retry(), range(2)))
    budget = env["lifecycle"].get_assignment(run_id)["budget"]
    assert 499.0 <= budget["paused_seconds"] <= 501.0


def test_genuine_active_work_exhaustion_is_refused(env):
    run_id = _waiting_budget_run(env)
    executor = env["executor"]
    now = datetime.now(timezone.utc)

    def compute(record, assignment):
        budget = dict(assignment.get("budget") or {})
        budget.update({
            "started_at": (now - timedelta(seconds=2000)).isoformat(),
            "max_wall_seconds": 900.0,
            "paused_seconds": 0.0,
            "waiting_since": None,
            "wait_credits": {},
            "wait_credits_schema": 1,
            "active_wait": None,
        })
        assignment["budget"] = budget
        step = step_by_id(assignment, "wait")
        step["status"] = "pending"
        step["failure"] = None
        step["attempts"] = 0
        return assignment, {}

    env["lifecycle"].mutate_assignment(run_id, compute, rationale="test")
    assignment = env["lifecycle"].get_assignment(run_id)
    assert executor._budget_allows(
        assignment, step_by_id(assignment, "wait")) is False


def test_legacy_open_wait_is_not_subtracted_twice(env):
    """paused_seconds already contains the interval; waiting_since must not
    subtract the same interval again and make exhausted work look unexhausted."""
    now = datetime.now(timezone.utc)
    budget = {
        "started_at": (now - timedelta(seconds=2000)).isoformat(),
        "paused_seconds": 500.0,
        "waiting_since": (now - timedelta(seconds=1500)).isoformat(),
        "max_wall_seconds": 900.0,
        "wait_credits_schema": 0,
        "wait_credits": {},
        "active_wait": None,
    }
    executor = env["executor"]
    assert 1499.0 <= executor._effective_wall_elapsed(budget) <= 1501.0
    assert executor._budget_allows(
        {"budget": budget}, {"attempts": 0}) is False
    assert executor._remaining_wall_seconds({"budget": budget}) == 0.0


def test_legacy_credit_clears_matching_active_wait(env):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(seconds=1500)).isoformat()
    end = (now - timedelta(seconds=1000)).isoformat()
    budget = {
        "started_at": (now - timedelta(seconds=2000)).isoformat(),
        "paused_seconds": 500.0,
        "waiting_since": start,
        "max_wall_seconds": 900.0,
        "wait_credits_schema": 0,
        "wait_credits": {},
        "active_wait": {"id": "legacy-open-wait", "started_at": start},
    }
    assert env["executor"]._credit_wait_once(
        budget, wait_id="legacy-open-wait", started_at=start,
        ended_at=end, legacy=True) is False
    assert budget["paused_seconds"] == 500.0
    assert budget["active_wait"] is None
    assert "waiting_since" not in budget
    assert budget["wait_credits"]["legacy-open-wait"]["already_credited"] is True
    assert 1499.0 <= env["executor"]._effective_wall_elapsed(budget) <= 1501.0


def test_legacy_retry_keeps_genuine_active_exhaustion(env):
    run_id = _waiting_budget_run(env)
    _force_budget_failure(
        env, run_id, started_ago=2000, wait_started_ago=1500,
        wait_ended_ago=1000, paused=500.0, schema=False,
        keep_waiting=True)
    executor = env["executor"]
    executor.retry_step(run_id, "wait", reason="legacy repair")
    assignment = env["lifecycle"].get_assignment(run_id)
    budget = assignment["budget"]
    assert 499.0 <= budget["paused_seconds"] <= 501.0
    assert budget["active_wait"] is None
    assert budget.get("waiting_since") is None
    assert 1499.0 <= executor._effective_wall_elapsed(budget) <= 1501.0
    assert executor._budget_allows(
        assignment, step_by_id(assignment, "wait")) is False


def test_recorded_credit_with_stale_open_wait_is_not_double_subtracted(env):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(seconds=1500)).isoformat()
    end = (now - timedelta(seconds=1000)).isoformat()
    budget = {
        "started_at": (now - timedelta(seconds=2000)).isoformat(),
        "paused_seconds": 500.0,
        "waiting_since": start,
        "max_wall_seconds": 900.0,
        "wait_credits_schema": 1,
        "wait_credits": {"wait-1": {
            "seconds": 500.0, "started_at": start, "ended_at": end}},
        "active_wait": {"id": "wait-1", "started_at": start},
    }
    executor = env["executor"]
    assert 1499.0 <= executor._effective_wall_elapsed(budget) <= 1501.0
    assert executor._credit_wait_once(
        budget, wait_id="wait-1", started_at=start,
        ended_at=end) is False
    assert budget["active_wait"] is None
    assert budget.get("waiting_since") is None
    assert 1499.0 <= executor._effective_wall_elapsed(budget) <= 1501.0


def test_concurrent_external_responses_credit_the_wait_once(env):
    run_id = _waiting_budget_run(env, correlation="corr-concurrent")
    executor = env["executor"]

    def respond(_):
        return executor.record_external_response(
            run_id, "corr-concurrent", response="net 30")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(respond, range(2)))
    assert all(item.get("status") in ("resumed", "unmatched")
               for item in results), results
    assignment = env["lifecycle"].get_assignment(run_id)
    budget = assignment["budget"]
    assert len(budget["wait_credits"]) == 1, budget["wait_credits"]
    assert float(budget["paused_seconds"]) < 5.0
    assert budget["active_wait"] is None
    assert budget.get("waiting_since") is None
    _run(executor.execute(run_id))
    assert env["lifecycle"].get_assignment(run_id)["status"] == "completed"
    assert len(env["lifecycle"].get_assignment(
        run_id)["budget"]["wait_credits"]) == 1


def test_restart_while_waiting_credits_the_interval_once(env):
    run_id = _waiting_budget_run(env, correlation="corr-restart-budget")
    now = datetime.now(timezone.utc)
    wait_start = (now - timedelta(seconds=600)).isoformat()

    def age_wait(record, assignment):
        budget = dict(assignment.get("budget") or {})
        budget["paused_seconds"] = 0.0
        budget["waiting_since"] = wait_start
        budget["wait_credits_schema"] = 1
        budget["wait_credits"] = {}
        budget.pop("idle_ledger_schema", None)
        budget.pop("idle_open", None)
        budget.pop("idle_intervals", None)
        budget["active_wait"] = {
            "id": "restart-wait", "step_id": "wait",
            "started_at": wait_start,
        }
        assignment["budget"] = budget
        return assignment, {}

    env["lifecycle"].mutate_assignment(
        run_id, age_wait, rationale="test: age the open wait")
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    before = restarted._effective_wall_elapsed(
        env["lifecycle"].get_assignment(run_id)["budget"])
    assert before < 5.0  # the open 600s wait is excluded
    result = restarted.record_external_response(
        run_id, "corr-restart-budget", response="net 30")
    assert result.get("status") == "resumed", result
    budget = env["lifecycle"].get_assignment(run_id)["budget"]
    assert len(budget["wait_credits"]) == 1
    assert 599.0 <= float(budget["paused_seconds"]) <= 601.0
    assert restarted._effective_wall_elapsed(budget) < 5.0
    assert budget["active_wait"] is None
    assert budget.get("waiting_since") is None


def test_evidence_backed_quote_plan_end_to_end(env, monkeypatch):
    from core.quote_evidence import (
        derive_quote_requirements,
        plan_quote_assignment,
        validate_quote_evidence,
    )
    import openpyxl

    tmp = env["tmp"]
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp))
    workbook_path = tmp / "quote_inputs.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Items"
    sheet.append(["SKU", "Qty", "Unit Price", "Discount Percent", "Category",
                  "Unit", "Pack"])
    sheet.append(["A", 2, 100.00, 0, "A", "each", "1"])
    sheet.append(["B", 3, 50.00, 5, "B", "each", "1"])
    workbook.save(workbook_path)

    customer = {
        "provider": "crm", "resource_id": "cust-1", "version": "v1",
        "kind": "customer", "record_type": "customer",
        "customer_id": "cust-1", "customer_name": "Example Customer",
        "access": "granted"}
    agreement = {
        "provider": "workdrive", "resource_id": "agreement-1", "version": "v3",
        "kind": "pricing_agreement", "customer_id": "cust-1",
        "price_basis": "customer_contract", "effective_date": "2026-10-01",
        "access": "granted",
        "fields": {
            "currency": "USD", "effective_date": "2026-10-01",
            "discount_policy": "5% on category B", "freight": "20.00",
            "tax_treatment": "none", "delivery_terms": "FOB destination",
            "validity": "30 days",
        },
        "citations": [{"sheet": "Terms", "row": 2}],
    }
    rows = {
        "provider": "onedrive", "resource_id": "rows-1", "version": "rev-7",
        "kind": "price_rows", "access": "granted",
        "citations": [{"sheet": "Items", "row": 2},
                      {"sheet": "Items", "row": 3}],
        "rows": [
            {"sku": "A", "quantity": "2", "unit": "each", "pack": "1",
             "unit_price": "100.00", "currency": "USD",
             "discount_percent": "0", "category": "A",
             "citation": {"sheet": "Items", "row": 2}},
            {"sku": "B", "quantity": "3", "unit": "each", "pack": "1",
             "unit_price": "50.00", "currency": "USD",
             "discount_percent": "5", "category": "B",
             "citation": {"sheet": "Items", "row": 3}},
        ],
    }
    from core.action_registry import action_registry

    async def read_customer(args, context):
        return {"data": {"customer_id": "cust-1", "name": "Example Customer"},
                "read_receipt": {"provider": "zoho_crm",
                                 "resource_id": "crm-cust-1",
                                 "coverage": "complete"}}

    action_registry.register(
        "test.quote.customer", read_customer, effects=[{"effect": "read"}])
    requirements = derive_quote_requirements(
        "Prepare a customer quote", requested={"customer_id": "cust-1"})
    validation = validate_quote_evidence(
        requirements, [customer, rows, agreement],
        requested={"customer_id": "cust-1"})
    assert validation["status"] == "ready", validation
    planned = plan_quote_assignment(
        objective="Prepare a customer quote", validation=validation,
        source={
            "kind": "workbook", "representation": "xlsx",
            "resource_id": "quote-workbook", "internal_fixture": True,
            "path": str(workbook_path), "sheet": "Items",
            "columns": ["SKU", "Qty", "Unit Price", "Discount Percent",
                        "Category", "Unit", "Pack"],
        },
        teaching=_teaching(), workspace_id="ws_assign",
        tenant_id="tenant_assign", employee_id="user-1",
        evidence_reads=[{
            "step_id": "read-customer",
            "action": "test.quote.customer",
            "arguments": {"record_id": "cust-1"},
        }],
        document_path=str(tmp / "quote.docx"),
        email_draft_path=str(tmp / "quote-draft.eml"),
        email_to=["customer@example.invalid"], subject="Customer quote")
    assert planned["status"] == "ready", planned
    plan = planned["plan"]
    run_id = env["executor"].create_assignment(
        "conv-quote", "Prepare a customer quote", assignment=plan)["run_id"]
    result = _run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    document = docx.Document(str(tmp / "quote.docx"))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "362.50" in text, text
    assignment = env["lifecycle"].get_assignment(run_id)
    calc = step_by_id(assignment, "calculate")
    assert calc["result"]["value"] == "362.50"
    assert calc["result"]["calculation_receipt"]["total"] == "362.50"
    read_customer_step = step_by_id(assignment, "read-customer")
    assert read_customer_step["status"] == "applied"
    assert read_customer_step["result"]["data"]["read_receipt"][
        "provider"] == "zoho_crm"
    assert proof["quote_evidence"]["status"] == "ready" if (
        proof := assignment.get("provenance")) else False
    draft = step_by_id(assignment, "email-draft")
    assert draft["status"] == "applied"
    assert "362.50" in str(draft["result"].get("body") or
                           draft["result"].get("draft") or "")


def test_service_line_plan_uses_the_same_executor(env, monkeypatch):
    """Portability control: hours/rates, different vocabulary and currency.

    The shared executor and line-item calculator carry no Brennan or quote
    vocabulary; only the typed line items and teaching differ.
    """
    from core.assignment_planner import plan_assignment

    tmp = env["tmp"]
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp))
    scope = tmp / "service-scope.txt"
    scope.write_text("Service scope: four consulting hours and two trips.\n")
    plan = plan_assignment(
        objective="Prepare a service proposal",
        sources=[{
            "kind": "document", "representation": "file",
            "resource_id": "service-scope", "internal_fixture": True,
            "path": str(scope),
        }],
        deliverables=[{
            "kind": "document", "path": str(tmp / "service-proposal.docx"),
            "title": "Service proposal",
        }],
        calculation={
            "line_items": [
                {"item_id": "consulting-hours", "quantity": "4",
                 "unit": "hour", "pack_size": "1", "unit_price": "120.00",
                 "price_basis": "rate", "currency": "CAD",
                 "category": "service"},
                {"item_id": "travel", "quantity": "2", "unit": "trip",
                 "pack_size": "1", "unit_price": "75.00",
                 "price_basis": "rate", "currency": "CAD",
                 "category": "service"},
            ],
            "currency": "CAD", "freight": "0", "tax": {"basis": "none"},
            "rounding": "half_up", "scale": 2,
        },
        teaching_snapshot=_teaching(),
        authorized_actions=["retrieve", "calculate", "present"],
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        provenance={"profile": "service"},
    )
    run_id = env["executor"].create_assignment(
        "conv-service", "Prepare a service proposal",
        assignment=plan)["run_id"]
    result = _run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    assignment = env["lifecycle"].get_assignment(run_id)
    calc = step_by_id(assignment, "calculate")
    assert calc["result"]["value"] == "630.00"
    text = "\n".join(
        p.text for p in docx.Document(
            str(tmp / "service-proposal.docx")).paragraphs)
    assert "630.00" in text


def test_non_sales_policy_plan_uses_the_same_executor(env, monkeypatch):
    """Portability control: an expense-policy assessment, not a quote."""
    from core.assignment_planner import plan_assignment

    tmp = env["tmp"]
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp))
    policy = tmp / "expense-policy.txt"
    policy.write_text("Expense limit: 200.00. Claimed: 250.00.\n")
    plan = plan_assignment(
        objective="Assess the expense claim against policy",
        sources=[{
            "kind": "document", "representation": "file",
            "resource_id": "expense-policy", "internal_fixture": True,
            "path": str(policy),
        }],
        deliverables=[{
            "kind": "document", "path": str(tmp / "expense-review.docx"),
            "title": "Expense review",
        }],
        calculation={
            "expression": "claimed - limit",
            "bindings": {"claimed": "250.00", "limit": "200.00"},
            "output_unit": "CAD",
        },
        teaching_snapshot=_teaching(),
        authorized_actions=["retrieve", "calculate", "present"],
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        provenance={"profile": "expense-policy"},
    )
    run_id = env["executor"].create_assignment(
        "conv-expense", "Assess the expense claim against policy",
        assignment=plan)["run_id"]
    result = _run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    assignment = env["lifecycle"].get_assignment(run_id)
    calc = step_by_id(assignment, "calculate")
    assert calc["result"]["value"] == "50.00"
    text = "\n".join(p.text for p in docx.Document(
        str(tmp / "expense-review.docx")).paragraphs)
    assert "50.00" in text
