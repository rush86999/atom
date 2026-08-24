"""Round 83 — severed journey-link repair: storage ingestion journeys.

The OneDrive/GDrive integration panels call /api/onedrive/*, /api/gdrive/*
and /api/ingest-gdrive-document — paths no real router served. These tests
verify the journey routers bind the REAL services to those paths, and that
every storage provider now has an HTTP full-sync trigger (Zoho WorkDrive,
Box, Dropbox included).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "journey-user-1"
    u.email = "journey@x.com"
    return u


@pytest.fixture
def client(user):
    from integrations.gdrive_journey_routes import (
        ingest_router as g_ingest,
        router as g_router,
    )
    from integrations.onedrive_journey_routes import (
        auth_router as o_auth,
        router as o_router,
    )

    app = FastAPI()
    app.include_router(o_router)
    app.include_router(o_auth)
    app.include_router(g_router)
    app.include_router(g_ingest)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OneDrive journey
# ---------------------------------------------------------------------------

class TestOneDriveJourney:
    def test_connection_status_disconnected(self, client):
        with patch("integrations.onedrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value=None)):
            r = client.get("/api/onedrive/connection-status")
        assert r.status_code == 200
        body = r.json()
        assert body["is_connected"] is False
        assert body["reason"]

    def test_connection_status_connected(self, client):
        with patch("integrations.onedrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")):
            r = client.get("/api/onedrive/connection-status")
        assert r.json()["is_connected"] is True

    def test_list_files_normalizes_graph_items(self, client):
        graph_data = {
            "value": [{
                "id": "i1", "name": "Report.docx", "webUrl": "https://1drv.ms/i1",
                "file": {"mimeType": "application/vnd..."},
                "fileSystemInfo": {"lastModifiedDateTime": "2026-01-02T03:04:05Z"},
            }],
            "nextLink": "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=abc&$top=200",
        }
        with patch("integrations.onedrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")), \
                patch("integrations.onedrive_journey_routes._service.list_files",
                      new=AsyncMock(return_value={"status": "success", "data": graph_data})):
            r = client.get("/api/onedrive/list-files")
        body = r.json()
        assert body["files"][0]["id"] == "i1"
        assert body["files"][0]["mime_type"] == "application/vnd..."
        assert body["files"][0]["modified_time"] == "2026-01-02T03:04:05Z"
        assert body["next_page_token"] == "abc"

    def test_list_files_not_connected(self, client):
        with patch("integrations.onedrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value=None)):
            r = client.get("/api/onedrive/list-files")
        assert r.json()["error"] == "not_connected"

    def test_ingest_document(self, client):
        with patch("integrations.onedrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")), \
                patch("integrations.onedrive_journey_routes._service.ingest_file_to_memory",
                      new=AsyncMock(return_value={"success": True, "result": {"status": "ingested"}})) as mock_ing:
            r = client.post("/api/onedrive/ingest-document",
                            json={"file_id": "i1", "metadata": {"name": "a.docx"}})
        assert r.json()["success"] is True
        assert mock_ing.call_args.args[1] == "i1"

    def test_full_sync_triggers_service(self, client):
        with patch("integrations.onedrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")), \
                patch("integrations.onedrive_journey_routes._service.full_sync",
                      new=AsyncMock(return_value={"success": True, "files_ingested": 3})) as mock_sync:
            r = client.post("/api/onedrive/sync")
        assert r.json()["success"] is True
        assert mock_sync.call_args.args == ("journey-user-1", "tok")

    def test_authorize_redirects_to_unified_flow(self, client):
        r = client.get("/api/auth/onedrive/authorize", follow_redirects=False)
        assert r.status_code in (302, 307)
        assert "/api/v1/auth/oauth/microsoft/authorize" in r.headers["location"]

    def test_disconnect_removes_connections(self, client):
        from core import connection_service as cs

        # One connection under "onedrive", one under the shared "microsoft365".
        conns = {"onedrive": [{"id": "c1"}], "microsoft365": [{"id": "c2"}]}
        with patch.object(cs.connection_service, "get_connections",
                          side_effect=lambda uid, iid: conns.get(iid, [])), \
                patch.object(cs.connection_service, "delete_connection",
                          side_effect=lambda cid, uid: True) as mock_del:
            r = client.post("/api/auth/onedrive/disconnect")
        assert r.json() == {"success": True, "removed_connections": 2}
        assert mock_del.call_count == 2


# ---------------------------------------------------------------------------
# Google Drive journey
# ---------------------------------------------------------------------------

class TestGDriveJourney:
    def test_connection_status(self, client):
        with patch("integrations.gdrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")):
            r = client.get("/api/gdrive/connection-status")
        assert r.json()["isConnected"] is True

    def test_list_files_normalizes_drive_resources(self, client):
        drive_data = {
            "files": [{
                "id": "g1", "name": "Sheet1", "mimeType": "application/vnd.google-apps.spreadsheet",
                "webViewLink": "https://drive.google.com/g1", "modifiedTime": "2026-02-03",
            }],
            "nextPageToken": "ptok",
        }
        with patch("integrations.gdrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")), \
                patch("integrations.gdrive_journey_routes._service.list_files",
                      new=AsyncMock(return_value={"status": "success", "data": drive_data})):
            r = client.get("/api/gdrive/list-files")
        body = r.json()
        assert body["files"][0]["mimeType"] == "application/vnd.google-apps.spreadsheet"
        assert body["nextPageToken"] == "ptok"

    def test_ingest_gdrive_document_bare_path(self, client):
        with patch("integrations.gdrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")), \
                patch("integrations.gdrive_journey_routes._service.ingest_file_to_memory",
                      new=AsyncMock(return_value={"success": True, "result": {"status": "ingested"}})) as mock_ing:
            r = client.post("/api/ingest-gdrive-document",
                            json={"file_id": "g1", "metadata": {"name": "Sheet1"}})
        assert r.json()["success"] is True
        assert mock_ing.call_args.args[1] == "g1"

    def test_full_sync_triggers_service(self, client):
        with patch("integrations.gdrive_journey_routes._service.get_access_token",
                   new=AsyncMock(return_value="tok")), \
                patch("integrations.gdrive_journey_routes._service.full_sync",
                      new=AsyncMock(return_value={"success": True, "files_ingested": 5})) as mock_sync:
            r = client.post("/api/gdrive/sync")
        assert r.json()["success"] is True
        assert mock_sync.call_args.args == ("journey-user-1", "tok")


# ---------------------------------------------------------------------------
# Other providers expose full-sync triggers on their own routers
# ---------------------------------------------------------------------------

class TestProviderSyncRoutes:
    def test_zoho_workdrive_full_sync_route_exists(self):
        from api.zoho_workdrive_routes import router

        paths = {r.path for r in router.routes}
        assert "/api/zoho-workdrive/full-sync" in paths

    def test_box_sync_route_exists(self):
        from integrations.box_routes import router

        paths = {r.path for r in router.routes}
        assert "/api/box/sync" in paths

    def test_dropbox_sync_route_exists(self):
        from integrations.dropbox_routes import router

        paths = {r.path for r in router.routes}
        assert "/api/dropbox/files/sync" in paths
