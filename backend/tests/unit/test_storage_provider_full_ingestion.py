"""Recursive, paginated, all-file-type ingestion for storage providers.

OneDrive, Google Drive, and Dropbox must all: walk every subfolder, follow
API pagination to exhaustion, attempt every file type through the parser
chain (no extension allowlist), and stamp folder-path context into the
memory metadata so agents can recall where a document came from.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# OneDrive
# ---------------------------------------------------------------------------

class TestOneDriveFullIngestion:
    @pytest.mark.asyncio
    async def test_walk_files_recurses_and_follows_nextlink(self):
        from integrations.onedrive_service import OneDriveService

        svc = OneDriveService("user1", {})
        # Page 1 of root: a folder + a file, with a nextLink pointing to page 2.
        pages = {
            "https://graph.microsoft.com/v1.0/me/drive/root/children?$top=200": {
                "value": [
                    {"id": "d1", "name": "Projects", "folder": {"childCount": 1}},
                    {"id": "f1", "name": "notes.md"},
                ],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=2",
            },
            "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=2": {
                "value": [{"id": "f2", "name": "top-level.pdf"}],
            },
            "https://graph.microsoft.com/v1.0/me/drive/items/d1/children?$top=200": {
                "value": [{"id": "f3", "name": "spec.docx"}],
            },
        }
        with patch.object(svc, "_graph_get", AsyncMock(side_effect=lambda tok, url: pages[url])):
            walked = await svc.walk_files("tok")

        by_id = {f["id"]: f for f in walked}
        # All three files (both root pages + nested) are captured.
        assert set(by_id) == {"f1", "f2", "f3"}
        assert by_id["f3"]["path"] == "/Projects"
        assert by_id["f1"]["path"] == ""

    @pytest.mark.asyncio
    async def test_full_sync_attempts_every_file_type_with_path_metadata(self):
        from integrations.onedrive_service import OneDriveService

        svc = OneDriveService("user1", {})
        files = [
            {"id": "f1", "name": "report.docx", "path": "/Reports", "lastModifiedDateTime": "2026-01-01"},
            {"id": "f2", "name": "diagram.png", "path": "/Reports/Sub", "lastModifiedDateTime": "2026-01-02"},
        ]
        with patch.object(svc, "walk_files", AsyncMock(return_value=files)), \
             patch.object(svc, "ingest_file_to_memory", AsyncMock(
                 return_value={"success": True, "result": {"status": "ingested"}})) as mock_ingest, \
             patch.object(svc, "sync_to_postgres_cache", AsyncMock(
                 return_value={"success": True, "metrics_synced": 2})):
            result = await svc.full_sync("user1", "tok")

        assert result["files_found"] == 2
        assert result["files_ingested"] == 2
        assert mock_ingest.call_count == 2  # png attempted too — no allowlist
        kwargs = mock_ingest.call_args_list[1].kwargs
        assert kwargs["extra_metadata"]["folder_path"] == "/Reports/Sub"


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

class TestGoogleDriveFullIngestion:
    @pytest.mark.asyncio
    async def test_walk_files_recurses_and_follows_pagetoken(self):
        from integrations.google_drive_service import DRIVE_API_BASE, GoogleDriveService

        svc = GoogleDriveService("user1", {})
        FOLDER = "application/vnd.google-apps.folder"

        async def fake_get(tok, url, params=None):
            assert url == f"{DRIVE_API_BASE}/files"
            q = params["q"]
            if "skiptoken" in (params.get("pageToken") or ""):
                return {"files": [{"id": "f2", "name": "sheet2.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}]}
            if "'root' in parents" in q:
                return {
                    "files": [
                        {"id": "d1", "name": "Team", "mimeType": FOLDER},
                        {"id": "f1", "name": "doc1.gdoc-name", "mimeType": "application/vnd.google-apps.document"},
                    ],
                    "nextPageToken": "skiptoken1",
                }
            if "'d1' in parents" in q:
                return {"files": [{"id": "f3", "name": "deck.pdf", "mimeType": "application/pdf"}]}
            raise AssertionError(f"unexpected query: {q}")

        with patch.object(svc, "_drive_get", AsyncMock(side_effect=fake_get)):
            walked = await svc.walk_files("tok")

        by_id = {f["id"]: f for f in walked}
        assert set(by_id) == {"f1", "f2", "f3"}
        assert by_id["f3"]["path"] == "/Team"

    @pytest.mark.asyncio
    async def test_ingest_appends_export_extension_for_gdocs(self):
        from integrations.google_drive_service import GoogleDriveService

        svc = GoogleDriveService("user1", {})
        with patch.object(svc, "download_file_bytes", AsyncMock(return_value=b"PK docx bytes")), \
             patch.object(svc, "get_file_metadata", AsyncMock(return_value={
                 "status": "success",
                 "data": {"name": "Strategy Doc", "mimeType": "application/vnd.google-apps.document"},
             })), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
                   AsyncMock(return_value={"status": "ingested", "chars_ingested": 10})) as mock_pfb:
            res = await svc.ingest_file_to_memory("tok", "f1")

        assert res["success"] is True
        # Name gains .docx so the parser dispatches on the exported Office bytes.
        assert mock_pfb.call_args.kwargs["file_name"] == "Strategy Doc.docx"
        assert mock_pfb.call_args.kwargs["source"] == "google_drive"


# ---------------------------------------------------------------------------
# Dropbox
# ---------------------------------------------------------------------------

class _FakeListResult:
    def __init__(self, entries, has_more=False, cursor=None):
        self.entries = entries
        self.has_more = has_more
        self.cursor = cursor


class TestDropboxFullIngestion:
    @pytest.mark.asyncio
    async def test_list_folder_follows_cursor_pagination(self):
        from integrations.dropbox_service import DropboxService

        svc = DropboxService("user1", {})
        dbx = MagicMock()
        dbx.files_list_folder.return_value = _FakeListResult(
            [SimpleNamespace(id="f1", name="a.txt", path_display="/a.txt", path_lower="/a.txt")],
            has_more=True, cursor="c1",
        )
        dbx.files_list_folder_continue.return_value = _FakeListResult(
            [SimpleNamespace(id="f2", name="b.txt", path_display="/b.txt", path_lower="/b.txt")],
        )
        with patch.object(svc, "_get_dropbox_client", return_value=dbx):
            entries = await svc.list_folder(access_token="tok")

        assert [e["id"] for e in entries] == ["f1", "f2"]
        dbx.files_list_folder_continue.assert_called_once_with("c1")

    @pytest.mark.asyncio
    async def test_walk_files_uses_recursive_listing_and_stamps_paths(self):
        from integrations.dropbox_service import DropboxService

        svc = DropboxService("user1", {})
        class FolderMetadata(SimpleNamespace):
            pass

        folder = FolderMetadata(id="d1", name="Reports", path_display="/Reports", path_lower="/reports")
        file_root = SimpleNamespace(id="f1", name="root.txt", path_display="/root.txt", path_lower="/root.txt")
        file_nested = SimpleNamespace(id="f2", name="q4.xlsx", path_display="/Reports/q4.xlsx", path_lower="/reports/q4.xlsx")
        dbx = MagicMock()
        dbx.files_list_folder.return_value = _FakeListResult([folder, file_root, file_nested])
        with patch.object(svc, "_get_dropbox_client", return_value=dbx):
            walked = await svc.walk_files(access_token="tok")

        by_id = {f["id"]: f for f in walked}
        assert set(by_id) == {"f1", "f2"}  # folders excluded, files kept
        assert by_id["f2"]["folder_path"] == "/Reports"
        assert by_id["f1"]["folder_path"] == ""
