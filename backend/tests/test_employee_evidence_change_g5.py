"""Real evidence-sensitive change with selective retention.

The employee derives the quote from actual workbook rows. A later source
value change is persisted as a new read of the same authorized resource; the
dependent quote/artifact re-evaluates while an unrelated accepted read keeps
its operation id and result.
"""
from __future__ import annotations

import json

from tests.test_assignment_routes import _scotch_catalog, route_env  # noqa: F401


def test_real_source_value_change_reopens_only_the_dependent_artifact(
        route_env, tmp_path, monkeypatch):
    import pandas as pd

    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    note = tmp_path / "delivery-note.txt"
    note.write_text("Unrelated delivery note: leave this branch intact.\n")

    async def fake_work(context, **_kwargs):
        source = next(
            (item for item in context["sources"]
             if str(item.get("representation") or "") == "parquet_frame"),
            context["sources"][0])
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized price list",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read the authorized price list",
                    "source_id": source["source_id"],
                }],
            },
            "source": "model", "technical_fallback": False, "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        assert context["work_request_schemas"]
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="derive the quote from the accepted price rows",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=QuoteCalculationRequest(
                    operation="quote_calculation",
                    source_step_id="source-1",
                    columns=QuoteColumns(
                        item_id="Item Number",
                        description="Description",
                        quantity="Quantity",
                        unit_price="Unit Price",
                        currency="Currency"),
                    currency="USD",
                    freight=MoneyTerm(
                        value="20.00", authority_ref="freight"),
                    tax=TaxTerm(
                        basis="none", authority_ref="tax_basis"),
                )).model_dump(),
            "source": "model", "technical_fallback": False, "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare the customer quote document from evidence",
            "sources": [{
                "kind": "workbook",
                "dataset_name": "scotch_parts_price_list",
                "sheet": "US$ SCOTCH PARTS",
            }],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "20.00",
                "tax_basis": "none"},
            "requested_output": "document",
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    before = route_env["lifecycle"].get_assignment(run_id)
    assert before["status"] == "completed", before["status"]
    before_calc = next(
        step for step in before["steps"] if step["adapter"] == "quote.calculate")
    assert before_calc["result"]["value"] == "105.00"
    before_artifact = next(
        item for item in before["deliverables"] if item["kind"] == "document")
    before_revision = before_artifact["artifact_revision"]

    # Add an unrelated authorized note through the normal source-add route.
    added = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(note)},
              "reason": "unrelated delivery note authorized"})
    assert added.status_code == 200, added.text
    after_add = route_env["lifecycle"].get_assignment(run_id)
    note_before = next(
        step for step in after_add["steps"] if step["step_id"] == "source-2")
    assert note_before["status"] == "applied", note_before
    note_operation = note_before.get("operation_id")
    note_result = dict(note_before.get("result") or {})

    # A real source value changes: SC-1 unit price 10 -> 40. The next read
    # must expose the changed rows and the dependent quote/artifact must
    # re-evaluate; the unrelated note read must not.
    parquet = tmp_path / "sheet_datasets" / "scotch-parts.parquet"
    frame = pd.read_parquet(parquet)
    frame.loc[0, "Unit Price"] = 40.0
    frame.loc[0, "Total"] = 80.0
    frame.to_parquet(parquet, index=False)

    invalidated = route_env["client"].post(
        f"/api/assignments/{run_id}/invalidate/source-1",
        json={"reason": "authorized source value changed"})
    assert invalidated.status_code == 200, invalidated.text
    affected = invalidated.json()["affected_steps"]
    assert "source-1" in affected
    assert "quote-total" in affected or "quote-calculate" in affected

    after = route_env["lifecycle"].get_assignment(run_id)
    assert after["status"] == "completed", after["status"]
    after_calc = next(
        step for step in after["steps"] if step["adapter"] == "quote.calculate")
    assert after_calc["status"] == "applied"
    assert after_calc["result"]["value"] == "165.00"
    assert after_calc["prior_results"], after_calc
    note_after = next(
        step for step in after["steps"] if step["step_id"] == "source-2")
    assert note_after.get("operation_id") == note_operation
    assert dict(note_after.get("result") or {}) == note_result
    after_artifact = next(
        item for item in after["deliverables"] if item["kind"] == "document")
    assert after_artifact["status"] == "applied"
    assert after_artifact["artifact_revision"] != before_revision
    text = "\n".join(
        paragraph.text for paragraph in __import__("docx").Document(
            after_artifact["artifact_path"]).paragraphs)
    for table in __import__("docx").Document(
            after_artifact["artifact_path"]).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "165.00" in text
    assert "price-book.xlsx" in text or "scotch-parts.xlsx" in text
