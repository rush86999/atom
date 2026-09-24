from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from openpyxl import Workbook

from core.workbook_read_artifact import (
    extract_targets,
    inspect_workbook_bytes,
    render_workbook_artifact,
)


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    first = workbook.active
    first.title = "Machine A"
    first.append(["Model", "Factory Price", "Dealer Price"])
    first.append(["U-22", 100, 125])
    first.append(["GSL48-16", "=B2*1.1", "=C2*1.1"])
    second = workbook.create_sheet("Machine B")
    second.append(["Model", "List Price"])
    second.append(["SLE24-16", 200])
    third = workbook.create_sheet("Notes")
    third.append(["This sheet has no requested model"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_extract_targets_keeps_model_codes_whole():
    values = extract_targets(
        "find prices for U-22, GSL48-16, SLE24-16, 381 and 622 in 2019"
    )
    assert values == ["U-22", "GSL48-16", "SLE24-16", "381", "622"]


def test_artifact_has_one_outcome_per_target_and_cell_provenance():
    artifact = inspect_workbook_bytes(
        _workbook_bytes(),
        "Consolidated Price List 2019.xlsx",
        query="prices for U-22, GSL48-16, SLE24-16, 381 and 622",
        provider="zoho_workdrive",
        resource_id="file-1",
        source_metadata={"team_id": "team-1", "modified_at": "2026-01-01"},
    )
    assert artifact["resource_id"] == "file-1"
    assert artifact["all_sheets_searched"] is True
    assert artifact["sheet_count"] == 3
    outcomes = artifact["coverage"]["outcomes"]
    assert [item["target"] for item in outcomes] == [
        "U-22", "GSL48-16", "SLE24-16", "381", "622"
    ]
    assert [item["status"] for item in outcomes] == [
        "found", "found", "found", "absent", "absent"
    ]
    first = outcomes[0]["evidence"][0]
    assert first["sheet"] == "Machine A"
    assert first["cell"] == "A2"
    assert first["prices"][0]["cell"] == "B2"
    assert first["prices"][0]["price_basis"] == "Factory Price"
    assert artifact["coverage"]["complete"] is True
    assert artifact["sha256"]
    rendered = render_workbook_artifact(artifact)
    assert "Machine A!A2" in rendered
    assert "TARGET 381: ABSENT" in rendered


def test_duplicate_matches_are_ambiguous():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Model", "Price"])
    sheet.append(["U-22", 1])
    second = workbook.create_sheet("Other")
    second.append(["Model", "Price"])
    second.append(["U-22", 2])
    buffer = io.BytesIO()
    workbook.save(buffer)
    artifact = inspect_workbook_bytes(
        buffer.getvalue(), "prices.xlsx", query="price for U-22"
    )
    outcome = artifact["coverage"]["outcomes"][0]
    assert outcome["status"] == "ambiguous"
    assert len(outcome["evidence"]) == 2
