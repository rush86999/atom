"""Zoho WorkDrive org-team fallback + teams pagination (PR review follow-up).

Covers the /users/me ``preferred_team_id`` fallback that fires when GET /teams
returns empty (plain org members without admin/owner role), the warning logs
on each silent-failure path, and a regression guard for the P1 pagination bug
(page parsing must run unconditionally every iteration or listing loops
forever on the second page).

HTTP is mocked with httpx.MockTransport — no network, no respx dependency.
"""
import httpx
import pytest
from unittest.mock import AsyncMock, patch

from integrations.zoho_workdrive_service import ZohoWorkDriveService


def _team_resource(tid: str, name: str, **attrs) -> dict:
    return {
        "id": tid,
        "type": "teams",
        "attributes": {"name": name, **attrs},
    }


def _service(handler) -> ZohoWorkDriveService:
    svc = ZohoWorkDriveService(config={})
    svc.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return svc


@pytest.mark.asyncio
class TestOrgTeamFallback:
    async def test_empty_teams_with_preferred_team_id_appends_org_team(self):
        requests: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request.url.path)
            if request.url.path.endswith("/teams") and "offset" in request.url.params:
                return httpx.Response(200, json={"data": []})
            if request.url.path.endswith("/teams"):
                return httpx.Response(200, json={"data": []})
            if request.url.path.endswith("/users/me"):
                return httpx.Response(
                    200,
                    json={"data": {"id": "me-1", "attributes": {"preferred_team_id": "org-1"}}},
                )
            if request.url.path.endswith("/teams/org-1"):
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "id": "org-1-row",
                            "type": "teams",
                            "attributes": {
                                "name": "Brennan Org",
                                "shared_status": "active",
                                "role_id": "member",
                            },
                        }
                    },
                )
            return httpx.Response(404)

        svc = _service(handler)
        with patch.object(svc, "get_access_token", new=AsyncMock(return_value="tok")):
            teams = await svc.get_teams("u1")

        assert len(teams) == 1
        team = teams[0]
        assert team["id"] == "org-1-row"
        assert team["name"] == "Brennan Org"
        assert team["status"] == "active"          # shared_status fallback used
        assert team["role"] == "member"            # role_id mapped
        assert any(p.endswith("/users/me") for p in requests)
        assert any(p.endswith("/teams/org-1") for p in requests)

    async def test_empty_teams_without_preferred_team_id_returns_empty(self, caplog):
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/users/me"):
                return httpx.Response(200, json={"data": {"attributes": {}}})
            return httpx.Response(200, json={"data": []})

        svc = _service(handler)
        with patch.object(svc, "get_access_token", new=AsyncMock(return_value="tok")):
            teams = await svc.get_teams("u1")

        assert teams == []

    async def test_users_me_non_200_warns_and_returns_empty(self, caplog):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/users/me"):
                return httpx.Response(500, json={})
            return httpx.Response(200, json={"data": []})

        svc = _service(handler)
        with patch.object(svc, "get_access_token", new=AsyncMock(return_value="tok")):
            with caplog.at_level("WARNING", logger="integrations.zoho_workdrive_service"):
                teams = await svc.get_teams("u1")

        assert teams == []
        assert any("/users/me returned 500" in r.message for r in caplog.records)

    async def test_org_team_fetch_non_200_warns(self, caplog):
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/users/me"):
                return httpx.Response(
                    200,
                    json={"data": {"attributes": {"preferred_team_id": "org-404"}}},
                )
            if path.endswith("/teams/org-404"):
                return httpx.Response(404, json={})
            return httpx.Response(200, json={"data": []})

        svc = _service(handler)
        with patch.object(svc, "get_access_token", new=AsyncMock(return_value="tok")):
            with caplog.at_level("WARNING", logger="integrations.zoho_workdrive_service"):
                teams = await svc.get_teams("u1")

        assert teams == []
        assert any("org-team fetch for org-404 returned 404" in r.message for r in caplog.records)

    async def test_fallback_never_runs_when_teams_listed(self):
        """A non-empty first page must short-circuit the fallback entirely."""
        requests: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request.url.path)
            if request.url.path.endswith("/teams"):
                return httpx.Response(
                    200,
                    json={"data": [_team_resource("t1", "Team One"), _team_resource("t2", "Team Two")]},
                )
            return httpx.Response(404)

        svc = _service(handler)
        with patch.object(svc, "get_access_token", new=AsyncMock(return_value="tok")):
            teams = await svc.get_teams("u1")

        assert [t["id"] for t in teams] == ["t1", "t2"]
        assert not any(p.endswith("/users/me") for p in requests)


@pytest.mark.asyncio
class TestTeamsPaginationTerminates:
    async def test_full_page_then_short_page_parses_every_iteration(self):
        """P1 regression guard: page parsing, the termination check and the
        offset increment must run unconditionally — nesting them inside an
        `if not teams:` made the second page loop forever."""
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            offset = int(request.url.params.get("page[offset]", 0))
            calls.append(offset)
            if offset == 0:
                # Exactly PAGE_SIZE items → forces a second iteration.
                data = [
                    _team_resource(f"p1-{i}", f"Page One {i}")
                    for i in range(ZohoWorkDriveService.PAGE_SIZE)
                ]
                return httpx.Response(200, json={"data": data})
            # Short page → terminates.
            return httpx.Response(
                200,
                json={"data": [_team_resource("p2-0", "Page Two Zero")]},
            )

        svc = _service(handler)
        with patch.object(svc, "get_access_token", new=AsyncMock(return_value="tok")):
            teams = await svc.get_teams("u1")

        assert len(calls) == 2
        assert calls == [0, ZohoWorkDriveService.PAGE_SIZE]
        assert len(teams) == ZohoWorkDriveService.PAGE_SIZE + 1
        assert teams[-1]["id"] == "p2-0"

    async def test_jsonapi_normalization_uses_display_name_fallback(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "t9",
                            "type": "teams",
                            "attributes": {"display_name": "Display Only", "role": "owner"},
                        }
                    ]
                },
            )

        svc = _service(handler)
        with patch.object(svc, "get_access_token", new=AsyncMock(return_value="tok")):
            teams = await svc.get_teams("u1")

        assert teams[0]["name"] == "Display Only"
        assert teams[0]["role"] == "owner"
