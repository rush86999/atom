"""Focused preparation tests for the incomplete-invoice browser driver.

These validate the partial/complete invoice fixture and every authored
loopback completion against the real planning/adaptation schemas and the
existing provider_shim index. They do not create a world, launch a browser or
contact a provider.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO / "scripts" / "acceptance" / (
    "browser_invoice_partial_evidence.py")


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "browser_invoice_partial_evidence", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


def test_partial_and_complete_invoice_fixture(driver, tmp_path):
    files = driver._write_fixture_files(tmp_path)
    partial = json.loads((tmp_path / driver.PARTIAL_NAME).read_text())
    complete = json.loads((tmp_path / driver.COMPLETE_NAME).read_text())
    assert partial["unit_price"] is None
    assert complete["unit_price"] == "42.50"
    assert files["expected_total"] == "140.25"
    assert partial["invoice_id"] == driver.INVOICE
    assert partial["po_id"] == driver.PO


def test_authored_shim_is_real_schema_and_indexed(driver):
    result = driver._validate_shim()
    assert len(result["responses"]) == 5
    assert result["responses"][0]["model"] == "WorkAdaptationProposal"
    assert result["responses"][0]["payload"]["decision"] == "replan"
    assert result["responses"][1]["model"] == "WorkAdaptationProposal"
    assert result["responses"][1]["payload"]["decision"] == "replan"
    assert result["responses"][1]["payload"]["observation_ids"] == [
        "fixture-observation"]
    assert result["responses"][2]["model"] == "CompactWaitChoiceProposal"
    assert result["responses"][2]["payload"]["decision"] == "clarify"
    assert result["responses"][3]["model"] == "EmployeeWorkProposal"
    assert result["responses"][4]["payload"]["decision"] == "clarify"
    assert (
        result["responses"][3]["payload"]["evidence_reads"][0]["source_id"]
        == "fixture:po.json")
    assert len(result["provider_shim_keys"]) == 5


def test_unlabelled_default_is_rejected(driver, tmp_path):
    doc = json.loads(driver.FIXTURE.read_text(encoding="utf-8"))
    doc["default"] = "plain fallback"
    path = tmp_path / "bad_shim.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError, match="not labelled"):
            driver._validate_shim()
    finally:
        driver.FIXTURE = original


def test_complete_evidence_requires_invoice_reconciliation(driver, tmp_path):
    doc = json.loads(driver.FIXTURE.read_text(encoding="utf-8"))
    payload = json.loads(doc["responses"][0]["response"])
    payload["decision"] = "retain"
    payload["work_request"] = None
    doc["responses"][0]["response"] = json.dumps(payload)
    path = tmp_path / "wrong_decision.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError, match="not a replan"):
            driver._validate_shim()
    finally:
        driver.FIXTURE = original


def _scratch_run_db(path: Path, lifecycle: dict) -> str:
    """A scratch goal_runs row shaped like a real run3 parameters column."""
    import sqlite3

    con = sqlite3.connect(path)
    try:
        con.execute("create table goal_runs (id text primary key, parameters text)")
        con.execute(
            "insert into goal_runs (id, parameters) values (?, ?)",
            ("run3", json.dumps({"task_lifecycle": lifecycle})))
        con.commit()
    finally:
        con.close()
    return "run3"


def test_open_questions_read_the_sibling_task_revision(driver, tmp_path):
    """Regression: unresolved entries live in task_lifecycle.task_revision,
    a SIBLING of assignment. An assignment-only projection hid the one open
    invoice question on the real run3 SQLite."""
    db = tmp_path / "run3.db"
    lifecycle = {
        "assignment": {
            "assignment_id": "a-1",
            "status": "waiting",
            "steps": [],
        },
        "task_revision": {
            "revision": 2,
            "unresolved": [
                {"question_id": "q-open", "status": "open",
                 "question": f"Which source contains {driver.INVOICE}?"},
                {"question_id": "q-done", "status": "resolved",
                 "question": "already answered"},
            ],
        },
    }
    run_id = _scratch_run_db(db, lifecycle)

    record = driver._durable_assignment(db, run_id)
    assert record["assignment_id"] == "a-1"
    assert record["status"] == "waiting"
    assert record["task_revision"]["revision"] == 2

    open_questions = driver._open_questions(record)
    assert [q["question_id"] for q in open_questions] == ["q-open"]
    assert driver.INVOICE in open_questions[0]["question"]


def test_missing_run_reads_as_empty(driver, tmp_path):
    db = tmp_path / "empty.db"
    _scratch_run_db(db, {"assignment": {}, "task_revision": {"unresolved": []}})
    assert driver._durable_assignment(db, "absent") == {}
    assert driver._open_questions(driver._durable_assignment(db, "absent")) == []


def _shim_index(driver, tmp_path):
    from scripts.orchestration_acceptance import provider_shim

    path = tmp_path / "invoice_shim.json"
    path.write_text(driver.FIXTURE.read_text(encoding="utf-8"),
                    encoding="utf-8")
    return provider_shim.load_script(path)


def _select(index, prompt):
    """Apply provider_shim's bare-substring selection to an authored index."""
    blob = prompt.lower()
    return next(
        ((key, response) for key, response in index.items()
         if isinstance(key, str) and key in blob),
        (None, None))


