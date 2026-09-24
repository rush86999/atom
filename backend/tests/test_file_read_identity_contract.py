from __future__ import annotations

import io
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from integrations.universal_integration_service import UniversalIntegrationService


def _bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Model", "Price"])
    sheet.append(["U-22", 100])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class _Storage:
    def __init__(self, records, content=None, metadata=None):
        self.records = records
        self.content = content or _bytes()
        self.metadata = metadata
        self.downloads = 0
        self.metadata_calls = 0

    async def search_files(self, user_id, query, limit=20):
        return self.records

    async def get_file_metadata(self, user_id, file_id):
        self.metadata_calls += 1
        return self.metadata

    async def download_file(self, user_id, file_id):
        self.downloads += 1
        return self.content


@pytest.mark.asyncio
async def test_unique_exact_resource_is_verified_and_read_has_coverage():
    record = {
        "id": "file-1",
        "name": "Consolidated Price List 2019.xlsx",
        "type": "file",
        "team_id": "team-1",
        "folder_id": "folder-1",
        "modified_at": "2026-01-01T00:00:00Z",
        "extension": "xlsx",
    }
    storage = _Storage([record], metadata=record)
    service = UniversalIntegrationService(workspace_id="default")
    with patch("core.auto_document_ingestion.AutoDocumentIngestionService") as ingest:
        ingest.return_value.process_file_bytes = AsyncMock(return_value={"status": "skipped"})
        result = await service._read_storage_file(
            "zoho_workdrive",
            storage,
            None,
            {"query": "Consolidated Price List 2019.xlsx prices for U-22"},
            {"user_id": "u1", "requested_targets": ["U-22"]},
        )
    data = result["data"]
    assert data["found"] is True
    assert data["identity_verified"] is True
    assert data["resource_id"] == "file-1"
    assert data["coverage_complete"] is True
    assert data["workbook_read"]["coverage"]["outcomes"][0]["target"] == "U-22"
    assert storage.metadata_calls == 1
    assert storage.downloads == 1


@pytest.mark.asyncio
async def test_duplicate_exact_names_are_ambiguous_and_not_downloaded():
    records = [
        {
            "id": "file-1",
            "name": "Consolidated Price List 2019.xlsx",
            "type": "file",
            "team_id": "team-1",
            "folder_id": "folder-1",
            "modified_at": "2026-01-01",
        },
        {
            "id": "file-2",
            "name": "Consolidated Price List 2019.xlsx",
            "type": "file",
            "team_id": "team-2",
            "folder_id": "folder-2",
            "modified_at": "2026-01-02",
        },
    ]
    storage = _Storage(records)
    service = UniversalIntegrationService(workspace_id="default")
    result = await service._read_storage_file(
        "zoho_workdrive",
        storage,
        None,
        {"query": "Consolidated Price List 2019.xlsx prices"},
        {"user_id": "u1"},
    )
    assert result["data"]["found"] is False
    assert result["data"]["ambiguous"] is True
    assert len(result["data"]["candidates"]) == 2
    assert storage.downloads == 0


@pytest.mark.asyncio
async def test_candidate_without_exact_identity_is_not_read():
    record = {
        "id": "file-1",
        "name": "Consolidated Price List 2019.xlsx",
        "type": "file",
        "team_id": "team-1",
        "folder_id": "folder-1",
        "modified_at": "2026-01-01",
    }
    storage = _Storage([record], metadata=record)
    service = UniversalIntegrationService(workspace_id="default")
    result = await service._read_storage_file(
        "zoho_workdrive",
        storage,
        None,
        {"query": "price list 2019"},
        {"user_id": "u1"},
    )
    assert result["data"]["found"] is False
    assert result["data"]["identity_verified"] is False
    assert storage.downloads == 0


@pytest.mark.asyncio
async def test_confirmed_unique_candidate_can_be_bound_after_clarification():
    record = {
        "id": "file-1",
        "name": "Consolidated Price List 2019.xlsx",
        "type": "file",
        "team_id": "team-1",
        "folder_id": "folder-1",
        "modified_at": "2026-01-01",
    }
    storage = _Storage([record], metadata=record)
    service = UniversalIntegrationService(workspace_id="default")
    result = await service._read_storage_file(
        "zoho_workdrive",
        storage,
        None,
        {"query": "price list 2019"},
        {
            "user_id": "u1",
            "file_identity_confirmed": True,
            "requested_targets": ["U-22"],
        },
    )
    assert result["data"]["found"] is True
    assert result["data"]["identity_verified"] is True
    assert storage.downloads == 1


@pytest.mark.asyncio
async def test_metadata_name_mismatch_fails_closed():
    search_record = {
        "id": "file-1",
        "name": "Consolidated Price List 2019.xlsx",
        "type": "file",
        "team_id": "team-1",
        "folder_id": "folder-1",
        "modified_at": "2026-01-01",
    }
    metadata = {**search_record, "name": "Other Workbook.xlsx"}
    storage = _Storage([search_record], metadata=metadata)
    service = UniversalIntegrationService(workspace_id="default")
    result = await service._read_storage_file(
        "zoho_workdrive",
        storage,
        None,
        {"query": "Consolidated Price List 2019.xlsx"},
        {"user_id": "u1"},
    )
    assert result["data"]["found"] is False
    assert result["data"]["identity_verified"] is False
    assert storage.downloads == 0
