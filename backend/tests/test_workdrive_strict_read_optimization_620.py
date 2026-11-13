# -*- coding: utf-8 -*-
"""Focused regression tests for the issue-620 strict WorkDrive read path.

The strict read must use the structured workbook artifact parsed from the
DOWNLOADED bytes as its evidence. Generic extraction (``parse_document_cached``)
and the awaited generic ingest are redundant second parses of the same payload
and measured 19.93s against the read's 25s limit, so they are skipped only on
that opt-in strict path. Ordinary reads keep their existing behavior.

Everything here is synthetic: no network, credentials, live WorkDrive
workbook, or database reads.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import openpyxl
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.workdrive_direct_proof import proof_from_storage_read_result
from integrations.universal_integration_service import UniversalIntegrationService

RID = "u-strict-620"
FILE_NAME = "Synthetic Price List 2026.xlsx"
EXECUTION_ID = "exec-620-strict"


def _workbook_bytes(price: float = 4321.0) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "LINMAC"
    sheet.append(["Model", "Description", "List Price"])
    sheet.append(["U-22", "Rotary machine", price])
    sheet.append(["622", "Press brake", 5000])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class _FakeWorkDrive:
    """The only storage calls ``_read_storage_file`` makes on this path."""

    access_token = None

    def __init__(self, content: bytes):
        self.content = content
        self.downloads = 0
        self.downloaded_ids: list[str] = []

    async def get_file_metadata(self, user_id, file_id):
        return {
            "id": file_id,
            "name": FILE_NAME,
            "version": "v620",
            "modified_time": "2026-11-12T00:00:00Z",
            "team_id": "team-620",
            "folder_id": "folder-620",
            "size": len(self.content),
        }

    async def download_file(self, user_id, file_id, workspace_id=None):
        self.downloads += 1
        self.downloaded_ids.append(str(file_id))
        return self.content


def _read_strict(storage: _FakeWorkDrive, *, strict: bool):
    service = UniversalIntegrationService(workspace_id="ws-620")
    context = {
        "user_id": "u1",
        "workspace_id": "ws-620",
        "execution_id": EXECUTION_ID,
        "requested_targets": ["U-22", "622"],
    }
    if strict:
        context["strict_workdrive_proof"] = True
    return asyncio.run(service._read_storage_file(
        "zoho_workdrive",
        storage,
        None,
        {
            "file_id": RID,
            "file_name": FILE_NAME,
            "query": "price of U-22 and 622",
            "identity_verified": True,
        },
        context,
    ))


@pytest.fixture()
def patched_extraction_and_ingest():
    """Spy on the two redundant parses without touching anything real."""
    import core.workbook_read_artifact as workbook_artifact

    extraction_calls: list[tuple] = []
    ingest_calls: list[tuple] = []
    inspection_calls: list[tuple] = []
    real_inspect = workbook_artifact.inspect_workbook_bytes

    async def fake_parse(content, ext, name, max_chars=None):
        extraction_calls.append((len(content), ext, name, max_chars))
        return "GENERIC EXTRACTION TEXT — must not be used on the strict path"

    def spy_inspect(content, file_name, **kwargs):
        inspection_calls.append((len(content), file_name))
        return real_inspect(content, file_name, **kwargs)

    class _FakeIngest:
        async def process_file_bytes(self, content, **kwargs):
            ingest_calls.append((len(content), kwargs))
            return {"status": "ingested"}

    with patch(
        "core.auto_document_ingestion.parse_document_cached",
        new=fake_parse,
    ), patch(
        "core.auto_document_ingestion.AutoDocumentIngestionService",
        new=_FakeIngest,
    ), patch(
        "core.workbook_read_artifact.inspect_workbook_bytes",
        new=spy_inspect,
    ), patch(
        "core.sheet_dataset_service.ensure_sheet_dataset_background",
        new=MagicMock(),
    ), patch(
        "core.sheet_dataset_service.datasets_for_file",
        new=AsyncMock(return_value=[]),
    ):
        yield extraction_calls, ingest_calls, inspection_calls


def test_strict_read_skips_redundant_extraction_and_ingest(
    patched_extraction_and_ingest,
):
    extraction_calls, ingest_calls, inspection_calls = (
        patched_extraction_and_ingest)
    content = _workbook_bytes()
    storage = _FakeWorkDrive(content)

    result = _read_strict(storage, strict=True)

    assert result["status"] == "success"
    data = result["data"]

    # Exact downloaded bytes, hash, and resource binding are preserved.
    assert storage.downloads == 1
    assert storage.downloaded_ids == [RID]
    assert data["found"] is True
    assert data["served"] is True
    assert data["read_completed"] is True
    assert data["content_sha256"] == hashlib.sha256(content).hexdigest()
    assert data["content_sha1"] == hashlib.sha1(content).hexdigest()

    artifact = data["workbook_read"]
    assert artifact["sha256"] == data["content_sha256"]
    assert artifact["byte_length"] == len(content)
    assert artifact["all_sheets_searched"] is True
    assert artifact["resource_id"] == RID

    receipt = data["strict_read_receipt"]
    assert receipt["schema"] == "workdrive-direct-receipt-1"
    assert receipt["sha256"] == data["content_sha256"]
    assert receipt["sha1"] == data["content_sha1"]
    assert receipt["bytes"] == len(content)
    assert receipt["resource_id"] == RID
    assert receipt["execution_id"] == EXECUTION_ID
    assert receipt["evidence_kind"] == "downloaded_bytes"
    assert receipt["materialized"] is False

    # The receipt is accepted by the strict proof verifier.
    proof = proof_from_storage_read_result(
        data, execution_id=EXECUTION_ID, expected_resource_id=RID)
    assert proof["status"] == "verified"
    assert proof["downloaded_sha256"] == data["content_sha256"]

    # THE OPTIMIZATION: one structured inspection, and neither redundant
    # second parse ran on the strict path.
    assert len(inspection_calls) == 1
    assert extraction_calls == []
    assert ingest_calls == []

    # The structured artifact is the excerpt evidence, and the note is honest
    # about the skipped ingest.
    assert "U-22" in data["excerpt"]
    assert "4,321" in data["excerpt"] or "4321" in data["excerpt"]
    assert "GENERIC EXTRACTION TEXT" not in data["excerpt"]
    assert data["ingested_into_workspace"] is False
    assert "skipped on the strict path" in data["note"]


def test_ordinary_read_still_runs_extraction_and_ingest(
    patched_extraction_and_ingest,
):
    extraction_calls, ingest_calls, inspection_calls = (
        patched_extraction_and_ingest)
    content = _workbook_bytes()
    storage = _FakeWorkDrive(content)

    result = _read_strict(storage, strict=False)

    assert result["status"] == "success"
    data = result["data"]
    assert data["found"] is True
    assert data["served"] is True
    assert "strict_read_receipt" not in data
    assert storage.downloads == 1

    # Ordinary reads keep the existing behavior: both parses run, and the
    # structured inspection still happens exactly once.
    assert len(extraction_calls) == 1
    assert len(ingest_calls) == 1
    assert len(inspection_calls) == 1
    assert data["ingested_into_workspace"] is True


def test_strict_path_fails_closed_when_artifact_cannot_be_read(
    patched_extraction_and_ingest,
):
    extraction_calls, ingest_calls, inspection_calls = (
        patched_extraction_and_ingest)
    storage = _FakeWorkDrive(b"not a workbook")

    result = _read_strict(storage, strict=True)

    assert result["status"] == "success"
    data = result["data"]
    assert storage.downloads == 1
    assert data["found"] is True
    assert data["served"] is False
    assert data["read_completed"] is False
    assert data["coverage_complete"] is False
    assert data["evidence_kind"] == "direct_download_unavailable"
    assert data["strict_read_receipt"] is None
    assert data["strict_proof_error"]
    assert data["content_sha256"] == hashlib.sha256(b"not a workbook").hexdigest()

    # Fail-closed does not fall back to a second parse or to ingestion.
    assert len(inspection_calls) == 1
    assert extraction_calls == []
    assert ingest_calls == []