def _complete_follow_up_prompt():
    from core.employee_adaptation import (
        WorkAdaptationProposal,
        _adaptation_prompt,
    )

    # The MqoAP4 capture's post-upload request: both uploads applied, the
    # invoice question resolved, no missing prerequisite, and the full
    # follow-up prompt rather than the compact allowed_step_ids shape.
    return _adaptation_prompt({
        "objective": "Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63",
        "existing_step_ids": [
            "source-1", "source-2", "source-3", "source-4"],
        "missing_prerequisites": [],
        "ready_operations": ["invoice_reconciliation"],
        "available_business_operations": [{
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": "ready",
            "missing": [],
            "roles": {
                "invoice": ["source-4"],
                "purchase_order": ["source-1"],
                "receiving": ["source-2"],
            },
            "known_identities": {
                "invoice.invoice_id": "INV-TRIGGER-91",
                "invoice.po_id": "PO-TRIGGER-63",
            },
            "evidence": [
                {"step_id": "source-1"},
                {"step_id": "source-2"},
                {"step_id": "source-3"},
                {"step_id": "source-4"},
            ],
        }],
        "resolved_obligations": [{
            "question_id": "a4100684-07fc-48c5-8c48-74c3ff982de6",
            "concept": "invoice_reconciliation",
            "item": "invoice reconciliation",
            "resolution": (
                "authorized source doc_f0dd39d633cd0bda6569d2d7 supplied "
                "the requested evidence role(s)"),
            "resolved_at": "2026-11-13T04:40:35.265852+00:00",
        }],
        "rules": {
            "allowed_proposal_kinds": ["replan"],
            "allowed_work_requests": ["invoice_reconciliation"],
        },
    }, [{"observation_id": "evidence-209dfab9b6ecd2f491bf",
         "kind": "evidence_result", "step_id": "source-4"}],
        WorkAdaptationProposal)


def _partial_follow_up_prompt():
    from core.employee_adaptation import (
        WorkAdaptationProposal,
        _adaptation_prompt,
    )

    # The partial-upload state must keep asking for the invoice; it must never
    # be routed to the complete-evidence reconciliation response.
    return _adaptation_prompt({
        "objective": "Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63",
        "existing_step_ids": ["source-1", "source-2", "source-3"],
        "missing_prerequisites": [{
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": "missing",
            "missing": ["invoice"],
            "known_identities": {
                "purchase_order.po_id": "PO-TRIGGER-63",
                "receiving.po_id": "PO-TRIGGER-63",
            },
        }],
        "ready_operations": [],
        "available_business_operations": [{
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "status": "missing",
            "missing": ["invoice"],
            "roles": {
                "invoice": [],
                "purchase_order": ["source-1"],
                "receiving": ["source-2"],
            },
            "evidence": [{"step_id": "source-1"}, {"step_id": "source-2"}],
        }],
        "rules": {
            "allowed_proposal_kinds": ["clarify", "retain"],
            "allowed_work_requests": [],
        },
    }, [{"observation_id": "evidence-partial", "kind": "evidence_result",
         "step_id": "source-3"}], WorkAdaptationProposal)


def test_complete_follow_up_routes_to_reconciliation(driver, tmp_path):
    from scripts.orchestration_acceptance import provider_shim

    index = _shim_index(driver, tmp_path)
    prompt = _complete_follow_up_prompt()

    # This is exactly why the old fixture never served its replan: the full
    # follow-up prompt has no compact allowed_step_ids payload.
    assert "allowed_step_ids" not in prompt.lower()
    assert '"ready_operations": ["invoice_reconciliation"]' in prompt.lower()

    key, response = _select(index, prompt)
    assert key == '"ready_operations": ["invoice_reconciliation"]'
    payload = json.loads(provider_shim.bind_prompt_observation_ids(
        response, prompt))
    assert payload["decision"] == "replan"
    assert payload["work_request"]["operation"] == "invoice_reconciliation"
    assert payload["observation_ids"] == ["evidence-209dfab9b6ecd2f491bf"]


