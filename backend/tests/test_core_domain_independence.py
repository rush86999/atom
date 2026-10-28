# -*- coding: utf-8 -*-
"""Domain independence of the core working mechanism.

The product is a general employee workspace: business vocabulary, schemas
and decision choices come from the source and the accepted task. Nothing in
this suite should depend on procurement/order words. Each check runs the
SAME code over at least two unrelated domains:

* procurement records with an ``O-1001``-style code and Process/Escalate;
* grant applications with a ``GR-2026-014`` reference and Fund/Decline/Hold;
* helpdesk hours with no currency column and a plain count operation.

What is platform-owned here: provenance, named gaps, deterministic
arithmetic, contract validation. What is task-owned: field roles, decisions,
subjects and output shape.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.dataset_aggregation import execute_validated_aggregate_plan
from core.pending_file_task import is_aggregate_request
from core.review_result import build_review_result


def _entry(tmp_path, df, name, file_name):
    path = tmp_path / f"{name.replace(' ', '_')}.parquet"
    df.to_parquet(path, index=False)
    return {
        "dataset_name": f"upload_{name.lower().replace(' ', '_')}",
        "entity_name": name,
        "file_name": file_name,
        "parquet_path": str(path),
        "content_hash": f"hash-{name}",
        "columns": [c for c in df.columns if c != "__sheet_row"],
        "row_count": len(df),
    }


def _grants(tmp_path):
    df = pd.DataFrame([
        {"Grant Ref": "GR-2026-014", "Stage": "Submitted",
         "Requested Amount": 40000.0, "Currency": "CAD", "__sheet_row": 2},
        {"Grant Ref": "GR-2026-021", "Stage": "Submitted",
         "Requested Amount": 12500.50, "Currency": "CAD", "__sheet_row": 3},
        {"Grant Ref": "GR-2026-033", "Stage": "Withdrawn",
         "Requested Amount": 99000.0, "Currency": "CAD", "__sheet_row": 4},
        {"Grant Ref": "GR-2026-040", "Stage": "Submitted",
         "Requested Amount": None, "Currency": "CAD", "__sheet_row": 5},
    ])
    return _entry(tmp_path, df, "Applications", "grants_2026.xlsx")


def _tickets(tmp_path):
    df = pd.DataFrame([
        {"Ticket": "HD-88", "State": "Open", "Hours": 1.5, "__sheet_row": 2},
        {"Ticket": "HD-91", "State": "Open", "Hours": 2.25, "__sheet_row": 3},
        {"Ticket": "HD-97", "State": "Closed", "Hours": 9.0, "__sheet_row": 4},
    ])
    return _entry(tmp_path, df, "Tickets", "helpdesk_hours.csv")


@pytest.mark.asyncio
async def test_sum_operation_is_not_quantity_times_price(tmp_path):
    """A single named measure totals without inventing qty/price."""
    entry = _grants(tmp_path)
    result = await execute_validated_aggregate_plan(
        [entry],
        {
            "dataset_name": entry["dataset_name"],
            "sql": 'SELECT "__sheet_row", "Grant Ref", "Stage", '
                   '"Requested Amount", "Currency" FROM df '
                   "WHERE \"Stage\" = 'Submitted'",
            "operation": "sum",
            "identity_column": "Grant Ref",
            "value_column": "Requested Amount",
            "currency_column": "Currency",
            "status_column": "Stage",
        },
        "Applications sheet submitted requested amount by currency",
        file_name="grants_2026.xlsx",
    )
    assert result["status"] == "partial"          # one blank amount is a gap
    assert result["complete"] is False
    assert result["operation"] == "sum"
    assert result["subtotals"]["CAD"]["value"] == "52500.50"
    assert result["selected_count"] == 3
    assert result["known_count"] == 2
    assert result["gaps"] == [{
        "identity": "GR-2026-040", "row": 5,
        "missing": "value (Requested Amount)", "cell": "C5",
    }]
    assert "quantity" not in result["block"].lower()


@pytest.mark.asyncio
async def test_sum_operation_without_currency_column_is_unstated(tmp_path):
    entry = _tickets(tmp_path)
    result = await execute_validated_aggregate_plan(
        [entry],
        {
            "dataset_name": entry["dataset_name"],
            "sql": 'SELECT "__sheet_row", "Ticket", "State", "Hours" '
                   'FROM df WHERE "State" = \'Open\'',
            "operation": "sum",
            "identity_column": "Ticket",
            "value_column": "Hours",
            "status_column": "State",
        },
        "Tickets sheet hours on open tickets",
        file_name="helpdesk_hours.csv",
    )
    assert result["status"] == "complete"
    assert result["subtotals"]["(unstated)"]["value"] == "3.75"
    assert [r["identity"] for r in result["rows"]] == ["HD-88", "HD-91"]


@pytest.mark.asyncio
async def test_count_operation_has_no_measure_assumption(tmp_path):
    entry = _tickets(tmp_path)
    result = await execute_validated_aggregate_plan(
        [entry],
        {
            "dataset_name": entry["dataset_name"],
            "sql": 'SELECT "__sheet_row", "Ticket", "State" FROM df '
                   "WHERE \"State\" = 'Open'",
            "operation": "count",
            "identity_column": "Ticket",
            "status_column": "State",
        },
        "how many open tickets are there",
        file_name="helpdesk_hours.csv",
    )
    assert result["status"] == "complete"
    assert result["operation"] == "count"
    assert result["subtotals"]["(unstated)"]["rows"] == 2
    assert result["subtotals"]["(unstated)"]["value"] == "2.00"


def test_spreadsheet_operation_classifier_is_vocabulary_neutral():
    positive = [
        "total the requested amount for submitted applications",
        "how many open tickets are there",
        "sum hours per state",
        "calculate the approved rows total",
    ]
    negative = [
        "find GR-2026-014",
        "show ticket HD-88",
        "what does the applications sheet say about GR-2026-033",
        "read cell C5",
    ]
    for ask in positive:
        assert is_aggregate_request(ask) is True, ask
    for ask in negative:
        assert is_aggregate_request(ask) is False, ask


def _review(decisions, decision, subject):
    return build_review_result(
        execution_id="exec-domain-independent",
        requested_records=[subject],
        answer=(
            f"{subject} was assessed from its recorded row.\n"
            "```review_result\n"
            f'{{"assessments": [{{"subject_id": "{subject}", '
            f'"decision": "{decision}", '
            '"evidence_ids": ["ev:row"], "policy_ids": ["policy-1"], '
            '"unresolved_requirements": []}]}\n'
            "```"
        ),
        allowed_decisions=decisions,
        evidence_index=[{
            "evidence_id": "ev:row",
            "subject_id": subject,
            "source_identity": {
                "file_name": "source.xlsx",
                "resource_id": "sha1:one",
                "content_hash": "one",
            },
            "retrieval_operation": "datasets.aggregate",
            "retrieval_execution_id": "exec-domain-independent",
            "row_ref": "Sheet!R2",
            "values": [],
        }],
        policy_index=[{"policy_id": "policy-1", "topic": "scope",
                       "lesson": "task-defined"}],
    )


def test_decision_choices_belong_to_the_task_not_the_platform():
    orders = _review(["Process", "Escalate"], "Escalate", "O-1001")
    grants = _review(["Fund", "Decline", "Hold"], "Hold", "GR-2026-014")
    tickets = _review(["Close", "Reassign"], "Reassign", "HD-88")
    assert orders["ok"] is True
    assert grants["ok"] is True
    assert tickets["ok"] is True

    # A decision outside the taught set is rejected in every domain.
    rogue = _review(["Fund", "Decline", "Hold"], "Process", "GR-2026-014")
    assert rogue["ok"] is False
    assert any(
        e.get("code") == "invalid_decision"
        for e in rogue.get("errors", [])
    )


def test_subject_identity_is_not_a_fixed_record_id_shape():
    """Codes, refs and human labels are all valid subjects."""
    for subject in ("0007", "O-1001", "GR-2026-014", "HD-88", "Acme renewal"):
        result = _review(["Approve", "Reject"], "Approve", subject)
        assert result["ok"] is True, subject
        assert result["assessments"][0]["subject_id"] == subject
