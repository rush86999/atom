"""A real new source version lets the reasoner choose the next work again.

The initial employee quote is derived from version 1. A new active catalog
version changes a real unit price; adding that version to the completed job
persists its identity/version, then the same adaptation contract is asked
what the changed evidence supports. A previous unrelated read keeps its
operation id and result.
"""
from __future__ import annotations

import json

from tests.test_assignment_routes import _scotch_catalog, route_env  # noqa: F401


def test_new_source_version_triggers_model_chosen_reassessment(
        route_env, tmp_path, monkeypatch):
    import docx
    import pandas as pd

    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
    entry = _scotch_catalog(route_env, tmp_path, monkeypatch)

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
        latest = observations[-1]
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason=(
                    "derive the quote from the newest accepted price rows"),
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=QuoteCalculationRequest(
                    operation="quote_calculation",
                    source_step_id=str(latest["step_id"]),
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
            "objective": (
                "Prepare the customer quote document from the authorized "
                "price list"),
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
    first_calc = next(
        step for step in before["steps"]
        if step["adapter"] == "quote.calculate")
    assert first_calc["result"]["value"] == "105.00"
    first_operation = first_calc["operation_id"]
    deliverable = (before.get("deliverables") or [{}])[0]
    first_sha = deliverable["sha256"]

    # A real active version changes the first unit price 10 -> 40. The
    # materialized frame and the catalog version move together.
    parquet = tmp_path / "sheet_datasets" / "scotch-parts.parquet"
    frame = pd.read_parquet(parquet)
    frame.loc[0, "Unit Price"] = 40.0
    frame.loc[0, "Total"] = 80.0
    frame.to_parquet(parquet, index=False)
    entry.content_hash = "c" * 40
    route_env["db"].commit()

    added = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={
            "source": {
                "kind": "workbook",
                "dataset_name": "scotch_parts_price_list",
                "sheet": "US$ SCOTCH PARTS",
            },
            "reason": "supplier published a revised price version",
        })
    assert added.status_code == 200, added.text
    body = added.json()
    rounds = body.get("reassessment_rounds") or []
    assert rounds, body
    assert rounds[0]["source"] == "model", rounds
    assert rounds[0]["technical_fallback"] is False, rounds
    assert rounds[0]["work_request_operation"] == "quote_calculation", rounds

    after = route_env["lifecycle"].get_assignment(run_id)
    assert after["status"] == "completed", after["status"]
    versioned_read = next(
        step for step in after["steps"]
        if step["step_id"] == "source-2")
    assert versioned_read["status"] == "applied"
    assert versioned_read["inputs"]["resource_binding"][
        "source_version"] == "c" * 40
    assert versioned_read["result"]["source_version"] == "c" * 40
    first_after = next(
        step for step in after["steps"]
        if step["step_id"] == first_calc["step_id"])
    assert first_after["operation_id"] == first_operation
    assert first_after["result"]["value"] == "105.00"
    second_calc = next(
        step for step in after["steps"]
        if step["adapter"] == "quote.calculate"
        and step["step_id"] != first_calc["step_id"])
    assert second_calc["result"]["value"] == "165.00"
    assert second_calc["prior_results"] == []
    deliverable_after = (after.get("deliverables") or [{}])[0]
    assert deliverable_after["artifact_revision"] != first_sha
    text = "\n".join(
        paragraph.text for paragraph in docx.Document(
            deliverable_after["artifact_path"]).paragraphs)
    for table in docx.Document(deliverable_after["artifact_path"]).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "165.00" in text, text
    assert "80.00" in text and "60.00" in text, text
    # The superseded version's total stays in durable history, not in the
    # current customer artifact.
    assert "105.00" not in text, text
