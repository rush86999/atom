"""Zoho WorkDrive search_files + grounding rule — regression tests.

Live 2026-09-03 ("consolidated price list 2019"): the planner routed a
file question to zoho_workdrive.search, UniversalIntegrationService called
a `search_files` method that never existed on ZohoWorkDriveService, and the
AttributeError surfaced to the model as "returned nothing usable" — so it
answered it had no such file while the workbook sat on the drive. On a
later turn the same session quoted a price ($14,500.00) and rendered an
"exact row" from the workbook that existed nowhere, then confirmed the
user's corrected value ($14,145.00) just as confidently. These tests pin
both fixes: a real remote search, and a grounding contract on every LIVE
TOOL RESULTS block.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.chat_tool_planner import (
    ToolPlan,
    _GROUNDING_RULE,
    _with_grounding,
    execute_tool_plan,
)
from integrations.zoho_workdrive_service import ZohoWorkDriveService


# ── service: search_files ───────────────────────────────────────────────


def _search_payload(names):
    """JSON:API-shaped response like WorkDrive's
    /teams/{team_id}/records?search[all]=… endpoint."""
    return {
        "data": [
            {
                "id": f"file-{i}",
                "type": "files",
                "attributes": {
                    "name": n,
                    "type": "spreadsheet",
                    "extn": "xlsx",
                    "storage_info": {"size_in_bytes": 1024 * i},
                    "modified_time": "Sep 1, 10:00 AM",
                },
            }
            for i, n in enumerate(names)
        ],
        "meta": {},
    }


def _fake_response(payload):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)


def _team(team_id="team-1"):
    return {"id": team_id, "name": "Team"}


@pytest.mark.asyncio
async def test_search_files_parses_results_and_honors_limit():
    svc = ZohoWorkDriveService("default", {})
    zoho_get = AsyncMock(return_value=_fake_response(_search_payload(
        ["Consolidated Price List 2019.xlsx", "Quotes.xlsx", "Inventory.xlsx"])))
    with patch.object(svc, "_zoho_get", zoho_get), \
         patch.object(svc, "get_access_token",
                      AsyncMock(return_value="1000.tok.secret")), \
         patch.object(svc, "get_teams", AsyncMock(return_value=[_team()])):
        out = await svc.search_files("user-1", "consolidated price list", limit=2)
    assert [f["name"] for f in out] == [
        "Consolidated Price List 2019.xlsx", "Quotes.xlsx"]
    assert out[0]["id"] == "file-0" and out[0]["extension"] == "xlsx"
    assert out[0]["type"] == "file"
    # content-wide search param rides the request to the team records
    # endpoint — the endpoint verified live (GET /search is 405 there).
    url = zoho_get.await_args.args[0]
    assert url.endswith("/teams/team-1/records")
    params = zoho_get.await_args.kwargs["params"]
    assert params["search[all]"] == "consolidated price list"


@pytest.mark.asyncio
async def test_search_files_raw_token_used_directly():
    """The universal executor passes its resolved token positionally
    (mirroring google_drive). A raw Zoho token must be used as-is, not
    treated as a user id."""
    svc = ZohoWorkDriveService("default", {})
    raw = "1000." + "a" * 30 + "." + "b" * 30
    zoho_get = AsyncMock(return_value=_fake_response(_search_payload(["A.xlsx"])))
    lookup = AsyncMock(return_value="SHOULD-NOT-BE-USED")
    with patch.object(svc, "_zoho_get", zoho_get), \
         patch.object(svc, "get_access_token", lookup), \
         patch.object(svc, "get_teams", AsyncMock(return_value=[_team()])):
        out = await svc.search_files(raw, "anything")
    assert out and out[0]["name"] == "A.xlsx"
    lookup.assert_not_awaited()
    assert zoho_get.await_args.kwargs["headers"]["Authorization"] == \
        f"Zoho-oauthtoken {raw}"


@pytest.mark.asyncio
async def test_search_files_resolves_token_per_user():
    svc = ZohoWorkDriveService("default", {})
    zoho_get = AsyncMock(return_value=_fake_response(_search_payload(["B.xlsx"])))
    with patch.object(svc, "_zoho_get", zoho_get), \
         patch.object(svc, "get_access_token",
                      AsyncMock(return_value="1000.resolved.token")) as lookup, \
         patch.object(svc, "get_teams", AsyncMock(return_value=[_team()])) as teams:
        out = await svc.search_files("user-9", "price list")
    lookup.assert_awaited_once_with("user-9")
    teams.assert_awaited_once_with("user-9")
    assert out and out[0]["name"] == "B.xlsx"


@pytest.mark.asyncio
async def test_search_files_empty_query_skips_http():
    svc = ZohoWorkDriveService("default", {})
    zoho_get = AsyncMock()
    with patch.object(svc, "_zoho_get", zoho_get):
        assert await svc.search_files("user-1", "   ") == []
    zoho_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_files_fault_isolated():
    """Any failure returns [] — the planner falls back to ingested-memory
    search instead of surfacing an error shape it reads as 'no such file'."""
    svc = ZohoWorkDriveService("default", {})
    with patch.object(svc, "_zoho_get", AsyncMock(side_effect=RuntimeError("boom"))), \
         patch.object(svc, "get_access_token",
                      AsyncMock(return_value="1000.tok.secret")), \
         patch.object(svc, "get_teams", AsyncMock(return_value=[_team()])):
        assert await svc.search_files("user-1", "price list") == []


@pytest.mark.asyncio
async def test_search_files_merges_teams_and_dedupes():
    """The same workbook can live in two team folders (or be shared across
    teams); one entry per file id, teams searched in order, and a failing
    team must not sink the hits from the others."""
    svc = ZohoWorkDriveService("default", {})
    callcount = {"n": 0}

    async def zoho_get(url, *, headers, params):
        callcount["n"] += 1
        if "team-1" in url:
            return _fake_response(_search_payload(
                ["Consolidated Price List 2019.xlsx", "Quotes.xlsx"]))
        if "team-2" in url:
            raise RuntimeError("boom")
        return _fake_response({"data": [], "meta": {}})

    with patch.object(svc, "_zoho_get", AsyncMock(side_effect=zoho_get)), \
         patch.object(svc, "get_access_token",
                      AsyncMock(return_value="1000.tok.secret")), \
         patch.object(svc, "get_teams",
                      AsyncMock(return_value=[_team("team-1"), _team("team-2")])):
        out = await svc.search_files("user-1", "price list", limit=10)
    assert [f["name"] for f in out] == [
        "Consolidated Price List 2019.xlsx", "Quotes.xlsx"]


# ── universal integration service wiring ────────────────────────────────


def _stub_registry(storage_service):
    reg = MagicMock()
    reg.get_service_instance = AsyncMock(return_value=storage_service)
    return reg


@pytest.mark.asyncio
async def test_universal_storage_zoho_search_passes_acting_user():
    """The storage branch must pass the CONTEXT user (WorkDrive resolves
    tokens per user); the instance has no access_token and the executor
    context usually carries none, so the old `token`-first call passed
    None and silently emptied results."""
    from integrations.universal_integration_service import UniversalIntegrationService

    svc = UniversalIntegrationService(workspace_id="default")
    storage = MagicMock()
    storage.access_token = None
    storage.search_files = AsyncMock(return_value=[
        {"id": "f1", "name": "Consolidated Price List 2019.xlsx"}])
    ctx = {"user_id": "user-1", "tenant_id": "default",
           "registry": _stub_registry(storage)}
    result = await svc._execute_storage(
        "zoho_workdrive", "search", {"query": "consolidated price list", "limit": 8}, ctx)
    assert result["status"] == "success"
    storage.search_files.assert_awaited_once_with("user-1", "consolidated price list", limit=8)
    assert result["data"][0]["name"] == "Consolidated Price List 2019.xlsx"


@pytest.mark.asyncio
async def test_universal_search_storage_zoho_branch_returns_list():
    """_search_storage previously had no zoho_workdrive branch and fell
    through to return [] — MCP search_files fan-outs never saw WorkDrive."""
    from integrations.universal_integration_service import UniversalIntegrationService

    svc = UniversalIntegrationService(workspace_id="default")
    storage = MagicMock()
    storage.access_token = None
    storage.search_files = AsyncMock(return_value=[{"id": "f1", "name": "A.xlsx"}])
    out = await svc._search_storage(
        "zoho_workdrive", "A.xlsx",
        {"user_id": "user-1", "registry": _stub_registry(storage)})
    assert out == [{"id": "f1", "name": "A.xlsx"}]


@pytest.mark.asyncio
async def test_planner_workdrive_search_happy_path_carries_rule():
    """With the method implemented, a WorkDrive search reaches the live API
    and the evidence block carries the grounding contract."""
    plan = ToolPlan(use_tool=True, service="zoho_workdrive", intent="search",
                    query="consolidated price list", reason="file lookup")
    fake_execute = AsyncMock(return_value={
        "status": "success",
        "data": [{"id": "f1", "name": "Consolidated Price List 2019.xlsx"}],
    })
    with patch("integrations.universal_integration_service.UniversalIntegrationService.execute", fake_execute):
        block = await execute_tool_plan(plan, "user-1", "default", {})
    assert block and "Consolidated Price List 2019.xlsx" in block
    assert _GROUNDING_RULE in block


@pytest.mark.asyncio
async def test_planner_empty_result_block_carries_grounding_rule():
    """The 'returned nothing usable' block is exactly where the model used
    to conclude 'I don't have that file' — and later, where it invented
    values. The rule must ride this block too."""
    plan = ToolPlan(use_tool=True, service="zoho_workdrive", intent="search",
                    query="wg350dsav price", reason="file lookup")
    fake_execute = AsyncMock(return_value={"status": "error", "message": "boom"})
    with patch("integrations.universal_integration_service.UniversalIntegrationService.execute", fake_execute), \
         patch("core.chat_tool_planner._memory_search_block",
               AsyncMock(return_value=None)):
        block = await execute_tool_plan(plan, "user-1", "default", {})
    assert block and "returned nothing usable" in block
    assert _GROUNDING_RULE in block


@pytest.mark.asyncio
async def test_memory_block_carries_grounding_rule():
    from core.chat_tool_planner import _memory_search_block

    hit = {
        "id": "doc1", "title": "Consolidated Price List 2019.xlsx",
        "preview": "=== Sheet: Exchange-Index ===", "source": "vector",
    }
    with patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch.search",
               AsyncMock(return_value={"results": [hit], "label": "hybrid"})):
        block = await _memory_search_block("user-1", "consolidated price list 2019",
                                           {"history": []})
    assert block and "Consolidated Price List 2019" in block
    assert _GROUNDING_RULE in block


# ── grounding helper ────────────────────────────────────────────────────


def test_with_grounding_appends_rule_once():
    assert _with_grounding("EVIDENCE").endswith(_GROUNDING_RULE)
    assert _with_grounding(None) is None
    assert _with_grounding("") == ""
