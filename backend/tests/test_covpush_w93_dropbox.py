"""Coverage wave 93 — integrations/dropbox_routes.py (TDD, 0% baseline).

The dropbox SDK is NOT installed in this venv, so a minimal fake `dropbox`
package is installed into sys.modules BEFORE importing the module (the
module imports `import dropbox` at top level). All HTTP/OAuth deps are
mocked; no network.

BUG FOUND + FIXED (wave 93, TDD RED->GREEN): integrations/dropbox_service.py
was a stub — it only had __init__/get_capabilities/execute_operation/
health_check, but dropbox_routes.py calls 12 service methods that did NOT
exist (list_folder, upload_file, download_file, search, create_folder,
delete_item, move_item, copy_item, create_shared_link, get_account_info,
get_space_usage, get_metadata). Every file/folder/item endpoint therefore
crashed with AttributeError -> 500 "Internal error" — the routes were dead.
The methods were implemented on the service (dropbox SDK, matching the
existing execute_operation style); the happy-path tests below exercise the
REAL service through the fake SDK and were RED (500) before the fix.

Also fixed: /user, /user/info, /space/usage, /file_metadata returned
connected Dropbox account data with NO authentication (anonymous data
exposure). get_current_user is now required on all four.
"""
import base64
import sys
import types
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import User


# ── Fake dropbox SDK (the real package is not installed) ────────────────────
class _Metadata:
    def __init__(self, name="f.txt", path_display="/f.txt"):
        self.id = "id-1"
        self.name = name
        self.path_display = path_display
        self.path_lower = path_display.lower()
        self.size = 10
        self.rev = "r1"
        self.is_downloadable = True
        self.content_hash = "h"
        self.client_modified = None
        self.server_modified = None
        self.media_info = None
        self.shared_folder_id = None
        self.sharing_info = None

    def to_dict(self):
        return {"name": self.name, "path": self.path_display}


class FileMetadata(_Metadata):
    pass


class FolderMetadata(_Metadata):
    def __init__(self, **kw):
        super().__init__(name="folder", path_display="/folder", **kw)


def _make_client():
    c = MagicMock()
    c.files_list_folder.return_value = SimpleNamespace(
        entries=[FileMetadata(), FolderMetadata()], cursor="c1", has_more=False)
    c.files_upload.return_value = FileMetadata(name="up.txt",
                                               path_display="/up.txt")
    c.files_download.return_value = (
        FileMetadata(), SimpleNamespace(content=b"dropbox-file-bytes"))
    c.files_search_v2.return_value = SimpleNamespace(
        matches=[SimpleNamespace(metadata=FileMetadata())],
        has_more=False, start=0)
    c.files_create_folder_v2.return_value = SimpleNamespace(
        metadata=FolderMetadata())
    c.files_delete_v2.return_value = SimpleNamespace(
        metadata=FileMetadata())
    c.files_move_v2.return_value = SimpleNamespace(
        metadata=FileMetadata())
    c.files_copy_v2.return_value = SimpleNamespace(
        metadata=FileMetadata())
    c.sharing_create_shared_link_with_settings.return_value = SimpleNamespace(
        url="https://db.tt/abc", name="f.txt", path_lower="/f.txt",
        link_permissions=SimpleNamespace(to_dict=lambda: {}),
        preview_type="direct", client_modified=None, server_modified=None)
    c.users_get_current_account.return_value = SimpleNamespace(
        account_id="acct-1", email="a@b.c",
        name=SimpleNamespace(given_name="A", surname="B",
                             familiar_name="AB", display_name="A B",
                             abbreviated_name="AB"),
        email_verified=True, profile_photo_url=None, disabled=False,
        country="US", locale="en", referral_link="ref")
    c.users_get_space_usage.return_value = SimpleNamespace(
        used=100, allocation=SimpleNamespace(to_dict=lambda: {
            "type": "individual", "allocated": 2000}))
    c.files_get_metadata.return_value = FileMetadata()
    return c


