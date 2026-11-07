"""TASK-WAIT-01 E1: two sequential missing facts in one normal assignment.

A normal objective starts with only the purchase order authorized. The
controlled proposal transport asks for one missing fact at a time (invoice,
then receiving). Supplying the authorized invoice through the public source
route must settle *only* the invoice obligation and let the same task ask for
receiving; supplying the authorized receiving record must then let the same
task reach one verified invoice reconciliation.

Public assignment routes, the real compiler/executor and scratch durable
records are exercised. Proposal/auth transport are the repository's existing
controlled fixtures; no provider, spend, account, send or deployment action
occurs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree

from tests.test_assignment_routes import route_env  # noqa: F401

PO = "PO-TWO-1"
INVOICE = "INV-TWO-1"


def _fixtures(tmp_path):
    po = tmp_path / "po.json"
    po.write_text(json.dumps({
        "po_id": PO, "vendor_id": "V-1", "quantity": "3",
        "unit_price": "40.00", "freight": "10.00", "currency": "USD"}))
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "po_id": PO, "invoice_id": INVOICE, "quantity": "3",
        "unit_price": "40.00", "freight": "10.00", "currency": "USD"}))
    receiving = tmp_path / "receiving.json"
    receiving.write_text(json.dumps({
        "po_id": PO, "received_quantity": "3"}))
    return po, invoice, receiving


def _install_transport(monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import InvoiceReconciliationRequest

    calls = []
    questions = []

    async def discovery(context, **kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized scope",
                "evidence_reads": [
                    {"step_id": f"evidence-{index}", "title": "Read source",
                     "source_id": source["source_id"]}
                    for index, source in enumerate(context["sources"], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def adaptation(context, observations, **kwargs):
        roles = {
            str(item.get("business_role") or ""): item["step_id"]
            for item in context.get("evidence_results") or []
            if item.get("business_role")
        }
        calls.append(dict(roles))
        capability = next(
            (item for item in context.get("available_business_operations") or []
             if str(item.get("operation") or "") == "invoice_reconciliation"),
            {})
        missing = [
            str(role) for role in capability.get("missing") or []
            if str(role).strip()]
        common = {
            "reason": "model-selected supported work",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if missing:
            # The model chooses one actionable missing fact, not the plan.
            role = missing[0]
            question = (
                f"Which authorized source contains the missing {role} "
                f"record for purchase order {PO}?")
            questions.append({"role": role, "question": question})
            return {
                "proposal": WorkAdaptationProposal(
                    decision="clarify",
                    clarification={
                        "question": question,
                        "concept": "invoice_reconciliation",
                        "unblocks": "invoice reconciliation",
                        "missing_roles": [role],
                    },
                    **common,
                ).model_dump(),
                "source": "model",
                "technical_fallback": False,
                "errors": [],
            }
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id=roles["invoice"],
                    purchase_order_step_id=roles["purchase_order"],
                    receiving_step_id=roles["receiving"]),
                **common,
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", discovery)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm", lambda *a, **k: object())
    return calls, questions


def _start(client, po):
    answer = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                f"Reconcile the supplier invoice for purchase order {PO}"),
            "sources": [{"path": str(po)}],
            "authorized_actions": ["retrieve", "calculate"],
            "requested_output": "document",
            "use_model": True,
        })
    assert answer.status_code == 200, answer.text
    return answer.json()["run_id"]


def _questions(lifecycle, run_id):
    from core.task_lifecycle import open_unresolved_questions

    return open_unresolved_questions(lifecycle.get_task(run_id))


def _reconciliations(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"] == "invoice.reconcile"
        and step["status"] == "applied"
    ]


def _applied_artifacts(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"].startswith("artifact.")
        and step["status"] == "applied"
    ]


def test_two_missing_facts_settle_sequentially_and_complete(
        route_env, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    po, invoice, receiving = _fixtures(tmp_path)
    calls, asked = _install_transport(monkeypatch)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    run_id = _start(client, po)
    first = _questions(lifecycle, run_id)
    assert len(first) == 1, first
    first_question = first[0]
    assert asked and asked[0]["role"] == "invoice", asked
    assert first_question["question"] == asked[0]["question"]
    assert first_question["inputs"]["missing"] == ["invoice"], (
        first_question["inputs"])
    started = lifecycle.get_assignment(run_id)
    requested_path = Path(started["provenance"]["requested_output_path"])
    assert requested_path.is_relative_to(tmp_path)
    assert not requested_path.exists(), "no report before either fact arrives"
    assert _reconciliations(started) == []
    assert _applied_artifacts(started) == []

    answer_invoice = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(invoice)},
              "reason": "the authorized invoice answers the invoice question"})
    assert answer_invoice.status_code == 200, answer_invoice.text
    body = answer_invoice.json()
    assert body["resolved_question_ids"] == [
        first_question["question_id"]], body
    after_invoice = lifecycle.get_assignment(run_id)
    assert _reconciliations(after_invoice) == []
    assert _applied_artifacts(after_invoice) == []
    assert not requested_path.exists(), (
        "no report while the receiving question is still open")

    second = _questions(lifecycle, run_id)
    assert len(second) == 1, second
    second_question = second[0]
    assert second_question["question_id"] != first_question["question_id"]
    assert asked[-1]["role"] == "receiving", asked
    assert second_question["inputs"]["missing"] == ["receiving"], (
        second_question["inputs"])

    answer_receiving = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "the authorized receiving record answers the question"})
    assert answer_receiving.status_code == 200, answer_receiving.text
    assert answer_receiving.json()["resolved_question_ids"] == [
        second_question["question_id"]], answer_receiving.json()

    final = lifecycle.get_assignment(run_id)
    reconciliations = _reconciliations(final)
    assert len(reconciliations) == 1, [
        (step["adapter"], step["status"]) for step in final["steps"]]
    assert reconciliations[0]["result"]["value"] == "130.00"
    assert final["status"] == "completed", final["status"]
    assert _questions(lifecycle, run_id) == []

    # The first source, the invoice read and its receipt stay retained.
    adapters = [step["adapter"] for step in final["steps"]]
    assert adapters.count("invoice.reconcile") == 1
    purchase_order_reads = [
        step for step in final["steps"]
        if step["adapter"] == "document.read"
        and (step.get("result") or {}).get("data", {}).get("po_id") == PO
        and (step.get("result") or {}).get("data", {}).get("invoice_id")
        is None
        and (step.get("result") or {}).get("data", {}).get("received_quantity")
        is None]
    assert len(purchase_order_reads) == 1, adapters
    invoice_reads = [
        step for step in final["steps"]
        if step["adapter"] == "document.read"
        and (step.get("result") or {}).get("data", {}).get("invoice_id")
        == INVOICE]
    assert len(invoice_reads) == 1, adapters
    assert invoice_reads[0]["result"]["verification"]["status"] == "verified"

    # Exactly one requested document appears, only after both facts, and its
    # bytes carry the current verified result bound to the reconciliation.
    artifacts = _applied_artifacts(final)
    assert len(artifacts) == 1, adapters
    blob = artifacts[0]["result"]["artifact"]
    artifact_path = Path(blob["path"])
    assert artifact_path.exists() and artifact_path.is_relative_to(tmp_path)
    assert hashlib.sha256(
        artifact_path.read_bytes()).hexdigest() == blob["sha256"]
    with ZipFile(artifact_path) as document:
        tree = ElementTree.fromstring(document.read("word/document.xml"))
    text = " ".join(
        node.text or "" for node in tree.iter() if node.tag.endswith("}t"))
    assert "130.00" in text, text
    assert PO in text, text
    bound = {
        str(requirement.get("step_id"))
        for requirement in artifacts[0].get("requires") or []
        if requirement.get("kind") == "receipt"
        and requirement.get("require") == "verified"
    }
    assert {reconciliations[0]["step_id"]} <= bound, bound


def test_wrong_subject_invoice_does_not_settle_the_invoice_question(
        route_env, tmp_path, monkeypatch):
    po, invoice, receiving = _fixtures(tmp_path)
    wrong = tmp_path / "wrong-po-invoice.json"
    wrong.write_text(json.dumps({
        "po_id": "PO-OTHER-9", "invoice_id": INVOICE, "quantity": "3",
        "unit_price": "40.00", "freight": "10.00", "currency": "USD"}))
    _install_transport(monkeypatch)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    run_id = _start(client, po)
    first = _questions(lifecycle, run_id)
    assert len(first) == 1, first
    first_question = first[0]

    rejected = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(wrong)},
              "reason": "wrong purchase order invoice"})
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["resolved_question_ids"] == [], body
    assert body["mismatched_question_ids"] == [
        first_question["question_id"]], body
    still_open = _questions(lifecycle, run_id)
    assert [q["question_id"] for q in still_open] == [
        first_question["question_id"]]
    assert _reconciliations(lifecycle.get_assignment(run_id)) == []

    # The valid invoice still settles the same obligation, then the same
    # task asks for receiving and completes after the valid record.
    accepted = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(invoice)},
              "reason": "correct purchase order invoice"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["resolved_question_ids"] == [
        first_question["question_id"]]
    second = _questions(lifecycle, run_id)
    assert len(second) == 1, second
    assert second[0]["inputs"]["missing"] == ["receiving"]

    answered = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "correct receiving record"})
    assert answered.status_code == 200, answered.text
    final = lifecycle.get_assignment(run_id)
    assert final["status"] == "completed", final["status"]
    assert len(_reconciliations(final)) == 1
