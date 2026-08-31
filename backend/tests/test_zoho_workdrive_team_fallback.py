"""Zoho WorkDrive org-team fallback — teams/teamfolders WITHOUT WorkDrive.teams.*

The pilot client lacks WorkDrive.teams.* in the API Console, so GET /teams
and GET /teams/{id} 500 with F7007 "Invalid OAuth scope". The org team id
is advertised on GET /users/me (no teams scope needed) and team-folders
listing only needs WorkDrive.teamfolders.ALL (granted) — so teams + team
folders must still resolve via the /users/me -> preferred_team_id fallback
even when the /teams listing itself errors.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock


def _resp(status: int, json_body: dict, text: str = ""):
    return SimpleNamespace(
        status_code=status,
        json=lambda: json_body,
        text=text,
        raise_for_status=lambda: (_ for _ in ()).throw(
            RuntimeError(f"HTTP {status}")
        ) if status != 200 else None,
    )


ME_BODY = {
    "data": {
        "id": "110002724475",
        "type": "users",
        "attributes": {"email_id": "vishal@brennan.ca", "preferred_team_id": "team-org-1"},
    }
}

TEAMFOLDER_ITEM = {
    "id": "tf-1",
    "type": "teamfolders",
    "attributes": {"name": "Accounting", "workspace": {"id": "ws-1"}},
}


@pytest.fixture
def svc():
    from integrations.zoho_workdrive_service import ZohoWorkDriveService

    s = ZohoWorkDriveService()
    s.get_access_token = AsyncMock(return_value="tok")
    return s


class TestGetTeamsFallback:
    async def test_teams_listing_500_still_returns_org_team(self, svc):
        """GET /teams 500 (F7007, missing teams scope) must NOT return [] —
        /users/me preferred_team_id is scope-free and enough for the picker."""
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(500, {}, '{"errors":[{"id":"F7007","title":"Invalid OAuth scope."}]}'),
                _resp(200, ME_BODY),
                # team detail 500 (teams scope missing) -> id-only entry
                _resp(500, {}, "F7007"),
            ]
        )
        teams = await svc.get_teams("u1")
        assert teams, "expected the org-team fallback entry"
        assert teams[0]["id"] == "team-org-1"

    async def test_teams_listing_empty_still_returns_org_team(self, svc):
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(200, {"data": []}),
                _resp(200, ME_BODY),
                _resp(500, {}, "F7007"),
            ]
        )
        teams = await svc.get_teams("u1")
        assert teams and teams[0]["id"] == "team-org-1"


class TestGetTeamFoldersFallback:
    async def test_teams_500_falls_back_and_lists_teamfolders(self, svc):
        """/teams 500 -> /users/me -> teamfolders, without any teams scope."""
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(500, {}, "F7007"),
                _resp(200, ME_BODY),
                _resp(200, {"data": [TEAMFOLDER_ITEM]}),
            ]
        )
        folders = await svc.get_team_folders("u1")
        assert folders, "expected team folders via the fallback"
        assert folders[0]["name"] == "Accounting"
        assert folders[0]["team_id"] == "team-org-1"

    async def test_teams_200_empty_falls_back_and_lists_teamfolders(self, svc):
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(200, {"data": []}),
                _resp(200, ME_BODY),
                _resp(200, {"data": [TEAMFOLDER_ITEM]}),
            ]
        )
        folders = await svc.get_team_folders("u1")
        assert folders and folders[0]["name"] == "Accounting"