def _install_fake_dropbox():
    dbx = types.ModuleType("dropbox")
    exc = types.ModuleType("dropbox.exceptions")
    exc.ApiError = type("ApiError", (Exception,), {})
    exc.AuthError = type("AuthError", (Exception,), {})
    files = types.ModuleType("dropbox.files")
    files.FileMetadata = FileMetadata
    files.FolderMetadata = FolderMetadata
    files.WriteMode = SimpleNamespace(overwrite="overwrite")
    files.SearchOptions = lambda **kw: kw
    sharing = types.ModuleType("dropbox.sharing")
    sharing.SharedLinkSettings = lambda **kw: kw
    dbx.exceptions = exc
    dbx.files = files
    dbx.sharing = sharing
    dbx.Dropbox = MagicMock(side_effect=lambda token: _make_client())
    sys.modules["dropbox"] = dbx
    sys.modules["dropbox.exceptions"] = exc
    sys.modules["dropbox.files"] = files
    sys.modules["dropbox.sharing"] = sharing


_install_fake_dropbox()

from integrations import dropbox_routes as dr  # noqa: E402
from integrations.dropbox_service import dropbox_service  # noqa: E402


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"db93-{uuid.uuid4().hex[:8]}"
    u.email = "dropbox93@x.com"
    u.tenant_id = "t-1"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(dr.router)
    from core.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(dr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def token():
    """Real auth handler, valid-token behavior via method patch."""
    with patch.object(dr.dropbox_auth_handler, "ensure_valid_token",
                      new=AsyncMock(return_value="tok-93")) as tv:
        yield tv


# ── OAuth flow ───────────────────────────────────────────────────────────────
class TestOAuth:
    def test_oauth_url_success(self, anon_client):
        with patch.object(dr.dropbox_auth_handler, "get_authorization_url",
                          return_value="https://dropbox.com/oauth2/auth?x=1"):
            response = anon_client.get("/api/dropbox/oauth/url?state=s1")
        assert response.status_code == 200
        assert response.json()["authorization_url"].startswith(
            "https://dropbox.com")

    def test_oauth_url_without_state(self, anon_client):
        with patch.object(dr.dropbox_auth_handler, "get_authorization_url",
                          return_value="https://dropbox.com/oauth2/auth"):
            response = anon_client.get("/api/dropbox/oauth/url")
        assert response.status_code == 200

    def test_oauth_url_error_500(self, anon_client):
        with patch.object(dr.dropbox_auth_handler, "get_authorization_url",
                          side_effect=RuntimeError("boom")):
            response = anon_client.get("/api/dropbox/oauth/url")
        assert response.status_code == 500

    def test_callback_success(self, anon_client):
        with patch.object(
                dr.dropbox_auth_handler, "exchange_code_for_token",
                new=AsyncMock(return_value={
                    "account_id": "acct-1", "expires_in": 14400})):
            response = anon_client.get(
                "/api/dropbox/callback?code=code-1&state=s1")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["account_id"] == "acct-1"

    def test_callback_error_500(self, anon_client):
        with patch.object(
                dr.dropbox_auth_handler, "exchange_code_for_token",
                new=AsyncMock(side_effect=RuntimeError("token server down"))):
            response = anon_client.get("/api/dropbox/callback?code=code-1")
        assert response.status_code == 500

    def test_callback_http_exception_passthrough(self, anon_client):
        """Wave-93 gap: HTTPException from the auth handler re-raises as-is."""
        from fastapi import HTTPException

        with patch.object(
                dr.dropbox_auth_handler, "exchange_code_for_token",
                new=AsyncMock(side_effect=HTTPException(
                    status_code=400, detail="Internal error"))):
            response = anon_client.get("/api/dropbox/callback?code=bad")
        assert response.status_code == 400

    def test_oauth_status_success(self, anon_client):
        with patch.object(dr.dropbox_auth_handler, "get_connection_status",
                          return_value={"connected": True}):
            response = anon_client.get("/api/dropbox/oauth/status")
        assert response.status_code == 200
        assert response.json()["connected"] is True

    def test_oauth_status_error_500(self, anon_client):
        with patch.object(dr.dropbox_auth_handler, "get_connection_status",
                          side_effect=RuntimeError("boom")):
            response = anon_client.get("/api/dropbox/oauth/status")
        assert response.status_code == 500


class TestUserEndpoints:
    def test_get_user_success(self, client, token):
        with patch.object(
                dr.dropbox_auth_handler, "get_user_info",
                new=AsyncMock(return_value={"email": "a@b.c"})):
            response = client.get("/api/dropbox/user")
        assert response.status_code == 200
        assert response.json()["email"] == "a@b.c"

    def test_get_user_error_500(self, client, token):
        with patch.object(
                dr.dropbox_auth_handler, "get_user_info",
                new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.get("/api/dropbox/user")
        assert response.status_code == 500

    def test_get_user_http_exception_passthrough(self, client):
        """Wave-93 gap: token-expiry 401 from ensure_valid_token surfaces."""
        from fastapi import HTTPException

        with patch.object(
                dr.dropbox_auth_handler, "ensure_valid_token",
                new=AsyncMock(side_effect=HTTPException(
                    status_code=401, detail="No valid token available"))):
            response = client.get("/api/dropbox/user")
        assert response.status_code == 401

    def test_get_user_anonymous_401(self, anon_client):
        assert anon_client.get("/api/dropbox/user").status_code == 401

    def test_user_info_authed_success(self, client, token):
        response = client.get("/api/dropbox/user/info?user_id=u1")
        assert response.status_code == 200
        assert response.json()["operation"] == "get_user_info"

    def test_user_info_anonymous_401(self, anon_client):
        assert anon_client.get("/api/dropbox/user/info?user_id=u1"
                               ).status_code == 401

    def test_space_usage_authed_success(self, client, token):
        response = client.get("/api/dropbox/space/usage?user_id=u1")
        assert response.status_code == 200
        assert response.json()["operation"] == "get_space_usage"

    def test_space_usage_anonymous_401(self, anon_client):
        assert anon_client.get("/api/dropbox/space/usage?user_id=u1"
                               ).status_code == 401

    def test_file_metadata_authed_success(self, client, token):
        response = client.get("/api/dropbox/file_metadata?user_id=u1"
                              "&path=/f.txt&include_media_info=true")
        assert response.status_code == 200
        assert response.json()["operation"] == "get_file_metadata"

    def test_file_metadata_anonymous_401(self, anon_client):
        assert anon_client.get("/api/dropbox/file_metadata?user_id=u1"
                               "&path=/f.txt").status_code == 401

    def test_user_info_error_500(self, client, token):
        with patch.object(dropbox_service, "get_account_info",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.get("/api/dropbox/user/info?user_id=u1")
        assert response.status_code == 500

    def test_space_usage_error_500(self, client, token):
        with patch.object(dropbox_service, "get_space_usage",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.get("/api/dropbox/space/usage?user_id=u1")
        assert response.status_code == 500

    def test_file_metadata_error_500(self, client, token):
        with patch.object(dropbox_service, "get_metadata",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.get("/api/dropbox/file_metadata?user_id=u1"
                                  "&path=/f.txt")
        assert response.status_code == 500


# ── File operations (REAL service + fake SDK => RED before the fix) ─────────
class TestFileOperations:
    def test_list_files_success(self, client, token):
        response = client.post("/api/dropbox/files/list", json={
            "user_id": "u1", "path": "/", "recursive": True, "limit": 5})
        assert response.status_code == 200
        body = response.json()
        assert body["operation"] == "list_files"
        assert body["count"] == 2
        assert body["data"]["entries"][0][".tag"] == "file"

    def test_list_files_nested_path(self, client, token):
        response = client.post("/api/dropbox/files/list", json={
            "user_id": "u1", "path": "/docs"})
        assert response.status_code == 200
        assert response.json()["path"] == "/docs"

    def test_list_files_anonymous_401(self, anon_client):
        response = anon_client.post("/api/dropbox/files/list",
                                    json={"user_id": "u1"})
        assert response.status_code == 401

    def test_list_files_error_500(self, client):
        with patch.object(dropbox_service, "list_folder",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/files/list",
                                   json={"user_id": "u1"})
        assert response.status_code == 500

    def test_upload_file_success(self, client, token):
        encoded = base64.b64encode(b"hello-dropbox").decode()
        response = client.post("/api/dropbox/files/upload", json={
            "user_id": "u1", "file_name": "up.txt", "file_content": encoded,
            "path": "/docs", "autorename": False})
        assert response.status_code == 200
        assert response.json()["operation"] == "upload_file"

    def test_upload_file_error_500(self, client):
        with patch.object(dropbox_service, "upload_file",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/files/upload", json={
                "user_id": "u1", "file_name": "up.txt",
                "file_content": "YQ=="})
        assert response.status_code == 500

    def test_download_file_success(self, client, token):
        response = client.post("/api/dropbox/files/download", json={
            "user_id": "u1", "path": "/f.txt"})
        assert response.status_code == 200
        body = response.json()
        assert body["operation"] == "download_file"
        assert body["data"]["file_name"] == "f.txt"
        assert base64.b64decode(body["data"]["content_bytes"]) == \
            b"dropbox-file-bytes"

    def test_download_file_error_500(self, client):
        with patch.object(dropbox_service, "download_file",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/files/download", json={
                "user_id": "u1", "path": "/f.txt"})
        assert response.status_code == 500

    def test_search_files_success(self, client, token):
        response = client.post("/api/dropbox/files/search", json={
            "user_id": "u1", "query": "report", "path": "/", "max_results": 5})
        assert response.status_code == 200
        body = response.json()
        assert body["operation"] == "search_files"
        assert body["count"] == 1

    def test_search_files_error_500(self, client):
        with patch.object(dropbox_service, "search",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/files/search", json={
                "user_id": "u1", "query": "q"})
        assert response.status_code == 500


class TestFolderOperations:
    def test_create_folder_success(self, client, token):
        response = client.post("/api/dropbox/folders/create", json={
            "user_id": "u1", "path": "/new-folder"})
        assert response.status_code == 200
        assert response.json()["operation"] == "create_folder"

    def test_create_folder_error_500(self, client):
        with patch.object(dropbox_service, "create_folder",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/folders/create", json={
                "user_id": "u1", "path": "/nf"})
        assert response.status_code == 500

    def test_list_folders_filters_files(self, client, token):
        response = client.post("/api/dropbox/folders/list", json={
            "user_id": "u1", "path": "/"})
        assert response.status_code == 200
        body = response.json()
        assert body["operation"] == "list_folders"
        assert body["count"] == 1
        assert body["data"]["entries"][0][".tag"] == "folder"

    def test_list_folders_error_500(self, client):
        with patch.object(dropbox_service, "list_folder",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/folders/list", json={
                "user_id": "u1"})
        assert response.status_code == 500


