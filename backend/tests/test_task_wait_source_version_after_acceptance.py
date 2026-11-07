"""G2: a source changed after acceptance must not certify a stale value.

The invoice source is accepted/read while the task waits for the receiving
fact. The invoice file then changes on disk before the receiving answer lets
dependent reconciliation run. The current authorized version must either be
refused/re-resolved, or the result must use the new value; the old accepted
value must not silently certify the dependent artifact.

Public assignment routes, compiler/executor, lifecycle and scratch records are
real. Discovery/adaptation choices and auth use the existing controlled
fixtures. No provider, browser or live account action occurs.
"""
from __future__ import annotations

import json

from tests.test_assignment_routes import route_env  # noqa: F401
from tests.test_task_wait_two_fact_events import (
    PO,
    _applied_artifacts,
    _fixtures,
    _install_transport,
    _questions,
    _reconciliations,
    _start,
)


def _invoice(quantity: str, unit_price: str, freight: str) -> dict:
    return {
        "po_id": PO,
        "invoice_id": "INV-TWO-1",
        "quantity": quantity,
        "unit_price": unit_price,
        "freight": freight,
        "currency": "USD",
    }


def test_source_change_after_acceptance_is_revalidated_before_consumption(
        route_env, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    po, invoice, receiving = _fixtures(tmp_path)
    _install_transport(monkeypatch)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    run_id = _start(client, po)
    first = _questions(lifecycle, run_id)
    assert len(first) == 1, first

    accepted = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(invoice)},
              "reason": "authorized invoice accepted before receiving"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["resolved_question_ids"] == [
        first[0]["question_id"]], accepted.json()

    # The accepted/read invoice changes before dependent consumption.
    invoice.write_text(json.dumps(_invoice("4", "50.00", "10.00")))

    second = _questions(lifecycle, run_id)
    assert len(second) == 1, second
    assert second[0]["inputs"]["missing"] == ["receiving"]

    answered = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "authorized receiving record"})
    assert answered.status_code == 200, answered.text

    final = lifecycle.get_assignment(run_id)
    reconciliations = _reconciliations(final)
    stale = [
        step for step in reconciliations
        if str((step.get("result") or {}).get("value") or "") == "130.00"]
    assert not stale, (
        "a changed source certified the old accepted value",
        final["status"], reconciliations)
    if final["status"] == "completed":
        assert reconciliations, (
            "completion must be backed by a reconciliation", final)
        assert str(reconciliations[0]["result"]["value"]) == "210.00", (
            "completion must use the current source value",
            reconciliations[0]["result"])
    else:
        # Refusal/re-resolution is acceptable; no stale final artifact may be
        # published while the source version is unresolved.
        assert _applied_artifacts(final) == [], (
            "a stale artifact was published", _applied_artifacts(final))


def test_explicitly_authorized_newer_version_replaces_cached_result(
        route_env, tmp_path, monkeypatch):
    """A caller-supplied newer version is allowed; stale bytes are not.

    Re-posting the same authorized source path after the bytes change is the
    explicit newer-version action. It must reuse/invalidate the existing
    source step and let dependent work use the new value, not the accepted
    cached 130.00.
    """
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    po, invoice, receiving = _fixtures(tmp_path)
    _install_transport(monkeypatch)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    run_id = _start(client, po)
    first = _questions(lifecycle, run_id)
    accepted = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(invoice)},
              "reason": "authorized invoice accepted before receiving"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["resolved_question_ids"] == [
        first[0]["question_id"]], accepted.json()

    invoice.write_text(json.dumps(_invoice("4", "50.00", "10.00")))
    replaced = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(invoice)},
              "reason": "explicitly authorized newer invoice version"})
    assert replaced.status_code == 200, replaced.text

    second = _questions(lifecycle, run_id)
    assert len(second) == 1, second
    assert second[0]["inputs"]["missing"] == ["receiving"]
    answered = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "authorized receiving record"})
    assert answered.status_code == 200, answered.text

    final = lifecycle.get_assignment(run_id)
    reconciliations = _reconciliations(final)
    assert final["status"] == "completed", (
        final["status"], reconciliations,
        lifecycle.get_task(run_id).get("task_revision", {}).get("unresolved"))
    assert len(reconciliations) == 1, reconciliations
    assert str(reconciliations[0]["result"]["value"]) == "210.00", (
        reconciliations[0]["result"])
    assert not [
        step for step in reconciliations
        if str((step.get("result") or {}).get("value") or "") == "130.00"]