def test_partial_follow_up_still_asks_for_the_invoice(driver, tmp_path):
    index = _shim_index(driver, tmp_path)

    key, response = _select(index, _partial_follow_up_prompt())
    assert key == "missing_prerequisites"
    payload = json.loads(response)
    assert payload["decision"] == "clarify"
    assert payload["clarification"]["missing_roles"] == ["invoice"]
    assert driver.INVOICE in payload["clarification"]["question"]
    assert payload.get("work_request") is None


def test_compact_complete_continuation_keeps_its_own_replan(driver, tmp_path):
    from core.employee_adaptation import _compact_single_request_prompt

    index = _shim_index(driver, tmp_path)
    prompt = _compact_single_request_prompt({
        "objective": "Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63",
        "existing_step_ids": ["source-1", "source-2", "source-3", "source-4"],
        "teaching": {"terms": {}},
        "available_business_operations": [{
            "operation": "invoice_reconciliation",
            "status": "ready",
            "evidence": [{"step_id": "source-1"}, {"step_id": "source-2"},
                         {"step_id": "source-4"}],
            "roles": {"invoice": ["source-4"],
                      "purchase_order": ["source-1"],
                      "receiving": ["source-2"]},
            "known_identities": {"invoice.po_id": "PO-TRIGGER-63"},
        }],
        "rules": {"allowed_work_requests": ["invoice_reconciliation"]},
    })
    assert "allowed_step_ids" in prompt.lower()
    key, response = _select(index, prompt)
    assert key == "allowed_step_ids"
    assert json.loads(response)["work_request"]["operation"] == (
        "invoice_reconciliation")


def test_full_follow_up_replan_binds_the_prompts_observation_ids(
        driver, tmp_path):
    """The served full-schema replan must cite the request's own handles.

    ``adopt_adaptation`` refuses a replan with an empty observation list, so a
    static authored ``[]`` produced a schema-valid completion that could never
    be adopted. The shim now expands ``{OBSERVATION_IDS}`` from the prompt.
    """
    from scripts.orchestration_acceptance import provider_shim

    index = _shim_index(driver, tmp_path)
    prompt = _complete_follow_up_prompt()
    key, response = _select(index, prompt)
    assert key == driver.FULL_FOLLOW_UP_MATCH
    assert provider_shim.OBSERVATION_IDS_PLACEHOLDER in response

    bound = provider_shim.bind_prompt_observation_ids(response, prompt)
    payload = json.loads(bound)
    assert payload["observation_ids"] == ["evidence-209dfab9b6ecd2f491bf"]
    assert payload["decision"] == "replan"
    assert payload["work_request"]["operation"] == "invoice_reconciliation"


def test_prompt_observation_binding_fails_closed_without_observations(
        driver):
    from scripts.orchestration_acceptance import provider_shim

    with pytest.raises(ValueError, match="names no observation ids"):
        provider_shim.bind_prompt_observation_ids(
            '{"observation_ids": {OBSERVATION_IDS}, "decision": "replan"}',
            "no observation block in this request")


def test_production_adoption_still_refuses_an_empty_observation_replan(
        driver):
    """The fixture is fixed; the production guard must stay in place."""
    from types import SimpleNamespace

    from core.employee_adaptation import PlanPatchError, adopt_adaptation

    lifecycle = SimpleNamespace(get_task=lambda _run_id: {
        "task_version": 1,
        "assignment": {
            "plan_revision": 1, "steps": [], "authorized_actions": [],
            "patch_history": [],
        },
    })
    proposal = {
        "decision": "replan",
        "observation_ids": [],
        "work_request": {
            "operation": "invoice_reconciliation",
            "invoice_step_id": "source-4",
            "purchase_order_step_id": "source-1",
            "receiving_step_id": "source-2",
            "currency": "USD",
        },
    }
    with pytest.raises(PlanPatchError, match="requires observation ids"):
        adopt_adaptation(lifecycle, "run", proposal)
    assert proposal["observation_ids"] == []


def test_full_follow_up_without_prompt_bound_ids_fails_preflight(
        driver, tmp_path):
    from scripts.orchestration_acceptance import provider_shim

    doc = json.loads(driver.FIXTURE.read_text(encoding="utf-8"))
    raw = doc["responses"][1]["response"]
    bound = provider_shim.bind_prompt_observation_ids(
        raw, 'OBSERVATIONS:\n[{"observation_id": "fixture-observation"}]')
    payload = json.loads(bound)
    payload["observation_ids"] = []
    doc["responses"][1]["response"] = json.dumps(payload)
    path = tmp_path / "empty_full_observation_ids.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError,
                           match="refuses an empty observation list"):
            driver._validate_shim()
    finally:
        driver.FIXTURE = original
