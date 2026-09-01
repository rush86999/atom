"""Zoho WorkDrive org-team fallback — teams/teamfolders WITHOUT WorkDrive.teams.*

The pilot client lacks WorkDrive.teams.* in the API Console, so GET /teams
and GET /teams/{id} 500 with F7007 "Invalid OAuth scope". The org team id
is advertised on GET /users/me (no teams scope needed) and team-folders
listing only needs WorkDrive.teamfolders.ALL (granted) — so teams + team
folders must still resolve via the /users/me -> preferred_team_id fallback
even when the /teams listing itself errors.

Also guards the P1 pagination regression (page parsing must run
unconditionally every iteration) and JSON:API normalization
(display_name fallback, shared_status/role_id mapping on the
single-team endpoint).
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


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

F7007_TEXT = '{"errors":[{"id":"F7007","title":"Invalid OAuth scope."}]}'


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
                _resp(500, {}, F7007_TEXT),
                _resp(200, ME_BODY),
                # team detail 500 (teams scope missing) -> id-only entry
                _resp(500, {}, F7007_TEXT),
            ]
        )
        teams = await svc.get_teams("u1")
        assert teams, "expected the org-team fallback entry"
        assert teams[0]["id"] == "team-org-1"
        assert teams[0]["name"] == "WorkDrive Team"  # id-only entry

    async def test_teams_listing_empty_still_returns_org_team(self, svc):
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(200, {"data": []}),
                _resp(200, ME_BODY),
                _resp(500, {}, F7007_TEXT),
            ]
        )
        teams = await svc.get_teams("u1")
        assert teams and teams[0]["id"] == "team-org-1"

    async def test_fallback_never_runs_when_teams_listed(self, svc):
        """A non-empty first page must short-circuit the fallback entirely."""
        calls: list[str] = []

        def handler(url: str, **kwargs):
            calls.append(url)
            return _resp(
                200,
                {
                    "data": [
                        {"id": "t1", "type": "teams", "attributes": {"name": "Team One"}},
                        {"id": "t2", "type": "teams", "attributes": {"name": "Team Two"}},
                    ]
                },
            )

        svc.client.get = AsyncMock(side_effect=handler)
        teams = await svc.get_teams("u1")
        assert [t["id"] for t in teams] == ["t1", "t2"]
        assert not any("/users/me" in u for u in calls)

    async def test_users_me_non_200_warns_and_returns_empty(self, svc, caplog):
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(200, {"data": []}),
                _resp(500, {}, "boom"),
            ]
        )
        with caplog.at_level("WARNING", logger="integrations.zoho_workdrive_service"):
            teams = await svc.get_teams("u1")
        assert teams == []
        assert any("/users/me returned 500" in r.message for r in caplog.records)

    async def test_org_team_detail_non_200_appends_id_only_entry(self, svc, caplog):
        """/teams/{id} 404/500 (teams scope missing) must still yield an
        id-only entry — the id alone drives the teamfolders listing."""
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(200, {"data": []}),
                _resp(200, ME_BODY),
                _resp(404, {}, "nope"),
            ]
        )
        with caplog.at_level("WARNING", logger="integrations.zoho_workdrive_service"):
            teams = await svc.get_teams("u1")
        assert [t["id"] for t in teams] == ["team-org-1"]
        assert teams[0]["name"] == "WorkDrive Team"
        assert any("using id-only entry" in r.message for r in caplog.records)

    async def test_org_team_detail_200_maps_shared_status_and_role_id(self, svc):
        """The single-team endpoint uses different attribute names — status
        falls back to shared_status, role comes from role_id."""
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(200, {"data": []}),
                _resp(200, ME_BODY),
                _resp(
                    200,
                    {
                        "data": {
                            "id": "team-org-1",
                            "type": "teams",
                            "attributes": {
                                "name": "Brennan Org",
                                "shared_status": "active",
                                "role_id": "member",
                            },
                        }
                    },
                ),
            ]
        )
        teams = await svc.get_teams("u1")
        assert len(teams) == 1
        assert teams[0]["name"] == "Brennan Org"
        assert teams[0]["status"] == "active"
        assert teams[0]["role"] == "member"

    async def test_jsonapi_normalization_uses_display_name_fallback(self, svc):
        def handler(url: str, **kwargs):
            return _resp(
                200,
                {
                    "data": [
                        {
                            "id": "t9",
                            "type": "teams",
                            "attributes": {"display_name": "Display Only", "role": "owner"},
                        }
                    ]
                },
            )

        svc.client.get = AsyncMock(side_effect=handler)
        teams = await svc.get_teams("u1")
        assert teams[0]["name"] == "Display Only"
        assert teams[0]["role"] == "owner"

    async def test_full_page_then_short_page_parses_every_iteration(self, svc):
        """P1 regression guard: page parsing, the termination check and the
        offset increment must run unconditionally — nesting them inside an
        `if not teams:` made the second page loop forever."""
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        calls: list[int] = []

        def handler(url: str, **kwargs):
            offset = int(kwargs["params"]["page[offset]"])
            calls.append(offset)
            if offset == 0:
                # Exactly PAGE_SIZE items -> forces a second iteration.
                data = [
                    {"id": f"p1-{i}", "type": "teams", "attributes": {"name": f"Page One {i}"}}
                    for i in range(ZohoWorkDriveService.PAGE_SIZE)
                ]
                return _resp(200, {"data": data})
            return _resp(
                200,
                {"data": [{"id": "p2-0", "type": "teams", "attributes": {"name": "Page Two Zero"}}]},
            )

        svc.client.get = AsyncMock(side_effect=handler)
        teams = await svc.get_teams("u1")
        assert len(calls) == 2
        assert calls == [0, ZohoWorkDriveService.PAGE_SIZE]
        assert len(teams) == ZohoWorkDriveService.PAGE_SIZE + 1
        assert teams[-1]["id"] == "p2-0"


class TestGetTeamFoldersFallback:
    async def test_teams_500_falls_back_and_lists_teamfolders(self, svc):
        """/teams 500 -> /users/me -> teamfolders, without any teams scope."""
        svc.client.get = AsyncMock(
            side_effect=[
                _resp(500, {}, F7007_TEXT),
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