class TestItemOperations:
    def test_delete_item_success(self, client, token):
        response = client.post("/api/dropbox/items/delete", json={
            "user_id": "u1", "path": "/old.txt"})
        assert response.status_code == 200
        assert response.json()["operation"] == "delete_item"

    def test_delete_item_error_500(self, client):
        with patch.object(dropbox_service, "delete_item",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/items/delete", json={
                "user_id": "u1", "path": "/x"})
        assert response.status_code == 500

    def test_move_item_success(self, client, token):
        response = client.post("/api/dropbox/items/move", json={
            "user_id": "u1", "from_path": "/a.txt", "to_path": "/b.txt",
            "autorename": False, "allow_ownership_transfer": True})
        assert response.status_code == 200
        assert response.json()["operation"] == "move_item"

    def test_move_item_error_500(self, client):
        with patch.object(dropbox_service, "move_item",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/items/move", json={
                "user_id": "u1", "from_path": "/a", "to_path": "/b"})
        assert response.status_code == 500

    def test_copy_item_success(self, client, token):
        response = client.post("/api/dropbox/items/copy", json={
            "user_id": "u1", "from_path": "/a.txt", "to_path": "/c.txt"})
        assert response.status_code == 200
        assert response.json()["operation"] == "copy_item"

    def test_copy_item_error_500(self, client):
        with patch.object(dropbox_service, "copy_item",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/items/copy", json={
                "user_id": "u1", "from_path": "/a", "to_path": "/c"})
        assert response.status_code == 500


