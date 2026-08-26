"""Tests for the Zoho WorkDrive ingest path: old-format .xls parsing and
honest success reporting (skipped/errored files must not be reported as
ingested)."""
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

from core.auto_document_ingestion import DocumentParser
from integrations.zoho_workdrive_service import ZohoWorkDriveService

OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class _FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data if data is not None else {}
        self.content = b""

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSheet:
    name = "Sheet1"
    nrows = 2
    ncols = 2

    def cell_value(self, r, c):
        return [["Item", "Price"], ["Widget", "12.50"]][r][c]


class _FakeWB:
    def sheets(self):
        return [_FakeSheet()]


class _FakeXlrd:
    def open_workbook(self, file_contents=None):
        return _FakeWB()


async def test_parse_excel_reads_old_xls_with_xlrd():
    fake = _FakeXlrd()
    mod = types.ModuleType("xlrd")
    mod.open_workbook = fake.open_workbook
    sys.modules["xlrd"] = mod
    try:
        text = await DocumentParser._parse_excel(OLE2_MAGIC + b"\x00" * 64)
    finally:
        sys.modules.pop("xlrd", None)
    assert "Sheet1" in text
    assert "Widget" in text
    assert "12.50" in text


async def test_ingest_reports_skipped_as_failure_not_success():
    svc = ZohoWorkDriveService(
        tenant_id="default",
        config={"client_id": "cid", "client_secret": "cs", "redirect_uri": "uri"},
    )
    svc.get_access_token = AsyncMock(return_value="tok")
    svc.download_file = AsyncMock(return_value=b"some bytes")
    svc.client = MagicMock()
    svc.client.get = AsyncMock(
        return_value=_FakeResponse(200, {"data": {"attributes": {"name": "old.xls"}}})
    )

    with patch(
        "core.auto_document_ingestion.AutoDocumentIngestionService"
    ) as cls:
        ingestor = cls.return_value
        ingestor.process_file_bytes = AsyncMock(
            return_value={"status": "skipped", "reason": "no_text", "file_name": "old.xls"}
        )
        result = await svc.ingest_file_to_memory("u1", "f1")

    assert result["success"] is False
    assert "no_text" in result["error"]
    ingestor.process_file_bytes.assert_awaited_once()


async def test_ingest_reports_success_only_when_actually_ingested():
    svc = ZohoWorkDriveService(
        tenant_id="default",
        config={"client_id": "cid", "client_secret": "cs", "redirect_uri": "uri"},
    )
    svc.get_access_token = AsyncMock(return_value="tok")
    svc.download_file = AsyncMock(return_value=b"# fly.toml\n")
    svc.client = MagicMock()
    svc.client.get = AsyncMock(
        return_value=_FakeResponse(200, {"data": {"attributes": {"name": "fly.toml"}}})
    )

    with patch(
        "core.auto_document_ingestion.AutoDocumentIngestionService"
    ) as cls:
        ingestor = cls.return_value
        ingestor.process_file_bytes = AsyncMock(
            return_value={"status": "ingested", "file_name": "fly.toml", "chars_ingested": 12}
        )
        result = await svc.ingest_file_to_memory("u1", "f1")

    assert result["success"] is True
    assert result["result"]["status"] == "ingested"
