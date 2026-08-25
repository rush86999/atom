"""Service-level tests for Zoho WorkDrive team discovery fallback.

RED case: `GET /api/v1/teams` returns `{"data":[]}` for users who are plain
members of their org's team (no admin/owner role) — the previous code returned
[] and the UI never saw the org's team folders. Fixed by falling back to
`/users/me` -> `preferred_team_id`, then listing that team's folders, and by
listing a team folder's files via `/teamfolders/{id}/files` (team folders have
no `workspace_id`).
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from integrations.zoho_workdrive_service import ZohoWorkDriveService


class _FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data if data is not None else {}
        self.text = ""

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _service(responses):
    svc = ZohoWorkDriveService(
        tenant_id="default",
        config={"client_id": "cid", "client_secret": "cs", "redirect_uri": "uri"},
    )
    svc.get_access_token = AsyncMock(return_value="tok")
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses)
    svc.client = client
    return svc, client


TEAMS_EMPTY = {"data": []}
ME_WITH_TEAM = {"data": {"attributes": {"preferred_team_id": "team-1"}}}
TEAM_1 = {
    "data": {
        "id": "team-1",
        "type": "teams",
        "attributes": {"name": "Brennan Machinery Inc.", "status": "ACTIVE", "role_id": 30},
    }
}


async def test_get_teams_falls_back_to_preferred_team_when_list_empty():
    svc, client = _service(
        [
            _FakeResponse(200, TEAMS_EMPTY),
            _FakeResponse(200, ME_WITH_TEAM),
            _FakeResponse(200, TEAM_1),
        ]
    )
    teams = await svc.get_teams("u1")
    assert teams == [
        {"id": "team-1", "name": "Brennan Machinery Inc.", "type": "teams", "status": "ACTIVE", "role": 30}
    ]
    urls = [c.args[0] for c in client.get.await_args_list]
    assert urls == [
        f"{svc.base_url}/teams",
        f"{svc.base_url}/users/me",
        f"{svc.base_url}/teams/team-1",
    ]


async def test_get_teams_returns_list_when_not_empty():
    svc, client = _service(
        [
            _FakeResponse(200, {"data": [{"id": "t1", "attributes": {"name": "Team A"}}]}),
        ]
    )
    teams = await svc.get_teams("u1")
    assert teams == [{"id": "t1", "name": "Team A", "type": "teams", "status": None, "role": None}]
    assert len(client.get.await_args_list) == 1  # no /users/me fallback call


async def test_get_team_folders_falls_back_to_preferred_team():
    tf_item = {
        "id": "tf1",
        "type": "teamfolders",
        "attributes": {"name": "Accounting", "workspace": {"id": "ws1"}},
    }
    svc, client = _service(
        [
            _FakeResponse(200, TEAMS_EMPTY),
            _FakeResponse(200, ME_WITH_TEAM),
            _FakeResponse(200, {"data": [tf_item]}),
        ]
    )
    folders = await svc.get_team_folders("u1")
    assert folders and folders[0]["name"] == "Accounting"
    assert folders[0]["workspace_id"] == "ws1"
    urls = [c.args[0] for c in client.get.await_args_list]
    assert urls[-1] == f"{svc.base_url}/teams/team-1/teamfolders"


async def test_get_team_folders_explicit_team_id_skips_fallback():
    tf_item = {
        "id": "tf1",
        "type": "teamfolders",
        "attributes": {"name": "General", "workspace": None},
    }
    svc, client = _service(
        [
            _FakeResponse(200, {"data": [tf_item]}),
        ]
    )
    folders = await svc.get_team_folders("u1", team_id="team-9")
    assert folders and folders[0]["name"] == "General"
    assert folders[0]["workspace_id"] is None
    assert len(client.get.await_args_list) == 1
    assert client.get.await_args_list[0].args[0] == f"{svc.base_url}/teams/team-9/teamfolders"


async def test_list_files_team_folder_uses_teamfolders_endpoint():
    svc, client = _service(
        [
            _FakeResponse(
                200,
                {"data": [{"id": "file1", "attributes": {"name": "a.pdf", "type": "file"}}]},
            ),
        ]
    )
    files = await svc.list_files("u1", parent_id="tf1", team_id="team-1")
    assert files == [
        {"id": "file1", "name": "a.pdf", "type": "file", "extension": None, "size": 0, "modified_at": None}
    ]
    assert client.get.await_args_list[0].args[0] == f"{svc.base_url}/teamfolders/tf1/files"


async def test_list_files_team_root_without_teamfolder_id_still_tries_root_workspace():
    svc, client = _service(
        [
            _FakeResponse(200, {"data": {"attributes": {"root_workspace": {"id": "wsX"}}}}),
            _FakeResponse(200, {"data": [{"id": "f2", "attributes": {"name": "b.xlsx", "type": "file"}}]}),
        ]
    )
    files = await svc.list_files("u1", parent_id="root", team_id="team-1")
    assert files and files[0]["name"] == "b.xlsx"
    urls = [c.args[0] for c in client.get.await_args_list]
    assert urls[0] == f"{svc.base_url}/teams/team-1"
    assert urls[1] == f"{svc.base_url}/workspaces/wsX/files"


async def test_list_files_recursive_subfolders_use_files_endpoint():
    svc, client = _service(
        [
            _FakeResponse(
                200,
                {
                    "data": [
                        {"id": "f1", "attributes": {"name": "a.pdf", "type": "file"}},
                        {"id": "sub1", "attributes": {"name": "sub", "type": "folder"}},
                    ]
                },
            ),
            _FakeResponse(
                200,
                {"data": [{"id": "f2", "attributes": {"name": "b.pdf", "type": "file"}}]},
            ),
        ]
    )
    files = await svc.list_files("u1", parent_id="tf1", team_id="team-1", recursive=True)
    assert {f["name"] for f in files} == {"a.pdf", "sub", "b.pdf"}
    urls = [c.args[0] for c in client.get.await_args_list]
    assert urls[0] == f"{svc.base_url}/teamfolders/tf1/files"
    assert urls[1] == f"{svc.base_url}/files/sub1/files"


async def test_download_file_uses_fresh_redirect_following_client():
    """download_file must not reuse the shared pool (stale keep-alive hangs)
    and must follow the signed-URL redirect."""
    from unittest.mock import patch as _patch

    svc = ZohoWorkDriveService(
        tenant_id="default",
        config={"client_id": "cid", "client_secret": "cs", "redirect_uri": "uri"},
    )
    svc.get_access_token = AsyncMock(return_value="tok")

    fake_resp = _FakeResponse(200, {})
    fake_resp.content = b"%PDF-1.6 fake-content"
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)

    class _FakeAsyncClient:
        last_kwargs = None

        def __init__(self, **kwargs):
            _FakeAsyncClient.last_kwargs = kwargs

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            return False

    with _patch("integrations.zoho_workdrive_service.httpx.AsyncClient", _FakeAsyncClient):
        content = await svc.download_file("u1", "f1")

    assert content == b"%PDF-1.6 fake-content"
    assert fake_client.get.await_args_list[0].args[0] == f"{svc.base_url}/download/f1"
    assert _FakeAsyncClient.last_kwargs.get("follow_redirects") is True


async def test_download_file_returns_none_on_failure():
    from unittest.mock import patch as _patch

    svc = ZohoWorkDriveService(
        tenant_id="default",
        config={"client_id": "cid", "client_secret": "cs", "redirect_uri": "uri"},
    )
    svc.get_access_token = AsyncMock(return_value="tok")

    class _FakeAsyncClient:
        async def __aenter__(self):
            return MagicMock(get=AsyncMock(side_effect=RuntimeError("download failed")))

        async def __aexit__(self, *args):
            return False

    with _patch("integrations.zoho_workdrive_service.httpx.AsyncClient", _FakeAsyncClient):
        content = await svc.download_file("u1", "f1")

    assert content is None
