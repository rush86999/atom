"""TASK-WAIT-01 E3: public source-route revocation recheck.

A waiting assignment asks for one tabular price source. The answer is a real
local connected-catalog reference backed by the existing IntegrationToken
grant (no external provider call). With the grant revoked, the public
`/sources` route refuses the answer before any read/quote effect and leaves
the same question open. Re-activating the same grant is the valid unchanged
twin: the identical answer settles only that question and the same task
produces one verified quote receipt.

Public assignment routes, the real compiler/executor/catalog recheck and
scratch durable records are exercised. Proposal/auth transport are the
repository's controlled fixtures.
"""
from __future__ import annotations

import json

import pandas as pd

from tests.test_assignment_routes import route_env  # noqa: F401


DATASET = "e3_quote_prices"
SHEET = "Prices"


def _seed_connected_grant(route_env, tmp_path):
    from core.models import DatasetEntry, IntegrationToken

    db = route_env["db"]
    root = tmp_path / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    parquet = root / "quote.parquet"
    pd.DataFrame({
        "Item": ["SC-1"],
        "Qty": [3],
        "Unit Price": [12.5],
        "Currency": ["USD"],
        "__sheet_row": [2],
    }).to_parquet(parquet, index=False)
    db.add(DatasetEntry(
        id="e3-entry", workspace_id="ws-1", tenant_id="tenant-1",
        created_by="lead-1", source_kind="file", source="onedrive",
        external_id="e3-drive", file_name="quote.xlsx",
        content_hash="b" * 40, entity_name=SHEET, dataset_name=DATASET,
        parquet_path=str(parquet), row_count=1, column_count=4,
        columns_json={
            "columns": [
                {"name": "Item"}, {"name": "Qty"},
                {"name": "Unit Price"}, {"name": "Currency"},
                {"name": "__sheet_row"}],
            "coverage": {
                "known": True, "source_row_count": 1,
                "materialized_row_count": 1, "truncated": False},
        },
        status="active"))
    token = IntegrationToken(
        id="e3-token", tenant_id="tenant-1", user_id="lead-1",
        workspace_id="ws-1", provider="onedrive",
        access_token="local-not-a-secret", status="active")
    db.add(token)
    db.commit()
    return token


def _install_transport(monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

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
        tabular = next(
            (item for item in context.get("evidence_results") or []
             if item.get("rows")
             and any(str(entry.get("column") or "") == "Unit Price"
                     for entry in (item.get("schema") or [])
                     if isinstance(entry, dict))),
            None)
        common = {
            "reason": "model-selected supported work",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if tabular is None:
            return {
                "proposal": WorkAdaptationProposal(
                    decision="clarify",
                    clarification={
                        "question": (
                            "Which authorized source contains the tabular "
                            "price rows needed for the quote?"),
                        "concept": "quote_calculation",
                        "unblocks": "quote calculation",
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
                work_request=QuoteCalculationRequest(
                    operation="quote_calculation",
                    source_step_id=str(tabular["step_id"]),
                    columns=QuoteColumns(
                        item_id="Item", quantity="Qty",
                        unit_price="Unit Price", currency="Currency"),
                    currency="USD",
                    freight=MoneyTerm(value="0.00", authority_ref="freight"),
                    tax=TaxTerm(basis="none", authority_ref="tax_basis")),
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


def _start(client, memo):
    answer = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare a quote for item SC-1 from the price list",
            "sources": [{"path": str(memo)}],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "0.00", "tax_basis": "none"},
            "use_model": True,
        })
    assert answer.status_code == 200, answer.text
    return answer.json()["run_id"]


def _questions(lifecycle, run_id):
    from core.task_lifecycle import open_unresolved_questions

    return open_unresolved_questions(lifecycle.get_task(run_id))


def _source_steps(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"] in ("dataset.read", "workbook.read")
        and step["status"] == "applied"
    ]


def _quotes(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"] == "quote.calculate"
        and step["status"] == "applied"
    ]


def _answer(client, run_id):
    return client.post(
        f"/api/assignments/{run_id}/sources",
        json={
            "source": {
                "kind": "workbook",
                "dataset_name": DATASET,
                "sheet": SHEET,
            },
            "reason": "authorized local price-list answer",
        })


def test_revoked_local_grant_refuses_source_answer_then_valid_twin_completes(
        route_env, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    # datasets_root() anchors under ATOM_DATA_DIR/sheet_datasets; keep the
    # connected catalog's materialized copy inside this owned scratch root.
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    token = _seed_connected_grant(route_env, tmp_path)
    _install_transport(monkeypatch)
    memo = tmp_path / "request.txt"
    memo.write_text("Please prepare the SC-1 quote from the price list.")
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    run_id = _start(client, memo)
    question = _questions(lifecycle, run_id)
    assert len(question) == 1, question
    assert question[0]["concept"] == "quote_calculation", question[0]
    before = lifecycle.get_assignment(run_id)
    assert _source_steps(before) == []
    assert _quotes(before) == []

    # The owner revokes the existing local grant while the task waits.
    token.status = "revoked"
    route_env["db"].commit()
    revoked = _answer(client, run_id)
    assert revoked.status_code == 403, revoked.text
    after_revoke = lifecycle.get_assignment(run_id)
    assert _source_steps(after_revoke) == []
    assert _quotes(after_revoke) == []
    still_open = _questions(lifecycle, run_id)
    assert [item["question_id"] for item in still_open] == [
        question[0]["question_id"]]

    # Valid unchanged twin: the same grant re-activated and the same answer.
    token.status = "active"
    route_env["db"].commit()
    accepted = _answer(client, run_id)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["resolved_question_ids"] == [
        question[0]["question_id"]], accepted.json()

    final = lifecycle.get_assignment(run_id)
    assert final["status"] == "completed", {
        "status": final["status"],
        "steps": [(step["adapter"], step["status"],
                   (step.get("result") or {}).get("value"),
                   step.get("error"))
                  for step in final["steps"]],
        "open": _questions(lifecycle, run_id),
        "rounds": accepted.json().get("continuation_rounds"),
    }
    assert len(_source_steps(final)) == 1, [
        (step["adapter"], step["status"]) for step in final["steps"]]
    quotes = _quotes(final)
    assert len(quotes) == 1, [
        (step["adapter"], step["status"]) for step in final["steps"]]
    assert quotes[0]["result"]["value"] == "37.50"
    assert _questions(lifecycle, run_id) == []
