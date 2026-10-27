# -*- coding: utf-8 -*-
"""Confirmation narration must be judged against the STRUCTURED read.

Rehearsal a1d357410 (2026-10-27), O-1010 confirmation:

* the read persisted the correct structured result
  (``requested_items=['O-1010']``, target ``Orders!R11``);
* the model's prose cited ``Orders!R11`` correctly;
* the evidence validator was handed ``workbook_read`` — the read ARTIFACT
  (sheets/headers/coverage, no targets) — so the citation was rejected
  (``supported_sheets=[]``);
* the fallback rendered the artifact as "No items were resolved…", which
  then failed the structured review.

These tests pin the selection rule at the shared boundary and the citation
outcome with each record shape.
"""
import os

os.environ.setdefault("TESTING", "1")

from core.answer_presentation import validate_rendered_against_record
import integrations.chat_orchestrator as chat


ARTIFACT = {
    "file_name": "orders.xlsx",
    "content_hash": "410d51493a517d78dab8885819e934cf25c2a2b5",
    "target_extraction_version": 3,
    "coverage": {"complete": True, "read_status": "ok"},
    "sheets": [{
        "name": "Orders",
        "headers": {"1": "Order ID", "2": "Status", "3": "Qty"},
        "searched": True,
    }],
}

STRUCTURED = {
    "schema_version": "structured-result-2",
    "attempt_id": "attempt-1",
    "evidence_action": "new_read",
    "evidence_revision": "rev-1",
    "source_identity": {
        "file_name": "orders.xlsx",
        "service": "datasets",
        "resource_id": "sha1:410d",
        "content_hash": "410d51493a517d78dab8885819e934cf25c2a2b5",
        "live_vs_saved": "saved copy",
    },
    "requested_items": ["O-1010"],
    "requested_fields": ["order_id", "status", "quantity"],
    "targets": [{
        "item": "O-1010",
        "aliases": [],
        "identity": {
            "status": "single",
            "candidates": [{
                "ref": "Orders!R11",
                "values": [
                    {"col": "A11", "basis": "Order ID",
                     "value": "O-1010", "display": "O-1010"},
                    {"col": "B11", "basis": "Status",
                     "value": "Approved", "display": "Approved"},
                    {"col": "C11", "basis": "Qty",
                     "value": 7, "display": "7"},
                ],
            }],
        },
    }],
}

NARRATION = "O-1010 is Approved for 7 units (row Orders!R11)."


def test_structured_result_is_the_presentation_record_when_both_exist():
    meta = {"structured_result": STRUCTURED, "workbook_read": ARTIFACT}
    assert chat._presentation_record_from_meta(meta) is STRUCTURED


def test_the_read_artifact_alone_is_not_presentation_evidence():
    assert chat._presentation_record_from_meta(
        {"workbook_read": ARTIFACT}) is None


def test_a_legacy_presentation_shaped_workbook_read_is_still_accepted():
    legacy = {
        "requested_items": ["O-1010"],
        "targets": [{"item": "O-1010"}],
    }
    assert chat._presentation_record_from_meta(
        {"workbook_read": legacy}) is legacy


def test_row_citation_validates_only_against_the_presentation_record():
    rejected = validate_rendered_against_record(NARRATION, ARTIFACT)
    assert rejected["ok"] is False
    assert any(
        violation["check"] == "citations_grounded"
        for violation in rejected["violations"])

    selected = chat._presentation_record_from_meta(
        {"structured_result": STRUCTURED, "workbook_read": ARTIFACT})
    accepted = validate_rendered_against_record(NARRATION, selected)
    assert accepted["ok"] is True
    assert accepted["checks"]["citations_grounded"] is True