class TestSharedLinks:
    def test_create_shared_link_success(self, client, token):
        response = client.post("/api/dropbox/shared_links/create", json={
            "user_id": "u1", "path": "/f.txt",
            "settings": {"requested_visibility": "public"}})
        assert response.status_code == 200
        assert response.json()["operation"] == "create_shared_link"

    def test_create_shared_link_no_settings(self, client, token):
        response = client.post("/api/dropbox/shared_links/create", json={
            "user_id": "u1", "path": "/f.txt"})
        assert response.status_code == 200

    def test_create_shared_link_error_500(self, client):
        with patch.object(
                dropbox_service, "create_shared_link",
                new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = client.post("/api/dropbox/shared_links/create", json={
                "user_id": "u1", "path": "/f.txt"})
        assert response.status_code == 500


class TestHealth:
    def test_health_ok(self, anon_client):
        response = anon_client.get("/api/dropbox/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_error_503(self, anon_client):
        """Wave-93 gap: health check exception branch (clock failure)."""
        from datetime import datetime as _dt

        class _BrokenClock(_dt):
            @classmethod
            def now(cls, *a, **k):
                raise RuntimeError("clock broken")

        with patch.object(dr, "datetime", _BrokenClock):
            response = anon_client.get("/api/dropbox/health")
        assert response.status_code == 503
